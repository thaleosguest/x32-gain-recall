"""Test : touchosc/mdns.py — annonce Zeroconf `_osc._udp` de Gain Recall (28/10/2026), pour « Browse » de TouchOSC.
- noms encodés / décodés (pointeurs de compression), requête lue, réponse ignorée ;
- adresse donnée = celle du réseau de celui qui demande (Wi-Fi, pas l'Ethernet SoundGrid) ;
- PTR du type -> PTR + SRV (port) + TXT + A ; instance, hôte, méta-requête ; rien pour un autre type ;
- requête « legacy » de bout en bout sur 127.0.0.1 (sans multicast) : même id, question recopiée.
Vérifié aussi à la main le 28/10 sur le réseau réel du PC (réponse reçue en multicast, à côté de celle de TouchOSC).

    py tests/test_mdns.py
"""
import os
import socket
import struct
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from touchosc import mdns as M

ok, why = True, []
def check(name, cond):
    global ok
    if not cond: why.append(name)
    ok = ok and cond


def query(labels, qtype, qid=7, qu=False):
    return struct.pack("!HHHHHH", qid, 0, 1, 0, 0, 0) + M.encode_name(labels) + struct.pack("!HH", qtype, 1 | (M.QU if qu else 0))


def parse(data):
    """[(nom, type, valeur)] de toutes les sections d'une réponse."""
    qid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    off, out = 12, []
    for _ in range(qd):
        _l, off = M.decode_name(data, off)
        off += 4
    for _ in range(an + ns + ar):
        name, off = M.decode_name(data, off)
        t, _c, _ttl, ln = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        if t == M.T_PTR:
            v = M.decode_name(data, off)[0]
        elif t == M.T_SRV:
            v = struct.unpack("!H", data[off + 4:off + 6])[0]
        elif t == M.T_A:
            v = socket.inet_ntoa(data[off:off + 4])
        else:
            v = data[off:off + ln]
        out.append((name, t, v))
        off += ln
    return qid, qd, out


raw = M.encode_name(("a", "_osc", "_udp", "local"))
pointer = raw + struct.pack("!H", 0xC000 | 2)                 # 2e nom = pointeur vers « _osc._udp.local »
check("noms : encodage, décodage, pointeur de compression", M.decode_name(raw, 0) == (("a", "_osc", "_udp", "local"), len(raw))
      and M.decode_name(pointer, len(raw)) == (("_osc", "_udp", "local"), len(raw) + 2))
check("requête lue (QU), réponse ignorée", M.parse_query(query(M.SERVICE, M.T_PTR, qu=True)) == (7, [(M.SERVICE, M.T_PTR, True)])
      and M.parse_query(struct.pack("!HHHHHH", 0, 0x8400, 0, 0, 0, 0)) is None and M.parse_query(b"\x00") is None)
addrs = ["100.113.68.110", "192.168.1.16", "192.168.10.5"]
check("adresse du réseau de celui qui demande", M.best_local("192.168.1.20", addrs) == "192.168.1.16"
      and M.best_local("192.168.10.40", addrs) == "192.168.10.5" and M.best_local("100.64.1.2", addrs) == "100.113.68.110"
      and M.best_local("x", addrs) == addrs[0] and M.best_local("1.2.3.4", []) is None)

r = M.Responder("XM32 Gain Recall (TEST)", 9300, log=lambda m: None, mdns_port=0, addrs_fn=lambda: ["127.0.0.1"],
                multicast=False)
inst = tuple(x.lower() for x in r.inst)
ans, add = r.answer([(M.SERVICE, M.T_PTR, False)], "192.168.1.16")
check("PTR du type : instance en réponse, SRV + TXT + A en compléments", len(ans) == 1 and len(add) == 3
      and parse(M.message(0, ans, add))[2] == [(M.SERVICE, M.T_PTR, inst), (inst, M.T_SRV, 9300), (inst, M.T_TXT,
      b"\x15app=X/M32 Gain Recall"), (r.host, M.T_A, "192.168.1.16")])
check("instance (SRV), hôte (A), méta-requête ; autre type : rien",
      [x[1] for x in parse(M.message(0, *r.answer([(inst, M.T_SRV, False)], "10.0.0.1")))[2]] == [M.T_SRV, M.T_A]
      and parse(M.message(0, *r.answer([(r.host, M.T_A, False)], "10.0.0.1")))[2] == [(r.host, M.T_A, "10.0.0.1")]
      and parse(M.message(0, *r.answer([(M.META, M.T_PTR, False)], "10.0.0.1")))[2] == [(M.META, M.T_PTR, M.SERVICE)]
      and r.answer([(("_http", "_tcp", "local"), M.T_PTR, False)], "10.0.0.1") == ([], []))
r.start()
q = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
q.settimeout(2.0)
q.sendto(query(M.SERVICE, M.T_PTR, qid=0x4242), ("127.0.0.1", r.sock.getsockname()[1]))
try:
    data, _src = q.recvfrom(9000)
    qid, qd, recs = parse(data)
except socket.timeout:
    qid, qd, recs = None, 0, []
r.stop()
check("requête legacy de bout en bout : même id, question recopiée, port et adresse",
      qid == 0x4242 and qd == 1 and (inst, M.T_SRV, 9300) in recs and (r.host, M.T_A, "127.0.0.1") in recs)
check("nom d'hôte propre", M.host_label("PC Portable_JS") == "xm32-gain-recall-pc-portable-js")

print("OK" if ok else "ÉCHEC : " + ", ".join(why))
sys.exit(0 if ok else 1)
