"""Test : lv1/model.py — état du mixer de la LV1 tenu par ses notifications (tablette TouchOSC, phase 5a, 27/10/2026).
Formats relevés sur la LV1 de Joseph (journal XTouch-LV1 111226 et écoute du 27/10) :
- /Channels : nom, fader, solo, mute, mono / stéréo ; liste complète -> pistes disparues retirées, tronquée -> rien ;
- fader, mute, solo, pan (/45), trim et phase par voie, mono / stéréo à chaud ;
- vumètres : voie la plus haute, oubliés après METER_STALE ; adresses inconnues ignorées ;
- auditeurs de lv1/remote.LV1Remote : appelés pour chaque message, une erreur n'arrête rien ;
- couches (27/10) : modes Mix / Input / Factory / Custom reconnus, Spill jamais mémorisé, jeu « affiché » adopté
  seulement au /Notify/CurrentLayer qui le suit (Custom sans CurrentLayer à la connexion), mémoire rechargée.

    py tests/test_lv1_model.py
"""
import os
import sys
import time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from lv1 import model as M
from lv1.remote import LV1Remote

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


def piste(g, c, name, fader=-144.0, solo=0, mute=0, stereo=False):
    ints = [0] * 12
    ints[0], ints[1], ints[11] = solo, mute, 2 if stereo else 1
    return [("s", name), ("i", g), ("i", c), ("d", fader), ("d", 0.0)] + [("i", v) for v in ints] + \
        [("h", 1099511627776), ("d", 0.0)]


def channels(pistes):
    args = [("i", len(pistes))]
    for p in pistes:
        args += p
    return args


m = M.LV1Mixer()
m.handle("/Channels", channels([piste(0, 0, "Channel 1", -10.0), piste(0, 6, "P170", solo=1, stereo=True),
                                piste(0, 63, "In 64"), piste(3, 0, "LR", -0.2)]))
snap = m.snapshot()
check("/Channels : nom, fader, solo, stéréo", snap[(0, 0)]["fader"] == -10.0 and snap[(0, 6)]["solo"] is True
      and snap[(0, 6)]["stereo"] is True and snap[(3, 0)]["fader"] == -0.2 and snap[(0, 0)]["mute"] is False)
m.handle("/Notify/Track/Out/Gain", [("i", 0), ("i", 0), ("d", -4.5), ("T", True)])
m.handle("/Notify/Track/Out/Mute", [("i", 0), ("i", 0), ("i", 1), ("T", True)])
m.handle("/Notify/Solo", [("i", 0), ("i", 6), ("i", 0), ("i", 1)])
m.handle("/Notify/Track/Pan", [("i", 0), ("i", 0), ("f", -22.5)])
m.handle("/Notify/TrackTrim", [("i", 0), ("i", 0), ("i", 0), ("f", 3.5)])
m.handle("/Notify/PhaseState", [("i", 0), ("i", 0), ("i", 0), ("i", 1), ("i", 1)])
m.handle("/Notify/StemFormatForSource", [("i", 0), ("i", 6), ("i", 100), ("i", 1)])
m.handle("/Notify/Inconnue", [("i", 0)])
t = m.snapshot()[(0, 0)]
check("fader, mute, pan /45, trim et phase de la voie 0", t["fader"] == -4.5 and t["mute"] is True and t["pan"] == -0.5
      and t["trim"] == {0: 3.5} and t["phase"] == {0: True})
check("solo coupé, P170 repassé en mono", m.snapshot()[(0, 6)]["solo"] is False and m.snapshot()[(0, 6)]["stereo"] is False)

m.handle("/Notify/Meters", [("i", 3), ("i", 0), ("i", 6), ("i", 0), ("f", -20.0), ("i", 0), ("i", 6), ("i", 1),
                            ("f", -12.0), ("i", 3), ("i", 0), ("i", 0), ("f", -3.0)])
s2 = m.snapshot()
check("vumètre : voie la plus haute", s2[(0, 6)]["meter"] == -12.0 and s2[(3, 0)]["meter"] == -3.0
      and s2[(0, 0)]["meter"] is None)
with m.lock:
    m.meters = {k: (d, t0 - M.METER_STALE - 1) for k, (d, t0) in m.meters.items()}
check("vumètre plus reçu : oublié", m.snapshot()[(0, 6)]["meter"] is None and m.meter(0, 6) is None)

trunc = channels([piste(0, 0, "Channel 1")])[:1 + 19 * 1 - 10]
m.handle("/Channels", [("i", 2)] + trunc[1:])
check("liste tronquée : rien retiré", (0, 63) in m.snapshot())
m.handle("/Channels", channels([piste(0, 0, "Channel 1"), piste(3, 0, "LR")]))
check("liste complète : pistes disparues retirées", sorted(m.snapshot()) == [(0, 0), (3, 0)])

