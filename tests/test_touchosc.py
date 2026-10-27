"""Test : TouchOSC (3.2) — template généré + pont tablette <-> Gain Recall.
Phase 0 (27/10/2026) : template relu (XML lexml 3, page 2000 x 1200, script Lua avec le protocole, ID uniques, fichier
identique d'une génération à l'autre) ; hello -> welcome ; paquet illisible ignoré ; état en erreur sans tomber ;
tablette oubliée après LOST_S.
Phase 1 (27/10/2026) : état traduit en messages, TOUT à l'arrivée d'une tablette puis SEULEMENT ce qui change, tout de
nouveau sur /xgr/sync ; actions de la liste fermée, erreur renvoyée en /xgr/notify ; bouton SYNC du template.
Autorisation (décision de Joseph, 27/10) : tablette inconnue en attente (welcome « pending », rien d'autre), oui ->
acceptée, non -> ignorée ; le PC lui-même toujours accepté (127.x ou ses adresses réseau). Adresses de documentation
192.0.2.x pour les fausses tablettes réseau (aucun vrai appareil touché).
Phase 2a (27/10) : page GAINS = 16 tranches de la couche LV1 de Mixer 1 (canal -> EXP -> préampli, stéréo en deux
voies, EXP sans préampli = pas de voie, tranche sans canal vide, titre de couche) ; un gain qui change ne renvoie que
sa voie ; template : 16 tranches (bandeau, nom, source, voies m / l / r) et panneau de connexion par-dessus.
Phase 2b (27/10) : vue PAR TABLETTE (banques 1-16 … 65-80, FOLLOW LV1, banques au-delà de la configuration ignorées) ;
gestes traduits en préamplis d'après la page de CETTE tablette (gain borné -12..60, 48V = bascule), tranche changée
-> message ; template : potards RELATIFS avec script, bouton 48V transparent à confirmer, boutons de banque / FOLLOW.

    py tests/test_touchosc.py
"""
import os
import socket
import sys
import tempfile
import time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from touchosc import build_tosc, protocol as P, tosc, views
from touchosc.bridge import Bridge
from lv1.osc_sniffer import decode_message, encode_message

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


# ── template
tmp = tempfile.mkdtemp()
f1, f2 = os.path.join(tmp, "a.tosc"), os.path.join(tmp, "b.tosc")
build_tosc.main(["", f1])
build_tosc.main(["", f2])
check("deux générations identiques", open(f1, "rb").read() == open(f2, "rb").read())
x = tosc.read_xml(f1)
check("lexml version 3", x.tag == "lexml" and x.get("version") == "3")
root = x.find("node")
rp = tosc.props_of(root)
check("racine GROUP 2000 x 1200", root.get("type") == "GROUP" and rp["frame"] == {"x": "0", "y": "0", "w": "2000", "h": "1200"})
nodes = list(x.iter("node"))
names = {tosc.props_of(n)["name"]: n for n in nodes}
check("voyant, état, lignes console / LV1 / TouchOSC, message", {"led", "status", "detail", "console", "lv1",
      "tablets", "notify"} <= set(names))
check("ID uniques", len({n.get("ID") for n in nodes}) == len(nodes))
script = rp["script"]
check("Lua : protocole et ports remplacés", "local PROTO = %d" % P.PROTO in script and str(P.PORT_IN) in script
      and "__" not in script)
check("Lua : hello, welcome, état, notify, attente", all(s in script for s in ("sendOSC('/xgr/hello'", "'/xgr/welcome'",
      "'/xgr/console'", "'/xgr/notify'", "'pending'")))
st = names["status"]
check("état = LABEL avec un texte", st.get("type") == "LABEL"
      and any(v.find("key").text == "text" for v in st.find("values")))
sync = names["sync"]
check("bouton SYNC : BUTTON qui envoie /xgr/sync", sync.get("type") == "BUTTON"
      and "sendOSC('%s')" % P.SYNC in tosc.props_of(sync)["script"])
check("libellé du bouton non interactif", tosc.props_of(names["sync_label"])["interactive"] == "0")
check("16 tranches : bandeau, nom, source, voies m / l / r", all("g%d_%s" % (k, part) in names for k in range(1, 17)
      for part in ("band", "name", "src", "m_knob", "m_db", "m_48", "l_knob", "r_48l")) and "g17_band" not in names)
