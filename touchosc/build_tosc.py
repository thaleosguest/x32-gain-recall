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
BANKS = ["1-16", "17-32", "33-48", "49-64", "65-80"]
DRAG_STEP_PX = 5         # glisser vertical sur un potard : 5 px par pas de 0,5 dB (~10 px par dB ; 72 dB = 720 px)

# 16 tranches + LR, comme la page Mixer
STRIP_X0, STRIP_PITCH, STRIP_W = 14, 116, 112
LR_X = STRIP_X0 + STRIP_PITCH * 16
# rangées (y, hauteur), de haut en bas comme la LV1
SRC, AB, PRE, PHASE, TRIM, NAME, PAN, MUTE, FVAL, PEAK, FADER, NUM, CUE = (
    (70, 54), (128, 30), (162, 152), (320, 30), (356, 74), (434, 30), (468, 52), (524, 30), (558, 26), (584, 22),
    (612, 474), (1090, 30), (1124, 30))
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
           label(g + "src", (x, PRE[0] + 4, w, 22), "", 13, MUTED)]
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
    return out


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


def build():
    root = Node("GROUP", "root", (0, 0, W, H), {"color": BG, "background": True},
                script=lua("root.lua", PROTO=P.PROTO, PORT_IN=P.PORT_IN, PORT_OUT=P.PORT_OUT, STRIPS=16))
    # rangée du haut (à la place des User keys de la LV1)
    root.add(
        box("header", (0, 0, W, 62), PANEL),
        label("title", (12, 8, 280, 46), "X/M32 GAIN RECALL", 22),
        *button("follow", (864, 8, 170, 46), "FOLLOW LV1", "/xgr/view/follow", size=20),
        label("g_title", (1046, 8, 300, 46), "", 24, BLUE),
        label("notify", (1350, 8, 380, 46), "", 18, ORANGE),
        *button("sync", (1740, 8, 150, 46), "SYNC", P.SYNC, size=22),
        box("led", (1910, 12, 38, 38), Color(90, 90, 90)),
    )
    for n, text in enumerate(BANKS):           # banques : vue de CETTE tablette (la LV1 ne bouge pas)
        root.add(*button("bank%d" % n, (300 + 112 * n, 8, 104, 46), text, "/xgr/view/bank", arg=n, size=20))
    for k in range(1, 17):
        root.add(*strip(k))
    root.add(*lr_strip())
    root.add(                                   # ligne d'état en bas, puis panneau de connexion PAR-DESSUS tout
        label("console", (14, 1164, 600, 30), "-", 16, MUTED),
        label("lv1", (630, 1164, 700, 30), "-", 16, MUTED),
        label("tablets", (1340, 1164, 300, 30), "-", 16, MUTED),
        label("footer", (1660, 1164, 330, 30), "X/M32 Gain Recall - protocol %d" % P.PROTO, 14, MUTED),
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
