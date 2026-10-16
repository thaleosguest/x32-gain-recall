"""Test multi-touch Qt (prototype v3) : 16 colonnes de préamplis posées sur la LV1 (Mixer 1), comme le float.

- parle à l'appli principale déjà lancée (port 8032), comme le float : gains réels de la console ;
- plusieurs doigts = plusieurs potards en même temps (le compteur de la languette montre les doigts vus) ;
- colonnes sans préampli : vraiment transparentes (on doit pouvoir toucher la LV1 au travers) ;
- ne prend pas le focus : la LV1 reste la fenêtre active ;
- 48V affiché seulement (pas de bascule dans ce test) ; croix ✕ de la languette pour quitter.

Lancer : py tools/qt_touch_test.py [--port 8032]
"""
import argparse
import os
import sys
import threading
import time
import math

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")     # pixels Qt = pixels écran (calage sur la LV1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import x32_gain_float as xf                                   # noqa: E402

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QEvent      # noqa: E402
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QRadialGradient, QPainterPath,  # noqa: E402
                           QInputDevice, QEventPoint)
from PySide6.QtWidgets import QApplication, QWidget                  # noqa: E402

PANEL, TRACK, TXT, MUT, LINE, PH_ON = "#383c42", "#2b2e33", "#e9edf0", "#8c939a", "#4d5259", "#d1343b"
TAB_W = 22
SENS = 0.05                     # dB par pixel, comme le float


