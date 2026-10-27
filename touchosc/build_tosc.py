"""touchosc/build_tosc.py — génère le template TouchOSC de la tablette (paysage 2000 x 1200 : Doogee R10 de Joseph ;
TouchOSC met à l'échelle sur un autre écran).

    py -m touchosc.build_tosc [sortie.tosc]      (défaut : dist/touchosc/XM32_Gain_Recall_LV1.tosc)

Phase 0 (27/10/2026) : présence. Phase 1 : état, SYNC, messages. Phase 2a/2b : page GAINS (16 tranches de la couche LV1,
banques + FOLLOW LV1 par tablette, gain au glisser vertical drag.lua, 48V à confirmer phantom.lua).
Phase 2c : DA voulue par Joseph = une PAGE MIXER DE LA LV1 (sa capture du 27/10), tranche par tranche de haut en bas :
bouton de source (« 1- EX 1 », couleur du canal), A / B, cadre préampli (le float : « A 1 = EXP 1 », potard(s) côte à
côte, dB, 48V), Ø + Trim, bandeau du nom, pan, MUTE, valeur du fader + crête, fader + échelle + vumètre, numéro, cue ;
tranche LR à droite. Ø / Trim / pan / MUTE / fader / cue / A-B / LR sont des commandes de la LV1 : dessinées GRISÉES,
sans effet, jusqu'à la phase 5 (contrôle de la LV1).
"""
import os
import sys

from . import protocol as P
from . import views
from .tosc import Color, Node, write

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(ROOT, "dist", "touchosc", "XM32_Gain_Recall_LV1.tosc")
W, H = 2000, 1200

# Couleurs relevées sur la LV1 (CLAUDE.md, « Style LV1 »)
BG, PANEL, TEXT, MUTED, LINE = Color(71, 71, 71), Color(17, 17, 17), Color(231, 231, 231), Color(160, 160, 160), \
    Color(120, 120, 120)
ORANGE, DARK, CLEAR = Color(255, 153, 38), Color(43, 43, 43), Color(0, 0, 0, 0)
INK = Color(17, 17, 17)                   # texte posé sur une couleur de canal (bandeaux de la LV1)
BLUE, TEAL, LR_BLUE = Color(56, 201, 255), Color(15, 162, 171), Color(68, 138, 255)
OFF = Color(90, 90, 90)                   # commandes de la LV1 : gris tant que la LV1 n'est pas connectée
METER = Color(60, 200, 90)                # vumètres
DRAG_STEP_PX = 5         # glisser vertical sur un potard : 5 px par pas de 0,5 dB (~10 px par dB ; 72 dB = 720 px)
PAN_PX_FULL = 120        # pan : 120 px du centre à un côté (pas de 1/45 ~ 2,7 px)
TRIM_STEP_PX, TRIM_LIMIT = 6, 30   # Trim : 6 px par pas de 0,5 dB ; ±30 dB comme XTouch-LV1 (la LV1 borne elle-même)

# 16 tranches + LR, comme la page Mixer
STRIP_X0, STRIP_PITCH, STRIP_W = 14, 116, 112
LR_X = STRIP_X0 + STRIP_PITCH * 16
# rangées (y, hauteur), de haut en bas comme la LV1
# (27/10 : tout descend de 50 px sous la rangée des couches, le fader raccourcit d'autant)
NAV_Y, NAV_H = 66, 48
SRC, AB, PRE, PHASE, TRIM, NAME, PAN, MUTE, FVAL, PEAK, FADER, NUM, CUE = (
    (120, 54), (178, 30), (212, 152), (370, 30), (406, 74), (484, 30), (518, 52), (574, 30), (608, 26), (634, 22),
    (662, 424), (1090, 30), (1124, 30))
# échelle du fader (fraction de la course, relevée sur la capture de Joseph)
SCALE = [("10", 0.0), ("0", 0.235), ("-10", 0.47), ("-20", 0.585), ("-30", 0.705), ("-40", 0.82), ("-60", 0.93),
         ("-inf", 1.0)]
