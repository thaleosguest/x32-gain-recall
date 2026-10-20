"""lv1/colorclick.py — Couleurs des canaux LV1 par CLICS dans la fenêtre « Select a Color » (3.1, STAGE PATCH).

La LV1 V17 refuse la couleur à distance (OSC `/Set/TrackColor` -> `SetTrackColor` = `return 6`, voir lv1/remote.py).
Idée de Joseph (20/10/2026) : page Patch -> vue Input A, un clic sur la bande de couleur d'un canal ouvre la fenêtre
« Select a Color from the Pallete Below » ; ‹ › y passent au canal précédent / suivant SANS la fermer, et une couleur
touchée s'applique TOUT DE SUITE (vérifié par Joseph). Donc : ouvrir la fenêtre sur In 1, puis › … couleur … › …

Géométrie relevée sur sa capture plein écran (LV1 1920x1080, 20/10/2026), en fractions de la zone client :
  bouton Input A (actif = bleu (56,201,255)) ; 1re ligne de la liste (In 1) : bande x 126..157, y 357..362, lignes
  au pas de 7 px ; fenêtre x 708..1197, y 270..754, fond (54,54,54) ; palette 4 x 8 (même ordre que
  lv1/channelinfo.PALETTE), cases 98x28 au pas 101x31, 1re case centrée (802, 360) ; champ du nom x 816..990,
  y 625..651, FOND = couleur du canal affiché ; ‹ (1022, 638), › (1070, 638), OK (1120, 716).

Clics : messages WM_LBUTTON* postés à la fenêtre enfant sous le point (souris immobile), comme XTouch-LV1
(lv1_clic.LV1Clicker.click), dans la fenêtre de la LV1 la plus en avant à cet endroit : « Color Picker » est une
fenêtre À PART (1er essai chez Joseph : fenêtre ouverte sur In 1, puis clics de palette perdus dans la fenêtre
principale, arrêt « changement pas vu » — garde-fou OK, rien de modifié). La LV1 tourne en administrateur : l'appli doit l'être aussi (exe --uac-admin, 3.1),
sinon Windows (UIPI) ignore les messages.

Garde-fous (rien n'est cliqué à l'aveugle) : page Patch / Input A lue à l'écran ; 1re ligne de la liste = couleur
d'In 1 (liste remontée, zoom normal) ; fenêtre couleur reconnue par 6 cases de sa palette ; avant chaque couleur,
FOND du champ du nom = couleur actuelle du canal visé ; après, le changement doit être vu sur CE canal (OSC
/Notify/TrackColor ou base de la LV1) ; un autre canal touché -> remis à sa couleur et arrêt.
"""
import time

from .channelinfo import PALETTE

