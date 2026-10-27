"""touchosc/build_tosc.py — génère le template TouchOSC de la tablette (DA LV1, paysage 2000 x 1200 : Doogee R10 de
Joseph ; TouchOSC met à l'échelle sur un autre écran).

    py -m touchosc.build_tosc [sortie.tosc]      (défaut : dist/touchosc/XM32_Gain_Recall_LV1.tosc)

Phase 0 (27/10/2026) : une page « présence » (voyant + état de la connexion à Gain Recall).
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
                                       "interactive": False}, values={"text": text})


def box(name, frame, color, **props):
    return Node("BOX", name, frame, dict({"color": color, "background": True, "interactive": False}, **props))


def build():
    root = Node("GROUP", "root", (0, 0, W, H), {"color": BG, "background": True},
                script=lua("root.lua", PROTO=P.PROTO, PORT_IN=P.PORT_IN, PORT_OUT=P.PORT_OUT))
    root.add(
        box("header", (0, 0, W, 110), PANEL),
        label("title", (40, 20, 1000, 70), "X/M32 GAIN RECALL", 40),
        box("led", (1890, 30, 50, 50), Color(90, 90, 90)),
        box("panel", (100, 250, 1800, 600), PANEL),
        box("panel_line", (100, 250, 1800, 4), LINE),
        label("status", (140, 330, 1720, 120), "Looking for X/M32 Gain Recall...", 48),
        label("detail", (140, 480, 1720, 90), "", 28, MUTED),
        label("footer", (40, 1120, 1200, 50), "X/M32 Gain Recall for eMotion LV1 - protocol %d" % P.PROTO, 22, MUTED),
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