kp, dp = tosc.props_of(names["g1_m_knob"]), tosc.props_of(names["g1_m_drag"])
check("potard = affichage ; glisser vertical par un bouton transparent posé dessus (retour de Joseph sur l'a7)",
      names["g1_m_knob"].get("type") == "RADIAL" and kp["interactive"] == "0" and "script" not in kp
      and names["g1_m_drag"].get("type") == "BUTTON" and dp["color"]["a"] == "0"
      and "'/xgr/g/1/m/gain'" in dp["script"] and "'g1_m_knob'" in dp["script"] and "'g1_m_db'" in dp["script"]
      and "local STEP_PX = 5" in dp["script"] and "PointerState.BEGIN" in dp["script"]
      and "'/xgr/g/16/r/gain'" in tosc.props_of(names["g16_r_drag"])["script"])
check("script racine : retours ignorés pendant et 1 s après un glisser", "local HOLD_MS = 1000" in script
      and "'_drag'" in script and "'48b'" in script)
pp = tosc.props_of(names["g7_l_48b"])
check("48V : bouton transparent sur la case, OK? puis confirmation dans les 3 s", names["g7_l_48b"].get("type") == "BUTTON"
      and "'/xgr/g/7/l/48v'" in pp["script"] and "'g7_l_48l'" in pp["script"] and "'OK?'" in pp["script"]
      and pp["color"]["a"] == "0")
check("banques 1-16 … 65-80 et FOLLOW LV1", all("sendOSC('/xgr/view/bank', %d)" % n in tosc.props_of(names["bank%d" % n])["script"]
      for n in range(5)) and "sendOSC('/xgr/view/follow')" in tosc.props_of(names["follow"])["script"]
      and tosc.props_of(names["bank4_label"]) is not None)
fr = lambda n: {k: int(v) for k, v in tosc.props_of(names[n])["frame"].items()}
l48, rk = fr("g7_l_48"), fr("g7_r_knob")
lk, ld, rd, md = fr("g7_l_knob"), fr("g7_l_drag"), fr("g7_r_drag"), fr("g7_m_drag")
check("stéréo côte à côte dans le cadre préampli (2c, comme le float sur la LV1)", rk["y"] == lk["y"] and rk["x"] > lk["x"]
      and ld["w"] == rd["w"] == 56 and rd["x"] == ld["x"] + 56 and md["w"] == 112 and "g7_l_side" not in names)
pre = fr("g7_pre")
check("glisser : zone de la voie, dans le cadre préampli", ld["y"] >= pre["y"] and ld["y"] + ld["h"] <= pre["y"] + pre["h"]
      and l48["y"] + l48["h"] <= pre["y"] + pre["h"])
check("page Mixer : source, A / B, préampli, Ø, Trim, nom, pan, MUTE, fader, numéro, cue (de haut en bas)",
      [fr("g3_" + n)["y"] for n in ("srcbox", "a", "pre", "phase", "trim_t", "band", "pan", "mute", "fval", "fader",
                                     "numbar", "cue")] == sorted(fr("g3_" + n)["y"] for n in ("srcbox", "a", "pre",
                                     "phase", "trim_t", "band", "pan", "mute", "fval", "fader", "numbar", "cue")))
check("vumètre : barre FADER lecture seule ; script racine : setMix / setLive", names["g3_meter"].get("type") == "FADER"
      and tosc.props_of(names["g3_meter"])["interactive"] == "0" and "function setMix" in script
      and "local function setLive" in script and "'^/xgr/lr/(%a+)$'" in script)
check("commandes de la LV1 (phase 5) sans effet : fader, pan, Trim non interactifs", all(
      tosc.props_of(names[n])["interactive"] == "0" for n in ("g3_fader", "g3_pan", "g3_trim", "g3_mute", "lr_fader")))
check("tranche LR à droite des 16 tranches", fr("lr_band")["x"] > fr("g16_band")["x"] and "lr_num" in names)
order = [tosc.props_of(n)["name"] for n in root.find("children")]
check("panneau de connexion par-dessus les tranches", order.index("panel") > order.index("g16_r_48l"))

# ── protocole
check("hello entier", P.parse_hello([("i", 1), ("s", "R10")]) == (1, "R10"))
check("hello réel (Lua)", P.parse_hello([("f", 1.0)]) == (1, "TouchOSC"))
check("hello mal formé", P.parse_hello([("s", "x")]) is None and P.parse_hello([]) is None)
check("template à jour / ancien / récent", (P.template_state(P.PROTO), P.template_state(P.PROTO - 1),
      P.template_state(P.PROTO + 1)) == ("ok", "old_template", "new_template"))