# voies du cadre préampli : mono « m » au centre, stéréo « l » / « r » côte à côte (comme le float sur la LV1)
#   (décalage x, largeur, taille du potard, taille du dB, largeur du 48V, taille du texte 48V)
UNITS = {"m": (0, STRIP_W, 60, 20, 56, 13), "l": (0, STRIP_W // 2, 46, 15, 44, 11),
         "r": (STRIP_W // 2, STRIP_W // 2, 46, 15, 44, 11)}


def lua(name, **tokens):
    with open(os.path.join(HERE, "template", name), encoding="utf-8") as f:
        src = f.read()
    for k, v in tokens.items():
        src = src.replace("__%s__" % k, str(v))
    if "__" in src.replace("__index", "").replace("__newindex", ""):
        raise ValueError("jeton non remplacé dans %s" % name)
    return src


def label(name, frame, text, size, color=TEXT):
    return Node("LABEL", name, frame, {"background": False, "textSize": size, "textColor": color,
                                       "interactive": False, "outline": False}, values={"text": text})


def box(name, frame, color, **props):
    return Node("BOX", name, frame, dict({"color": color, "background": True, "interactive": False, "outline": False},
                                         **props))


def button(name, frame, text, osc, arg=None, size=30):
    """Bouton au style LV1 (fond 17, liseré 160, texte 231) qui envoie `osc` (avec `arg` entier) à l'appui. Libellé =
    LABEL posé dessus, non interactif (le toucher passe au bouton)."""
    x, y, w, h = frame
    script = ("function onValueChanged(key)\n"
              "  if key == 'x' and self.values.x == 1 then sendOSC('%s'%s) end\n"
              "end\n" % (osc, "" if arg is None else ", %d" % arg))
    return [Node("BUTTON", name, frame, {"color": MUTED, "background": False, "outline": True}, script=script),
            label(name + "_label", (x, y, w, h), text, size)]


def overlay(name, frame, script):
    """Bouton TRANSPARENT posé sur une case dessinée (48V, potard) : reçoit le toucher, la case garde son apparence."""
    return Node("BUTTON", name, frame, {"color": CLEAR, "background": False, "outline": False}, script=script)


def lv1_key(name, frame, text, size=16):
    """Commande de la LV1 pas encore branchée (phase 5) : case à liseré gris, texte gris, sans effet."""
    return [box(name, frame, PANEL, outline=True), label(name + "_l", frame, text, size, OFF)]


def fader_block(g, x):
    """Fader (grisé, phase 5), son échelle et la place du vumètre, comme la page Mixer."""
    y, h = FADER
    out = [Node("FADER", g + "fader", (x + 14, y, 34, h), {"color": OFF, "background": True, "outline": False,
                                                            "interactive": False}),
           Node("FADER", g + "meter", (x + 52, y, 8, h), {"color": METER, "background": True, "outline": False,
                                                           "interactive": False})]       # vumètre : barre, lecture seule
    for i, (t, f) in enumerate(SCALE):
        out.append(label("%sscale%d" % (g, i), (x + 60, y + int(f * (h - 20)), 50, 20), t, 13, OFF))
    return out


def strip(k):
    """Tranche k (1..16), de haut en bas comme la LV1. Actif : source, cadre préampli (gain au glisser, 48V à
    confirmer), bandeau du nom, numéro. Grisé (commandes de la LV1, phase 5) : A / B, Ø, Trim, pan, MUTE, fader, cue."""
    x = STRIP_X0 + STRIP_PITCH * (k - 1)
    g = "g%d_" % k
    w = STRIP_W
    out = [box(g + "srcbox", (x, SRC[0], w, SRC[1]), DARK),
           label(g + "input", (x, SRC[0], w, SRC[1]), "", 17, INK),
           *lv1_key(g + "a", (x + 4, AB[0], w // 2 - 6, AB[1]), "A", 16),
           *lv1_key(g + "b", (x + w // 2 + 2, AB[0], w // 2 - 6, AB[1]), "B", 16),
           box(g + "pre", (x, PRE[0], w, PRE[1]), PANEL, outline=True),
           label(g + "src", (x, PRE[0] + 4, w, 22), "", 12, MUTED)]
    py = PRE[0]
    for u, (dx, uw, knob, db_size, ph_w, ph_size) in UNITS.items():
        ux = x + dx
        path = "/xgr/g/%d/%s/" % (k, u)
        ph = (ux + (uw - ph_w) // 2, py + 120, ph_w, 24)
        out += [Node("RADIAL", g + u + "_knob", (ux + (uw - knob) // 2, py + 30 + (60 - knob) // 2, knob, knob),
                     {"color": MUTED, "background": True, "outline": False, "interactive": False}),
                overlay(g + u + "_drag", (ux, py + 26, uw, 66),     # glisser vertical sur la largeur de la voie
                        lua("drag.lua", PATH=path + "gain", KNOB=g + u + "_knob", DB=g + u + "_db",
                            GMIN=views.GAIN_MIN, GSPAN=views.GAIN_MAX - views.GAIN_MIN, STEP_PX=DRAG_STEP_PX)),
                label(g + u + "_db", (ux, py + 92, uw, 26), "-", db_size),
                box(g + u + "_48", ph, DARK, outline=True),
                label(g + u + "_48l", ph, "48V", ph_size, MUTED),
                overlay(g + u + "_48b", ph, lua("phantom.lua", PATH=path + "48v", LABEL=g + u + "_48l"))]
    out += [*lv1_key(g + "phase", (x + 6, PHASE[0], w - 12, PHASE[1]), "Ø", 18),
            label(g + "trim_t", (x + 4, TRIM[0], 54, 28), "Trim", 16, OFF),
            label(g + "trim_v", (x + 58, TRIM[0], 50, 28), "-", 16, OFF),
            Node("RADIAL", g + "trim", (x + w // 2 - 20, TRIM[0] + 32, 40, 40),
                 {"color": OFF, "background": True, "outline": False, "interactive": False}),
            box(g + "band", (x, NAME[0], w, NAME[1]), DARK),
            label(g + "name", (x, NAME[0], w, NAME[1]), "", 17, INK),
            label(g + "pan_a", (x + 4, PAN[0], 20, 22), "A", 13, OFF),
            Node("RADIAL", g + "pan", (x + w // 2 - 24, PAN[0] + 2, 48, 48),
                 {"color": OFF, "background": True, "outline": False, "interactive": False}),
            *lv1_key(g + "mute", (x + 10, MUTE[0], w - 20, MUTE[1]), "MUTE", 16),
            label(g + "fval", (x, FVAL[0], w, FVAL[1]), "-", 19, OFF),
            label(g + "peak", (x, PEAK[0], w, PEAK[1]), "-", 15, OFF),
            *fader_block(g, x),
            box(g + "numbar", (x, NUM[0], w, NUM[1]), DARK),
            label(g + "num", (x, NUM[0], w - 8, NUM[1]), "", 17, INK),
            *lv1_key(g + "cue", (x + 20, CUE[0], w - 40, CUE[1]), "CUE", 14)]
    # phase 5b : gestes sur les commandes de la LV1 (boutons transparents par-dessus ; LR n'en a aucun)
    base = "/xgr/g/%d/set/" % k
    out += [overlay(g + "fader_drag", (x, FADER[0], w, FADER[1]),
                    lua("fader.lua", PATH=base + "fader", FADER=g + "fader", FVAL=g + "fval", H=FADER[1] - 20,
                        CURVE="{ %s }" % ", ".join("{%s, %s}" % p for p in views.LV1_FADER))),
            overlay(g + "pan_drag", (x, PAN[0], w, PAN[1]),
                    lua("pan.lua", PATH=base + "pan", KNOB=g + "pan", PX_FULL=PAN_PX_FULL)),
            overlay(g + "trim_drag", (x, TRIM[0], w, TRIM[1]),
                    lua("trim.lua", PATH=base + "trim", KNOB=g + "trim", VAL=g + "trim_v", STEP_PX=TRIM_STEP_PX,
                        LIMIT=TRIM_LIMIT, SPAN=P.TRIM_SPAN)),
            overlay(g + "mute_b", (x + 10, MUTE[0], w - 20, MUTE[1]), tap(base + "mute")),
            overlay(g + "cue_b", (x + 20, CUE[0], w - 40, CUE[1]), tap(base + "solo")),
            overlay(g + "phase_b", (x + 6, PHASE[0], w - 12, PHASE[1]), tap(base + "phase"))]
    return out


def tap(path):
    """Script d'un bouton d'appui (MUTE, CUE, Ø) : envoie la bascule ; Gain Recall part de l'état annoncé par la LV1."""
    return ("function onValueChanged(key)\n"
            "  if key == 'x' and self.values.x == 1 then sendOSC('%s') end\n"
            "end\n" % path)


def lr_strip():
    """Tranche LR (master), comme la page Mixer : tout grisé jusqu'à la phase 5."""
    x, w, g = LR_X, STRIP_W, "lr_"
    return [box(g + "srcbox", (x, SRC[0], w, SRC[1]), LR_BLUE),
            box(g + "pre", (x, PRE[0], w, PRE[1]), PANEL, outline=True),
            box(g + "band", (x, NAME[0], w, NAME[1]), LR_BLUE),
            label(g + "name", (x, NAME[0], w, NAME[1]), "LR", 17, INK),
            *lv1_key(g + "c", (x + 14, PAN[0] + 2, 36, 30), "C", 14),
            *lv1_key(g + "m", (x + 62, PAN[0] + 2, 36, 30), "M", 14),
            *lv1_key(g + "mute", (x + 10, MUTE[0], w - 20, MUTE[1]), "MUTE", 16),
            label(g + "fval", (x, FVAL[0], w, FVAL[1]), "-", 19, OFF),
            label(g + "peak", (x, PEAK[0], w, PEAK[1]), "-", 15, OFF),
            *fader_block(g, x),
            box(g + "numbar", (x, NUM[0], w, NUM[1]), LR_BLUE),
            label(g + "num", (x, NUM[0], w - 8, NUM[1]), "LR", 17, INK),
            *lv1_key(g + "cue", (x + 20, CUE[0], w - 40, CUE[1]), "CUE", 14)]


def hidden(name, text=""):
    """Libellé invisible qui sert de variable partagée entre les scripts de la page (sélection, page de liste…)."""
    return Node("LABEL", name, (0, 0, 10, 10), {"visible": False, "interactive": False, "background": False},
                values={"text": text})


def key(name, frame, text, size, script, color=PANEL):
    """Case au style LV1 (fond, liseré gris, texte) + bouton transparent par-dessus qui porte le script."""
    return [box(name, frame, color, outline=True), label(name + "_l", frame, text, size),
            overlay(name + "_b", frame, script)]


SC_ROWS, SC_ROW_Y, SC_ROW_H = 12, 150, 76


def scenes_page():
    """Page SCENES (phase 3a, le panneau Scènes du float) : liste paginée (sélection sur la tablette), RECALL confirmé
    (« OK? » puis 2e appui) avec « + 48V », UNDO, SAVE (nom automatique). Cachée au départ."""
    g = Node("GROUP", "page_scenes", (0, 0, W, H), {"background": False, "visible": False})
    g.add(label("sc_title", (40, 76, 600, 60), "SCENES", 30), hidden("sc_sel"), hidden("sc_off", "0"),
          hidden("sc_selid"), hidden("sc_ph", "0"), hidden("sc_count", "0"),
          box("sc_list", (40, 140, 1180, 920), PANEL, outline=True))
    for r in range(1, SC_ROWS + 1):
        y = SC_ROW_Y + (SC_ROW_H + 0) * (r - 1)
        g.add(box("sc_row%d" % r, (50, y, 1160, SC_ROW_H - 4), DARK),
              label("sc_row%d_name" % r, (70, y, 800, SC_ROW_H - 4), "", 28),
              label("sc_row%d_info" % r, (880, y, 310, SC_ROW_H - 4), "", 22, MUTED),
              overlay("sc_row%d_b" % r, (50, y, 1160, SC_ROW_H - 4),
                      "function onValueChanged(key)\n"
                      "  if key == 'x' and self.values.x == 1 then\n"
                      "    self.parent:findByName('sc_sel', false).values.text = '%d'\n"
                      "  end\nend\n" % r))
    page_step = ("function onValueChanged(key)\n"
                 "  if key ~= 'x' or self.values.x ~= 1 then return end\n"
                 "  local off = self.parent:findByName('sc_off', false)\n"
                 "  local n = tonumber(self.parent:findByName('sc_count', false).values.text) or 0\n"
                 "  local o = (tonumber(off.values.text) or 0) + %d\n"
                 "  if o >= 0 and o < n then off.values.text = tostring(o) end\n"
                 "end\n")
    g.add(*key("sc_prev", (50, 1072, 200, 60), "<", 30, page_step % -SC_ROWS),
          *key("sc_next", (1010, 1072, 200, 60), ">", 30, page_step % SC_ROWS),
          label("sc_pageinfo", (260, 1072, 740, 60), "", 22, MUTED),
          box("sc_side", (1260, 140, 700, 920), PANEL, outline=True),
          label("sc_sel_name", (1290, 160, 640, 70), "No scene selected", 34),
          label("sc_sel_info", (1290, 230, 640, 40), "", 22, MUTED),
          box("sc_recall", (1290, 300, 400, 110), PANEL, outline=True),
          label("sc_recall_l", (1290, 300, 400, 110), "RECALL", 36),
          overlay("sc_recall_b", (1290, 300, 400, 110), lua("recall.lua")),
          *key("sc_48", (1710, 300, 220, 110), "+ 48V", 28,
               "function onValueChanged(key)\n"
               "  if key ~= 'x' or self.values.x ~= 1 then return end\n"
               "  local ph = self.parent:findByName('sc_ph', false)\n"
               "  local on = ph.values.text ~= '1'\n"
               "  ph.values.text = on and '1' or '0'\n"
               "  self.parent:findByName('sc_48', false).color = on and Color(209/255, 52/255, 59/255, 1)"
               " or Color(17/255, 17/255, 17/255, 1)\n"
               "end\n"),
          *key("sc_undo", (1290, 430, 300, 90), "UNDO", 28, tap("/xgr/sc/undo")),
          *key("sc_save", (1630, 430, 300, 90), "SAVE NEW", 28, tap("/xgr/sc/save")),
          label("sc_last", (1290, 560, 640, 120), "", 22, MUTED),
          label("sc_help", (1290, 900, 640, 140), "Tap a scene, then RECALL twice (confirm). + 48V also recalls the "
                "phantom power. SAVE NEW stores the current gains (rename it on the PC).", 18, MUTED))
    return g


def routing_page():
    """Page ROUTING (phase 3b, à venir). Cachée au départ."""
    g = Node("GROUP", "page_routing", (0, 0, W, H), {"background": False, "visible": False})
    g.add(label("rt_title", (40, 76, 600, 60), "ROUTING", 30),
          label("rt_soon", (40, 300, 1900, 80), "Routing profiles: coming next (phase 3b)", 30, MUTED))
    return g


def nav_row():
    """Rangée des couches (page Mixer), comme la colonne de la LV1 : modes INPUT (ou FACTORY en 16 / 32 / 64 canaux), MIX
    (80 canaux) et CUSTOM, puis les 8 couches du mode affiché, aux noms de la LV1. Vue de CETTE tablette."""
    out = [hidden("nav_kinds"), hidden("nav_kind")]
    first = ("local k = self.parent:findByName('nav_kinds', false).values.text\n"
             "  sendOSC('/xgr/view/layer', k:find('factory') and 'factory' or 'input', 0)")
    for n, (m, text, send) in enumerate((("a", "INPUT", first), ("mix", "MIX", "sendOSC('/xgr/view/layer', 'mix', 0)"),
                                         ("custom", "CUSTOM", "sendOSC('/xgr/view/layer', 'custom', 0)"))):
        out += key("nav_kind_" + m, (14 + 136 * n, NAV_Y, 130, NAV_H), text, 20,
                   "function onValueChanged(key)\n  if key ~= 'x' or self.values.x ~= 1 then return end\n  %s\nend\n"
                   % send)
    for n in range(1, 9):
        out += key("nav_l%d" % n, (430 + 150 * (n - 1), NAV_Y, 144, NAV_H), "", 20,
                   "function onValueChanged(key)\n"
                   "  if key ~= 'x' or self.values.x ~= 1 then return end\n"
                   "  local kind = self.parent:findByName('nav_kind', false).values.text\n"
                   "  if kind ~= '' then sendOSC('/xgr/view/layer', kind, %d) end\n"
                   "end\n" % (n - 1))
    return out


def build():
    root = Node("GROUP", "root", (0, 0, W, H), {"color": BG, "background": True},
                script=lua("root.lua", PROTO=P.PROTO, PORT_IN=P.PORT_IN, PORT_OUT=P.PORT_OUT, STRIPS=16))
    # pages (phase 3a) : une seule visible à la fois, choisie par les onglets ; la page Mixer = la page Mixer de la LV1
    mixer = Node("GROUP", "page_mixer", (0, 0, W, H), {"background": False})
    mixer.add(*nav_row())
    for k in range(1, 17):
        mixer.add(*strip(k))
    mixer.add(*lr_strip())
    root.add(mixer, scenes_page(), routing_page())
    # rangée du haut (à la place des User keys de la LV1) : onglets, banques + FOLLOW (page Mixer), état
    root.add(box("header", (0, 0, W, 62), PANEL))
    for n, (page, text) in enumerate((("mixer", "MIXER"), ("scenes", "SCENES"), ("routing", "ROUTING"))):
        x, y, w, h = 12 + 116 * n, 8, 108, 46
        root.add(Node("BUTTON", "tab_" + page, (x, y, w, h), {"color": MUTED, "background": False, "outline": True},
                      script=lua("tab.lua", PAGE=page)),
                 label("tab_%s_label" % page, (x, y, w, h), text, 20, BLUE if page == "mixer" else TEXT))
    root.add(
        *button("follow", (370, 8, 170, 46), "FOLLOW LV1", "/xgr/view/follow", size=18),
        label("g_title", (550, 8, 520, 46), "", 24, BLUE),
        label("notify", (1080, 8, 650, 46), "", 18, ORANGE),
        *button("sync", (1740, 8, 150, 46), "SYNC", P.SYNC, size=22),
        box("led", (1910, 12, 38, 38), Color(90, 90, 90)),
    )
    root.add(                                   # ligne d'état en bas, puis panneau de connexion PAR-DESSUS tout
        label("console", (14, 1164, 520, 30), "-", 16, MUTED),
        label("lv1", (550, 1164, 640, 30), "-", 16, MUTED),
        label("tablets", (1200, 1164, 220, 30), "-", 16, MUTED),
        label("footer", (1430, 1164, 560, 30), "X/M32 GAIN RECALL - protocol %d" % P.PROTO, 14, MUTED),
        box("panel", (100, 250, 1800, 600), PANEL),
        box("panel_line", (100, 250, 1800, 4), LINE),
        label("status", (140, 330, 1720, 120), "Looking for X/M32 Gain Recall...", 44),
        label("detail", (140, 480, 1720, 90), "", 26, MUTED),
    )
    return root


def main(argv):
    out = argv[1] if len(argv) > 1 else DEFAULT_OUT
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    n = write(build(), out)
    print("Template : %s (%d octets, protocole %d)" % (out, n, P.PROTO))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
