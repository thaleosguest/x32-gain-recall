"""Test : TouchOSC phase 0 (3.2, 27/10/2026) — template généré + présence tablette <-> Gain Recall.
- template : XML lexml 3 relu, page 2000 x 1200, voyant / état / détail, script Lua avec le protocole, aucun jeton
  oublié, ID uniques, fichier identique d'une génération à l'autre ;
- protocole : hello en entier ou en réel, état du template (à jour / trop ancien / trop récent), texte de la console ;
- pont : une fausse tablette (UDP local) envoie /xgr/hello -> /xgr/welcome reçu sur son port, avec la console ;
  paquet illisible ignoré, état de Gain Recall en erreur sans tomber, tablette oubliée après LOST_S.

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
check("voyant, état, détail présents", {"led", "status", "detail"} <= set(names))
check("ID uniques", len({n.get("ID") for n in nodes}) == len(nodes))
script = rp["script"]
check("Lua : protocole et ports remplacés", "local PROTO = %d" % P.PROTO in script and str(P.PORT_IN) in script
      and "__" not in script)
check("Lua : hello et welcome", "sendOSC('/xgr/hello'" in script and "'/xgr/welcome'" in script)
st = names["status"]
check("état = LABEL avec un texte", st.get("type") == "LABEL"
      and any(v.find("key").text == "text" for v in st.find("values")))

# ── protocole
check("hello entier", P.parse_hello([("i", 1), ("s", "R10")]) == (1, "R10"))
check("hello réel (Lua)", P.parse_hello([("f", 1.0)]) == (1, "TouchOSC"))
check("hello mal formé", P.parse_hello([("s", "x")]) is None and P.parse_hello([]) is None)
check("template à jour / ancien / récent", (P.template_state(P.PROTO), P.template_state(P.PROTO - 1),
      P.template_state(P.PROTO + 1)) == ("ok", "old_template", "new_template"))
check("console", P.console_text({"connected": True, "info": {"name": "X32RACK-JS"}}) == "X32RACK-JS"
      and P.console_text({"connected": False}) == "No console" and P.console_text(None) == "No console")

# ── pont, avec une fausse tablette
tab = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
tab.bind(("127.0.0.1", 0))
tab.settimeout(2.0)
logs = []
state = {"connected": True, "info": {"name": "X32RACK-JS"}}
b = Bridge("3.2.0-a1", lambda: state, port=0, reply_port=tab.getsockname()[1], bind="127.0.0.1", log=logs.append)
b.start()


def ask(args):
    tab.sendto(encode_message(P.HELLO, args), ("127.0.0.1", b.port))
    return decode_message(tab.recv(65536))


addr, args = ask([("i", P.PROTO), ("s", "R10")])
check("welcome reçu", addr == P.WELCOME and [v for _t, v in args] == [P.PROTO, "3.2.0-a1", "X32RACK-JS", "ok"])
check("tablette retenue", b.snapshot() == [{"ip": "127.0.0.1", "name": "R10", "proto": P.PROTO}]
      and any("tablette 127.0.0.1" in m for m in logs))
tab.sendto(b"\x00\x01garbage", ("127.0.0.1", b.port))
addr, args = ask([("f", float(P.PROTO - 1))])
check("paquet illisible ignoré, template ancien signalé", args[3][1] == "old_template")


def boom():
    raise RuntimeError("panne")


b.state_fn, b._state_t = boom, 0.0
addr, args = ask([("i", P.PROTO)])
check("état en erreur : le pont répond quand même", addr == P.WELCOME and any("illisible" in m for m in logs))
b.forget_lost(time.time() + P.LOST_S + 1)
check("tablette oubliée après LOST_S", b.snapshot() == [] and any("partie" in m for m in logs))
b.stop()

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
