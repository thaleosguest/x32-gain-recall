"""touchosc/mdns.py — annonce Zeroconf (mDNS / DNS-SD) du récepteur OSC de Gain Recall (28/10/2026, plug and play).

Dans TouchOSC, Connections > OSC > Browse liste les récepteurs `_osc._udp` du réseau (manuel Hexler) : choisir
« XM32 Gain Recall (PC) » remplit Host et Send Port (le Receive Port 9301 reste à taper : TouchOSC envoie depuis un
autre port que celui où il écoute, vu le 28/10). Décision de Joseph du 28/10 : fait avant la 3.2.0.

Répondeur minimal en Python pur (RFC 6762 / 6763, pas de dépendance) : groupe 224.0.0.251:5353 rejoint sur chaque
interface IPv4 ; réponses aux questions PTR / SRV / TXT / A / ANY sur le type `_osc._udp.local`, l'instance, l'hôte et
`_services._dns-sd._udp.local`. L'adresse donnée (A) est celle du PC sur le réseau de celui qui demande (plus long
préfixe commun) : la tablette en Wi-Fi ne reçoit pas l'adresse Ethernet de la SoundGrid. Annonce au démarrage (2 fois)
et « au revoir » (TTL 0) à l'arrêt. Requête « legacy » (port source ≠ 5353) : réponse directe avec la question.
"""
import re
import socket
import struct
import threading
import time

GROUP, MDNS_PORT = "224.0.0.251", 5353
SERVICE = ("_osc", "_udp", "local")
META = ("_services", "_dns-sd", "_udp", "local")
T_A, T_PTR, T_TXT, T_SRV, T_ANY = 1, 12, 16, 33, 255
TTL_HOST, TTL_OTHER = 120, 4500
FLUSH = 0x8000          # bit « cache-flush » de la classe (enregistrements uniques)
QU = 0x8000             # bit « réponse directe demandée » de la classe d'une question


def local_addresses():
    """Adresses IPv4 utiles de ce PC (ni 127.x, ni 169.254.x)."""
    try:
        addrs = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        addrs = []
    return sorted(a for a in set(addrs) if not a.startswith(("127.", "169.254.")))


def best_local(src, addrs):
    """Adresse de ce PC sur le réseau de `src` (plus long préfixe commun), sinon la première."""
    if not addrs:
        return None
    try:
        s = struct.unpack("!I", socket.inet_aton(src))[0]
    except OSError:
        return addrs[0]

    def common(a):
        x = s ^ struct.unpack("!I", socket.inet_aton(a))[0]
        return 32 - x.bit_length()
    return max(addrs, key=common)


def encode_name(labels):
    out = b""
    for label in labels:
        b = label.encode("utf-8")[:63]
        out += bytes([len(b)]) + b
    return out + b"\x00"


def decode_name(data, off):
    """(étiquettes en minuscules, position après le nom) ; suit les pointeurs de compression."""
    labels, end, jumps = [], None, 0
    while True:
        n = data[off]
        if n & 0xC0 == 0xC0:
            if end is None:
                end = off + 2
            off = ((n & 0x3F) << 8) | data[off + 1]
            jumps += 1
            if jumps > 20:
                raise ValueError("boucle de compression")
            continue
        off += 1
        if n == 0:
            break
        labels.append(data[off:off + n].decode("utf-8", "replace").lower())
        off += n
    return tuple(labels), (end if end is not None else off)


def parse_query(data):
    """(id, [(étiquettes, type, réponse directe demandée)]) d'une requête mDNS ; None pour une réponse ou un paquet
    illisible."""
    try:
        qid, flags, qd = struct.unpack("!HHH", data[:6])
        if flags & 0x8000:
            return None
        off, qs = 12, []
        for _ in range(qd):
            labels, off = decode_name(data, off)
            qtype, qclass = struct.unpack("!HH", data[off:off + 4])
            off += 4
            qs.append((labels, qtype, bool(qclass & QU)))
        return qid, qs
    except (IndexError, struct.error, ValueError):
        return None


def record(labels, rtype, ttl, rdata, flush=False):
    return encode_name(labels) + struct.pack("!HHIH", rtype, 1 | (FLUSH if flush else 0), ttl, len(rdata)) + rdata


def message(qid, answers, additionals=(), questions=()):
    head = struct.pack("!HHHHHH", qid, 0x8400, len(questions), len(answers), 0, len(additionals))
    q = b"".join(encode_name(l) + struct.pack("!HH", t, 1) for l, t in questions)
    return head + q + b"".join(answers) + b"".join(additionals)


def host_label(name):
    return "xm32-gain-recall-" + (re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "pc")


