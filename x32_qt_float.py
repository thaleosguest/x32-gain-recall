"""X/M32 Gain Recall — float v3 en Qt (PySide6).

Même rôle que x32_gain_float.py (float tk, 2.x), avec une interface Qt : potards lissés et surtout MULTI-TOUCH
(la LV1 est pensée pour plusieurs doigts ; tk ne voit qu'un doigt, chaque toucher y devient un clic de souris).
Toute la logique sans interface est reprise telle quelle de x32_gain_float (liaison avec l'appli principale,
fenêtres et couches de la LV1, lectures d'écran, calage, configuration) : seuls l'affichage et le toucher
changent. Configuration partagée avec le float tk (même fichier) : le calage est conservé.

v3, étape 1 (2026-10-14) : colonnes, languette, suivi de la LV1, calage, 48V, bulle des dB, saisie d'une valeur,
fonds, verrou. Pas encore : cadres Edit / Channel, panneaux Scènes / Routing / Consoles, barre de connexion
(menu ⋮ -> « Ouvrir la page » en attendant).
"""
import argparse
import math
import os
import sys
import threading
import time
import webbrowser

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")     # pixels Qt = pixels écran (calage sur la LV1)

import x32_gain_float as xf                                   # noqa: E402
from x32_gain_float import (                                  # noqa: E402
    APP_SHORT, APP_VERSION, APP_AUTHOR, AUTO_H, AUTO_OPEN_MODES, AUTO_PITCH, AUTO_X0, AUTO_Y0, BANKS,
    DEFAULT_THEME, GAIN_DB_PER_PX, GAIN_MAX, GAIN_MIN, LAYOUT_VERSION, LV1_BANKS, LV1_TABS, MIXER_TABS,
    OLD_TAB_W, OLD_TITLE_H, STRIP_EXTRA_H, TAB_W, THEMES, client_rect, exp_txt, find_lv1_window,
    foreground_window, join_tags, lv1_tab, lv1_windows, monitor_rect, place_below, quantize, set_theme_map,
    set_topmost, strip_tag, tc, window_alive, window_iconic, window_pid)

from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, QTimer, QEvent        # noqa: E402
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetrics, QRadialGradient,  # noqa: E402
                           QPainterPath, QInputDevice, QEventPoint, QIcon, QPixmap, QAction, QActionGroup)
from PySide6.QtWidgets import (QApplication, QWidget, QMenu, QDialog, QLabel, QLineEdit,   # noqa: E402
                               QPushButton, QVBoxLayout, QHBoxLayout)

QT_FLOAT_VERSION = "3.0.0-a2"

# couleurs du float tk (teintes du thème d'origine, converties par tc() pour le fond choisi)
BG, PANEL, BOX, LINE2 = "#08090a", "#111213", "#0d0e0f", "#3a3e43"
TXT, MUT, OK, AMBER, WARN, TEAL = "#e9edf0", "#8c939a", "#3ddc84", "#f2b63b", "#ff5b4d", "#13a9af"
PH_ON = xf.PH_ON
TAP_PX = 12                     # un toucher qui bouge moins que ça est un « tap » (48V, valeur, languette)
# Calage relevé sur la LV1 V17 en 1920x1080 (2026-10-14, Mixer 1, SndChk) : intérieur du cadre « Preamp / Gain / 48 »
# d'une tranche = 92 px au pas de 96 (x 143..234 pour la tranche 1), y 184..315. Les cartes restent DANS le cadre :
# le contour gris et le liseré jaune de la tranche sélectionnée restent visibles (demande de Joseph).
CARD_L, CARD_R = 1 / 96.0, 93 / 96.0        # bords de la carte, en fraction du pas des tranches
QT_AUTO_H = 132 / 1080.0
# Languette (v3) : dans l'espace vide de la barre du haut, entre « Setup » et le cadenas (x 1287..1370, boutons
# y 8..49 en 1920x1080) ; calée par la droite (le cadenas ne bouge pas quand des pages sont détachées)
TOOL_BOX = (1292 / 1920.0, 8 / 1080.0, 74 / 1920.0, 42 / 1080.0)
TOOL_ITEMS = ("conn", "arrow", "more")


def qc(color):
    return QColor(tc(color))


# --------------------------------------------------------------------------
#  Liaison avec l'appli : lectures et envois sur des fils (l'interface ne bloque jamais)
# --------------------------------------------------------------------------
class Link:
    def __init__(self, backend):
        self.backend = backend
        self.snap = None
        self.meters = None
        self.pending = {}
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = False
        threading.Thread(target=self._poll, name="etat", daemon=True).start()
        threading.Thread(target=self._send, name="envois", daemon=True).start()

    def _poll(self):
        while not self.stop:
            if not self.backend.needs_login:
                self.snap = self.backend.snapshot()
                self.meters = self.backend.meters()
            time.sleep(0.2)

    def _send(self):
        while not self.stop:
            self.wake.wait()
            self.wake.clear()
            with self.lock:
                todo, self.pending = self.pending, {}
            for (kind, idx), val in todo.items():
                if kind == "gain":
                    self.backend.set_gain(idx, val)
                else:
                    self.backend.set_phantom(idx, val)

    def set_gain(self, idx, db):
        with self.lock:
            self.pending[("gain", idx)] = db       # seule la dernière valeur de chaque préampli part
        self.wake.set()

    def set_phantom(self, idx, on):
        with self.lock:
            self.pending[("ph", idx)] = on
        self.wake.set()


# --------------------------------------------------------------------------
#  Colonnes : dessin et géométrie
# --------------------------------------------------------------------------
class Col:
    """Une colonne : canal LV1 (vue LV1) ou préampli (vue X32). idxs vide = trou transparent."""

    def __init__(self, idxs, ch):
        self.idxs, self.ch = list(idxs), ch
        self.color = None
        self.tag = ""
        self.name = ""
        self.x = self.w = 0              # zone de la colonne (pas des tranches) : prise au doigt
        self.cx = self.cw = 0            # carte, DANS le cadre de la tranche LV1


