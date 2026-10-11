#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X32 GAIN FLOAT
==============
Petite fenetre compagnon, SANS bordure, toujours au premier plan, pensee pour etre glissee dans
l'espace vide de l'interface Waves eMotion LV1 : entre la rangee A/B (flip d'entree) et la rangee
Ø (phase) de chaque voie. Mode "reduit" : pas de faders, juste potards de gain + 48V + diode de niveau.

DEUX MODES DE CONNEXION :
  1) Par defaut : client HTTP de l'appli principale (x32_gain_recall.py) deja lancee sur la meme
     machine. C'est litteralement la meme appli, la meme connexion OSC, le meme etat (gains, 48V,
     scan reseau) que dans le navigateur : se connecter ici connecte aussi l'onglet navigateur, et
     inversement. Lancez d'abord x32_gain_recall.py (ou son .exe), puis x32_gain_float.py a cote.
     --port : port local de l'appli principale si different du defaut (8032).
  2) --direct : connexion OSC directe a la console, independamment de l'appli principale (utile si
     vous ne voulez PAS lancer le navigateur). Reutilise alors la classe X32Client de
     x32_gain_recall.py (meme fichier requis a cote). --ip / --sim comme avant.

SCENES / ROUTING : boutons "Scènes" et "Routing" dans la barre de titre, ouvrent un panneau sous les
potards (la fenêtre s'agrandit) listant respectivement les scènes de gains et les profils de routing,
avec un bouton "Charger" par ligne (confirmation avant envoi). Version volontairement simplifiée par
rapport au navigateur : le rappel de scène ne touche jamais le 48V (comme le comportement par défaut du
navigateur), et le chargement de routing ne touche que le routing E/S, jamais le patch de sortie console
— pour les options plus fines (sous-ensemble de voies, inclure le 48V, patch de sortie), utiliser le
navigateur.

REPLIER / DEPLIER : bouton ▾/▸ dans la barre de titre, replie toute la fenêtre à une simple barre de
titre (pour libérer de la place sur l'écran de la LV1), la redéplie à l'identique (banque, taille,
position mémorisées).

A SAVOIR (limites assumees, pas de source fiable pour faire mieux depuis cette session) :
  - Pas d'alignement pixel-perfect automatique avec la fenetre LV1 reelle (impossible a deviner sans
    connaitre votre resolution d'ecran et le zoom de la LV1 chez vous) : la largeur de voie et la
    position de la fenetre se reglent a la main (boutons -/+ et glisser-deposer), puis sont memorisees
    dans x32_float_config.json pour le prochain lancement.
  - La diode de niveau n'est PAS le vrai detecteur de clip materiel de la X32 : aucun chemin OSC
    documente ne l'expose (meme souci que l'horloge en v1.3, cf. CHANGELOG). C'est un seuil sur le
    niveau mesure (-3 dBFS par defaut, reglable avec --clip-db) : une approximation, pas une lecture
    du vrai statut de clip de la console.
  - Sensibilite du potard par defaut volontairement reduite (0,10 dB/px, etait 0,25 en 1.4.1) pour le
    tactile, choix arbitraire de ma part faute de pouvoir tester sur un vrai ecran tactile d'ici :
    ajustable avec --sensitivity si ce n'est pas le bon compromis pour vous.

Usage :
    python x32_gain_float.py                        # se connecte a x32_gain_recall.py sur 127.0.0.1:8032
    python x32_gain_float.py --port 8033             # ... si l'appli principale a pris un autre port
    python x32_gain_float.py --direct --ip 192.168.1.50   # connexion OSC directe, sans l'appli principale
    python x32_gain_float.py --direct --sim          # ... avec un simulateur integre, sans console
"""
import argparse
import http.cookiejar
import json
import math
import os
import sys
import tkinter as tk
from tkinter import messagebox
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x32_gain_recall import (  # noqa: E402  (import apres sys.path, volontaire)
    X32Client, X32Sim, N_HA, GAIN_MIN, GAIN_MAX, quantize, scan_network,
    PresetStore, RoutingStore, pick_data_path,
)

FLOAT_VERSION = "2.1.0"
GAIN_DB_PER_PX = 0.10     # sensibilite par defaut du glisser (dB par pixel) ; --sensitivity pour ajuster
CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x32_float_config.json")

# Memes banques que l'appli principale (groupes de 16 headamps sur les 128 : Local, AES50-A, AES50-B)
BANKS = [("Local 1-16", 0), ("Local 17-32", 16), ("AES50-A 1-16", 32), ("AES50-A 17-32", 48),
         ("AES50-A 33-48", 64), ("AES50-B 1-16", 80), ("AES50-B 17-32", 96), ("AES50-B 33-48", 112)]

BG, PANEL, LINE, LINE2 = "#08090a", "#111213", "#2c2f33", "#3a3e43"
TEAL, CYAN, WARN, MUT, TXT, OK, AMBER = "#13a9af", "#3fd0ff", "#ff5b4d", "#8c939a", "#e9edf0", "#3ddc84", "#f2b63b"


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


EMPTY_SNAPSHOT = {"connected": False, "trying": False, "gains": [None] * N_HA, "phantom": [None] * N_HA}
EMPTY_METERS = {"on": True, "live": False, "v": [None] * N_HA}


# --------------------------------------------------------------------------
#  Backend 1 : client HTTP de x32_gain_recall.py deja lance (mode par defaut)
# --------------------------------------------------------------------------
class ServerBackend:
    """Parle en HTTP/JSON a l'API locale de x32_gain_recall.py (meme machine). Gere la session
    (cookie) si l'appli principale tourne en mode --lan avec code d'acces : needs_login passe a True,
    l'appelant doit alors fournir le code via login(code)."""

    def __init__(self, port):
        self.base = "http://127.0.0.1:%d" % port
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.needs_login = False
        self.last_error = ""
        self.reachable = False

    def _get(self, path):
        try:
            with self.opener.open(self.base + path, timeout=2.5) as r:
                ct = r.headers.get("Content-Type", "")
                body = r.read()
            self.reachable = True
            if "application/json" not in ct:
                self.needs_login = True
                return None
            self.needs_login = False
            return json.loads(body)
        except urllib.error.HTTPError as e:
            self.reachable = True
            if e.code == 401:
                self.needs_login = True
            else:
                self.last_error = "HTTP %d" % e.code
            return None
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            self.reachable = False
            return None

    def _post(self, path, data):
        try:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(self.base + path, data=body,
                                          headers={"Content-Type": "application/json"}, method="POST")
            with self.opener.open(req, timeout=4) as r:
                self.reachable = True
                self.needs_login = False
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            self.reachable = True
            if e.code == 401:
                self.needs_login = True
            else:
                try:
                    self.last_error = json.loads(e.read()).get("error", "HTTP %d" % e.code)
                except Exception:
                    self.last_error = "HTTP %d" % e.code
            return None
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            self.reachable = False
            return None

    def login(self, code):
        r = self._post("/api/login", {"code": code})
        return r is not None

    def snapshot(self):
        return self._get("/api/state") or EMPTY_SNAPSHOT

    def meters(self):
        return self._get("/api/meters") or EMPTY_METERS

    def connect(self, ip):
        return self._post("/api/connect", {"ip": ip}) or {"ok": False, "error": self.last_error}

    def demo(self):
        return self._post("/api/demo", {}) or {"ok": False, "error": self.last_error}

    def disconnect(self):
        return self._post("/api/disconnect", {}) or {"ok": False}

    def scan(self):
        r = self._post("/api/scan", {})
        return (r or {}).get("found", [])

    def set_gain(self, idx, db):
        self._post("/api/gain", {"idx": idx, "db": db})

    def set_phantom(self, idx, on):
        self._post("/api/phantom", {"idx": idx, "on": bool(on)})

    def presets(self):
        return (self._get("/api/presets") or {}).get("presets", [])

    def recall_preset(self, pid):
        return self._post("/api/presets/recall", {"id": pid}) or {"ok": False, "error": self.last_error}

    def routings(self):
        return (self._get("/api/routings") or {}).get("profiles", [])

    def apply_routing(self, pid):
        return self._post("/api/routings/apply", {"id": pid, "groups": ["io"]}) or {"ok": False, "error": self.last_error}

    def close(self):
        pass


# --------------------------------------------------------------------------
#  Backend 2 : connexion OSC directe (--direct), sans l'appli principale
# --------------------------------------------------------------------------
class DirectBackend:
    def __init__(self):
        self.client = X32Client()
        self.sim = None
        self.needs_login = False
        self.reachable = True
        self.last_error = ""
        # Memes fichiers JSON que l'appli principale (scenes de gains, profils de routing) : on les relit a
        # chaque appel plutot qu'une seule fois au demarrage, au cas ou l'appli principale (ou le navigateur)
        # les modifie entre-temps.
        self._data_path = pick_data_path()
        self._routing_path = os.path.join(os.path.dirname(os.path.abspath(self._data_path)), "x32_routings.json")

    def login(self, code):
        return True

    def snapshot(self):
        return self.client.snapshot()

    def meters(self):
        return self.client.meters_snapshot()

    def connect(self, ip):
        ok = self.client.connect(ip)
        self.client.demo = (ip == "127.0.0.1")
        return {"ok": ok, "error": self.client.error}

    def demo(self):
        if not (self.sim and self.sim.is_alive()):
            try:
                self.sim = X32Sim()
            except OSError as e:
                return {"ok": False, "error": "Simulateur impossible : %s" % e}
            self.sim.start()
        self.client.connect("127.0.0.1")
        self.client.demo = True
        return {"ok": True}

    def disconnect(self):
        self.client.disconnect()
        return {"ok": True}

    def scan(self):
        return scan_network()

    def set_gain(self, idx, db):
        self.client.set_gain(idx, db)

    def set_phantom(self, idx, on):
        self.client.set_phantom(idx, on)

    def presets(self):
        return PresetStore(self._data_path).all()

    def recall_preset(self, pid):
        pr = PresetStore(self._data_path).get(pid)
        if not pr:
            return {"ok": False, "error": "Scène introuvable"}
        if not self.client.snapshot()["connected"]:
            return {"ok": False, "error": "Non connecté à la console"}
        return {"ok": True, "result": self.client.recall(pr)}

    def routings(self):
        return RoutingStore(self._routing_path).summaries()

    def apply_routing(self, pid):
        pr = RoutingStore(self._routing_path).get(pid)
        if not pr:
            return {"ok": False, "error": "Profil introuvable"}
        if not self.client.snapshot()["connected"]:
            return {"ok": False, "error": "Non connecté à la console"}
        nodes = pr["nodes"].get("io", {})
        return {"ok": True, "result": self.client.apply_routing(nodes, pr["name"])}

    def close(self):
        self.client.disconnect()
        if self.sim:
            self.sim.stop = True


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

        self.val = tk.Label(self, text="—", bg="#000000", fg=CYAN, font=("Consolas", 10, "bold"),
                             cursor="xterm")
        self.val.pack(fill="x", padx=4, pady=(3, 3))
        self.val.bind("<Button-1>", self._edit_value)

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
        new_db = quantize(self._drag_db0 + delta_px * self.owner.sensitivity)
        if new_db != self.db:
            self.db = new_db
            self._draw_knob()
            self.owner.send_gain(self.idx, new_db)

    def _edit_value(self, _e=None):
        """Clic sur la valeur en dB : saisie directe au clavier plutôt que de glisser (voie %s)."""
        if self.owner.locked:
            return
        cur = ("%.1f" % self.db) if self.db is not None else "0.0"
        r = _SimpleAsk(self.owner.root, "Gain — voie %s" % self.owner.label(self.idx),
                       "Valeur en dB (%.0f à +%.0f) :" % (GAIN_MIN, GAIN_MAX), initial=cur).result
        if r is None:
            return
        try:
            db = quantize(float(r.replace(",", ".")))
        except ValueError:
            messagebox.showerror("Gain", "« %s » n'est pas un nombre valide." % r, parent=self.owner.root)
            return
        self.db = db
        self._draw_knob()
        self.val.config(text="%.1f" % db)
        self.owner.send_gain(self.idx, db)

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
        self.sensitivity = args.sensitivity
        self.logged_in = False
        self.collapsed = False
        self.panel_mode = None

        if args.direct:
            self.backend = DirectBackend()
        else:
            self.backend = ServerBackend(args.port)

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
        self.connectbar = self._build_connectbar()
        self.strips_frame = tk.Frame(self.root, bg=BG)
        self.strips_frame.pack(side="top", fill="x")
        self.strips = []
        self._build_strips()
        self.panel = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=LINE2)
        self._build_resize_grip()

        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        if args.direct and args.sim:
            r = self.backend.demo()
            if not r.get("ok"):
                messagebox.showerror("X32 Gain Float", r.get("error", "Simulateur impossible"))
        elif args.direct and args.ip:
            self.backend.connect(args.ip)
        if args.direct:
            self.ip_var.set(args.ip or "127.0.0.1")

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

        self.bank_var = tk.StringVar(value=BANKS[self.bank][0])
        self.bank_menu = tk.OptionMenu(bar, self.bank_var, *[b[0] for b in BANKS], command=self._select_bank)
        self.bank_menu.config(bg="#0d0e0f", fg=TXT, bd=0, highlightthickness=0, font=("Segoe UI", 9, "bold"),
                               activebackground="#1c1e20", relief="flat")
        self.bank_menu["menu"].config(bg="#15171a", fg=TXT)
        self.bank_menu.pack(side="left", padx=2)

        self.btn_scenes = tk.Button(bar, text="Scènes", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 8, "bold"),
                                     activebackground="#1c1e20", command=lambda: self._toggle_panel("scenes"))
        self.btn_scenes.pack(side="left", padx=(8, 1))
        self.btn_routing = tk.Button(bar, text="Routing", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 8, "bold"),
                                      activebackground="#1c1e20", command=lambda: self._toggle_panel("routing"))
        self.btn_routing.pack(side="left", padx=1)

        tk.Button(bar, text="−", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9, "bold"),
                  activebackground="#0d0e0f", command=lambda: self._resize_strips(-2)).pack(side="right", padx=1)
        tk.Button(bar, text="+", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9, "bold"),
                  activebackground="#0d0e0f", command=lambda: self._resize_strips(2)).pack(side="right", padx=1)
        self.btn_lock = tk.Button(bar, text="🔓", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9),
                                   activebackground="#0d0e0f", command=self._toggle_lock)
        self.btn_lock.pack(side="right", padx=4)
        tk.Button(bar, text="✕", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9),
                  activebackground="#0d0e0f", command=self.quit).pack(side="right", padx=4)
        self.btn_collapse = tk.Button(bar, text="▾", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 9, "bold"),
                                       activebackground="#0d0e0f", command=self._toggle_collapse)
        self.btn_collapse.pack(side="right", padx=4)

    def _build_connectbar(self):
        """Barre de connexion, toujours visible : IP + Connecter + Scanner + Démo (mode --direct),
        ou juste un statut + bouton Scanner/Connecter qui agissent sur l'appli principale (mode serveur)."""
        bar = tk.Frame(self.root, bg="#111213")
        bar.pack(side="top", fill="x")
        self.ip_var = tk.StringVar(value="")
        self.ip_entry = tk.Entry(bar, textvariable=self.ip_var, width=13, bg="#000000", fg=CYAN,
                                  insertbackground=CYAN, bd=0, font=("Consolas", 9))
        self.ip_entry.pack(side="left", padx=(4, 2), pady=3)
        self.ip_entry.bind("<Return>", lambda e: self._connect())

        self.btn_connect = tk.Button(bar, text="Connecter", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 8, "bold"),
                                      activebackground="#2a2c2e", command=self._connect)
        self.btn_connect.pack(side="left", padx=2)
        tk.Button(bar, text="Scanner", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 8, "bold"),
                  activebackground="#2a2c2e", command=self._scan).pack(side="left", padx=2)
        tk.Button(bar, text="Démo", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 8, "bold"),
                  activebackground="#2a2c2e", command=self._demo).pack(side="left", padx=2)

        self.status_lbl = tk.Label(bar, text="", bg="#111213", fg=MUT, font=("Segoe UI", 8))
        self.status_lbl.pack(side="left", padx=6)
        return bar

    def _build_strips(self):
        for w in self.strips_frame.winfo_children():
            w.destroy()
        self.strips = []
        start = BANKS[self.bank][1]
        for k in range(16):
            s = Strip(self.strips_frame, self, start + k, self.strip_w)
            s.pack(side="left")
            self.strips.append(s)
        self.bank_var.set(BANKS[self.bank][0])

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

    def _select_bank(self, name):
        for i, (n, _s) in enumerate(BANKS):
            if n == name:
                self.bank = i
                self._build_strips()
                return

    def _toggle_lock(self):
        self.locked = not self.locked
        self.btn_lock.config(text="🔒" if self.locked else "🔓")

    def _toggle_collapse(self):
        """Replie la fenêtre en un simple bandeau (barre de titre seule) pour libérer de la place sur
        l'écran de la LV1 quand on n'a pas besoin des gains — comme un volet qu'on referme."""
        self.collapsed = not self.collapsed
        if self.collapsed:
            self._toggle_panel(None)
            self.connectbar.pack_forget()
            self.strips_frame.pack_forget()
            self.btn_collapse.config(text="▸")
        else:
            self.connectbar.pack(side="top", fill="x")
            self.strips_frame.pack(side="top", fill="x")
            self.btn_collapse.config(text="▾")
        self.root.update_idletasks()

    def _toggle_panel(self, mode):
        if self.panel_mode == mode or mode is None:
            self.panel.pack_forget()
            self.panel_mode = None
            self.btn_scenes.config(bg="#0d0e0f")
            self.btn_routing.config(bg="#0d0e0f")
            return
        for w in self.panel.winfo_children():
            w.destroy()
        self.panel_mode = mode
        self.btn_scenes.config(bg=("#1c1e20" if mode == "scenes" else "#0d0e0f"))
        self.btn_routing.config(bg=("#1c1e20" if mode == "routing" else "#0d0e0f"))
        if mode == "scenes":
            self._fill_scenes_panel()
        else:
            self._fill_routing_panel()
        self.panel.pack(side="top", fill="x", after=self.strips_frame)
        self.root.update_idletasks()

    def _panel_row(self, text, sub, on_click):
        row = tk.Frame(self.panel, bg="#0d0e0f", highlightthickness=1, highlightbackground=LINE)
        row.pack(fill="x", padx=6, pady=3)
        txt = tk.Frame(row, bg="#0d0e0f")
        txt.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        tk.Label(txt, text=text, bg="#0d0e0f", fg=TXT, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x")
        if sub:
            tk.Label(txt, text=sub, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 8), anchor="w").pack(fill="x")
        tk.Button(row, text="Charger", bd=0, bg=TEAL, fg="#032", font=("Segoe UI", 8, "bold"),
                  command=on_click).pack(side="right", padx=6, pady=4)

    def _fill_scenes_panel(self):
        tk.Label(self.panel, text="SCÈNES DE GAINS", bg=PANEL, fg=MUT, font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=6, pady=(6, 2))
        items = self.backend.presets()
        if not items:
            tk.Label(self.panel, text="Aucune scène (ou appli principale non connectée).", bg=PANEL, fg=MUT,
                      font=("Segoe UI", 8), wraplength=self._panel_width()).pack(padx=8, pady=6)
            return
        for p in items:
            self._panel_row(p.get("name", "?"), p.get("created", ""), lambda pid=p["id"], n=p.get("name", "?"): self._recall_scene(pid, n))

    def _fill_routing_panel(self):
        tk.Label(self.panel, text="PROFILS DE ROUTING", bg=PANEL, fg=MUT, font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=6, pady=(6, 2))
        items = self.backend.routings()
        if not items:
            tk.Label(self.panel, text="Aucun profil (ou appli principale non connectée).", bg=PANEL, fg=MUT,
                      font=("Segoe UI", 8), wraplength=self._panel_width()).pack(padx=8, pady=6)
            return
        for p in items:
            counts = p.get("counts", {})
            sub = "%d lignes E/S · %s" % (counts.get("io", 0), p.get("source", ""))
            self._panel_row(p.get("name", "?"), sub, lambda pid=p["id"], n=p.get("name", "?"): self._apply_routing(pid, n))

    def _panel_width(self):
        return max(200, len(self.strips) * self.strip_w)

    def _recall_scene(self, pid, name):
        if not messagebox.askyesno("Rappeler la scène ?",
                                    "Rappeler « %s » ? Seuls les gains sont rappelés (pas le 48V, "
                                    "comme dans le navigateur par défaut)." % name, parent=self.root):
            return
        r = self.backend.recall_preset(pid)
        if not r.get("ok"):
            messagebox.showerror("Scènes", r.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Scène « %s » rappelée" % name, fg=OK)

    def _apply_routing(self, pid, name):
        if not messagebox.askyesno("Charger ce routing ?",
                                    "Charger « %s » ? Seul le routing E/S est touché (pas le patch de sortie). "
                                    "À faire de préférence hors signal : ça peut couper l'audio en cours." % name,
                                    parent=self.root):
            return
        r = self.backend.apply_routing(pid)
        if not r.get("ok"):
            messagebox.showerror("Routing", r.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Routing « %s » envoyé" % name, fg=OK)

    def label(self, idx):
        return "#%d (%s)" % (idx + 1, self._bank_label_for(idx))

    def _bank_label_for(self, idx):
        for name, start in BANKS:
            if start <= idx < start + 16:
                return "%s · %d" % (name, idx - start + 1)
        return str(idx)

    # -- connexion ----------------------------------------------------------
    def _connect(self):
        ip = self.ip_var.get().strip()
        if not ip:
            self.status_lbl.config(text="Entrez une IP", fg=WARN)
            return
        self.status_lbl.config(text="Connexion…", fg=MUT)
        r = self.backend.connect(ip)
        if not r.get("ok"):
            self.status_lbl.config(text=r.get("error") or "Échec", fg=WARN)

    def _demo(self):
        r = self.backend.demo()
        if r.get("ok"):
            self.ip_var.set("127.0.0.1")
        else:
            self.status_lbl.config(text=r.get("error") or "Échec", fg=WARN)

    def _scan(self):
        self.status_lbl.config(text="Recherche…", fg=MUT)
        self.root.update_idletasks()
        found = self.backend.scan()
        if not found:
            self.status_lbl.config(text="Rien trouvé — IP manuelle", fg=WARN)
            return
        c = found[0]
        self.ip_var.set(c["ip"])
        self.status_lbl.config(text="%s (%s)" % (c.get("name", "?"), c["ip"]), fg=OK)
        if len(found) > 1:
            messagebox.showinfo("Scan réseau",
                                 "%d consoles trouvées, la première a été mise dans le champ IP :\n\n" % len(found) +
                                 "\n".join("%s — %s (%s)" % (c["ip"], c.get("name", "?"), c.get("model", "?")) for c in found),
                                 parent=self.root)

    def _login_prompt(self):
        code = _SimpleAsk(self.root, "Code d'accès", "Code à 4 chiffres de l'appli principale (affiché dans son terminal) :").result
        if code and self.backend.login(code):
            self.status_lbl.config(text="Connecté au serveur local", fg=OK)
        elif code is not None:
            self.status_lbl.config(text="Code incorrect", fg=WARN)

    # -- commandes --------------------------------------------------------
    def send_gain(self, idx, db):
        self.backend.set_gain(idx, db)

    def send_phantom(self, idx, on):
        self.backend.set_phantom(idx, on)

    # -- boucle d'etat ------------------------------------------------------
    def _poll(self):
        if self.backend.needs_login and not getattr(self, "_login_pending", False):
            self._login_pending = True
            self.root.after(50, self._do_login_then_poll)
            return
        snap = self.backend.snapshot()
        self.led_conn.itemconfig(self._conn_id, fill=(OK if snap.get("connected") else
                                                        ("#f2b63b" if snap.get("trying") else "#555555")))
        if not self.backend.reachable and not self.args.direct:
            self.status_lbl.config(text="Appli principale non trouvée sur le port %d" % self.args.port, fg=WARN)
        elif not snap.get("connected") and not snap.get("trying"):
            if self.status_lbl.cget("text") in ("", "Recherche…"):
                self.status_lbl.config(text="Non connecté à la console", fg=MUT)
        else:
            self.status_lbl.config(text="", fg=MUT)
        m = self.backend.meters()
        for s in self.strips:
            s.set_gain(snap["gains"][s.idx] if snap.get("gains") else None)
            s.set_phantom(snap["phantom"][s.idx] if snap.get("phantom") else None)
            s.set_led(m["v"][s.idx] if m.get("live") else None, self.clip_db)
        self.root.after(200, self._poll)

    def _do_login_then_poll(self):
        self._login_pending = False
        self._login_prompt()
        self._poll()

    def quit(self):
        save_cfg({"bank": self.bank, "strip_w": self.strip_w,
                   "x": self.root.winfo_x(), "y": self.root.winfo_y()})
        self.backend.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class _SimpleAsk:
    """Petite boîte de dialogue modale (code d'accès à 4 chiffres) sans dépendre de tkinter.simpledialog
    (pour garder le même style visuel sombre que le reste de l'appli)."""

    def __init__(self, parent, title, prompt, initial=""):
        self.result = None
        top = tk.Toplevel(parent)
        top.title(title)
        top.configure(bg=PANEL)
        top.attributes("-topmost", True)
        top.resizable(False, False)
        tk.Label(top, text=prompt, bg=PANEL, fg=TXT, font=("Segoe UI", 9), wraplength=260, justify="left").pack(
            padx=14, pady=(14, 6))
        var = tk.StringVar(value=initial)
        e = tk.Entry(top, textvariable=var, bg="#000000", fg=CYAN, insertbackground=CYAN, bd=0,
                     font=("Consolas", 14), justify="center")
        e.pack(padx=14, pady=4, fill="x")
        e.focus_set()
        e.select_range(0, "end")

        def ok(_e=None):
            self.result = var.get().strip()
            top.destroy()

        def cancel():
            self.result = None
            top.destroy()

        e.bind("<Return>", ok)
        row = tk.Frame(top, bg=PANEL)
        row.pack(pady=(6, 12))
        tk.Button(row, text="Annuler", command=cancel, bd=0, bg="#1c1e20", fg=TXT).pack(side="left", padx=6)
        tk.Button(row, text="OK", command=ok, bd=0, bg=TEAL, fg="#032").pack(side="left", padx=6)
        top.grab_set()
        parent.wait_window(top)


def main():
    ap = argparse.ArgumentParser(description="X32 Gain Float — fenêtre compagnon toujours au premier plan")
    ap.add_argument("--version", action="version", version="X32 Gain Float %s" % FLOAT_VERSION)
    ap.add_argument("--port", type=int, default=8032,
                     help="port local de x32_gain_recall.py déjà lancé (défaut 8032, mode serveur)")
    ap.add_argument("--direct", action="store_true",
                     help="connexion OSC directe à la console, sans passer par x32_gain_recall.py")
    ap.add_argument("--ip", help="adresse IP de la X32 (avec --direct)")
    ap.add_argument("--sim", action="store_true",
                     help="démarre un simulateur de X32 intégré, sans console (avec --direct)")
    ap.add_argument("--clip-db", type=float, default=-3.0,
                     help="seuil (dBFS) à partir duquel la diode passe au rouge (défaut -3 ; "
                          "ce n'est PAS le vrai détecteur de clip matériel, voir l'en-tête du fichier)")
    ap.add_argument("--sensitivity", type=float, default=GAIN_DB_PER_PX,
                     help="sensibilité du glisser sur le potard, en dB par pixel (défaut %.2f : plus petit = "
                          "glisser plus doux/précis, plus grand = glisser plus rapide/nerveux)" % GAIN_DB_PER_PX)
    args = ap.parse_args()
    try:
        app = FloatApp(args)
        app.run()
    except Exception as e:  # pas de console visible en .exe --windowed : on affiche l'erreur plutôt que de disparaître
        try:
            messagebox.showerror("X32 Gain Float — erreur au démarrage", "%s: %s" % (type(e).__name__, e))
        except Exception:
            raise
        raise


if __name__ == "__main__":
    main()