check("console", P.console_text({"connected": True, "info": {"name": "X32RACK-JS"}}) == "X32RACK-JS"
      and P.console_text({"connected": False}) == "No console" and P.console_text(None) == "No console")
full = {"connected": True, "info": {"name": "X32RACK-JS"}, "exp_map": {0: 17, 32: 1}, "lv1_count": 64,
        "consoles": [{"connected": True}, {"connected": True}]}
m = P.state_messages(full, tablets=1)
check("état : console (+ 2e console), LV1, TouchOSC", m["/xgr/console"] == (("s", "X32RACK-JS + 1 more"),)
      and m["/xgr/console/ok"] == (("i", 1),) and m["/xgr/lv1"] == (("s", "64 LV1 channels known, 2 X32 sources on EXP"),)
      and m["/xgr/tablets"] == (("i", 1),))
check("état : connexion en cours / rien", P.state_messages({"trying": True, "ip": "192.168.1.201"})["/xgr/console"]
      == (("s", "Connecting to 192.168.1.201..."),) and P.state_messages(None)["/xgr/lv1"] == (("s", "No LV1 session read"),))
check("actions : sync seulement", P.parse_action(P.SYNC, []) == ("sync",) and P.parse_action("/xgr/rien", []) is None)
check("autorisées : PC toujours, réseau sur liste", P.allowed("127.0.0.1", ()) and P.allowed("192.168.1.20", {"192.168.1.20"})
      and not P.allowed("192.168.1.50", {"192.168.1.20"}) and P.allowed("192.168.1.16", (), own={"192.168.1.16"}))
check("welcome en attente : rien sur la console", [v for _t, v in P.welcome(P.PROTO, "3.2", {"connected": True}, pending=True)[1]]
      == [P.PROTO, "3.2", "", "pending"])

# ── page GAINS (views)
gstate = {"lv1_layers": {"mixer1": {"mode": 0, "page": 0, "bank": 0, "channels": list(range(1, 17))}},
          "exp_map": {32: 1, 33: 2, 0: 17, 130: 1003}, "lv1_sources": {"1": [1, 2], "2": [17], "7": [11], "3": [1003]},
          "lv1_channels": {"1": {"label": "P170 ST", "color": "#ff4f4f"}, "2": {"label": "Kick"}},
          "gains": [None] * 256, "phantom": [0] * 256, "consoles": [{"n": 0, "card": 1, "connected": True}]}
gstate["gains"][32], gstate["gains"][33], gstate["gains"][0] = 32.5, 30.0, -4.0
gstate["phantom"][0] = 1
page = views.gain_page(gstate)
st1, st2, st3, st7 = page["strips"][0], page["strips"][1], page["strips"][2], page["strips"][6]
check("titre de couche", page["title"] == "Ch 1-16" and len(page["strips"]) == 16)
check("stéréo : deux voies, A 1/2, EXP 1/2, couleur", [u["idx"] for u in st1["units"]] == [32, 33]
      and st1["src"] == "A 1/2 = EXP 1/2" and st1["color"] == "FF4F4F" and st1["label"] == "P170 ST"
      and st1["input"] == "1- EX 1\n1- EX 2")
check("mono : une voie, gain et 48V", [(u["idx"], u["db"], u["phantom"]) for u in st2["units"]] == [(0, -4.0, True)]
      and st2["src"] == "L 1 = EXP 17" and st2["name"] == "Kick" and st2["input"] == "1- EX 17")
check("console 2 : 2·L 3, EXP 2·3, carte inconnue -> EX 3", st3["src"] == "2·L 3 = EXP 2·3" and st3["input"] == "EX 3")
check("EXP sans préampli : pas de voie", st7["units"] == [] and st7["src"] == "no X32 preamp" and st7["label"] == "In 7")
gl = {"mixer1": {"mode": 1, "page": 2, "bank": None, "channels": [5, None] + [None] * 14}}
cust = views.gain_page({"lv1_layers": gl})
check("couche Custom, tranche sans canal vide", cust["title"] == "Custom 3" and cust["strips"][1] == {
      "ch": 0, "label": "", "name": "", "color": "", "units": [], "src": "", "input": "", "mix": None})
