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

DEPUIS LA 1.5.0 : plus besoin de gerer deux .exe separes. X32_Gain_Recall.exe integre desormais ce
fichier : le bouton "Float" du navigateur (ou `X32_Gain_Recall.exe --float`) relance le meme
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
    PresetStore, RoutingStore, pick_data_path, LAN_COOKIE,
)
from lv1.patchmap import PatchMap, MANUAL_FILENAME, LIVE_DB  # noqa: E402
from lv1.companion import CompanionPoller, DEFAULT_URL as COMPANION_URL  # noqa: E402

FLOAT_VERSION = "2.6.0"
GAIN_DB_PER_PX = 0.10     # sensibilite par defaut du glisser (dB par pixel) ; --sensitivity pour ajuster
STRIP_EXTRA_H = 116       # hauteur d'une voie = largeur + ceci (98 avant la 2.6.0 ; + le nom LV1)
# Dans le dossier de donnees de l'appli (%APPDATA%\\X32 Gain Recall, voir x32_gain_recall.app_data_dir) :
# PAS a cote de __file__, qui dans l'exe PyInstaller pointe vers son dossier temporaire _MEI..., efface a
# chaque fermeture (position/taille/banque du float etaient oubliees a chaque lancement de l'exe).
CFG_PATH = os.path.join(x32_gain_recall.app_data_dir(), "x32_float_config.json")

# Memes banques que l'appli principale (groupes de 16 headamps sur les 128 : Local, AES50-A, AES50-B)
BANKS = [("Local 1-16", 0), ("Local 17-32", 16), ("AES50-A 1-16", 32), ("AES50-A 17-32", 48),
         ("AES50-A 33-48", 64), ("AES50-B 1-16", 80), ("AES50-B 17-32", 96), ("AES50-B 33-48", 112)]

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