def draw_knob(p, kr, db, color, held):
    size = kr.width()
    a = kr.adjusted(2, 2, -2, -2)
    pen = QPen(qc(BG), max(2.0, size * 0.09), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(a, (90 + 135) * 16, -270 * 16)
    frac = None
    if db is not None:
        frac = max(0.0, min(1.0, (db - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)))
        pen.setColor(QColor(color or MUT))
        p.setPen(pen)
        p.drawArc(a, (90 + 135) * 16, int(-270 * frac * 16))
    b = kr.adjusted(size * .2, size * .2, -size * .2, -size * .2)
    grad = QRadialGradient(b.center() - QPointF(b.width() * .2, b.height() * .25), b.width() * .75)
    grad.setColorAt(0, QColor("#8f96a0" if held else "#747a83"))
    grad.setColorAt(1, QColor("#4a4f56"))
    p.setPen(QPen(QColor("#22252a"), 1))
    p.setBrush(grad)
    p.drawEllipse(b)
    if frac is not None:
        th = math.radians(-135 + frac * 270)
        c, rr = b.center(), b.width() / 2
        u = QPointF(math.sin(th), -math.cos(th))
        p.setPen(QPen(QColor(TXT), max(1.6, size * .07), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(c + u * rr * .15, c + u * rr * .8)
    else:
        p.setPen(QColor(MUT))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(b, Qt.AlignCenter, "?")


class FloatWindow(QWidget):
    """Les colonnes, dessinées dans une seule fenêtre transparente (trous = traversables)."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.setWindowTitle(APP_SHORT + " — Float")
        self.f_tag = QFont("Segoe UI", 7, QFont.Bold)
        self.f_name = QFont("Segoe UI", 9, QFont.Bold)
        self.f_val = QFont("Consolas", 9, QFont.Bold)
        self.f_val_s = QFont("Consolas", 8, QFont.Bold)
        self.f_ph = QFont("Segoe UI", 7, QFont.Bold)
        self.points = {}                 # id du point (doigt / souris) -> état du geste

    # -- géométrie -------------------------------------------------------------
    def unit_rects(self, col):
        """[(idx, zone du préampli, potard, valeur, 48V, diode)] d'une colonne."""
        app = self.app
        top = 5 + QFontMetrics(self.f_tag).height() + 3
        if col.ch is None:
            top += QFontMetrics(self.f_name).height()
        uw = col.cw / 2.0
        n = len(col.idxs)
        body_h = app.strip_h - top - 2
        fixed = 7 + 4 + 16 + 4 + 15 + 6
        ksz = max(14, min(uw - 6, body_h - fixed))
        if app.max_knob:
            ksz = min(ksz, app.max_knob)
        block = fixed + ksz
        y0 = top + max(0, (body_h - block) / 2)
        x0 = col.cx + (col.cw - uw * n) / 2
        out = []
        for k, idx in enumerate(col.idxs[:2]):
            ux = x0 + k * uw
            cx = ux + uw / 2
            led = QRectF(cx - 4, y0, 8, 7)
            kr = QRectF(cx - ksz / 2, y0 + 11, ksz, ksz)
            val = QRectF(ux, kr.bottom() + 3, uw, 16)
            pw = max(20, min(uw - 8, 38))
            ph = QRectF(cx - pw / 2, val.bottom() + 3, pw, 15)
            out.append((idx, QRectF(ux, top, uw, app.strip_h - top), kr, val, ph, led))
        return out

    # -- dessin ----------------------------------------------------------------
    def paintEvent(self, e):
        app = self.app
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        if not app.collapsed:
            clip = e.rect()
            for col in app.cols:
                if col.idxs and clip.intersects(QRectF(col.x, 0, col.w, app.strip_h).toAlignedRect()):
                    self._paint_col(p, col)
            # coin bas-droit : redimensionnement à la main
            r = self.width() - 1, app.strip_h - 1
            p.setPen(QPen(QColor(MUT), 1))
            p.drawLine(QPointF(r[0] - 8, r[1]), QPointF(r[0], r[1] - 8))
            p.drawLine(QPointF(r[0] - 4, r[1]), QPointF(r[0], r[1] - 4))
        p.end()

    def _paint_col(self, p, col):
        app = self.app
        r = QRectF(col.cx, 0, col.cw, app.strip_h)
        card = QPainterPath()
        card.addRoundedRect(r, 5, 5)
        p.fillPath(card, qc(PANEL))
        p.save()
        p.setClipPath(card)
        p.fillRect(QRectF(r.left(), 0, r.width(), 5), QColor(col.color) if col.color else qc(PANEL))
        p.restore()
        fm = QFontMetrics(self.f_tag)
        p.setPen(QColor(MUT))
        p.setFont(self.f_tag)
        p.drawText(QRectF(col.cx, 7, col.cw, fm.height()), Qt.AlignCenter, self._fit_tag(col.tag, col.cw - 4))
        if col.ch is None and col.name:
            p.setPen(QColor(TXT))
            p.setFont(self.f_name)
            name = QFontMetrics(self.f_name).elidedText(col.name, Qt.ElideRight, int(col.cw - 4))
            p.drawText(QRectF(col.cx, 7 + fm.height(), col.cw, QFontMetrics(self.f_name).height()), Qt.AlignCenter, name)
        held = {g["idx"] for g in self.points.values() if g.get("mode") == "gain"}
        for idx, zone, kr, val, ph, led in self.unit_rects(col):
            db = app.gain(idx)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(app.led_color(idx)))
            p.drawEllipse(led.center(), 3.5, 3.5)
            draw_knob(p, kr, db, col.color, idx in held)
            p.setPen(QColor(TXT))
            f = self.f_val if val.width() >= 34 else self.f_val_s
            text = "—" if db is None else "%.1f" % db
            if QFontMetrics(f).horizontalAdvance(text) > val.width() - 2 and db is not None:
                text = "%.0f" % db
            p.setFont(f)
            p.drawText(val, Qt.AlignCenter, text)
            on = app.phantom(idx)
            if on:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(PH_ON))
            else:
                p.setPen(QPen(qc(LINE2), 1))
                p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(ph, ph.height() / 2, ph.height() / 2)
            p.setPen(QColor("#ffffff" if on else (MUT if on is not None else tc(LINE2))))
            p.setFont(self.f_ph)
            p.drawText(ph, Qt.AlignCenter, "48V")

    def _fit_tag(self, one, avail):
        """« L 15 = EXP 15 », raccourci si la colonne est étroite (comme le float tk)."""
        fm = QFontMetrics(self.f_tag)
        if " = " not in one or fm.horizontalAdvance(one) <= avail:
            return one
        src, exp = one.split(" = ", 1)
        nums = exp.replace("EXP ", "")
        for cand in ("%s=%s" % (src.replace(" ", ""), exp.replace(" ", "")),
                     "%s · %s" % (src.replace(" ", ""), nums), exp, nums):
            if fm.horizontalAdvance(cand) <= avail:
                return cand
        return nums

    # -- toucher / souris ------------------------------------------------------
    def _hit(self, pos):
        if self.app.collapsed:
            return None
        if pos.x() > self.width() - 12 and pos.y() > self.app.strip_h - 12:
            return ("grip", None)
        for col in self.app.cols:
            if col.idxs and col.x <= pos.x() < col.x + col.w:
                for idx, zone, kr, val, ph, led in self.unit_rects(col):
                    if ph.adjusted(-3, -3, 3, 3).contains(pos):
                        return ("ph", idx)
                    if val.contains(pos):
                        return ("val", idx)
                    if zone.contains(pos):
                        return ("gain", idx)
                if len(col.idxs) >= 1:
                    return ("gain", self._nearest(col, pos))
        return None

    def _nearest(self, col, pos):
        rects = self.unit_rects(col)
        return min(rects, key=lambda r: abs(r[1].center().x() - pos.x()))[0]

    def _press(self, pid, pos, gpos):
        hit = self._hit(pos)
        if not hit:
            return
        kind, what = hit
        g = {"mode": kind, "idx": what, "y0": pos.y(), "p0": QPointF(gpos), "moved": False}
        if kind == "gain":
            db = self.app.gain(what)
            if db is None or self.app.locked:
                return
            g["db0"] = db
            self.app.dragging_start()
            self.app.pop.show_for(self, what)
        elif kind == "grip":
            g["size0"] = (self.app.strip_w, self.app.strip_h)
        self.points[pid] = g
        self.update()

    def _move(self, pid, pos, gpos):
        g = self.points.get(pid)
        if not g:
            return
        d = QPointF(gpos) - g["p0"]
        if abs(d.x()) + abs(d.y()) > TAP_PX:
            g["moved"] = True
        if g["mode"] == "gain":
            db = quantize(g["db0"] + (g["y0"] - pos.y()) * self.app.sensitivity)
            if db != self.app.local.get(g["idx"]):
                self.app.set_gain_local(g["idx"], db)
                self.app.pop.show_for(self, g["idx"])
        elif g["mode"] == "grip" and g["moved"]:
            w0, h0 = g["size0"]
            self.app.set_auto_place(False)
            n = max(1, len(self.app.cols))
            self.app.set_strip_size(w0 + d.x() / n, h0 + d.y())

    def _release(self, pid, gpos):
        g = self.points.pop(pid, None)
        if not g:
            return
        if g["mode"] == "gain":
            self.app.dragging_end(g["idx"])
            self.app.pop.hide_soon()
        elif not g["moved"]:
            if g["mode"] == "ph":
                self.app.phantom_tap(g["idx"])
            elif g["mode"] == "val":
                self.app.edit_value(g["idx"])
        self.update()

    def event(self, e):
        t = e.type()
        if t in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd, QEvent.TouchCancel):
            for pt in e.points():
                st = pt.state()
                gp = pt.globalPosition()
                if st == QEventPoint.State.Pressed:
                    self._press(pt.id(), pt.position(), gp)
                elif st == QEventPoint.State.Updated:
                    self._move(pt.id(), pt.position(), gp)
                elif st == QEventPoint.State.Released:
                    self._release(pt.id(), gp)
            if t == QEvent.TouchCancel:
                for pid in list(self.points):
                    self._release(pid, QPointF())
            e.accept()
            return True
        return super().event(e)

    @staticmethod
    def _from_touch(e):
        return e.device() is not None and e.device().type() == QInputDevice.DeviceType.TouchScreen

    def mousePressEvent(self, e):
        if not self._from_touch(e) and e.button() == Qt.LeftButton:
            self._press("mouse", e.position(), e.globalPosition())

    def mouseMoveEvent(self, e):
        if not self._from_touch(e):
            self._move("mouse", e.position(), e.globalPosition())

    def mouseReleaseEvent(self, e):
        if not self._from_touch(e) and e.button() == Qt.LeftButton:
            self._release("mouse", e.globalPosition())


