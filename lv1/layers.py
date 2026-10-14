"""Couche (« layer ») affichée sur la LV1, lue dans sa base de travail (même copie que le patch).

Établi le 2026-10-12 sur LV1 V17, en changeant UNE couche à la fois dans la LV1 et en comparant la base
avant/après (puis avec un enregistreur de toutes les écritures) : la LV1 écrit aussitôt, sans
sauvegarde, dans `surface_property_int` (libellés dans `surface_type` / `surface_property_type`) :
  - surface 2 = eSurface_OVV1 (vue « Mixer 1 » ; 3 = OVV2, « Mixer 2 ») ;
  - propriété 12 = eProp_LayersMode, valeurs de `ovv_track_mapping_type` :
      0 Factory  : configuration ≤ 64 canaux ; page 0-3 = Ch 1-16 .. Ch 49-64, page 4 = Grp/Fx ;
      1 CustomL  : couches Custom, page 0-7 = « Page-1 » .. « Page-8 » ;
      4 InptChn  : configuration 80 canaux ; page 0-4 = Ch 1-16 .. Ch 65-80 ;
      5 BussChn  : configuration 80 canaux ; groupes, FX, auxiliaires… (pas des entrées) ;
  - propriété 14 = eProp_LayersPage : la page dans ce mode.
Couches Custom : `ovv_layer` (surface_type 2 = Mixer 1, une ligne par page, dans l'ordre des id) et
`ovv_layer_track` (layer_id, obj_id, strip_index 0-15) ; obj_id -> `object` (obj_type 0 = canal
d'entrée, obj_index = canal 0-based). Les autres obj_type (groupes, FX…) n'ont pas de préampli.
Comportement interne non documenté par Waves : à revérifier après une mise à jour de la LV1.
"""
import sqlite3

SURFACE_MIXER1 = 2
PROP_LAYERS_MODE = 12
PROP_LAYERS_PAGE = 14
MODE_FACTORY, MODE_CUSTOM, MODE_INPUTS, MODE_BUSSES = 0, 1, 4, 5
TALKBACK = -8          # Talk Back (même clé que lv1/session_patch.py)
# Tranches des couches non-entrées qui ont une entrée réglable, par mode : {mode: {page: {tranche: canal}}}.
# Couche « Masters » : LR, Center, Sub, -, Cue, Talk Back, -, -, Matrix 1-8 -> Talk Back = 6e tranche.
# Disposition fixe de la LV1 (pas dans la base), relevée par Joseph le 2026-10-12 (enregistreur + captures) :
#   - 80 canaux : mode BussChn (5), pages Groups, Fx, Mon 1-16, Mon 17-24, Masters (4), Link DCA ;
#   - 64 canaux : mode Factory (0), pages Ch 1-16..49-64 (0-3), Grp/Fx, Monitor, Masters (6), Link DCA.
OTHER_PAGE_INPUTS = {MODE_BUSSES: {4: {5: TALKBACK}}, MODE_FACTORY: {6: {5: TALKBACK}}}
INPUT_PAGES = {MODE_FACTORY: 4, MODE_INPUTS: 5}   # pages de canaux d'entrée par mode
STRIPS = 16


def _custom_channels(con, surface, page):
    """16 entrées (canal LV1 1-based, ou None) de la page Custom `page` de la surface."""
    layers = [r[0] for r in con.execute("SELECT id FROM ovv_layer WHERE surface_type = ? ORDER BY id", (surface,))]
    if not 0 <= page < len(layers):
        return None
    out = [None] * STRIPS
    for strip, obj_type, obj_index in con.execute(
            "SELECT t.strip_index, o.obj_type, o.obj_index FROM ovv_layer_track t "
            "JOIN object o ON o.id = t.obj_id WHERE t.layer_id = ?", (layers[page],)):
        if 0 <= strip < STRIPS and obj_type == 0:
            out[strip] = obj_index + 1
        elif 0 <= strip < STRIPS and obj_type == 8:      # Talk Back
            out[strip] = TALKBACK
    return out


