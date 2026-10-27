"""touchosc/bridge.py — pont UDP entre les tablettes TouchOSC et Gain Recall (3.2, plan validé par Joseph le 27/10/2026).

Un fil : écoute PORT_IN (réseau par défaut, décision de Joseph du 27/10 ; 127.0.0.1 avec --touchosc-local), retient
chaque tablette AUTORISÉE à son /xgr/hello et lui répond sur PORT_OUT. Le PC lui-même est toujours accepté ; une
inconnue est mise en attente (`pending`, welcome « pending », rien d'autre) jusqu'à `decide(ip, oui/non)` (question
« Autoriser la tablette ? » du float) ; refusée = ignorée jusqu'au prochain lancement. Toutes les PUBLISH_EVERY s, l'état de Gain Recall (`state_fn`) est traduit en messages
(protocol.state_messages) et chaque tablette ne reçoit que ce qui a changé pour ELLE (tout à son arrivée ou sur
/xgr/sync). Les gestes passent par protocol.parse_action (liste fermée) puis par `actions` {nom: fonction} fournies
par x32_gain_recall (mêmes fonctions que l'API web : rien d'importé d'ici, testable avec des fausses).
"""
import socket
import threading
import time

from lv1.osc_sniffer import decode_message, encode_message
from . import protocol as P
from . import views


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
        # ip -> {"name", "proto", "seen", "sent": {adresse: arguments déjà envoyés}, "view": None (suit la LV1) ou
        # banque 0..4, "page": dernière page GAINS envoyée (pour traduire ses gestes en préamplis)}
        self.tablets = {}
        self.pending = {}        # ip -> {"name", "seen"} : tablettes inconnues qui attendent une réponse
        self.denied = set()      # refusées pendant ce lancement
        self.own = local_addresses()
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
            views_of = {ip: t.get("view") for ip, t in self.tablets.items()}
        if not views_of:
            return 0
        state = self.read_state()
        built = {}                           # vue -> (page, messages) : calculés une fois par vue
        for v in set(views_of.values()):
            page = views.gain_page(state, bank=v)
            built[v] = (page, P.state_messages(state, tablets=len(views_of), page=page))
        n = 0
        for ip, v in views_of.items():
            page, msgs = built[v]
            with self.lock:
                t = self.tablets.get(ip)
                if t is None:
                    continue
                t["page"] = page
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
        if not P.allowed(ip, self.allow, self.own):
            if ip in self.denied or address != P.HELLO:
                return
            hello = P.parse_hello(args)
            if hello is None:
                return
            with self.lock:
                new = ip not in self.pending
                self.pending[ip] = {"name": hello[1], "seen": time.time()}
            if new:
                self.log("TouchOSC : tablette %s (%s) en attente d'autorisation" % (ip, hello[1]))
            self.send(ip, *P.welcome(hello[0], self.version, {}, pending=True))
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
        if act[0] in ("bank", "follow"):         # vue de CETTE tablette : la couche de la LV1 ne bouge pas
            with self.lock:
                if ip in self.tablets:            # (oubliée entre-temps : rien)
                    self.tablets[ip]["view"] = act[1] if act[0] == "bank" else None
            self._published = 0.0
            return
        params = act[1:]
        if act[0] in ("gain", "phantom"):         # voie de la page que CETTE tablette affiche -> préampli
            with self.lock:
                page = (self.tablets.get(ip) or {}).get("page")
            idx = views.unit_idx(page, act[1], act[2])
            if idx is None:
                self.notify(ip, "This strip just changed: try again")
                return
            params = (idx,) + tuple(act[3:])
        fn = self.actions.get(act[0])
        if fn is None:
            return
        try:
            err = fn(*params)
        except Exception as e:
            err = "Gain Recall error: %s" % e
            self.log("TouchOSC : action %s en erreur (%r)" % (act[0], e))
        if err:
            self.notify(ip, str(err))
        self._published = 0.0                # retour visible tout de suite

    def decide(self, ip, ok):
        """Réponse à « Autoriser la tablette ? » : oui -> acceptée (elle reçoit tout à son prochain hello), non ->
        ignorée jusqu'au prochain lancement. La liste retenue est enregistrée par x32_gain_recall."""
        with self.lock:
            self.pending.pop(ip, None)
            if ok:
                self.allow.add(ip)
                self.denied.discard(ip)
            else:
                self.denied.add(ip)
                self.allow.discard(ip)
                self.tablets.pop(ip, None)
        self.log("TouchOSC : tablette %s %s" % (ip, "autorisée" if ok else "refusée (jusqu'au prochain lancement)"))

    def forget_lost(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            for ip in [ip for ip, t in self.tablets.items() if now - t["seen"] > P.LOST_S]:
                del self.tablets[ip]
                self.log("TouchOSC : tablette %s partie" % ip)
            for ip in [ip for ip, t in self.pending.items() if now - t["seen"] > P.LOST_S]:
                del self.pending[ip]           # partie sans réponse : la question tombe

    def snapshot(self):
        """Tablettes vues : [{"ip", "name", "proto"}]."""
        with self.lock:
            return [{"ip": ip, "name": t["name"], "proto": t["proto"]} for ip, t in sorted(self.tablets.items())]

    def status(self):
        """État du pont pour /api/state["touchosc"] : écoute, autorisées, tablettes, en attente (question du float),
        refusées, paquets reçus et dernier reçu."""
        last = self.last_rx
        with self.lock:
            pending = [{"ip": ip, "name": t["name"]} for ip, t in sorted(self.pending.items())]
            allow, denied = sorted(self.allow), sorted(self.denied)
        return {"listen": "%s:%d" % (self.sock.getsockname()[0], self.port), "reply_port": self.reply_port,
                "allow": allow, "tablets": self.snapshot(), "pending": pending, "denied": denied,
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


def local_addresses():
    """Adresses IPv4 de ce PC (Wi-Fi, Ethernet, Tailscale…) : un TouchOSC du PC qui passe par l'une d'elles est accepté."""
    try:
        return set(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        return set()


def start(version, state_fn, port=P.PORT_IN, lan=True, allow=(), actions=None, log=print):
    """Pont démarré, ou None (port pris, réseau absent) : Gain Recall continue sans tablette. Réseau par défaut,
    tablettes limitées à `allow` (+ le PC lui-même, + celles autorisées ensuite) ; lan False : 127.0.0.1 seulement."""
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
