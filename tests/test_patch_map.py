"""Test : PATCH MAP (3.1, demande de Joseph du 20/10/2026) — EXP -> source X32 -> canal X32 -> canal LV1.
- données relevées chez Joseph (exp_map : AES50-A 1-15 -> EXP 1-15, Local 1-16 -> EXP 17-32 ; In 1 « P170 ST » sur
  EXP 1 + 2, FireRoom sur EXP 15 + 16) : sources, côtés L / R, canal non patché, EXP 16 sans préampli ;
- plusieurs consoles : EXP 2·5 (1005) de la console 2 ;
- panneau Qt : lignes affichées, recherche « a12 » / « fireroom » / introuvable.

    py tests/test_patch_map.py
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import x32_gain_float as xf

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


exp_map = {str(32 + k): k + 1 for k in range(15)}               # AES50-A 1..15 -> EXP 1..15
exp_map.update({str(k): 17 + k for k in range(16)})             # Local 1..16 -> EXP 17..32
lv1_sources = {"1": [1, 2], "2": [3], "7": [11], "63": [15, 16]}
lv1_channels = {"1": {"label": "P170 ST", "color": "#FF4F4F"}, "2": {"label": "In 2", "color": "#0FA2AB"},
                "7": {"label": "In 7"}, "63": {"label": "FireRoom", "color": "#FF8800"}}
names = [None] * 128
names[32] = "Kick"                                              # canal X32 alimenté par AES50-A 1

rows = {r["exp"]: r for r in xf.patch_map_rows(exp_map, lv1_sources, lv1_channels, names)}
check("32 lignes pour la console 1", sorted(rows) == list(range(1, 33)))
check("EXP 1 = AES50-A 1, canal X32 Kick, P170 ST L", rows[1]["src_long"] == "AES50-A 1" and rows[1]["src_short"] == "A1"
      and rows[1]["x32"] == "Kick" and rows[1]["lv1"] == [(1, "L", "P170 ST", "#FF4F4F")])
check("EXP 2 = P170 ST R", rows[2]["lv1"] == [(1, "R", "P170 ST", "#FF4F4F")])
check("EXP 11 = A11 -> In 7 (mono, sans côté)", rows[11]["src_short"] == "A11" and rows[11]["lv1"] == [(7, "", "In 7", None)])
check("EXP 12 non patché", rows[12]["lv1"] == [])
check("EXP 16 : pas de préampli, FireRoom R", rows[16]["src"] is None and rows[16]["lv1"][0][1:3] == ("R", "FireRoom"))
check("EXP 17 = Local 1", rows[17]["src_long"] == "Local 1" and rows[17]["src_short"] == "L1")

r2 = {r["exp"]: r for r in xf.patch_map_rows({"164": 1005}, {"40": [1005]}, {"40": {"label": "Bass"}})}
check("console 2 : EXP 2·5 = 2·AES50-A 5 -> Bass", r2[1005]["exp_txt"] == "2·5" and r2[1005]["src_long"] == "2·AES50-A 5"
      and r2[1005]["lv1"][0][2] == "Bass")

# ── panneau Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QLabel
app_qt = QApplication([])
import x32_qt_panels as qp


class Fake:
    snap = {"names": names}
    win, patch_btn, show_btn = qp.QWidget(), qp.QWidget(), qp.QWidget()
    exp_map = {int(k): v for k, v in exp_map.items()}
    lv1_sources = {int(k): v for k, v in lv1_sources.items()}
    lv1_channels = lv1_channels
    def sync_panel(self): pass


fake = Fake()
pn = qp.Panel(fake)
pn.mode = "patchmap"
pn.title.setText("PATCH MAP")
content_v = qp.QVBoxLayout()
holder = qp.QWidget()
holder.setLayout(content_v)
pn._fill_patchmap(content_v)
holder.resize(600, 900)
holder.show()
find = holder.findChild(QLineEdit)
vis = lambda: [l.text() for l in holder.findChildren(QLabel) if l.isVisible() and l.text().startswith("EXP ")]
check("32 lignes affichées", len(vis()) == 32)
find.setText("a12")
check("recherche « a12 » -> EXP 12", vis() == ["EXP 12"])
find.setText("FireRoom")
check("recherche « FireRoom » -> EXP 15 et 16", vis() == ["EXP 15", "EXP 16"])
find.setText("zzz")
check("introuvable -> aucune ligne", vis() == [])
if "--image" in sys.argv:                       # rendu dans le vrai panneau (style, largeur, titre)
    fake.win.setGeometry(0, 0, 600, 100)
    pn2 = qp.Panel(fake)
    pn2.open("patchmap")
    pn2.grab().save(sys.argv[sys.argv.index("--image") + 1])

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
