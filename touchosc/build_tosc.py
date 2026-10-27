"""touchosc/build_tosc.py — génère le template TouchOSC de la tablette (DA LV1, paysage 2000 x 1200 : Doogee R10 de
Joseph ; TouchOSC met à l'échelle sur un autre écran).

    py -m touchosc.build_tosc [sortie.tosc]      (défaut : dist/touchosc/XM32_Gain_Recall_LV1.tosc)

Phase 0 (27/10/2026) : présence. Phase 1 : barre d'état, SYNC, messages. Phase 2a : page GAINS, 16 tranches calquées
sur la couche LV1 (lecture seule) ; le panneau de connexion ne s'affiche que tant que Gain Recall ne répond pas.
"""
import os
import sys

from . import protocol as P
from .tosc import Color, Node, write

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(ROOT, "dist", "touchosc", "XM32_Gain_Recall_LV1.tosc")
W, H = 2000, 1200

# Couleurs relevées sur la LV1 (CLAUDE.md, « Style LV1 »)
BG, PANEL, TEXT, MUTED, LINE = Color(71, 71, 71), Color(17, 17, 17), Color(231, 231, 231), Color(160, 160, 160), \
    Color(120, 120, 120)
ORANGE, DARK = Color(255, 153, 38), Color(43, 43, 43)

# Page GAINS : 16 tranches de STRIP_W, au pas STRIP_PITCH, à partir de STRIP_X0
STRIP_X0, STRIP_PITCH, STRIP_W, STRIP_Y = 40, 120, 112, 180
# voies d'une tranche : mono « m » pleine largeur, stéréo « l » / « r » demi-largeur ; (dx, largeur, potard, tailles)
UNITS = {"m": (0, STRIP_W, 104, 30, 20), "l": (0, 56, 52, 20, 14), "r": (56, 56, 52, 20, 14)}


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


def button(name, frame, text, osc):
    """Bouton au style LV1 (fond 17, liseré 160, texte 231) qui envoie `osc` à l'appui. Libellé = LABEL posé dessus,
    non interactif (le toucher passe au bouton)."""
    x, y, w, h = frame
    script = ("function onValueChanged(key)\n"
              "  if key == 'x' and self.values.x == 1 then sendOSC('%s') end\n"
              "end\n" % osc)
    return [Node("BUTTON", name, frame, {"color": MUTED, "background": False, "outline": True}, script=script),
            label(name + "_label", (x, y, w, h), text, 30)]


def strip(k):
    """Tranche k (1..16) : bandeau couleur, nom LV1, source X32, puis les voies (potard, dB, 48V). Lecture seule en 2a."""
    x = STRIP_X0 + STRIP_PITCH * (k - 1)
    g = "g%d_" % k
    out = [box(g + "band", (x, STRIP_Y, STRIP_W, 14), DARK),
           label(g + "name", (x, STRIP_Y + 20, STRIP_W, 60), "", 24),
           label(g + "src", (x, STRIP_Y + 80, STRIP_W, 40), "", 15, MUTED)]
    for u, (dx, w, knob, db_size, ph_size) in UNITS.items():
        ux = x + dx
        top = STRIP_Y + (140 if u == "m" else 150)
        out += [Node("RADIAL", g + u + "_knob", (ux + (w - knob) // 2, top, knob, knob),
                     {"color": MUTED, "background": True, "outline": False, "interactive": False}),
                label(g + u + "_db", (ux, top + knob + 6, w, db_size + 20), "-", db_size),
                box(g + u + "_48", (ux + w // 2 - (40 if u == "m" else 22), top + knob + db_size + 34,
                                    80 if u == "m" else 44, 56 if u == "m" else 44), DARK),
                label(g + u + "_48l", (ux + w // 2 - (40 if u == "m" else 22), top + knob + db_size + 34,
                                       80 if u == "m" else 44, 56 if u == "m" else 44), "48V", ph_size, MUTED)]
    return out


def build():
    root = Node("GROUP", "root", (0, 0, W, H), {"color": BG, "background": True},
                script=lua("root.lua", PROTO=P.PROTO, PORT_IN=P.PORT_IN, PORT_OUT=P.PORT_OUT, STRIPS=16))
    root.add(
        box("header", (0, 0, W, 110), PANEL),
        label("title", (40, 20, 600, 70), "X/M32 GAIN RECALL", 40),
        label("g_title", (700, 20, 600, 70), "", 40, Color(56, 201, 255)),
        *button("sync", (1640, 25, 200, 60), "SYNC", P.SYNC),
        box("led", (1890, 30, 50, 50), Color(90, 90, 90)),
        label("console", (40, 116, 700, 44), "-", 22, MUTED),
        label("lv1", (760, 116, 860, 44), "-", 22, MUTED),
        label("tablets", (1640, 116, 320, 44), "-", 22, MUTED),
    )
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
