"""Test : PATCH DE SCÈNE (3.1, demande de Joseph du 20/10/2026) — prises physiques étiquetées -> EXP -> canal LV1.
- clés de prises <-> préamplis (Local / AES50-A / AES50-B, consoles 2…) ; appareils par défaut selon le modèle ;
- étiquettes par EXP avec le routing relevé chez Joseph (AES50-A 1-15 -> EXP 1-15, Local 1-16 -> EXP 17-32) ;
- renommage automatique : l'étiquette gagne quand le canal reçoit la source (même sur « test » tapé à la main, nom
  d'avant gardé) ou quand elle est modifiée ; nom retapé ensuite -> respecté ; canal stéréo -> nom de la voie gauche ;
  pas de renvoi pendant 5 s ; étiquette effacée (Clear) -> « Channel N » + n° 13 ; autre source sans étiquette -> nom
  d'avant / par défaut ; canal plus patché -> laissé ;
- feuilles (nouvelle, dupliquer, renommer, supprimer, activer) enregistrées et relues ; export / import d'une
  feuille (fichier bricolé : le valable gardé ; autre fichier : refusé) ;
- fenêtre STAGE PATCH : faces S16 + X32 Rack, PATCH MAP, saisie rapide au clavier (Entrée / ↑ / ↓, couleur au
  toucher), nom LV1 en pâle pour une prise sans étiquette (--image fichier.png : rendu).

    py tests/test_stage.py [--image stage.png]
"""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import x32_stage as xs

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


# ── prises <-> préamplis
check("A:in:1 = préampli 32", xs.port_preamp("A:in:1") == 32 and xs.port_preamp("local:in:16") == 15)
check("B:in:5 console 2 = 128 + 84", xs.port_preamp("B:in:5", 1) == 128 + 84)
check("sortie : pas de préampli", xs.port_preamp("A:out:7") is None)
check("aller-retour", all(xs.preamp_port(xs.port_preamp(k, c)) == (c, k)
                          for c in (0, 1) for k in ("local:in:1", "local:in:32", "A:in:1", "A:in:48", "B:in:9")))
check("repères", xs.port_tag("A:in:1") == "A1" and xs.port_tag("local:in:3", 1) == "2·L3" and
      xs.port_tag("A:out:7") == "A OUT 7")
check("défauts X32RACK", xs.default_devices("X32RACK") == {"local": "x32r", "A": "s16", "B": None})
check("défauts X32 / M32C", xs.default_devices("X32")["local"] == "x32" and xs.default_devices("X32")["A"] is None
      and xs.default_devices("M32C")["local"] == "m32c")
check("prises S16 : 16 entrées + 8 sorties", len(xs.DEVICES["s16"]["sockets"]) == 24)
check("prises X32 : 32 + 16", len(xs.DEVICES["x32"]["sockets"]) == 48)

# ── feuille du croquis de Joseph : S16 sur le port A
sheet = xs.new_sheet("Croquis")
c0 = xs.sheet_console(sheet, 0, "X32RACK")
for n, (name, col) in enumerate((("Kick", 18), ("Snare", 18), ("HH", 18), ("OV L", 18), ("OV R", 18), ("BASS", 14)), 1):
    c0["ports"]["A:in:%d" % n] = {"name": name, "color": col}
c0["ports"]["A:out:7"] = {"name": "Genelec", "color": 14}
c0["ports"]["local:in:1"] = {"name": "Piano L", "color": 6}
c0["ports"]["local:in:2"] = {"name": "Piano R", "color": 6}

exp_map = {32 + k: k + 1 for k in range(15)}              # AES50-A 1..15 -> EXP 1..15
exp_map.update({k: 17 + k for k in range(16)})             # Local 1..16 -> EXP 17..32
by_exp = xs.labels_by_exp(sheet, exp_map)
check("EXP 1 = Kick (A1)", by_exp[1][0]["name"] == "Kick" and by_exp[1][1] == "A:in:1")
check("EXP 17 = Piano L", by_exp[17][0]["name"] == "Piano L")
check("sortie absente des EXP", all(v[1] != "A:out:7" for v in by_exp.values()))

