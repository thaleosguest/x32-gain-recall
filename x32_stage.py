"""PATCH DE SCÈNE (3.1, demande de Joseph du 20/10/2026) : les faces des boîtiers Behringer (S16, X32 Rack, X32,
M32C), chaque prise physique nommée et colorée (« Kick » sur S16 IN 1), et le nom qui suit la prise jusqu'à la LV1.

Chaîne (rien de deviné, tout est lu) :
    prise « A:in:1 »  ->  préampli X32 (AES50-A 1 = n° 32)  ->  EXP (exp_map, routing lu sur la console)
                      ->  canal(aux) LV1 (lv1_sources, patch lu dans la base de la LV1)

Feuilles de patch : une par spectacle / studio, séparées des scènes de gains (choix de Joseph) ; une feuille active.
Renommage automatique des canaux LV1 (choix de Joseph) : voir lv1_renames() pour les règles (on ne touche jamais un
nom tapé à la main dans la LV1). Canal stéréo : nom de la voie GAUCHE (choix de Joseph).

Module sans interface (pas de Qt) : modèles d'appareils, clés de prises, stockage, calculs. Faces dessinées dans
x32_qt_stage.py.
"""
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime

N_HA = 128                          # préamplis par console (x32_gain_recall.N_HA)
SLOTS = ("local", "A", "B")         # emplacements d'une console : ses prises, puis ses ports AES50
SLOT_BASE = {"local": 0, "A": 32, "B": 80}        # n° du préampli de l'entrée 1 (Local 1-32, AES50-A/B 1-48)
SLOT_TAG = {"local": "L", "A": "A", "B": "B"}


# --------------------------------------------------------------------------
#  Appareils : prises et géométrie des faces
# --------------------------------------------------------------------------
# Coordonnées en fractions de la face (x de gauche à droite, y de haut en bas), vue que Joseph a devant lui pour
# brancher : face AVANT de la S16 (entrées et sorties devant), face ARRIÈRE des X32 / X32 Rack (prises derrière :
# IN 1 est donc à DROITE, comme sur les photos).
def _row(io, first, last, x0, x1, y):
    """Prises first..last réparties de x0 à x1 (first à x0 ; last < first = numéros décroissants vers la droite)."""
    n = abs(last - first)
    step = (x1 - x0) / n if n else 0
    d = 1 if last >= first else -1
    return [(io, first + k * d, x0 + k * step, y) for k in range(n + 1)]


DEVICES = {
    "s16": {
        "name": "S16", "view": "avant", "ratio": 4.8, "slots": ("A", "B"),
        "ins": 16, "outs": 8,
        "sockets": _row("in", 1, 8, 0.088, 0.445, 0.36) + _row("in", 9, 16, 0.088, 0.445, 0.76)
                   + _row("out", 1, 8, 0.545, 0.905, 0.76),
        # repères de début de rangée « A 1 » / « A 9 » (croquis de Joseph)
        "tags": [(1, 0.035, 0.12), (9, 0.035, 0.52)],
        "deco": [("box", 0.49, 0.06, 0.95, 0.52, "S16"), ("box", 0.49, 0.56, 0.95, 0.97, "")],
    },
    "x32r": {
        "name": "X32 Rack", "view": "arrière", "ratio": 3.2, "slots": ("local", "A", "B"),
        "ins": 16, "outs": 8,
        "sockets": _row("in", 8, 1, 0.575, 0.935, 0.30) + _row("in", 16, 9, 0.575, 0.935, 0.62)
                   + _row("out", 8, 1, 0.045, 0.435, 0.47),
        "tags": [(1, 0.965, 0.12), (9, 0.965, 0.44)],
        "deco": [("box", 0.02, 0.13, 0.46, 0.32, "TALKBACK · AUX IN / OUT"),
                 ("box", 0.10, 0.66, 0.52, 0.95, "EXPANSION SLOT"),
                 ("box", 0.54, 0.80, 0.96, 0.95, "ETHERNET · MIDI · ULTRANET · AES50 B / A")],
    },
    "x32": {
        "name": "X32", "view": "arrière", "ratio": 3.4, "slots": ("local", "A", "B"),
        "ins": 32, "outs": 16,
        "sockets": _row("in", 16, 9, 0.425, 0.665, 0.36) + _row("in", 8, 1, 0.705, 0.945, 0.36)
                   + _row("in", 32, 25, 0.425, 0.665, 0.62) + _row("in", 24, 17, 0.705, 0.945, 0.62)
                   + _row("out", 8, 1, 0.145, 0.385, 0.36) + _row("out", 16, 9, 0.145, 0.385, 0.62),
        "tags": [(1, 0.972, 0.20), (17, 0.972, 0.46)],
        "deco": [("box", 0.02, 0.24, 0.12, 0.72, "MONITOR"),
                 ("box", 0.14, 0.80, 0.40, 0.96, "SLOT"),
                 ("box", 0.42, 0.80, 0.68, 0.96, "USB · ETHERNET · MIDI · AES50 B / A"),
                 ("box", 0.70, 0.80, 0.96, 0.96, "AUX IN / OUT")],
    },
    "m32c": {
        # cœur sans préampli : ses prises sont sur les boîtiers de ses ports AES50
        "name": "M32C", "view": "arrière", "ratio": 9.0, "slots": ("local",),
        "ins": 0, "outs": 0, "sockets": [], "tags": [],
        "deco": [("box", 0.03, 0.15, 0.40, 0.85, "SLOT DN32-WSG"), ("box", 0.45, 0.15, 0.97, 0.85, "AES50 A · AES50 B")],
    },
}
DEVICE_ORDER = ("s16", "x32r", "x32", "m32c")


