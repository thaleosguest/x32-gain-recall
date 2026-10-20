"""Float v3 (Qt) — panneaux : Scènes, Routing (+ éditeur en matrice / listes), Consoles, connexion à la console.

Mêmes fonctions que les panneaux du float tk (x32_gain_float.FloatApp._fill_*_panel, RoutingMatrix,
_edit_routing), en version tactile : gros boutons, listes qui défilent au doigt (avec élan), confirmations au style
du float. Le panneau s'ouvre sous les colonnes (au-dessus s'il n'y a pas la place) et se ferme par sa croix ✕.
"""
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea, QScroller,
                               QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox, QDialog, QStackedWidget)

import x32_qt_float as qf
from x32_i18n import T
from x32_qt_float import TXT, MUT, OK, AMBER, WARN, TEAL, PANEL, LINE2, Dialog, tc

BLUE = "#31b6f7"
CYAN = "#3fd0ff"
PANEL_W = {"scenes": 460, "routing": 460, "consoles": 430, "console": 460}
TITLES = {"scenes": "SCÈNES DE GAINS", "routing": "PROFILS DE ROUTING", "consoles": "CONSOLES",
          "console": "CONSOLE"}

CSS = """
QFrame#panel { background: %(panel)s; border: 1px solid %(line)s; border-radius: 10px; }
QWidget#content, QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QLabel { color: %(txt)s; font: 10pt "Segoe UI"; }
QLabel#title { color: %(mut)s; font: bold 9pt "Segoe UI"; letter-spacing: 1px; }
QLabel[mut="1"] { color: %(mut)s; font: 9pt "Segoe UI"; }
QLabel[name="1"] { font: bold 11pt "Segoe UI"; }
QLabel[badge="1"] { color: %(teal)s; font: bold 8pt "Segoe UI"; }
QLabel#status { color: %(mut)s; font: 9pt "Segoe UI"; }
QLineEdit { background: #000; color: %(txt)s; border: 1px solid %(line)s; border-radius: 6px; padding: 7px 9px;
            font: 11pt "Segoe UI"; selection-background-color: %(teal)s; }
QPushButton { background: %(btn)s; color: %(txt)s; border: 0; border-radius: 7px; padding: 8px 13px;
              font: bold 10pt "Segoe UI"; min-height: 22px; }
QPushButton:pressed { background: %(line)s; }
QPushButton[kind="ok"] { background: %(teal)s; color: #032; }
QPushButton[kind="blue"] { background: %(blue)s; color: #001a2a; }
QPushButton[kind="amber"] { background: transparent; color: %(amber)s; border: 1px solid %(amber)s; }
QPushButton[kind="warn"] { background: transparent; color: %(warn)s; border: 1px solid %(warn)s; }
QPushButton[kind="tab"] { background: %(btn)s; }
QPushButton[kind="tabon"] { background: %(teal)s; color: #032; }
QPushButton#close { font: bold 14pt "Segoe UI"; padding: 2px 12px; }
QPushButton#close:pressed { background: %(warn)s; }
QFrame[row="1"] { background: %(row)s; border: 1px solid %(line)s; border-radius: 8px; }
QFrame[row="2"] { background: #0a2a2a; border: 2px solid %(teal)s; border-radius: 8px; }
QComboBox { background: %(btn)s; color: %(txt)s; border: 0; border-radius: 6px; padding: 6px 10px;
            font: 10pt "Segoe UI"; min-height: 22px; }
QComboBox QAbstractItemView { background: %(row)s; color: %(txt)s; selection-background-color: %(teal)s;
                              selection-color: #032; font: 12pt "Segoe UI"; }
QCheckBox { color: %(mut)s; font: 9pt "Segoe UI"; }
QScrollBar:vertical { background: transparent; width: 14px; margin: 2px; }
QScrollBar::handle:vertical { background: %(line)s; border-radius: 5px; min-height: 40px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def css():
    return CSS % {"panel": tc(PANEL), "line": tc(LINE2), "txt": TXT, "mut": MUT, "teal": TEAL, "btn": tc("#25282b"),
                  "blue": BLUE, "amber": AMBER, "warn": WARN, "row": tc("#0d0e0f")}


def button(text, cb=None, kind=None):
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    b.setFocusPolicy(Qt.NoFocus)
    if cb:
        b.clicked.connect(lambda _checked=False, cb=cb: cb())     # clicked envoie un booléen : on l'ignore
    return b


def label(text, mut=False, prop=None):
    lb = QLabel(text)
    if mut:
        lb.setProperty("mut", "1")
    if prop:
        lb.setProperty(prop, "1")
    lb.setWordWrap(mut)
    return lb


def row_frame(active=False):
    f = QFrame()
    f.setProperty("row", "2" if active else "1")
    return f


def touch_scroll(area):
    """Défilement au doigt avec élan (comme un téléphone)."""
    QScroller.grabGesture(area.viewport(), QScroller.TouchGesture)


def pick_console(app, title):
    """Plusieurs consoles : n° (0-based) de la console choisie, ou None (annulé). Une seule : 0."""
    cs = list(app._consoles or [])
    if len(cs) <= 1:
        return 0
    d = QDialog(None, Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
    d.setStyleSheet(css() + "QDialog { background: %s; border: 2px solid %s; border-radius: 10px; }"
                    % (tc(PANEL), tc(LINE2)))
    v = QVBoxLayout(d)
    v.setContentsMargins(16, 12, 16, 14)
    t = QLabel(title)
    t.setStyleSheet("font: bold 13pt 'Segoe UI';")
    v.addWidget(t)
    res = {"n": None}

    def pick(n):
        res["n"] = n
        d.accept()
    for c in cs:
        st = "" if c.get("connected") else T("  (non connectée)")
        b = button(T("Console %d — %s%s") % (c["n"] + 1, c.get("name") or c.get("ip") or "?", st),
                   lambda _c=False, n=c["n"]: pick(n), "ok" if c.get("connected") else None)
        b.setEnabled(bool(c.get("connected")))
        b.setStyleSheet("text-align: left; font: bold 12pt 'Segoe UI'; padding: 10px 16px;")
        v.addWidget(b)
    v.addWidget(button(T("Annuler"), d.reject))
    d.adjustSize()
    c0 = app.win.mapToGlobal(app.win.rect().center())
    d.move(c0.x() - d.width() // 2, max(0, c0.y() - d.height() // 2))
    d.exec()
    return res["n"]


# --------------------------------------------------------------------------
#  Menu de la languette
# --------------------------------------------------------------------------
MENU_CSS = """
QFrame#menu { background: rgb(17,17,17); border: 1px solid rgb(160,160,160); border-radius: 6px; }
QPushButton { background: transparent; color: %(txt)s; border: 0; border-radius: 6px; text-align: left;
              padding: 9px 14px; font: 13pt "Segoe UI"; }
