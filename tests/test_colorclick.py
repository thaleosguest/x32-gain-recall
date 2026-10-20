"""Test : couleurs des canaux LV1 par clics (lv1/colorclick.py, 3.1) contre une LV1 SIMULÉE (page Patch / Input A,
fenêtre « Select a Color » : ‹ › changent de canal sans la fermer, couleur appliquée tout de suite — comportement
vérifié par Joseph le 20/10/2026) :
- cas normal : 3 canaux colorés dans l'ordre, OK à la fin, rien d'autre touché ;
- vue Input B affichée : clic sur Input A d'abord ;
- liste pas en haut (1re ligne ≠ In 1) : refus SANS clic dans la liste ;
- un clic › perdu (décalage) : vu avant de colorer (fond du champ) ou après (mauvais canal remis) -> arrêt propre ;
- changement jamais vu (LV1 qui ignore) : arrêt ;
- couleurs à donner : x32_stage.lv1_color_targets (voie gauche d'abord, déjà bonne = rien).

    py tests/test_colorclick.py
"""
import os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from lv1 import colorclick as cc
from lv1.channelinfo import PALETTE
import x32_stage as xs

cc.STEP_S, cc.SETTLE_S = 0.0, 0.0

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


class FakeLV1:
    def __init__(self, colors, n=16, view_a=True, top=True, lose_next=None, deaf=False):
        self.colors = dict(colors)                 # canal -> n° de palette
        self.n, self.view_a, self.top = n, view_a, top
        self.open, self.pos = False, None
        self.lose_next = lose_next                 # n° du clic › à perdre (simulation d'un décalage)
        self.next_count = 0
        self.deaf = deaf
        self.events, self.clicks, self.logs = [], [], []

    def rgb(self, idx):
        return cc.hex_rgb(PALETTE[idx])

    def read(self, pts):
        out = []
        for p in pts:
            if p == cc.INPUT_A:
                out.append(cc.BLUE if self.view_a else (17, 17, 17))
            elif p == cc.ROW1:
                out.append(self.rgb(self.colors.get(1 if self.top else 9, 13)))
            elif not self.open:
                out.append((17, 17, 17))
            elif p == cc.DLG_BG:
                out.append(cc.DIALOG_BG)
            elif p == cc.FIELD:
                out.append(self.rgb(self.colors.get(self.pos, 13)))
            else:
                i = next((i for i in range(32) if cc.cell(i) == p), None)
                out.append(self.rgb(i) if i is not None else (0, 0, 0))
        return out

    def click(self, p):
        self.clicks.append(p)
        if p == cc.INPUT_A:
            self.view_a = True
        elif p == cc.ROW1 and self.view_a and not self.open:
            self.open, self.pos = True, (1 if self.top else 9)
        elif self.open and p == cc.NEXT:
            self.next_count += 1
            if self.next_count != self.lose_next:
                self.pos = min(self.n, self.pos + 1)
        elif self.open and p == cc.PREV:
            self.pos = max(1, self.pos - 1)
        elif self.open and p == cc.OK:
            self.open = False
        elif self.open:
            i = next((i for i in range(32) if cc.cell(i) == p), None)
            if i is not None and not self.deaf:
                self.colors[self.pos] = i
                self.events.append((self.pos, i, time.time()))

    def changes(self, since):
        return [e for e in self.events if e[2] >= since]

    def stopped(self):
        return False

    def log(self, t):
        self.logs.append(t)


base = {1: 19, 2: 13, 3: 13, 4: 14, 5: 13, 6: 13, 7: 13, 8: 13, 9: 13, 10: 13}

# cas normal
lv = FakeLV1(base)
done, err = cc.ColorJob({3: 18, 5: 18, 10: 7, 4: 14}, base, lv, wait=0.5).run()
check("normal : 3 canaux faits (In 4 déjà bon)", done == [3, 5, 10] and err is None)
check("normal : couleurs dans la LV1", lv.colors[3] == 18 and lv.colors[5] == 18 and lv.colors[10] == 7)
check("normal : rien d'autre touché", all(lv.colors[c] == base[c] for c in base if c not in (3, 5, 10)))
check("normal : fenêtre refermée par OK", not lv.open and lv.clicks[-1] == cc.OK)

# vue Input B : clic sur Input A d'abord
lv = FakeLV1(base, view_a=False)
done, err = cc.ColorJob({2: 6}, base, lv, wait=0.5).run()
check("Input B affichée : Input A cliqué puis In 2 colorée", lv.clicks[0] == cc.INPUT_A and done == [2] and err is None)

# liste pas en haut : aucun clic dans la liste
lv = FakeLV1({**base, 9: 25}, top=False)
done, err = cc.ColorJob({2: 6}, {**base, 9: 25}, lv, wait=0.5).run()
check("liste pas en haut : refus sans clic", done == [] and "In 1" in (err or "") and cc.ROW1 not in lv.clicks)

# un › perdu : In 4 visé, la fenêtre reste sur In 3 (même couleur 13 que In 4 ? non : In 4 = 14) -> vu avant de colorer
lv = FakeLV1(base, lose_next=2)
done, err = cc.ColorJob({4: 7}, base, lv, wait=0.5).run()
check("› perdu, couleurs différentes : vu AVANT de colorer", done == [] and "In 4" in (err or "")
      and lv.colors == base and not lv.open)

# un › perdu, canaux de même couleur (In 5 visé, fenêtre sur In 4... ici In 6 visé, fenêtre sur In 5, tous deux 13) :
# mauvais canal coloré -> remis comme avant, arrêt
lv = FakeLV1(base, lose_next=3)
done, err = cc.ColorJob({2: 18, 6: 7}, base, lv, wait=0.5).run()
check("› perdu, mêmes couleurs : In 2 faite puis arrêt", done == [2] and "décalage" in (err or ""))
check("› perdu : canal touché par erreur remis (In 5 = 13)", lv.colors[5] == 13 and lv.colors[6] == 13 and lv.colors[2] == 18)

# LV1 qui ignore les clics de couleur
lv = FakeLV1(base, deaf=True)
done, err = cc.ColorJob({3: 18}, base, lv, wait=0.3).run()
check("changement jamais vu : arrêt", done == [] and "pas vu" in (err or ""))

# couleurs à donner (feuille du croquis)
sheet = xs.new_sheet("t")
ports = xs.sheet_console(sheet, 0, "X32RACK")["ports"]
ports["A:in:1"] = {"name": "Kick", "color": 18}
ports["A:in:2"] = {"name": "Snare", "color": None}
ports["local:in:1"] = {"name": "Piano L", "color": 6}
ports["local:in:2"] = {"name": "Piano R", "color": 24}
exp_map = {32: 1, 33: 2, 0: 17, 1: 18}
srcs = {1: [1], 2: [2], 20: [17, 18], 21: [18]}
info = {1: {"color": "#0FA2AB"}, "2": {"color": "#0FA2AB"}, 20: {"color": "#0FA2AB"}, 21: {"color": PALETTE[24]}}
t = xs.lv1_color_targets(sheet, exp_map, srcs, info)
check("cibles : Kick jaune, piano stéréo = couleur de gauche, Snare sans couleur ignorée, déjà bonne ignorée",
      t == {1: 18, 20: 6})

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
