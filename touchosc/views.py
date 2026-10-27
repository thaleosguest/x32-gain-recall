"""touchosc/views.py — ce que la tablette affiche, calculé depuis l'état de Gain Recall (merged_snapshot). Fonctions pures.

Page GAINS (phase 2a, 27/10/2026) = calque du float en vue LV1 : les 16 tranches de la couche affichée sur la LV1
(Mixer 1), chaque tranche = un canal LV1 (couleur, nom) et les préamplis X32 qui l'alimentent (canal -> EXP par
lv1_sources, EXP -> préampli par exp_map inversée, comme x32_qt_float / x32_gain_float._lv1_layout : un EXP qu'aucun
préampli n'alimente n'a pas de voie, jamais deviné). Canal stéréo = deux voies (gauche, droite), gains NON liés.

strip_tag / exp_txt : mêmes règles que x32_gain_float (pas importé : il importe x32_gain_recall, où tourne le pont).
"""
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


def _info(channels, ch):
    return (channels or {}).get(str(ch)) or (channels or {}).get(ch) or {}


def bank_count(state):
    """Banques de 16 entrées que la tablette propose (1-16 … 65-80), d'après le nombre de canaux LV1 connus."""
    n = int((state or {}).get("lv1_count") or 0)
    return max(1, min(5, (n + STRIPS - 1) // STRIPS)) if n else 4


def gain_page(state, surface="mixer1", bank=None):
    """{"title", "follow", "bank", "banks", "strips": [16 x {"ch", "label", "color" (« RRGGBB » ou ""), "units":
    [{"idx", "db", "phantom"}], "src"}]}. bank None = couche affichée sur la LV1 (`surface`, Mixer 1 par défaut, comme
    le float) ; bank 0..4 = vue fixe de la tablette (Ch 1-16 … 65-80, phase 2b : la LV1 ne bouge pas)."""
    state = state or {}
    banks = bank_count(state)
    if bank is not None and 0 <= bank < banks:
        lay = {"mode": 0, "page": bank, "bank": bank,
               "channels": list(range(bank * STRIPS + 1, bank * STRIPS + STRIPS + 1))}
    else:
        bank = None
        lay = ((state.get("lv1_layers") or {}).get(surface) or (state.get("lv1_layer") if surface == "mixer1" else None)
               or {})
    chans = list(lay.get("channels") or [])[:STRIPS]
    chans += [None] * (STRIPS - len(chans))
    exp_to_idx = {}
    for k, e in (state.get("exp_map") or {}).items():
        if e:
            exp_to_idx.setdefault(int(e), int(k))
    sources = {int(k): v for k, v in (state.get("lv1_sources") or {}).items()}
    gains, phantom = state.get("gains") or [], state.get("phantom") or []
    strips = []
    for ch in chans:
        if not ch:
            strips.append({"ch": 0, "label": "", "color": "", "units": [], "src": ""})
            continue
        info = _info(state.get("lv1_channels"), ch)
        exps = [int(e) for e in sources.get(ch, []) if e]
        idxs = [exp_to_idx[e] for e in exps if e in exp_to_idx]
        units = [{"idx": i, "db": gains[i] if i < len(gains) else None,
                  "phantom": bool(phantom[i]) if i < len(phantom) and phantom[i] is not None else False}
                 for i in idxs]
        if len(idxs) == 2 and strip_tag(idxs[0]).split()[0] == strip_tag(idxs[1]).split()[0]:
            src = "%s/%s" % (strip_tag(idxs[0]), strip_tag(idxs[1]).split()[1])
        else:
            src = " + ".join(strip_tag(i) for i in idxs)
        mapped = [e for e in exps if e in exp_to_idx]
        if mapped:
            src += "  EXP " + "/".join(exp_txt(e) for e in mapped)
        color = (info.get("color") or "").lstrip("#").upper()
        strips.append({"ch": ch, "label": info.get("label") or ("In %d" % ch if ch > 0 else ""),
                       "color": color if len(color) == 6 else "", "units": units, "src": src or "no X32 preamp"})
    shown = lay.get("bank") if lay.get("channels") else None
    return {"title": layer_title(lay), "follow": bank is None, "bank": shown, "banks": banks, "strips": strips}


def unit_idx(page, k, u):
    """Préampli de la voie u (« m », « l », « r ») de la tranche k (1..16) de la page affichée, ou None (la tranche a
    changé entre l'affichage et le geste)."""
    if not page or not 1 <= k <= len(page["strips"]):
        return None
    units = page["strips"][k - 1]["units"]
    names = unit_names(len(units))
    return units[names.index(u)]["idx"] if u in names else None


def unit_names(n):
    """Emplacements des voies dans une tranche du template : mono « m » (pleine largeur), stéréo « l » + « r »."""
    return {1: ["m"], 2: ["l", "r"]}.get(n, [])
