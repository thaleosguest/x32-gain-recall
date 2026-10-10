#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X32 GAIN FLOAT
==============
Petite fenetre compagnon, SANS bordure, toujours au premier plan, pensee pour etre glissee dans
l'espace vide de l'interface Waves eMotion LV1 : entre la rangee A/B (flip d'entree) et la rangee
Ø (phase) de chaque voie. Mode "reduit" : pas de faders, juste potards de gain + 48V + diode de niveau.

Se connecte en direct a la X32 par OSC (UDP 10023), independamment de x32_gain_recall.py : les deux
peuvent tourner en meme temps sur la meme console (la X32 accepte plusieurs clients OSC/remote en
parallele — c'est l'usage courant avec X32-Edit + une appli de controle tierce en meme temps — mais
je n'ai pas de source documentant un nombre maximum garanti de clients simultanes : au-dela de
quelques-uns, ca reste a verifier sur votre materiel).

Ce fichier importe la classe X32Client de x32_gain_recall.py pour ne PAS dupliquer/faire diverger la
lecture des gains, du 48V et des niveaux d'entree entre les deux applis. Garder les deux fichiers dans
le meme dossier.

A SAVOIR (limites assumees, pas de source fiable pour faire mieux depuis cette session) :
  - Pas d'alignement pixel-perfect automatique avec la fenetre LV1 reelle (impossible a deviner sans
    connaitre votre resolution d'ecran et le zoom de la LV1 chez vous) : la largeur de voie et la
    position de la fenetre se reglent a la main (boutons -/+ et glisser-deposer), puis sont memorisees
    dans x32_float_config.json pour le prochain lancement.
  - La diode d'ecretage n'est PAS le vrai detecteur de clip materiel de la X32 : aucun chemin OSC
    documente ne l'expose (meme souci que l'horloge en v1.3, cf. CHANGELOG). C'est un seuil sur le
    niveau mesure (-3 dBFS par defaut, reglable avec --clip-db) : une approximation, pas une lecture
    du vrai statut de clip de la console.

Usage :
    python x32_gain_float.py --ip 192.168.1.50
    python x32_gain_float.py --sim                  # demarre un simulateur integre, sans console
