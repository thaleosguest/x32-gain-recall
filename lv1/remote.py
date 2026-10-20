"""lv1/remote.py — Télécommande OSC de la LV1 (3.1, PATCH DE SCÈNE) : renommer un canal d'entrée.

Protocole « MyFOH » (le même que l'appli iPad et le module Companion, voir lv1/osc_sniffer.py) :
  - découverte : la LV1 annonce `/zDNS` en multicast UDP 225.1.1.1:13337 (service `_waveslv113._tcp`, nom du PC,
    port TCP qui CHANGE à chaque session : relevé 51557 le 20/10/2026) ;
  - TCP : [longueur BE][8 octets d'en-tête][OSC] ; /handshake + /device_name ; /ping -> /pong obligatoire ;
  - `/Set/TrackName [i groupe, i canal 0-based, s nom]` (action « Rename » de Companion ; groupe 0 = entrées) ;
  - couleur : LECTURE seulement, `/Notify/TrackColor [i groupe, i canal, i n° de palette, f r, f g, f b]` (P170 ST =
    19 = #FF4F4F de lv1/channelinfo.PALETTE). PAS d'écriture possible en LV1 V17 (relevé le 20/10/2026) : le service
    de télécommande (MyMonService.dll) accepte `/Set/TrackColor [i, i, i, f, f, f]` et appelle
    `WCRx_ExternalService::SetTrackColor` de MixerController_MyMon_Control.dll, qui ne fait que `return 6` (non
    implémenté) ; essai chez Joseph : In 80 renommé, couleur inchangée (OSC et base). À revérifier après une mise à
    jour de la LV1 (code de SetTrackColor), pas avant.

On n'écrit JAMAIS dans la base de la LV1 : uniquement par ces messages, comme une télécommande.

Essais (racine du repo) :
    py -m lv1.remote --discover               trouver la LV1 (adresse, port)
    py -m lv1.remote --dump                   noms + couleurs des canaux d'entrée vus par OSC
    py -m lv1.remote --name 80 "Essai"        renommer In 80
"""
import socket
import struct
import sys
import threading
import time
import uuid as uuid_mod

from .osc_sniffer import encode_message, decode_message, HEADER, HEADER_LEN

MCAST_GROUP, MCAST_PORT = "225.1.1.1", 13337
SERVICE = "_waveslv113._tcp"
GROUP_INPUT = 0
DEVICE_NAME = "X32 Gain Recall"


def _local_ipv4():
    try:
        return set(socket.gethostbyname_ex(socket.gethostname())[2]) | {"127.0.0.1"}
    except OSError:
        return {"127.0.0.1"}


def parse_zdns(args, src_ip=None):
    """Annonce /zDNS -> {"host", "port", "ips", "name", "uuid"} ou None (autre service)."""
    vals = [v for _t, v in args]
    if len(vals) < 2 or vals[0] != SERVICE:
        return None
    port, name, ips = None, None, []
    for t, v in args[2:]:
        if t == "i" and port is None and 1025 < v < 65535:
            port = v
        elif t == "s" and v:
            if v.count(".") == 3 and all(p.isdigit() for p in v.split(".")):
                ips.append(v)
            elif ":" not in v and name is None:
                name = v
    if not port:
        return None

    def rank(ip):
        return (100 if ip.startswith("192.168.") and not ip.startswith("192.168.56.") else 90 if ip.startswith("10.")
                else -50 if ip.startswith("169.254.") else -100 if ip.startswith("127.") else 40)
    ips.sort(key=rank, reverse=True)
    local = _local_ipv4()
    if (name and name.lower() == socket.gethostname().lower()) or (src_ip in local) or local & set(ips):
        host = "127.0.0.1"                      # la LV1 tourne sur ce PC (cas normal : même machine que l'appli)
    else:
        host = ips[0] if ips else src_ip
    return {"host": host, "port": port, "ips": ips, "name": name, "uuid": vals[1]}


