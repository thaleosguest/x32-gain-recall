"""touchosc/build_tosc.py — génère le template TouchOSC de la tablette (DA LV1, paysage 2000 x 1200 : Doogee R10 de
Joseph ; TouchOSC met à l'échelle sur un autre écran).

    py -m touchosc.build_tosc [sortie.tosc]      (défaut : dist/touchosc/XM32_Gain_Recall_LV1.tosc)

Phase 0 (27/10/2026) : présence. Phase 1 : barre d'état, SYNC, messages. Phase 2a : page GAINS, 16 tranches calquées
sur la couche LV1 ; le panneau de connexion ne s'affiche que tant que Gain Recall ne répond pas. Phase 2b : banques
1-16 … 65-80 + FOLLOW LV1 (vue par tablette), potards de gain relatifs (knob.lua), 48V à confirmer (phantom.lua).
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
BANKS = ["1-16", "17-32", "33-48", "49-64", "65-80"]

# Page GAINS : 16 tranches de STRIP_W, au pas STRIP_PITCH, à partir de STRIP_X0
STRIP_X0, STRIP_PITCH, STRIP_W, STRIP_Y = 40, 120, 112, 180
# voies d'une tranche (y du haut, potard, taille du dB, 48V largeur x hauteur, taille, repère) : mono « m », stéréo
# « l » au-dessus de « r », pleine largeur toutes les deux (Joseph, 27/10 : même taille à toucher que le mono)
UNITS = {"m": (STRIP_Y + 140, 104, 30, 80, 56, 20, ""),
         "l": (STRIP_Y + 140, 96, 26, 72, 46, 18, "L"),
         "r": (STRIP_Y + 360, 96, 26, 72, 46, 18, "R")}


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
    """Bouton TRANSPARENT posé sur une case dessinée (48V) : reçoit le toucher, la case garde son apparence."""
    return Node("BUTTON", name, frame, {"color": CLEAR, "background": False, "outline": False}, script=script)


def strip(k):
    """Tranche k (1..16) : bandeau couleur, nom LV1, source X32, puis les voies (potard relatif, dB, 48V à confirmer)."""
    x = STRIP_X0 + STRIP_PITCH * (k - 1)
    g = "g%d_" % k
    out = [box(g + "band", (x, STRIP_Y, STRIP_W, 14), DARK),
           label(g + "name", (x, STRIP_Y + 20, STRIP_W, 60), "", 24),
           label(g + "src", (x, STRIP_Y + 80, STRIP_W, 40), "", 15, MUTED)]
    for u, (top, knob, db_size, ph_w, ph_h, ph_size, side) in UNITS.items():
        ph = (x + (STRIP_W - ph_w) // 2, top + knob + db_size + 34, ph_w, ph_h)
        path = "/xgr/g/%d/%s/" % (k, u)
        out += [Node("RADIAL", g + u + "_knob", (x + (STRIP_W - knob) // 2, top, knob, knob),
                     {"color": MUTED, "background": True, "outline": False, "interactive": True,
                      "response": 1},                     # 1 = relatif (Response.RELATIVE, reposé en Lua)
                     script=lua("knob.lua", PATH=path + "gain", GMIN=views.GAIN_MIN,
                                GSPAN=views.GAIN_MAX - views.GAIN_MIN)),
                label(g + u + "_db", (x, top + knob + 6, STRIP_W, db_size + 20), "-", db_size),
                box(g + u + "_48", ph, DARK),
                label(g + u + "_48l", ph, "48V", ph_size, MUTED),
                overlay(g + u + "_48b", ph, lua("phantom.lua", PATH=path + "48v", LABEL=g + u + "_48l"))]
        if side:                                # repère de la voie stéréo, en haut à gauche du potard
            out.append(label(g + u + "_side", (x, top - 4, 24, 28), side, 18, MUTED))
    return out


def build():
    root = Node("GROUP", "root", (0, 0, W, H), {"color": BG, "background": True},
                script=lua("root.lua", PROTO=P.PROTO, PORT_IN=P.PORT_IN, PORT_OUT=P.PORT_OUT, STRIPS=16))
    root.add(
        box("header", (0, 0, W, 110), PANEL),
        label("title", (40, 20, 520, 70), "X/M32 GAIN RECALL", 36),
        *button("follow", (1250, 25, 230, 60), "FOLLOW LV1", "/xgr/view/follow", size=26),
        *button("sync", (1640, 25, 200, 60), "SYNC", P.SYNC),
        box("led", (1890, 30, 50, 50), Color(90, 90, 90)),
        label("console", (40, 116, 560, 44), "-", 22, MUTED),
        label("g_title", (620, 116, 520, 44), "", 26, Color(56, 201, 255)),
        label("lv1", (1160, 116, 600, 44), "-", 18, MUTED),
        label("tablets", (1780, 116, 180, 44), "-", 18, MUTED),
    )
    for n, text in enumerate(BANKS):           # banques : vue de CETTE tablette (la LV1 ne bouge pas)
        root.add(*button("bank%d" % n, (580 + 130 * n, 25, 120, 60), text, "/xgr/view/bank", arg=n, size=26))
    for k in range(1, 17):
        root.add(*strip(k))
    root.add(                                   # panneau de connexion PAR-DESSUS les tranches (caché une fois connecté)
        box("panel", (100, 250, 1800, 600), PANEL),
        box("panel_line", (100, 250, 1800, 4), LINE),
        label("status", (140, 330, 1720, 120), "Looking for X/M32 Gain Recall...", 44),
        label("detail", (140, 480, 1720, 90), "", 26, MUTED),
        label("notify", (100, 1110, 1800, 46), "", 28, ORANGE),
        label("footer", (40, 1160, 1200, 36), "X/M32 Gain Recall for eMotion LV1 - protocol %d" % P.PROTO, 18, MUTED),
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