def default_devices(model):
    """Appareils par défaut d'une console d'après son modèle (/info) : ses propres prises ; S16 sur le port A sauf
    pour une X32 pleine taille (elle a 32 entrées). Modifiable dans le panneau."""
    m = (model or "").upper().replace(" ", "")
    if "RACK" in m or m == "M32R":
        local = "x32r"
    elif m in ("M32C", "X32CORE", "M32CORE"):
        local = "m32c"
    elif m in ("X32", "M32"):
        local = "x32"
    else:
        local = None
    return {"local": local, "A": "s16" if local != "x32" else None, "B": None}


def port_key(slot, io, n):
    return "%s:%s:%d" % (slot, io, int(n))


def parse_key(key):
    slot, io, n = str(key).split(":")
    if slot not in SLOTS or io not in ("in", "out"):
        raise ValueError("prise inconnue : %s" % key)
    return slot, io, int(n)


def port_tag(key, console=0):
    """« A1 », « L15 » (console 2 : « 2·A1 ») pour une entrée ; « A OUT 7 » pour une sortie."""
    slot, io, n = parse_key(key)
    t = SLOT_TAG[slot] + (str(n) if io == "in" else " OUT %d" % n)
    return ("%d·" % (console + 1) + t) if console else t


def port_preamp(key, console=0):
    """N° global du préampli (k·N_HA + i) d'une ENTRÉE, None pour une sortie. Local 1-32 = 0-31, AES50-A = 32-79,
    AES50-B = 80-127 (comme x32_gain_float.strip_tag)."""
    slot, io, n = parse_key(key)
    if io != "in":
        return None
    lim = 32 if slot == "local" else 48
    if not 1 <= n <= lim:
        return None
    return console * N_HA + SLOT_BASE[slot] + n - 1


def preamp_port(idx):
    """(console, clé de prise) d'un préampli global : inverse de port_preamp."""
    k, i = divmod(int(idx), N_HA)
    if i < 32:
        return k, port_key("local", "in", i + 1)
    if i < 80:
        return k, port_key("A", "in", i - 31)
    return k, port_key("B", "in", i - 79)


# --------------------------------------------------------------------------
#  Feuilles de patch
# --------------------------------------------------------------------------
def clean_label(v):
    """{"name", "color"} propre, ou None (prise sans étiquette). color = n° de la palette LV1 (0-31) ou None."""
    if not isinstance(v, dict):
        return None
    name = re.sub(r"\s+", " ", str(v.get("name") or "")).strip()[:24]
    color = v.get("color")
    try:
        color = int(color) if color is not None else None
    except (TypeError, ValueError):
        color = None
    if color is not None and not 0 <= color <= 31:
        color = None
    if not name and color is None:
        return None
    return {"name": name, "color": color}


EXPORT_TYPE = "x32-stage-patch"           # fichier d'une feuille exportée (« Concert A.stagepatch.json »)
EXPORT_EXT = ".stagepatch.json"