class ToolBar(QWidget):
    """Languette (v3) : point de connexion (glisser = déplacer le float), flèche de repli, menu ⋮, cadenas.
    Posée dans l'espace vide de la barre du haut de la LV1 (demande de Joseph) ; sans LV1 : à gauche du float."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.points = {}
        self.resize(74, 42)

    def item_at(self, pos):
        i = int(pos.x() * len(TOOL_ITEMS) / max(1, self.width()))
        return TOOL_ITEMS[max(0, min(len(TOOL_ITEMS) - 1, i))]

    def paintEvent(self, _e):
        app = self.app
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 6, 6)
        p.fillPath(path, qc(PANEL))
        p.setPen(QPen(qc(LINE2), 1))
        p.drawPath(path)
        cw = self.width() / float(len(TOOL_ITEMS))
        h = self.height()
        dot = OK if app.conn_state == "ok" else (AMBER if app.conn_state == "trying" else "#555555")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(dot))
        p.drawEllipse(QPointF(cw / 2, h / 2), 5, 5)
        if app.locked:
            p.setPen(QColor(WARN))
            p.setFont(QFont("Segoe UI", 6))
            p.drawText(QRectF(0, h - 13, cw, 12), Qt.AlignCenter, "🔒")
        p.setPen(QColor(TXT))
        p.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p.drawText(QRectF(cw, 0, cw, h), Qt.AlignCenter, "▾" if app.collapsed else "▴")
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(QRectF(2 * cw, 0, cw, h), Qt.AlignCenter, "⋮")
        p.end()

    def _press(self, pid, pos, gpos):
        self.points[pid] = {"item": self.item_at(pos), "p0": QPointF(gpos), "moved": False,
                            "win0": self.app.win.pos()}

    def _move(self, pid, pos, gpos):
        g = self.points.get(pid)
        if not g:
            return
        d = QPointF(gpos) - g["p0"]
        if abs(d.x()) + abs(d.y()) > TAP_PX:
            g["moved"] = True
        if g["item"] == "conn" and g["moved"] and not self.app.collapsed:
            self.app.set_auto_place(False)          # déplacement à la main : calage manuel
            self.app.win.move(g["win0"] + QPoint(round(d.x()), round(d.y())))
            self.app.save_soon()

    def _release(self, pid):
        g = self.points.pop(pid, None)
        if not g or g["moved"]:
            return
        if g["item"] == "arrow":
            self.app.toggle_collapse()
        elif g["item"] == "more":
            self.app.more_menu(self.mapToGlobal(QPoint(0, self.height())))
        self.update()

    def event(self, e):
        t = e.type()
        if t in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd, QEvent.TouchCancel):
            for pt in e.points():
                st = pt.state()
                if st == QEventPoint.State.Pressed:
                    self._press(pt.id(), pt.position(), pt.globalPosition())
                elif st == QEventPoint.State.Updated:
                    self._move(pt.id(), pt.position(), pt.globalPosition())
                elif st == QEventPoint.State.Released:
                    self._release(pt.id())
            if t == QEvent.TouchCancel:
                self.points.clear()
            e.accept()
            return True
        return super().event(e)

    def mousePressEvent(self, e):
        if not FloatWindow._from_touch(e) and e.button() == Qt.LeftButton:
            self._press("mouse", e.position(), e.globalPosition())

    def mouseMoveEvent(self, e):
        if not FloatWindow._from_touch(e):
            self._move("mouse", e.position(), e.globalPosition())

    def mouseReleaseEvent(self, e):
        if not FloatWindow._from_touch(e) and e.button() == Qt.LeftButton:
            self._release("mouse")


# --------------------------------------------------------------------------
#  Petites fenêtres : bulle des dB, confirmation, saisie
# --------------------------------------------------------------------------
class ValuePop(QWidget):
    """Bulle « +32.5 dB » en gros au-dessus du potard qu'on tourne : le doigt ne la cache pas."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
                         | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.idx = None
        self.text = ""
        self.sub = ""
        self.color = None
        self.resize(150, 66)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._hide)

    def show_for(self, fw, idx):
        if not self.app.cfg.get("value_pop", True):
            return
        self.timer.stop()
        db = self.app.gain(idx)
        self.text = ("%+.1f dB" % db) if db is not None else "— dB"
        if self.isVisible() and self.idx == idx:
            self.update()
            return
        self.idx = idx
        self.sub = "Gain " + self.app.label(idx)
        self.color = self.app.color_of(idx)
        for col in self.app.cols:
            for r in fw.unit_rects(col) if idx in col.idxs else ():
                if r[0] == idx:
                    c = fw.mapToGlobal(r[2].center().toPoint())
                    x, y = c.x() - self.width() // 2, c.y() - self.height() - 80
                    if y < 0:
                        y = c.y() + 80
                    self.move(max(0, x), y)
        self.show()
        self.update()

    def hide_soon(self, ms=700):
        self.timer.start(ms)

    def _hide(self):
        self.idx = None
        self.hide()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.fillPath(path, QColor(20, 22, 25, 235))
        p.setPen(QPen(QColor(self.color or AMBER), 2))
        p.drawPath(path)
        p.setPen(QColor(TXT))
        p.setFont(QFont("Consolas", 20, QFont.Bold))
        p.drawText(QRectF(0, 4, self.width(), 36), Qt.AlignCenter, self.text)
        p.setPen(QColor(MUT))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRectF(0, 40, self.width(), 20), Qt.AlignCenter, self.sub)
        p.end()


