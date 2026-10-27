"""touchosc/bridge.py — pont UDP entre les tablettes TouchOSC et Gain Recall (3.2, plan validé par Joseph le 27/10/2026).

Un fil : écoute PORT_IN (127.0.0.1 par défaut : TouchOSC du PC en serveur, tablettes en clients de TouchOSC ; réseau
avec --touchosc-lan, expéditeurs limités à une liste), retient chaque tablette à son /xgr/hello et lui répond sur
PORT_OUT. Toutes les PUBLISH_EVERY s, l'état de Gain Recall (`state_fn`) est traduit en messages
(protocol.state_messages) et chaque tablette ne reçoit que ce qui a changé pour ELLE (tout à son arrivée ou sur
/xgr/sync). Les gestes passent par protocol.parse_action (liste fermée) puis par `actions` {nom: fonction} fournies
par x32_gain_recall (mêmes fonctions que l'API web : rien d'importé d'ici, testable avec des fausses).
"""
import socket
import threading
import time

from lv1.osc_sniffer import decode_message, encode_message
from . import protocol as P


class Bridge(threading.Thread):
    PUBLISH_EVERY = 0.1      # s : état relu et différences envoyées au plus 10 fois par seconde

    def __init__(self, version, state_fn=lambda: {}, port=P.PORT_IN, reply_port=P.PORT_OUT, bind="127.0.0.1",
                 allow=(), actions=None, log=print):
        super().__init__(daemon=True, name="touchosc")
        self.version, self.state_fn, self.reply_port, self.log = version, state_fn, reply_port, log
        self.allow, self.actions = set(allow or ()), dict(actions or {})
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind, port))
        self.sock.settimeout(0.05)
        self.port = self.sock.getsockname()[1]
        self.lock = threading.Lock()
        self.tablets = {}        # ip -> {"name", "proto", "seen", "sent": {adresse: arguments déjà envoyés}}
        self.refused = set()     # adresses refusées déjà signalées au journal
        self.rx, self.last_rx = 0, None   # diagnostic (27/10, R10 muette) : paquets reçus, dernier (ip, adresse, instant)
        self._state, self._published = {}, 0.0
        self._stop = threading.Event()

    # -- état ---------------------------------------------------------------
    def read_state(self):
        try:
            self._state = self.state_fn() or {}
        except Exception as e:              # l'état de Gain Recall ne doit jamais faire tomber le pont
            self.log("TouchOSC : état illisible (%r)" % e)
        return self._state

    def publish(self, force_ip=None):
        """Envoie à chaque tablette les messages d'état qui ont changé pour elle (force_ip : tout, à celle-là)."""
        with self.lock:
            ips = list(self.tablets)
        if not ips:
            return 0
        msgs = P.state_messages(self.read_state(), tablets=len(ips))
        n = 0
        for ip in ips:
            with self.lock:
                t = self.tablets.get(ip)
                if t is None:
                    continue
                if ip == force_ip:
                    t["sent"] = {}
                todo = [(a, args) for a, args in sorted(msgs.items()) if t["sent"].get(a) != args]
                for a, args in todo:
                    t["sent"][a] = args
            for a, args in todo:
                self.send(ip, a, list(args))
            n += len(todo)
        return n

    def send(self, ip, address, args):
        try:
            self.sock.sendto(encode_message(address, args), (ip, self.reply_port))
        except OSError as e:
            self.log("TouchOSC : envoi à %s impossible (%s)" % (ip, e))

    def notify(self, ip, text):
        self.send(ip, P.NOTIFY, [("s", text)])

    # -- réception ----------------------------------------------------------
    def handle(self, data, addr):
        try:
            address, args = decode_message(data)
        except (ValueError, IndexError, UnicodeError):
            return
        ip = addr[0]
        self.rx += 1
        self.last_rx = (ip, address, time.time())
        if not P.allowed(ip, self.allow):
            if ip not in self.refused:
                self.refused.add(ip)
                self.log("TouchOSC : %s refusée (pas dans --touchosc-allow)" % ip)
            return
        if address == P.HELLO:
            hello = P.parse_hello(args)
            if hello is None:
                return
            proto, name = hello
            with self.lock:
                new = ip not in self.tablets
                if new:
                    self.tablets[ip] = {"sent": {}}
                self.tablets[ip].update(name=name, proto=proto, seen=time.time())
            if new:
                self.log("TouchOSC : tablette %s (%s, protocole %d%s)" % (
                    ip, name, proto, "" if proto == P.PROTO else ", attendu %d" % P.PROTO))
            self.send(ip, *P.welcome(proto, self.version, self._state if not new else self.read_state()))
            if new:
                self.publish(force_ip=ip)
            return
        with self.lock:
            known = ip in self.tablets
        if not known:                        # geste avant le 1er hello : ignoré (la tablette s'annonce chaque seconde)
            return
        act = P.parse_action(address, args)
        if act is None:
            return
        if act[0] == "sync":
            self.publish(force_ip=ip)
            return
        fn = self.actions.get(act[0])
        if fn is None:
            return
        try:
            err = fn(*act[1:])
        except Exception as e:
            err = "Gain Recall error: %s" % e
            self.log("TouchOSC : action %s en erreur (%r)" % (act[0], e))
        if err:
            self.notify(ip, str(err))
        self._published = 0.0                # retour visible tout de suite

    def forget_lost(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            for ip in [ip for ip, t in self.tablets.items() if now - t["seen"] > P.LOST_S]:
                del self.tablets[ip]
                self.log("TouchOSC : tablette %s partie" % ip)

    def snapshot(self):
        """Tablettes vues : [{"ip", "name", "proto"}]."""
        with self.lock:
            return [{"ip": ip, "name": t["name"], "proto": t["proto"]} for ip, t in sorted(self.tablets.items())]

    def status(self):
        """État du pont pour /api/state["touchosc"] : écoute, tablettes, refusées, paquets reçus et dernier reçu."""
        last = self.last_rx
        return {"listen": "%s:%d" % (self.sock.getsockname()[0], self.port), "reply_port": self.reply_port,
                "allow": sorted(self.allow), "tablets": self.snapshot(), "refused": sorted(self.refused),
                "rx": self.rx, "last": {"ip": last[0], "address": last[1], "ago": round(time.time() - last[2], 1)}
                if last else None}

    def run(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65536)
                self.handle(data, addr)
            except socket.timeout:
                pass
            except OSError:
                if self._stop.is_set():
                    break
                # Windows : ICMP « port injoignable » d'un envoi précédent (WSAECONNRESET, tablette partie) : on continue
                time.sleep(0.01)
            now = time.time()
            if now - self._published >= self.PUBLISH_EVERY:
                self._published = now
                self.forget_lost(now)
                self.publish()

    def stop(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


def start(version, state_fn, port=P.PORT_IN, lan=False, allow=(), actions=None, log=print):
    """Pont démarré, ou None (port pris, réseau absent) : Gain Recall continue sans tablette. Local (127.0.0.1) par
    défaut ; lan : toutes les interfaces, expéditeurs limités à `allow` (+ le PC lui-même)."""
    try:
        b = Bridge(version, state_fn, port=port, bind="0.0.0.0" if lan else "127.0.0.1", allow=allow,
                   actions=actions, log=log)
    except OSError as e:
        log("TouchOSC : port UDP %d indisponible (%s), tablette désactivée" % (port, e))
        return None
    b.start()
    log("TouchOSC : en écoute sur le port UDP %d%s (réponses vers le port %d)" % (
        b.port, " (réseau, autorisées : %s)" % (", ".join(sorted(b.allow)) or "aucune") if lan else " (local)",
        b.reply_port))
    return b