def clean_consoles(consoles):
    """Partie « consoles » d'une feuille venue d'un fichier : seules les prises, étiquettes et appareils valables sont
    gardés (fichier modifié à la main, autre version : jamais d'erreur à l'import, le reste est ignoré)."""
    out = {}
    for k, c in (consoles or {}).items() if isinstance(consoles, dict) else ():
        try:
            k = str(int(k))
        except (TypeError, ValueError):
            continue
        if not isinstance(c, dict):
            continue
        ports = {}
        for key, lab in (c.get("ports") or {}).items() if isinstance(c.get("ports"), dict) else ():
            try:
                parse_key(key)
            except (ValueError, AttributeError):
                continue
            lab = clean_label(lab)
            if lab:
                ports[key] = lab
        devs = c.get("devices") if isinstance(c.get("devices"), dict) else {}
        devices = {}
        for slot in SLOTS:
            d = devs.get(slot)
            devices[slot] = d if d in DEVICES and slot in DEVICES[d]["slots"] else None
        entry = {"devices": devices, "ports": ports}
        if devs:
            entry["devices_set"] = True
        out[k] = entry
    return out


def new_sheet(name, consoles=None):
    return {"id": uuid.uuid4().hex[:12], "name": (name or "Patch")[:60],
            "created": datetime.now().isoformat(timespec="seconds"), "consoles": consoles or {}}


def sheet_console(sheet, console, model=None):
    """Partie d'une feuille pour la console n° console (0-based) : {"devices", "ports"} (créée au besoin)."""
    c = sheet.setdefault("consoles", {}).setdefault(str(console), {})
    if not isinstance(c.get("devices"), dict) or (model and not c.get("devices_set")):
        c["devices"] = default_devices(model)      # suit le modèle de la console tant qu'on n'a rien choisi
    c.setdefault("ports", {})
    return c


def labels_by_preamp(sheet):
    """{préampli global: étiquette} des entrées étiquetées de la feuille."""
    out = {}
    for k, c in ((sheet or {}).get("consoles") or {}).items():
        for key, v in (c.get("ports") or {}).items():
            try:
                idx = port_preamp(key, int(k))
            except ValueError:
                continue
            v = clean_label(v)
            if idx is not None and v:
                out[idx] = v
    return out


def exp_ports(exp_map):
    """{EXP: "console:clé de prise"} pour chaque EXP alimenté par un préampli (étiqueté ou non)."""
    out = {}
    for idx, e in (exp_map or {}).items():
        if e:
            k, key = preamp_port(int(idx))
            out.setdefault(int(e), "%d:%s" % (k, key))
    return out


def left_port(exps, ports):
    """Prise de la voie gauche d'abord (canal stéréo), ou None."""
    for e in exps:
        if int(e) in ports:
            return ports[int(e)]
    return None


def labels_by_exp(sheet, exp_map):
    """{EXP: (étiquette, clé de prise, console)} : l'étiquette de la prise qui alimente chaque EXP (exp_map =
    {préampli global: EXP}, lu sur la console). Un EXP sans préampli connu n'a pas d'étiquette."""
    byp = labels_by_preamp(sheet)
    out = {}
    for idx, e in (exp_map or {}).items():
        if not e:
            continue
        lab = byp.get(int(idx))
        if lab:
            k, key = preamp_port(int(idx))
            out.setdefault(int(e), (lab, key, k))
    return out


def port_chain(key, console, exp_map, lv1_sources, lv1_channels):
    """Où va une entrée : {"preamp", "exp", "lv1": [(canal, côté, libellé, couleur)]} (exp None si l'entrée n'arrive
    sur aucun EXP)."""
    idx = port_preamp(key, console)
    exp = None
    if idx is not None:
        for i, e in (exp_map or {}).items():
            if int(i) == idx and e:
                exp = int(e)
                break
    lv1 = []
    if exp is not None:
        for ch, exps in (lv1_sources or {}).items():
            exps = [int(x) for x in exps if x]
            if exp in exps:
                side = "" if len(exps) == 1 else ("L" if exps.index(exp) == 0 else "R")
                info = (lv1_channels or {}).get(str(ch)) or (lv1_channels or {}).get(ch) or {}
                lv1.append((int(ch), side, info.get("label") or "In %s" % ch, info.get("color")))
    return {"preamp": idx, "exp": exp, "lv1": sorted(lv1)}