lv1_sources = {1: [1], 2: [2], 3: [3], 4: [4], 5: [5], 6: [6], 20: [17, 18], 9: [9]}
lv1_info = {1: {"name": "Channel 1", "color": "#0FA2AB"}, 2: {"name": "Channel 2"}, 3: {"name": "Charley"},
            4: {"name": ""}, 5: {"name": "Channel 5"}, 6: {"name": "Channel 6"}, 20: {"name": "Channel 20"},
            9: {"name": "Channel 9"}}
r = {x["ch"]: x for x in xs.lv1_renames(sheet, exp_map, lv1_sources, lv1_info, {}, now=1000)}
check("In 1 -> Kick + jaune", r[1]["name"] == "Kick" and r[1]["send_name"] and r[1]["color"] == 18
      and r[1]["send_color"] and r[1]["prev_color"] == 13 and r[1]["src"] == "0:A:in:1")
check("In 3 nommé à la main (Charley) : l'étiquette gagne, nom d'avant gardé",
      r[3]["name"] == "HH" and r[3]["send_name"] and r[3]["prev_name"] == "Charley")
check("OV en 2 mono : OV L / OV R", r[4]["name"] == "OV L" and r[5]["name"] == "OV R")
check("piano stéréo : nom de la voie gauche", r[20]["name"] == "Piano L" and r[20]["src"] == "0:local:in:1")
check("In 9 (EXP 9 sans étiquette) : rien", 9 not in r)
r_nc = xs.lv1_renames(sheet, exp_map, lv1_sources, lv1_info, {}, now=1000, with_color=False)
check("sans couleur : jamais de couleur", all(not x["send_color"] for x in r_nc))


def names(src, info, applied, now=1010):
    return {x["ch"]: x for x in xs.lv1_renames(sheet, exp_map, src, info, applied, now=now)}


# renommage envoyé il y a 2 s, base de la LV1 pas encore à jour : pas de renvoi
applied = {1: {"name": "Kick", "src": "0:A:in:1", "label": "Kick", "prev_name": None, "color": 18, "prev_color": 13,
               "t": 998}}
check("pas de renvoi avant 5 s", 1 not in names(lv1_sources, lv1_info, applied, now=1000))
check("base pas à jour après 5 s (nom par défaut) : renvoi", names(lv1_sources, lv1_info, applied)[1]["send_name"])
info2 = {**lv1_info, 1: {"name": "Kick", "color": "#F3FA1D"}}
check("à jour : rien", 1 not in names(lv1_sources, info2, applied))
# Joseph renomme In 1 dans la LV1 ensuite (même source, même étiquette) : respecté
info3 = {**lv1_info, 1: {"name": "Grosse caisse", "color": "#F3FA1D"}}
check("renommé à la main ensuite : respecté", 1 not in names(lv1_sources, info3, applied))
# ... mais l'étiquette modifiée dans STAGE PATCH gagne de nouveau
sheet["consoles"]["0"]["ports"]["A:in:1"] = {"name": "Kick In", "color": 18}
check("étiquette modifiée : elle gagne", names(lv1_sources, info3, applied)[1]["name"] == "Kick In")
sheet["consoles"]["0"]["ports"]["A:in:1"] = {"name": "Kick", "color": 18}
# scénario de Joseph : canal « test » sans source, EXP 4 attribué (prise A4 « OV L ») -> l'étiquette gagne
src_t = {**lv1_sources, 30: [4]}
info_t = {**lv1_info, 30: {"name": "test"}}
rt = names(src_t, info_t, {})[30]
check("canal « test » + EXP 4 : prend « OV L », « test » gardé", rt["name"] == "OV L" and rt["send_name"]
      and rt["prev_name"] == "test" and rt["src"] == "0:A:in:4")
app_t = {30: {"name": "OV L", "src": "0:A:in:4", "label": "OV L", "prev_name": "test", "color": None,
              "prev_color": 13, "t": 0}}