class Strip(tk.Frame):
    """Une voie : diode de niveau, potard de gain (glisser verticalement), valeur en dB, bouton 48V."""

    def __init__(self, master, owner, idx, width):
        super().__init__(master, bg=PANEL, width=width, height=width + STRIP_EXTRA_H,
                          highlightthickness=1, highlightbackground="#000000")
        self.owner = owner
        self.idx = idx
        self.width = width
        self.db = None
        self.phantom_state = None
        self.pack_propagate(False)

        # Pastille de couleur (depuis la 2.5.0) : couleur du canal LV1 correspondant, lue EN DIRECT via
        # l'API HTTP de Bitfocus Companion (module communautaire companion-module-waves-lv1), a partir
        # du meme numero EXP deja lu en direct sur la console (pas de 2e correspondance a deviner).
        # Grise/neutre (PANEL) tant qu'aucune couleur n'est connue - jamais une couleur inventee : voir
        # lv1/companion.py et set_color() plus bas.
        self.swatch = tk.Frame(self, bg=PANEL, height=5, highlightthickness=0)
        self.swatch.pack(fill="x", side="top")
        self.swatch.pack_propagate(False)

        # Repere de voie + correspondance EXP (LV1) : absent avant la 1.5.1, repere seulement par
        # position dans la rangee - on demandait de compter les colonnes a la main pour savoir quel
        # potard est quel preampli. Le numero EXP (2e ligne) est rempli par set_exp(), a partir
        # d'une lecture EN DIRECT du patch de la console (jamais une supposition) - vide tant que
        # non connecte ou non lu.
        # Depuis la 2.6.0 : « L 15 = EXP 15 » sur une ligne (sur deux si la voie est trop etroite), puis
        # le nom du canal LV1 en plus gros - mise en page demandee par Joseph.
        self._tag = strip_tag(idx)
        self._tag_font = tkfont.Font(family="Segoe UI", size=7, weight="bold")
        self.chlabel = tk.Label(self, text=self._tag, bg=PANEL, fg=MUT,
                                 font=self._tag_font, justify="center")
        self.chlabel.pack(pady=(3, 0))

        # Nom du canal LV1 qui recoit ce preampli (depuis la 2.6.0) : variable Companion in<N>_name du
        # canal donne par la table de patch LV1 (meme canal que la couleur). Voir set_name().
        self._name_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.namelbl = tk.Label(self, text="", bg=PANEL, fg=TXT, font=self._name_font)
        self.namelbl.pack(fill="x", padx=1)
        self._name_full = ""

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
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=tc(LINE2), width=2)
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

    def set_exp(self, exp_num):
        """exp_num : numero Carte/EXP (int) lu EN DIRECT sur la console pour cette voie, ou None/0 si
        non connu (non connecte, lecture pas encore faite, ou ce canal n'est pas patche vers la
        carte) - jamais une supposition, voir X32Client.refresh_exp_map()."""
        text = self._tag
        if exp_num:
            one = "%s = EXP %d" % (self._tag, exp_num)
            text = one if self._tag_font.measure(one) <= self.width - 4 else "%s\nEXP %d" % (self._tag, exp_num)
        if self.chlabel.cget("text") != text:
            self.chlabel.config(text=text)

    def set_name(self, name):
        """name : nom du canal LV1 correspondant (« FireRoom », « In 15 »...), ou "" si cette voie
        n'arrive sur aucun canal LV1. Raccourci avec « … » pour tenir dans la largeur de la voie."""
        name = name or ""
        if name == self._name_full:
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
        """hex_color : couleur "#RRGGBB" du canal LV1 correspondant, lue EN DIRECT via Companion
        (lv1/companion.py, via lv1_channels), ou None si inconnue (Companion desactive/injoignable, canal non
        patche, ou pas encore interroge) - jamais une couleur inventee, voir la pastille en haut de la
        voie dans __init__."""
        bg = hex_color or tc(PANEL)
        if self.swatch.cget("bg") != bg:
            self.swatch.config(bg=bg)

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

        # Depuis la 1.7.0 : la barre de connexion (IP/Connecter/Scanner/Démo) est EN HAUT, la barre de
        # titre (repli/zoom/banque/Scènes/Routing) juste en dessous - a la demande explicite de
        # l'utilisateur (ordre inverse de la 1.5.0/1.6.0). L'ordre d'empilement tkinter suit l'ordre des
        # appels a pack(side="top"), donc l'inversion se fait simplement en appelant les deux methodes
        # dans l'autre sens ; aucune des deux ne depend de l'autre.
        self.connectbar = self._build_connectbar()
        self.titlebar = self._build_titlebar()
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

        apply_theme(self.root)
        self.root.after(1000, self._theme_pass)
        self._poll()

    # -- construction de l'UI -------------------------------------------
    def _build_titlebar(self):
        # Barre de titre : boutons de taille/repli a GAUCHE (plus accessibles au pouce quand la fenetre
        # est glissee pres du bord), cibles agrandies pour le tactile (padx/pady genereux, pas juste la
        # police), et une large zone vide AU MILIEU dediee au glisser-deposer au doigt - importante
        # surtout replie (▸), ou la barre de titre est tout ce qui reste visible pour reattraper la
        # fenetre : avant la 1.5.0, les boutons occupaient presque toute la largeur et ne laissaient que
        # de minces interstices pour saisir la fenetre.
        bar = tk.Frame(self.root, bg="#0d0e0f")
        bar.pack(side="top", fill="x")
        bar.bind("<ButtonPress-1>", self._win_drag_start)
        bar.bind("<B1-Motion>", self._win_drag_move)

        self.led_conn = tk.Canvas(bar, width=9, height=9, bg="#0d0e0f", highlightthickness=0)
        self.led_conn.pack(side="left", padx=(6, 4), pady=6)
        self._conn_id = self.led_conn.create_oval(1, 1, 8, 8, fill="#555555", outline="")

        self.btn_collapse = tk.Button(bar, text="▾", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 11, "bold"),
                                       activebackground="#1c1e20", padx=7, pady=4, command=self._toggle_collapse)
        self.btn_collapse.pack(side="left", padx=(0, 2), pady=2)
        tk.Button(bar, text="−", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 11, "bold"),
                  activebackground="#1c1e20", padx=7, pady=4,
                  command=lambda: self._resize_strips(-2)).pack(side="left", padx=1, pady=2)
        tk.Button(bar, text="+", bd=0, bg="#0d0e0f", fg=MUT, font=("Segoe UI", 11, "bold"),
                  activebackground="#1c1e20", padx=7, pady=4,
                  command=lambda: self._resize_strips(2)).pack(side="left", padx=(1, 8), pady=2)

        self.bank_var = tk.StringVar(value=BANKS[self.bank][0])
        self.bank_menu = tk.OptionMenu(bar, self.bank_var, *[b[0] for b in BANKS], command=self._select_bank)
        self.bank_menu.config(bg="#0d0e0f", fg=TXT, bd=0, highlightthickness=0, font=("Segoe UI", 9, "bold"),
                               activebackground="#1c1e20", relief="flat")
        self.bank_menu["menu"].config(bg="#15171a", fg=TXT)
        self.bank_menu.pack(side="left", padx=2)

        # Boutons Scenes/Routing plus "explicites" (demande utilisateur) : contour visible au repos,
        # et bascule vers le meme bleu "actif" que les onglets Gains/Routing du navigateur une fois le
        # panneau ouvert (gere dans _toggle_panel), plutot qu'un simple gris a peine plus clair.
        self.btn_scenes = tk.Button(bar, text="Scènes", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 9, "bold"),
                                     activebackground="#2a2c2e", relief="flat", padx=10, pady=5,
                                     highlightthickness=1, highlightbackground=LINE2, cursor="hand2",
                                     command=lambda: self._toggle_panel("scenes"))
        self.btn_scenes.pack(side="left", padx=(8, 2))
        self.btn_routing = tk.Button(bar, text="Routing", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 9, "bold"),
                                      activebackground="#2a2c2e", relief="flat", padx=10, pady=5,
                                      highlightthickness=1, highlightbackground=LINE2, cursor="hand2",
                                      command=lambda: self._toggle_panel("routing"))
        self.btn_routing.pack(side="left", padx=2)

        self.btn_lock = tk.Button(bar, text="🔓", bd=0, bg="#1c1e20", fg=MUT, font=("Segoe UI", 10),
                                   activebackground="#2a2c2e", relief="flat", padx=7, pady=5,
                                   highlightthickness=1, highlightbackground=LINE2, cursor="hand2",
                                   command=self._toggle_lock)
        self.btn_lock.pack(side="right", padx=4, pady=2)
        tk.Button(bar, text="✕", bd=0, bg="#1c1e20", fg=MUT, font=("Segoe UI", 10), activebackground=WARN,
                  relief="flat", padx=7, pady=5, highlightthickness=1, highlightbackground=LINE2,
                  cursor="hand2", command=self.quit).pack(side="right", padx=4, pady=2)
        # Choix du fond (Anthracite par defaut, Noir = celui d'origine, Or, Bleu nuit), memorise
        self.theme_var = tk.StringVar(value=self.theme)
        self.btn_theme = tk.Button(bar, text="◐", bd=0, bg="#1c1e20", fg=TXT, font=("Segoe UI", 10),
                                    activebackground="#2a2c2e", relief="flat", padx=7, pady=5,
                                    highlightthickness=1, highlightbackground=LINE2, cursor="hand2",
                                    command=self._theme_menu)
        self.btn_theme.pack(side="right", padx=4, pady=2)

        # Poignee de glisser : prend tout l'espace restant entre les boutons de gauche et de droite.
        # Memes bindings que la barre elle-meme, mais garantie d'etre toujours presente et large, meme
        # fenetre repliee ou tres etroite - contrairement aux interstices entre boutons.
        handle = tk.Label(bar, text="⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯", bg="#0d0e0f", fg="#2a2c2e", font=("Segoe UI", 8))
        handle.pack(side="left", fill="both", expand=True)
        handle.bind("<ButtonPress-1>", self._win_drag_start)
        handle.bind("<B1-Motion>", self._win_drag_move)
        self.drag_handle = handle
        return bar

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
        bar = tk.Frame(self.root, bg="#111213")
        bar.pack(side="top", fill="x")
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

    def _build_strips(self):
        for w in self.strips_frame.winfo_children():
            w.destroy()
        self.strips = []
        start = BANKS[self.bank][1]
        for k in range(16):
            s = Strip(self.strips_frame, self, start + k, self.strip_w)
            s.pack(side="left")
            self.strips.append(s)
        apply_theme(self.strips_frame)
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
            s.config(width=self.strip_w, height=self.strip_w + STRIP_EXTRA_H)
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

    def _theme_menu(self):
        m = tk.Menu(self.root, tearoff=0, bg="#15171a", fg=TXT, activebackground=TEAL, activeforeground="#032",
                    selectcolor=TXT)
        m.add_command(label="Fond de la fenêtre", state="disabled")
        for name in THEMES:
            m.add_radiobutton(label=name + ("  (défaut)" if name == DEFAULT_THEME else ""), value=name,
                              variable=self.theme_var, command=lambda n=name: self._set_theme(n))
        apply_theme(m)
        b = self.btn_theme
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _set_theme(self, name):
        self.theme = name
        self.theme_var.set(name)
        set_theme_map(name)
        apply_theme(self.root)
        for s in self.strips:
            s._draw_knob()
        self._save_cfg()

    def _theme_pass(self):
        """Passe reguliere (1 s) : rattrape les widgets crees en cours de route avec les teintes d'origine
        (lignes du panneau Scenes reconstruites apres une sauvegarde, etc.)."""
        apply_theme(self.root)
        self.root.after(1000, self._theme_pass)

    def _save_cfg(self):
        save_cfg({"bank": self.bank, "strip_w": self.strip_w, "theme": self.theme,
                  "x": self.root.winfo_x(), "y": self.root.winfo_y()})

    def _toggle_lock(self):
        self.locked = not self.locked
        self.btn_lock.config(text="🔒" if self.locked else "🔓",
                              bg=(WARN if self.locked else tc("#1c1e20")),
                              fg=("#fff" if self.locked else MUT))

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
            # BUG corrige (1.7.1) : pack_forget() puis pack() replace un widget a la FIN de la pile
            # d'empilement courante, pas a sa position d'origine - comme la barre de titre restait
            # packee pendant le repli, un simple pack(side="top") la repoussait en dessous d'elle a
            # chaque depli, inversant l'ordre voulu (connexion en haut) au bout d'un cycle repli/depli.
            # Fix : forcer explicitement la position avec before=.
            self.connectbar.pack(side="top", fill="x", before=self.titlebar)
            self.strips_frame.pack(side="top", fill="x")
            self.btn_collapse.config(text="▾")
        self.root.update_idletasks()

    def _toggle_panel(self, mode):
        if self.panel_mode == mode or mode is None:
            self.panel.pack_forget()
            self.panel_mode = None
            self.btn_scenes.config(bg=tc("#1c1e20"), fg=TXT)
            self.btn_routing.config(bg=tc("#1c1e20"), fg=TXT)
            return
        for w in self.panel.winfo_children():
            w.destroy()
        self.panel_mode = mode
        self.btn_scenes.config(bg=(TEAL if mode == "scenes" else tc("#1c1e20")),
                                fg=("#032" if mode == "scenes" else TXT))
        self.btn_routing.config(bg=(TEAL if mode == "routing" else tc("#1c1e20")),
                                 fg=("#032" if mode == "routing" else TXT))
        if mode == "scenes":
            self._fill_scenes_panel()
        else:
            self._fill_routing_panel()
        self.panel.pack(side="top", fill="x", after=self.strips_frame)
        apply_theme(self.panel)
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
        return max(200, len(self.strips) * self.strip_w)

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
        m = self.backend.meters()
        em = snap.get("exp_map") or {}
        lm = snap.get("lv1_map") or {}
        lc = snap.get("lv1_channels") or {}
        self.exp_map = em
        self.lv1_map = lm
        for s in self.strips:
            s.set_gain(snap["gains"][s.idx] if snap.get("gains") else None)
            s.set_phantom(snap["phantom"][s.idx] if snap.get("phantom") else None)
            s.set_led(m["v"][s.idx] if m.get("live") else None, self.clip_db)
            # cle string (vient du JSON, mode serveur) ou int (dict Python direct, mode --direct)
            exp = em.get(str(s.idx), em.get(s.idx))
            s.set_exp(exp)
            ch = self._lv1_channel(exp)
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
    ap = argparse.ArgumentParser(description="X32 Gain Float — fenêtre compagnon toujours au premier plan")
    ap.add_argument("--version", action="version", version="X32 Gain Float %s" % FLOAT_VERSION)
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
            messagebox.showerror("X32 Gain Float — erreur au démarrage", "%s: %s" % (type(e).__name__, e))
        except Exception:
            raise
        raise


if __name__ == "__main__":
    main()