"""
import argparse
import json
import math
import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x32_gain_recall import (  # noqa: E402  (import apres sys.path, volontaire)
    X32Client, X32Sim, N_HA, GAIN_MIN, GAIN_MAX, GAIN_STEP, quantize, APP_NAME, X32_PORT,
)

FLOAT_VERSION = "1.0.0"
CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x32_float_config.json")

# Memes banques que l'appli principale (groupes de 16 headamps sur les 128 : Local, AES50-A, AES50-B)
BANKS = [("Local 1-16", 0), ("Local 17-32", 16), ("AES50-A 1-16", 32), ("AES50-A 17-32", 48),
         ("AES50-A 33-48", 64), ("AES50-B 1-16", 80), ("AES50-B 17-32", 96), ("AES50-B 33-48", 112)]

BG, PANEL, LINE, LINE2 = "#08090a", "#111213", "#2c2f33", "#3a3e43"
TEAL, CYAN, WARN, MUT, TXT, OK, AMBER = "#13a9af", "#3fd0ff", "#ff5b4d", "#8c939a", "#e9edf0", "#3ddc84", "#f2b63b"

CLIENT = X32Client()
SIM = None


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_cfg(d):
    try:
        tmp = CFG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CFG_PATH)
    except OSError:
        pass


class Strip(tk.Frame):
    """Une voie : diode de niveau, potard de gain (glisser verticalement), valeur en dB, bouton 48V."""

    def __init__(self, master, owner, idx, width):
        super().__init__(master, bg=PANEL, width=width, height=width + 70,
                          highlightthickness=1, highlightbackground="#000000")
        self.owner = owner
        self.idx = idx
        self.width = width
        self.db = None
        self.phantom_state = None
        self.pack_propagate(False)

        self.led = tk.Canvas(self, width=width - 10, height=7, bg=PANEL, highlightthickness=0)
        self.led.pack(pady=(4, 3))
        self._led_id = self.led.create_oval(2, 0, 9, 7, fill="#333333", outline="")

        ksz = max(34, width - 12)
        self.knob = tk.Canvas(self, width=ksz, height=ksz, bg=PANEL, highlightthickness=0,
                               cursor="sb_v_double_arrow")
        self.knob.pack(pady=2)
        self.knob.bind("<ButtonPress-1>", self._drag_start)
        self.knob.bind("<B1-Motion>", self._drag_move)
        self._draw_knob()

        self.val = tk.Label(self, text="—", bg="#000000", fg=CYAN, font=("Consolas", 10, "bold"))
        self.val.pack(fill="x", padx=4, pady=(3, 3))

        self.ph = tk.Button(self, text="48V", bg="#25282b", fg="#aeb6bd", bd=0, relief="flat",
                             font=("Segoe UI", 8, "bold"), activebackground="#33383c",
                             command=self._phantom_click, state="disabled")
        self.ph.pack(fill="x", padx=4, pady=(0, 4))

        self._drag_y0 = None
        self._drag_db0 = None

    # -- rendu --------------------------------------------------------
    def _draw_knob(self):
        c = self.knob
        c.delete("all")
        w = int(c["width"]); h = int(c["height"])
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 3
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=LINE2, width=2)
        if self.db is None:
            c.create_text(cx, cy, text="?", fill=MUT, font=("Segoe UI", 9))
            return
        frac = max(0.0, min(1.0, (self.db - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)))
        theta = math.radians(-135 + frac * 270)   # -135deg..+135deg, 0deg = tout en haut
        dx, dy = math.sin(theta), -math.cos(theta)
        c.create_line(cx, cy, cx + dx * r * 0.82, cy + dy * r * 0.82, fill=CYAN, width=3, capstyle="round")
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=CYAN, outline="")

    def set_gain(self, db):
        self.db = db
        self._draw_knob()
        self.val.config(text=("%.1f" % db) if db is not None else "—")

    def set_phantom(self, on):
        self.phantom_state = on
        self.ph.config(state="normal" if on is not None else "disabled")
        if on:
            self.ph.config(bg="#1668e6", fg="#ffffff")
        else:
            self.ph.config(bg="#25282b", fg="#aeb6bd")

    def set_led(self, lvl_db, clip_threshold):
        color = "#333333"
        if lvl_db is not None:
            if lvl_db >= clip_threshold:
                color = WARN
            elif lvl_db >= clip_threshold - 10:
                color = AMBER
            elif lvl_db > -60:
                color = OK
        self.led.itemconfig(self._led_id, fill=color)

    # -- interaction ----------------------------------------------------
    def _drag_start(self, e):
        self._drag_y0 = e.y_root
        self._drag_db0 = self.db if self.db is not None else 0.0

    def _drag_move(self, e):
        if self._drag_y0 is None or self.owner.locked:
            return
        delta_px = self._drag_y0 - e.y_root     # glisser vers le haut = augmente le gain
        new_db = quantize(self._drag_db0 + delta_px * 0.25)
        if new_db != self.db:
            self.owner.send_gain(self.idx, new_db)

    def _phantom_click(self):
        if self.owner.locked:
            return
        if self.phantom_state:
            self.owner.send_phantom(self.idx, False)
        else:
            if messagebox.askyesno(
                "Activer le +48 V ?",
                "Voie %s : vérifiez qu'aucun micro ruban / dynamique non protégé n'est branché avant d'activer "
                "l'alimentation fantôme." % self.owner.label(self.idx),
                parent=self.owner.root,
            ):
                self.owner.send_phantom(self.idx, True)


class FloatApp:
    def __init__(self, args):
        self.args = args
        cfg = load_cfg()
        self.bank = cfg.get("bank", 0)
        self.strip_w = cfg.get("strip_w", 46)
        self.locked = False
        self.clip_db = args.clip_db

        self.root = tk.Tk()
        self.root.title("X32 Gain Float")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        self.root.configure(bg=BG)
        x = cfg.get("x", 200); y = cfg.get("y", 200)
        self.root.geometry("+%d+%d" % (x, y))

        self._build_titlebar()
        self.strips_frame = tk.Frame(self.root, bg=BG)
        self.strips_frame.pack(side="top", fill="x")
        self.strips = []
        self._build_strips()
        self._build_resize_grip()

        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        if args.sim:
            global SIM
            try:
                SIM = X32Sim()
                SIM.start()
            except OSError as e:
                messagebox.showerror("X32 Gain Float", "Simulateur impossible : %s" % e)
                sys.exit(1)
            CLIENT.connect("127.0.0.1")
        elif args.ip:
            CLIENT.connect(args.ip)
        CLIENT.set_meters(True)

        self._poll()

    # -- construction de l'UI -------------------------------------------
    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg="#0d0e0f", height=20)
        bar.pack(side="top", fill="x")
        bar.bind("<ButtonPress-1>", self._win_drag_start)
        bar.bind("<B1-Motion>", self._win_drag_move)

        self.led_conn = tk.Canvas(bar, width=9, height=9, bg="#0d0e0f", highlightthickness=0)
        self.led_conn.pack(side="left", padx=(6, 4), pady=5)
        self._conn_id = self.led_conn.create_oval(1, 1, 8, 8, fill="#555555", outline="")

        self.lbl_bank = tk.Label(bar, text=BANKS[self.bank][0], bg="#0d0e0f", fg=TXT,
                                  font=("Segoe UI", 9, "bold"))
        self.lbl_bank.pack(side="left", padx=2)
        self.lbl_bank.bind("<ButtonPress-1>", self._win_drag_start)
        self.lbl_bank.bind("<B1-Motion>", self._win_drag_move)

        tk.Button(bar, text="◀", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 8),
                  activebackground="#0d0e0f", command=lambda: self._change_bank(-1)).pack(side="left")
        tk.Button(bar, text="▶", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 8),
                  activebackground="#0d0e0f", command=lambda: self._change_bank(1)).pack(side="left")

        tk.Button(bar, text="−", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9, "bold"),
                  activebackground="#0d0e0f", command=lambda: self._resize_strips(-2)).pack(side="right", padx=1)
        tk.Button(bar, text="+", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9, "bold"),
                  activebackground="#0d0e0f", command=lambda: self._resize_strips(2)).pack(side="right", padx=1)
        self.btn_lock = tk.Button(bar, text="🔓", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9),
                                   activebackground="#0d0e0f", command=self._toggle_lock)
        self.btn_lock.pack(side="right", padx=4)
        tk.Button(bar, text="✕", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9),
                  activebackground="#0d0e0f", command=self.quit).pack(side="right", padx=4)

    def _build_strips(self):
        for w in self.strips_frame.winfo_children():
            w.destroy()
        self.strips = []
        start = BANKS[self.bank][1]
        for k in range(16):
            s = Strip(self.strips_frame, self, start + k, self.strip_w)
            s.pack(side="left")
            self.strips.append(s)
        self.lbl_bank.config(text=BANKS[self.bank][0])

    def _build_resize_grip(self):
        grip = tk.Canvas(self.root, width=10, height=10, bg="#0d0e0f", highlightthickness=0, cursor="bottom_right_corner")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.create_line(1, 9, 9, 1, fill=MUT)
        grip.create_line(4, 9, 9, 4, fill=MUT)
        grip.bind("<ButtonPress-1>", lambda e: setattr(self, "_grip_x0", e.x_root))
        grip.bind("<B1-Motion>", self._grip_drag)

    # -- fenetre : deplacement / redimensionnement -----------------------
    def _win_drag_start(self, e):
        self._drag_ox = e.x_root - self.root.winfo_x()
        self._drag_oy = e.y_root - self.root.winfo_y()

    def _win_drag_move(self, e):
        self.root.geometry("+%d+%d" % (e.x_root - self._drag_ox, e.y_root - self._drag_oy))

    def _grip_drag(self, e):
        dx = e.x_root - getattr(self, "_grip_x0", e.x_root)
        self._grip_x0 = e.x_root
        if abs(dx) >= 3:
            self._resize_strips(1 if dx > 0 else -1)

    def _resize_strips(self, delta):
        self.strip_w = max(28, min(90, self.strip_w + delta))
        for s in self.strips:
            s.width = self.strip_w
            s.config(width=self.strip_w, height=self.strip_w + 70)
            ksz = max(34, self.strip_w - 12)
            s.knob.config(width=ksz, height=ksz)
            s.led.config(width=self.strip_w - 10)
            s._draw_knob()

    def _change_bank(self, d):
        self.bank = (self.bank + d) % len(BANKS)
        self._build_strips()

    def _toggle_lock(self):
        self.locked = not self.locked
        self.btn_lock.config(text="🔒" if self.locked else "🔓")

    def label(self, idx):
        return "#%d (%s)" % (idx + 1, self._bank_label_for(idx))

    def _bank_label_for(self, idx):
        for name, start in BANKS:
            if start <= idx < start + 16:
                return "%s · %d" % (name, idx - start + 1)
        return str(idx)

    # -- commandes --------------------------------------------------------
    def send_gain(self, idx, db):
        CLIENT.set_gain(idx, db)

    def send_phantom(self, idx, on):
        CLIENT.set_phantom(idx, on)

    # -- boucle d'etat ------------------------------------------------------
    def _poll(self):
        snap = CLIENT.snapshot()
        self.led_conn.itemconfig(self._conn_id, fill=(OK if snap["connected"] else ("#f2b63b" if snap["trying"] else "#555555")))
        m = CLIENT.meters_snapshot()
        for s in self.strips:
            s.set_gain(snap["gains"][s.idx])
            s.set_phantom(snap["phantom"][s.idx])
            s.set_led(m["v"][s.idx] if m["live"] else None, self.clip_db)
        self.root.after(120, self._poll)

    def quit(self):
        save_cfg({"bank": self.bank, "strip_w": self.strip_w,
                   "x": self.root.winfo_x(), "y": self.root.winfo_y()})
        CLIENT.disconnect()
        if SIM:
            SIM.stop = True
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="X32 Gain Float — fenêtre compagnon toujours au premier plan")
    ap.add_argument("--version", action="version", version="X32 Gain Float %s" % FLOAT_VERSION)
    ap.add_argument("--ip", help="adresse IP de la X32")
    ap.add_argument("--sim", action="store_true", help="démarre un simulateur de X32 intégré (sans console)")
    ap.add_argument("--clip-db", type=float, default=-3.0,
                     help="seuil (dBFS) à partir duquel la diode passe au rouge (défaut -3 ; "
                          "ce n'est PAS le vrai détecteur de clip matériel, voir l'en-tête du fichier)")
    args = ap.parse_args()
    app = FloatApp(args)
    app.run()


if __name__ == "__main__":
    main()