QPushButton:pressed { background: %(teal)s; color: #032; }
QPushButton[kind="info"] { color: %(mut)s; font: 9pt "Segoe UI"; }
QPushButton#close { font: bold 13pt "Segoe UI"; text-align: center; padding: 4px 12px; }
QFrame#sep { background: rgb(60,60,60); max-height: 1px; min-height: 1px; margin: 3px 8px; }
"""


class MenuPopup(QWidget):
    """Menu maison, au style de la languette (et du cadenas de la LV1). Le menu « popup » de Qt se refermait
    aussitôt (la LV1 reste la fenêtre active : le float ne prend jamais le focus). Celui-ci ne prend pas le focus
    et se ferme quand on choisit une entrée, qu'on retouche le hamburger ou sa croix ✕."""

    W = 330

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(MENU_CSS % {"txt": TXT, "mut": MUT, "teal": TEAL})
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setObjectName("menu")
        outer.addWidget(self.frame)
        self.lay = QVBoxLayout(self.frame)
        self.lay.setContentsMargins(6, 4, 6, 6)
        self.lay.setSpacing(0)
        self.setFixedWidth(self.W)

    def show_entries(self, entries, parent=None):
        while self.lay.count():
            it = self.lay.takeAt(0)
            ws = [it.widget()] if it.widget() else []
            if it.layout():
                while it.layout().count():
                    ws.append(it.layout().takeAt(0).widget())
            for w in ws:
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
        head = QHBoxLayout()
        if parent is not None:
            head.addWidget(self._btn(T("◂  Retour"), lambda: self.show_entries(parent)), 1)
        else:
            head.addStretch(1)
        x = QPushButton("✕")
        x.setObjectName("close")
        x.setFocusPolicy(Qt.NoFocus)
        x.clicked.connect(self.hide)
        head.addWidget(x)
        self.lay.addLayout(head)
        for e in entries:
            if e == "-":
                sep = QFrame()
                sep.setObjectName("sep")
                self.lay.addWidget(sep)
                continue
            text, act = e[0], e[1]
            if isinstance(act, list):
                self.lay.addWidget(self._btn(text + "   ▸", lambda sub=act: self.show_entries(sub, entries)))
            elif act is None:
                b = self._btn(text, None)
                b.setProperty("kind", "info")
                self.lay.addWidget(b)
            else:
                checked = e[2] if len(e) > 2 else None
                if checked is None:
                    mark = ""
                elif len(e) > 3 and e[3] == "radio":         # choix dans un sous-menu : coche sur le courant
                    mark = "✓   " if checked else "      "
                else:                                         # option à cocher : case
                    mark = "☑  " if checked else "☐  "
                self.lay.addWidget(self._btn(mark + text, lambda act=act: self._run(act)))
        self.adjustSize()
        self.place()
        self.show()
        self.raise_()
        self.app.raise_now(self)

    def _btn(self, text, cb):
        b = QPushButton(text)
        b.setFocusPolicy(Qt.NoFocus)
        if cb:
            b.clicked.connect(lambda _checked=False, cb=cb: cb())     # clicked envoie un booléen : on l'ignore
        return b

    def _run(self, act):
        self.hide()
        QTimer.singleShot(0, act)             # après la fermeture (l'action peut ouvrir une fenêtre)

    def place(self):
        """Sous la languette, calé sur son bord droit, dans l'écran."""
        t = self.app.tool
        x, y = t.x() + t.width() - self.width(), t.y() + t.height() + 4
        scr = t.screen().availableGeometry() if t.screen() else None
        if scr:
            x = max(scr.left(), min(x, scr.right() - self.width()))
            if y + self.height() > scr.bottom():
                y = max(scr.top(), t.y() - self.height() - 4)
        self.move(x, y)


# --------------------------------------------------------------------------
#  Tuile « X32 Routing » sur la page Patch de la LV1
# --------------------------------------------------------------------------
class PatchButton(QWidget):
    """Sur la page Patch de la LV1 (3.0.1, demande de Joseph) : une tuile au style des appareils du rack (« 1. X32RACK »,
    « 2. LV1-PORT » : 96x96 px en 1920x1080, bandeau bleu (68,138,255), corps noir, contour gris (160), bleu clair
    (56,201,255) quand elle est choisie), dans l'espace vide à droite. Ouvre le panneau Routing."""

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
        on = self.app.panel.mode == "routing" and self.app.panel.isVisible()
        k = w / 96.0
        p.fillRect(QRectF(0, 0, w, h), QColor(0, 0, 0))
        head = QRectF(0, 0, w, 28 * k)
        p.fillRect(head, QColor(68, 138, 255))
        p.setPen(QColor(0, 0, 0))
        p.setFont(QFont("Segoe UI", max(6, round(8 * k)), QFont.Bold))
        p.drawText(head.adjusted(5 * k, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, "X32 / M32")
        # petite matrice de routing, comme la grille du patch de la LV1
        g = QRectF(18 * k, 36 * k, 60 * k, 32 * k)
        p.setPen(QPen(QColor(60, 60, 60), 1))
        cols, rows = 6, 3
        for i in range(cols + 1):
            x = g.left() + i * g.width() / cols
            p.drawLine(QPointF(x, g.top()), QPointF(x, g.bottom()))
        for j in range(rows + 1):
            y = g.top() + j * g.height() / rows
            p.drawLine(QPointF(g.left(), y), QPointF(g.right(), y))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(56, 201, 255))
        cw, ch = g.width() / cols, g.height() / rows
        for i, j in ((0, 0), (1, 1), (2, 2), (4, 0), (5, 1)):
            p.drawRect(QRectF(g.left() + i * cw + 1.5, g.top() + j * ch + 1.5, cw - 3, ch - 3))
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", max(6, round(9 * k)), QFont.Bold))
        p.drawText(QRectF(0, 70 * k, w, 22 * k), Qt.AlignCenter, "ROUTING")
        p.setBrush(Qt.NoBrush)
        if on or self.down:
            p.setPen(QPen(QColor(56, 201, 255), 3 * k))
            p.drawRect(QRectF(1.5 * k, 1.5 * k, w - 3 * k, h - 3 * k))
        else:
            p.setPen(QPen(QColor(160, 160, 160), 1))
            p.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))
        p.end()

    def mousePressEvent(self, _e):
        self.down = True
        self.update()

    def mouseReleaseEvent(self, e):
        self.down = False
        if self.rect().contains(e.position().toPoint()):
            self.app.panel.toggle("routing")
            self.app.raise_now(self.app.panel)
        self.update()


