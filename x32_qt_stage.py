"""Float v3 (Qt) — STAGE PATCH (3.1) : PATCH MAP + faces des boîtiers dans une seule fenêtre, au style de la LV1.

Demandes de Joseph (20/10/2026) :
  - croquis sur la face de la S16 : chaque prise branchée = pastille de la couleur choisie avec son nom (« Kick »…),
    repères « A 1 » / « A 9 » en début de rangée ;
  - regrouper PATCH MAP et faces ; remplir la PATCH MAP vite, les faces se remplissent seules : « passer du In 2 au
    In 3, renommer, choisir la couleur, passer au In 4 ainsi de suite » -> éditeur au style de la fenêtre couleur de
    la LV1 (palette 4 x 8 dans le même ordre, nom, ‹ ›) : Entrée = enregistrer + ligne suivante, ↑ / ↓ aussi ;
    toucher une couleur l'enregistre sans quitter le champ du nom ;
  - bouton sur la page Patch de la LV1 (colonne Input A / Input B, dans le cadre dessiné par Joseph) et fenêtres
    au style de la LV1 (relevé sur ses captures : panneaux (17,17,17) sur fond (71,71,71), boutons noirs à liseré
    (160,160,160), actif bleu (56,201,255), fenêtres (54,54,54) bordées de (160,160,160), textes (231,231,231)).
Ouverte depuis le bouton : posée sur la zone liste + grille du patch de la LV1, cachée hors de la page Patch.
Prise sans étiquette mais canal LV1 nommé : nom et couleur de la LV1 en plus pâle (rien d'enregistré).
Données et règles : x32_stage.py ; stockage et renommage automatique des canaux LV1 : appli principale (/api/stage).
"""
import json
import os
import re
import time

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QLinearGradient
from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea, QFrame,
                               QVBoxLayout, QHBoxLayout, QApplication)

import x32_stage as xs
import x32_gain_float as xf
from lv1.channelinfo import PALETTE
from x32_i18n import T
from x32_qt_float import AMBER, Dialog, client_rect
from x32_qt_panels import touch_scroll

TAG_BG = "#e8487a"              # repère « A 1 » (rose du croquis)
SEL = "#38c9ff"                 # prise / ligne sélectionnée (bleu actif de la LV1)
SLOT_TITLES = {"local": "PRISES DE LA CONSOLE", "A": "PORT AES50 A", "B": "PORT AES50 B"}
# Page Patch de la LV1 (relevé sur captures plein écran de Joseph, 1920x1080, 20/10/2026) : boutons Input A / Input B
# à x 18, 92x54, y 271 et 339, flèche ^ de la colonne vers y 248 ; colonne jusqu'à y 1071, flèche ⌄ vers y 1050 ->
# le nôtre EN BAS de la colonne (choix de Joseph, 2e capture), à la même distance de la flèche qu'Input A en haut.
# Zone liste + grille : x 124..1905, y 225..1070.
STAGE_BTN_BOX = (18 / 1920.0, 973 / 1080.0, 92 / 1920.0, 54 / 1080.0)
STAGE_BOX = (124 / 1920.0, 225 / 1080.0, 1781 / 1920.0, 845 / 1080.0)
LEFT_W = 640                    # colonne PATCH MAP + éditeur

LV1_CSS = """
QWidget#stage { background: rgb(71,71,71); }
QFrame#panel { background: rgb(17,17,17); border-radius: 6px; }
QFrame#editor { background: rgb(54,54,54); border: 2px solid rgb(160,160,160); border-radius: 8px; }
QLabel { color: rgb(231,231,231); font: bold 10pt "Segoe UI"; background: transparent; }
QLabel[mut="1"] { color: rgb(160,160,160); font: 9pt "Segoe UI"; }
QLabel#title { font: bold 15pt "Segoe UI"; }
QLabel#head { color: rgb(160,160,160); font: bold 9pt "Segoe UI"; }
QLabel#port { font: bold 14pt "Segoe UI"; }
QPushButton { background: rgb(17,17,17); color: rgb(231,231,231); border: 1px solid rgb(160,160,160);
              border-radius: 6px; padding: 6px 14px; font: bold 11pt "Segoe UI"; min-height: 26px; }
QPushButton:pressed, QPushButton[on="1"] { background: rgb(56,201,255); color: rgb(17,17,17); border: 0; }
QPushButton#arrow { background: rgb(43,43,43); min-width: 30px; padding: 4px 10px; font: bold 15pt "Segoe UI"; }
QPushButton#arrow:pressed { background: rgb(56,201,255); }
QPushButton#danger { color: rgb(255,107,93); border-color: rgb(255,107,93); }
QPushButton#close { font: bold 14pt "Segoe UI"; padding: 2px 12px; }
QLineEdit { background: rgb(17,17,17); color: rgb(231,231,231); border: 1px solid rgb(160,160,160);
            border-radius: 6px; padding: 5px 10px; font: bold 12pt "Segoe UI";
            selection-background-color: rgb(56,201,255); selection-color: rgb(17,17,17); }
QComboBox { background: rgb(17,17,17); color: rgb(231,231,231); border: 1px solid rgb(160,160,160);
            border-radius: 6px; padding: 5px 10px; font: bold 11pt "Segoe UI"; min-height: 26px; }
QComboBox QAbstractItemView { background: rgb(54,54,54); color: rgb(231,231,231); font: bold 12pt "Segoe UI";
                              selection-background-color: rgb(56,201,255); selection-color: rgb(17,17,17); }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
QScrollBar:vertical { background: rgb(71,71,71); width: 16px; margin: 2px; border-radius: 7px; }
QScrollBar::handle:vertical { background: rgb(200,200,200); border-radius: 6px; min-height: 40px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def text_on(hex_color):
    c = QColor(hex_color)
    return "#111111" if (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) > 140 else "#ffffff"


def lv1_button(text, cb=None, name=None):
    b = QPushButton(text)
    b.setFocusPolicy(Qt.NoFocus)
    if name:
        b.setObjectName(name)
    if cb:
        b.clicked.connect(lambda _checked=False, cb=cb: cb())     # clicked envoie un booléen : on l'ignore
    return b


def set_on(b, on):
    b.setProperty("on", "1" if on else "0")
    b.style().unpolish(b)
    b.style().polish(b)


def mut_label(text):
    lb = QLabel(text)
    lb.setProperty("mut", "1")
    lb.setWordWrap(True)
    return lb


# --------------------------------------------------------------------------
#  Bouton de la page Patch de la LV1
# --------------------------------------------------------------------------
class StageButton(QWidget):
    """Page Patch de la LV1 : bouton « Stage Patch » en bas de la colonne Input A / Input B, à leur style (92x54 en
    1920x1080, fond (17,17,17), contour (160,160,160), texte (231,231,231) gras ; actif = fond bleu (56,201,255))."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.down = False

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        k = w / 92.0
        sw = self.app.stage_win
        on = (sw is not None and sw.is_open and sw.isVisible()) or self.down
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(Qt.NoPen if on else QPen(QColor(160, 160, 160), 1))
        p.setBrush(QColor(56, 201, 255) if on else QColor(17, 17, 17))
        p.drawRoundedRect(r, 6 * k, 6 * k)
        p.setPen(QColor(17, 17, 17) if on else QColor(231, 231, 231))
        p.setFont(QFont("Segoe UI", max(7, round(11 * k)), QFont.Bold))
        p.drawText(r, Qt.AlignCenter, T("Stage\nPatch"))
        p.end()

    def mousePressEvent(self, _e):
        self.down = True
        self.update()

    def mouseReleaseEvent(self, e):
        self.down = False
        if self.rect().contains(e.position().toPoint()):
            self.app.toggle_stage(docked=True)
        self.update()


