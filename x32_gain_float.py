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
potards (la fenêtre s'agrandit). Le panneau Scènes a un champ "nom + Sauvegarder" en haut (capture TOUS
les gains actuellement lus sur la console, pas seulement la banque affichée — comme le "Sauvegarder" du
navigateur) et liste les scènes existantes, chacune avec 4 boutons : Charger, Écraser (remplace le
contenu de la scène par les gains actuels de la console), Renommer et Supprimer (depuis la 1.7.0 — avant,
seul "Charger" existait ici, il fallait passer par le navigateur pour les 3 autres). Le panneau Routing
liste les profils de routing (importés via le navigateur) avec un bouton "Charger". Confirmation avant
tout envoi/écrasement/suppression. Version volontairement simplifiée par rapport au navigateur sur deux
points : le rappel de scène ne touche jamais le 48V (comme le comportement par défaut du navigateur), et
le chargement de routing ne touche que le routing E/S, jamais le patch de sortie console — pour ça
(sous-ensemble de voies, inclure le 48V, patch de sortie, importer un .scn), utiliser le navigateur. Le
fichier x32_presets.json (scènes) est partagé entre le navigateur et le float : une scène sauvegardée,
renommée, écrasée ou supprimée depuis l'un se reflète dans l'autre.

REPLIER / DEPLIER : bouton ▾/▸ dans la barre de titre, replie toute la fenêtre à une simple barre de
titre (pour libérer de la place sur l'écran de la LV1), la redéplie à l'identique (banque, taille,
position mémorisées).

COULEURS ET NOMS DE CANAUX : une fine pastille en haut de chaque voie prend la couleur du canal LV1 qui
reçoit ce préampli, et son nom s'affiche sous la ligne « L 15 = EXP 15 ». Numéro EXP lu en direct sur la
console (set_exp()), canal LV1 d'après le patch LV1 (lv1/patchmap.py), couleur et nom lus dans la base de
la LV1 (lv1/channelinfo.py) — Companion seulement en option (--companion). Tout est fourni par l'appli
principale via /api/state (lv1_channels) ; en --direct, DirectBackend installe les mêmes sources. Grise si
la voie n'arrive sur aucun canal LV1 ou si la couleur est inconnue — jamais une couleur inventée.

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

DEPUIS LA 1.5.0 : plus besoin de gerer deux .exe separes. XM32_Gain_Recall_LV1.exe integre desormais ce
fichier : le bouton "Float" du navigateur (ou `XM32_Gain_Recall_LV1.exe --float`) relance le meme
executable avec ce drapeau interne, qui delegue a main() ci-dessous. Ce fichier reste aussi utilisable
seul (en Python source, cote pratique pour qui ne veut pas du tout de l'exe principal).

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
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x32_gain_recall  # noqa: E402  (pour installer la table LV1 en --direct, voir DirectBackend)
from x32_gain_recall import (  # noqa: E402  (import apres sys.path, volontaire)
    X32Client, X32Sim, N_HA, GAIN_MIN, GAIN_MAX, quantize, scan_network,
    PresetStore, RoutingStore, pick_data_path, LAN_COOKIE, APP_SHORT, APP_AUTHOR, APP_VERSION,
)
from lv1.patchmap import PatchMap, MANUAL_FILENAME, LIVE_DB  # noqa: E402
from brand_icon import ICON_PNG_B64  # noqa: E402
from lv1.companion import CompanionPoller, DEFAULT_URL as COMPANION_URL  # noqa: E402

FLOAT_VERSION = "2.8.5"
GAIN_DB_PER_PX = 0.05     # sensibilite par defaut du glisser (dB par pixel ; 0,10 avant la 2.2.0 : plus fin au
                          # doigt, demande de Joseph - 10 px par pas de 0,5 dB) ; --sensitivity pour ajuster
STRIP_EXTRA_H = 116       # hauteur d'une voie = largeur + ceci (98 avant la 2.6.0 ; + le nom LV1)
# Dans le dossier de donnees de l'appli (%APPDATA%\\X32 Gain Recall, voir x32_gain_recall.app_data_dir) :
# PAS a cote de __file__, qui dans l'exe PyInstaller pointe vers son dossier temporaire _MEI..., efface a
# chaque fermeture (position/taille/banque du float etaient oubliees a chaque lancement de l'exe).
CFG_PATH = os.path.join(x32_gain_recall.app_data_dir(), "x32_float_config.json")

# Memes banques que l'appli principale (groupes de 16 headamps sur les 128 : Local, AES50-A, AES50-B)
BANKS = [("Local 1-16", 0), ("Local 17-32", 16), ("AES50-A 1-16", 32), ("AES50-A 17-32", 48),
         ("AES50-A 33-48", 64), ("AES50-B 1-16", 80), ("AES50-B 17-32", 96), ("AES50-B 33-48", 112)]
# Vue LV1 (float 2.7.0, appli 2.1.0) : une colonne par canal LV1, alignée sur les tranches de la LV1 (couches
# « Ch 1-16 », « Ch 17-32 »... de la LV1) ; (nom, premier canal)
# Modes de la LV1 (panneau « Modes ») où le float se déplie tout seul ; replié dans les autres
AUTO_OPEN_MODES = ("SndChk", "Setup")
# Onglets du haut de la LV1, dans l'ordre (lus à l'écran, voir lv1_tab()) ; float visible sur les deux
# premiers seulement (demande de Joseph : invisible sur All, Channel, Show, Patch, Setup)
LV1_TABS = ("Mixer 1", "Mixer 2", "All", "Channel", "Show", "Patch", "Setup")
MIXER_TABS = ("Mixer 1", "Mixer 2")
TAB_W = 22          # largeur de la languette à gauche des voies (2.2.0 : remplace la barre du haut)
OLD_TITLE_H = 34    # hauteur de l'ancienne barre du haut (pour convertir un calage d'avant la 2.2.0)
LAYOUT_VERSION = 2
# Couleur rendue TRANSPARENTE et traversable à la souris par Windows (-transparentcolor) : une colonne
# sans préampli X32 (canal sans source, groupe, matrice...) disparaît complètement, on voit et on clique
# la LV1 en dessous (2.2.0, demande de Joseph). Couleur jamais utilisée ailleurs.
HOLE = "#010203"
LV1_BANKS = [("LV1 Ch 1-16", 1), ("LV1 Ch 17-32", 17), ("LV1 Ch 33-48", 33), ("LV1 Ch 49-64", 49),
             ("LV1 Ch 65-80", 65)]

BG, PANEL, LINE, LINE2 = "#08090a", "#111213", "#2c2f33", "#3a3e43"
TEAL, CYAN, WARN, MUT, TXT, OK, AMBER = "#13a9af", "#3fd0ff", "#ff5b4d", "#8c939a", "#e9edf0", "#3ddc84", "#f2b63b"
BLUE = "#31b6f7"

# Fonds au choix (depuis la 2.6.0, demande de Joseph : le noir d'origine se confondait avec le fond de la
# LV1). Le code construit toute la fenetre avec les gris fonces du theme d'origine ("Noir") ; un theme
# est une correspondance de ces gris vers ses propres teintes, appliquee a tous les widgets par
# apply_theme() (et via tc() pour les couleurs posees en cours de route : 48V, boutons actifs...).
_CANON = ("#08090a", "#111213", "#0d0e0f", "#1c1e20", "#2a2c2e", "#15171a", "#25282b", "#33383c", "#2c2f33", "#3a3e43")
_THEME_TONES = {
    "Anthracite": ("#2b2e33", "#383c42", "#24272b", "#4a4e56", "#5a5f68", "#30343a", "#454a51", "#555a62", "#4d5259", "#5d636b"),
    "Noir":       _CANON,
    "Or":         ("#4d3d0e", "#614d13", "#433509", "#7a601a", "#8c6f1f", "#564410", "#705816", "#82671c", "#8f7222", "#a17f27"),
    "Bleu nuit":  ("#0b1424", "#132036", "#09111f", "#1f2e4a", "#2a3c5c", "#101a2c", "#223250", "#2e4064", "#2a3b5a", "#37496e"),
}
THEMES = tuple(_THEME_TONES)               # ordre du menu
DEFAULT_THEME = "Anthracite"
_REV = {c.lower(): _CANON[i] for tones in _THEME_TONES.values() for i, c in enumerate(tones)}
_theme_map = {}                            # canonique -> couleur du theme courant


def set_theme_map(name):
    global _theme_map
    tones = _THEME_TONES.get(name, _THEME_TONES[DEFAULT_THEME])
    _theme_map = {c: tones[i] for i, c in enumerate(_CANON)}


def tc(color):
    """Couleur du theme courant pour une teinte du theme d'origine (les autres couleurs sont inchangees)."""
    return _theme_map.get(color.lower(), color) if isinstance(color, str) else color


def apply_theme(widget):
    """Repeint recursivement widget et ses enfants : toute teinte connue d'UN des themes est remplacee par
    son equivalent dans le theme courant (on peut donc passer de n'importe quel theme a n'importe quel autre)."""
    for opt in ("bg", "activebackground", "highlightbackground", "highlightcolor", "selectcolor", "fg"):
        try:
            v = str(widget.cget(opt))
        except (tk.TclError, ValueError):
            continue
        canon = _REV.get(v.lower())
        if canon:
            new = _theme_map.get(canon, canon)
            if new.lower() != v.lower():
                try:
                    widget.configure({opt: new})
                except tk.TclError:
                    pass
    for child in widget.winfo_children():
        apply_theme(child)


set_theme_map(DEFAULT_THEME)   # meme bleu "action primaire" que le navigateur (.pill.on), pour une identite visuelle coherente


def strip_tag(idx):
    """Repere de voie avec la source : 'L 15' (Local 15), 'A 1' / 'B 3' (AES50-A/B), comme demande
    pour la ligne « L 15 = EXP 15 » du float."""
    if idx < 32:
        return "L %d" % (idx + 1)
    if idx < 80:
        return "A %d" % (idx - 31)
    return "B %d" % (idx - 79)


def monitor_rect(x, y):
    """(gauche, haut, largeur, hauteur) de l'écran qui contient le point (x, y) (Windows, multi-écrans) ;
    à défaut l'écran principal vu par Tk (None : appelant)."""
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        u32 = ctypes.windll.user32
        u32.MonitorFromPoint.restype = wintypes.HMONITOR
        u32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        u32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
        h = u32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)   # 2 = MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if h and u32.GetMonitorInfoW(h, ctypes.byref(mi)):
            r = mi.rcMonitor
            return r.left, r.top, r.right - r.left, r.bottom - r.top
    except (AttributeError, OSError, ValueError):
        pass
    return None


def _user32():
    try:
        import ctypes
        return ctypes, ctypes.windll.user32
    except (AttributeError, OSError, ImportError):
        return None, None


def find_lv1_window():
    """HWND de la fenêtre principale de la LV1 (titre « eMotion LV1 … », visible), ou None."""
    ctypes, u32 = _user32()
    if not u32:
        return None
    from ctypes import wintypes
    found = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _l):
        if u32.IsWindowVisible(hwnd) and not u32.GetWindow(hwnd, 4):     # 4 = GW_OWNER : fenêtre principale
            n = u32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.startswith("eMotion LV1"):
                    found.append(hwnd)
        return True
    u32.EnumWindows(proto(cb), 0)
    return found[0] if found else None


