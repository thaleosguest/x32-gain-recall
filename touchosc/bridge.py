"""touchosc/bridge.py — pont UDP entre les tablettes TouchOSC et Gain Recall (3.2, plan validé par Joseph le 27/10/2026).

Un fil : écoute PORT_IN, retient chaque tablette à son /xgr/hello (IP, nom, protocole, dernier contact) et lui
répond sur PORT_OUT. L'état de Gain Recall vient de `state_fn` (fournie par x32_gain_recall : rien d'importé d'ici,
testable avec une fausse fonction). Phase 0 : présence seulement (protocol.py).
"""
import socket
import threading
import time

from lv1.osc_sniffer import decode_message, encode_message
from . import protocol as P


class Bridge(threading.Thread):
    STATE_EVERY = 1.0        # s : état relu au plus une fois par seconde pour les réponses

    def __init__(self, version, state_fn=lambda: {}, port=P.PORT_IN, reply_port=P.PORT_OUT, bind="0.0.0.0",
                 log=print):
        super().__init__(daemon=True, name="touchosc")
        self.version, self.state_fn, self.reply_port, self.log = version, state_fn, reply_port, log
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind, port))
        self.sock.settimeout(0.5)
        self.port = self.sock.getsockname()[1]
        self.lock = threading.Lock()
        self.tablets = {}        # ip -> {"name", "proto", "seen"}
        self._state, self._state_t = {}, 0.0
        self._stop = threading.Event()

    def state(self):
        now = time.time()
        if now - self._state_t >= self.STATE_EVERY:
            try:
                self._state = self.state_fn() or {}
            except Exception as e:          # l'état de Gain Recall ne doit jamais faire tomber le pont
                self.log("TouchOSC : état illisible (%r)" % e)
            self._state_t = now
        return self._state

    def send(self, ip, address, args):
        try:
            self.sock.sendto(encode_message(address, args), (ip, self.reply_port))
        except OSError as e:
            self.log("TouchOSC : envoi à %s impossible (%s)" % (ip, e))

    def handle(self, data, addr):
        try:
            address, args = decode_message(data)
        except (ValueError, IndexError, UnicodeError):
            return
        ip = addr[0]
        if address == P.HELLO:
            hello = P.parse_hello(args)
            if hello is None:
                return
            proto, name = hello
            with self.lock:
                new = ip not in self.tablets
                self.tablets[ip] = {"name": name, "proto": proto, "seen": time.time()}
            if new:
                self.log("TouchOSC : tablette %s (%s, protocole %d%s)" % (
                    ip, name, proto, "" if proto == P.PROTO else ", attendu %d" % P.PROTO))
            self.send(ip, *P.welcome(proto, self.version, self.state()))

    def forget_lost(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            for ip in [ip for ip, t in self.tablets.items() if now - t["seen"] > P.LOST_S]:
                del self.tablets[ip]
                self.log("TouchOSC : tablette %s partie" % ip)

    def snapshot(self):
        """Tablettes vues : [{"ip", "name", "proto"}] (pour /api/state, plus tard)."""
        with self.lock:
            return [{"ip": ip, "name": t["name"], "proto": t["proto"]} for ip, t in sorted(self.tablets.items())]

    def run(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65536)
            except socket.timeout:
                self.forget_lost()
                continue
            except OSError:
                if self._stop.is_set():
                    break
                # Windows : ICMP « port injoignable » d'un envoi précédent (WSAECONNRESET, tablette partie) : on continue
                time.sleep(0.01)
                continue
            self.handle(data, addr)
            self.forget_lost()

    def stop(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


def start(version, state_fn, port=P.PORT_IN, bind="0.0.0.0", log=print):
    """Pont démarré, ou None (port pris, réseau absent) : Gain Recall continue sans tablette. bind 127.0.0.1 avec
    --local-only (comme l'interface web)."""
    try:
        b = Bridge(version, state_fn, port=port, bind=bind, log=log)
    except OSError as e:
        log("TouchOSC : port UDP %d indisponible (%s), tablette désactivée" % (port, e))
        return None
    b.start()
    log("TouchOSC : en écoute sur le port UDP %d (réponses vers le port %d de la tablette)" % (b.port, b.reply_port))
    return b