class StageStore:
    """x32_stage_patch.json : {"version", "active", "sheets": [...], "applied": {canal: {...}}, "auto": bool}.
    « applied » = ce que l'appli a écrit dans la LV1 (garde-fou du renommage automatique)."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.sheets, self.active, self.applied, self.auto = [], None, {}, True
        self.load()
        if not self.sheets:
            sh = new_sheet("Patch 1")
            self.sheets.append(sh)
            self.active = sh["id"]

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            self.sheets = [s for s in d.get("sheets", []) if isinstance(s, dict) and s.get("id")]
            self.active = d.get("active")
            self.applied = {int(k): v for k, v in (d.get("applied") or {}).items()}
            self.auto = bool(d.get("auto", True))
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            try:
                os.replace(self.path, self.path + ".corrompu-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            except OSError:
                pass

    def _write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "active": self.active, "auto": self.auto, "sheets": self.sheets,
                       "applied": {str(k): v for k, v in self.applied.items()}}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def _get(self, sid):
        return next((s for s in self.sheets if s["id"] == sid), None)

    def current(self):
        """Copie de la feuille active (la 1re si l'id actif a disparu)."""
        with self.lock:
            sh = self._get(self.active) or (self.sheets[0] if self.sheets else None)
            return json.loads(json.dumps(sh)) if sh else None

    def summaries(self):
        with self.lock:
            return [{"id": s["id"], "name": s["name"], "ports": sum(len(c.get("ports") or {})
                                                                    for c in s.get("consoles", {}).values())}
                    for s in self.sheets]

    def state(self, models=()):
        """Pour /api/stage : liste des feuilles, feuille active complète (consoles connues complétées)."""
        with self.lock:
            sh = self._get(self.active) or self.sheets[0]
            for k, model in enumerate(models):
                sheet_console(sh, k, model)
            return {"sheets": self.summaries(), "active": sh["id"], "sheet": json.loads(json.dumps(sh)),
                    "auto": self.auto, "applied": {str(k): v for k, v in self.applied.items()}}

    def set_port(self, console, key, label, model=None):
        parse_key(key)
        with self.lock:
            sh = self._get(self.active) or self.sheets[0]
            ports = sheet_console(sh, int(console), model)["ports"]
            lab = clean_label(label)
            if lab:
                ports[key] = lab
            else:
                ports.pop(key, None)
            self._write()
            return lab

    def set_device(self, console, slot, device, model=None):
        if slot not in SLOTS or (device is not None and device not in DEVICES):
            raise ValueError("appareil inconnu")
        if device and slot not in DEVICES[device]["slots"]:
            raise ValueError("%s ne se branche pas sur %s" % (DEVICES[device]["name"], slot))
        with self.lock:
            sh = self._get(self.active) or self.sheets[0]
            c = sheet_console(sh, int(console), model)
            c["devices"][slot] = device
            c["devices_set"] = True
            self._write()

    def sheet_action(self, action, sid=None, name=None):
        """new / duplicate / rename / delete / activate. Rend l'id de la feuille concernée."""
        with self.lock:
            name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
            if action == "new":
                sh = new_sheet(name or "Patch %d" % (len(self.sheets) + 1))
                cur = self._get(self.active)
                if cur:                                  # mêmes appareils que la feuille active, prises vides
                    sh["consoles"] = {k: {"devices": dict(c.get("devices") or {}), "ports": {},
                                          "devices_set": bool(c.get("devices_set"))}
                                      for k, c in cur.get("consoles", {}).items()}
                self.sheets.append(sh)
                self.active = sh["id"]
            elif action == "duplicate":
                src = self._get(sid or self.active)
                if not src:
                    raise ValueError("feuille introuvable")
                sh = json.loads(json.dumps(src))
                sh.update(id=uuid.uuid4().hex[:12], name=name or src["name"] + " (copie)",
                          created=datetime.now().isoformat(timespec="seconds"))
                self.sheets.append(sh)
                self.active = sh["id"]
            elif action == "rename":
                sh = self._get(sid)
                if not sh or not name:
                    raise ValueError("feuille introuvable ou nom vide")
                sh["name"] = name
            elif action == "delete":
                if len(self.sheets) <= 1:
                    raise ValueError("Il faut garder au moins une feuille")
                self.sheets = [s for s in self.sheets if s["id"] != sid]
                if self.active == sid:
                    self.active = self.sheets[0]["id"]
            elif action == "activate":
                if not self._get(sid):
                    raise ValueError("feuille introuvable")
                self.active = sid
            else:
                raise ValueError("action inconnue")
            self._write()
            return self.active

    def export_sheet(self, sid=None):
        """Document à écrire dans un fichier : une feuille (nom, appareils, étiquettes), sans id."""
        with self.lock:
            sh = self._get(sid or self.active)
            if not sh:
                raise ValueError("feuille introuvable")
            return {"type": EXPORT_TYPE, "version": 1, "exported": datetime.now().isoformat(timespec="seconds"),
                    "sheet": {"name": sh["name"], "consoles": json.loads(json.dumps(sh.get("consoles") or {}))}}

    def import_sheet(self, doc):
        """Ajoute la feuille d'un fichier exporté (nouvel id ; nom déjà pris -> « (2) », « (3) »…) et la rend active.
        Rend la feuille ajoutée."""
        if not isinstance(doc, dict) or doc.get("type") != EXPORT_TYPE or not isinstance(doc.get("sheet"), dict):
            raise ValueError("Ce fichier n'est pas une feuille de patch exportée")
        src = doc["sheet"]
        base = re.sub(r"\s+", " ", str(src.get("name") or "")).strip()[:60] or "Patch importé"
        with self.lock:
            names = {s["name"] for s in self.sheets}
            name, n = base, 2
            while name in names:
                name, n = "%s (%d)" % (base[:54], n), n + 1
            sh = new_sheet(name, clean_consoles(src.get("consoles")))
            self.sheets.append(sh)
            self.active = sh["id"]
            self._write()
            return json.loads(json.dumps(sh))

    def set_auto(self, on):
        with self.lock:
            self.auto = bool(on)
            self._write()

    def mark_applied(self, ch, entry):
        with self.lock:
            if entry is None:
                self.applied.pop(int(ch), None)
            else:
                self.applied[int(ch)] = entry
            self._write()


# --------------------------------------------------------------------------
#  Renommage automatique des canaux LV1
# --------------------------------------------------------------------------
def is_default_name(ch, name):
    name = (name or "").strip()
    return not name or bool(re.fullmatch(r"Channel\s*%d" % int(ch), name, re.I))


def palette_index(color):
    """N° de palette LV1 d'une couleur « #RRGGBB » (lv1/channelinfo.PALETTE), None si hors palette."""
    from lv1.channelinfo import PALETTE
    try:
        return [c.upper() for c in PALETTE].index((color or "").upper())
    except ValueError:
        return None


def lv1_color_targets(sheet, exp_map, lv1_sources, lv1_info, applied=None):
    """Couleurs à donner dans la LV1 (bouton « Couleurs -> LV1 », clics : lv1/colorclick.py) : {canal: n° de palette}
    pour chaque canal alimenté par une prise étiquetée AVEC une couleur (canal stéréo : voie gauche d'abord), si sa
    couleur dans la LV1 est différente ; et couleur par défaut (n° 13) pour un canal dont l'étiquette de la prise a été
    effacée (Clear : `applied[ch]["cleared"]`, même prise toujours branchée, nom resté « Channel N » ; Joseph : « il
    prendra la forme d'une piste par défaut »). lv1_info = {canal: {"name", "color": "#RRGGBB"}} (clés int ou str)."""
    by_exp = labels_by_exp(sheet, exp_map)
    ports = exp_ports(exp_map)
    out = {}
    for ch, mine in (applied or {}).items():
        ch = int(ch)
        exps = (lv1_sources or {}).get(ch) or (lv1_sources or {}).get(str(ch)) or []
        info = (lv1_info or {}).get(ch) or (lv1_info or {}).get(str(ch)) or {}
        if (mine or {}).get("cleared") and mine.get("src") == left_port(exps, ports) \
                and not any(int(e) in by_exp for e in exps if e) \
                and is_default_name(ch, info.get("name")) and \
                (palette_index(info.get("color")) if info.get("color") else 13) != 13:
            out[ch] = 13
    for ch, exps in (lv1_sources or {}).items():
        ch = int(ch)
        if ch <= 0:
            continue
        idx = None
        for e in [int(x) for x in exps if x]:
            lab = by_exp.get(e, ({},))[0]
            if lab.get("color") is not None:
                idx = lab["color"]
                break
        if idx is None:
            continue
        info = (lv1_info or {}).get(ch) or (lv1_info or {}).get(str(ch)) or {}
        cur = palette_index(info.get("color")) if info.get("color") else 13
        if cur != idx:
            out[ch] = idx
    return out


def lv1_renames(sheet, exp_map, lv1_sources, lv1_info, applied, now=None, settle=5.0, with_color=True):
    """Ce qu'il faut écrire dans la LV1 : [{"ch", "name", "send_name", "color", "send_color", "why", "src", "label",
    "prev_name", "prev_color"}] (name = nom visé, envoyé si send_name ; color = n° de palette, envoyé si send_color ;
    une entrée sans rien à envoyer sert à noter dans `applied` la source prise en compte).

    Règles (renommage automatique, choix de Joseph du 20/10/2026 ; priorité revue le même jour) :
      - canal LV1 alimenté par une prise étiquetée (canal stéréo : voie GAUCHE, sinon la droite) -> nom de l'étiquette,
        et sa couleur si elle en a une ;
      - L'ÉTIQUETTE GAGNE quand le canal reçoit cette source (nouvelle prise, ou 1re fois vue) ou quand l'étiquette est
        modifiée dans STAGE PATCH, même sur un nom tapé à la main (Joseph : canal « test » sans source, EXP 4 attribué
        -> il prend le nom de la prise) ; le nom d'avant est gardé (prev_name) ;
      - ensuite, même source et même étiquette : un nom retapé à la main dans la LV1 est respecté (pas de bras de fer) ;
      - étiquette EFFACÉE (Clear) sur la prise qui alimente toujours le canal -> piste par défaut : « Channel N » et
        couleur n° 13 (couleur par le bouton « Couleurs -> LV1 » : marque `cleared` dans applied) ;
      - canal que l'appli avait nommé et passé sur une AUTRE source sans étiquette -> son nom d'avant (« test »), sinon
        nom par défaut, et sa couleur d'avant ; canal qui n'est plus patché du tout : laissé tel quel ;
      - un nom envoyé il y a moins de ``settle`` s n'est pas renvoyé (la base de la LV1 suit ~1 s plus tard).
    lv1_info = {canal: {"name": nom brut, "color": "#RRGGBB"}} ;
    applied = {canal: {"name", "src", "label", "prev_name", "color", "prev_color", "t"}}.
    """
    now = time.time() if now is None else now
    by_exp = labels_by_exp(sheet, exp_map)
    ports = exp_ports(exp_map)
    out = []
    for ch, exps in sorted((lv1_sources or {}).items(), key=lambda kv: int(kv[0])):
        ch = int(ch)
        if ch <= 0:                                  # Talk Back : pas un canal d'entrée renommable
            continue
        exps = [int(e) for e in exps if e]
        if not exps:
            continue
        lab, src = None, None
        for e in exps:                               # gauche d'abord
            if e in by_exp:
                lab, key, k = by_exp[e]
                src = "%d:%s" % (k, key)
                break
        info = (lv1_info or {}).get(ch) or (lv1_info or {}).get(str(ch)) or {}
        cur = (info.get("name") or "").strip()
        cur_col = palette_index(info.get("color")) if info.get("color") else None
        mine = (applied or {}).get(ch)
        default = is_default_name(ch, cur)
        recent = mine is not None and now - float(mine.get("t") or 0) < settle
        if lab and lab["name"]:
            fresh = mine is None or mine.get("src") != src or mine.get("label") != lab["name"]
            if not (fresh or default or cur == mine.get("name")):
                continue                             # renommé à la main après coup : respecté
            if not fresh and recent:
                continue                             # envoyé il y a peu : la base de la LV1 n'a pas encore suivi
            want_col = lab.get("color") if with_color else None
            send_name = cur != lab["name"]
            send_color = want_col is not None and want_col != cur_col
            if not (send_name or send_color or fresh):
                continue
            if mine is not None:
                prev_name, prev_col = mine.get("prev_name"), mine.get("prev_color")
            else:
                prev_name = None if default or cur == lab["name"] else cur
                prev_col = cur_col
            out.append({"ch": ch, "name": lab["name"], "send_name": send_name, "color": want_col,
                        "send_color": send_color, "why": "label", "src": src, "label": lab["name"],
                        "prev_name": prev_name, "prev_color": prev_col})
        elif mine is not None and cur == mine.get("name") and not default and not recent:
            here = left_port(exps, ports)
            if mine.get("src") and mine.get("src") == here:
                # même prise, étiquette effacée (Clear dans STAGE PATCH) : piste par défaut, « Channel N » + n° 13
                send_color = with_color and cur_col not in (None, 13)
                out.append({"ch": ch, "name": "Channel %d" % ch, "send_name": True, "color": 13 if send_color else None,
                            "send_color": send_color, "why": "cleared", "src": here, "label": None,
                            "prev_name": None, "prev_color": None})
                continue
            prev = mine.get("prev_color") if with_color else None
            send_color = prev is not None and prev != cur_col
            out.append({"ch": ch, "name": mine.get("prev_name") or "Channel %d" % ch, "send_name": True,
                        "color": prev if send_color else None, "send_color": send_color, "why": "restore",
                        "src": None, "label": None, "prev_name": None, "prev_color": None})
    return out
