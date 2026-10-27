"""touchosc/views.py — ce que la tablette affiche, calculé depuis l'état de Gain Recall (merged_snapshot). Fonctions pures.

Page GAINS (phase 2a, 27/10/2026) = calque du float en vue LV1 : les 16 tranches de la couche affichée sur la LV1
(Mixer 1), chaque tranche = un canal LV1 (couleur, nom) et les préamplis X32 qui l'alimentent (canal -> EXP par
lv1_sources, EXP -> préampli par exp_map inversée, comme x32_qt_float / x32_gain_float._lv1_layout : un EXP qu'aucun
préampli n'alimente n'a pas de voie, jamais deviné). Canal stéréo = deux voies (gauche, droite), gains NON liés.

strip_tag / exp_txt : mêmes règles que x32_gain_float (pas importé : il importe x32_gain_recall, où tourne le pont).
"""
from lv1.channelinfo import color_for

N_HA = 128                   # préamplis par console (x32_gain_recall.N_HA)
GAIN_MIN, GAIN_MAX = -12.0, 60.0
STRIPS = 16


def strip_tag(idx):
    """« L 15 » (Local), « A 1 » / « B 3 » (AES50-A / B) ; console 2… : « 2·A 5 » (x32_gain_float.strip_tag)."""
    if idx >= N_HA:
        return "%d·%s" % (idx // N_HA + 1, strip_tag(idx % N_HA))
    if idx < 32:
        return "L %d" % (idx + 1)
    if idx < 80:
        return "A %d" % (idx - 31)
    return "B %d" % (idx - 79)


def exp_txt(e):
    """« 15 », ou « 2·15 » pour la voie 15 de la carte de la console 2 (x32_gain_float.exp_txt)."""
    e = int(e)
    return str(e) if e < 1000 else "%d·%d" % (e // 1000 + 1, e % 1000)


# Course du fader de la LV1 (dB -> 0..1, haut = +10), relevée sur la capture de la page Mixer de Joseph (27/10) ; sert
# aussi aux vumètres (même échelle à côté du fader). -144 = -inf.
LV1_FADER = [(10.0, 1.0), (0.0, 0.765), (-10.0, 0.53), (-20.0, 0.415), (-30.0, 0.295), (-40.0, 0.18), (-60.0, 0.07),
             (-144.0, 0.0)]
LR_KEY = (3, 0)          # piste LR (groupe 3) : lecture seule sur la tablette (Joseph, 27/10, comme la X-Touch)


def fader_frac(db):
    if db is None or db <= LV1_FADER[-1][0]:
        return 0.0
    if db >= LV1_FADER[0][0]:
        return 1.0
    for (d1, p1), (d2, p2) in zip(LV1_FADER, LV1_FADER[1:]):
        if d2 <= db <= d1:
            return round(p2 + (p1 - p2) * (db - d2) / (d1 - d2), 4)
    return 0.0


def level_text(db, inf_below=-143.9):
    """Valeur de fader / crête comme la LV1 : « -4.5 », « -Inf »."""
    if db is None:
        return "-"
    return "-Inf" if db <= inf_below else "%.1f" % db


def mix_info(mixer, key, chan_info=None):
    """Piste (g, c) du mixer de la LV1 -> ce que la tranche affiche (phase 5a, lecture seule) ; None si la LV1 ne l'a
    pas annoncée. Pan : celui annoncé, sinon celui de la base (chan_info, la LV1 ne l'envoie pas à la connexion)."""
    t = (mixer or {}).get(key)
    if t is None:
        return None
    pan = t.get("pan")
    if pan is None:
        pan = (chan_info or {}).get("pan")
    meter = t.get("meter")
    return {"fader": t.get("fader"), "mute": bool(t.get("mute")), "solo": bool(t.get("solo")),
            "pan": 0.0 if pan is None else float(pan), "trim": (t.get("trim") or {}).get(0),
            "phase": any((t.get("phase") or {}).values()), "meter": meter,
            "input": (chan_info or {}).get("input") or "A"}


def gain_frac(db):
    """dB -> 0..1 sur la course du préampli X32 (-12..+60), pour le potard."""
    if db is None:
        return 0.0
    return max(0.0, min(1.0, (float(db) - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)))


def db_text(db):
    return "-" if db is None else "%.1f" % float(db)


def layer_title(lay):
    """Nom court de la couche LV1 affichée : « Ch 17-32 », « Custom 3 », « No input channels »."""
    if not lay or not lay.get("channels"):
        return "No input channels on this layer"
    if lay.get("bank") is not None:
        a = lay["bank"] * STRIPS + 1
        return "Ch %d-%d" % (a, a + STRIPS - 1)
    if lay.get("mode") == 1:
        return "Custom %d" % ((lay.get("page") or 0) + 1)
    return "Layer %d" % ((lay.get("page") or 0) + 1)


def card_slots(state):
    """{console k: place de sa carte dans le rack de la LV1} (le « 1- » de « 1- EX 1 »), d'après consoles[].card."""
    out = {}
    for c in (state or {}).get("consoles") or []:
        try:
            if c.get("card"):
                out[int(c.get("n") or 0)] = int(c["card"])
        except (TypeError, ValueError):
            pass
    return out


def input_name(e, slots):
    """Nom de la source LV1 d'un EXP, comme sur le bouton de source de la LV1 : « 1- EX 15 » (carte en place 1) ;
    « EX 15 » si la place de la carte de cette console n'est pas connue."""
    k, voie = divmod(int(e), 1000)
    return ("%d- EX %d" % (slots[k], voie)) if k in slots else "EX %d" % voie


def input_names(exps, slots):
    """Bouton de source d'une tranche : « 1- EX 1 » ; stéréo de la même carte en une ligne, « 1- EX 31/32 » (TouchOSC
    n'affiche pas le retour à la ligne de la LV1, essai de Joseph du 27/10 : « - EX 31 1- EX 3 »)."""
    names = [input_name(e, slots) for e in exps]
    if len(names) == 2 and names[0].rsplit(" ", 1)[0] == names[1].rsplit(" ", 1)[0]:
        return "%s/%s" % (names[0], names[1].rsplit(" ", 1)[1])
    return " + ".join(names)


def _info(channels, ch):
    return (channels or {}).get(str(ch)) or (channels or {}).get(ch) or {}


def bank_count(state):
    """Banques de 16 entrées (1-16 … 65-80) d'après le nombre de canaux LV1 connus : jeu « input » de secours quand la
    télécommande de la LV1 n'a encore donné aucun jeu de couches."""
    n = int((state or {}).get("lv1_count") or 0)
    return max(1, min(5, (n + STRIPS - 1) // STRIPS)) if n else 4


MASTERS_RO = (3, 4, 5)   # LR, C, M : lecture seule sur la tablette (décision de Joseph, 27/10)
KINDS = ("factory", "input", "mix", "custom")


def layer_sets(state, surface="mixer1"):
    """Jeux de couches proposés : {mode: [(nom, [(g, c) | None])]} — ceux vus par la télécommande (lv1/model.py, mémorisés),
    sinon un jeu « input » construit d'après le nombre de canaux (banques Ch 1-16 …). Custom = pages de `surface`."""
    known = ((state or {}).get("lv1_sets") or {}).get("sets") or {}
    view = 0 if surface == "mixer1" else 1
    out = {k: known[k] for k in ("factory", "input", "mix") if known.get(k)}
    if known.get("custom%d" % view):
        out["custom"] = known["custom%d" % view]
    if not out.get("factory") and not out.get("input"):
        out["input"] = [("Ch %d-%d" % (b * STRIPS + 1, b * STRIPS + STRIPS), [(0, b * STRIPS + i) for i in range(STRIPS)])
                        for b in range(bank_count(state))]
    if out.get("factory"):                       # 16 / 32 / 64 canaux : un seul jeu (pas de mode Input / Mix)
        out.pop("input", None)
        out.pop("mix", None)
    return out


def shown_layer(state, surface="mixer1"):
    """(mode, n° de couche, entrées, nom) affiché sur la LV1 : jeu adopté par la télécommande (Custom et Spill compris),
    sinon la couche lue dans la base (lv1/layers.py, entrées seulement). None si rien."""
    view = 0 if surface == "mixer1" else 1
    sh = (((state or {}).get("lv1_sets") or {}).get("shown") or {}).get(view)
    if sh and sh.get("layers") and 0 <= sh.get("index", -1) < len(sh["layers"]):
        name, entries = sh["layers"][sh["index"]]
        return sh.get("kind"), sh["index"], entries, name
    lay = ((state or {}).get("lv1_layers") or {}).get(surface) or (
        (state or {}).get("lv1_layer") if surface == "mixer1" else None) or {}
    if lay.get("channels"):
        entries = [(0, ch - 1) if ch and ch > 0 else None for ch in lay["channels"]]
        return ("input" if lay.get("bank") is not None else None), lay.get("bank"), entries, layer_title(lay)
    return None


def gain_page(state, surface="mixer1", view=None):
    """Page Mixer (couches LV1, 27/10) : {"title", "follow", "kinds", "kind", "index", "names", "strips", "live", "lr"}.
    view None = couche affichée sur la LV1 (Mixer 1, comme le float) ; (mode, n°) = vue fixe de la tablette (la LV1 ne
    bouge pas). Tranche : entrée (g 0 : préampli X32, Trim, Ø, A / B), bus (groupes, Fx, Mon, DCA : fader, MUTE, CUE,
    pan) ou master en lecture seule (LR, C, M). « key » = (groupe, canal) visé par les commandes de la LV1."""
    state = state or {}
    sets = layer_sets(state, surface)
    kinds = [k for k in KINDS if k in sets]
    entries, title, kind, index = [], "No input channels on this layer", None, None
    if view is not None and view[0] in sets and 0 <= view[1] < len(sets[view[0]]) and sets[view[0]][view[1]][1]:
        kind, index = view
        title, entries = sets[kind][index]
    else:
        view = None
        sh = shown_layer(state, surface)
        if sh:
            kind, index, entries, title = sh
    entries = list(entries or [])[:STRIPS]
    entries += [None] * (STRIPS - len(entries))
    exp_to_idx = {}
    for k, e in (state.get("exp_map") or {}).items():
        if e:
            exp_to_idx.setdefault(int(e), int(k))
    sources = {int(k): v for k, v in (state.get("lv1_sources") or {}).items()}
    slots = card_slots(state)
    gains, phantom = state.get("gains") or [], state.get("phantom") or []
    mixer = state.get("lv1_mixer") or {}
    strips = []
    for key in entries:
        if not key:
            strips.append({"ch": 0, "key": None, "kind": "", "label": "", "name": "", "color": "", "units": [],
                           "src": "", "input": "", "mix": None})
            continue
        g, c = key
        if g != 0:                                   # bus / master : pas de préampli X32, pas de Trim / Ø / A-B
            t = mixer.get((g, c)) or {}
            pal = t.get("pal")
            color = (color_for(pal) or "").lstrip("#").upper() if pal is not None else ""
            name = t.get("name") or ""
            strips.append({"ch": c + 1, "key": (g, c), "kind": "ro" if g in MASTERS_RO else "bus", "label": name,
                           "name": name, "color": color if len(color) == 6 else "", "units": [], "src": "", "input": "",
                           "mix": mix_info(mixer, (g, c)) if t else None})
            continue
        ch = c + 1
        info = _info(state.get("lv1_channels"), ch)
        exps = [int(e) for e in sources.get(ch, []) if e]
        idxs = [exp_to_idx[e] for e in exps if e in exp_to_idx]
        units = [{"idx": i, "db": gains[i] if i < len(gains) else None,
                  "phantom": bool(phantom[i]) if i < len(phantom) and phantom[i] is not None else False}
                 for i in idxs]
        # comme le float sur la LV1 : « A1 = EXP 1 », « A7/8 = EXP 7/8 » (sans espace après la lettre : tient dans la case)
        tags = [strip_tag(i).replace(" ", "") for i in idxs]
        if len(idxs) == 2 and strip_tag(idxs[0]).split()[0] == strip_tag(idxs[1]).split()[0]:
            src = "%s/%s" % (tags[0], strip_tag(idxs[1]).split()[1])
        else:
            src = " + ".join(tags)
        mapped = [e for e in exps if e in exp_to_idx]
        if mapped:
            src += " = EXP " + "/".join(exp_txt(e) for e in mapped)
        color = (info.get("color") or "").lstrip("#").upper()
        label = info.get("label") or "In %d" % ch
        strips.append({"ch": ch, "key": (0, c), "kind": "in", "label": label, "name": info.get("name") or label,
                       "color": color if len(color) == 6 else "", "units": units, "src": src or "no X32 preamp",
                       "input": input_names(exps, slots), "mix": mix_info(mixer, (0, c), info)})
    names = [n for n, _e in sets.get(kind, [])] if kind in sets else []
    names += [""] * (8 - len(names))
    return {"title": title, "follow": view is None, "kinds": kinds, "kind": kind, "index": index, "names": names[:8],
            "strips": strips, "live": bool(state.get("lv1_live")), "lr": mix_info(mixer, LR_KEY)}


def unit_idx(page, k, u):
    """Préampli de la voie u (« m », « l », « r ») de la tranche k (1..16) de la page affichée, ou None (la tranche a
    changé entre l'affichage et le geste)."""
    if not page or not 1 <= k <= len(page["strips"]):
        return None
    units = page["strips"][k - 1]["units"]
    names = unit_names(len(units))
    return units[names.index(u)]["idx"] if u in names else None


def scene_info(created):
    """Date d'une scène pour la liste : « 27/10 14:32 » (ISO enregistré par Gain Recall), sinon le texte tel quel."""
    c = str(created or "")
    if len(c) >= 16 and c[4] == "-" and c[10] == "T":
        return "%s/%s %s" % (c[8:10], c[5:7], c[11:16])
    return c


def last_recall_text(lr):
    """Dernier rappel (état de Gain Recall, last_recall) : « Last recall: 'Show 1', 32 gains, verified »."""
    if not lr or not lr.get("name") and not lr.get("sent_gain"):
        return "No recall yet"
    parts = ["%d gains" % (lr.get("sent_gain") or 0)]
    if lr.get("sent_phantom"):
        parts.append("%dx 48V" % lr["sent_phantom"])
    if lr.get("bad"):
        parts.append("%d NOT confirmed" % len(lr["bad"]))
    elif lr.get("verified"):
        parts.append("verified")
    elif lr.get("verified") is None:
        parts.append("checking...")
    return "Last recall: '%s', %s" % (lr.get("name") or "?", ", ".join(parts))


def scene_page(state):
    """Page SCENES (phase 3a) : {"items": [{"id", "name", "info"}], "last", "can_undo"} — scènes dans l'ordre du
    magasin de Gain Recall (comme le float)."""
    state = state or {}
    items = [{"id": p.get("id") or "", "name": p.get("name") or "(no name)", "info": scene_info(p.get("created"))}
             for p in state.get("presets") or []]
    return {"items": items, "last": last_recall_text(state.get("last_recall")), "can_undo": bool(state.get("can_undo"))}


def unit_names(n):
    """Emplacements des voies dans une tranche du template : mono « m » (pleine largeur), stéréo « l » + « r »."""
    return {1: ["m"], 2: ["l", "r"]}.get(n, [])
