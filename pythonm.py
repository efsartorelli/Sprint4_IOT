# -*- coding: utf-8 -*-
import cv2
import face_recognition
import time
import csv
import os
import numpy as np
from collections import deque
import math

# ===================== CONFIG =====================
SERIAL_PORT = 'COM3'
SERIAL_BAUD = 9600
VIDEO_SOURCE = "video.mp4"
CHECK_INTERVAL_S = 0.8          
CSV_PATH = "registro.csv"

# Paleta/cores
COL_TEXT  = (242, 244, 248)
COL_HINT  = (195, 200, 210)
COL_BASE  = (35, 37, 45)     # fundo menu
COL_HL    = (70, 110, 160)   # vinheta do menu
COL_FOOT  = (24, 25, 31)

COL_BTN_BASE   = (72, 76, 96)
COL_BTN_HOVER  = (94, 100, 126)
COL_BTN_PRESS  = (56, 60, 78)
COL_BTN_BORDER = (120, 126, 150)

COL_CLOCK_FILL   = (54, 58, 75)
COL_CLOCK_BORDER = (120, 126, 150)

# Dashboard
COL_CARD = (45, 45, 55)
COL_BORDER = (70, 70, 80)
COL_MUTED = (170, 170, 170)
COL_OK = (0, 200, 0)
COL_BAD = (20, 60, 255)
COL_DIV = (60, 60, 70)

# Tamanhos
MENU_W, MENU_H = 1100, 600
DASH_W, DASH_H = 760, 560   # mais espaco pro dashboard

# ===================== ESTADO DASHBOARD =====================
known_faces = []          # encodings conhecidos
face_ids = []             # rotulos "Rosto 1", "Rosto 2", ...
face_counts = {}          # contagem de aparicoes por rosto
events = deque(maxlen=18) # ultimos eventos
next_face_number = 1

# ===================== CSV (DATA + HORA) =====================
def ensure_csv_header():
    need_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    if need_header:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["data", "hora", "id", "status", "primeira_vez", "ocorrencia"])

def save_event_csv(e):
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([e["data"], e["hora"], e["id"],
                        e["status"], "sim" if e["primeira_vez"] else "nao", e["n"]])
    except Exception as ex:
        print("Falha ao salvar registro.csv:", ex)

def read_all_events_csv():
    if not os.path.exists(CSV_PATH):
        return []
    rows = []
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            r = list(csv.reader(f))
            if len(r) <= 1:
                return []
            for row in r[1:]:
                if len(row) == 6:
                    rows.append(row)
                elif len(row) == 5:
                    # legado (sem data)
                    rows.append(["", row[0], row[1], row[2], row[3], row[4]])
    except Exception as ex:
        print("Falha ao ler registro.csv:", ex)
    return rows

# ===================== ROSTOS =====================
def get_or_create_face_id(encoding, tol=0.5):
    global next_face_number
    if known_faces:
        dists = face_recognition.face_distance(known_faces, encoding)
        idx = int(np.argmin(dists))
        if dists[idx] < tol:
            return face_ids[idx], False
    face_id = f"Rosto {next_face_number}"
    next_face_number += 1
    known_faces.append(encoding)
    face_ids.append(face_id)
    face_counts[face_id] = 0
    return face_id, True

# ===================== UTILS GRAFICOS =====================
def draw_dot(img, center, color, r=6):
    cv2.circle(img, center, r, color, -1)
    cv2.circle(img, center, r, (0, 0, 0), 1)