DLG_CSS = """
QDialog { background: %(panel)s; border: 2px solid %(edge)s; border-radius: 10px; }
QLabel { color: %(txt)s; }
QLabel#title { color: %(edge)s; font: bold 14pt "Segoe UI"; }
QLabel#body { font: 11pt "Segoe UI"; }
QLineEdit { background: #000; color: %(txt)s; border: 1px solid %(line)s; border-radius: 6px;
            font: 16pt "Consolas"; padding: 6px; }
QPushButton { font: bold 13pt "Segoe UI"; padding: 10px 20px; border-radius: 8px; border: 0; }
QPushButton#cancel { background: %(btn)s; color: %(txt)s; }
QPushButton#ok { background: %(okbg)s; color: %(okfg)s; }
"""


class Dialog(QDialog):
    """Fenêtre au style du float : gros boutons pour le doigt, toujours devant, centrée sur le float."""

    def __init__(self, app, title, text, ok_text, danger=False, edit=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        edge = WARN if danger else TEAL
        self.setStyleSheet(DLG_CSS % {"panel": tc(PANEL), "edge": edge, "txt": TXT, "line": tc(LINE2),
                                      "btn": tc("#25282b"), "okbg": WARN if danger else TEAL,
                                      "okfg": "#ffffff" if danger else "#032"})
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        head = QHBoxLayout()
        self.led = QLabel("●")
        self.led.setStyleSheet("color:%s; font: 18pt 'Segoe UI';" % edge)
        head.addWidget(self.led)
        t = QLabel(title)
        t.setObjectName("title")
        head.addWidget(t, 1)
        lay.addLayout(head)
        b = QLabel(text)
        b.setObjectName("body")
        b.setWordWrap(True)
        b.setMinimumWidth(360)
        lay.addWidget(b)
        self.edit = None
        if edit is not None:
            self.edit = QLineEdit(edit)
            self.edit.selectAll()
            self.edit.returnPressed.connect(self.accept)
            lay.addWidget(self.edit)
        row = QHBoxLayout()
        c = QPushButton("Annuler")
        c.setObjectName("cancel")
        c.clicked.connect(self.reject)
        o = QPushButton(ok_text)
        o.setObjectName("ok")
        o.clicked.connect(self.accept)
        row.addWidget(c)
        row.addStretch(1)
        row.addWidget(o)
        lay.addSpacing(8)
        lay.addLayout(row)
        self._blink = True
        if danger:
            tm = QTimer(self)
            tm.timeout.connect(self._tick)
            tm.start(450)
        self.adjustSize()
        fw = app.win
        c0 = fw.mapToGlobal(QPoint(fw.width() // 2, fw.height() // 2))
        self.move(max(0, c0.x() - self.width() // 2), max(0, c0.y() - self.height() // 2))

    def _tick(self):
        self._blink = not self._blink
        self.led.setStyleSheet("color:%s; font: 18pt 'Segoe UI';" % (WARN if self._blink else "#3a1d1b"))

    def ask(self):
        ok = self.exec() == QDialog.Accepted
        if self.edit is not None:
            return self.edit.text().strip() if ok else None
        return ok


# --------------------------------------------------------------------------
#  Le float
# --------------------------------------------------------------------------
class QtFloat:
    def __init__(self, args, qapp):
        self.args = args
        self.qapp = qapp
        cfg = xf.load_cfg()
        self.cfg = cfg
        self.bank = cfg.get("bank", 0) if 0 <= cfg.get("bank", 0) < len(BANKS) else 0
        self.view = cfg.get("view") or ("x32" if cfg else "lv1")
        self.lv1_bank = cfg.get("lv1_bank", 0) if 0 <= cfg.get("lv1_bank", 0) < len(LV1_BANKS) else 0
        self.strip_w = float(cfg.get("strip_w", 46))
        self.strip_h = int(cfg.get("strip_h") or round(self.strip_w) + STRIP_EXTRA_H)
        self.auto_place = cfg.get("auto_place", True)
        self.theme = cfg.get("theme") if cfg.get("theme") in THEMES else DEFAULT_THEME
        set_theme_map(self.theme)
        self.sensitivity = args.sensitivity
        self.clip_db = args.clip_db
        self.max_knob = None
        self.locked = False
        self.collapsed = False
        self.conn_state = None
        self.update = None
        self.autostart = None
        self.lv1_sources, self.exp_map, self.lv1_map, self.lv1_channels = {}, {}, {}, {}
        self.lv1_custom, self.lv1_custom_name = None, ""
        self._layout = None
        self._lv1_layer_seen = self._lv1_preset_seen = None
        self._lv1_lay = {}
        self.local = {}                  # préampli -> gain tenu pendant / juste après un glisser
        self._drags = 0
        self.cols = []

        # LV1 (comme le float tk, voir x32_gain_float.FloatApp._follow_lv1)
        self.detached = args.lv1_window
        self._lv1_hwnd = self._lv1_pid = None
        self._lv1_seek = 0.0
        self._lv1_found = {}
        self._detached_now = ()
        self._gone_since = None
        self._lv1_tab = None
        self._surface = "mixer1"
        if self.detached:
            self._lv1_tab = "Mixer 2" if self.detached == "MIXER2" else "Mixer 1"
            self._surface = "mixer2" if self.detached == "MIXER2" else "mixer1"
        self._wait_lv1 = bool(args.wait_lv1)
        self._shown = None
        self._z_state = None
        self._reader_args = self._reader_res = None
        self._server_seen = False
        self._refused_since = None

        if args.direct:
            self.backend = xf.DirectBackend(None if args.no_colors else args.companion, args.color_poll)
        else:
            self.backend = xf.ServerBackend(args.port, session_token=args.session_token)
        if args.direct and args.sim:
            self.backend.demo()
        elif args.direct and args.ip:
            self.backend.connect(args.ip)
        self.link = Link(self.backend)

        self.win = FloatWindow(self)
        self.tool = ToolBar(self)
        self.pop = ValuePop(self)
        try:
            icon = QIcon()
            for d in xf.ICON_PNG_B64:
                pm = QPixmap()
                pm.loadFromData(__import__("base64").b64decode(d), "PNG")
                icon.addPixmap(pm)
            qapp.setWindowIcon(icon)
        except Exception:
            pass
        x, y = self._apply_screen_profile(cfg.get("x", 200), cfg.get("y", 200))
        self.win.move(x + TAB_W, y)          # config partagée avec le float tk : sa fenêtre commence à la languette
        self.build_cols()

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_cfg)
        self._t_poll = QTimer()
        self._t_poll.timeout.connect(self.apply_state)
        self._t_poll.start(200)
        self._t_follow = QTimer()
        self._t_follow.timeout.connect(self.follow_lv1)
        self._t_follow.start(100)
        threading.Thread(target=self._screen_reader, name="lecture-ecran", daemon=True).start()
        if args.lv1_front:
            QTimer.singleShot(500, lambda: self._lv1_front(15))
        self.follow_lv1()

    # -- état des préamplis ----------------------------------------------------
    def gain(self, idx):
        if idx in self.local:
            return self.local[idx]
        g = (self.link.snap or {}).get("gains")
        return g[idx] if g and idx < len(g) else None

    def phantom(self, idx):
        p = (self.link.snap or {}).get("phantom")
        return p[idx] if p and idx < len(p) else None

    def led_color(self, idx):
        m = self.link.meters or {}
        v = (m.get("v") or [None] * (idx + 1))[idx] if m.get("live") and idx < len(m.get("v") or []) else None
        if v is None:
            return "#333333"
        if v >= self.clip_db:
            return WARN
        if v >= self.clip_db - 10:
            return AMBER
        return OK if v > -60 else "#333333"

    def color_of(self, idx):
        for col in self.cols:
            if idx in col.idxs:
                return col.color
        return None

    def label(self, idx):
        return strip_tag(idx)

    def set_gain_local(self, idx, db):
        self.local[idx] = db
        self.link.set_gain(idx, db)
        self._update_col_of(idx)

    def dragging_start(self):
        self._drags += 1

    def dragging_end(self, idx):
        self._drags = max(0, self._drags - 1)
        # l'état lu peut être en retard d'un tour : la valeur locale tient encore un instant
        QTimer.singleShot(800, lambda: self.local.pop(idx, None) if not self._held(idx) else None)

    def _held(self, idx):
        return any(g.get("mode") == "gain" and g.get("idx") == idx for g in self.win.points.values())

    def _update_col_of(self, idx):
        for col in self.cols:
            if idx in col.idxs:
                self.win.update(QRectF(col.x, 0, col.w, self.strip_h).toAlignedRect())

    def phantom_tap(self, idx):
        if self.locked:
            return
        on = self.phantom(idx)
        if on is None:
            return
        if on:
            self.link.set_phantom(idx, False)
        elif Dialog(self, "Activer le +48 V ?",
                    "Voie %s : vérifiez qu'aucun micro ruban / dynamique non protégé n'est branché avant "
                    "d'activer l'alimentation fantôme." % self.label(idx), "Activer +48 V", danger=True).ask():
            self.link.set_phantom(idx, True)

    def edit_value(self, idx):
        if self.locked:
            return
        cur = self.gain(idx)
        r = Dialog(self, "Gain — voie %s" % self.label(idx), "Valeur en dB (%.0f à +%.0f) :" % (GAIN_MIN, GAIN_MAX),
                   "OK", edit="%.1f" % (cur if cur is not None else 0.0)).ask()
        if r is None:
            return
        try:
            db = quantize(float(r.replace(",", ".")))
        except ValueError:
            Dialog(self, "Gain", "« %s » n'est pas un nombre valide." % r, "OK").ask()
            return
        self.set_gain_local(idx, db)
        QTimer.singleShot(1500, lambda: self.local.pop(idx, None) if not self._held(idx) else None)

    # -- colonnes ----------------------------------------------------------------
    def bank_name(self):
        if self.view == "lv1" and self.lv1_custom is not None:
            return self.lv1_custom_name
        return LV1_BANKS[self.lv1_bank][0] if self.view == "lv1" else BANKS[self.bank][0]

    def lv1_layout(self):
        exp_to_idx = {int(e): int(k) for k, e in (self.exp_map or {}).items() if e}
        if self.lv1_custom is not None:
            chans = self.lv1_custom
        else:
            start = LV1_BANKS[self.lv1_bank][1]
            chans = list(range(start, start + 16))
        return [(ch or 0, [exp_to_idx[e] for e in (self.lv1_sources.get(ch, []) if ch else []) if e in exp_to_idx])
                for ch in chans]

    def build_cols(self):
        if self.view == "lv1":
            self._layout = self.lv1_layout()
            self.cols = [Col(idxs, ch) for ch, idxs in self._layout]
        else:
            self._layout = None
            start = BANKS[self.bank][1]
            self.cols = [Col([start + k], None) for k in range(16)]
        self._relayout()
        self._refresh_cols()

    def _relayout(self):
        w = self.strip_w
        for i, col in enumerate(self.cols):
            col.x, col.w = int(round(i * w)), int(round((i + 1) * w)) - int(round(i * w))
            col.cx = int(round(i * w + w * CARD_L))
            col.cw = int(round(i * w + w * CARD_R)) - col.cx
        width = int(round(len(self.cols) * w))
        if (self.win.width(), self.win.height()) != (width, self.strip_h):
            self.win.setFixedSize(width, self.strip_h)
        self.win.update()

    def set_strip_size(self, w, h=None):
        w = max(28.0, min(140.0, w))
        h = self.strip_h if h is None else int(max(70, min(700, h)))
        if abs(w - self.strip_w) < 0.01 and h == self.strip_h:
            return
        self.strip_w, self.strip_h = w, h
        self._relayout()
        self.save_soon()

    def _refresh_cols(self):
        """Repères, couleurs et noms (vue LV1 : la colonne EST le canal ; vue X32 : canal qui reçoit l'EXP)."""
        em, lc = self.exp_map or {}, self.lv1_channels or {}
        for col in self.cols:
            if col.ch == 0:
                col.tag, col.color, col.name = "", None, ""
                continue
            if col.ch is not None:
                ch = col.ch
                exps = self.lv1_sources.get(ch, [])
                col.tag = ("%s = EXP %s" % (join_tags(col.idxs), "/".join(exp_txt(e) for e in exps)) if col.idxs
                           else ("EXP %s" % "/".join(exp_txt(e) for e in exps) if exps else ""))
            else:
                exp = em.get(str(col.idxs[0]), em.get(col.idxs[0]))
                col.tag = strip_tag(col.idxs[0]) + (" = EXP %s" % exp_txt(exp) if exp else "")
                lm = self.lv1_map or {}
                ch = (lm.get(str(exp), lm.get(exp)) if exp else None)
            info = (lc.get(str(ch), lc.get(ch)) or {}) if ch else {}
            col.color = info.get("color")
            col.name = info.get("label") or ("In %d" % ch if ch else "")

    # -- boucle d'état (200 ms) --------------------------------------------------
    def apply_state(self):
        b = self.backend
        if b.needs_login and not getattr(self, "_login_open", False):
            self._login_open = True
            code = Dialog(self, "Code d'accès", "Code d'accès de l'appli (affiché sur la page) :", "OK",
                          edit="").ask()
            if code:
                b.login(code)
            self._login_open = False
        snap = self.link.snap
        if not self.args.direct:
            if b.reachable:
                self._server_seen, self._refused_since = True, None
            elif b.refused and self._server_seen:
                self._refused_since = self._refused_since or time.monotonic()
                if time.monotonic() - self._refused_since > 1.5:
                    self.quit()
                    return
        if not snap:
            return
        conn = "ok" if snap.get("connected") else ("trying" if snap.get("trying") else None)
        changed = conn != self.conn_state
        self.conn_state = conn
        if snap.get("autostart_ok"):
            self.autostart = bool(snap.get("autostart"))
        self.update = snap.get("update")
        self.exp_map = snap.get("exp_map") or {}
        self.lv1_map = snap.get("lv1_map") or {}
        self.lv1_channels = snap.get("lv1_channels") or {}
        self.lv1_sources = {int(k): [int(e) for e in v] for k, v in (snap.get("lv1_sources") or {}).items()}
        lay = (snap.get("lv1_layers") or {}).get(self._surface) or (
            snap.get("lv1_layer") if self._surface == "mixer1" else None) or {}
        self._lv1_lay = lay
        if self._surface != getattr(self, "_surface_seen", None):
            self._surface_seen = self._surface
            self._lv1_layer_seen = self._lv1_preset_seen = None
        key = (lay.get("mode"), lay.get("page"), tuple(lay.get("channels") or ()))
        rebuild = False
        if key != self._lv1_layer_seen:
            self._lv1_layer_seen = key
            lb, chans = lay.get("bank"), lay.get("channels")
            if self.view == "lv1" and chans:
                if lb is not None and 0 <= lb < len(LV1_BANKS):
                    self.lv1_bank, self.lv1_custom = lb, None
                else:
                    self.lv1_custom = list(chans)[:16] + [None] * (16 - len(chans))
                    self.lv1_custom_name = ("LV1 Custom %d" % (lay.get("page", 0) + 1) if lay.get("mode") == 1
                                            else "LV1 Mix (Talk Back)")
                rebuild = True
        preset = lay.get("preset_name")
        has_inputs = any(lay.get("channels") or [])
        state = (preset, has_inputs)
        if preset and state != self._lv1_preset_seen:
            self._lv1_preset_seen = state
            want_open = preset in AUTO_OPEN_MODES and has_inputs
            if want_open == self.collapsed:
                self.toggle_collapse()
        if self.view == "lv1" and self.lv1_layout() != self._layout:
            rebuild = True
        if rebuild:
            self.build_cols()
        else:
            self._refresh_cols()
        self.win.update()
        if changed:
            self.tool.update()

    # -- LV1 : devant / derrière, caché, calage (100 ms) -------------------------
    def follow_lv1(self):
        now = time.time()
        if self._lv1_hwnd and not window_alive(self._lv1_hwnd):
            self._lv1_hwnd = None
        if now >= self._lv1_seek:
            self._lv1_seek = now + 2.0
            found = lv1_windows()
            self._lv1_found = found
            self._detached_now = tuple(k for k in found if k != "main")
            if not self._lv1_hwnd:
                self._lv1_hwnd = found.get(self.detached or "main")
                self._lv1_pid = window_pid(self._lv1_hwnd) if self._lv1_hwnd else None
        lv1 = self._lv1_hwnd
        if self.detached:
            if lv1:
                self._gone_since = None
            else:
                self._gone_since = self._gone_since or now
                if now - self._gone_since > 4:
                    self.quit()
                    return
        fg = foreground_window()
        front = (not lv1) or (fg and window_pid(fg) in (self._lv1_pid, os.getpid()))
        res, self._reader_res = self._reader_res, None
        if res and res.get("tab"):
            self._lv1_tab = res["tab"]
            if res["tab"] in MIXER_TABS:
                self._surface = "mixer2" if res["tab"] == "Mixer 2" else "mixer1"
        if lv1 and not window_iconic(lv1) and front and not self._drags and self._reader_args is None:
            self._reader_args = {"hwnd": lv1, "detached": self.detached,
                                 "names": tuple(t for t in LV1_TABS
                                                if t.replace(" ", "").upper() not in self._detached_now)}
        if lv1:
            self._wait_lv1 = True
        shown = not (lv1 and (window_iconic(lv1) or (self._lv1_tab and self._lv1_tab not in MIXER_TABS)))
        if self._wait_lv1 and not lv1:
            shown = False
        if shown != self._shown:
            self._shown = shown
            if shown:
                if not self.collapsed:
                    self.win.show()
                self.tool.show()
                self._z_state = None
            else:
                self.win.hide()
                self.tool.hide()
                self.pop.hide()
        if shown and lv1 and self.auto_place and not window_iconic(lv1):
            self._auto_fit(lv1)
        if shown:
            self._place_tool(lv1)
            hwnds = [int(w.winId()) for w in (self.win, self.tool) if w.isVisible()]
            key = (len(hwnds),)
            if front:
                if self._z_state != ("top",) + key:
                    for h in hwnds:
                        set_topmost(h, True)
                    self._z_state = ("top",) + key
            elif self._z_state != (fg,) + key:
                for h in hwnds:
                    set_topmost(h, False)
                    place_below(h, fg)
                self._z_state = (fg,) + key

    def _place_tool(self, lv1):
        """Languette dans l'espace vide de la barre du haut de la LV1 (fenêtre principale) ; Mixer détaché ou
        pas de LV1 : à gauche des colonnes, comme l'ancienne languette."""
        rect = client_rect(lv1) if (lv1 and not self.detached and not window_iconic(lv1)) else None
        if rect and rect[2] >= 400:
            x, y, w, h = rect
            geom = (x + round(w * TOOL_BOX[0]), y + round(h * TOOL_BOX[1]),
                    max(60, round(w * TOOL_BOX[2])), max(32, round(h * TOOL_BOX[3])))
        else:
            p = self.win.pos()
            geom = (p.x() - 76, p.y(), 74, 42)
        if (self.tool.x(), self.tool.y(), self.tool.width(), self.tool.height()) != geom:
            self.tool.setGeometry(*geom)

    def _screen_reader(self):
        """Lecture de l'onglet de la LV1 (captures de 15-45 ms) sur un fil à part, jamais pendant un glisser."""
        while True:
            args, self._reader_args = self._reader_args, None
            if args:
                try:
                    tab = None if args["detached"] else lv1_tab(args["hwnd"], args["names"])
                    self._reader_res = {"tab": tab}
                except Exception as e:
                    print("Lecture d'écran : %s" % e)
            time.sleep(0.3)

    # -- calage ------------------------------------------------------------------
    def set_auto_place(self, on):
        if on == self.auto_place:
            return
        self.auto_place = on
        self._auto_geom = None
        self.save_soon()

    def _auto_fit(self, lv1):
        rect = client_rect(lv1)
        if not rect or rect[2] < 400 or rect == getattr(self, "_auto_geom", None):
            return
        self._auto_geom = rect
        x, y, w, h = rect
        self.set_strip_size(w * AUTO_PITCH, round(h * QT_AUTO_H))
        self.win.move(x + round(w * AUTO_X0), y + round(h * AUTO_Y0))
        self.save_soon()

    def _apply_screen_profile(self, x, y):
        """Comme le float tk : calage mémorisé pour cet écran, sinon le dernier mis à l'échelle."""
        layout = self.cfg.get("layout")
        if layout != LAYOUT_VERSION:
            dx, dy = (OLD_TAB_W[layout] - TAB_W, 0) if layout in OLD_TAB_W else (-TAB_W, OLD_TITLE_H)
            x, y = x + dx, y + dy
            for prof in (self.cfg.get("screens") or {}).values():
                prof["dx"] = prof.get("dx", 0) + dx
                prof["dy"] = prof.get("dy", 0) + dy
        rect = monitor_rect(x, y)
        screens = self.cfg.get("screens") or {}
        if not rect:
            return x, y
        prof = screens.get("%dx%d" % (rect[2], rect[3]))
        if prof:
            self.strip_w = float(prof.get("strip_w", self.strip_w))
            self.strip_h = int(prof.get("strip_h") or self.strip_h)
            return rect[0] + prof["dx"], rect[1] + prof["dy"]
        last = screens.get(self.cfg.get("last_screen") or "")
        if last:
            try:
                w0, h0 = (int(v) for v in self.cfg["last_screen"].split("x"))
            except ValueError:
                return x, y
            s = min(rect[2] / float(w0), rect[3] / float(h0))
            self.strip_w = float(last.get("strip_w", self.strip_w)) * s
            self.strip_h = int(int(last.get("strip_h") or self.strip_h) * s)
            return rect[0] + int(last["dx"] * rect[2] / float(w0)), rect[1] + int(last["dy"] * rect[3] / float(h0))
        return x, y

    def save_soon(self):
        self._save_timer.start(800)

    def save_cfg(self):
        p = self.win.pos()
        x, y = p.x() - TAB_W, p.y()        # repère du float tk (voir __init__)
        screens = dict(self.cfg.get("screens") or {})
        last = self.cfg.get("last_screen")
        rect = monitor_rect(x, y)
        if rect:
            last = "%dx%d" % (rect[2], rect[3])
            screens[last] = {"dx": x - rect[0], "dy": y - rect[1], "strip_w": round(self.strip_w, 3),
                             "strip_h": self.strip_h}
        cfg = dict(self.cfg)            # garde les réglages propres au float tk (routing_view...)
        cfg.update({"bank": self.bank, "view": self.view, "lv1_bank": self.lv1_bank,
                    "strip_w": round(self.strip_w, 3), "strip_h": self.strip_h, "theme": self.theme, "x": x, "y": y,
                    "screens": screens, "last_screen": last, "layout": LAYOUT_VERSION,
                    "auto_place": self.auto_place, "value_pop": self.cfg.get("value_pop", True)})
        self.cfg = cfg
        xf.save_cfg(cfg)

    # -- languette et menu -------------------------------------------------------
    def toggle_collapse(self):
        """Repli : les colonnes disparaissent, la languette reste."""
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.pop.hide()
            self.win.hide()
        elif self._shown:
            self.win.show()
            self._z_state = None
        self.tool.update()

    def toggle_lock(self):
        self.locked = not self.locked
        self.tool.update()

    def select_bank(self, name):
        for view, banks in (("lv1", LV1_BANKS), ("x32", BANKS)):
            for i, (n, _s) in enumerate(banks):
                if n == name:
                    self.view = view
                    self.lv1_custom = None
                    if view == "lv1":
                        self.lv1_bank = i
                    else:
                        self.bank = i
                    self.build_cols()
                    self.save_cfg()
                    return

    def set_theme(self, name):
        self.theme = name
        set_theme_map(name)
        self.win.update()
        self.save_cfg()

    def more_menu(self, gpos):
        m = QMenu()
        m.setStyleSheet("QMenu { background:%s; color:%s; font: 13pt 'Segoe UI'; border:1px solid %s; }"
                        "QMenu::item { padding: 7px 26px 7px 22px; }"
                        "QMenu::item:selected { background:%s; color:#032; }"
                        "QMenu::item:disabled { color:%s; }"
                        "QMenu::separator { height:1px; background:%s; margin:4px 8px; }"
                        % (tc("#15171a"), TXT, tc(LINE2), TEAL, MUT, tc(LINE2)))
        banks = m.addMenu("Banque : %s" % self.bank_name())
        grp = QActionGroup(banks)
        for group in (LV1_BANKS, BANKS):
            if group is BANKS:
                banks.addSeparator()
            for name, _s in group:
                a = banks.addAction(name)
                a.setCheckable(True)
                a.setChecked(name == self.bank_name())
                grp.addAction(a)
                a.triggered.connect(lambda _c=False, n=name: self.select_bank(n))

        def check(label, on, fn):
            a = m.addAction(label)
            a.setCheckable(True)
            a.setChecked(bool(on))
            a.triggered.connect(fn)
            return a
        check("Caler sur la LV1 (auto)", self.auto_place, lambda c: self.set_auto_place(c))
        check("Bulle des dB en réglant", self.cfg.get("value_pop", True),
              lambda c: (self.cfg.__setitem__("value_pop", c), self.save_soon()))
        m.addAction("Plus large  (+)").triggered.connect(lambda: self._nudge(2))
        m.addAction("Plus étroit  (−)").triggered.connect(lambda: self._nudge(-2))
        m.addSeparator()
        if not self.args.direct:
            m.addAction("Scènes, routing, consoles : ouvrir la page").triggered.connect(
                lambda: webbrowser.open("http://127.0.0.1:%d/" % self.args.port))
        check("Verrouiller l'édition", self.locked, lambda c: self.toggle_lock())
        themes = m.addMenu("Fond de la fenêtre")
        tg = QActionGroup(themes)
        for name in THEMES:
            a = themes.addAction(name + ("  (défaut)" if name == DEFAULT_THEME else ""))
            a.setCheckable(True)
            a.setChecked(name == self.theme)
            tg.addAction(a)
            a.triggered.connect(lambda _c=False, n=name: self.set_theme(n))
        m.addSeparator()
        a = m.addAction("%s v%s (float Qt %s) — by %s" % (APP_SHORT, APP_VERSION, QT_FLOAT_VERSION, APP_AUTHOR))
        a.setEnabled(False)
        if self.update and self.update.get("url"):
            m.addAction("⬆ Mise à jour %s disponible…" % self.update.get("version")).triggered.connect(
                lambda: webbrowser.open(self.update["url"]))
        m.addAction("Fermer le float").triggered.connect(self.quit)
        if not self.args.direct:
            if self.autostart is not None:
                check("Lancer avec Windows", self.autostart, self._toggle_autostart)
            m.addAction("Quitter l'appli").triggered.connect(self._quit_app)
        m.exec(gpos)

    def _nudge(self, delta):
        self.set_auto_place(False)
        self.set_strip_size(self.strip_w + delta / 8.0)

    def _toggle_autostart(self, on):
        r = self.backend.set_autostart(on)
        if r.get("ok"):
            self.autostart = r.get("on")
        else:
            Dialog(self, "Lancer avec Windows", r.get("error") or "Impossible", "OK").ask()

    def _quit_app(self):
        if Dialog(self, "Quitter l'appli ?", "Le float, la page et la connexion à la console s'arrêtent.",
                  "Quitter", danger=True).ask():
            self.backend.quit_app()
            self.quit()

    def _lv1_front(self, tries):
        ctypes, u32 = xf._user32()
        hwnd = find_lv1_window()
        if not (u32 and hwnd) or u32.GetForegroundWindow() == hwnd:
            return
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)
        u32.SetForegroundWindow(hwnd)
        if tries > 1:
            QTimer.singleShot(200, lambda: self._lv1_front(tries - 1))

    def quit(self):
        try:
            self.save_cfg()
        except Exception:
            pass
        self.link.stop = True
        self.backend.close()
        self.qapp.quit()


def main():
    ap = argparse.ArgumentParser(description=APP_SHORT + " (Float Qt) — float v3, multi-touch")
    ap.add_argument("--version", action="version", version="%s Float Qt %s - by %s" % (APP_SHORT, QT_FLOAT_VERSION,
                                                                                         APP_AUTHOR))
    ap.add_argument("--port", type=int, default=8032, help="port local de l'appli principale (défaut 8032)")
    ap.add_argument("--session-token", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--lv1-front", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--wait-lv1", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--lv1-window", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--direct", action="store_true", help="connexion OSC directe à la console")
    ap.add_argument("--ip", help="adresse IP de la X32 (avec --direct)")
    ap.add_argument("--sim", action="store_true", help="simulateur de X32 intégré (avec --direct)")
    ap.add_argument("--clip-db", type=float, default=-3.0, help="seuil (dBFS) de la diode rouge (défaut -3)")
    ap.add_argument("--sensitivity", type=float, default=GAIN_DB_PER_PX, help="dB par pixel (défaut 0.05)")
    ap.add_argument("--companion", nargs="?", const="http://127.0.0.1:8000", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--no-colors", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--color-poll", type=float, default=1.0, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.lv1_window:
        main_cfg = xf.load_cfg()
        xf.CFG_PATH = os.path.join(os.path.dirname(xf.CFG_PATH), "x32_float_config_%s.json" % args.lv1_window)
        if not os.path.exists(xf.CFG_PATH):
            xf.save_cfg({k: v for k, v in main_cfg.items() if k in ("theme", "view", "routing_view")})
    qapp = QApplication(sys.argv[:1])
    qapp.setQuitOnLastWindowClosed(False)
    QtFloat(args, qapp)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