def read_layer(con, surface=SURFACE_MIXER1):
    """{"mode", "page", "bank", "channels"} pour la surface demandée (Mixer 1 par défaut), ou None si la
    base n'a pas ces propriétés.
      bank     : banque de 16 canaux d'entrée affichée (0 = Ch 1-16 … 4 = Ch 65-80), sinon None ;
      channels : les 16 canaux LV1 des 16 tranches affichées (None = tranche sans canal d'entrée), ou
                 None si la couche affichée ne contient pas de canaux d'entrée (Grp/Fx…)."""
    try:
        rows = dict(con.execute(
            "SELECT property, value FROM surface_property_int WHERE surface = ? AND property IN (?, ?)",
            (surface, PROP_LAYERS_MODE, PROP_LAYERS_PAGE)).fetchall())
        if PROP_LAYERS_PAGE not in rows:
            return None
        mode, page = rows.get(PROP_LAYERS_MODE), rows[PROP_LAYERS_PAGE]
        bank = channels = None
        if mode in INPUT_PAGES and 0 <= page < INPUT_PAGES[mode]:
            bank = page
            channels = list(range(page * STRIPS + 1, page * STRIPS + STRIPS + 1))
        elif mode == MODE_CUSTOM:
            channels = _custom_channels(con, surface, page)
        elif page in OTHER_PAGE_INPUTS.get(mode, {}):
            spots = OTHER_PAGE_INPUTS[mode][page]
            channels = [spots.get(i) for i in range(STRIPS)]
        preset = _mode_preset(con, surface, mode, page)
    except sqlite3.Error:
        return None
    bays = preset[2] if preset else None
    return {"mode": mode, "page": page, "bank": bank, "channels": channels,
            "preset": preset[0] if preset else None, "preset_name": preset[1] if preset else None,
            "bays": bays, "input_bay": _input_bay(bays)}


SECTION_INPUT = 0         # ovv_section_mapping_type : 0 = Input (cadres Preamp / Gain / 48)


def _input_bay(bays):
    """Rangée où la section Input (cadres Preamp / Gain / 48) est VISIBLE : "top", "middle" ou None.
    Relevé le 2026-10-14 (enregistreur + captures) : Big Fader masque Middle et Bottom (seul Top reste) ; Input en
    Bottom est recouvert par les faders (seuls Polarity / Trim restent visibles) -> rien à régler à l'écran."""
    if not bays:
        return None
    top, middle, _bottom, big = bays
    if top == SECTION_INPUT:
        return "top"
    if middle == SECTION_INPUT and not big:
        return "middle"
    return None


SURFACE_MIXER2 = 3


def read_layers(con):
    """{"mixer1": couche de la vue Mixer 1, "mixer2": couche de la vue Mixer 2} (read_layer).
    Établi le 2026-10-12 : Mixer 2 = surface 3, mêmes propriétés et mêmes tables que Mixer 1."""
    return {"mixer1": read_layer(con, SURFACE_MIXER1), "mixer2": read_layer(con, SURFACE_MIXER2)}


def _mode_preset(con, surface, mode, page):
    """(id, nom, (top, middle, bottom, big_faders)) du mode affiché dans le panneau « Modes » de la LV1 (Home, Setup, SndChk, Edit, Fx,
    Monitor, Status, Dugan) pour la page courante, ou None.
    Établi le 2026-10-12 avec l'enregistreur : chaque clic dans « Modes » réécrit
    `ovv_page_data.selected_mode_preset_id` (-> `ovv_modes_presets`) ; 8 lignes par mode de couche
    (`ovv_track_mode` de la surface), une par page, dans l'ordre des id. En couche Custom le mode est
    propre à chaque page ; en couches d'entrée, un clic change les 8 pages d'un coup."""
    tm = con.execute("SELECT id FROM ovv_track_mode WHERE surface_type = ? AND track_mapping_type = ?",
                     (surface, mode)).fetchone()
    if not tm:
        return None
    rows = con.execute(
        "SELECT selected_mode_preset_id, section_mapping_type_top_bay, section_mapping_type_middle_bay, "
        "section_mapping_type_bottom_bay, big_faders FROM ovv_page_data WHERE track_mode_id = ? ORDER BY id",
        (tm[0],)).fetchall()
    if not rows:
        return None
    row = rows[page] if 0 <= page < len(rows) else rows[0]
    pid = row[0]
    name = con.execute("SELECT preset_name FROM ovv_modes_presets WHERE id = ?", (pid,)).fetchone()
    # sections Top / Middle / Bottom et Big Fader de la page (relevé 2026-10-14 : réécrits aussitôt, sans
    # sauvegarde, à chaque changement dans le panneau « Modes » ; libellés dans ovv_section_mapping_type)
    return pid, (name[0] if name else None), tuple(row[1:5])