def draw_header(img, text, subtext=None):
    cv2.putText(img, text, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, COL_TEXT, 2)
    if subtext:
        cv2.putText(img, subtext, (20, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)

def rounded_box(img, rect, radius, fill, border=None, shadow=False):
    x1, y1, x2, y2 = rect
    w, h = x2 - x1, y2 - y1
    r = max(10, min(radius, min(w, h)//2))
    if shadow:
        ov = img.copy()
        cv2.rectangle(ov, (x1+6, y1+8), (x2+6, y2+8), (0,0,0), -1)
        cv2.addWeighted(ov, 0.22, img, 0.78, 0, img)
    cv2.rectangle(img, (x1+r, y1), (x2-r, y2), fill, -1)
    cv2.rectangle(img, (x1, y1+r), (x2, y2-r), fill, -1)
    cv2.circle(img, (x1+r, y1+r), r, fill, -1)
    cv2.circle(img, (x2-r, y1+r), r, fill, -1)
    cv2.circle(img, (x1+r, y2-r), r, fill, -1)
    cv2.circle(img, (x2-r, y2-r), r, fill, -1)
    if border is not None:
        cv2.rectangle(img, (x1+r, y1), (x2-r, y2), border, 1)
        cv2.rectangle(img, (x1, y1+r), (x2, y2-r), border, 1)
        cv2.ellipse(img, (x1+r, y1+r), (r, r), 0, 180, 270, border, 1)
        cv2.ellipse(img, (x2-r, y1+r), (r, r), 0, 270, 360, border, 1)
        cv2.ellipse(img, (x1+r, y2-r), (r, r), 0, 90, 180, border, 1)
        cv2.ellipse(img, (x2-r, y2-r), (r, r), 0, 0, 90, border, 1)

# ===================== DASHBOARD (colunas com espaco maior p/ data+hora) =====================
def draw_dashboard(rosto_autorizado):
    dash = np.full((DASH_H, DASH_W, 3), (28, 28, 34), dtype=np.uint8)

    draw_header(dash, "Dashboard de Acesso", "ESC para sair")

    # card: autorizado
    card_x, card_y, card_w, card_h = 20, 70, DASH_W - 40, 96
    rounded_box(dash, (card_x, card_y, card_x+card_w, card_y+card_h),
                12, COL_CARD, COL_BORDER, shadow=True)

    auth_id = "nenhum"
    color_dot = (120, 120, 120)
    if rosto_autorizado is not None and len(known_faces) > 0:
        dists = face_recognition.face_distance(known_faces, rosto_autorizado)
        idx = int(np.argmin(dists))
        if dists[idx] < 0.5:
            auth_id = face_ids[idx]
            color_dot = COL_OK

    draw_dot(dash, (card_x + 24, card_y + 50), color_dot, r=9)
    cv2.putText(dash, "Autorizado:", (card_x + 44, card_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, COL_MUTED, 2)
    cv2.putText(dash, f"{auth_id}", (card_x + 44, card_y + 68),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, COL_TEXT, 2)

    cv2.line(dash, (20, 185), (DASH_W - 20, 185), COL_DIV, 1)
    cv2.putText(dash, "Ultimos eventos", (20, 210),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, COL_TEXT, 2)

    # ---- colunas COM MAIS ESPACO ----
    y0 = 238
    X_DATA = 20
    X_HORA = 160    # antes 110 -> agora 160 (mais espaco pra data)
    X_ROST = 240
    X_STAT = 360
    X_OCC  = 500
    X_PV   = 620

    cv2.putText(dash, "Data", (X_DATA, y0),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)
    cv2.putText(dash, "Hora", (X_HORA, y0),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)
    cv2.putText(dash, "Rosto", (X_ROST, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)
    cv2.putText(dash, "Status", (X_STAT, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)
    cv2.putText(dash, "Ocorrencia", (X_OCC, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)
    cv2.putText(dash, "1a vez", (X_PV, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_MUTED, 1)

    y = y0 + 26
    row_h = 26
    for e in list(events)[:12]:
        cv2.line(dash, (20, y+7), (DASH_W - 20, y+7), (40, 40, 46), 1)
        cv2.putText(dash, e["data"], (X_DATA, y),  cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        cv2.putText(dash, e["hora"], (X_HORA, y),  cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        cv2.putText(dash, e["id"],   (X_ROST, y),  cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        col = COL_OK if e["status"] == "Aprovado" else COL_BAD
        draw_dot(dash, (X_STAT-5, y-6), col, r=5)
        cv2.putText(dash, e["status"], (X_STAT+10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        cv2.putText(dash, f"#{e['n']}", (X_OCC, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        cv2.putText(dash, "sim" if e["primeira_vez"] else "nao", (X_PV, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, COL_TEXT, 1)
        y += row_h

    cv2.imshow("Dashboard", dash)

# ===================== MENU =====================
menu_selection = {"choice": None, "mx": -1, "my": -1}
hover_anim = {"view": 0.0, "start": 0.0}
_last_t = time.time()

# botoes (pos calculada em tempo de desenho)
BTN_VIEW  = (0, 0, 0, 0)
BTN_START = (0, 0, 0, 0)

def on_menu_mouse(event, x, y, flags, param):
    menu_selection["mx"], menu_selection["my"] = x, y
    if event == cv2.EVENT_LBUTTONDOWN:
        if BTN_VIEW[0] <= x <= BTN_VIEW[2] and BTN_VIEW[1] <= y <= BTN_VIEW[3]:
            menu_selection["choice"] = "view"
        elif BTN_START[0] <= x <= BTN_START[2] and BTN_START[1] <= y <= BTN_START[3]:
            menu_selection["choice"] = "start"

def soft_background(w, h):
    bg = np.full((h, w, 3), COL_BASE, dtype=np.uint8)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.33, h * 0.28
    dist = np.sqrt((xx - cx)**2 + (yy - cy)**2)
    r = max(w, h) * 0.9
    alpha = np.clip(1.0 - (dist / r), 0.0, 1.0)
    alpha = (alpha ** 2) * 0.45
    overlay = np.zeros_like(bg, dtype=np.float32)
    overlay[:] = COL_HL
    mix = (bg.astype(np.float32) * (1 - alpha[..., None]) + overlay * alpha[..., None])
    return mix.astype(np.uint8)

def draw_button(img, rect, label, hovered=False, pressed=False, key="view", t=0.0):
    global hover_anim, _last_t
    target = 1.0 if hovered else 0.0
    dt = max(0.0001, t - _last_t)
    hover_anim[key] = np.clip(hover_anim[key] + (target - hover_anim[key]) * min(1.0, 8.0 * dt), 0.0, 1.0)
    def lerp(c1, c2, a): return tuple(int(c1[i] + (c2[i]-c1[i])*a) for i in range(3))
    fill = lerp(COL_BTN_BASE, COL_BTN_HOVER, hover_anim[key]*0.9)
    if pressed: fill = COL_BTN_PRESS
    rounded_box(img, rect, 18, fill, COL_BTN_BORDER, shadow=True)
    if hover_anim[key] > 0.02 and not pressed:
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * (t % 1.0))
        glow = np.zeros_like(img)
        x1, y1, x2, y2 = rect
        pad = 10
        cv2.rectangle(glow, (x1-pad, y1-pad), (x2+pad, y2+pad),
                      (120 + int(40*pulse), 130 + int(40*pulse), 160 + int(50*pulse)), -1)
        alpha = 0.07 * hover_anim[key]
        cv2.addWeighted(glow, alpha, img, 1 - alpha, 0, img)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.78, 2)
    x1, y1, x2, y2 = rect
    tx = x1 + (x2 - x1 - tw)//2
    ty = y1 + (y2 - y1 + th)//2
    cv2.putText(img, label, (tx+1, ty+1), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0,0,0), 3)
    cv2.putText(img, label, (tx, ty),     cv2.FONT_HERSHEY_SIMPLEX, 0.78, COL_TEXT, 2)

def draw_clock(img):
    now  = time.strftime("%H:%M:%S")
    date = time.strftime("%d/%m/%Y")
    w, h = 240, 90
    x2, y1 = MENU_W - 24, 22
    x1, y2 = x2 - w, y1 + h
    rounded_box(img, (x1, y1, x2, y2), 14, COL_CLOCK_FILL, COL_CLOCK_BORDER, shadow=True)
    cv2.putText(img, "Relogio", (x1+16, y1+24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_HINT, 1)
    cv2.putText(img, now,       (x1+16, y1+54), cv2.FONT_HERSHEY_SIMPLEX, 0.95, COL_TEXT, 2)
    cv2.putText(img, date,      (x1+16, y1+80), cv2.FONT_HERSHEY_SIMPLEX, 0.6,  COL_HINT, 1)

def show_menu():
    global _last_t, BTN_VIEW, BTN_START
    cv2.namedWindow("Menu", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Menu", MENU_W, MENU_H)
    cv2.setMouseCallback("Menu", on_menu_mouse)
    _last_t = time.time()
    while True:
        t = time.time()
        ui = soft_background(MENU_W, MENU_H)
        title = "Controle de Acesso - Menu"
        subt  = "Selecione uma opcao para continuar"
        cv2.putText(ui, title, (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 5)
        cv2.putText(ui, title, (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, COL_TEXT, 3)
        cv2.putText(ui, subt,  (80, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,0,0), 3)
        cv2.putText(ui, subt,  (80, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COL_HINT, 1)

        bw, bh, gap = 460, 84, 36
        cx = MENU_W // 2
        yb = 300
        BTN_VIEW  = (cx - bw - gap//2, yb, cx - gap//2, yb + bh)
        BTN_START = (cx + gap//2,       yb, cx + bw + gap//2, yb + bh)

        mx, my = menu_selection["mx"], menu_selection["my"]
        hv_view  = BTN_VIEW[0]  <= mx <= BTN_VIEW[2]  and BTN_VIEW[1]  <= my <= BTN_VIEW[3]
        hv_start = BTN_START[0] <= mx <= BTN_START[2] and BTN_START[1] <= my <= BTN_START[3]

        draw_button(ui, BTN_VIEW,  "Ver registro anterior", hv_view,  False, "view",  t)
        draw_button(ui, BTN_START, "Iniciar programa", hv_start, False, "start", t)

        cv2.rectangle(ui, (0, MENU_H-46), (MENU_W, MENU_H), COL_FOOT, -1)
        msg = "Atalhos: V = ver registro, I = iniciar, ESC = sair"
        cv2.putText(ui, msg, (80, MENU_H-16), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (210,212,220), 1)

        draw_clock(ui)

        cv2.imshow("Menu", ui)
        k = cv2.waitKey(16) & 0xFF
        if menu_selection["choice"] in ("view", "start"):
            c = menu_selection["choice"]
            menu_selection["choice"] = None
            return c
        if k == 27: return "quit"
        if k in (ord('v'), ord('V')): return "view"
        if k in (ord('i'), ord('I')): return "start"
        _last_t = t

# ===================== REGISTRO ANTERIOR (scrollbar direita + colunas largas) =====================
def show_previous_log():
    W, H = 1100, 700
    cv2.namedWindow("Registro Anterior", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Registro Anterior", W, H)

    rows = read_all_events_csv()
    rows_rev = rows[::-1]  # mais recentes primeiro

    # layout da tabela (MAIS ESPACO PARA DATA E HORA)
    MARGIN_L = 20
    MARGIN_R = 20
    MARGIN_T = 90
    MARGIN_B = 40
    ROW_H = 30

    top = MARGIN_T + 34
    bottom = H - MARGIN_B
    visible = max(1, (bottom - top) // ROW_H)

    # colunas (com folga)
    X_DATA = MARGIN_L + 30            # 30px de folga apos ponto colorido
    X_HORA = X_DATA + 170             # antes ~100 -> agora 170
    X_ROST = X_HORA + 120
    X_STAT = X_ROST + 200
    X_OCC  = X_STAT + 150
    X_PV   = X_OCC + 150

    # scrollbar na direita
    SCROLL_W = 16
    track_right = W - MARGIN_R
    track_left = track_right - SCROLL_W
    track_top = top
    track_bottom = bottom
    track_h = track_bottom - track_top

    max_off = max(0, len(rows_rev) - visible)
    state = {"offset": 0, "drag": False}

    def offset_from_y(mouse_y):
        if max_off == 0:
            return 0
        thumb_h = max(28, int(track_h * (visible / max(1, len(rows_rev)))))
        thumb_h = min(thumb_h, track_h)
        span = track_h - thumb_h
        if span <= 0:
            return 0
        rel = np.clip(mouse_y - track_top - thumb_h // 2, 0, span) / float(span)
        return int(round(rel * max_off))

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if track_left <= x <= track_right and track_top <= y <= track_bottom:
                state["drag"] = True
                state["offset"] = offset_from_y(y)
        elif event == cv2.EVENT_MOUSEMOVE and state["drag"]:
            state["offset"] = offset_from_y(y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["drag"] = False

    cv2.setMouseCallback("Registro Anterior", on_mouse)

    while True:
        offset = int(np.clip(state["offset"], 0, max_off))

        panel = np.full((H, W, 3), (28, 28, 34), dtype=np.uint8)
        draw_header(panel, "Registro Anterior", "ESC para voltar | setas/pgup/pgdn/home/end ou arraste a barra")

        # cabecalho
        y0 = MARGIN_T
        cv2.putText(panel, "Data", (X_DATA, y0),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)
        cv2.putText(panel, "Hora", (X_HORA, y0),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)
        cv2.putText(panel, "Rosto", (X_ROST, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)
        cv2.putText(panel, "Status", (X_STAT, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)
        cv2.putText(panel, "Ocorrencia", (X_OCC, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)
        cv2.putText(panel, "1a vez", (X_PV, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COL_MUTED, 1)

        # linhas visiveis
        y = top
        end = min(len(rows_rev), offset + visible)
        for row in rows_rev[offset:end]:
            if len(row) >= 6:
                data, hora, rid, status, pvez, occ = row[:6]
            else:
                hora, rid, status, pvez, occ = row[:5]
                data = ""
            color = COL_OK if status == "Aprovado" else COL_BAD
            # ponto de status antes da data
            draw_dot(panel, (X_DATA - 16, y - 6 + ROW_H // 2), color, r=5)

            # textos (baseline centralizado na linha)
            by = y + ROW_H//2
            cv2.putText(panel, f"{data}", (X_DATA, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)
            cv2.putText(panel, f"{hora}", (X_HORA, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)
            cv2.putText(panel, f"{rid}",  (X_ROST, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)
            cv2.putText(panel, f"{status}", (X_STAT, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)
            cv2.putText(panel, f"#{occ}",  (X_OCC, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)
            cv2.putText(panel, f"{pvez}",  (X_PV, by), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COL_TEXT, 1)

            # linha divisoria
            cv2.line(panel, (MARGIN_L, y + ROW_H - 4), (W - MARGIN_R - SCROLL_W - 6, y + ROW_H - 4), COL_DIV, 1)
            y += ROW_H

        # paginacao
        info = f"{offset+1}-{end} / {len(rows_rev)}"
        cv2.putText(panel, info, (W - 160 - SCROLL_W, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COL_MUTED, 1)

        # scrollbar direita
        cv2.rectangle(panel, (track_left, track_top), (track_right, track_bottom), (40,40,46), -1)
        cv2.rectangle(panel, (track_left, track_top), (track_right, track_bottom), (80,80,90), 1)
        if len(rows_rev) > 0:
            thumb_h = max(28, int(track_h * (visible / max(1, len(rows_rev)))))
            thumb_h = min(thumb_h, track_h)
            span = track_h - thumb_h
            thumb_y = track_top if max_off == 0 else int(track_top + (offset / max_off) * span)
            cv2.rectangle(panel, (track_left+2, thumb_y), (track_right-2, thumb_y + thumb_h),
                          (120,120,130), -1)
            cv2.rectangle(panel, (track_left+2, thumb_y), (track_right-2, thumb_y + thumb_h),
                          (170,170,180), 1)

        cv2.imshow("Registro Anterior", panel)

        k = cv2.waitKey(16) & 0xFF
        if k == 27:  # ESC
            break
        elif k in (81, ord('a'), 82, ord('w')):  # esquerda/cima
            state["offset"] = max(0, offset-1)
        elif k in (83, ord('d'), 84, ord('s')):  # direita/baixo
            state["offset"] = min(max_off, offset+1)
        elif k == 85:  # PgUp
            state["offset"] = max(0, offset-visible+1)
        elif k == 86:  # PgDn
            state["offset"] = min(max_off, offset+visible-1)
        elif k == 36:  # Home
            state["offset"] = 0
        elif k == 35:  # End
            state["offset"] = max_off

    cv2.destroyWindow("Registro Anterior")

# ===================== CORE DO PROGRAMA =====================
def run_program():
    import serial
    ensure_csv_header()

    rosto_autorizado = None
    ultimo_envio = None
    texto = ""
    cor = (255, 255, 255)
    last_check_time = 0.0

    cv2.namedWindow("Reconhecimento Facial", cv2.WINDOW_AUTOSIZE)  # nao achata
    cv2.namedWindow("Dashboard", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Dashboard", DASH_W, DASH_H)

    try:
        arduino = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)
    except Exception as ex:
        print("Aviso: nao foi possivel abrir a porta serial. Rodando sem Arduino. Erro:", ex)
        arduino = None

    cap = cv2.VideoCapture(VIDEO_SOURCE)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Fim do video")
            break

        now = time.time()
        if (now - last_check_time) >= CHECK_INTERVAL_S:
            last_check_time = now

            # processamento (nao afeta exibicao)
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            acesso = False

            for face_encoding in face_encodings:
                if rosto_autorizado is None:
                    rosto_autorizado = face_encoding
                    acesso = True
                else:
                    match = face_recognition.compare_faces([rosto_autorizado], face_encoding, tolerance=0.5)
                    acesso = match[0]

                face_id, primeira_vez = get_or_create_face_id(face_encoding, tol=0.5)
                face_counts[face_id] += 1
                evento = {
                    "data": time.strftime("%d/%m/%Y"),
                    "hora": time.strftime("%H:%M:%S"),
                    "id": face_id,
                    "status": "Aprovado" if acesso else "Negado",
                    "primeira_vez": primeira_vez,
                    "n": face_counts[face_id],
                }
                events.appendleft(evento)
                save_event_csv(evento)

            if acesso:
                texto = "Acesso Liberado"
                cor = (0, 255, 0)
                msg = b'1'
            else:
                texto = "Acesso Negado"
                cor = (0, 0, 255)
                msg = b'0'

            if arduino is not None:
                try:
                    if msg != (ultimo_envio or b''):
                        arduino.write(msg)
                        ultimo_envio = msg
                except Exception as ex:
                    print("Falha ao enviar para Arduino:", ex)

        try:
            cv2.putText(frame, texto, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, cor, 2)
        except:
            pass

        cv2.imshow("Reconhecimento Facial", frame)
        draw_dashboard(rosto_autorizado)

        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break

    cap.release()
    cv2.destroyWindow("Reconhecimento Facial")
    cv2.destroyWindow("Dashboard")
    try:
        if arduino is not None:
            arduino.close()
    except:
        pass

# ===================== LOOP PRINCIPAL =====================
def main():
    while True:
        choice = show_menu()
        if choice == "quit" or choice is None:
            break
        elif choice == "view":
            show_previous_log()
        elif choice == "start":
            global known_faces, face_ids, face_counts, events, next_face_number
            known_faces = []
            face_ids = []
            face_counts = {}
            events = deque(maxlen=18)
            next_face_number = 1
            run_program()

    try:
        cv2.destroyWindow("Menu")
    except:
        pass
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
