# -*- coding: utf-8 -*-
"""
lv1/channelinfo.py — Nom et couleur des canaux LV1, tels que la LV1 les range dans sa base de session
(CurrentLV1.dat / .emo), sans Companion.

Établi sur une LV1 V17 en cours (2026-10-12) :
  - nom    : snapshot_chainer.name (snapshot_id = -1 = état courant), chainer = objet canal
             (object.obj_type = 0, object.obj_index = canal 0-based)
  - couleur: snapshot_chainer_params.param_value pour param_id = 592 (snapshot_id = -1) : un NUMÉRO dans
             la palette fixe de la LV1 ci-dessous. Pas de ligne = couleur par défaut (n° 13, teal).
PALETTE relevée en donnant les 32 couleurs du sélecteur LV1 aux canaux In 33 à In 64, puis en lisant
pour chacun le numéro dans la base et la couleur RVB que la LV1 envoie (via Companion).
"""
import re

PARAM_COLOR = 592
PARAM_BALANCE, BALANCE_SCALE = 436, 45.0   # pan d'une entrée (-45..+45) : relevé par XTouch-LV1 (lv1_db.input_pans)
DEFAULT_COLOR_INDEX = 13
PALETTE = (
    "#5E98A0", "#448AFF", "#689F38", "#1A8E66", "#92C3C7", "#5C7182", "#F5BB41", "#EE0074",   # 0-7
    "#2962FF", "#38C9FF", "#8DF7FF", "#136A84", "#87A5D2", "#0FA2AB", "#00E676", "#75F6B7",   # 8-15
    "#8C51C0", "#EF9A9A", "#F3FA1D", "#FF4F4F", "#E7E7E7", "#A30000", "#8CFF00", "#A0A0A0",   # 16-23
    "#FA7B14", "#FF00FF", "#CE93D8", "#F06292", "#827717", "#946B7C", "#A04182", "#7C4DFF",   # 24-31
)


def color_for(index):
    """Couleur "#RRGGBB" d'un numéro de palette, ou None si le numéro est inconnu (jamais inventée)."""
    if index is None:
        index = DEFAULT_COLOR_INDEX
    try:
        i = int(index)
    except (TypeError, ValueError):
        return None
    return PALETTE[i] if 0 <= i < len(PALETTE) and i == index else None


def display_name(channel, name):
    """Nom à afficher pour le canal LV1 ``channel`` : son nom s'il a été renommé, sinon « In N » (nom par
    défaut « Channel N » de la LV1, ou nom inconnu : le numéro vient de la table de patch). "" si la
    voie n'arrive sur aucun canal."""
    if not channel:
        return ""
    name = (name or "").strip()
    if not name or re.fullmatch(r"Channel\s*%d" % int(channel), name, re.I):
        return "In %d" % int(channel)
    return name


# Bus / masters (28/10, tablette TouchOSC) : object.obj_type = n° de groupe de la télécommande OSC (1 Groups, 2 Fx, 3 LR,
# 4 Center, 5 Mono, 6 Matrix, 7 Cue, 8 Talk Back, 12 Link DCA, 25 Mon), couleur = même param 592. Pas de ligne = couleur
# d'usine du type, relevée sur la LV1 de Joseph (n° annoncé par /Notify/TrackColor pour les bus sans ligne). La
# télécommande n'envoie ces couleurs qu'au hasard des connexions (tout, une partie ou rien) : la base fait foi.
BUS_DEFAULT_COLOR = {1: 11, 2: 2, 3: 8, 4: 8, 5: 8, 6: 8, 7: 8, 8: 8, 12: 24, 25: 3}


def read_bus_colors(con):
    """{(groupe, index 0-based): n° de palette} des bus et masters, depuis une COPIE de la session ; {} si illisible."""
    try:
        objs = con.execute("SELECT id, obj_type, obj_index FROM object WHERE obj_type IN (%s)"
                           % ",".join(str(g) for g in BUS_DEFAULT_COLOR)).fetchall()
        colors = dict(con.execute("SELECT chainer_id, param_value FROM snapshot_chainer_params "
                                  "WHERE snapshot_id = -1 AND param_id = ?", (PARAM_COLOR,)).fetchall())
    except Exception:
        return {}
    out = {}
    for oid, g, c in objs:
        v = colors.get(oid)
        try:
            out[(g, c)] = int(v) if v is not None else BUS_DEFAULT_COLOR[g]
        except (TypeError, ValueError):
            pass
    return out


def read_channel_info(con):
    """{canal LV1 (1-based): {"name": str, "color": "#RRGGBB" | None}} depuis une connexion ouverte sur
    une COPIE de la session. {} si la session n'a pas ces tables (autre version de LV1)."""
    try:
        names = dict(con.execute("""
            SELECT o.obj_index + 1, sc.name FROM snapshot_chainer sc JOIN object o ON o.id = sc.chainer_id
            WHERE o.obj_type = 0 AND sc.snapshot_id = -1
        """).fetchall())
        params = """
            SELECT o.obj_index + 1, p.param_value FROM snapshot_chainer_params p JOIN object o ON o.id = p.chainer_id
            WHERE o.obj_type = 0 AND p.snapshot_id = -1 AND p.param_id = ?
        """
        colors = dict(con.execute(params, (PARAM_COLOR,)).fetchall())
        pans = dict(con.execute(params, (PARAM_BALANCE,)).fetchall())
    except Exception:
        return {}
    # pan : la LV1 ne l'annonce pas à la connexion (tablette TouchOSC, 3.2) ; pas de ligne = centre
    return {ch: {"name": (nm or "").strip(), "color": color_for(colors.get(ch)),
                 "pan": max(-1.0, min(1.0, float(pans.get(ch) or 0.0) / BALANCE_SCALE))} for ch, nm in names.items()}
