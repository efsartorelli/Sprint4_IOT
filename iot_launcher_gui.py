#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher GUI (dark mode) para dois scripts, com relógio, log em tempo real
e execução sem abrir console.
- Botões:
  - "Iniciar programa" -> C:/sprint/iot/pythonm.py
  - "Mandar informações para o banco de dados" -> C:/sprint/iot/import_registros_supabase.py

Ajustes principais:
- Define cwd do subprocesso como a pasta do script (corrige paths relativos).
- Usa '-u' (desbufferizado) para log em tempo real.
- Tenta usar 'py' (mesmo ambiente do duplo-clique) com fallback.
- Força UTF-8 no filho (PYTHONIOENCODING/PYTHONUTF8) e lê com errors="replace".
- Esconde console extra (CREATE_NO_WINDOW).
"""

import sys, os, threading, queue, subprocess
from shutil import which
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext

# === Config ===
SCRIPT_1_PATH = r"C:/sprint/iot/pythonm.py"
SCRIPT_2_PATH = r"C:/sprint/iot/import_registros_supabase.py"

# Se tiver venv específico, informe aqui (senão deixe None)
INTERPRETER_1 = None  # ex.: r"C:/sprint/iot/.venv/Scripts/python.exe"
INTERPRETER_2 = None
PREFER_PY_LAUNCHER = True

SCRIPT_1_PATH = os.path.normpath(SCRIPT_1_PATH)
SCRIPT_2_PATH = os.path.normpath(SCRIPT_2_PATH)

# === Paleta (dark) ===
BG = "#0b0c0f"; PANEL = "#111318"; FG = "#e5e7eb"; FG_DIM = "#9ca3af"
PRIMARY = "#2563eb"; PRIMARY_HOVER = "#1d4ed8"; OK="#22c55e"; WARN="#f59e0b"; ERR="#ef4444"
FONT_TITLE=("Segoe UI",22,"bold"); FONT_CLOCK=("Segoe UI",14,"bold")
FONT_SUB=("Segoe UI",10); FONT_BTN=("Segoe UI",11,"bold"); FONT_MONO=("Consolas",11)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Challenge Sprint - IOT")
        self.geometry("900x560"); self.minsize(760,480); self.configure(bg=BG)

        style=ttk.Style(self)
        try:
            if "clam" in style.theme_names(): style.theme_use("clam")
        except: pass
        style.configure("Dark.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Dark.TLabel", background=BG, foreground=FG)
        style.configure("Dim.TLabel", background=BG, foreground=FG_DIM)
        self.option_add("*Button.Font", FONT_BTN)

        self.log_queue=queue.Queue(); self.current_process=None; self.reader_thread=None
        self._build_header(); self._build_controls(); self._build_log()
        self._tick_clock(); self.after(60,self._drain_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        header=ttk.Frame(self,style="Dark.TFrame",padding=(18,16,18,10))
        header.grid(row=0,column=0,sticky="ew")
        header.columnconfigure(0,weight=1); header.columnconfigure(1,weight=0)
        ttk.Label(header,text="Challenge Sprint - IOT",style="Dark.TLabel",font=FONT_TITLE)\
            .grid(row=0,column=0,sticky="w")
        self.clock_lbl=ttk.Label(header,text="--:--:--",style="Dark.TLabel",font=FONT_CLOCK)
        self.clock_lbl.grid(row=0,column=1,sticky="e",padx=(12,0))
        ttk.Label(header,text="Execute os programas e acompanhe o log.",
                  style="Dim.TLabel",font=FONT_SUB)\
            .grid(row=1,column=0,columnspan=2,sticky="w",pady=(6,0))

    def _build_controls(self):
        controls=ttk.Frame(self,style="Dark.TFrame",padding=(18,2,18,8))
        controls.grid(row=1,column=0,sticky="ew")
        for i in range(6): controls.columnconfigure(i,weight=1)

        self.btn_run1=self._make_primary_button(
            controls,"Iniciar programa",
            lambda:self._run_script(SCRIPT_1_PATH,INTERPRETER_1,"Iniciar programa")
        )
        self.btn_run1.grid(row=0,column=0,columnspan=2,sticky="ew",padx=(0,8),ipady=6)

        self.btn_run2=self._make_primary_button(
            controls,"Mandar informações para o banco de dados",
            lambda:self._run_script(SCRIPT_2_PATH,INTERPRETER_2,"Mandar informações para o banco de dados")
        )
        self.btn_run2.grid(row=0,column=2,columnspan=3,sticky="ew",padx=(8,8),ipady=6)

        self.btn_clear=self._make_secondary_button(controls,"Limpar log",self._clear_log)
        self.btn_clear.grid(row=0,column=5,sticky="ew",padx=(8,0),ipady=6)

    def _make_primary_button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,
                         bg=PRIMARY,fg="#fff",activebackground=PRIMARY_HOVER,
                         activeforeground="#fff",relief="flat",bd=0,padx=16,pady=8,
                         highlightthickness=0,cursor="hand2")

    def _make_secondary_button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,
                         bg="#1f2937",fg=FG,activebackground="#374151",
                         activeforeground=FG,relief="flat",bd=0,padx=16,pady=8,
                         highlightthickness=0,cursor="hand2")

    def _build_log(self):
        wrap=ttk.Frame(self,style="Dark.TFrame",padding=(18,8,18,18))
        wrap.grid(row=2,column=0,sticky="nsew")
        self.rowconfigure(2,weight=1); wrap.columnconfigure(0,weight=1); wrap.rowconfigure(0,weight=1)

        panel=ttk.Frame(wrap,style="Panel.TFrame",padding=10)
        panel.grid(row=0,column=0,sticky="nsew")
        panel.columnconfigure(0,weight=1); panel.rowconfigure(0,weight=1)

        self.log=scrolledtext.ScrolledText(
            panel,wrap="word",font=FONT_MONO,background=PANEL,foreground=FG,insertbackground=FG,
            borderwidth=0,relief="flat",highlightthickness=0,padx=8,pady=8,height=18
        )
        self.log.grid(row=0,column=0,sticky="nsew")
        self.log.tag_configure("header",foreground=FG,font=("Consolas",11,"bold"))
        self.log.tag_configure("ok",foreground=OK)
        self.log.tag_configure("warn",foreground=WARN)
        self.log.tag_configure("err",foreground=ERR)
        self.log.tag_configure("dim",foreground=FG_DIM)
        self.log.configure(state="disabled")

    def _append_log(self,text,tag=None):
        self.log.configure(state="normal")
        self.log.insert("end",text,tag) if tag else self.log.insert("end",text)
        self.log.see("end"); self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal"); self.log.delete("1.0","end"); self.log.configure(state="disabled")

    def _tick_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000,self._tick_clock)

    def _disable_buttons(self,disabled=True):
        state="disabled" if disabled else "normal"
        for b in (self.btn_run1,self.btn_run2,self.btn_clear): b.configure(state=state)

    def _on_close(self):
        if self.current_process and self.current_process.poll() is None:
            try: self.current_process.terminate()
            except: pass
        self.destroy()

    # Escolhe intérprete e comando
    def _build_cmd(self,script_path,interpreter_override=None):
        if interpreter_override and os.path.isfile(interpreter_override):
            return [interpreter_override,"-u",script_path], interpreter_override
        if PREFER_PY_LAUNCHER and which("py"):
            return ["py","-u",script_path], "py"
        return [sys.executable,"-u",script_path], sys.executable

    # Executa script
    def _run_script(self,script_path,interpreter_override=None,label="Script"):
        if not os.path.isfile(script_path):
            self._append_log(f"[{label}] Caminho não encontrado: {script_path}\n","err"); return
        if self.current_process and self.current_process.poll() is None:
            self._append_log("Já existe um processo em execução. Aguarde terminar.\n","warn"); return

        script_dir=os.path.dirname(script_path) or None
        cmd,used_interp=self._build_cmd(script_path,interpreter_override)

        self._clear_log()
        self._append_log(f"=== {label} ===\n","header")
        self._append_log(f"Interpreter: {used_interp}\n","dim")
        self._append_log(f"CWD: {script_dir or os.getcwd()}\n","dim")
        self._append_log(f"Script: {script_path}\n","dim")
        self._append_log(f"Forçando IO em UTF-8 (PYTHONIOENCODING, PYTHONUTF8)\n\n","dim")

        creationflags=0
        if os.name=="nt":
            try: creationflags=subprocess.CREATE_NO_WINDOW
            except: creationflags=0

        env=os.environ.copy()
        env["PYTHONIOENCODING"]="utf-8"
        env["PYTHONUTF8"]="1"

        try:
            self.current_process=subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=creationflags, cwd=script_dir, env=env
            )
        except Exception as e:
            self._append_log(f"Falha ao iniciar o processo: {e}\n","err"); return

        self._disable_buttons(True)
        self.reader_thread=threading.Thread(target=self._reader_loop,daemon=True)
        self.reader_thread.start()
        self.after(200,self._check_process_end)

    def _reader_loop(self):
        try:
            assert self.current_process and self.current_process.stdout
            for line in self.current_process.stdout:
                self.log_queue.put(line)
        except Exception as e:
            self.log_queue.put(f"[log] erro ao ler a saída: {e}\n")

    def _drain_log_queue(self):
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        finally:
            self.after(80,self._drain_log_queue)

    def _check_process_end(self):
        if not self.current_process:
            self._disable_buttons(False); return
        code=self.current_process.poll()
        if code is None:
            self.after(200,self._check_process_end); return
        if code==0: self._append_log("\n[OK] Processo finalizado com sucesso.\n","ok")
        else: self._append_log(f"\n[ERRO] Processo terminou com código {code}.\n","err")
        self._disable_buttons(False); self.current_process=None; self.reader_thread=None

def main():
    app=App(); app.mainloop()

if __name__=="__main__":
    main()
