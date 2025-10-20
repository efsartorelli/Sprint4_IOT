# 🔐 Challenge Sprint - IOT

## 💡 Grupo

- NICOLAS BONI(R551965)
- ENZO SARTORELLI(RM94618)
- EDUARDO NISTAL(RM94524)
- KAUE PASTORI(RM98501)
- RODRIGO VIANA(551057)

Interface gráfica (GUI) em **Python/Tkinter** para executar dois scripts da Sprint de IoT com **modo escuro**, **botões azuis**, **relógio** e **log em tempo real**, sem abrir janelas de console.

> **Scripts controlados pela GUI**
> - `pythonm.py` — **Iniciar programa**
> - `import_registros_supabase.py` — **Mandar informações para o banco de dados**


## 📂 Estrutura sugerida de pastas

```
C:\sprint\iot\
├─ iot_launcher_gui.py                # GUI (dark mode) para rodar os scripts
├─ start_iot_gui_silent.bat           # Inicia a GUI sem abrir console (recomendado)
├─ start_iot_gui_hidden.vbs           # Alternativa 100% sem console (WSH)
├─ pythonm.py                         # Script 1 (seu programa principal)
└─ import_registros_supabase.py       # Script 2 (envio de registros ao banco/Supabase)
```

---

## ✨ Funcionalidades da solução

- **GUI moderna (dark mode)** com **botões azuis** e layout clean.
- **Relógio** (HH:MM:SS) no topo, sem data.
- **Dois botões de ação**:
  - **Iniciar programa** → executa `pythonm.py`
  - **Mandar informações para o banco de dados** → executa `import_registros_supabase.py`
- **Log em tempo real** (stdout/stderr unificado), com mensagens de sucesso/erro e destaque de cores.
- **Sem console**: uso de `CREATE_NO_WINDOW` no subprocesso + opções de inicialização **.BAT/.VBS** para não exibir CMD.
- **Compatibilidade de encoding**: força `UTF-8` no processo filho (`PYTHONIOENCODING`/`PYTHONUTF8`) e leitura com `errors="replace"` (evita travar por acentos).
- **CWD correto**: cada script roda no **diretório do próprio arquivo**, garantindo que **paths relativos** funcionem (abrir CSV, .env, etc.).
- **Botões com bloqueio durante execução** para evitar processos simultâneos.

---

## 🛠️ Pré‑requisitos


- **Python 3.8+**
  - De preferência com o **Python Launcher** (`py`) e **pythonw** no `PATH`.
- Tkinter já vem com o Python padrão do Windows.

> Tool **venv**.

---

## ⚙️ Configuração rápida

1. Copie os arquivos para `C:\sprint\iot\` (ou ajuste os caminhos dentro do `iot_launcher_gui.py`):
   ```python
   SCRIPT_1_PATH = r"C:/sprint/iot/pythonm.py"
   SCRIPT_2_PATH = r"C:/sprint/iot/import_registros_supabase.py"
   # se tiver venv:
   INTERPRETER_1 = r"C:/sprint/iot/.venv/Scripts/python.exe"  # opcional
   INTERPRETER_2 = r"C:/sprint/iot/.venv/Scripts/python.exe"  # opcional
   ```

2. Cole este **patch de encoding** no topo dos seus scripts `pythonm.py` e `import_registros_supabase.py`:
   ```python
   # -*- coding: utf-8 -*-
   import sys, io

   try:
       enc = (sys.stdout.encoding or "").lower()
   except Exception:
       enc = ""

   if enc != "utf-8":
       if hasattr(sys.stdout, "buffer"):
           sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
       if hasattr(sys.stderr, "buffer"):
           sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
   ```

---

## ▶️ Como executar (sem abrir CMD)

### Execute o arquvio .vbs
Dê duplo clique em:
```
Challenge sprint iot.vbs
```
**clique em `iniciar programa` para dar inicio.**
- Dentro do sistema clique em `ver registro anterior` para visualizar registros anteriores.
- Clique em `iniciar programa` para iniciar a verificação facial.
- Clique `ESC` para fechar.

**clique em `Mandar informações para banco de dados` para dar inicio.**
- Todos os registros realizados serão enviados para o banco.

---

## 🧪 Como funciona por baixo dos panos

- Subprocessos são iniciados com:
  - **`cwd`** = pasta do script alvo (corrige caminhos relativos).
  - **`-u`** (unbuffered) para log sair na hora.
  - **`PYTHONIOENCODING=utf-8`** e **`PYTHONUTF8=1`** forçados no ambiente do filho.
  - **`CREATE_NO_WINDOW`** no Windows (evita abrir console dos filhos).
- A GUI tenta usar o **`py` launcher** (mesmo ambiente do duplo-clique). Caso não exista, usa o **Python** da própria GUI, ou o que você apontar nas variáveis `INTERPRETER_*`.

---