check("pas de couche d'entrées", views.gain_page({})["title"] == "No input channels on this layer")
# phase 5a : commandes de la LV1 en lecture seule
mixer = {(0, 0): {"fader": -4.5, "mute": True, "solo": False, "pan": None, "trim": {0: 3.5}, "phase": {0: False, 1: True},
                  "meter": -12.3}, (3, 0): {"fader": -0.2, "mute": False, "solo": None, "pan": None, "trim": {},
                  "phase": {}, "meter": -75.4}}
lp = views.gain_page(dict(gstate, lv1_mixer=mixer, lv1_live=True,
                          lv1_channels=dict(gstate["lv1_channels"], **{"1": {"label": "P170 ST", "color": "#ff4f4f",
                                                                             "pan": 0.25, "input": "B"}})))
mx = lp["strips"][0]["mix"]
check("mixer : fader, mute, pan de la base (LV1 muette), trim, phase d'une voie, A / B, vumètre", mx == {
      "fader": -4.5, "mute": True, "solo": False, "pan": 0.25, "trim": 3.5, "phase": True, "meter": -12.3, "input": "B"}
      and lp["live"] is True and lp["strips"][1]["mix"] is None and lp["lr"]["fader"] == -0.2)
check("courbe du fader LV1", views.fader_frac(10) == 1.0 and views.fader_frac(0) == 0.765 and views.fader_frac(-144) == 0.0
      and views.fader_frac(None) == 0.0 and abs(views.fader_frac(-5) - 0.6475) < 1e-4)
mm = P.gain_messages(lp)
check("messages mixer : fader -144.0 comme la LV1, crête arrondie sous -60, pan 0..1, A / B", mm["/xgr/g/1/fval"] == (("s", "-4.5"),)
      and mm["/xgr/g/1/mute"] == (("i", 1),) and mm["/xgr/g/1/pan"] == (("f", 0.625),) and mm["/xgr/g/1/ab"] == (("s", "B"),)
      and mm["/xgr/g/1/trimv"] == (("s", "3.5"),) and mm["/xgr/g/1/phase"] == (("i", 1),) and mm["/xgr/live"] == (("i", 1),)
      and mm["/xgr/lr/peak"] == (("s", "-75"),) and mm["/xgr/g/1/peak"] == (("s", "-12.3"),))
check("LR en lecture seule : ni pan, ni Trim, ni CUE, ni A / B", sorted(a for a in mm if a.startswith("/xgr/lr/"))
      == ["/xgr/lr/fader", "/xgr/lr/fval", "/xgr/lr/meter", "/xgr/lr/mute", "/xgr/lr/peak"])
check("tranche sans info de la LV1 : tirets", mm["/xgr/g/2/fval"] == (("s", "-"),) and mm["/xgr/g/2/ab"] == (("s", ""),)
      and P.mix_messages("/x", {"fader": -144.0})["/x/fval"] == (("s", "-144.0"),))
check("dB et course", views.db_text(32.5) == "32.5" and views.db_text(None) == "-" and views.gain_frac(-12) == 0.0
      and views.gain_frac(60) == 1.0 and views.gain_frac(24) == 0.5)
gm = P.gain_messages(page)
check("actions : banque, follow, gain borné, 48V ; le reste ignoré", P.parse_action("/xgr/view/bank", [("i", 2)]) == ("bank", 2)
      and P.parse_action("/xgr/view/bank", [("f", 1.0)]) == ("bank", 1) and P.parse_action("/xgr/view/bank", [("i", 7)]) is None
      and P.parse_action("/xgr/view/follow", []) == ("follow",)
      and P.parse_action("/xgr/g/3/l/gain", [("f", 30.5)]) == ("gain", 3, "l", 30.5)
      and P.parse_action("/xgr/g/3/m/gain", [("f", 99.0)]) == ("gain", 3, "m", 60.0)
      and P.parse_action("/xgr/g/16/r/48v", []) == ("phantom", 16, "r")
      and P.parse_action("/xgr/g/17/m/gain", [("f", 1.0)]) is None and P.parse_action("/xgr/g/1/x/gain", [("f", 1.0)]) is None
      and P.parse_action("/xgr/g/1/m/gain", []) is None)
b1 = views.gain_page(dict(gstate, lv1_count=64), bank=1)
check("vue fixe : banque 2 = Ch 17-32, ne suit plus", b1["title"] == "Ch 17-32" and b1["follow"] is False and b1["bank"] == 1
      and b1["strips"][0]["ch"] == 17 and b1["banks"] == 4)