def float_hwnd(root):
    """HWND de la fenêtre Tk (cadre de premier niveau)."""
    try:
        root.update_idletasks()
        return int(root.wm_frame(), 16)
    except (tk.TclError, ValueError):
        return None


def window_alive(hwnd):
    _c, u32 = _user32()
    return bool(u32 and u32.IsWindow(hwnd) and u32.IsWindowVisible(hwnd))


def window_iconic(hwnd):
    _c, u32 = _user32()
    return bool(u32 and u32.IsIconic(hwnd))


def client_rect(hwnd):
    """(gauche, haut, largeur, hauteur) de la zone client de `hwnd`, en coordonnées écran, ou None."""
    ctypes, u32 = _user32()
    if not u32 or not hwnd:
        return None
    from ctypes import wintypes
    r = wintypes.RECT()
    pt = wintypes.POINT(0, 0)
    u32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    if not u32.GetClientRect(hwnd, ctypes.byref(r)) or not u32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None
    return pt.x, pt.y, r.right - r.left, r.bottom - r.top


def screen_row(x, y, w):
    """Pixels (r, g, b) de la ligne d'écran [x, x+w) à la hauteur y (capture GDI d'une seule ligne)."""
    ctypes, u32 = _user32()
    if not u32 or w <= 0:
        return []
    g32 = ctypes.windll.gdi32
    for fn in (u32.GetDC, g32.CreateCompatibleDC, g32.CreateCompatibleBitmap, g32.SelectObject):
        fn.restype = ctypes.c_void_p
    u32.GetDC.argtypes = [ctypes.c_void_p]
    u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    g32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    g32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    g32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    g32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    g32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
                              ctypes.c_void_p, ctypes.c_uint]
    g32.DeleteObject.argtypes = [ctypes.c_void_p]
    g32.DeleteDC.argtypes = [ctypes.c_void_p]
    hdc = u32.GetDC(None)
    mem = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, 1)
    old = g32.SelectObject(mem, bmp)
    try:
        g32.BitBlt(mem, 0, 0, w, 1, hdc, x, y, 0x00CC0020)               # SRCCOPY
        bmi = (ctypes.c_uint32 * 10)(40, w, 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)  # 32 bits, haut en bas
        buf = (ctypes.c_ubyte * (4 * w))()
        g32.GetDIBits(mem, bmp, 0, 1, buf, bmi, 0)
        return [(buf[4 * i + 2], buf[4 * i + 1], buf[4 * i]) for i in range(w)]
    finally:
        g32.SelectObject(mem, old)
        g32.DeleteObject(bmp)
        g32.DeleteDC(mem)
        u32.ReleaseDC(None, hdc)


def lv1_tab(hwnd):
    """Onglet du haut affiché par la LV1 (« Mixer 1 », « Mixer 2 », « All »…), ou None si illisible.
    La LV1 ne l'écrit pas dans sa base (vérifié le 2026-10-12) : on le LIT À L'ÉCRAN. Sur une ligne en
    haut de la fenêtre (14 px sur 1080), les 7 onglets sont 7 boutons de même largeur (~4,7 % de la
    fenêtre) : gris clair (231,231,231), et bleu (56,201,255) pour l'onglet actif. On cherche ces 7
    boutons par leur largeur relative (pas de coordonnées fixes : marche à toute résolution)."""
    rect = client_rect(hwnd)
    if not rect or rect[2] < 400:
        return None
    x, y, w, h = rect
    row = screen_row(x, y + max(1, round(h * 14 / 1080.0)), w)
    runs, cur, start = [], None, 0
    for i, (r, g, b) in enumerate(row + [(0, 0, 0)]):
        k = "C" if (b > 200 and g > 150 and r < 130) else ("W" if (r > 200 and g > 200 and b > 200) else None)
        if k != cur:
            if cur:
                runs.append((cur, start, i - start))
            cur, start = k, i
    tabs = [k for k, s, n in runs if 0.035 * w <= n <= 0.06 * w]
    if len(tabs) < len(LV1_TABS) or tabs[:len(LV1_TABS)].count("C") != 1:
        return None
    return LV1_TABS[tabs.index("C")]


def _wintypes(u32, ctypes):
    u32.GetForegroundWindow.restype = ctypes.c_void_p
    u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


def foreground_window():
    ctypes, u32 = _user32()
    if not u32:
        return None
    _wintypes(u32, ctypes)
    return u32.GetForegroundWindow()


def window_pid(hwnd):
    ctypes, u32 = _user32()
    if not u32 or not hwnd:
        return None
    _wintypes(u32, ctypes)
    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


_SWP = 0x0001 | 0x0002 | 0x0010 | 0x0200       # NOSIZE | NOMOVE | NOACTIVATE | NOOWNERZORDER


def set_topmost(me, on):
    ctypes, u32 = _user32()
    if u32:
        _wintypes(u32, ctypes)
        u32.SetWindowPos(me, -1 if on else -2, 0, 0, 0, 0, _SWP)     # HWND_TOPMOST / HWND_NOTOPMOST