# source changée pour une prise étiquetée (A5 « OV R ») : l'étiquette gagne même sur un nom retapé
check("nouvelle source étiquetée : gagne même sur un nom retapé",
      names({**src_t, 30: [5]}, {**info_t, 30: {"name": "Overhead"}}, app_t)[30]["name"] == "OV R")
# source sans étiquette : le canal retrouve « test »
rb = names({**src_t, 30: [9]}, {**info_t, 30: {"name": "OV L"}}, app_t)[30]
check("source sans étiquette : nom d'avant (« test »)", rb["name"] == "test" and rb["why"] == "restore")
# Clear de la prise A4 qui alimente toujours In 4 : piste par défaut (« Channel 4 » + couleur n° 13)
import copy
sh_c = copy.deepcopy(sheet)
del sh_c["consoles"]["0"]["ports"]["A:in:4"]
app_4 = {4: {"name": "OV L", "src": "0:A:in:4", "label": "OV L", "prev_name": "Overhead", "color": 18,
             "prev_color": 13, "t": 0}}
info_4 = {**lv1_info, 4: {"name": "OV L", "color": "#F3FA1D"}}
r4 = {x["ch"]: x for x in xs.lv1_renames(sh_c, exp_map, lv1_sources, info_4, app_4, now=1010)}[4]
check("Clear : « Channel 4 » + n° 13 (pas le nom d'avant)", r4["why"] == "cleared" and r4["name"] == "Channel 4"
      and r4["color"] == 13 and r4["send_color"] and r4["src"] == "0:A:in:4")
mark = {4: {"name": "Channel 4", "src": "0:A:in:4", "label": None, "cleared": True, "color": 13, "t": 0}}
info_4b = {**lv1_info, 4: {"name": "Channel 4", "color": "#F3FA1D"}}
check("Clear : couleur par défaut à donner (bouton Couleurs)", xs.lv1_color_targets(sh_c, exp_map, lv1_sources,
                                                                                    info_4b, mark).get(4) == 13)
check("Clear puis renommé à la main : couleur laissée", 4 not in xs.lv1_color_targets(
    sh_c, exp_map, lv1_sources, {**lv1_info, 4: {"name": "Tom", "color": "#F3FA1D"}}, mark))
check("Clear, déjà n° 13 : rien", 4 not in xs.lv1_color_targets(
    sh_c, exp_map, lv1_sources, {**lv1_info, 4: {"name": "Channel 4", "color": "#0FA2AB"}}, mark))
check("Clear, puis nouvelle étiquette : c'est elle qui compte", xs.lv1_color_targets(
    sheet, exp_map, lv1_sources, info_4b, mark).get(4) != 13)
check("Clear : rien de plus au tour suivant", 4 not in {x["ch"] for x in xs.lv1_renames(
    sh_c, exp_map, lv1_sources, {**lv1_info, 4: {"name": "Channel 4", "color": "#0FA2AB"}}, mark, now=1020)})
# 1re fois vue, nom déjà bon : rien à envoyer, source seulement notée (pour respecter un renommage ultérieur)
r0 = names(lv1_sources, info2, {})[1]
check("déjà bon : rien envoyé, source notée", not r0["send_name"] and r0["src"] == "0:A:in:1" and r0["prev_name"] is None)
# In 1 repatché sur EXP 9 (pas d'étiquette) : nom par défaut + couleur d'avant
rr = names({**lv1_sources, 1: [9]}, info2, applied)
check("source sans étiquette, pas de nom d'avant : nom par défaut", rr[1]["name"] == "Channel 1"
      and rr[1]["why"] == "restore" and rr[1]["color"] == 13 and rr[1]["send_color"])