check("banque au-delà de la configuration : suit la LV1", views.gain_page(dict(gstate, lv1_count=64), bank=4)["follow"] is True)
check("voie -> préampli d'après la page", views.unit_idx(page, 1, "l") == 32 and views.unit_idx(page, 1, "r") == 33
      and views.unit_idx(page, 2, "m") == 0 and views.unit_idx(page, 1, "m") is None and views.unit_idx(page, 7, "m") is None)
check("messages : stéréo l / r, mono m, rien pour les voies absentes", gm["/xgr/g/1/units"] == (("i", 2),)
      and gm["/xgr/g/1/l/db"] == (("s", "32.5"),) and gm["/xgr/g/1/r/db"] == (("s", "30.0"),)
      and gm["/xgr/g/2/m/48v"] == (("i", 1),) and "/xgr/g/1/m/db" not in gm and "/xgr/g/7/m/db" not in gm
      and gm["/xgr/g/title"] == (("s", "Ch 1-16"),))
check("messages : nom LV1, numéro de canal, source LV1", gm["/xgr/g/2/name"] == (("s", "Kick"),)
      and gm["/xgr/g/2/ch"] == (("i", 2),) and gm["/xgr/g/2/input"] == (("s", "1- EX 17"),))

# ── pont, avec une fausse tablette
tab = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tab.bind(("127.0.0.1", 0))
tab.settimeout(0.5)
logs = []
state = dict(gstate, connected=True, info={"name": "X32RACK-JS"}, lv1_count=64)
b = Bridge("3.2.0-a2", lambda: dict(state), port=0, reply_port=tab.getsockname()[1], log=logs.append)
b.PUBLISH_EVERY = 0.05
b.start()


def send(address, args=()):
    tab.sendto(encode_message(address, list(args)), ("127.0.0.1", b.port))


def drain(wait=0.4):
    """Messages reçus par la tablette pendant `wait` s : {adresse: [valeurs]} (dernier reçu) + liste dans l'ordre."""
    got, order, end = {}, [], time.time() + wait
    while time.time() < end:
        try:
            a, args = decode_message(tab.recv(65536))
        except socket.timeout:
            continue
        got[a] = [v for _t, v in args]
        order.append(a)
    return got, order


check("pont local par défaut", b.sock.getsockname()[0] == "127.0.0.1")
send(P.HELLO, [("i", P.PROTO), ("s", "R10")])
got, order = drain()
check("arrivée : welcome puis tout l'état", order[:1] == [P.WELCOME] and got[P.WELCOME] == [P.PROTO, "3.2.0-a2", "X32RACK-JS", "ok"]
      and {"/xgr/console", "/xgr/console/ok", "/xgr/lv1", "/xgr/tablets"} <= set(got))
check("tablette retenue", b.snapshot() == [{"ip": "127.0.0.1", "name": "R10", "proto": P.PROTO}]
      and any("tablette 127.0.0.1" in m for m in logs))
got, order = drain(0.3)
check("rien de changé : rien envoyé", order == [])
state["lv1_count"] = 80
got, order = drain(0.3)
check("changement : seulement les messages concernés (LV1, banques proposées)", order == ["/xgr/lv1", "/xgr/view/banks"]
      and got["/xgr/lv1"][0].startswith("80 LV1") and got["/xgr/view/banks"] == [5])
state["gains"] = list(state["gains"])
state["gains"][33] = 36.0
got, order = drain(0.3)
check("gain changé : seulement sa voie (potard + dB)", sorted(order) == ["/xgr/g/1/r/db", "/xgr/g/1/r/gain"]
      and got["/xgr/g/1/r/db"] == ["36.0"])
send(P.SYNC)
got, order = drain(0.3)
check("SYNC : tout l'état renvoyé", {"/xgr/console", "/xgr/console/ok", "/xgr/lv1", "/xgr/tablets"} <= set(order))
send(P.HELLO, [("i", P.PROTO)])
got, order = drain(0.3)
check("hello suivant : welcome seul (pas tout l'état)", order == [P.WELCOME])

tab.sendto(b"\x00\x01garbage", ("127.0.0.1", b.port))
send(P.HELLO, [("f", float(P.PROTO - 1))])
got, _o = drain(0.3)
check("paquet illisible ignoré, template ancien signalé", got[P.WELCOME][3] == "old_template")

