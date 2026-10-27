"""Test : TouchOSC (3.2) — template généré + pont tablette <-> Gain Recall.
Phase 0 (27/10/2026) : template relu (XML lexml 3, page 2000 x 1200, script Lua avec le protocole, ID uniques, fichier
identique d'une génération à l'autre) ; hello -> welcome ; paquet illisible ignoré ; état en erreur sans tomber ;
tablette oubliée après LOST_S.
Phase 1 (27/10/2026) : état traduit en messages, TOUT à l'arrivée d'une tablette puis SEULEMENT ce qui change, tout de
nouveau sur /xgr/sync ; actions de la liste fermée, erreur renvoyée en /xgr/notify ; bouton SYNC du template.
Autorisation (décision de Joseph, 27/10) : tablette inconnue en attente (welcome « pending », rien d'autre), oui ->
acceptée, non -> ignorée ; le PC lui-même toujours accepté (127.x ou ses adresses réseau). Adresses de documentation
192.0.2.x pour les fausses tablettes réseau (aucun vrai appareil touché).

    py tests/test_touchosc.py
"""
import os
import socket
import sys
import tempfile
import time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from touchosc import build_tosc, protocol as P, tosc
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

# ── pont, avec une fausse tablette
tab = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tab.bind(("127.0.0.1", 0))
tab.settimeout(0.5)
logs = []
state = {"connected": True, "info": {"name": "X32RACK-JS"}, "exp_map": {0: 1}, "lv1_count": 64}
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
check("changement : seulement le message concerné", order == ["/xgr/lv1"] and got["/xgr/lv1"][0].startswith("80 LV1"))
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
