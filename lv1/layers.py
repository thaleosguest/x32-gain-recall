"""Couche (« layer ») affichée sur la LV1, lue dans sa base de travail (même copie que le patch).

Établi le 2026-10-12 sur LV1 V17, en changeant UNE couche à la fois dans la LV1 et en comparant la base
avant/après : la LV1 écrit aussitôt, sans sauvegarde, dans `surface_property_int` (libellés dans
`surface_type` / `surface_property_type`) :
  - surface 2 = eSurface_OVV1 (vue « Mixer 1 » ; 3 = OVV2, « Mixer 2 ») ;
  - propriété 12 = eProp_LayersMode : 0 = Factory (ovv_track_mapping_type), 1 = Custom… ;
  - propriété 14 = eProp_LayersPage : en Factory, 0 = Ch 1-16, 1 = Ch 17-32, 2 = Ch 33-48,
    3 = Ch 49-64, 4 = Grp/Fx (au-delà : autres couches, pas des canaux d'entrée).
La même page se retrouve dans `ovv_track_mode.cur_page` (surface_type 2, track_mapping_type 0).
Comportement interne non documenté par Waves : à revérifier après une mise à jour de la LV1.
"""
import sqlite3

SURFACE_MIXER1 = 2
PROP_LAYERS_MODE = 12
PROP_LAYERS_PAGE = 14
MODE_FACTORY = 0
FACTORY_INPUT_PAGES = 4      # pages 0..3 = Ch 1-16 .. Ch 49-64


def read_layer(con, surface=SURFACE_MIXER1):
    """{"mode", "page", "bank"} pour la surface demandée (Mixer 1 par défaut), ou None si la base n'a pas
    ces propriétés. bank = numéro de la banque de 16 canaux d'entrée affichée (0 = Ch 1-16), ou None si
    la couche affichée n'est pas une couche Factory de canaux d'entrée (Grp/Fx, Custom…)."""
    try:
        rows = dict(con.execute(
            "SELECT property, value FROM surface_property_int WHERE surface = ? AND property IN (?, ?)",
            (surface, PROP_LAYERS_MODE, PROP_LAYERS_PAGE)).fetchall())
    except sqlite3.Error:
        return None
    if PROP_LAYERS_PAGE not in rows:
        return None
    mode, page = rows.get(PROP_LAYERS_MODE), rows[PROP_LAYERS_PAGE]
    bank = page if mode == MODE_FACTORY and 0 <= page < FACTORY_INPUT_PAGES else None
    return {"mode": mode, "page": page, "bank": bank}