# autorisation (appels directs : le pont de test n'écoute qu'en local)
NEW, OTHER, OWN = "192.0.2.50", "192.0.2.51", "192.0.2.99"
hello = encode_message(P.HELLO, [("i", P.PROTO), ("s", "R10")])
b.handle(hello, (NEW, 9301))
b.handle(hello, (NEW, 9301))
check("inconnue : en attente, signalée une fois, pas acceptée", NEW not in b.tablets
      and b.status()["pending"] == [{"ip": NEW, "name": "R10"}] and sum("%s (R10) en attente" % NEW in m for m in logs) == 1)
b.handle(encode_message(P.SYNC, []), (NEW, 9301))
check("en attente : ses gestes sont ignorés", NEW not in b.tablets)
b.decide(NEW, True)
b.handle(hello, (NEW, 9301))
check("autorisée : acceptée au hello suivant, plus en attente", NEW in b.tablets and NEW in b.allow
      and b.status()["pending"] == [])
b.handle(hello, (OTHER, 9301))
b.decide(OTHER, False)
b.handle(hello, (OTHER, 9301))
check("refusée : ignorée, ni en attente ni acceptée", OTHER not in b.tablets and b.status()["pending"] == []
      and b.status()["denied"] == [OTHER])
b.own = {OWN}
b.handle(hello, (OWN, 9301))
check("adresse réseau du PC : acceptée d'office", OWN in b.tablets)
with b.lock:
    for ip in (NEW, OWN):
        b.tablets.pop(ip, None)

# vue par tablette et gestes (2b)
send("/xgr/view/bank", [("i", 1)])
got, order = drain(0.3)
check("banque 17-32 : titre, vue fixe, tranches de la banque", got.get("/xgr/g/title") == ["Ch 17-32"]
      and got.get("/xgr/view/follow") == [0] and got.get("/xgr/view/bank") == [1])
send("/xgr/view/follow")
got, order = drain(0.3)
check("FOLLOW LV1 : retour à la couche de la LV1", got.get("/xgr/g/title") == ["Ch 1-16"] and got.get("/xgr/view/follow") == [1])
gcalls = []
b.actions = {"gain": lambda idx, db: gcalls.append(("gain", idx, db)), "phantom": lambda idx: gcalls.append(("ph", idx))}
send("/xgr/g/1/r/gain", [("f", 31.5)])
send("/xgr/g/2/m/48v")
drain(0.3)
check("gain et 48V : préampli de la page de la tablette", gcalls == [("gain", 33, 31.5), ("ph", 0)])
send("/xgr/g/7/m/gain", [("f", 20.0)])
got, _o = drain(0.3)
check("voie absente (EXP sans préampli) : message, rien envoyé", got.get(P.NOTIFY) == ["This strip just changed: try again"]
      and len(gcalls) == 2)

# actions : fonction fournie par Gain Recall, erreur renvoyée à la tablette
calls = []
real_parse = P.parse_action
P.parse_action = lambda a, args: ("essai", 7) if a == "/xgr/essai" else real_parse(a, args)
b.actions = {"essai": lambda n: calls.append(n) or "Console not connected"}
send("/xgr/essai")
got, _o = drain(0.3)
check("action appelée, erreur en /xgr/notify", calls == [7] and got.get(P.NOTIFY) == ["Console not connected"])
b.actions = {"essai": lambda n: 1 / 0}
send("/xgr/essai")
got, _o = drain(0.3)
check("action qui plante : message, pont vivant", "Gain Recall error" in got.get(P.NOTIFY, [""])[0] and b.is_alive())
P.parse_action = real_parse


def boom():
    raise RuntimeError("panne")


b.state_fn = boom
send(P.SYNC)
got, _o = drain(0.3)
check("état en erreur : le pont tient (dernier état gardé)", b.is_alive() and any("illisible" in m for m in logs)
      and "/xgr/console" in got)
stt = b.status()
check("diagnostic : écoute, paquets reçus, dernier, autorisées, refusées", stt["listen"].startswith("127.0.0.1:")
      and stt["rx"] > 5 and stt["last"]["ip"] == "127.0.0.1" and stt["allow"] == [NEW] and stt["denied"] == [OTHER]
      and len(stt["tablets"]) == 1)
b.forget_lost(time.time() + P.LOST_S + 1)
check("tablette oubliée après LOST_S", b.snapshot() == [] and any("partie" in m for m in logs))
b.stop()

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