class ShowButton(QWidget):
    """Page Show de la LV1 (3.0.1, demande de Joseph) : bouton « X32 Gains » dans la colonne de gauche, sous
    « Sessions », au style de ses boutons (relevé : 92x54 px en 1920x1080, fond (17,17,17), contour (160,160,160),
    texte (231,231,231) gras ; actif = fond bleu (56,201,255)). Ouvre le panneau des scènes de gains."""

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
        on = (self.app.panel.mode == "scenes" and self.app.panel.isVisible()) or self.down
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(Qt.NoPen if on else QPen(QColor(160, 160, 160), 1))
        p.setBrush(QColor(56, 201, 255) if on else QColor(17, 17, 17))
        p.drawRoundedRect(r, 6 * k, 6 * k)
        p.setPen(QColor(17, 17, 17) if on else QColor(231, 231, 231))
        p.setFont(QFont("Segoe UI", max(7, round(11 * k)), QFont.Bold))
        p.drawText(r, Qt.AlignCenter, T("Gains\nX32"))
        p.end()

    def mousePressEvent(self, _e):
        self.down = True
        self.update()

    def mouseReleaseEvent(self, e):
        self.down = False
        if self.rect().contains(e.position().toPoint()):
            self.app.panel.toggle("scenes")
            self.app.raise_now(self.app.panel)
        self.update()