def place_below(me, other):
    """Range `me` juste sous la fenêtre `other` (l'appli active). Si Windows refuse (appli en
    administrateur), le float reste où HWND_NOTOPMOST l'a mis."""
    ctypes, u32 = _user32()
    if u32 and other:
        _wintypes(u32, ctypes)
        u32.SetWindowPos(me, other, 0, 0, 0, 0, _SWP)


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8-sig") as f:
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

    def __init__(self, port, session_token=None):
        self.base = "http://127.0.0.1:%d" % port
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.needs_login = False
        self.last_error = ""
        self.reachable = False
        if session_token:
            # Deja authentifie par le bouton "Float" du navigateur (qui a lui-meme deja le code
            # d'acces --lan valide) : on recoit une session toute prete, pas besoin de retaper le
            # code dans cette fenetre separee. Sans ca, needs_login passerait a True au premier
            # /api/state et redemanderait le code, alors que l'utilisateur vient tout juste de le
            # taper dans le navigateur il y a une seconde.
            self.jar.set_cookie(http.cookiejar.Cookie(
                version=0, name=LAN_COOKIE, value=session_token,
                port=None, port_specified=False,
                domain="127.0.0.1", domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True, secure=False, expires=None,
                discard=True, comment=None, comment_url=None, rest={}, rfc2109=False,
            ))

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

    def save_preset(self, name):
        return self._post("/api/presets/save", {"name": name}) or {"ok": False, "error": self.last_error}

    def recall_preset(self, pid):
        return self._post("/api/presets/recall", {"id": pid}) or {"ok": False, "error": self.last_error}

    def rename_preset(self, pid, name):
        return self._post("/api/presets/rename", {"id": pid, "name": name}) or {"ok": False, "error": self.last_error}

    def delete_preset(self, pid):
        return self._post("/api/presets/delete", {"id": pid}) or {"ok": False, "error": self.last_error}

    def overwrite_preset(self, pid):
        return self._post("/api/presets/save", {"overwrite_id": pid}) or {"ok": False, "error": self.last_error}

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
    def __init__(self, companion_url=None, color_poll=1.0):
        self.client = X32Client()
        self.sim = None
        self.needs_login = False
        self.reachable = True
        self.last_error = ""
        # Memes fichiers JSON que l'appli principale (scenes de gains, profils de routing) : on les relit a
        # chaque appel plutot qu'une seule fois au demarrage, au cas ou l'appli principale (ou le navigateur)
        # les modifie entre-temps.
        x32_gain_recall.migrate_legacy_files()   # float lance seul (--direct) : meme recopie qu'au demarrage de l'appli
        self._data_path = pick_data_path()
        self._routing_path = os.path.join(os.path.dirname(os.path.abspath(self._data_path)), "x32_routings.json")
        # Table EXP -> canal LV1 : en mode serveur c'est l'appli principale qui la tient (champ lv1_map de
        # /api/state) ; ici, sans elle, on lit nous-memes les memes sources par defaut (session LV1 en
        # direct + table manuelle du dossier des scenes). X32Client.snapshot() la lit dans x32_gain_recall.LV1.
        if x32_gain_recall.LV1 is None:
            x32_gain_recall.LV1 = PatchMap(
                manual_path=os.path.join(x32_gain_recall.app_data_dir(), MANUAL_FILENAME),
                session_path=LIVE_DB).start()
        # Couleur + nom des canaux LV1 (Companion) : meme interrogateur que l'appli principale, lu par
        # X32Client.snapshot() dans x32_gain_recall.LV1_COMPANION (champ lv1_channels).
        if companion_url and x32_gain_recall.LV1_COMPANION is None:
            x32_gain_recall.LV1_COMPANION = CompanionPoller(
                companion_url, lambda: x32_gain_recall.lv1_channels_in_use(self.client), color_poll).start()

    def login(self, code):
        return True

    def snapshot(self):
        return self.client.snapshot()

    def meters(self):
        return self.client.meters_snapshot()

    def connect(self, ip):
        ok = self.client.connect(ip)
        self.client.demo = (ip == "127.0.0.1")
        if ok:
            threading.Thread(target=self.client.refresh_exp_map, daemon=True).start()
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
        threading.Thread(target=self.client.refresh_exp_map, daemon=True).start()
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

    def save_preset(self, name):
        snap = self.client.snapshot()
        gains = {str(i): g for i, g in enumerate(snap["gains"]) if g is not None}
        if not gains:
            return {"ok": False, "error": "Aucune valeur de gain lue : connectez-vous d'abord."}
        phantom = {str(i): p for i, p in enumerate(snap["phantom"]) if p is not None}
        names = {str(i): n for i, n in enumerate(snap["names"]) if n}
        pr = PresetStore(self._data_path).add(name, gains, phantom, names, snap["info"])
        return {"ok": True, "id": pr["id"]}

    def recall_preset(self, pid):
        pr = PresetStore(self._data_path).get(pid)
        if not pr:
            return {"ok": False, "error": "Scène introuvable"}
        if not self.client.snapshot()["connected"]:
            return {"ok": False, "error": "Non connecté à la console"}
        return {"ok": True, "result": self.client.recall(pr)}

    def rename_preset(self, pid, name):
        ok = PresetStore(self._data_path).rename(pid, name)
        return {"ok": ok, "error": "" if ok else "Scène introuvable"}

    def delete_preset(self, pid):
        ok = PresetStore(self._data_path).delete(pid)
        return {"ok": ok, "error": "" if ok else "Scène introuvable"}

    def overwrite_preset(self, pid):
        snap = self.client.snapshot()
        gains = {str(i): g for i, g in enumerate(snap["gains"]) if g is not None}
        if not gains:
            return {"ok": False, "error": "Aucune valeur de gain lue : connectez-vous d'abord."}
        phantom = {str(i): p for i, p in enumerate(snap["phantom"]) if p is not None}
        names = {str(i): n for i, n in enumerate(snap["names"]) if n}
        ok = PresetStore(self._data_path).overwrite(pid, gains, phantom, names, snap["info"])
        return {"ok": ok, "error": "" if ok else "Scène introuvable"}

    def routings(self):
        return RoutingStore(self._routing_path).summaries()

    def apply_routing(self, pid):
        pr = RoutingStore(self._routing_path).get(pid)
        if not pr:
            return {"ok": False, "error": "Profil introuvable"}
        if not self.client.snapshot()["connected"]:
            return {"ok": False, "error": "Non connecté à la console"}
        nodes = pr["nodes"].get("io", {})
        result = self.client.apply_routing(nodes, pr["name"])
        threading.Thread(target=lambda: (time.sleep(0.7), self.client.refresh_exp_map()), daemon=True).start()
        return {"ok": True, "result": result}

    def close(self):
        self.client.disconnect()
        if self.sim:
            self.sim.stop = True


class Unit(tk.Frame):
    """Un préampli : diode de niveau, potard de gain (glisser verticalement), valeur en dB, bouton 48V.
    compact=True : demi-largeur, pour les deux préamplis d'un canal LV1 stéréo réunis dans une colonne
    (vue LV1, float 2.7.0). Les deux gains restent indépendants sur la X32 : ils ne sont réunis que
    graphiquement."""

    def __init__(self, master, owner, idx, width, compact=False):
        super().__init__(master, bg=PANEL)
        self.owner = owner
        self.idx = idx
        self.compact = compact
        self.db = None
        self.phantom_state = None

        self.led = tk.Canvas(self, width=max(8, width - 10), height=7, bg=PANEL, highlightthickness=0)
        self.led.pack(pady=(4, 3))
        self._led_id = self.led.create_oval(2, 0, 9, 7, fill="#333333", outline="")

        self.knob = tk.Canvas(self, width=34, height=34, bg=PANEL, highlightthickness=0,
                               cursor="sb_v_double_arrow")
        self.knob.pack(pady=2)
        # zone de prise au doigt (2.2.0) : le potard, mais aussi sa diode et le fond de la colonne autour,
        # les potards étant devenus petits quand le float est bas
        for w in (self.knob, self.led, self):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.configure(cursor="sb_v_double_arrow")

        self._val_font = tkfont.Font(family="Consolas", size=7 if compact else 10, weight="bold")
        self.val = tk.Label(self, text="—", bg="#000000", fg=CYAN, font=self._val_font, cursor="xterm")
        self.val.pack(fill="x", padx=1 if compact else 4, pady=(3, 3))
        self.val.bind("<Button-1>", self._edit_value)

        self.ph = tk.Button(self, text="48V", bg="#25282b", fg="#aeb6bd", bd=0, relief="flat",
                             font=("Segoe UI", 7 if compact else 8, "bold"), activebackground="#33383c",
                             command=self._phantom_click, state="disabled")
        self.ph.pack(fill="x", padx=1 if compact else 4, pady=(0, 4))

        self._drag_y0 = None
        self._drag_db0 = None
        self.resize(width)

    def resize(self, width, avail_h=None):
        """avail_h : hauteur disponible pour le préampli (2.1.0 : le float se règle aussi en hauteur) ; le
        potard grandit jusqu'à ce que la largeur OU la hauteur l'arrête."""
        self.width = width
        # hauteur prise par tout sauf le potard, mesurée sur les vrais widgets (diode, valeur, 48V et leurs
        # marges) : le potard prend le reste, pour que le 48V reste visible même quand le float est bas
        # (demande de Joseph, 2.2.0 : avant, une estimation fixe coupait le 48V des voies mono)
        fixed = (self.led.winfo_reqheight() + 7 + 4 + self.val.winfo_reqheight() + 6
                 + self.ph.winfo_reqheight() + 4 + 2)
        room = (avail_h or 999) - fixed
        if self.compact:
            ksz = max(14, min(width - 6, room))
        else:
            ksz = max(16, min(width - 12, room))
        self.knob.config(width=ksz, height=ksz)
        self.led.config(width=max(8, width - 10))
        self._draw_knob()
        self._show_val()

    # -- rendu --------------------------------------------------------
    def _draw_knob(self):
        c = self.knob
        c.delete("all")
        w = int(c["width"]); h = int(c["height"])
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 3
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=tc(LINE2), width=2)
        if self.db is None:
            c.create_text(cx, cy, text="?", fill=MUT, font=("Segoe UI", 8 if self.compact else 9))
            return
        frac = max(0.0, min(1.0, (self.db - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)))
        theta = math.radians(-135 + frac * 270)   # -135deg..+135deg, 0deg = tout en haut
        dx, dy = math.sin(theta), -math.cos(theta)
        c.create_line(cx, cy, cx + dx * r * 0.82, cy + dy * r * 0.82, fill=CYAN,
                      width=2 if self.compact else 3, capstyle="round")
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=CYAN, outline="")

    def _show_val(self):
        if self.db is None:
            text = "—"
        else:
            text = "%.1f" % self.db
            if self._val_font.measure(text) > self.width - 2:   # demi-colonne étroite : sans décimale
                text = "%.0f" % self.db
        if self.val.cget("text") != text:
            self.val.config(text=text)

    def set_gain(self, db):
        if db == self.db:
            return
        self.db = db
        self._draw_knob()
        self._show_val()

    def set_phantom(self, on):
        self.phantom_state = on
        self.ph.config(state="normal" if on is not None else "disabled")
        if on:
            self.ph.config(bg="#1668e6", fg="#ffffff")
        else:
            self.ph.config(bg=tc("#25282b"), fg="#aeb6bd")

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
            self.set_gain(new_db)
            self.owner.send_gain(self.idx, new_db)

    def _edit_value(self, _e=None):
        """Clic sur la valeur en dB : saisie directe au clavier plutôt que de glisser."""
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
        self.set_gain(db)
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