def discover(timeout=4.0):
    """Écoute les annonces de la LV1 pendant ``timeout`` s ; rend la 1re trouvée (dict de parse_zdns) ou None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", MCAST_PORT))
        for ip in _local_ipv4():
            try:
                s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                             socket.inet_aton(MCAST_GROUP) + socket.inet_aton(ip))
            except OSError:
                pass
        s.settimeout(0.5)
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = s.recvfrom(8192)
            except socket.timeout:
                continue
            try:
                address, args = decode_message(data)
            except Exception:
                continue
            if address == "/zDNS":
                found = parse_zdns(args, addr[0])
                if found:
                    return found
    except OSError:
        return None
    finally:
        s.close()
    return None


class LV1Remote:
    """Connexion OSC tenue sur un fil : découverte, poignée de main, ping/pong, reconnexion. Thread-safe pour
    rename(). Garde les noms / couleurs reçus (canal 1-based) : ``names``, ``colors``."""

    def __init__(self, host=None, port=None, device_name=DEVICE_NAME, log=print):
        self.fixed = (host, port) if host and port else None
        self.addr = self.fixed
        self.device_name = device_name
        self.uuid = str(uuid_mod.uuid4()).upper()
        self.log = log
        self.sock = None
        self.registered = False
        self.lock = threading.Lock()
        self.names, self.colors = {}, {}
        self.color_events = []           # [(canal, n° de palette, heure)] : changements vus (lv1/colorclick.py)
        self.error = None
        self._stop = False

    # -- état ---------------------------------------------------------------
    def connected(self):
        return self.sock is not None and self.registered

    def status(self):
        return {"connected": self.connected(), "host": self.addr[0] if self.addr else None,
                "port": self.addr[1] if self.addr else None, "error": self.error}

    # -- envoi --------------------------------------------------------------
    def _send(self, msgs):
        frames = b"".join(struct.pack(">I", len(p)) + HEADER + p for p in (encode_message(a, x) for a, x in msgs))
        with self.lock:
            if self.sock is None:
                raise OSError("LV1 non connectée")
            self.sock.sendall(frames)

    def rename(self, ch, name):
        """Renomme le canal d'entrée ch (1-based)."""
        self._send([("/Set/TrackName", [("i", GROUP_INPUT), ("i", int(ch) - 1), ("s", str(name))])])
        self.names[int(ch)] = str(name)

    def request_state(self):
        self._send([("/Get/Aux/Tracks", []), ("/Get/Layers", [("i", 0), ("i", 0)])])

    # -- connexion ----------------------------------------------------------
    def connect_once(self, timeout=5.0):
        if not self.fixed:
            found = discover(timeout)
            if not found:
                raise OSError("LV1 introuvable sur le réseau (annonce /zDNS)")
            self.addr = (found["host"], found["port"])
        s = socket.create_connection(self.addr, timeout=timeout)
        s.settimeout(0.5)
        with self.lock:
            self.sock, self.registered = s, False
        self._send([("/handshake", [("i", 1), ("i", -1), ("i", 1)]),
                    ("/device_name", [("s", self.device_name), ("s", self.uuid)])])
        end = time.time() + timeout
        buf = b""
        while time.time() < end and not self.registered:
            buf = self._pump(buf)
        if not self.registered:
            self.close()
            raise OSError("pas de réponse de la LV1 à la poignée de main")
        self.error = None
        self._buf = buf
        return self

    def _pump(self, buf):
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return buf
        if not chunk:
            raise OSError("connexion fermée par la LV1")
        buf += chunk
        while len(buf) >= 4 + HEADER_LEN:
            size = struct.unpack_from(">I", buf, 0)[0]
            if size == 0 or size > 16 * 1024 * 1024:
                buf = buf[1:]
                continue
            total = 4 + HEADER_LEN + size
            if len(buf) < total:
                break
            payload, buf = buf[4 + HEADER_LEN:total], buf[total:]
            try:
                address, args = decode_message(payload)
            except Exception:
                continue
            self._handle(address, args)
        return buf

    def _handle(self, address, args):
        v = [x for _t, x in args]
        if address == "/ping":
            self._send([("/pong", args)])
        elif address == "/handshake" and v[:1] == [1]:
            self.registered = True
        elif address in ("/Notify/Track/Name", "/Notify/TrackName") and len(v) >= 3 and v[0] == GROUP_INPUT:
            self.names[v[1] + 1] = v[2]
        elif address == "/Notify/TrackColor" and len(v) >= 3 and v[0] == GROUP_INPUT:
            self.colors[v[1] + 1] = v[2]
            self.color_events.append((v[1] + 1, v[2], time.time()))
            del self.color_events[:-500]
        elif address == "/Channels" and v:
            for k in range(int(v[0])):              # 19 valeurs par piste : nom, groupe, canal, ...
                rec = v[1 + 19 * k: 1 + 19 * (k + 1)]
                if len(rec) >= 3 and rec[1] == GROUP_INPUT:
                    self.names[rec[2] + 1] = rec[0]

    def run_forever(self, retry=5.0):
        """Fil de fond : connexion tenue, reconnexion (nouvelle découverte : le port change à chaque session)."""
        buf = getattr(self, "_buf", b"")      # connect_once() déjà fait par l'appelant (lv1-colors, 3.1)
        while not self._stop:
            try:
                if self.sock is None:
                    self.connect_once()
                    self.log("LV1 OSC : connectée (%s:%s)" % self.addr)
                    buf = self._buf
                else:
                    buf = self._pump(buf)
            except OSError as e:
                if self.error != str(e):
                    self.log("LV1 OSC : %s" % e)
                self.error = str(e)
                self.close()
                if not self.fixed:
                    self.addr = None
                t = time.time() + retry
                while time.time() < t and not self._stop:
                    time.sleep(0.2)

    def start(self):
        threading.Thread(target=self.run_forever, daemon=True, name="lv1-remote").start()
        return self

    def close(self):
        with self.lock:
            s, self.sock, self.registered = self.sock, None, False
        if s:
            try:
                s.close()
            except OSError:
                pass

    def stop(self):
        self._stop = True
        self.close()


def _wait(r, seconds):
    end, buf = time.time() + seconds, r._buf
    while time.time() < end:
        buf = r._pump(buf)
    r._buf = buf


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--discover":
        print(discover(6.0) or "LV1 introuvable")
        return 0
    r = LV1Remote(device_name="X32 Gain Recall (essai)").connect_once()
    print("Connecté à %s:%s" % r.addr)
    if argv[0] == "--dump":
        r.request_state()
        _wait(r, 2.0)
        for ch in sorted(r.names):
            print("In %-3d %-24s couleur n° %s" % (ch, r.names[ch], r.colors.get(ch)))
    elif argv[0] == "--name" and len(argv) >= 3:
        r.rename(int(argv[1]), argv[2])
        _wait(r, 1.0)
        print("Envoyé : In %s -> « %s »" % (argv[1], argv[2]))
    else:
        print(__doc__)
    r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