class Responder(threading.Thread):
    def __init__(self, instance, port, log=print, mdns_port=MDNS_PORT, addrs_fn=local_addresses, multicast=True,
                 txt=("app=X/M32 Gain Recall",)):
        super().__init__(daemon=True, name="mdns")
        self.inst = (instance[:63],) + SERVICE
        self.host = (host_label(socket.gethostname()), "local")
        self.port, self.log, self.mdns_port, self.addrs_fn, self.multicast = port, log, mdns_port, addrs_fn, multicast
        self.txt = b"".join(bytes([len(t.encode())]) + t.encode() for t in txt) or b"\x00"
        self.addrs, self.joined = [], set()
        self.answered = 0
        self._stop = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("" if multicast else "127.0.0.1", mdns_port))
        self.sock.settimeout(0.5)
        if multicast:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        self._refresh_addrs()

    # -- enregistrements ----------------------------------------------------
    def records(self, addr, ttl_host=TTL_HOST, ttl_other=TTL_OTHER, flush=True):
        srv = struct.pack("!HHH", 0, 0, self.port) + encode_name(self.host)
        return {"meta": record(META, T_PTR, ttl_other, encode_name(SERVICE)),
                "ptr": record(SERVICE, T_PTR, ttl_other, encode_name(self.inst)),
                "srv": record(self.inst, T_SRV, ttl_host, srv, flush),
                "txt": record(self.inst, T_TXT, ttl_other, self.txt, flush),
                "a": record(self.host, T_A, ttl_host, socket.inet_aton(addr), flush)}

    def answer(self, questions, addr, flush=True):
        """(réponses, compléments) pour ces questions, adresse `addr` dans le A."""
        r = self.records(addr, flush=flush)
        inst = tuple(x.lower() for x in self.inst)
        host = tuple(x.lower() for x in self.host)
        ans, add = [], []
        for labels, qtype, _qu in questions:
            if labels == META and qtype in (T_PTR, T_ANY):
                ans.append(r["meta"])
            elif labels == SERVICE and qtype in (T_PTR, T_ANY):
                ans.append(r["ptr"])
                add += [r["srv"], r["txt"], r["a"]]
            elif labels == inst and qtype in (T_SRV, T_TXT, T_ANY):
                ans += [r["srv"]] if qtype == T_SRV else [r["txt"]] if qtype == T_TXT else [r["srv"], r["txt"]]
                add.append(r["a"])
            elif labels == host and qtype in (T_A, T_ANY):
                ans.append(r["a"])
        uniq = lambda xs: list(dict.fromkeys(xs))
        ans = uniq(ans)
        return ans, [x for x in uniq(add) if x not in ans]

    # -- réseau -------------------------------------------------------------
    def _refresh_addrs(self):
        self.addrs = list(self.addrs_fn())
        if not self.multicast:
            return
        for a in self.addrs:
            if a in self.joined:
                continue
            try:
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                     socket.inet_aton(GROUP) + socket.inet_aton(a))
                self.joined.add(a)
            except OSError as e:
                self.log("Zeroconf : groupe mDNS non rejoint sur %s (%s)" % (a, e))

    def _send_multicast(self, data, addr):
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(addr))
            self.sock.sendto(data, (GROUP, self.mdns_port))
        except OSError:
            pass

    def announce(self, goodbye=False):
        """Annonce non sollicitée sur chaque interface, avec l'adresse de celle-ci (TTL 0 = au revoir)."""
        if not self.multicast:
            return
        for a in self.addrs:
            r = self.records(a, *((0, 0) if goodbye else (TTL_HOST, TTL_OTHER)))
            self._send_multicast(message(0, [r["ptr"], r["srv"], r["txt"], r["a"]]), a)

    def handle(self, data, src):
        q = parse_query(data)
        if not q:
            return
        qid, questions = q
        addr = best_local(src[0], self.addrs)
        if addr is None:
            return
        legacy = src[1] != self.mdns_port
        ans, add = self.answer(questions, addr, flush=not legacy)
        if not ans:
            return
        self.answered += 1
        try:
            if legacy:                       # résolveur simple : réponse directe, même id, question recopiée
                self.sock.sendto(message(qid, ans, add, [(l, t) for l, t, _u in questions]), src)
            elif any(qu for _l, _t, qu in questions) or not self.multicast:
                self.sock.sendto(message(0, ans, add), src)
            else:
                self._send_multicast(message(0, ans, add), addr)
        except OSError:
            pass

    def run(self):
        last_addrs, announced = time.time(), 0
        while not self._stop.is_set():
            now = time.time()
            if announced < 2 and now >= getattr(self, "_next_announce", 0):
                self.announce()
                announced += 1
                self._next_announce = now + 1.0
            if now - last_addrs > 30:            # Wi-Fi reconnecté, nouvelle adresse...
                last_addrs = now
                before = set(self.addrs)
                self._refresh_addrs()
                if set(self.addrs) != before:
                    announced = 0
            try:
                data, src = self.sock.recvfrom(9000)
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                time.sleep(0.5)
                continue
            self.handle(data, src)

    def stop(self):
        self._stop.set()
        self.announce(goodbye=True)
        try:
            self.sock.close()
        except OSError:
            pass


def start(port, log=print):
    """Annonce `_osc._udp` du port `port` de ce PC, ou None (5353 indisponible : Gain Recall continue sans)."""
    try:
        r = Responder("XM32 Gain Recall (%s)" % socket.gethostname(), port, log=log)
    except OSError as e:
        log("Zeroconf : annonce impossible (%s) ; dans TouchOSC, entrer l'adresse du PC à la main" % e)
        return None
    r.start()
    log("Zeroconf : « %s » annoncé (_osc._udp, port %d, adresses %s)" % (r.inst[0], port, ", ".join(r.addrs) or "-"))
    return r