class Strip(tk.Frame):
    """Une colonne : pastille de couleur du canal LV1, repère « L 15 = EXP 15 », nom du canal LV1, puis
    un préampli (Unit) — ou deux côte à côte en demi-largeur pour un canal LV1 stéréo (vue LV1), ou aucun
    pour un canal LV1 qui ne reçoit rien de la X32 (la colonne reste là pour garder l'alignement sur les
    tranches de la LV1).
    Vue X32 : idxs = [préampli], ch = None. Vue LV1 : idxs = préamplis du canal ch (voie G puis D)."""

    def __init__(self, master, owner, idxs, width, ch=None, height=None):
        super().__init__(master, bg=PANEL, width=width, height=height or width + STRIP_EXTRA_H,
                          highlightthickness=1, highlightbackground="#000000")
        self.owner = owner
        self.idxs = list(idxs)
        self.ch = ch
        self.width = width
        self.height = height or width + STRIP_EXTRA_H
        self.pack_propagate(False)
        self.units = []
        self._tag_one = None
        self._name_full = None
        self.empty = not self.idxs
        if self.empty:
            # aucun préampli X32 dans cette colonne : trou transparent (voir HOLE), rien d'autre
            self.config(bg=HOLE, highlightthickness=0)
            return

        # Pastille de couleur : couleur du canal LV1 (lue dans la base de la LV1, ou Companion), grise
        # (PANEL) tant qu'aucune couleur n'est connue - jamais une couleur inventee.
        self.swatch = tk.Frame(self, bg=PANEL, height=5, highlightthickness=0)
        self.swatch.pack(fill="x", side="top")
        self.swatch.pack_propagate(False)

        # « L 15 = EXP 15 » (sur deux lignes si la voie est trop etroite), puis le nom du canal LV1 en plus
        # gros - mise en page demandee par Joseph (2.6.0). Stereo (vue LV1) : « L 8/9 = EXP 8/9 ».
        self._tag_font = tkfont.Font(family="Segoe UI", size=7, weight="bold")
        self.chlabel = tk.Label(self, text="", bg=PANEL, fg=MUT, font=self._tag_font, justify="center")
        self.chlabel.pack(pady=(3, 0))
        self._name_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.namelbl = tk.Label(self, text="", bg=PANEL, fg=TXT, font=self._name_font)
        # vue LV1 (le float suit les couches) : pas de nom, la LV1 l'affiche déjà juste en dessous ; la
        # place va au potard (2.2.0, demande de Joseph). Vue X32 : nom du canal LV1 comme avant.
        self.show_name = ch is None
        if self.show_name:
            self.namelbl.pack(fill="x", padx=1)

        body = tk.Frame(self, bg=PANEL)
        body.pack(fill="both", expand=True)
        uw = self._unit_width()
        for i in self.idxs:
            u = Unit(body, owner, i, uw, compact=len(self.idxs) > 1)
            u.resize(uw, self._avail_h())
            u.pack(side="left", expand=True)      # centré verticalement si la colonne est plus haute
            self.units.append(u)

    def _unit_width(self):
        return (self.width - 2) // max(1, len(self.idxs))

    def _avail_h(self):
        """Hauteur laissée aux préamplis : colonne moins pastille, repère, nom (mesurés) et bordures."""
        head = (self.swatch.winfo_reqheight() + self.chlabel.winfo_reqheight() + 3
                + (self.namelbl.winfo_reqheight() if self.show_name else 0))
        return self.height - head - 2

    def resize(self, width, height=None):
        self.width = width
        self.height = height or width + STRIP_EXTRA_H
        self.config(width=width, height=self.height)
        if self.empty:
            return
        for u in self.units:
            u.resize(self._unit_width(), self._avail_h())
        if self._tag_one is not None:
            one, self._tag_one = self._tag_one, None
            self.set_tag(one)
        name, self._name_full = self._name_full, None
        self.set_name(name)

    def set_tag(self, one):
        """one : repère « L 15 = EXP 15 », raccourci (« L15=EXP15 », « L15 · 15 », « EXP 15 », « 15 ») si
        la colonne est trop étroite."""
        if self.empty or one == self._tag_one:
            return
        self._tag_one = one
        # toujours sur UNE ligne (2.2.0) : sur deux lignes, les potards de cette colonne descendaient et
        # n'étaient plus alignés avec les autres ; on raccourcit plutôt le repère si la colonne est étroite
        text = one
        if " = " in one:
            src, exp = one.split(" = ", 1)
            nums = exp.replace("EXP ", "")
            for cand in (one, "%s=%s" % (src.replace(" ", ""), exp.replace(" ", "")),
                         "%s · %s" % (src.replace(" ", ""), nums), exp, nums):
                text = cand
                if self._tag_font.measure(cand) <= self.width - 4:
                    break
        if self.chlabel.cget("text") != text:
            self.chlabel.config(text=text)
            for u in self.units:
                u.resize(self._unit_width(), self._avail_h())

    def set_name(self, name):
        """name : nom du canal LV1 (« FireRoom », « In 15 »...), ou "" si aucun. Raccourci avec « … »."""
        name = name or ""
        if self.empty or name == self._name_full:
            return
        self._name_full = name
        avail = max(10, self.width - 4)
        text = name
        if self._name_font.measure(text) > avail:
            while text and self._name_font.measure(text + "…") > avail:
                text = text[:-1]
            text += "…"
        self.namelbl.config(text=text)

    def set_color(self, hex_color):
        """hex_color : couleur "#RRGGBB" du canal LV1, ou None si inconnue - jamais une couleur inventee."""
        if self.empty:
            return
        bg = hex_color or tc(PANEL)
        if self.swatch.cget("bg") != bg:
            self.swatch.config(bg=bg)


def join_tags(idxs):
    """« L 8/9 » pour deux préamplis de la même source, sinon « L 8 + A 3 »."""
    tags = [strip_tag(i) for i in idxs]
    if len(tags) == 2 and tags[0].split()[0] == tags[1].split()[0]:
        return "%s/%s" % (tags[0], tags[1].split()[1])
    return " + ".join(tags)