# couches (27/10) : jeux par mode, adoption au CurrentLayer, mémoire
def layers_msg(view, flag, layers):
    args = [("i", view), ("i", flag), ("i", len(layers))]
    for name, ents in layers:
        args += [("s", name), ("i", len(ents))]
        for e in ents:
            args += [("i", e[0] if e else -1), ("i", e[1] if e else -1)]
    return args


mix = [("Groups", [(1, 0), (1, 1)]), ("Fx", [(2, 0)]), ("Masters", [(3, 0), None, (4, 0)]), (" ", [None])]
inp = [("Ch 1-16", [(0, 0), (0, 1)]), ("Ch 17-32", [(0, 16)]), (" ", [None])]
cus = [("Page-1", [(0, 61), None]), ("Page-2", [None])]
fac = [("Ch 1-16", [(0, 0)]), ("Grp/Fx", [(1, 0)]), ("Monitor", [(25, 0)]), ("Masters", [(3, 0)]), ("Link DCA", [(12, 0)])]
check("modes reconnus ; Spill (inconnu) jamais", M.set_kind(0, mix) == "mix" and M.set_kind(0, inp) == "input"
      and M.set_kind(1, cus) == "custom" and M.set_kind(0, fac) == "factory" and M.set_kind(0, [("DCA 1", [(0, 3)])]) is None)
m2 = M.LV1Mixer()
m2.handle("/Notify/Layers", layers_msg(0, 0, mix))
m2.handle("/Notify/Layers", layers_msg(1, 0, inp))
m2.handle("/Notify/Layers", layers_msg(0, 1, cus))          # à la connexion : Custom SANS CurrentLayer
ls = m2.layers_snapshot()
check("jeux mémorisés (Mix, Input, Custom de Mixer 1), rien d'affiché sans CurrentLayer", sorted(ls["sets"]) == ["custom0",
      "input", "mix"] and ls["shown"] == {} and ls["sets"]["mix"][2] == ("Masters", [(3, 0), None, (4, 0)])
      and ls["sets"]["mix"][3] == ("", [None]))
m2.handle("/Notify/Layers", layers_msg(0, 0, mix))
m2.handle("/Notify/CurrentLayer", [("i", 0), ("i", 2)])
m2.handle("/Notify/CurrentLayer", [("i", 1), ("i", 1)])     # Mixer 2 : son jeu Input était en attente -> adopté
m2.handle("/Notify/CurrentLayer", [("i", 1), ("i", 0)])     # puis seulement l'index change
sh = m2.layers_snapshot()["shown"]
check("adopté au CurrentLayer qui suit (Mixer 1 : Mix, couche Masters ; Mixer 2 : Input)", sh[0]["kind"] == "mix"
      and sh[0]["index"] == 2 and sh[1]["kind"] == "input" and sh[1]["index"] == 0)
m2.handle("/Notify/CurrentLayer", [("i", 0), ("i", 0)])
check("autre couche du même jeu : index mis à jour", m2.layers_snapshot()["shown"][0]["index"] == 0)
rev = m2.sets_rev
m2.handle("/Notify/Layers", layers_msg(0, 0, [("DCA 1", [(0, 3)])]))
m2.handle("/Notify/CurrentLayer", [("i", 0), ("i", 0)])
check("Spill : affiché, pas mémorisé", m2.layers_snapshot()["shown"][0]["kind"] is None and m2.sets_rev == rev
      and "mix" in m2.layers_snapshot()["sets"])
m3 = M.LV1Mixer()
m3.load_sets({"mix": [["Groups", [[1, 0], None]]], "bidon": [], "input": "pas une liste"})
check("mémoire rechargée (clés connues, valeurs propres)", m3.layers_snapshot()["sets"] == {"mix": [("Groups", [(1, 0), None])]})
m3.handle("/Notify/TrackColor", [("i", 1), ("i", 0), ("i", 11), ("f", 0.1), ("f", 0.2), ("f", 0.3)])
check("couleur d'une piste (n° de palette)", m3.snapshot()[(1, 0)]["pal"] == 11)

# auditeurs de LV1Remote
r = LV1Remote(log=lambda x: None)
got = []
r.listeners.append(lambda a, args: got.append(a))
r.listeners.append(lambda a, args: 1 / 0)
r._handle("/Notify/Solo", [("i", 0), ("i", 1), ("i", 1), ("i", 1)])
check("auditeurs : appelés, une erreur n'arrête rien", got == ["/Notify/Solo"] and "auditeur" in (r.error or ""))

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