# In 1 plus patché du tout : laissé
check("canal plus patché : laissé", 1 not in names({k: v for k, v in lv1_sources.items() if k != 1}, info2, applied))
# console 2
sheet2 = xs.new_sheet("2")
xs.sheet_console(sheet2, 1, "X32RACK")["ports"]["A:in:3"] = {"name": "Sax", "color": None}
r2 = xs.lv1_renames(sheet2, {128 + 34: 1003}, {40: [1003]}, {40: {"name": "Channel 40"}}, {}, now=0)
check("console 2 : 2·A3 -> EXP 2·3 -> In 40 Sax", r2 and r2[0]["ch"] == 40 and r2[0]["name"] == "Sax")

# ── stockage
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "x32_stage_patch.json")
st = xs.StageStore(path)
check("1re feuille créée", len(st.sheets) == 1 and st.active == st.sheets[0]["id"])
st.set_port(0, "A:in:1", {"name": "  Kick  ", "color": 18}, "X32RACK")
st.set_port(0, "A:in:2", {"name": "Snare", "color": 99})
first = st.active
st.sheet_action("new", name="Studio")
check("nouvelle feuille : mêmes appareils, prises vides",
      st.current()["consoles"]["0"]["devices"]["A"] == "s16" and not st.current()["consoles"]["0"]["ports"])
st.sheet_action("activate", first)
st.sheet_action("duplicate", first, "Croquis bis")
st.set_device(0, "B", "s16")
try:
    st.set_device(0, "B", "m32c")
    check("M32C refusé sur un port AES50", False)
except ValueError:
    pass
st.mark_applied(1, {"name": "Kick", "color": 18, "prev_color": 13, "t": 1})
st2 = xs.StageStore(path)
cur = st2.current()
check("relu : 3 feuilles, copie active", len(st2.sheets) == 3 and cur["name"] == "Croquis bis")
check("relu : étiquette nettoyée, couleur hors palette ignorée",
      cur["consoles"]["0"]["ports"]["A:in:1"] == {"name": "Kick", "color": 18}
      and cur["consoles"]["0"]["ports"]["A:in:2"] == {"name": "Snare", "color": None})
check("relu : appliqué", st2.applied[1]["name"] == "Kick")
st2.set_port(0, "A:in:2", {"name": "", "color": None})
check("étiquette effacée", "A:in:2" not in st2.current()["consoles"]["0"]["ports"])
st2.sheet_action("delete", st2.active)
check("feuille supprimée", len(st2.sheets) == 2)
doc = st2.export_sheet()
check("export : type, nom, étiquettes, sans id", doc["type"] == xs.EXPORT_TYPE and "id" not in doc["sheet"]
      and doc["sheet"]["consoles"]["0"]["ports"]["A:in:1"]["name"] == "Kick")
n_before = len(st2.sheets)
imp = st2.import_sheet(doc)
check("import : nouvelle feuille active, nom libre « (2) »", len(st2.sheets) == n_before + 1 and st2.active == imp["id"]
      and imp["name"] == doc["sheet"]["name"] + " (2)" and imp["consoles"]["0"]["ports"]["A:in:1"]["name"] == "Kick")
bad = {"type": xs.EXPORT_TYPE, "sheet": {"name": "  Bricolé  ", "consoles": {
    "0": {"devices": {"local": "x32r", "A": "m32c", "B": "fusée"},
          "ports": {"A:in:1": {"name": "Voix", "color": 25}, "Z:in:1": {"name": "x"}, "A:in:2": {"name": "", "color": 99},
                    "A:out:7": {"name": "Genelec", "color": 14}}},
    "trois": {"ports": {}}}}}
imp2 = st2.import_sheet(bad)
c0 = imp2["consoles"]["0"]
check("import d'un fichier bricolé : le valable gardé, le reste ignoré", imp2["name"] == "Bricolé"
      and c0["devices"] == {"local": "x32r", "A": None, "B": None} and set(c0["ports"]) == {"A:in:1", "A:out:7"}
      and list(imp2["consoles"]) == ["0"])
for junk in (None, {"type": "autre"}, {"type": xs.EXPORT_TYPE, "sheet": "x"}):
    try:
        st2.import_sheet(junk)
        check("fichier qui n'est pas une feuille : refusé", False)
    except ValueError:
        pass