class FloatApp:
    def __init__(self, args):
        self.args = args
        cfg = load_cfg()
        self.bank = cfg.get("bank", 0)
        # Vue LV1 (une colonne par canal LV1, stéréo regroupé) ou X32 (une colonne par préampli). Nouvelle
        # installation : vue LV1 ; config d'avant le float 2.7.0 : on garde la vue X32 qu'elle connaissait.
        self.view = cfg.get("view") or ("x32" if cfg else "lv1")
        self.lv1_bank = cfg.get("lv1_bank", 0)
        if not 0 <= self.bank < len(BANKS):
            self.bank = 0
        if not 0 <= self.lv1_bank < len(LV1_BANKS):
            self.lv1_bank = 0
        self.lv1_sources = {}          # {canal LV1: [EXP voie G, EXP voie D]} (vue LV1)
        self._layout = None            # [(canal, [préamplis])] affichés en vue LV1 (reconstruit s'il change)
        self._lv1_layer_seen = None    # dernière couche LV1 vue (le float suit ses changements)
        self._lv1_preset_seen = None   # dernier mode LV1 vu (Home, SndChk...) : repli / dépli automatique
        self.lv1_custom = None         # couche Custom suivie : 16 canaux LV1 (None = tranche sans entrée)
        self.lv1_custom_name = ""
        # Largeur d'une colonne en pixels, à virgule (2.1.0) : les 16 colonnes se calent au pixel près sur
        # les 16 tranches de la LV1 (la largeur totale est répartie, certaines colonnes ont 1 px de plus).
        # Position + largeur mémorisées PAR ÉCRAN (résolution) : chaque écran garde son calage, et un
        # écran jamais vu part du dernier calage mis à l'échelle (la LV1 plein écran suit la taille de
        # l'écran). Voir _apply_screen_profile() / _save_cfg().
        self.cfg = cfg
        self.strip_w = float(cfg.get("strip_w", 46))
        # hauteur des colonnes (2.1.0, réglable avec le coin bas-droit) ; défaut : largeur + STRIP_EXTRA_H
        self.strip_h = int(cfg.get("strip_h") or round(self.strip_w) + STRIP_EXTRA_H)
        self.console_open = False      # barre de connexion (IP, Connecter...) : sous les voies, à la demande
        self._console_auto = None      # True si ouverte automatiquement (pas connecté) : refermée à la connexion
        self.locked = False
        self.clip_db = args.clip_db
        self.sensitivity = args.sensitivity
        self.logged_in = False
        self.collapsed = False
        self.panel_mode = None
        self.active_scene_id = None   # id de la derniere scene chargee/renommee/ecrasee - pour la surligner dans le panneau
        self.theme = cfg.get("theme") if cfg.get("theme") in THEMES else DEFAULT_THEME
        set_theme_map(self.theme)

        # Couleurs de canaux LV1 (depuis la 2.5.0), lues via l'API HTTP de Bitfocus Companion. exp_map
        # (numero EXP par preampli) est mis a jour par le thread principal a chaque _poll() ; le thread
        # de couleurs ci-dessous le relit en lecture seule - pas de verrou necessaire, reaffectation de
        # dict/reference atomique en CPython (GIL), jamais de mutation partagee en place.
        # Depuis la 2.6.0, la couleur est cherchee pour le CANAL LV1 qui recoit cet EXP (lv1_map, table
        # EXP -> canal tenue par lv1/patchmap.py), et non plus pour "In <numero EXP>" : la LV1 indexe ses
        # couleurs par canal, et EXP N n'alimente pas forcement In N (ex. In 19 <- EXP 21 + 22).
        self.exp_map = {}
        self.lv1_map = {}                # {numero EXP: canal LV1} (cles str en mode serveur, int en --direct)
        # Couleur et nom des canaux LV1 : lus dans la base de la LV1 par l'appli principale (lv1/channelinfo.py)
        # et partages avec le navigateur via /api/state (lv1_channels) ; Companion seulement si --companion.
        # En --direct, DirectBackend installe les memes sources. Plus d'interrogation propre au float.
        companion_url = None if args.no_colors else args.companion
        if args.direct and args.no_colors:
            x32_gain_recall.LV1_NO_COLORS = True

        if args.direct:
            self.backend = DirectBackend(companion_url, args.color_poll)
        else:
            self.backend = ServerBackend(args.port, session_token=args.session_token)

        self.root = tk.Tk()
        self.root.title(APP_SHORT + " — Float")
        try:  # logo dans la barre des tâches / Alt+Tab (au lieu de la plume de Tk)
            self._icons = [tk.PhotoImage(data=d) for d in ICON_PNG_B64]
            self.root.iconphoto(True, *self._icons)
        except tk.TclError:
            pass
        self.root.overrideredirect(True)
        # Liée à la LV1 (2.1.0, demande de Joseph) : toujours juste devant la fenêtre de la LV1, derrière les
        # autres applis, cachée quand la LV1 est réduite. Sans LV1 : toujours au premier plan comme avant.
        # Voir _follow_lv1().
        self._lv1_hwnd = None
        self._lv1_pid = None
        self._lv1_seek = 0.0
        self._hidden_with_lv1 = False
        self._z_state = None           # "top" (premier plan) ou HWND de l'appli active sous laquelle on est
        self._lv1_tab = None           # onglet du haut de la LV1 (« Mixer 1 »…), lu à l'écran
        self._tab_tick = 0
        self._surface = "mixer1"       # vue LV1 suivie : celle de l'onglet Mixer 1 / Mixer 2 affiché
        self._shown = True             # fenêtres affichées (cachées : LV1 réduite ou autre onglet)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        self.root.configure(bg=BG)
        try:
            self.root.attributes("-transparentcolor", HOLE)
        except tk.TclError:
            pass
        x = cfg.get("x", 200); y = cfg.get("y", 200)
        x, y = self._apply_screen_profile(x, y)
        self.root.geometry("+%d+%d" % (x, y))

        # 2.2.0 (demande de Joseph) : plus de barre en haut, pour s'intégrer à la LV1. Une languette à
        # GAUCHE des voies (point de connexion = poignée, flèche de repli, menu ⋯), posée sur la colonne
        # « Insert / Input Select » de la LV1 ; repliée, il ne reste qu'elle, à gauche du canal 1. Scènes
        # et Routing : petite fenêtre en bas à gauche de la LV1 (_build_dock), panneaux au-dessus d'elle.
        # La barre de connexion s'ouvre SOUS les voies (Console), sans jamais les décaler.
        self.tab = self._build_tab()
        self.right = tk.Frame(self.root, bg=BG)
        self.right.pack(side="left", anchor="n")
        self.strips_frame = tk.Frame(self.right, bg=BG)
        self.strips_frame.pack(side="top", fill="x")
        self.connectbar = self._build_connectbar()
        self.strips = []
        self._build_strips()
        self._build_dock()
        self._build_resize_grip()

        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        if args.direct and args.sim:
            r = self.backend.demo()
            if not r.get("ok"):
                messagebox.showerror(APP_SHORT, r.get("error", "Simulateur impossible"))
        elif args.direct and args.ip:
            self.backend.connect(args.ip)
        if args.direct:
            self.ip_var.set(args.ip or "127.0.0.1")

        apply_theme(self.root)
        self.root.after(1000, self._theme_pass)
        self.root.after(300, self._follow_lv1)
        self._poll()

    # -- construction de l'UI -------------------------------------------
    def _build_tab(self):
        """Languette verticale à gauche des voies (2.2.0, remplace la barre du haut) : point de connexion
        (poignée pour déplacer la fenêtre), flèche de repli, menu ⋯ (banques, taille, console, fond,
        verrou, fermer), cadenas visible quand l'édition est verrouillée."""
        tab = tk.Frame(self.root, bg="#0d0e0f", width=TAB_W)
        tab.pack(side="left", fill="y", anchor="n")
        tab.bind("<ButtonPress-1>", self._win_drag_start)
        tab.bind("<B1-Motion>", self._win_drag_move)

        self.led_conn = tk.Canvas(tab, width=TAB_W, height=20, bg="#0d0e0f", highlightthickness=0, cursor="fleur")
        self.led_conn.pack(side="top", pady=(2, 0))
        c = TAB_W / 2.0
        self._conn_id = self.led_conn.create_oval(c - 4.5, 5.5, c + 4.5, 14.5, fill="#555555", outline="")
        self.led_conn.bind("<ButtonPress-1>", self._win_drag_start)
        self.led_conn.bind("<B1-Motion>", self._win_drag_move)

        self.btn_collapse = tk.Button(tab, text="◂", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 10, "bold"),
                                       activebackground="#1c1e20", padx=0, pady=2, width=2,
                                       command=self._toggle_collapse)
        self.btn_collapse.pack(side="top")
        self.btn_more = tk.Button(tab, text="⋯", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 11, "bold"),
                                  activebackground="#1c1e20", padx=0, pady=0, width=2, command=self._more_menu)
        self.btn_more.pack(side="top")
        self.lock_lbl = tk.Label(tab, text="🔒", bg="#0d0e0f", fg=WARN, font=("Segoe UI", 9))

        self.bank_var = tk.StringVar(value=self._bank_name())
        self.theme_var = tk.StringVar(value=self.theme)
        self.console_var = tk.BooleanVar(value=False)
        self.lock_var = tk.BooleanVar(value=False)
        return tab

    def _more_menu(self):
        mk = dict(tearoff=0, bg="#15171a", fg=TXT, activebackground=TEAL, activeforeground="#032", selectcolor=TXT)
        m = tk.Menu(self.root, **mk)
        banks = tk.Menu(m, **mk)
        for name, _s in LV1_BANKS:
            banks.add_radiobutton(label=name, value=name, variable=self.bank_var,
                                  command=lambda n=name: self._select_bank(n))
        banks.add_separator()
        for name, _s in BANKS:
            banks.add_radiobutton(label=name, value=name, variable=self.bank_var,
                                  command=lambda n=name: self._select_bank(n))
        m.add_cascade(label="Banque : %s" % self._bank_name(), menu=banks)
        m.add_command(label="Plus large  (+)", command=lambda: self._resize_strips(2))
        m.add_command(label="Plus étroit  (−)", command=lambda: self._resize_strips(-2))
        m.add_separator()
        m.add_command(label="Scènes…", command=lambda: self._toggle_panel("scenes"))
        m.add_command(label="Routing…", command=lambda: self._toggle_panel("routing"))
        m.add_checkbutton(label="Console (IP, connexion)", variable=self.console_var,
                          command=lambda: self._toggle_console(self.console_var.get()))
        m.add_checkbutton(label="Verrouiller l'édition", variable=self.lock_var, command=self._toggle_lock)
        themes = tk.Menu(m, **mk)
        for name in THEMES:
            themes.add_radiobutton(label=name + ("  (défaut)" if name == DEFAULT_THEME else ""), value=name,
                                   variable=self.theme_var, command=lambda n=name: self._set_theme(n))
        m.add_cascade(label="Fond de la fenêtre", menu=themes)
        m.add_separator()
        m.add_command(label="%s v%s (float %s) — by %s" % (APP_SHORT, APP_VERSION, FLOAT_VERSION, APP_AUTHOR),
                      state="disabled")
        m.add_command(label="Fermer le float", command=self.quit)
        apply_theme(m)
        b = self.btn_more
        m.tk_popup(b.winfo_rootx() + b.winfo_width(), b.winfo_rooty())

    def _build_dock(self):
        """Panneau Scènes / Routing (ouvert depuis le menu ⋯) : fenêtre à part, sous le float (2.2.0)."""
        self.panel_win = tk.Toplevel(self.root, bg=BG)
        self.panel_win.overrideredirect(True)
        try:
            self.panel_win.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        self.panel_win.withdraw()
        self.panel = tk.Frame(self.panel_win, bg=PANEL, highlightthickness=1, highlightbackground=LINE2)
        self.panel.pack(fill="both", expand=True)

    def _place_dock(self):
        """Panneau ouvert : juste sous le float, ou au-dessus s'il n'y a pas la place en bas."""
        if not self.panel_mode:
            return
        r = self.root
        self.panel_win.update_idletasks()
        ph = self.panel_win.winfo_reqheight()
        x = r.winfo_x() + TAB_W
        y = r.winfo_y() + r.winfo_height() + 4
        if y + ph > r.winfo_screenheight():
            y = max(0, r.winfo_y() - ph - 4)
        if (self.panel_win.winfo_x(), self.panel_win.winfo_y()) != (x, y):
            self.panel_win.geometry("+%d+%d" % (x, y))

    def _build_connectbar(self):
        """Barre de connexion, EN HAUT depuis la 1.7.0 (a la demande explicite : avant, elle etait sous
        la barre de titre banque/Scenes/Routing - l'ordre est desormais inverse). Toujours visible :
        IP + Connecter + Scanner + Démo (mode --direct), ou juste un statut + bouton Scanner/Connecter
        qui agissent sur l'appli principale (mode serveur).
        Boutons plus "explicites" (a la demande) : couleurs distinctes par role - Connecter en bleu
        (action primaire, meme bleu que le bouton "Connecter" du navigateur), Scanner neutre, Démo avec
        un liseré ambre pour bien le distinguer d'une vraie connexion console - plus de "padding" pour
        le tactile. Note honnete : tkinter ne sait pas dessiner de bords vraiment arrondis sur un bouton
        natif (pas d'equivalent CSS border-radius) ; l'effet "bouton" est simule par un contour
        (highlightthickness) + du remplissage, pas par un veritable arrondi."""
        bar = tk.Frame(self.root, bg="#111213")   # pas empilée ici : voir _toggle_console()
        bar.bind("<ButtonPress-1>", self._win_drag_start)
        bar.bind("<B1-Motion>", self._win_drag_move)

        self.ip_entry = None  # cree ci-dessous, reference gardee pour _connect()
        self.ip_var = tk.StringVar(value="")
        self.ip_entry = tk.Entry(bar, textvariable=self.ip_var, width=13, bg="#000000", fg=CYAN,
                                  insertbackground=CYAN, bd=0, font=("Consolas", 10), highlightthickness=1,
                                  highlightbackground=LINE2, highlightcolor=BLUE)
        self.ip_entry.pack(side="left", padx=(6, 4), pady=5, ipady=3)
        self.ip_entry.bind("<Return>", lambda e: self._connect())

        self.btn_connect = tk.Button(bar, text="Connecter", bd=0, bg=BLUE, fg="#001a2a", font=("Segoe UI", 9, "bold"),
                                      activebackground="#5cc9ff", relief="flat", padx=12, pady=6,
                                      highlightthickness=0, cursor="hand2", command=self._connect)
        self.btn_connect.pack(side="left", padx=3, pady=4)
        tk.Button(bar, text="Scanner", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 9, "bold"),
                  activebackground="#2a2c2e", relief="flat", padx=11, pady=6, highlightthickness=1,
                  highlightbackground=LINE2, cursor="hand2", command=self._scan).pack(side="left", padx=2, pady=4)
        tk.Button(bar, text="Démo", bd=0, bg="#1c1e20", fg=AMBER, font=("Segoe UI", 9, "bold"),
                  activebackground="#2a2c2e", relief="flat", padx=11, pady=6, highlightthickness=1,
                  highlightbackground=AMBER, cursor="hand2", command=self._demo).pack(side="left", padx=(2, 6), pady=4)

        self.status_lbl = tk.Label(bar, text="", bg="#111213", fg=MUT, font=("Segoe UI", 8))
        self.status_lbl.pack(side="left", padx=6)

        # Poignee de glisser (meme principe que celle de la barre de titre, 1.5.0) : desormais que cette
        # barre est tout en haut, il lui faut aussi une zone large pour deplacer la fenetre au doigt.
        handle = tk.Label(bar, text="⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯", bg="#111213", fg="#2a2c2e", font=("Segoe UI", 8))
        handle.pack(side="left", fill="both", expand=True)
        handle.bind("<ButtonPress-1>", self._win_drag_start)
        handle.bind("<B1-Motion>", self._win_drag_move)
        return bar

    def _bank_name(self):
        if self.view == "lv1" and self.lv1_custom is not None:
            return self.lv1_custom_name
        return LV1_BANKS[self.lv1_bank][0] if self.view == "lv1" else BANKS[self.bank][0]

    def _lv1_layout(self):
        """Vue LV1 : [(canal, [préamplis X32 qui l'alimentent, voie G puis D])] pour les 16 canaux de la
        banque. Préampli retrouvé par son numéro EXP, lu en direct sur la X32 (exp_map) : un EXP que la LV1
        reçoit mais qu'aucun préampli n'alimente en ce moment n'a pas de potard (jamais deviné)."""
        exp_to_idx = {}
        for k, e in (self.exp_map or {}).items():
            if e:
                exp_to_idx[int(e)] = int(k)
        if self.lv1_custom is not None:
            chans = self.lv1_custom
        else:
            start = LV1_BANKS[self.lv1_bank][1]
            chans = list(range(start, start + 16))
        out = []
        for ch in chans:
            exps = self.lv1_sources.get(ch, []) if ch else []
            out.append((ch or 0, [exp_to_idx[e] for e in exps if e in exp_to_idx]))
        return out

    def _build_strips(self):
        for w in self.strips_frame.winfo_children():
            w.destroy()
        self.strips = []
        if self.view == "lv1":
            self._layout = self._lv1_layout()
            cols = [(idxs, ch) for ch, idxs in self._layout]
        else:
            self._layout = None
            start = BANKS[self.bank][1]
            cols = [([start + k], None) for k in range(16)]
        widths, height = self._col_widths(len(cols))
        for (idxs, ch), w in zip(cols, widths):
            s = Strip(self.strips_frame, self, idxs, w, ch=ch, height=height)
            s.pack(side="left")
            self.strips.append(s)
        apply_theme(self.strips_frame)
        self.bank_var.set(self._bank_name())

    def _build_resize_grip(self):
        grip = tk.Canvas(self.root, width=10, height=10, bg="#0d0e0f", highlightthickness=0,
                         cursor="bottom_right_corner")
        self.grip = grip
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.create_line(1, 9, 9, 1, fill=MUT)
        grip.create_line(4, 9, 9, 4, fill=MUT)
        grip.bind("<ButtonPress-1>", lambda e: setattr(self, "_grip0", (e.x_root, e.y_root, self.strip_w, self.strip_h)))
        grip.bind("<B1-Motion>", self._grip_drag)

    # -- fenetre : deplacement / redimensionnement -----------------------
    def _win_drag_start(self, e):
        self._drag_ox = e.x_root - self.root.winfo_x()
        self._drag_oy = e.y_root - self.root.winfo_y()

    def _win_drag_move(self, e):
        self.root.geometry("+%d+%d" % (e.x_root - self._drag_ox, e.y_root - self._drag_oy))
        self._save_soon()

    def _save_soon(self):
        """Enregistre position / taille 0,8 s après le dernier changement : rien n'est perdu si le float
        est fermé autrement que par ✕ / Échap (appli principale fermée, session Windows...)."""
        if getattr(self, "_save_job", None):
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(800, self._save_cfg)

    def _grip_drag(self, e):
        """Coin bas-droit : la largeur TOTALE suit la souris au pixel près (répartie sur les 16 colonnes),
        pour caler le bord droit du float sur le bord droit de la 16e tranche de la LV1."""
        x0, y0, w0, h0 = getattr(self, "_grip0", (e.x_root, e.y_root, self.strip_w, self.strip_h))
        n = max(1, len(self.strips))
        self._set_strip_w(w0 + (e.x_root - x0) / n, h0 + (e.y_root - y0))

    def _col_widths(self, n):
        """Largeurs entières des n colonnes pour une largeur moyenne self.strip_w (somme = round(n * w)),
        et la hauteur commune."""
        w = self.strip_w
        widths = [int(round((i + 1) * w)) - int(round(i * w)) for i in range(n)]
        return widths, self.strip_h

    def _set_strip_w(self, w, h=None):
        w = max(28.0, min(140.0, w))
        h = self.strip_h if h is None else int(max(110, min(700, h)))
        if abs(w - self.strip_w) < 0.01 and h == self.strip_h:
            return
        self.strip_w, self.strip_h = w, h
        widths, height = self._col_widths(len(self.strips))
        for s, cw in zip(self.strips, widths):
            if s.width != cw or int(s.cget("height")) != height:
                s.resize(cw, height)
        self._save_soon()

    def _resize_strips(self, delta):
        """Boutons −/+ : un quart de pixel par colonne (4 px sur la largeur totale), pour le réglage fin."""
        self._set_strip_w(self.strip_w + delta / 8.0)

    # -- calage par écran -----------------------------------------------------
    @staticmethod
    def _screen_key(rect):
        return "%dx%d" % (rect[2], rect[3])

    def _apply_screen_profile(self, x, y):
        """Position + largeur des colonnes pour l'écran où se trouve le float : celles mémorisées pour
        cette résolution, sinon le dernier calage mis à l'échelle de cet écran, sinon (x, y) tels quels."""
        if self.cfg.get("layout") != LAYOUT_VERSION:
            # calage d'avant la 2.2.0 : barre en haut, voies au bord gauche de la fenêtre. Maintenant la
            # languette est à gauche et plus de barre : on décale pour garder les voies au même endroit.
            x, y = x - TAB_W, y + OLD_TITLE_H
            for prof in (self.cfg.get("screens") or {}).values():
                prof["dx"] = prof.get("dx", 0) - TAB_W
                prof["dy"] = prof.get("dy", 0) + OLD_TITLE_H
        rect = monitor_rect(x, y)
        screens = self.cfg.get("screens") or {}
        if not rect:
            return x, y
        prof = screens.get(self._screen_key(rect))
        if prof:
            self.strip_w = float(prof.get("strip_w", self.strip_w))
            self.strip_h = int(prof.get("strip_h") or self.strip_h)
            return rect[0] + prof["dx"], rect[1] + prof["dy"]
        last = screens.get(self.cfg.get("last_screen") or "")
        if last:
            try:
                w0, h0 = (int(v) for v in self.cfg["last_screen"].split("x"))
            except ValueError:
                return x, y
            sx, sy = rect[2] / float(w0), rect[3] / float(h0)
            self.strip_w = float(last.get("strip_w", self.strip_w)) * min(sx, sy)
            self.strip_h = int(int(last.get("strip_h") or self.strip_h) * min(sx, sy))
            return rect[0] + int(last["dx"] * sx), rect[1] + int(last["dy"] * sy)
        return x, y

    def _select_bank(self, name):
        for view, banks in (("lv1", LV1_BANKS), ("x32", BANKS)):
            for i, (n, _s) in enumerate(banks):
                if n == name:
                    self.view = view
                    self.lv1_custom = None
                    if view == "lv1":
                        self.lv1_bank = i
                    else:
                        self.bank = i
                    self._build_strips()
                    self._save_cfg()
                    return

    def _set_theme(self, name):
        self.theme = name
        self.theme_var.set(name)
        set_theme_map(name)
        apply_theme(self.root)
        for s in self.strips:
            for u in s.units:
                u._draw_knob()
        self._save_cfg()

    def _follow_lv1(self):
        """Toutes les 100 ms : fenêtres du float (voies, dock Scènes/Routing, panneau) devant la LV1,
        derrière les autres applis (demande de Joseph).
        - LV1 (ou le float) active : « toujours au premier plan » -> la LV1 ne passe plus devant quand on
          clique dessus ; une autre appli active : juste SOUS elle ;
        - cachées quand la LV1 est réduite, ou affiche un autre onglet que Mixer 1 / Mixer 2 (2.2.0) ;
        - sans LV1 : toujours au premier plan, comme avant.
        (Se placer par rapport à la fenêtre de la LV1 elle-même est refusé par Windows : elle tourne en
        administrateur.) Fenêtre de la LV1 recherchée toutes les 2 s, onglet lu à l'écran toutes les 300 ms."""
        now = time.time()
        if self._lv1_hwnd and not window_alive(self._lv1_hwnd):
            self._lv1_hwnd = None
        if not self._lv1_hwnd and now >= self._lv1_seek:
            self._lv1_seek = now + 2.0
            self._lv1_hwnd = find_lv1_window()
            self._lv1_pid = window_pid(self._lv1_hwnd) if self._lv1_hwnd else None
        lv1 = self._lv1_hwnd
        fg = foreground_window()
        front = (not lv1) or (fg and window_pid(fg) in (self._lv1_pid, os.getpid()))
        self._tab_tick += 1
        if lv1 and not window_iconic(lv1) and front and self._tab_tick % 3 == 0:
            tab = lv1_tab(lv1)          # illisible (fenêtre couverte...) : on garde le dernier connu
            if tab:
                self._lv1_tab = tab
                if tab in MIXER_TABS:
                    self._surface = "mixer2" if tab == "Mixer 2" else "mixer1"
        shown = not (lv1 and (window_iconic(lv1) or (self._lv1_tab and self._lv1_tab not in MIXER_TABS)))
        if shown != self._shown:
            self._shown = shown
            if shown:
                self.root.deiconify()
                self._z_state = None   # Tk réapplique son « -topmost » au réaffichage : tout refaire
            else:
                self.root.withdraw()
            self._sync_dock()
        if shown:
            self._sync_dock()
            wins = [w for w in (self.root, self.panel_win) if w.state() != "withdrawn"]
            hwnds = [h for h in (float_hwnd(w) for w in wins) if h]
            if front:
                if self._z_state != "top":
                    for h in hwnds:
                        set_topmost(h, True)
                    self._z_state = "top"
            elif self._z_state != fg:
                for h in hwnds:
                    set_topmost(h, False)
                    place_below(h, fg)
                self._z_state = fg
        self.root.after(100, self._follow_lv1)

    def _theme_pass(self):
        """Passe reguliere (1 s) : rattrape les widgets crees en cours de route avec les teintes d'origine
        (lignes du panneau Scenes reconstruites apres une sauvegarde, etc.)."""
        apply_theme(self.root)
        self.root.after(1000, self._theme_pass)

    def _save_cfg(self):
        x, y = self.root.winfo_x(), self.root.winfo_y()
        screens = dict(self.cfg.get("screens") or {})
        last = self.cfg.get("last_screen")
        rect = monitor_rect(x, y)
        if rect:
            last = self._screen_key(rect)
            screens[last] = {"dx": x - rect[0], "dy": y - rect[1], "strip_w": round(self.strip_w, 3),
                             "strip_h": self.strip_h}
        self.cfg = {"bank": self.bank, "view": self.view, "lv1_bank": self.lv1_bank,
                    "strip_w": round(self.strip_w, 3), "strip_h": self.strip_h, "theme": self.theme, "x": x, "y": y,
                    "screens": screens, "last_screen": last, "layout": LAYOUT_VERSION}
        save_cfg(self.cfg)

    def _toggle_lock(self):
        self.locked = not self.locked
        self.lock_var.set(self.locked)
        if self.locked:
            self.lock_lbl.pack(side="top", pady=(2, 0))
        else:
            self.lock_lbl.pack_forget()

    def _toggle_collapse(self):
        """Replie la fenêtre pour libérer l'écran de la LV1 : il ne reste que la languette (point de
        connexion = poignée, et flèche pour rouvrir), à gauche du canal 1 (2.2.0, demande de Joseph)."""
        self.collapsed = not self.collapsed
        if self.collapsed:
            self._toggle_panel(None)
            self.right.pack_forget()
            self.btn_more.pack_forget()
            self.grip.place_forget()
            self.btn_collapse.config(text="▸")
        else:
            self.right.pack(side="left", anchor="n")
            self.btn_more.pack(side="top", after=self.btn_collapse)
            self.grip.place(relx=1.0, rely=1.0, anchor="se")
            self.btn_collapse.config(text="◂")
        self._sync_dock()
        self.root.update_idletasks()

    def _sync_dock(self):
        """Panneau Scènes/Routing ouvert : visible avec les voies, caché sinon."""
        show = self._shown and not self.collapsed
        if show and self.panel_mode:
            self._place_dock()
            if self.panel_win.state() == "withdrawn":
                self.panel_win.deiconify()
                self._z_state = None
        elif self.panel_win.state() != "withdrawn":
            self.panel_win.withdraw()

    def _toggle_console(self, show=None, auto=False):
        """Barre de connexion (IP, Connecter, Scanner, Démo) SOUS les voies : ne décale jamais les voies."""
        show = (not self.console_open) if show is None else show
        self.console_var.set(show)
        if show == self.console_open:
            return
        self.console_open = show
        self._console_auto = auto if show else False   # refermée : plus jamais rouverte d'office
        if show and not self.collapsed:
            self.connectbar.pack(side="top", fill="x", after=self.strips_frame)
        else:
            self.connectbar.pack_forget()

    def _toggle_panel(self, mode):
        if self.panel_mode == mode or mode is None:
            self.panel_win.withdraw()
            self.panel_mode = None
            return
        for w in self.panel.winfo_children():
            w.destroy()
        self.panel_mode = mode
        if mode == "scenes":
            self._fill_scenes_panel()
        else:
            self._fill_routing_panel()
        apply_theme(self.panel_win)
        self._place_dock()
        self.panel_win.deiconify()
        self._z_state = None

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

    def _scene_row(self, p):
        """Une scène, avec Charger + Écraser + Renommer + Supprimer cote a cote - depuis la 1.7.0,
        a la demande explicite : avant, seul "Charger" existait ici (il fallait passer par le
        navigateur pour renommer/supprimer/ecraser une scene, cf. README/limites connues).
        Depuis la 1.7.1 : la ligne de la DERNIERE scene chargee/renommee/ecrasee est surlignee
        (bordure + fond teal, badge "SCENE ACTIVE") - avant, rien n'indiquait quelle scene etait la
        scene courante une fois le panneau refermé puis rouvert, ou apres un renommage."""
        pid, name = p["id"], p.get("name", "?")
        active = (pid == self.active_scene_id)
        row_bg = "#0a2a2a" if active else "#0d0e0f"
        row = tk.Frame(self.panel, bg=row_bg, highlightthickness=2 if active else 1,
                        highlightbackground=TEAL if active else LINE)
        row.pack(fill="x", padx=6, pady=3)
        txt = tk.Frame(row, bg=row_bg)
        txt.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        name_row = tk.Frame(txt, bg=row_bg)
        name_row.pack(fill="x")
        tk.Label(name_row, text=name, bg=row_bg, fg=TXT, font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")
        if active:
            tk.Label(name_row, text="  ● SCÈNE ACTIVE", bg=row_bg, fg=TEAL, font=("Segoe UI", 8, "bold"),
                     anchor="w").pack(side="left")
        created = p.get("created", "")
        if created:
            tk.Label(txt, text=created, bg=row_bg, fg=MUT, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        btns = tk.Frame(row, bg=row_bg)
        btns.pack(side="right", padx=4, pady=4)
        tk.Button(btns, text="Charger", bd=0, bg=TEAL, fg="#032", font=("Segoe UI", 8, "bold"),
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=lambda: self._recall_scene(pid, name)).pack(side="left", padx=2)
        tk.Button(btns, text="⟳ Écraser", bd=0, bg="#1c1e20", fg=AMBER, font=("Segoe UI", 8, "bold"),
                  relief="flat", padx=8, pady=4, highlightthickness=1, highlightbackground=AMBER,
                  cursor="hand2", command=lambda: self._overwrite_scene(pid, name)).pack(side="left", padx=2)
        tk.Button(btns, text="✎", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=8, pady=4, highlightthickness=1, highlightbackground=LINE2,
                  cursor="hand2", command=lambda: self._rename_scene(pid, name)).pack(side="left", padx=2)
        tk.Button(btns, text="✕", bd=0, bg="#1c1e20", fg=WARN, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=8, pady=4, highlightthickness=1, highlightbackground=WARN,
                  cursor="hand2", command=lambda: self._delete_scene(pid, name)).pack(side="left", padx=2)

    def _fill_scenes_panel(self):
        tk.Label(self.panel, text="SCÈNES DE GAINS", bg=PANEL, fg=MUT, font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=6, pady=(6, 2))

        save_row = tk.Frame(self.panel, bg=PANEL)
        save_row.pack(fill="x", padx=6, pady=(0, 6))
        name_var = tk.StringVar(value="")
        name_entry = tk.Entry(save_row, textvariable=name_var, bg="#000000", fg=CYAN, insertbackground=CYAN,
                               bd=0, font=("Consolas", 9))
        name_entry.pack(side="left", fill="x", expand=True, ipady=3)

        def do_save():
            self._save_scene(name_var.get().strip())

        name_entry.bind("<Return>", lambda e: do_save())
        tk.Button(save_row, text="Sauvegarder", bd=0, bg=TEAL, fg="#032", font=("Segoe UI", 8, "bold"),
                  command=do_save).pack(side="left", padx=(4, 0))

        items = self.backend.presets()
        if not items:
            tk.Label(self.panel, text="Aucune scène pour l'instant — tapez un nom ci-dessus et "
                                       "« Sauvegarder » pour créer la première, à partir des gains actuels.",
                     bg=PANEL, fg=MUT, font=("Segoe UI", 8), wraplength=self._panel_width(),
                     justify="left").pack(padx=8, pady=(0, 6))
            return
        for p in items:
            self._scene_row(p)

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
        return 300

    def _save_scene(self, name):
        if not name:
            messagebox.showwarning("Scènes", "Entrez un nom pour la scène.", parent=self.root)
            return
        if not messagebox.askyesno("Sauvegarder cette scène ?",
                                    "Sauvegarder « %s » avec TOUS les gains actuellement lus sur la console "
                                    "(pas seulement la banque affichée) ?" % name, parent=self.root):
            return
        r = self.backend.save_preset(name)
        if not r.get("ok"):
            messagebox.showerror("Scènes", r.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Scène « %s » sauvegardée" % name, fg=OK)
            self.active_scene_id = r.get("id")
            self._fill_scenes_panel_refresh()

    def _fill_scenes_panel_refresh(self):
        if self.panel_mode == "scenes":
            for w in self.panel.winfo_children():
                w.destroy()
            self._fill_scenes_panel()

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
            self.active_scene_id = pid
            self._fill_scenes_panel_refresh()

    def _overwrite_scene(self, pid, name):
        if not messagebox.askyesno(
            "Écraser la scène ?",
            "Remplacer le contenu de « %s » par les gains actuellement lus sur la console "
            "(TOUS les gains, pas seulement la banque affichée) ? Cette action est irréversible." % name,
            parent=self.root,
        ):
            return
        r = self.backend.overwrite_preset(pid)
        if not r.get("ok"):
            messagebox.showerror("Scènes", r.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Scène « %s » mise à jour" % name, fg=OK)
            self.active_scene_id = pid
            self._fill_scenes_panel_refresh()

    def _rename_scene(self, pid, name):
        r = _SimpleAsk(self.root, "Renommer la scène", "Nouveau nom :", initial=name).result
        if r is None:
            return
        new_name = r.strip()[:60]
        if not new_name:
            messagebox.showwarning("Scènes", "Le nom ne peut pas être vide.", parent=self.root)
            return
        res = self.backend.rename_preset(pid, new_name)
        if not res.get("ok"):
            messagebox.showerror("Scènes", res.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Scène renommée en « %s »" % new_name, fg=OK)
            self._fill_scenes_panel_refresh()

    def _delete_scene(self, pid, name):
        if not messagebox.askyesno(
            "Supprimer définitivement ?",
            "Supprimer la scène « %s » ? Cette action est irréversible." % name,
            parent=self.root,
        ):
            return
        r = self.backend.delete_preset(pid)
        if not r.get("ok"):
            messagebox.showerror("Scènes", r.get("error", "Échec"), parent=self.root)
        else:
            self.status_lbl.config(text="Scène « %s » supprimée" % name, fg=OK)
            if self.active_scene_id == pid:
                self.active_scene_id = None
            self._fill_scenes_panel_refresh()
            self._fill_scenes_panel_refresh()

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
        # barre de connexion : ouverte d'office tant que la console n'est pas connectée (une fois), refermée
        # toute seule dès la connexion si c'est elle qui s'était ouverte
        if self._console_auto is None:
            if snap.get("connected"):
                self._console_auto = False
            elif not snap.get("trying") and self.backend.reachable:
                self._toggle_console(True, auto=True)
        elif self._console_auto and snap.get("connected"):
            self._toggle_console(False)
        m = self.backend.meters()
        em = snap.get("exp_map") or {}
        lm = snap.get("lv1_map") or {}
        lc = snap.get("lv1_channels") or {}
        self.exp_map = em
        self.lv1_map = lm
        # cles string (JSON, mode serveur) ou int (dict Python direct, mode --direct) : normalisees en int
        self.lv1_sources = {int(k): [int(e) for e in v] for k, v in (snap.get("lv1_sources") or {}).items()}
        # Suit la couche affichée sur la LV1 (Ch 1-16, 17-32... lue dans sa base, lv1/layers.py) : seulement
        # quand elle CHANGE, pour qu'un choix fait à la main dans le float tienne jusqu'au prochain
        # changement de couche dans la LV1. Grp/Fx, Custom... (bank None) : on ne bouge pas.
        lay = (snap.get("lv1_layers") or {}).get(self._surface) or (
            snap.get("lv1_layer") if self._surface == "mixer1" else None) or {}
        if self._surface != getattr(self, "_surface_seen", None):
            self._surface_seen = self._surface        # Mixer 1 <-> Mixer 2 : tout réappliquer
            self._lv1_layer_seen = self._lv1_preset_seen = None
        key = (lay.get("mode"), lay.get("page"), tuple(lay.get("channels") or ()))
        if key != self._lv1_layer_seen:
            self._lv1_layer_seen = key
            lb, chans = lay.get("bank"), lay.get("channels")
            if self.view == "lv1" and chans:
                if lb is not None and 0 <= lb < len(LV1_BANKS):
                    self.lv1_bank, self.lv1_custom = lb, None
                else:   # couche Custom : les 16 canaux qu'elle affiche, dans l'ordre de ses tranches
                    self.lv1_custom = list(chans)[:16] + [None] * (16 - len(chans))
                    self.lv1_custom_name = "LV1 Custom %d" % (lay.get("page", 0) + 1)
                self._build_strips()
        # Mode de la LV1 (panneau « Modes ») : float déplié en SndChk / Setup, replié dans les autres modes
        # (demande de Joseph). Seulement quand le mode CHANGE : un dépli / repli à la main tient jusqu'au
        # prochain changement de mode dans la LV1.
        preset = lay.get("preset_name")
        if preset and preset != self._lv1_preset_seen:
            self._lv1_preset_seen = preset
            want_open = preset in AUTO_OPEN_MODES
            if want_open == self.collapsed:
                self._toggle_collapse()
        if self.view == "lv1" and self._lv1_layout() != self._layout:
            self._build_strips()      # repatch dans la LV1 ou sur la X32 : colonnes à refaire
        for s in self.strips:
            for u in s.units:
                u.set_gain(snap["gains"][u.idx] if snap.get("gains") else None)
                u.set_phantom(snap["phantom"][u.idx] if snap.get("phantom") else None)
                u.set_led(m["v"][u.idx] if m.get("live") else None, self.clip_db)
            if s.ch == 0:
                # vue LV1, tranche Custom qui n'est pas un canal d'entrée (groupe, FX...) : colonne vide
                s.set_tag("")
                s.set_color(None)
                s.set_name("")
                continue
            if s.ch is not None:
                # vue LV1 : la colonne EST le canal LV1 s.ch
                ch = s.ch
                exps = self.lv1_sources.get(ch, [])
                tag = ""
                if s.idxs:
                    tag = "%s = EXP %s" % (join_tags(s.idxs), "/".join(str(e) for e in exps))
                elif exps:
                    tag = "EXP %s" % "/".join(str(e) for e in exps)
            else:
                exp = em.get(str(s.idxs[0]), em.get(s.idxs[0]))
                tag = strip_tag(s.idxs[0]) + (" = EXP %d" % exp if exp else "")
                ch = self._lv1_channel(exp)
            s.set_tag(tag)
            info = (lc.get(str(ch), lc.get(ch)) or {}) if ch else {}
            s.set_color(info.get("color"))
            s.set_name(info.get("label") or ("In %d" % ch if ch else ""))
        self.root.after(200, self._poll)

    def _do_login_then_poll(self):
        self._login_pending = False
        self._login_prompt()
        self._poll()

    # -- canal LV1 d'une voie -------------------------------------------------
    def _lv1_channel(self, exp):
        """Canal LV1 alimente par ce numero EXP d'apres la table lv1_map, ou None si la table ne le dit pas
        (pastille neutre plutot qu'une couleur d'un autre canal)."""
        if not exp:
            return None
        lm = self.lv1_map
        return lm.get(str(exp), lm.get(exp))

    def quit(self):
        self._save_cfg()
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
    ap = argparse.ArgumentParser(description=APP_SHORT + " (Float) — fenêtre compagnon toujours au premier plan")
    ap.add_argument("--version", action="version", version="%s Float %s - by %s" % (APP_SHORT, FLOAT_VERSION, APP_AUTHOR))
    ap.add_argument("--port", type=int, default=8032,
                     help="port local de x32_gain_recall.py déjà lancé (défaut 8032, mode serveur)")
    ap.add_argument("--session-token", default=None,
                     help=argparse.SUPPRESS)  # usage interne : passe par le bouton "Float" du navigateur
                     # pour eviter de retaper le code d'acces --lan ; non documente pour la saisie manuelle
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
    ap.add_argument("--companion", nargs="?", const=COMPANION_URL, default=None, metavar="URL",
                     help="avec --direct, FACULTATIF : interroge aussi Bitfocus Companion pour la couleur et "
                          "le nom LV1 (sinon lus directement dans la LV1). En mode normal, c'est l'appli "
                          "principale qui s'en charge (son option --companion).")
    ap.add_argument("--no-colors", action="store_true",
                     help="désactive la lecture des couleurs de canaux LV1 via Companion (activée par défaut)")
    ap.add_argument("--color-poll", type=float, default=1.0,
                     help="intervalle (s) d'interrogation de Companion pour les couleurs (défaut 1.0 ; "
                          "pas la boucle de gains à 200ms, pour ne pas bloquer l'UI sur 16 requêtes HTTP)")
    args = ap.parse_args()
    try:
        app = FloatApp(args)
        app.run()
    except Exception as e:  # pas de console visible en .exe --windowed : on affiche l'erreur plutôt que de disparaître
        try:
            messagebox.showerror(APP_SHORT + " — erreur au démarrage", "%s: %s" % (type(e).__name__, e))
        except Exception:
            raise
        raise


if __name__ == "__main__":
    main()