class Toast(QWidget):
    """Petit message en bas à droite de l'écran au démarrage (3.0.1) : l'appli est active, consoles trouvées.
    Se ferme seul après quelques secondes, ou au toucher."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
                         | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.title = self.text = ""
        self.ok = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.setFixedSize(380, 78)

    def say(self, title, text, ok=True, ms=7000):
        self.title, self.text, self.ok = title, text, ok
        fm = QFontMetrics(QFont("Segoe UI", 9))
        th = fm.boundingRect(0, 0, 420 - 86, 400, Qt.TextWordWrap, text).height()
        self.setFixedSize(420, max(78, 44 + th + 12))
        scr = self.app.qapp.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 16, scr.bottom() - self.height() - 16)
        self.show()
        self.raise_()
        self.update()
        self.timer.start(ms)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
        p.fillPath(path, QColor(17, 17, 17))
        p.setPen(QPen(QColor(160, 160, 160), 1))
        p.drawPath(path)
        ls = 46
        p.drawImage(QRectF(14, (h - ls) / 2, ls, ls), qf.logo_image(ls, self.ok))
        p.setPen(QColor(TXT))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(QRectF(74, 12, w - 86, 24), Qt.AlignVCenter | Qt.AlignLeft, self.title)
        p.setPen(QColor(OK if self.ok else MUT))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(74, 38, w - 86, h - 46), Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap, self.text)
        p.end()

    def mouseReleaseEvent(self, _e):
        self.hide()


# --------------------------------------------------------------------------
#  Panneau (sous les colonnes)
# --------------------------------------------------------------------------
class Panel(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        self.app = app
        self.mode = None
        self.auto = False                # barre de connexion ouverte d'office (pas de console)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setObjectName("panel")
        outer.addWidget(self.frame)
        lay = QVBoxLayout(self.frame)
        lay.setContentsMargins(12, 8, 10, 10)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("title")
        head.addWidget(self.title, 1)
        x = button("✕", lambda: self.close_panel())
        x.setObjectName("close")
        head.addWidget(x)
        lay.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        touch_scroll(self.scroll)
        lay.addWidget(self.scroll, 1)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.setStyleSheet(css())

    # -- ouverture / placement -------------------------------------------------
    def toggle(self, mode, auto=False):
        if self.mode == mode and not auto:
            self.close_panel()
        else:
            self.open(mode, auto)

    def open(self, mode, auto=False):
        if mode != self.mode:
            self.say("")
        self.mode = mode
        self.auto = auto
        self.title.setText(T(TITLES[mode]))
        self.setStyleSheet(css())                      # fond choisi (thème) appliqué à l'ouverture
        self.rebuild()
        self.app.sync_panel()

    def close_panel(self):
        self.mode = None
        self.auto = False
        self.hide()

    def rebuild(self, keep_scroll=False):
        pos = self.scroll.verticalScrollBar().value() if keep_scroll else 0
        content = QWidget()
        content.setObjectName("content")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(6)
        getattr(self, "_fill_" + self.mode)(v)
        v.addStretch(1)
        self.scroll.setWidget(content)
        w = PANEL_W[self.mode]
        content.setMinimumWidth(w - 40)
        h = min(560, content.sizeHint().height() + 70 + (18 if self.status.text() else 0))
        self.setFixedSize(w, max(150, h))
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(pos))
        self.place()

    def place(self):
        """Sous les colonnes, au-dessus s'il n'y a pas la place en bas ; page Patch de la LV1 : sous la tuile
        « X32 Routing », calé sur son bord droit."""
        fw = self.app.win
        pb, sb = self.app.patch_btn, self.app.show_btn
        if pb.isVisible() and self.mode == "routing":
            x, y = pb.x() + pb.width() - self.width(), pb.y() + pb.height() + 8
        elif sb.isVisible() and self.mode == "scenes":       # page Show : à droite du bouton, calé sur son bas
            x, y = sb.x() + sb.width() + 10, max(0, sb.y() + sb.height() - self.height())
        else:
            x, y = fw.x(), fw.y() + fw.height() + 6
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr and y + self.height() > scr.bottom():
            y = max(scr.top(), fw.y() - self.height() - 6)
        if (self.x(), self.y()) != (x, y):
            self.move(x, y)

    def say(self, text, color=MUT):
        self.status.setText(text)
        self.status.setStyleSheet("color: %s;" % color)

    # -- scènes ----------------------------------------------------------------
    def _item(self, v, name, sub, active, badge, buttons):
        """Une ligne de liste : nom (+ badge si actif) et détail, puis les boutons EN TOUTES LETTRES sur une 2e
        ligne (3.0.1, demande de Joseph : plus de petits symboles)."""
        f = row_frame(active)
        g = QVBoxLayout(f)
        g.setContentsMargins(10, 6, 8, 8)
        g.setSpacing(4)
        top = QHBoxLayout()
        top.addWidget(label(name, prop="name"))
        if active:
            top.addWidget(label("  ● " + badge, prop="badge"))
        top.addStretch(1)
        g.addLayout(top)
        if sub:
            g.addWidget(label(sub, mut=True))
        row = QHBoxLayout()
        row.setSpacing(6)
        for text, cb, kind in buttons:
            row.addWidget(button(text, cb, kind))
        row.addStretch(1)
        g.addLayout(row)
        v.addWidget(f)

    def _fill_scenes(self, v):
        app, b = self.app, self.app.backend
        save = QHBoxLayout()
        name = QLineEdit()
        name.setPlaceholderText(T("Nom de la nouvelle scène"))
        name.returnPressed.connect(lambda: self.save_scene(name.text().strip()))
        save.addWidget(name, 1)
        save.addWidget(button(T("Sauvegarder"), lambda: self.save_scene(name.text().strip()), "ok"))
        v.addLayout(save)
        items = b.presets() if hasattr(b, "presets") else []
        if not items:
            v.addWidget(label(T("Aucune scène pour l'instant — tapez un nom ci-dessus et « Sauvegarder » pour créer "
                              "la première, à partir des gains actuels."), mut=True))
        for p in items:
            pid, nm = p["id"], p.get("name", "?")
            self._item(v, nm, p.get("created", ""), pid == app.active_scene_id, T("ACTIVE"), [
                (T("Charger"), lambda _c=False, pid=pid, nm=nm: self.recall_scene(pid, nm), "ok"),
                (T("Écraser"), lambda _c=False, pid=pid, nm=nm: self.overwrite_scene(pid, nm), "amber"),
                (T("Renommer"), lambda _c=False, pid=pid, nm=nm: self.rename_scene(pid, nm), None),
                (T("Supprimer"), lambda _c=False, pid=pid, nm=nm: self.delete_scene(pid, nm), "warn")])

    def save_scene(self, name):
        app = self.app
        if not name:
            self.say(T("Entrez un nom pour la scène."), WARN)
            return
        if not Dialog(app, T("Sauvegarder cette scène ?"), T("Sauvegarder « %s » avec TOUS les gains actuellement lus sur "
                      "la console (pas seulement la banque affichée) ?") % name, T("Sauvegarder")).ask():
            return
        r = app.backend.save_preset(name)
        if not r.get("ok"):
            self.say(r.get("error", T("Échec")), WARN)
        else:
            app.active_scene_id = r.get("id")
            self.say(T("Scène « %s » sauvegardée") % name, OK)
            self.rebuild(True)

    def recall_scene(self, pid, name):
        app = self.app
        if not Dialog(app, T("Rappeler la scène ?"), T("Rappeler « %s » ? Seuls les gains sont rappelés (pas le 48V, "
                      "comme dans le navigateur par défaut).") % name, T("Rappeler")).ask():
            return
        r = app.backend.recall_preset(pid)
        if not r.get("ok"):
            self.say(r.get("error", T("Échec")), WARN)
        else:
            app.active_scene_id = pid
            self.say(T("Scène « %s » rappelée") % name, OK)
            self.rebuild(True)

    def overwrite_scene(self, pid, name):
        app = self.app
        if not Dialog(app, T("Écraser la scène ?"), T("Remplacer le contenu de « %s » par les gains actuellement lus sur "
                      "la console (TOUS les gains) ? Cette action est irréversible.") % name, T("Écraser"),
                      danger=True).ask():
            return
        r = app.backend.overwrite_preset(pid)
        if not r.get("ok"):
            self.say(r.get("error", T("Échec")), WARN)
        else:
            app.active_scene_id = pid
            self.say(T("Scène « %s » mise à jour") % name, OK)
            self.rebuild(True)

    def rename_scene(self, pid, name):
        app = self.app
        r = Dialog(app, T("Renommer la scène"), T("Nouveau nom :"), T("Renommer"), edit=name).ask()
        if r is None:
            return
        new = r.strip()[:60]
        if not new:
            self.say(T("Le nom ne peut pas être vide."), WARN)
            return
        res = app.backend.rename_preset(pid, new)
        if not res.get("ok"):
            self.say(res.get("error", T("Échec")), WARN)
        else:
            self.say(T("Scène renommée en « %s »") % new, OK)
            self.rebuild(True)

    def delete_scene(self, pid, name):
        app = self.app
        if not Dialog(app, T("Supprimer définitivement ?"), T("Supprimer la scène « %s » ? Cette action est "
                      "irréversible.") % name, T("Supprimer"), danger=True).ask():
            return
        r = app.backend.delete_preset(pid)
        if not r.get("ok"):
            self.say(r.get("error", T("Échec")), WARN)
        else:
            if app.active_scene_id == pid:
                app.active_scene_id = None
            self.say(T("Scène « %s » supprimée") % name, OK)
            self.rebuild(True)

    # -- routing ---------------------------------------------------------------
    def _active_routings(self):
        """{id de profil: [n° de console]} : dernier routing chargé sur chaque console (mémorisé par l'appli)."""
        out = {}
        for c in self.app._consoles or []:
            act = c.get("routing_active") or {}
            if act.get("id"):
                out.setdefault(act["id"], []).append(c["n"])
        return out

    def _fill_routing(self, v):
        b = self.app.backend
        items = b.routings() if hasattr(b, "routings") else []
        editable = hasattr(b, "routing_model")
        if editable:
            def from_console():
                t = pick_console(self.app, T("Partir du routing de quelle console ?"))
                if t is not None:
                    self.app.edit_routing({"console": True, "target": t})
            v.addWidget(button(T("Créer un nouveau routing"), from_console, "ok"))
        if not items:
            v.addWidget(label(T("Aucun profil (ou appli principale non connectée)."), mut=True))
            return
        active = self._active_routings()
        several = len(self.app._consoles or []) > 1
        for p in items:
            pid, nm = p["id"], p.get("name", "?")
            cons = active.get(pid, [])
            badge = T("ACTIF") + ((T(" (console %s)") % ", ".join(str(n + 1) for n in cons)) if several else "")
            counts = p.get("counts", {})
            buttons = [(T("Charger"), lambda _c=False, pid=pid, nm=nm: self.apply_routing(pid, nm), "ok")]
            if editable:
                buttons.append((T("Modifier"), lambda _c=False, pid=pid: self.app.edit_routing({"id": pid}), None))
            if hasattr(b, "_post"):
                buttons += [(T("Renommer"), lambda _c=False, pid=pid, nm=nm: self.rename_routing(pid, nm), None),
                            (T("Supprimer"), lambda _c=False, pid=pid, nm=nm: self.delete_routing(pid, nm), "warn")]
            self._item(v, nm, T("%d lignes E/S · %s") % (counts.get("io", 0), p.get("source", "").replace("intégré", T("intégré"))
                       .replace("éditeur", T("éditeur"))), bool(cons),
                       badge, buttons)

    def apply_routing(self, pid, name):
        app = self.app
        target = pick_console(app, T("Charger « %s » sur quelle console ?") % name)
        if target is None:
            return
        where = T(" sur la console %d") % (target + 1) if len(app._consoles or []) > 1 else ""
        if not Dialog(app, T("Charger ce routing ?"), T("Charger « %s »%s ? Seul le routing E/S est touché (pas le patch de "
                      "sortie). À faire de préférence hors signal : ça peut couper l'audio en cours.") % (name, where),
                      T("Charger"), danger=True).ask():
            return
        r = app.backend.apply_routing(pid, target)
        self.say(*((T("Routing « %s » envoyé") % name, OK) if r.get("ok") else (r.get("error", T("Échec")), WARN)))
        QTimer.singleShot(600, lambda: self.rebuild(True) if self.mode == "routing" else None)

    def rename_routing(self, pid, name):
        r = Dialog(self.app, T("Renommer le routing"), T("Nouveau nom :"), T("Renommer"), edit=name).ask()
        if r is None:
            return
        new = r.strip()[:60]
        if not new:
            self.say(T("Le nom ne peut pas être vide."), WARN)
            return
        res = self.app.backend._post("/api/routings/rename", {"id": pid, "name": new}) or {}
        self.say(*((T("Routing renommé en « %s »") % new, OK) if res.get("ok") else (T("Renommage impossible"), WARN)))
        self.rebuild(True)

    def delete_routing(self, pid, name):
        if not Dialog(self.app, T("Supprimer définitivement ?"), T("Supprimer le routing « %s » de la liste ? La console "
                      "n'est pas touchée. Cette action est irréversible.") % name, T("Supprimer"), danger=True).ask():
            return
        res = self.app.backend._post("/api/routings/delete", {"id": pid}) or {}
        self.say(*((T("Routing « %s » supprimé") % name, OK) if res.get("ok") else (T("Suppression impossible"), WARN)))
        self.rebuild(True)

    def say_pair(self, pair):
        self.say(*pair)

    # -- consoles --------------------------------------------------------------
    def _fill_consoles(self, v):
        app, b = self.app, self.app.backend
        cards = app._lv1_cards or []
        labels = [T("(automatique / non choisie)")] + ["%d - %s" % (c["slot"], c["name"]) for c in cards]
        slots = [None] + [c["slot"] for c in cards]
        for c in app._consoles or []:
            f = row_frame()
            g = QVBoxLayout(f)
            g.setContentsMargins(10, 6, 6, 8)
            top = QHBoxLayout()
            dot = OK if c.get("connected") else (AMBER if c.get("trying") else "#555555")
            d = QLabel("●")
            d.setStyleSheet("color: %s; font: 12pt 'Segoe UI';" % dot)
            top.addWidget(d)
            top.addWidget(label(T("Console %d — %s (%s)") % (c["n"] + 1, c.get("name") or "?", c.get("ip") or "—"),
                                prop="name"), 1)
            if c["n"] > 0:
                top.addWidget(button(T("Retirer"), lambda _c=False, n=c["n"]: self._console_do(b.consoles_remove(n)),
                                     "warn"))
            g.addLayout(top)
            line = QHBoxLayout()
            line.addWidget(label(T("Carte LV1 :"), mut=True))
            cb = QComboBox()
            cb.addItems(labels)
            cur = c.get("card")
            cb.setCurrentIndex(slots.index(cur) if cur in slots else 0)
            cb.activated.connect(lambda i, n=c["n"]: self._console_do(b.consoles_card(n, slots[i])))
            line.addWidget(cb, 1)
            g.addLayout(line)
            v.addWidget(f)
        add = QHBoxLayout()
        ip = QLineEdit()
        ip.setPlaceholderText(T("Adresse IP d'une autre console"))
        ip.returnPressed.connect(lambda: self._console_do(b.consoles_add(ip.text().strip())))
        add.addWidget(ip, 1)
        add.addWidget(button(T("Ajouter"), lambda: self._console_do(b.consoles_add(ip.text().strip())), "ok"))
        v.addLayout(add)
        self._found = QVBoxLayout()
        v.addLayout(self._found)
        v.addWidget(button(T("Scanner le réseau"), self._scan_more))
        v.addWidget(label(T("Chaque console règle les préamplis de SA carte (position dans le rack de la LV1, le « 2- » "
                          "de « 2-EX 1 »). Carte choisie automatiquement si son nom dans la LV1 reprend celui de la "
                          "console."), mut=True))

    def _console_do(self, r):
        if r is not None and not r.get("ok"):
            self.say(r.get("error") or T("Impossible"), WARN)
        QTimer.singleShot(400, lambda: self.rebuild(True))

    def _scan_more(self):
        self.say(T("Recherche…"))
        QTimer.singleShot(30, self._scan_more_now)

    def _scan_more_now(self):
        app = self.app
        known = {c.get("ip") for c in app._consoles or []}
        res = [c for c in (app.backend.scan() or []) if c.get("ip") not in known]
        while self._found.count():
            w = self._found.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not res:
            self.say(T("Aucune autre console trouvée sur le réseau."))
            return
        self.say("")
        for c in res:
            f = row_frame()
            h = QHBoxLayout(f)
            h.setContentsMargins(10, 4, 6, 4)
            h.addWidget(label("%s (%s) %s" % (c.get("name", "?"), c["ip"], c.get("model", ""))), 1)
            h.addWidget(button(T("Ajouter"), lambda _c=False, ip=c["ip"]: self._console_do(app.backend.consoles_add(ip)),
                               "ok"))
            self._found.addWidget(f)

    # -- connexion à la console (ancienne barre de connexion) ---------------------
    def _fill_console(self, v):
        app = self.app
        row = QHBoxLayout()
        self.ip = QLineEdit(app.ip_text)
        self.ip.setPlaceholderText(T("Adresse IP de la console"))
        self.ip.returnPressed.connect(self.connect)
        row.addWidget(self.ip, 1)
        row.addWidget(button(T("Connecter"), self.connect, "blue"))
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(button(T("Scanner"), self.scan))
        row2.addWidget(button(T("Démo"), self.demo, "amber"))
        row2.addStretch(1)
        v.addLayout(row2)
        self._scan_rows = QVBoxLayout()
        v.addLayout(self._scan_rows)
        snap = app.link.snap or {}
        if not app.backend.reachable and not app.args.direct:
            self.say(T("Appli principale non trouvée sur le port %d") % app.args.port, WARN)
        elif not snap.get("connected") and not snap.get("trying") and not self.status.text():
            self.say(T("Non connecté à la console"))

    def connect(self):
        ip = self.ip.text().strip()
        if not ip:
            self.say(T("Entrez une IP"), WARN)
            return
        self.app.ip_text = ip
        self.say(T("Connexion…"))
        r = self.app.backend.connect(ip)
        if not r.get("ok"):
            self.say(r.get("error") or T("Échec"), WARN)

    def demo(self):
        r = self.app.backend.demo()
        if r.get("ok"):
            self.ip.setText("127.0.0.1")
            self.say(T("Démo (simulateur)"), OK)
        else:
            self.say(r.get("error") or T("Échec"), WARN)

    def scan(self):
        self.say(T("Recherche…"))
        QTimer.singleShot(30, self._scan_now)

    def _scan_now(self):
        found = self.app.backend.scan()
        while self._scan_rows.count():
            w = self._scan_rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not found:
            self.say(T("Rien trouvé — IP manuelle"), WARN)
            return
        self.ip.setText(found[0]["ip"])
        self.say(T("%d console(s) trouvée(s)") % len(found), OK)
        for c in found:
            f = row_frame()
            h = QHBoxLayout(f)
            h.setContentsMargins(10, 4, 6, 4)
            h.addWidget(label("%s — %s (%s)" % (c["ip"], c.get("name", "?"), c.get("model", "?"))), 1)
            h.addWidget(button(T("Choisir"), lambda _c=False, ip=c["ip"]: (self.ip.setText(ip), self.connect()), "blue"))
            self._scan_rows.addWidget(f)


# --------------------------------------------------------------------------
#  Éditeur de routing : matrice (lignes = sources ou sorties, colonnes = EXP 1-32) ou listes
# --------------------------------------------------------------------------
class MatrixHeader(QWidget):
    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.setFixedHeight(MatrixView.HEAD)
        self.setFixedWidth(MatrixView.LW + 32 * MatrixView.C + 4)

    def paintEvent(self, _e):
        ed, C, LW, H = self.ed, MatrixView.C, MatrixView.LW, MatrixView.HEAD
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(tc("#15171a")))
        aim = ed.mx.aim
        if aim:
            p.fillRect(QRectF(LW + (aim[1] - 1) * C, 0, C, H), QColor("#24414d"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(MUT))
        p.drawText(QRectF(4, 0, LW, H), Qt.AlignVCenter | Qt.AlignLeft, "EXP →")
        for c in range(1, 33):
            chg = ed.model["in"][c - 1] != ed.orig["in"][c - 1]
            p.setPen(QColor(AMBER if chg else MUT))
            p.drawText(QRectF(LW + (c - 1) * C, 0, C, H), Qt.AlignCenter, str(c))
        p.end()


class MatrixView(QWidget):
    """Matrice (2.4.0, demande de Joseph) : aide à la visée (ligne + colonne surlignées, texte « A 18 → EXP 2 ») ;
    doigt posé = visée (on peut glisser), la case est routée AU RELÂCHER ; recliquer coupe."""

    C, LW, HEAD = 24, 140, 22

    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.aim = None                  # (rang de section, colonne, ligne)
        self.down = None
        self.sections = []
        self.setMouseTracking(True)
        self.relayout()

    def rows(self, kind):
        ed = self.ed
        if kind == "out":
            return list(enumerate(ed.slots))
        used = set(ed.model["in"])
        return [(v, t) for v, t in ed.choices["in"]
                if v and (ed.show_all.isChecked() or v <= 64 or 80 < v <= 112 or v in used)]

    def relayout(self):
        C, H = self.C, self.HEAD
        y, self.sections = 4, []
        for kind, title in (("in", T("ENTRÉES → LV1 : une case par EXP (colonne)")),
                            ("out", T("SORTIES ← RETOURS LV1 : une case par sortie (ligne)"))):
            rows = self.rows(kind)
            y += 20
            head = y
            y += H
            top = y
            y += C * len(rows)
            self.sections.append((kind, title, rows, head, top, y))
            y += 14
        self.setFixedSize(self.LW + 32 * C + 4, y)
        self.update()

    def is_on(self, kind, key, c):
        m = self.ed.model
        return m["in"][c - 1] == key if kind == "in" else m["out"][key] == 128 + c

    def paintEvent(self, _e):
        ed, C, LW, H = self.ed, self.C, self.LW, self.HEAD
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b0c0d"))
        f_small, f_bold = QFont("Segoe UI", 8), QFont("Segoe UI", 8, QFont.Bold)
        for si, (kind, title, rows, head, top, bottom) in enumerate(self.sections):
            p.setFont(f_bold)
            p.setPen(QColor(MUT))
            p.drawText(QRectF(4, head - 20, 600, 20), Qt.AlignVCenter | Qt.AlignLeft, title)
            if self.aim and self.aim[0] == si:
                r, c = self.aim[2], self.aim[1]
                band = QColor("#1d2a30")
                p.fillRect(QRectF(0, top + r * C, LW + 32 * C, C), band)
                p.fillRect(QRectF(LW + (c - 1) * C, head, C, bottom - head), band)
            for c in range(1, 33):
                chg = kind == "in" and ed.model["in"][c - 1] != ed.orig["in"][c - 1]
                p.setPen(QColor(AMBER if chg else MUT))
                p.drawText(QRectF(LW + (c - 1) * C, head, C, H), Qt.AlignCenter, str(c))
            for r, (key, lab) in enumerate(rows):
                y = top + r * C
                chg = kind == "out" and ed.model["out"][key] != ed.orig["out"][key]
                val = ed.model["out"][key] if kind == "out" else 0
                if kind == "out" and val and not 128 < val <= 160:
                    lab = "%s (%s)" % (lab, ed.lab["out"].get(val, "?"))
                p.setFont(f_small)
                p.setPen(QColor(AMBER if chg else TXT))
                p.drawText(QRectF(4, y, LW - 6, C), Qt.AlignVCenter | Qt.AlignLeft, lab)
                p.setPen(QPen(QColor("#23262a"), 1))
                for c in range(1, 33):
                    x0 = LW + (c - 1) * C
                    p.setBrush(Qt.NoBrush)
                    p.drawRect(QRectF(x0, y, C, C))
                    if self.is_on(kind, key, c):
                        p.setPen(Qt.NoPen)
                        p.setBrush(QColor(CYAN))
                        p.drawRoundedRect(QRectF(x0 + 4, y + 4, C - 8, C - 8), 3, 3)
                        p.setPen(QPen(QColor("#23262a"), 1))
            if self.aim and self.aim[0] == si:
                r, c = self.aim[2], self.aim[1]
                p.setPen(QPen(QColor(AMBER), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRect(QRectF(LW + (c - 1) * C + 1, top + r * C + 1, C - 2, C - 2))
        p.end()

    def cell(self, pos):
        c = int((pos.x() - self.LW) // self.C) + 1
        for si, (kind, title, rows, head, top, bottom) in enumerate(self.sections):
            if top <= pos.y() < bottom and 1 <= c <= 32:
                return si, c, int((pos.y() - top) // self.C)
        return None

    def set_aim(self, hit):
        self.aim = hit
        ed = self.ed
        if hit:
            si, c, r = hit
            kind, rows = self.sections[si][0], self.sections[si][2]
            key, lab = rows[r]
            if kind == "in":
                cur = ed.lab["in"].get(ed.model["in"][c - 1], "OFF")
                ed.info.setText(T("%s → EXP %d     (EXP %d reçoit aujourd'hui : %s)") % (lab, c, c, cur))
            else:
                cur = ed.lab["out"].get(ed.model["out"][key], "OFF")
                ed.info.setText(T("EXP %d → %s     (%s reçoit aujourd'hui : %s)") % (c, lab, lab, cur))
        else:
            ed.info.setText(" ")
        self.update()
        ed.header.update()

    def mouseMoveEvent(self, e):
        self.set_aim(self.cell(e.position()))

    def mousePressEvent(self, e):
        hit = self.cell(e.position())
        self.set_aim(hit)
        self.down = hit[0] if hit else None

    def mouseReleaseEvent(self, e):
        hit = self.cell(e.position())
        if not hit or hit[0] != self.down:
            return
        si, c, r = hit
        kind, rows = self.sections[si][0], self.sections[si][2]
        key = rows[r][0]
        m = self.ed.model
        if kind == "in":
            m["in"][c - 1] = 0 if m["in"][c - 1] == key else key
        else:
            m["out"][key] = 0 if m["out"][key] == 128 + c else 128 + c
        self.relayout()
        self.set_aim(hit)

    def leaveEvent(self, _e):
        self.set_aim(None)


class RoutingEditor(QWidget):
    """Éditeur libre (2.4.0) : source de chaque EXP 1-32, retour de chaque sortie (X32 OUT, AES50 A/B)."""

    def __init__(self, app, src, r, choices, slots):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setWindowTitle(T("Éditeur de routing — %s") % qf.APP_SHORT)
        self.setStyleSheet(css() + "RoutingEditor { background: %s; }" % tc(PANEL))
        self.setAttribute(Qt.WA_StyledBackground)
        self.model = {"in": list(r["model"]["in"]), "out": list(r["model"]["out"])}
        self.orig = {"in": list(self.model["in"]), "out": list(self.model["out"])}
        self.pid = src.get("id") if r.get("editable") else None
        name0 = r["name"] if r.get("editable") else (T("Routing perso") if src.get("console") else r["name"] + T(" (perso)"))
        self.choices, self.slots = choices, slots or ["Sortie %d" % (i + 1) for i in range(48)]
        self.lab = {k: {v: t for v, t in choices[k]} for k in ("in", "out")}
        self.val = {k: {t: v for v, t in choices[k]} for k in ("in", "out")}
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        top.addWidget(label(T("Nom"), mut=True))
        self.name = QLineEdit(name0)
        top.addWidget(self.name, 1)
        v.addLayout(top)
        tabs = QHBoxLayout()
        self.tab_btns = {}
        for text, key in ((T("Matrice"), "mx"), (T("Listes"), "list")):
            b = button(text, lambda _c=False, k=key: self.show_view(k), "tab")
            tabs.addWidget(b)
            self.tab_btns[key] = b
        tabs.addStretch(1)
        v.addLayout(tabs)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        # matrice
        mxw = QWidget()
        mv = QVBoxLayout(mxw)
        mv.setContentsMargins(0, 0, 0, 0)
        self.info = QLabel(" ")
        self.info.setStyleSheet("color: %s; font: bold 10pt 'Segoe UI';" % AMBER)
        mv.addWidget(self.info)
        self.show_all = QCheckBox(T("Toutes les sources (+ AES50 33-48, Aux, Talkback)"))
        self.show_all.toggled.connect(lambda _on: self.mx.relayout())
        mv.addWidget(self.show_all)
        self.mx = MatrixView(self)
        self.header = MatrixHeader(self)
        mv.addWidget(self.header)
        sa = QScrollArea()
        sa.setWidget(self.mx)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setFixedWidth(self.mx.width() + 18)
        mv.addWidget(sa, 1)
        self.stack.addWidget(mxw)
        # listes
        lw = QWidget()
        grid = QGridLayout(lw)
        grid.addWidget(label(T("ENTRÉES → LV1"), mut=True), 0, 0, 1, 2)
        grid.addWidget(label(T("SORTIES ← RETOURS LV1"), mut=True), 0, 2, 1, 2)
        self.combos = []
        for col, kind, names in ((0, "in", ["EXP %d" % (i + 1) for i in range(32)]), (2, "out", self.slots)):
            for i, text in enumerate(names):
                grid.addWidget(label(text), i + 1, col)
                cb = QComboBox()
                cb.addItems([t for _v, t in choices[kind]])
                cb.activated.connect(lambda _i, cb=cb, kind=kind, i=i: self.model[kind].__setitem__(
                    i, self.val[kind].get(cb.currentText(), 0)))
                grid.addWidget(cb, i + 1, col + 1)
                self.combos.append((cb, kind, i))
        ls = QScrollArea()
        ls.setWidget(lw)
        ls.setWidgetResizable(True)
        ls.setFrameShape(QFrame.NoFrame)
        touch_scroll(ls)
        self.stack.addWidget(ls)
        v.addWidget(label(T("X32R : seules OUT 1-8 sont physiques. S16 : voies 1-8 ou 9-16 selon son sélecteur de "
                          "sorties (même retour sur les deux = marche dans les deux positions). L'enregistrement ne "
                          "touche pas la console : « Charger » ensuite."), mut=True))
        bar = QHBoxLayout()
        bar.addWidget(button(T("Enregistrer") if self.pid else T("Enregistrer comme nouveau profil"),
                             lambda: self.save(False), "ok"))
        if self.pid:
            bar.addWidget(button(T("Enregistrer sous…"), lambda: self.save(True)))
        bar.addStretch(1)
        bar.addWidget(button(T("Fermer"), self.close))
        v.addLayout(bar)
        self.show_view(app.cfg.get("routing_view", "mx"))
        self.resize(self.mx.width() + 60, 720)

    def show_view(self, key):
        self.app.cfg["routing_view"] = key
        for k, b in self.tab_btns.items():
            b.setProperty("kind", "tabon" if k == key else "tab")
            b.style().unpolish(b)
            b.style().polish(b)
        if key == "mx":
            self.mx.relayout()
            self.header.update()
            self.stack.setCurrentIndex(0)
        else:
            for cb, kind, i in self.combos:
                cb.setCurrentText(self.lab[kind].get(self.model[kind][i], "OFF"))
            self.stack.setCurrentIndex(1)

    def save(self, as_new):
        res = self.app.backend.save_routing(None if as_new else self.pid, self.name.text().strip(), self.model)
        if not res.get("ok"):
            Dialog(self.app, "Routing", res.get("error") or T("Échec"), T("OK")).ask()
            return
        self.orig = {"in": list(self.model["in"]), "out": list(self.model["out"])}
        self.close()
        pn = self.app.panel
        pn.say(T("Routing « %s » enregistré") % res.get("name"), OK)
        if pn.mode == "routing":
            pn.rebuild(True)

    def closeEvent(self, e):
        if self.model != self.orig and not Dialog(self.app, "Routing", T("Fermer sans enregistrer ?"), T("Fermer"),
                                                   danger=True).ask():
            e.ignore()
            return
        e.accept()