check("relu après import", xs.StageStore(path).current()["name"] == "Bricolé")

# ── fenêtre STAGE PATCH (PATCH MAP + faces)
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
app_qt = QApplication([])
import x32_qt_stage as qs
from lv1.channelinfo import display_name

store = xs.StageStore(os.path.join(tmp, "qt.json"))
store.sheets[0] = sheet
store.active = sheet["id"]


class Backend:
    def stage(self):
        d = store.state(["X32RACK"])
        d["lv1_remote"] = {"connected": True, "host": "127.0.0.1", "port": 51557}
        d["log"] = [{"ch": 1, "name": "Kick"}]
        return d

    def stage_post(self, what, d):
        if what == "port":
            store.set_port(d["console"], d["port"], d)
        elif what == "auto":
            store.set_auto(d["on"])
        elif what == "export":
            return {"ok": True, "doc": store.export_sheet(d.get("id"))}
        elif what == "import":
            try:
                store.import_sheet(d.get("doc"))
            except ValueError as e:
                return {"ok": False, "error": str(e)}
        return dict(self.stage(), ok=True)


lv1_ui = {k: dict(v) for k, v in lv1_info.items()}
lv1_ui[7] = {"name": "Tom", "color": "#8C51C0"}            # canal nommé dans la LV1, prise A7 sans étiquette
src_ui = dict(lv1_sources)
src_ui[7] = [7]


class Fake:
    backend = Backend()
    link = type("Link", (), {"snap": {"phantom": [0] * 32 + [1, 1] + [0] * 94}})()
    win = QWidget()
    stage_btn = None
    _consoles = [{"n": 0, "name": "X32RACK-JS", "connected": True}]
    exp_map = exp_map
    lv1_sources = src_ui
    lv1_channels = {str(k): {"label": display_name(k, v["name"]), "name": v["name"],
                             "color": "#F3FA1D" if k < 5 else v.get("color") or "#00E676"} for k, v in lv1_ui.items()}
    toast = type("Toast", (), {"said": [], "say": lambda self, *a, **k: self.said.append(a)})()
    cfg = {}
    def save_soon(self): pass
    def raise_now(self, w): pass
    def stage_lv1(self): return None


w = qs.StagePatch(Fake())
w.open(docked=False)
for _ in range(3):
    app_qt.processEvents()
w._size_faces()
app_qt.processEvents()
check("faces : console (X32 Rack) + port A (S16)", [f.dev_key for f in w.faces] == ["x32r", "s16"])
s16 = w.faces[1]
check("proportions de la S16", abs(s16.width() / s16.height() - 4.8) < 0.1)
check("prises cliquables : 24 sur la S16", len(s16._hit) == 24)
check("PATCH MAP : 32 lignes, 1re ligne choisie (EXP 1 = A1)", len(w.rows) == 32 and w.sel == (0, "A:in:1"))
chain = w.chain(0, "A:in:6")
check("chemin A6 -> EXP 6 -> In 6", chain["exp"] == 6 and chain["lv1"][0][0] == 6)
ports = w.ports(0)
check("couleur LV1 identique : pas de repère (Kick jaune / In 1 jaune, BASS vert / In 6 vert)",
      not w.color_differs(ports["A:in:1"], w.chain(0, "A:in:1")) and not w.color_differs(ports["A:in:6"], chain))
check("couleur LV1 différente : repère (OV R jaune / In 5 vert)", w.color_differs(ports["A:in:5"], w.chain(0, "A:in:5")))
check("48V sur A1", w.phantom_on(0, "A:in:1") and not w.phantom_on(0, "A:in:3"))
check("prise sans étiquette, canal LV1 « Tom » : rempli tout seul (pâle)",
      w.auto_label(w.chain(0, "A:in:7")) == ("Tom", "#8C51C0") and w.auto_label(w.chain(0, "A:in:9")) is None)