class Link:
    """État lu sur l'appli principale toutes les 200 ms, envoi des gains : sur des fils, l'UI ne bloque jamais."""

    def __init__(self, port):
        self.backend = xf.ServerBackend(port)
        self.snap = None
        self.pending = {}
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._poll, daemon=True).start()
        threading.Thread(target=self._send, daemon=True).start()

    def _poll(self):
        while True:
            s = self.backend._get("/api/state")
            if s:
                self.snap = s
            time.sleep(0.2)

    def _send(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            with self.lock:
                todo, self.pending = self.pending, {}
            for idx, db in todo.items():
                self.backend.set_gain(idx, db)

    def set_gain(self, idx, db):
        with self.lock:
            self.pending[idx] = db       # seule la dernière valeur de chaque préampli part
        self.wake.set()


class Overlay(QWidget):
    def __init__(self, link):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.link = link
        self.pitch, self.col_h = 96.0, 133
        self.cols = []                   # [(canal, [préamplis], couleur, repère)]
        self.local = {}                  # idx -> gain tenu pendant un glisser (l'état lu peut être en retard)
        self.grabs = {}                  # id du point (doigt / souris) -> (idx, y0, db0)
        self.max_fingers = 0
        self._geom = None
        self.resize(TAB_W + 16 * 96, 133)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(100)

    # -- données / calage ------------------------------------------------------
    def _tick(self):
        hw = (xf.lv1_windows() or {}).get("main")
        rect = xf.client_rect(hw) if hw else None
        if rect and rect[2] > 400:
            x, y, w, h = rect
            self.pitch, self.col_h = w * xf.AUTO_PITCH, round(h * xf.AUTO_H)
            geom = (x + round(w * xf.AUTO_X0) - TAB_W, y + round(h * xf.AUTO_Y0),
                    TAB_W + math.ceil(16 * self.pitch), self.col_h)
        else:
            geom = (100, 100, TAB_W + 16 * 96, 133)
            self.pitch, self.col_h = 96.0, 133
        if geom != self._geom:
            self._geom = geom
            self.setGeometry(*geom)
        s = self.link.snap or {}
        lay = (s.get("lv1_layers") or {}).get("mixer1") or s.get("lv1_layer") or {}
        chans = (lay.get("channels") or list(range(1, 17)))[:16]
        exp_to_idx = {int(e): int(k) for k, e in (s.get("exp_map") or {}).items() if e}
        srcs = {int(k): [int(e) for e in v] for k, v in (s.get("lv1_sources") or {}).items()}
        lc = s.get("lv1_channels") or {}
        cols = []
        for ch in chans:
            idxs = [exp_to_idx[e] for e in srcs.get(ch, []) if e in exp_to_idx] if ch else []
            info = lc.get(str(ch)) or {}
            cols.append((ch, idxs[:2], info.get("color"), "L %d" % ch if ch else ""))
        self.cols = cols
        self.update()

    def _gain(self, idx):
        if idx in self.local:
            return self.local[idx]
        g = (self.link.snap or {}).get("gains")
        return g[idx] if g and idx < len(g) else None

    def _phantom(self, idx):
        p = (self.link.snap or {}).get("phantom")
        return p[idx] if p and idx < len(p) else None

    # -- dessin ----------------------------------------------------------------
    def _col_rect(self, i):
        x0 = TAB_W + round(i * self.pitch)
        return QRectF(x0, 0, TAB_W + round((i + 1) * self.pitch) - x0 - 2, self.col_h)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # languette : ✕ + nombre de doigts vus (en cours / maximum)
        tab = QPainterPath()
        tab.addRoundedRect(QRectF(0, 0, TAB_W - 3, self.col_h), 5, 5)
        p.fillPath(tab, QColor(PANEL))
        p.setPen(QColor(TXT))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(QRectF(0, 2, TAB_W - 3, 24), Qt.AlignCenter, "✕")
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor("#3ddc84" if self.grabs else MUT))
        p.drawText(QRectF(0, self.col_h / 2 - 20, TAB_W - 3, 40), Qt.AlignCenter,
                   "%d\n%d" % (len(self.grabs), self.max_fingers))
        for i, (ch, idxs, color, tag) in enumerate(self.cols):
            if idxs:
                self._strip(p, self._col_rect(i), idxs, color, tag)
        p.end()

    def _strip(self, p, r, idxs, color, tag):
        card = QPainterPath()
        card.addRoundedRect(r, 6, 6)
        p.fillPath(card, QColor(PANEL))
        p.save()
        p.setClipPath(card)
        p.fillRect(QRectF(r.left(), 0, r.width(), 4), QColor(color or PANEL))
        p.restore()
        p.setPen(QColor(MUT))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(QRectF(r.left(), 6, r.width(), 13), Qt.AlignCenter, tag)
        uw = (r.width() - 4) / 2
        x0 = r.left() + (r.width() - uw * len(idxs)) / 2
        for k, idx in enumerate(idxs):
            self._unit(p, QRectF(x0 + k * uw, 20, uw, r.height() - 22), idx, color)

    def _unit(self, p, r, idx, color):
        g, ph = self._gain(idx), self._phantom(idx)
        cx = r.center().x()
        size = max(16, min(r.width() - 4, r.height() - 46))
        kr = QRectF(cx - size / 2, r.top() + 2, size, size)
        held = any(v[0] == idx for v in self.grabs.values())
        a = kr.adjusted(2, 2, -2, -2)
        pen = QPen(QColor(TRACK), size * 0.09, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(a, (90 + 135) * 16, -270 * 16)
        b = kr.adjusted(size * .2, size * .2, -size * .2, -size * .2)
        if g is not None:
            frac = max(0.0, min(1.0, (g - xf.GAIN_MIN) / (xf.GAIN_MAX - xf.GAIN_MIN)))
            pen.setColor(QColor(color or MUT))
            p.setPen(pen)
            p.drawArc(a, (90 + 135) * 16, int(-270 * frac * 16))
        grad = QRadialGradient(b.center() - QPointF(b.width() * .2, b.height() * .25), b.width() * .75)
        grad.setColorAt(0, QColor("#8a919b" if held else "#747a83"))
        grad.setColorAt(1, QColor("#4a4f56"))
        p.setPen(QPen(QColor("#22252a"), 1))
        p.setBrush(grad)
        p.drawEllipse(b)
        if g is not None:
            th = math.radians(-135 + frac * 270)
            c, rr = b.center(), b.width() / 2
            u = QPointF(math.sin(th), -math.cos(th))
            p.setPen(QPen(QColor(TXT), max(2, size * .07), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(c + u * rr * .15, c + u * rr * .8)
        p.setPen(QColor(TXT))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(QRectF(r.left(), kr.bottom() + 2, r.width(), 16), Qt.AlignCenter,
                   "—" if g is None else "%.1f" % g)
        pw = min(r.width() - 6, 34)
        pr = QRectF(cx - pw / 2, kr.bottom() + 21, pw, 14)
        if ph:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(PH_ON))
        else:
            p.setPen(QPen(QColor(LINE), 1))
            p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(pr, 7, 7)
        p.setPen(QColor("#ffffff" if ph else MUT))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(pr, Qt.AlignCenter, "48V")

    # -- toucher / souris ------------------------------------------------------
    def _hit(self, pos):
        """Préampli sous le point (toute la colonne compte, pas seulement le potard : prise au doigt)."""
        for i, (ch, idxs, color, tag) in enumerate(self.cols):
            r = self._col_rect(i)
            if idxs and r.contains(pos):
                k = 0 if len(idxs) == 1 or pos.x() < r.center().x() else 1
                return idxs[k]
        return None

    def _press(self, pid, pos):
        if pos.x() < TAB_W and pos.y() < 28:
            QApplication.quit()
            return
        idx = self._hit(pos)
        g = self._gain(idx) if idx is not None else None
        if g is not None:
            self.grabs[pid] = (idx, pos.y(), g)
            self.max_fingers = max(self.max_fingers, len(self.grabs))

    def _move(self, pid, pos):
        if pid not in self.grabs:
            return
        idx, y0, db0 = self.grabs[pid]
        db = xf.quantize(db0 + (y0 - pos.y()) * SENS)
        if db != self.local.get(idx):
            self.local[idx] = db
            self.link.set_gain(idx, db)

    def _release(self, pid):
        g = self.grabs.pop(pid, None)
        if g and not any(v[0] == g[0] for v in self.grabs.values()):
            idx = g[0]
            QTimer.singleShot(800, lambda: self.local.pop(idx, None))   # laisse l'état lu rattraper

    def event(self, e):
        t = e.type()
        if t in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd, QEvent.TouchCancel):
            for pt in e.points():
                st = pt.state()
                if st == QEventPoint.State.Pressed:
                    self._press(pt.id(), pt.position())
                elif st == QEventPoint.State.Updated:
                    self._move(pt.id(), pt.position())
                elif st == QEventPoint.State.Released or t == QEvent.TouchCancel:
                    self._release(pt.id())
            if t == QEvent.TouchCancel:
                self.grabs.clear()
            self.update()
            e.accept()
            return True
        return super().event(e)

    @staticmethod
    def _from_touch(e):
        return e.device() is not None and e.device().type() == QInputDevice.DeviceType.TouchScreen

    def mousePressEvent(self, e):
        if not self._from_touch(e):
            self._press("mouse", e.position())
            self.update()

    def mouseMoveEvent(self, e):
        if not self._from_touch(e):
            self._move("mouse", e.position())
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._from_touch(e):
            self._release("mouse")
            self.update()


def main():
    ap = argparse.ArgumentParser(description="Test multi-touch Qt (prototype v3)")
    ap.add_argument("--port", type=int, default=8032)
    args = ap.parse_args()
    app = QApplication(sys.argv)
    w = Overlay(Link(args.port))
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