REF_W, REF_H = 1920.0, 1080.0
INPUT_A = (60, 282)
ROW1 = (141, 360)
ROW_PITCH = 7
DLG_BG = (730, 600)
CELL0, CELL_DX, CELL_DY = (802, 360), 101, 31
FIELD = (819, 638)
PREV, NEXT, OK = (1022, 638), (1070, 638), (1120, 716)
BLUE = (56, 201, 255)
DIALOG_BG = (54, 54, 54)
CHECK_CELLS = (0, 3, 13, 18, 28, 31)
STEP_S = 0.045          # entre deux clics ‹ › (la LV1 réagit en ~50 ms, file de messages dans l'ordre)
SETTLE_S = 0.15         # après une suite de ‹ › ou un clic de couleur, avant de relire l'écran


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def close(a, b, tol=12):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def cell(i):
    return (CELL0[0] + (i % 4) * CELL_DX, CELL0[1] + (i // 4) * CELL_DY)


class JobError(Exception):
    pass


class ColorJob:
    """Applique {canal: n° de palette} dans la LV1. `io` fournit :
         read(points)          -> [(r, g, b) | None] aux points (coordonnées de référence 1920x1080) ;
         click(point)          -> clic à ce point ;
         changes(since)        -> [(canal, n° de palette, t)] vus depuis `since` (OSC ou base de la LV1) ;
         stopped()             -> True si l'utilisateur a demandé l'arrêt ;
         log(texte).
    `colors` = couleur actuelle de chaque canal (n° de palette, d'après la LV1), mise à jour au fil de l'eau."""

    def __init__(self, targets, colors, io, wait=3.0):
        self.targets = {int(k): int(v) for k, v in targets.items()}
        self.colors = {int(k): v for k, v in colors.items()}
        self.io = io
        self.wait = wait
        self.done = []
        self.pos = None
        self.dialog_open = False
        self.last_field = None

    # -- lecture ------------------------------------------------------------
    def _read(self, pts):
        return self.io.read(list(pts))

    def dialog_visible(self):
        pts = [DLG_BG] + [cell(i) for i in CHECK_CELLS]
        got = self._read(pts)
        return close(got[0], DIALOG_BG, 6) and all(close(g, hex_rgb(PALETTE[i])) for g, i in zip(got[1:], CHECK_CELLS))

    def field_is(self, idx, timeout=0.8):
        """Fond du champ du nom = couleur n° idx ? Relu jusqu'à `timeout` (fenêtre pas encore dessinée, aperçu au
        survol de la souris : 2e essai chez Joseph, arrêt « pas In 1 » juste après l'ouverture). Garde la dernière
        lecture dans self.last_field (message d'erreur)."""
        end = time.time() + timeout
        while True:
            self.last_field = self._read([FIELD])[0]
            if close(self.last_field, hex_rgb(PALETTE[idx])):
                return True
            if time.time() > end:
                return False
            self._sleep(0.05)

    def _field_why(self, idx):
        return "champ %s, attendu n° %d %s" % (self.last_field, idx, hex_rgb(PALETTE[idx]))

    def _cur(self, ch):
        c = self.colors.get(ch)
        return 13 if c is None else c          # pas de couleur connue = couleur par défaut de la LV1 (n° 13)

    # -- étapes ---------------------------------------------------------------
    def _sleep(self, s):
        end = time.time() + s
        while time.time() < end:
            if self.io.stopped():
                raise JobError("arrêté")
            time.sleep(min(0.02, max(0.0, end - time.time())))

    def open_dialog(self):
        if not close(self._read([INPUT_A])[0], BLUE):
            self.io.click(INPUT_A)                        # vue Input A
            self._sleep(0.35)
            if not close(self._read([INPUT_A])[0], BLUE):
                raise JobError("page Patch, vue Input : bouton Input A introuvable")
        if not close(self._read([ROW1])[0], hex_rgb(PALETTE[self._cur(1)])):
            raise JobError("liste du patch : la 1re ligne n'est pas In 1 (remontez la liste, zoom normal)")
        self.io.click(ROW1)
        t_end = time.time() + 1.5
        while not self.dialog_visible():
            if time.time() > t_end:
                raise JobError("la fenêtre « Select a Color » ne s'est pas ouverte")
            self._sleep(0.05)
        self.dialog_open = True
        if not self.field_is(self._cur(1)):
            raise JobError("fenêtre couleur : le canal affiché n'est pas In 1 (%s)" % self._field_why(self._cur(1)))
        self.pos = 1

    def move_to(self, ch):
        n = ch - self.pos
        btn = NEXT if n > 0 else PREV
        for _ in range(abs(n)):
            self.io.click(btn)
            self._sleep(STEP_S)
        self.pos = ch
        self._sleep(SETTLE_S)
        if not self.dialog_visible():
            raise JobError("fenêtre couleur fermée")
        if not self.field_is(self._cur(ch)):
            raise JobError("fenêtre couleur : le canal affiché ne semble pas être In %d (%s)"
                           % (ch, self._field_why(self._cur(ch))))

    def set_color(self, ch, idx):
        t0 = time.time()
        self.io.click(cell(idx))
        t_end = t0 + self.wait
        while time.time() < t_end:
            self._sleep(0.05)
            for c, i, _t in self.io.changes(t0):
                if c == ch and i == idx:
                    self.colors[ch] = idx
                    return
                if c != ch:
                    # mauvais canal : on lui remet sa couleur (la fenêtre est sur lui) et on s'arrête
                    old = self._cur(c)
                    self.io.click(cell(old))
                    self.io.log("In %d touché par erreur : remis en n° %d" % (c, old))
                    raise JobError("décalage : In %d touché au lieu d'In %d (remis comme avant)" % (c, ch))
        raise JobError("In %d : changement de couleur pas vu dans la LV1" % ch)

    def run(self):
        """Rend (canaux faits, erreur ou None). La fenêtre couleur est refermée par OK à la fin (sauf si elle n'a pas
        pu être reconnue)."""
        todo = sorted(ch for ch, idx in self.targets.items() if self._cur(ch) != idx)
        err = None
        try:
            if todo:
                self.open_dialog()
                for ch in todo:
                    if self.io.stopped():
                        raise JobError("arrêté")
                    self.move_to(ch)
                    self.set_color(ch, self.targets[ch])
                    self.done.append(ch)
                    self.io.log("In %d -> n° %d" % (ch, self.targets[ch]))
        except JobError as e:
            err = str(e)
        finally:
            if self.dialog_open and self.dialog_visible():
                self.io.click(OK)
        return self.done, err


# --------------------------------------------------------------------------
#  Clic posté à la LV1 (souris immobile) — méthode de XTouch-LV1
# --------------------------------------------------------------------------
_U32 = None


def _user32():
    global _U32
    if _U32 is None:
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32", use_last_error=True)
        vp = ctypes.c_void_p
        u.ChildWindowFromPointEx.argtypes = [vp, wt.POINT, ctypes.c_uint]
        u.ChildWindowFromPointEx.restype = vp
        u.ScreenToClient.argtypes = [vp, ctypes.POINTER(wt.POINT)]
        u.ClientToScreen.argtypes = [vp, ctypes.POINTER(wt.POINT)]
        u.PostMessageW.argtypes = [vp, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        u.PostMessageW.restype = wt.BOOL
        u.GetWindowThreadProcessId.argtypes = [vp, ctypes.POINTER(wt.DWORD)]
        u.GetWindowRect.argtypes = [vp, ctypes.POINTER(wt.RECT)]
        u.IsWindowVisible.argtypes = [vp]
        u.IsIconic.argtypes = [vp]
        u.EnumWindows.argtypes = [vp, vp]
        _U32 = u
    return _U32


def lv1_window_at(hwnd, sx, sy):
    """Fenêtre de premier niveau de la LV1 (même processus que `hwnd`) la plus en avant qui contient le point écran :
    la fenêtre « Color Picker » est une fenêtre À PART (relevé le 20/10/2026 : titre « Color Picker », classe
    Qt624QWindow, x 708..1212 y 270..769), pas un enfant de la fenêtre principale. None si aucune (jamais une autre
    appli : on énumère les fenêtres de la LV1, de la plus en avant à la plus en arrière)."""
    import ctypes
    from ctypes import wintypes as wt
    u = _user32()
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _l):
        p = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid.value and u.IsWindowVisible(h) and not u.IsIconic(h):
            r = wt.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.left <= sx < r.right and r.top <= sy < r.bottom:
                found.append(h)
                return False
        return True
    u.EnumWindows(cb, None)
    return found[0] if found else None


def post_click(hwnd, sx, sy, hold=0.03):
    """Clic gauche au point écran (sx, sy) : WM_MOUSEMOVE / WM_LBUTTONDOWN / WM_LBUTTONUP postés à la fenêtre enfant
    la plus profonde sous le point, dans la fenêtre de la LV1 la plus en avant à cet endroit (lv1_window_at). Rend
    False si aucune fenêtre de la LV1 n'est sous le point ou si Windows refuse le message (appli pas en admin)."""
    import ctypes
    from ctypes import wintypes as wt
    u = _user32()
    top = lv1_window_at(hwnd, sx, sy)
    if not top:
        return False
    h, p = top, wt.POINT(int(sx), int(sy))
    u.ScreenToClient(h, ctypes.byref(p))
    while True:
        child = u.ChildWindowFromPointEx(h, p, 0x0001 | 0x0004)     # CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT
        if not child or child == h:
            break
        sp = wt.POINT(p.x, p.y)
        u.ClientToScreen(h, ctypes.byref(sp))
        u.ScreenToClient(child, ctypes.byref(sp))
        h, p = child, sp
    lp = (p.y & 0xFFFF) << 16 | (p.x & 0xFFFF)
    ok = u.PostMessageW(h, 0x0200, 0, lp) and u.PostMessageW(h, 0x0201, 0x0001, lp)
    time.sleep(hold)
    return bool(ok and u.PostMessageW(h, 0x0202, 0, lp))