row7 = next(r for r in w.rows if r["exp"] == 7)
check("ligne EXP 7 : nom LV1 en pâle, pas d'étiquette", row7["auto"][0] == "Tom" and row7["label"] is None)
check("champ du nom à la couleur de l'étiquette (Kick jaune)", "#F3FA1D" in w.name.styleSheet())

# saisie rapide : nom, Entrée -> enregistré + ligne suivante ; couleur au toucher ; ↓ / ↑
w.name.setText("Grosse caisse")
QTest.keyClick(w.name, Qt.Key_Return)
check("Entrée : A1 enregistrée, A2 choisie", store.current()["consoles"]["0"]["ports"]["A:in:1"]["name"] == "Grosse caisse"
      and w.sel == (0, "A:in:2") and w.name.text() == "Snare")
w.name.setText("Caisse claire")
w.pick_color(7)
lab2 = store.current()["consoles"]["0"]["ports"]["A:in:2"]
check("couleur touchée : enregistrée avec le nom tapé", lab2 == {"name": "Caisse claire", "color": 7}
      and w.sel == (0, "A:in:2"))
QTest.keyClick(w.name, Qt.Key_Down)
check("↓ : A3", w.sel == (0, "A:in:3"))
QTest.keyClick(w.name, Qt.Key_Up)
check("↑ : A2", w.sel == (0, "A:in:2"))
for _ in range(5):
    QTest.keyClick(w.name, Qt.Key_Return)
w.name.setText("Tom 1")
QTest.keyClick(w.name, Qt.Key_Return)
check("A7 nommée « Tom 1 » (au lieu du nom LV1)", store.current()["consoles"]["0"]["ports"]["A:in:7"]["name"] == "Tom 1"
      and w.sel == (0, "A:in:8"))
w.select((0, "A:out:7"))
check("sortie choisie depuis la face : Genelec", w.name.text() == "Genelec")
QTest.keyClick(w.name, Qt.Key_Return)
check("› sur une sortie : OUT 8 de la S16", w.sel == (0, "A:out:8"))
w.find.setText("snare")
check("recherche : rien (Snare renommée)", len(w.rows) == 0)
w.find.setText("caisse")
check("recherche « caisse » : EXP 1 et 2", [r["exp"] for r in w.rows] == [1, 2])
w.find.setText("")
w.select((0, "A:in:3"))
w.clear_port()
check("Effacer : A3 sans étiquette", "A:in:3" not in store.current()["consoles"]["0"]["ports"])
check("Effacer : notification « In 3 : piste par défaut »", Fake.toast.said and "In 3" in Fake.toast.said[-1][1])
w._toggle_auto()
check("bouton renommage auto : désactivé", store.auto is False and w.auto_btn.property("on") == "0")
# Exporter… / Importer… (fenêtres de fichier simulées)
from PySide6.QtWidgets import QFileDialog
exp_path = os.path.join(tmp, "Concert A.stagepatch.json")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (exp_path[:-len(".stagepatch.json")], ""))
w.export_sheet()
check("Exporter : fichier écrit (extension ajoutée), dossier retenu", os.path.isfile(exp_path)
      and Fake.cfg.get("stage_dir") == tmp and Fake.toast.said[-1][0] in ("Feuille exportée", "Sheet exported"))
n0 = len(store.sheets)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (exp_path, ""))
w.import_sheet()
check("Importer : feuille ajoutée et active", len(store.sheets) == n0 + 1 and w.state["active"] == store.active
      and w.sheets.count() == n0 + 1)
open(os.path.join(tmp, "pas_une_feuille.json"), "w").write('{"a": 1}')
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (os.path.join(tmp, "pas_une_feuille.json"), ""))
w.import_sheet()
check("Importer un autre fichier : refusé, rien d'ajouté", len(store.sheets) == n0 + 1)
for _ in range(3):
    app_qt.processEvents()
f0, f1 = w.faces
check("après import : faces l'une sous l'autre (pas de chevauchement)", f0.geometry().bottom() < f1.geometry().top())
w.select((0, "A:in:1"))
if "--image" in sys.argv:
    w.grab().save(sys.argv[sys.argv.index("--image") + 1])

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