# --------------------------------------------------------------------------
#  Une face d'appareil
# --------------------------------------------------------------------------
class FaceView(QWidget):
    """Face dessinée d'un appareil posé sur un emplacement (local / A / B) d'une console."""

    def __init__(self, win, console, slot, device):
        super().__init__()
        self.win, self.console, self.slot, self.dev_key = win, console, slot, device
        self.dev = xs.DEVICES[device]
        self.setMinimumHeight(60)
        self._hit = []                     # [(clé, centre, rayon)]

    def key_of(self, io, n):
        return xs.port_key(self.slot, io, n)

    def _radius(self, W):
        socks = self.dev["sockets"]
        best = 1.0
        for i, (_io, _n, x, y) in enumerate(socks):
            for _io2, _n2, x2, y2 in socks[i + 1:]:
                if abs(y - y2) < 0.01:
                    best = min(best, abs(x - x2))
        return max(9.0, min(best * W * 0.40, self.height() * 0.13))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        body = QRectF(2, 2, W - 4, H - 4)
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, QColor("#3b3e42"))
        g.setColorAt(1, QColor("#26282b"))
        p.setPen(QPen(QColor("#5a5e63"), 1.5))
        p.setBrush(g)
        p.drawRoundedRect(body, 8, 8)
        if self.dev_key in ("s16", "x32r", "m32c"):           # oreilles de rack
            for x in (6, W - 22):
                p.setBrush(QColor("#1c1d1f"))
                p.setPen(QPen(QColor("#4a4d51"), 1))
                p.drawRoundedRect(QRectF(x, H * 0.12, 16, H * 0.76), 4, 4)
        f = QFont("Segoe UI")
        for _kind, x0, y0, x1, y1, txt in self.dev["deco"]:
            r = QRectF(x0 * W, y0 * H, (x1 - x0) * W, (y1 - y0) * H)
            p.setPen(QPen(QColor("#4a4d51"), 1))
            p.setBrush(QColor("#1d1f22"))
            p.drawRoundedRect(r, 6, 6)
            if txt:
                big = txt == self.dev["name"]
                f.setPixelSize(int(H * (0.16 if big else 0.055)))
                f.setBold(big)
                p.setFont(f)
                p.setPen(QColor("#d8dadc" if big else "#7d8288"))
                p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, txt)
        f.setPixelSize(max(10, int(H * 0.06)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#9aa0a6"))
        p.drawText(QRectF(30, 4, W * 0.5, H * 0.1), Qt.AlignLeft | Qt.AlignVCenter,
                   "%s — %s" % (self.dev["name"], T("face " + self.dev["view"])))
        r = self._radius(W)
        self._hit = []
        ports = self.win.ports(self.console)
        for io, n, x, y in self.dev["sockets"]:
            self._socket(p, io, n, QPointF(x * W, y * H), r, ports.get(self.key_of(io, n)))
        for n, x, y in self.dev["tags"]:                     # repères de rangée « A 1 », « A 9 »
            txt = "%s %d" % (xs.SLOT_TAG[self.slot], n)
            f.setPixelSize(max(9, int(r * 0.62)))
            f.setBold(True)
            p.setFont(f)
            tw = QFontMetrics(f).horizontalAdvance(txt) + 10
            rr = QRectF(x * W - tw / 2, y * H, tw, r * 0.95)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(TAG_BG))
            p.drawRoundedRect(rr, 3, 3)
            p.setPen(QColor("#ffffff"))
            p.drawText(rr, Qt.AlignCenter, txt)
        p.end()

    def _socket(self, p, io, n, c, r, lab):
        key = self.key_of(io, n)
        self._hit.append((key, c, r))
        f = QFont("Segoe UI")
        f.setPixelSize(max(8, int(r * 0.48)))                # « IN 1 » au-dessus
        f.setBold(True)
        p.setFont(f)
        txt = ("IN %d" if io == "in" else "OUT %d") % n
        tw = QFontMetrics(f).horizontalAdvance(txt) + 8
        pill = QRectF(c.x() - tw / 2, c.y() - r * 1.95, tw, r * 0.62)
        p.setPen(QPen(QColor("#c9ccd0"), 1))
        p.setBrush(QColor("#2b2d30"))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        p.setPen(QColor("#e4e6e8"))
        p.drawText(pill, Qt.AlignCenter, txt)
        chain = self.win.chain(self.console, key) if io == "in" else None
        auto = None
        if not (lab and (lab.get("name") or lab.get("color") is not None)) and chain:
            auto = self.win.auto_label(chain)                # nom / couleur du canal LV1, en plus pâle
        if lab and (lab.get("name") or lab.get("color") is not None) or auto:
            if auto:
                name, col = auto
            else:
                name, col = lab.get("name") or "", (PALETTE[lab["color"]] if lab.get("color") is not None
                                                   else "#cfd3d6")
            rr = r * 1.18
            p.setOpacity(0.55 if auto else 1.0)
            p.setPen(QPen(QColor("#111"), 1.5))
            p.setBrush(QColor(col))
            p.drawEllipse(c, rr, rr)
            size = int(rr * 0.62)
            while size > 7:
                f.setPixelSize(size)
                if QFontMetrics(f).horizontalAdvance(name) <= rr * 1.9:
                    break
                size -= 1
            p.setFont(f)
            p.setPen(QColor(text_on(col)))
            p.drawText(QRectF(c.x() - rr * 1.2, c.y() - rr, rr * 2.4, rr * 2), Qt.AlignCenter, name)
            p.setOpacity(1.0)
            if not auto and self.win.color_differs(lab, chain):
                # la LV1 V17 ne laisse pas changer la couleur à distance : repère orange = à régler à la main
                p.setPen(QPen(QColor("#111"), 1))
                p.setBrush(QColor(AMBER))
                pc = QPointF(c.x() - rr * 0.85, c.y() - rr * 0.85)
                p.drawEllipse(pc, r * 0.32, r * 0.32)
                f.setPixelSize(max(8, int(r * 0.48)))
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#111"))
                p.drawText(QRectF(pc.x() - r * 0.32, pc.y() - r * 0.32, r * 0.64, r * 0.64), Qt.AlignCenter, "!")
        else:
            p.setPen(QPen(QColor("#8d9196"), 1.5))           # XLR : collerette, trou, 3 broches
            p.setBrush(QColor("#151617"))
            p.drawEllipse(c, r, r)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2e3033"))
            p.drawEllipse(c, r * 0.72, r * 0.72)
            p.setBrush(QColor("#0b0b0c" if io == "in" else "#b9a66a"))
            for dx, dy in ((-0.32, -0.18), (0.32, -0.18), (0, 0.34)):
                p.drawEllipse(QPointF(c.x() + dx * r, c.y() + dy * r), r * 0.11, r * 0.11)
        if self.win.sel == (self.console, key):
            p.setPen(QPen(QColor(SEL), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, r * 1.32, r * 1.32)
        if chain and chain["exp"] is not None:               # sous la prise : EXP + liseré du canal LV1
            f.setPixelSize(max(8, int(r * 0.45)))
            f.setBold(False)
            p.setFont(f)
            lv1 = chain["lv1"]
            box = QRectF(c.x() - r * 1.6, c.y() + r * 1.3, r * 3.2, r * 0.6)
            p.setPen(QColor("#aeb3b8"))
            p.drawText(box, Qt.AlignCenter, "EXP " + xf.exp_txt(chain["exp"]))
            if lv1 and lv1[0][3]:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(lv1[0][3]))
                p.drawRoundedRect(QRectF(c.x() - r * 0.7, c.y() + r * 1.95, r * 1.4, r * 0.18), 2, 2)
        if io == "in" and self.win.phantom_on(self.console, key):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ff3b30"))
            p.drawEllipse(QPointF(c.x() + r * 0.95, c.y() - r * 0.95), r * 0.2, r * 0.2)

    def mouseReleaseEvent(self, e):
        pos = e.position()
        best = None
        for key, c, r in self._hit:
            d = ((pos.x() - c.x()) ** 2 + (pos.y() - c.y()) ** 2) ** 0.5
            if d <= r * 1.5 and (best is None or d < best[0]):
                best = (d, key)
        if best:
            self.win.select((self.console, best[1]))


# --------------------------------------------------------------------------
#  PATCH MAP : une ligne par EXP
# --------------------------------------------------------------------------
LIST_COLS = (("EXP", 62), ("SOURCE X32", 116), ("NOM", 180), ("CANAL LV1", 0))
ROW_H = 30


class PatchHeader(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(24)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(160, 160, 160))
        x = 8
        for text, w in LIST_COLS:
            p.drawText(QRectF(x, 0, w or 300, self.height()), Qt.AlignVCenter | Qt.AlignLeft, T(text))
            x += w
        p.end()


class PatchList(QWidget):
    """Lignes dessinées (rapide à redessiner pendant la saisie) : EXP, source X32, nom de la prise (étiquette, ou nom
    du canal LV1 en pâle), canal(aux) LV1. Toucher une ligne = la choisir dans l'éditeur."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.rows = []

    def set_rows(self, rows):
        self.rows = rows
        h = max(ROW_H, len(rows) * ROW_H)
        if self.height() != h:
            self.setFixedHeight(h)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W = self.width()
        f = QFont("Segoe UI", 10, QFont.Bold)
        fn = QFont("Segoe UI", 10)
        fi = QFont("Segoe UI", 10)
        fi.setItalic(True)
        y0 = max(0, e.rect().top() // ROW_H)
        y1 = min(len(self.rows), e.rect().bottom() // ROW_H + 1)
        for i in range(y0, y1):
            row = self.rows[i]
            y = i * ROW_H
            on = row["ck"] is not None and row["ck"] == self.win.sel
            p.fillRect(QRectF(0, y, W, ROW_H - 1), QColor(56, 201, 255) if on else QColor(71, 71, 71))
            p.fillRect(QRectF(0, y + ROW_H - 1, W, 1), QColor(17, 17, 17))
            txt = QColor(17, 17, 17) if on else QColor(231, 231, 231)
            mut = QColor(40, 60, 70) if on else QColor(150, 150, 150)
            x = 8
            cells = [("EXP " + row["exp_txt"], txt, f), (row["src_long"] or "—", txt if row["src_long"] else mut, fn)]
            for (text, col, font), (_h, w) in zip(cells, LIST_COLS):
                p.setFont(font)
                p.setPen(col)
                p.drawText(QRectF(x, y, w - 6, ROW_H), Qt.AlignVCenter | Qt.AlignLeft, text)
                x += w
            # nom de la prise
            lab, auto = row["label"], row["auto"]
            name, colr, font, pen = None, None, f, txt
            if lab and (lab.get("name") or lab.get("color") is not None):
                name = lab.get("name") or ""
                colr = PALETTE[lab["color"]] if lab.get("color") is not None else None
            elif auto:
                name, colr, font, pen = auto[0], auto[1], fi, mut
            if colr:
                p.setPen(QPen(QColor(17, 17, 17), 1))
                p.setBrush(QColor(colr))
                p.setOpacity(1.0 if font is f else 0.5)
                p.drawRoundedRect(QRectF(x, y + 8, 14, 14), 3, 3)
                p.setOpacity(1.0)
            p.setFont(font)
            p.setPen(pen)
            p.drawText(QRectF(x + 20, y, LIST_COLS[2][1] - 24, ROW_H), Qt.AlignVCenter | Qt.AlignLeft,
                       name if name is not None else "")
            x += LIST_COLS[2][1]
            # canal(aux) LV1
            lv1 = row["lv1"]
            if lv1:
                col = next((c for _ch, _s, _l, c in lv1 if c), None)
                if col:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(col))
                    p.drawRoundedRect(QRectF(x, y + 9, 12, 12), 2, 2)
                p.setFont(f)
                p.setPen(txt)
                p.drawText(QRectF(x + 18, y, W - x - 22, ROW_H), Qt.AlignVCenter | Qt.AlignLeft,
                           ", ".join(l + (" " + s if s else "") for _c, s, l, _col in lv1))
            else:
                p.setFont(fi)
                p.setPen(mut)
                p.drawText(QRectF(x, y, W - x - 4, ROW_H), Qt.AlignVCenter | Qt.AlignLeft, T("non patché"))
        p.end()

    def mouseReleaseEvent(self, e):
        i = int(e.position().y() // ROW_H)
        if 0 <= i < len(self.rows) and self.rows[i]["ck"] is not None:
            self.win.select(self.rows[i]["ck"])


# --------------------------------------------------------------------------
#  Éditeur : palette 4 x 8 de la LV1, nom, ‹ ›
# --------------------------------------------------------------------------
class PaletteGrid(QWidget):
    """Les 32 couleurs dans l'ordre et la disposition de la fenêtre « Select a Color » de la LV1 (4 colonnes x 8
    rangées, n° 0 en haut à gauche) ; couleur choisie entourée de blanc, comme dans la LV1."""
    CW, CH, GAP = 52, 21, 3

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.current = None
        self.setFixedSize(4 * self.CW + 5 * self.GAP, 8 * self.CH + 9 * self.GAP)

    def cell(self, i):
        return QRectF(self.GAP + (i % 4) * (self.CW + self.GAP), self.GAP + (i // 4) * (self.CH + self.GAP),
                      self.CW, self.CH)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(17, 17, 17))
        for i, col in enumerate(PALETTE):
            p.fillRect(self.cell(i), QColor(col))
        if self.current is not None:
            p.setPen(QPen(QColor(255, 255, 255), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.cell(self.current).adjusted(1, 1, -1, -1))
        p.end()

    def mouseReleaseEvent(self, e):
        for i in range(32):
            if self.cell(i).adjusted(-1, -1, 1, 1).contains(e.position()):
                self.win.pick_color(i)
                return


# --------------------------------------------------------------------------
#  Couleurs -> LV1 : clics dans la fenêtre « Select a Color » (lv1/colorclick.py)
# --------------------------------------------------------------------------
def is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class ColorRunner:
    """Fil de fond qui applique les couleurs (lv1.colorclick.ColorJob) ; fournit au job la lecture d'écran, les clics
    postés à la LV1 et les changements vus (OSC /Notify/TrackColor d'une connexion à la LV1, sinon base de la LV1)."""

    def __init__(self, win, targets):
        self.win, self.app = win, win.app
        self.targets = targets
        self.hwnd = self.app.stage_lv1()
        self.rect = client_rect(self.hwnd) if self.hwnd else None
        self.remote = None
        self.job = None
        self.stop_flag = False
        self.result = None                   # (faits, erreur) à la fin
        self.lines = []

    def colors_now(self):
        out = {}
        for ch, v in (self.app.lv1_channels or {}).items():
            idx = xs.palette_index(v.get("color")) if v.get("color") else None
            if idx is not None:
                out[int(ch)] = idx
        return out

    def start(self):
        import threading
        threading.Thread(target=self._run, daemon=True, name="lv1-colors").start()

    def _run(self):
        from lv1 import colorclick
        try:
            try:
                from lv1.remote import LV1Remote
                self.remote = LV1Remote(device_name="X32 Gain Recall (couleurs)", log=lambda m: None)
                self.remote.connect_once(timeout=4.0)
                import threading
                threading.Thread(target=self.remote.run_forever, daemon=True).start()
                time.sleep(1.2)                 # couleurs envoyées à la connexion : passées, pas des changements
            except OSError:
                self.remote = None              # vérification par la base de la LV1 seulement
            self.job = colorclick.ColorJob(self.targets, self.colors_now(), self)
            self.result = self.job.run()
            if self.result[1]:
                print("Couleurs LV1 : arrêt : %s" % self.result[1])
        except Exception as e:                  # jamais de fil mort en silence
            self.result = (self.job.done if self.job else [], str(e))
        finally:
            if self.remote:
                self.remote.stop()

    # -- io pour ColorJob ---------------------------------------------------------
    def _pt(self, p):
        x, y, w, h = self.rect
        return x + round(w * p[0] / 1920.0), y + round(h * p[1] / 1080.0)

    def read(self, points):
        pts = [self._pt(p) for p in points]
        x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
        x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        b = xf.screen_bytes(x0, y0, w, h)
        if not b:
            return [None] * len(points)
        out = []
        for sx, sy in pts:
            o = 4 * ((sy - y0) * w + (sx - x0))
            out.append((b[o + 2], b[o + 1], b[o]))
        return out

    def click(self, p):
        from lv1 import colorclick
        if not colorclick.post_click(self.hwnd, *self._pt(p)):
            raise colorclick.JobError("clic refusé : LV1 introuvable sous le point (masquée ?) ou appli pas en "
                                      "administrateur")

    def changes(self, since):
        ev = [(c, i, t) for c, i, t in (self.remote.color_events if self.remote else []) if t >= since]
        known = self.job.colors if self.job else {}
        now = time.time()
        for ch, idx in self.colors_now().items():       # base de la LV1 (~1 s plus tard) : seulement l'inattendu
            if idx != known.get(ch, 13) and not any(c == ch for c, _i, _t in ev):
                ev.append((ch, idx, now))
        return ev

    def stopped(self):
        return self.stop_flag

    def log(self, text):
        self.lines.append(text)
        print("Couleurs LV1 : %s" % text)


# --------------------------------------------------------------------------
#  La fenêtre
# --------------------------------------------------------------------------
class StagePatch(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.app = app
        self.state = None
        self.console = 0
        self.sel = None                   # (console, clé de prise) dans l'éditeur
        self.is_open = False
        self.docked = False               # ouverte par le bouton de la page Patch : cachée hors de cette page
        self.runner = None                # couleurs en cours d'envoi à la LV1 (fenêtre cachée pendant ce temps)
        self.rows = []
        self.setObjectName("stage")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(LV1_CSS)
        self.setWindowTitle(T("Stage patch — %s") % "X/M32 Gain Recall")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        # barre du haut : titre, feuilles, renommage auto, croix
        top = QFrame()
        top.setObjectName("panel")
        tb = QHBoxLayout(top)
        tb.setContentsMargins(14, 8, 8, 8)
        t = QLabel(T("STAGE PATCH"))
        t.setObjectName("title")
        tb.addWidget(t)
        tb.addSpacing(18)
        h = QLabel(T("Feuille"))
        h.setObjectName("head")
        tb.addWidget(h)
        self.sheets = QComboBox()
        self.sheets.setMinimumWidth(240)
        self.sheets.setFocusPolicy(Qt.NoFocus)
        self.sheets.activated.connect(self._pick_sheet)
        tb.addWidget(self.sheets)
        for text, act in ((T("Nouvelle"), "new"), (T("Dupliquer"), "duplicate"), (T("Renommer"), "rename"),
                          (T("Supprimer"), "delete")):
            tb.addWidget(lv1_button(text, lambda a=act: self.sheet_action(a), "danger" if act == "delete" else None))
        tb.addSpacing(10)
        tb.addWidget(lv1_button(T("Exporter…"), self.export_sheet))
        tb.addWidget(lv1_button(T("Importer…"), self.import_sheet))
        tb.addStretch(1)
        self.color_btn = lv1_button(T("Couleurs → LV1"), self.apply_colors)
        tb.addWidget(self.color_btn)
        self.auto_btn = lv1_button(T("Renommer les canaux LV1"), self._toggle_auto)
        tb.addWidget(self.auto_btn)
        tb.addSpacing(10)
        tb.addWidget(lv1_button("✕", self.close_win, "close"))
        outer.addWidget(top)
        body = QHBoxLayout()
        body.setSpacing(8)
        outer.addLayout(body, 1)
        # gauche : éditeur + PATCH MAP
        left = QFrame()
        left.setObjectName("panel")
        left.setFixedWidth(LEFT_W)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 10, 10, 10)
        lv.setSpacing(8)
        lv.addWidget(self._build_editor())
        self.find = QLineEdit()
        self.find.setPlaceholderText(T("Rechercher : canal, EXP, source (A1, L3…)"))
        self.find.setStyleSheet("font: 10pt 'Segoe UI';")
        self.find.textChanged.connect(lambda _t: self.refresh())
        lv.addWidget(self.find)
        lv.addWidget(PatchHeader())
        self.list = PatchList(self)
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidget(self.list)
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        touch_scroll(self.list_scroll)
        lv.addWidget(self.list_scroll, 1)
        body.addWidget(left)
        # droite : faces
        right = QFrame()
        right.setObjectName("panel")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 10, 10, 10)
        rv.setSpacing(6)
        self.cons_bar = QHBoxLayout()
        rv.addLayout(self.cons_bar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        touch_scroll(self.scroll)
        rv.addWidget(self.scroll, 1)
        self.info = mut_label("")
        rv.addWidget(self.info)
        body.addWidget(right, 1)
        self.faces = []
        self._built = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._ticks = 0
        self.resize(1781, 845)

    def _build_editor(self):
        ed = QFrame()
        ed.setObjectName("editor")
        h = QHBoxLayout(ed)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(14)
        self.palette = PaletteGrid(self)
        h.addWidget(self.palette)
        v = QVBoxLayout()
        v.setSpacing(6)
        self.port_lbl = QLabel("")
        self.port_lbl.setObjectName("port")
        v.addWidget(self.port_lbl)
        self.chain_lbl = mut_label("")
        v.addWidget(self.chain_lbl)
        v.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(lv1_button("‹", lambda: self.step(-1), "arrow"))
        self.name = QLineEdit()
        self.name.setMaxLength(24)
        self.name.returnPressed.connect(lambda: self.step(1))
        self.name.installEventFilter(self)
        row.addWidget(self.name, 1)
        row.addWidget(lv1_button("›", lambda: self.step(1), "arrow"))
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(lv1_button(T("Sans couleur"), lambda: self.pick_color(None)))
        row2.addStretch(1)
        row2.addWidget(lv1_button(T("Effacer"), self.clear_port, "danger"))
        v.addLayout(row2)
        v.addWidget(mut_label(T("Entrée ou › : enregistrer et passer à la suivante. ↑ ↓ aussi. Toucher une couleur "
                                "l'enregistre.")))
        h.addLayout(v, 1)
        return ed

    def eventFilter(self, obj, e):
        if obj is self.name and e.type() == QEvent.KeyPress:
            if e.key() == Qt.Key_Down:
                self.step(1)
                return True
            if e.key() == Qt.Key_Up:
                self.step(-1)
                return True
        return False

    # -- ouverture, placement --------------------------------------------------
    def open(self, docked):
        self.is_open = True
        self.docked = docked
        self.reload()
        if self.sel is None:
            first = next((r["ck"] for r in self.rows if r["ck"] is not None), None)
            if first:
                self.select(first, focus=False)
        self.timer.start(1000)
        self.sync(self.app.stage_lv1(), True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.name.setFocus()
        self.app.raise_now(self)

    def close_win(self):
        self.commit()
        self.is_open = False
        self.timer.stop()
        self.hide()
        if self.app.stage_btn:
            self.app.stage_btn.update()

    def sync(self, lv1, on_patch):
        """Appelé par le float à chaque tour : posée sur la zone du patch de la LV1 ; ouverte par le bouton de la page
        Patch : cachée quand la LV1 affiche une autre page."""
        if not self.is_open:
            return
        rect = client_rect(lv1) if lv1 else None
        if rect and rect[2] >= 800:
            x, y, w, h = rect
            geom = (x + round(w * STAGE_BOX[0]), y + round(h * STAGE_BOX[1]), round(w * STAGE_BOX[2]),
                    round(h * STAGE_BOX[3]))
        else:
            scr = QApplication.primaryScreen().availableGeometry()
            w, h = min(1781, scr.width() - 40), min(845, scr.height() - 40)
            geom = (scr.x() + (scr.width() - w) // 2, scr.y() + (scr.height() - h) // 2, w, h)
        if (self.x(), self.y(), self.width(), self.height()) != geom:
            self.setGeometry(*geom)
            QTimer.singleShot(0, self._size_faces)
        show = (on_patch or not self.docked or not lv1) and self.runner is None
        if show and not self.isVisible():
            self.show()
            self.app.raise_now(self)
        elif not show and self.isVisible():
            self.commit()
            self.hide()

    # -- données -----------------------------------------------------------
    def reload(self, st=None):
        st = st or self.app.backend.stage()
        if not st:
            self.info.setText(T("Patch de scène indisponible (appli principale injoignable)."))
            return
        self.state = st
        key = (st["active"], self.console, tuple(sorted(self.devices(self.console).items(), key=str)),
               len(self.app._consoles or []))
        if key != self._built:
            self._built = key
            self.rebuild()
        self.refresh()

    def ports(self, console):
        c = ((self.state or {}).get("sheet") or {}).get("consoles", {}).get(str(console)) or {}
        return c.get("ports") or {}

    def devices(self, console):
        c = ((self.state or {}).get("sheet") or {}).get("consoles", {}).get(str(console)) or {}
        return c.get("devices") or xs.default_devices(None)

    def label(self, ck):
        return self.ports(ck[0]).get(ck[1]) if ck else None

    def chain(self, console, key):
        app = self.app
        return xs.port_chain(key, console, app.exp_map, app.lv1_sources, app.lv1_channels)

    def auto_label(self, chain):
        """(nom, couleur) du canal LV1 qu'alimente une prise sans étiquette, s'il a été renommé ; None sinon."""
        for ch, _side, lab, col in (chain or {}).get("lv1") or []:
            if lab and lab != "In %d" % ch:
                return lab, col or "#cfd3d6"
        return None

    def color_differs(self, lab, chain):
        """La prise a une couleur et un canal LV1 qu'elle alimente n'a pas cette couleur (à régler dans la LV1)."""
        if not lab or lab.get("color") is None or not chain or not chain["lv1"]:
            return False
        want = PALETTE[lab["color"]].upper()
        return any(col and col.upper() != want for _ch, _s, _l, col in chain["lv1"])

    def phantom_on(self, console, key):
        idx = xs.port_preamp(key, console)
        ph = (self.app.link.snap or {}).get("phantom") or []
        return idx is not None and idx < len(ph) and bool(ph[idx])

    def notify(self, title, text, ok=True, ms=7000):
        """Notification en bas à droite, rien à cliquer (Joseph : jamais de message bloquant caché derrière)."""
        self.app.toast.say(title, text, ok=ok, ms=ms)
        self.app.raise_now(self.app.toast)

    def _post(self, what, d):
        r = self.app.backend.stage_post(what, d)
        if not r.get("ok"):
            self.notify(T("Patch de scène"), r.get("error") or T("Échec"), ok=False)
            return False
        self.reload(r)
        return True

    def _rows(self):
        """Lignes de la PATCH MAP (x32_gain_float.patch_map_rows) + prise, étiquette et nom LV1 de chacune."""
        app = self.app
        rows = xf.patch_map_rows(app.exp_map, app.lv1_sources, app.lv1_channels, (app.link.snap or {}).get("names"))
        q = self.find.text().strip().lower().replace(" ", "")
        out = []
        for row in rows:
            ck = xs.preamp_port(row["src"]) if row["src"] is not None else None
            lab = self.label(ck)
            auto = self.auto_label({"lv1": row["lv1"]})
            if q:
                text = " ".join(["exp%s" % row["exp_txt"], row["src_long"] or "", row["src_short"] or "",
                                 (lab or {}).get("name") or "", auto[0] if auto else ""]
                                + [l for _c, _s, l, _col in row["lv1"]]).lower().replace(" ", "")
                if q not in text:
                    continue
            out.append(dict(row, ck=ck, label=lab, auto=auto))
        return out

    # -- construction ------------------------------------------------------
    def rebuild(self):
        st = self.state
        self.sheets.blockSignals(True)
        self.sheets.clear()
        for s in st["sheets"]:
            self.sheets.addItem("%s  (%d)" % (s["name"], s["ports"]), s["id"])
            if s["id"] == st["active"]:
                self.sheets.setCurrentIndex(self.sheets.count() - 1)
        self.sheets.blockSignals(False)
        while self.cons_bar.count():
            w = self.cons_bar.takeAt(0).widget()
            if w:
                w.deleteLater()
        cs = list(self.app._consoles or [])
        if len(cs) > 1:
            for c in cs:
                b = lv1_button(T("Console %d — %s") % (c["n"] + 1, c.get("name") or c.get("ip") or "?"),
                               lambda n=c["n"]: self._pick_console(n))
                set_on(b, c["n"] == self.console)
                self.cons_bar.addWidget(b)
            self.cons_bar.addStretch(1)
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 8, 0)
        cv.setSpacing(6)
        self.faces = []
        devs = self.devices(self.console)
        for slot in xs.SLOTS:
            head = QHBoxLayout()
            t = QLabel(T(SLOT_TITLES[slot]))
            t.setObjectName("head")
            head.addWidget(t)
            cb = QComboBox()
            cb.setFocusPolicy(Qt.NoFocus)
            cb.addItem(T("— rien —"), None)
            for key in xs.DEVICE_ORDER:
                if slot in xs.DEVICES[key]["slots"]:
                    cb.addItem(xs.DEVICES[key]["name"], key)
            cb.setCurrentIndex(max(0, cb.findData(devs.get(slot))))
            cb.activated.connect(lambda _i, cb=cb, slot=slot: self._post(
                "device", {"console": self.console, "slot": slot, "device": cb.currentData()}))
            head.addWidget(cb)
            head.addStretch(1)
            cv.addLayout(head)
            dev = devs.get(slot)
            if dev in xs.DEVICES:
                fv = FaceView(self, self.console, slot, dev)
                cv.addWidget(fv)
                self.faces.append(fv)
        cv.addStretch(1)
        self.scroll.setWidget(content)
        self._size_faces()
        QTimer.singleShot(0, self._size_faces)          # largeur définitive une fois la page posée

    def _size_faces(self):
        """Hauteur de chaque face = largeur disponible / proportions de la vraie face ; puis mise en page refaite
        (sinon, après une reconstruction sans changement de taille de la fenêtre — import d'une feuille —, les faces se
        chevauchaient)."""
        w = self.scroll.viewport().width() - 10
        for fv in self.faces:
            fv.setFixedHeight(max(60, int(w / fv.dev["ratio"])))
        content = self.scroll.widget()
        if content is not None and content.layout() is not None:
            content.layout().invalidate()
            content.layout().activate()
            content.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._size_faces)

    def refresh(self):
        """Redessine sans reconstruire (pendant la saisie) : lignes, faces, éditeur, barre d'état."""
        if not self.state:
            return
        self.rows = self._rows()
        self.list.set_rows(self.rows)
        for fv in self.faces:
            fv.update()
        set_on(self.auto_btn, bool(self.state.get("auto")))
        n = len(self.color_targets())
        self.color_btn.setText(T("Couleurs → LV1") + ("  (%d)" % n if n else ""))
        self._load_editor(keep_text=True)
        rem = self.state.get("lv1_remote") or {}
        if not self.state.get("auto"):
            txt = T("Renommage automatique désactivé.")
        elif rem.get("connected"):
            txt = T("LV1 reliée (OSC %s:%s) : les canaux LV1 prennent le nom de la prise qui les alimente.") % (
                rem.get("host"), rem.get("port"))
        elif rem:
            txt = T("LV1 pas encore reliée (%s).") % (rem.get("error") or "…")
        else:
            txt = T("Les canaux LV1 prendront le nom de la prise qui les alimente.")
        txt += "  " + T("● orange : couleur LV1 différente, à régler à la main.")
        log = self.state.get("log") or []
        if log:
            txt += "  " + T("Dernier : In %d → « %s ».") % (log[-1]["ch"], log[-1]["name"])
        self.info.setText(txt)

    def _tick(self):
        if not self.isVisible():
            return
        self._ticks += 1
        if self._ticks % 3 == 0:                 # état du serveur (renommages, liaison LV1) toutes les 3 s
            st = self.app.backend.stage()
            if st:
                self.state = st
        self.refresh()

    # -- éditeur -------------------------------------------------------------
    def _port_title(self, ck):
        c, key = ck
        slot, io, n = xs.parse_key(key)
        dev = xs.DEVICES.get(self.devices(c).get(slot) or "", {}).get("name") or SLOT_TITLES[slot].title()
        return "%s  ·  %s %s %d" % (xs.port_tag(key, c), dev, "IN" if io == "in" else "OUT", n)

    def _load_editor(self, keep_text=False):
        ck = self.sel
        if not ck:
            self.port_lbl.setText(T("Choisissez une ligne ou une prise"))
            self.chain_lbl.setText("")
            self.palette.current = None
            self.palette.update()
            return
        lab = self.label(ck) or {}
        c, key = ck
        _slot, io, _n = xs.parse_key(key)
        self.port_lbl.setText(self._port_title(ck))
        auto = None
        if io == "in":
            ch = self.chain(c, key)
            auto = self.auto_label(ch)
            if ch["exp"] is None:
                txt = T("Cette entrée n'arrive sur aucun EXP (routing de la console).")
            else:
                lv1 = ", ".join(l + (" " + s if s else "") for _c, s, l, _col in ch["lv1"])
                txt = "→ EXP %s → %s" % (xf.exp_txt(ch["exp"]), ("LV1 " + lv1) if lv1 else T("aucun canal LV1"))
                if self.color_differs(lab, ch):
                    txt += "\n" + T("Couleur différente dans la LV1 : à régler à la main (la LV1 ne "
                                    "laisse pas changer la couleur à distance).")
        else:
            txt = T("Sortie : le nom sert de repère sur la face (pas envoyé à la LV1).")
        self.chain_lbl.setText(txt)
        if not keep_text:
            self.name.setText(lab.get("name") or "")
            self.name.selectAll()
        self.name.setPlaceholderText(auto[0] if auto else T("Nom (Kick, Snare, OV L…)"))
        col = lab.get("color")
        self.palette.current = col
        self.palette.update()
        if col is not None:                     # champ du nom à la couleur choisie, comme dans la LV1
            self.name.setStyleSheet("background: %s; color: %s;" % (PALETTE[col], text_on(PALETTE[col])))
        else:
            self.name.setStyleSheet("")

    def select(self, ck, focus=True):
        if ck != self.sel:
            self.commit()
            self.sel = ck
            self._load_editor()
            for i, r in enumerate(self.rows):
                if r["ck"] == ck:
                    self.list_scroll.ensureVisible(0, i * ROW_H + ROW_H // 2, 0, ROW_H * 2)
                    break
            self.list.update()
            for fv in self.faces:
                fv.update()
        if focus:
            self.activateWindow()
            self.name.setFocus()
            self.name.selectAll()

    def commit(self):
        """Enregistre le nom tapé s'il a changé."""
        if not self.sel or not self.state:
            return
        lab = self.label(self.sel) or {}
        name = self.name.text().strip()
        if name != (lab.get("name") or ""):
            self._post_port(self.sel, name, lab.get("color"))

    def _post_port(self, ck, name, color):
        c, key = ck
        return self._post("port", {"console": c, "port": key, "name": name, "color": color})

    def pick_color(self, i):
        if not self.sel:
            return
        self._post_port(self.sel, self.name.text().strip(), i)
        self._load_editor(keep_text=True)
        self.name.setFocus()

    def clear_port(self):
        """Efface l'étiquette : le(s) canal(aux) LV1 alimenté(s) par la prise redeviennent des pistes par défaut
        (« Channel N » tout de suite, couleur n° 13 par le bouton « Couleurs → LV1 »)."""
        if not self.sel:
            return
        c, key = self.sel
        chans = [ch for ch, _s, _l, _c in self.chain(c, key)["lv1"]] if xs.parse_key(key)[1] == "in" else []
        self.name.setText("")
        if self._post_port(self.sel, "", None) and chans:
            self.notify(T("Étiquette effacée"), T("%s : piste par défaut (« Channel N »). Couleur par défaut : bouton "
                                                  "« Couleurs → LV1 ».") % ", ".join("In %d" % ch for ch in chans))
        self._load_editor()

    def _order(self):
        """Ordre de ‹ › : lignes de la PATCH MAP pour une entrée qui y figure, sinon les prises de même type de
        l'appareil (sorties, entrées sans EXP)."""
        c, key = self.sel
        slot, io, _n = xs.parse_key(key)
        listed = [r["ck"] for r in self.rows if r["ck"] is not None]
        if io == "in" and self.sel in listed:
            return listed
        dev = xs.DEVICES.get(self.devices(c).get(slot) or "")
        if not dev:
            return [self.sel]
        nums = sorted(n for io2, n, _x, _y in dev["sockets"] if io2 == io)
        return [(c, xs.port_key(slot, io, n)) for n in nums]

    def step(self, d):
        if not self.sel:
            return
        self.commit()
        order = self._order()
        i = order.index(self.sel) if self.sel in order else -1
        j = i + d
        if 0 <= j < len(order):
            self.select(order[j])
        else:
            self.name.selectAll()

    # -- couleurs -> LV1 -------------------------------------------------------
    def color_targets(self):
        app = self.app
        return xs.lv1_color_targets((self.state or {}).get("sheet"), app.exp_map, app.lv1_sources, app.lv1_channels,
                                    (self.state or {}).get("applied"))

    def apply_colors(self):
        """Couleurs des étiquettes -> canaux LV1, par clics dans sa fenêtre « Select a Color » (la LV1 refuse la
        couleur à distance). Page Patch de la LV1, appli en administrateur ; la fenêtre se cache pendant les clics.
        Pas de confirmation (le bouton suffit) ; résultat en notification en bas à droite (choix de Joseph)."""
        self.commit()
        title = T("Couleurs → LV1")
        targets = self.color_targets()
        if not targets:
            self.notify(title, T("Les canaux LV1 ont déjà les couleurs des prises."))
            return
        if not is_admin():
            self.notify(title, T("Il faut lancer X32 Gain Recall en administrateur (la LV1 l'est) : sinon Windows "
                                 "bloque les clics."), ok=False, ms=10000)
            return
        if not self.app.stage_lv1() or self.app._lv1_tab != "Patch":
            self.notify(title, T("Affichez la page Patch de la LV1 (vue Input A, liste en haut), puis recommencez."),
                        ok=False, ms=10000)
            return
        self.runner = ColorRunner(self, targets)
        self.hide()
        self.notify(title, T("%d canaux en cours… ne touchez pas la LV1.") % len(targets), ms=60000)
        QTimer.singleShot(250, self.runner.start)       # fenêtre cachée avant la 1re lecture d'écran
        self._watch_runner()

    def _watch_runner(self):
        r = self.runner
        if r is None:
            return
        if r.result is None:
            QTimer.singleShot(150, self._watch_runner)
            return
        self.runner = None
        done, err = r.result
        self.sync(self.app.stage_lv1(), self.app._lv1_tab == "Patch")
        if not self.isVisible():
            self.show()
        self.app.raise_now(self)
        msg = T("%d couleur(s) appliquée(s) dans la LV1.") % len(done)
        if err:
            msg += "\n" + T("Arrêt : %s") % err
        self.notify(T("Couleurs → LV1"), msg, ok=not err, ms=12000)
        self.refresh()

    # -- fichiers : une feuille par spectacle -------------------------------------
    def _file_dir(self):
        d = self.app.cfg.get("stage_dir") or ""
        return d if d and os.path.isdir(d) else os.path.join(os.path.expanduser("~"), "Documents")

    def export_sheet(self):
        """Feuille affichée -> « <nom>.stagepatch.json » (à ranger avec le spectacle, ou à passer sur l'autre PC)."""
        from PySide6.QtWidgets import QFileDialog
        self.commit()
        r = self.app.backend.stage_post("export", {"id": (self.state or {}).get("active")})
        if not r.get("ok"):
            self.notify(T("Exporter"), r.get("error") or T("Échec"), ok=False)
            return
        doc = r["doc"]
        safe = re.sub(r'[\\/:*?"<>|]+', "-", doc["sheet"]["name"]).strip() or "Patch"
        # fenêtre de Windows rattachée à STAGE PATCH : toujours devant elle (Joseph : jamais de message caché)
        path, _f = QFileDialog.getSaveFileName(self, T("Exporter la feuille"), os.path.join(self._file_dir(),
                                               safe + xs.EXPORT_EXT), T("Feuille de patch (*.stagepatch.json)"))
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += xs.EXPORT_EXT
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
        except OSError as e:
            self.notify(T("Exporter"), str(e), ok=False)
            return
        self.app.cfg["stage_dir"] = os.path.dirname(path)
        self.app.save_soon()
        self.notify(T("Feuille exportée"), os.path.basename(path))

    def import_sheet(self):
        """« .stagepatch.json » -> nouvelle feuille, active (les noms partent dans la LV1 comme pour une feuille choisie)."""
        from PySide6.QtWidgets import QFileDialog
        self.commit()
        path, _f = QFileDialog.getOpenFileName(self, T("Importer une feuille"), self._file_dir(),
                                               T("Feuille de patch (*.stagepatch.json *.json)"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
        except (OSError, ValueError) as e:
            self.notify(T("Importer"), T("Fichier illisible : %s") % e, ok=False)
            return
        self.app.cfg["stage_dir"] = os.path.dirname(path)
        self.app.save_soon()
        if self._post("import", {"doc": doc}):
            cur = next((s for s in self.state["sheets"] if s["id"] == self.state["active"]), {})
            self.notify(T("Feuille importée"), T("« %s » (%d prises) : feuille active.") % (cur.get("name"),
                                                                                         cur.get("ports", 0)))
            self._load_editor()

    # -- actions -----------------------------------------------------------
    def _pick_console(self, n):
        self.commit()
        self.console = n
        self._built = None
        self.reload()

    def _pick_sheet(self, i):
        self.commit()
        self._post("sheet", {"action": "activate", "id": self.sheets.itemData(i)})
        self._load_editor()

    def _toggle_auto(self):
        self._post("auto", {"on": not (self.state or {}).get("auto")})

    def sheet_action(self, act):
        self.commit()
        sid = self.state["active"]
        cur = next((s for s in self.state["sheets"] if s["id"] == sid), {})
        name = None
        if act in ("new", "rename", "duplicate"):
            prompt = {"new": T("Nom de la nouvelle feuille (spectacle, studio…) :"),
                      "rename": T("Nouveau nom :"), "duplicate": T("Nom de la copie :")}[act]
            init = {"new": "", "rename": cur.get("name", ""), "duplicate": cur.get("name", "") + T(" (copie)")}[act]
            name = Dialog(self.app, T("Feuille de patch"), prompt, T("OK"), edit=init, parent=self).ask()
            if name is None:
                return
        elif act == "delete":
            if not Dialog(self.app, T("Feuille de patch"), T("Supprimer la feuille « %s » ?") % cur.get("name"),
                          T("Supprimer"), danger=True, parent=self).ask():
                return
        self._post("sheet", {"action": act, "id": sid, "name": name})
        self._load_editor()
