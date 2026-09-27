#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X32 GAIN RECALL
===============
Petit outil pour regler, sauvegarder et rappeler les GAINS (preamps / headamps)
d'une Behringer X32 / Midas M32 via le protocole OSC (UDP, port 10023).

- Aucune dependance : Python 3.8+ (bibliotheque standard uniquement).
- L'interface s'ouvre dans le navigateur (serveur local 127.0.0.1 uniquement).
- Les scenes de gains sont stockees dans x32_presets.json a cote du script.

Usage :
    python x32_gain_recall.py              # lance l'appli
    python x32_gain_recall.py --sim        # lance avec une X32 simulee (test sans console)
    python x32_gain_recall.py --ip 192.168.1.50

Sources du protocole : "UNOFFICIAL X32/M32 OSC REMOTE PROTOCOL" (P.-G. Maillot), v4.02.
  - /headamp/[000..127]/gain    : float 0..1  <->  -12..+60 dB, pas de 0,5 dB (145 valeurs)
  - /headamp/[000..127]/phantom : int 0/1
  - 000-031 = entrees locales XLR, 032-079 = AES50 A, 080-127 = AES50 B
  - /xremote a renouveler avant 10 s pour recevoir les changements faits sur la console
"""
import argparse
import json
import os
import random
import socket
import struct
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_NAME = "X32 Gain Recall"
APP_VERSION = "1.0.0"
X32_PORT = 10023
GAIN_MIN, GAIN_MAX, GAIN_STEP = -12.0, 60.0, 0.5
N_HA = 128


# --------------------------------------------------------------------------
#  OSC (encodage / decodage minimal : i, f, s)
# --------------------------------------------------------------------------
def _pad(b: bytes) -> bytes:
    return b + b"\x00" * (4 - len(b) % 4)


def osc_encode(address, *args):
    tags = ","
    payload = b""
    for a in args:
        if isinstance(a, bool):
            a = int(a)
        if isinstance(a, int):
            tags += "i"
            payload += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            payload += struct.pack(">f", a)
        else:
            tags += "s"
            payload += _pad(str(a).encode("utf-8"))
    return _pad(address.encode("ascii")) + _pad(tags.encode("ascii")) + payload


def _read_str(data, pos):
    end = data.index(b"\x00", pos)
    s = data[pos:end].decode("utf-8", "replace")
    return s, (end + 4) & ~3  # (end+1) arrondi au multiple de 4 superieur


def osc_decode(data):
    addr, pos = _read_str(data, 0)
    args = []
    if pos >= len(data) or data[pos:pos + 1] != b",":
        return addr, args
    tags, pos = _read_str(data, pos)
    for t in tags[1:]:
        if t == "f":
            args.append(struct.unpack(">f", data[pos:pos + 4])[0]); pos += 4
        elif t == "i":
            args.append(struct.unpack(">i", data[pos:pos + 4])[0]); pos += 4
        elif t == "s":
            s, pos = _read_str(data, pos); args.append(s)
        elif t == "b":
            n = struct.unpack(">i", data[pos:pos + 4])[0]
            pos += 4 + ((n + 3) & ~3); args.append(b"")
        else:
            break
    return addr, args


def db_to_float(db):
    return (db - GAIN_MIN) / (GAIN_MAX - GAIN_MIN)


def float_to_db(f):
    db = GAIN_MIN + f * (GAIN_MAX - GAIN_MIN)
    return quantize(db)


def quantize(db):
    db = max(GAIN_MIN, min(GAIN_MAX, db))
    return round(db / GAIN_STEP) * GAIN_STEP


# --------------------------------------------------------------------------
#  Client X32
# --------------------------------------------------------------------------
class X32Client:
    def __init__(self):
        self.lock = threading.RLock()
        self.sock = None
        self.gen = 0
        self.ip = ""
        self.port = X32_PORT
        self.gains = [None] * N_HA
        self.phantom = [None] * N_HA
        self.names = [None] * 32
        self.info = {}
        self.connected = False
        self.last_rx = 0.0
        self.rev = 0
        self.demo = False
        self.last_recall = None
        self.undo = None
        self.error = ""

    # -- etat -------------------------------------------------------------
    def _bump(self):
        self.rev += 1

    def snapshot(self):
        with self.lock:
            alive = self.sock is not None and (time.time() - self.last_rx) < 15 and self.last_rx > 0
            return {
                "rev": self.rev,
                "ip": self.ip,
                "connected": bool(alive),
                "trying": self.sock is not None and not alive,
                "info": self.info,
                "gains": list(self.gains),
                "phantom": list(self.phantom),
                "names": list(self.names),
                "known": sum(1 for g in self.gains if g is not None),
                "demo": self.demo,
                "last_recall": self.last_recall,
                "can_undo": self.undo is not None,
                "error": self.error,
            }

    # -- connexion --------------------------------------------------------
    def connect(self, ip, port=X32_PORT):
        self.disconnect()
        with self.lock:
            self.error = ""
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(("", 0))
                s.settimeout(0.5)
            except OSError as e:
                self.error = "Socket : %s" % e
                return False
            self.sock = s
            self.ip, self.port = ip, port
            self.gen += 1
            gen = self.gen
            self.last_rx = 0.0
            self.gains = [None] * N_HA
            self.phantom = [None] * N_HA
            self.names = [None] * 32
            self.info = {}
            self._bump()
        threading.Thread(target=self._rx_loop, args=(s, gen), daemon=True).start()
        threading.Thread(target=self._keepalive_loop, args=(gen,), daemon=True).start()
        threading.Thread(target=self._initial_sync, args=(gen,), daemon=True).start()
        return True

    def disconnect(self):
        with self.lock:
            self.gen += 1
            s, self.sock = self.sock, None
            self.connected = False
            self.last_rx = 0.0
            self._bump()
        if s:
            try:
                s.close()
            except OSError:
                pass

    def _send(self, address, *args):
        s = self.sock
        if not s:
            return
        try:
            s.sendto(osc_encode(address, *args), (self.ip, self.port))
        except OSError as e:
            self.error = "Envoi : %s" % e

    # -- threads ----------------------------------------------------------
    def _rx_loop(self, sock, gen):
        while self.gen == gen:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Windows : ICMP "port unreachable" remonte comme une erreur de recv
                continue
            except OSError:
                break
            try:
                addr, args = osc_decode(data)
            except Exception:
                continue
            self.last_rx = time.time()
            self._handle(addr, args)

    def _handle(self, addr, args):
        with self.lock:
            if addr.startswith("/headamp/") and args:
                parts = addr.split("/")
                try:
                    idx = int(parts[2])
                except (ValueError, IndexError):
                    return
                if not 0 <= idx < N_HA or len(parts) < 4:
                    return
                if parts[3] == "gain" and isinstance(args[0], float):
                    self.gains[idx] = float_to_db(args[0]); self._bump()
                elif parts[3] == "phantom" and isinstance(args[0], int):
                    self.phantom[idx] = 1 if args[0] else 0; self._bump()
            elif addr.startswith("/ch/") and addr.endswith("/config/name") and args:
                try:
                    n = int(addr.split("/")[2]) - 1
                except ValueError:
                    return
                if 0 <= n < 32:
                    self.names[n] = str(args[0]).strip() or None; self._bump()
            elif addr == "/xinfo" and len(args) >= 4:
                self.info = {"ip": args[0], "name": args[1], "model": args[2], "fw": args[3]}; self._bump()
            elif addr == "/info" and len(args) >= 4 and not self.info:
                self.info = {"name": args[1], "model": args[2], "fw": args[3]}; self._bump()

    def _keepalive_loop(self, gen):
        # /xremote expire au bout de 10 s cote console : on renouvelle toutes les 5 s.
        while self.gen == gen:
            self._send("/xremote")
            self._send("/info")
            for _ in range(10):
                if self.gen != gen:
                    return
                time.sleep(0.5)

    def _initial_sync(self, gen):
        self._send("/xinfo")
        self._send("/xremote")
        time.sleep(0.15)
        self.request_all(gen)
        for _ in range(2):  # UDP peut perdre des paquets : on redemande ce qui manque
            time.sleep(0.8)
            if self.gen != gen:
                return
            if self.last_rx > 0:
                self.request_all(gen, only_missing=True)

    def request_all(self, gen=None, only_missing=False):
        gen = self.gen if gen is None else gen
        for i in range(N_HA):
            if self.gen != gen:
                return
            if not only_missing or self.gains[i] is None:
                self._send("/headamp/%03d/gain" % i)
            if not only_missing or self.phantom[i] is None:
                self._send("/headamp/%03d/phantom" % i)
            time.sleep(0.003)
        for n in range(1, 33):
            if self.gen != gen:
                return
            if not only_missing or self.names[n - 1] is None:
                self._send("/ch/%02d/config/name" % n)
            time.sleep(0.003)

    # -- commandes --------------------------------------------------------
    def set_gain(self, idx, db):
        if not 0 <= idx < N_HA:
            return None
        db = quantize(float(db))
        with self.lock:
            self.gains[idx] = db
            self._bump()
        self._send("/headamp/%03d/gain" % idx, float(db_to_float(db)))
        return db

    def set_phantom(self, idx, on):
        if not 0 <= idx < N_HA:
            return
        with self.lock:
            self.phantom[idx] = 1 if on else 0
            self._bump()
        self._send("/headamp/%03d/phantom" % idx, 1 if on else 0)

    def recall(self, preset, indices=None, with_phantom=False):
        """Applique un preset. Renvoie un resume ; verifie ensuite en relisant la console
        (l'X32 n'accuse pas reception des commandes 'set' : on releit pour confirmer)."""
        plan_g, plan_p = {}, {}
        with self.lock:
            for k, v in preset.get("gains", {}).items():
                i = int(k)
                if indices is not None and i not in indices:
                    continue
                v = quantize(float(v))
                if self.gains[i] is None or abs(self.gains[i] - v) > 1e-6:
                    plan_g[i] = v
            if with_phantom:
                for k, v in preset.get("phantom", {}).items():
                    i = int(k)
                    if indices is not None and i not in indices:
                        continue
                    v = 1 if v else 0
                    if self.phantom[i] is None or self.phantom[i] != v:
                        plan_p[i] = v
            self.undo = {
                "gains": {i: self.gains[i] for i in plan_g if self.gains[i] is not None},
                "phantom": {i: self.phantom[i] for i in plan_p if self.phantom[i] is not None},
                "label": preset.get("name", ""),
            }
        for i, v in plan_g.items():
            self.set_gain(i, v)
            time.sleep(0.002)
        for i, v in plan_p.items():
            self.set_phantom(i, v)
            time.sleep(0.002)
        result = {"t": time.time(), "name": preset.get("name", ""), "sent_gain": len(plan_g),
                  "sent_phantom": len(plan_p), "verified": None, "bad": []}
        self.last_recall = result
        self._bump()
        threading.Thread(target=self._verify, args=(result, dict(plan_g), dict(plan_p)), daemon=True).start()
        return result

    def _verify(self, result, plan_g, plan_p):
        time.sleep(0.5)
        with self.lock:
            for i in plan_g:
                self.gains[i] = None
            for i in plan_p:
                self.phantom[i] = None
        for i in plan_g:
            self._send("/headamp/%03d/gain" % i); time.sleep(0.003)
        for i in plan_p:
            self._send("/headamp/%03d/phantom" % i); time.sleep(0.003)
        time.sleep(0.8)
        bad = []
        with self.lock:
            for i, v in plan_g.items():
                if self.gains[i] is None or abs(self.gains[i] - v) > 1e-6:
                    bad.append(i)
            for i, v in plan_p.items():
                if self.phantom[i] != v and i not in bad:
                    bad.append(i)
            result["bad"] = sorted(bad)
            result["verified"] = len(bad) == 0
            self._bump()

    def do_undo(self):
        with self.lock:
            u, self.undo = self.undo, None
        if not u:
            return False
        for i, v in u["gains"].items():
            self.set_gain(int(i), v); time.sleep(0.002)
        for i, v in u["phantom"].items():
            self.set_phantom(int(i), v); time.sleep(0.002)
        with self.lock:
            self.last_recall = {"t": time.time(), "name": "Annulation : " + u["label"], "sent_gain": len(u["gains"]),
                                "sent_phantom": len(u["phantom"]), "verified": None, "bad": []}
            self._bump()
        return True


# --------------------------------------------------------------------------
#  Simulateur de X32 (pour tester sans console)
# --------------------------------------------------------------------------
class X32Sim(threading.Thread):
    NAMES = ["Kick", "Snare", "Hat", "Tom 1", "Tom 2", "Floor", "OH L", "OH R", "Bass", "Gtr L", "Gtr R",
             "Keys L", "Keys R", "Lead", "BV 1", "BV 2"]

    def __init__(self, port=X32_PORT):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(0.5)
        rnd = random.Random(32)
        self.gain = [quantize(rnd.uniform(8, 42)) for _ in range(N_HA)]
        self.phantom = [1 if i in (6, 7, 11) else 0 for i in range(N_HA)]
        self.names = {i + 1: n for i, n in enumerate(self.NAMES)}
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                data, peer = self.sock.recvfrom(4096)
                a, args = osc_decode(data)
            except socket.timeout:
                continue
            except OSError:
                continue
            except Exception:
                continue
            send = lambda *m: self.sock.sendto(osc_encode(*m), peer)
            if a == "/info":
                send("/info", "V2.05", "osc-server", "X32", "4.06")
            elif a == "/xinfo":
                send("/xinfo", "127.0.0.1", "X32-SIMULATEUR", "X32", "4.06")
            elif a.startswith("/headamp/"):
                p = a.split("/")
                try:
                    i = int(p[2])
                except (ValueError, IndexError):
                    continue
                if not 0 <= i < N_HA:
                    continue
                if p[3] == "gain":
                    if args:
                        self.gain[i] = float_to_db(float(args[0]))
                    else:
                        send(a, float(db_to_float(self.gain[i])))
                elif p[3] == "phantom":
                    if args:
                        self.phantom[i] = 1 if args[0] else 0
                    else:
                        send(a, self.phantom[i])
            elif a.startswith("/ch/") and a.endswith("/config/name") and not args:
                try:
                    n = int(a.split("/")[2])
                except ValueError:
                    continue
                send(a, self.names.get(n, "Ch%02d" % n))


# --------------------------------------------------------------------------
#  Scenes de gains (fichier JSON)
# --------------------------------------------------------------------------
class PresetStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.items = []
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = data.get("presets", []) if isinstance(data, dict) else []
        except FileNotFoundError:
            self.items = []
        except (OSError, ValueError):
            # fichier corrompu : on le garde de cote plutot que de l'ecraser
            try:
                os.replace(self.path, self.path + ".corrompu-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            except OSError:
                pass
            self.items = []

    def _write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "presets": self.items}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def all(self):
        with self.lock:
            return json.loads(json.dumps(self.items))

    def get(self, pid):
        with self.lock:
            for p in self.items:
                if p["id"] == pid:
                    return json.loads(json.dumps(p))
        return None

    def add(self, name, gains, phantom, names, info, note=""):
        p = {"id": uuid.uuid4().hex[:12], "name": name, "note": note,
             "created": datetime.now().isoformat(timespec="seconds"),
             "console": info or {}, "gains": gains, "phantom": phantom, "names": names}
        with self.lock:
            self.items.append(p)
            self._write()
        return p

    def overwrite(self, pid, gains, phantom, names, info):
        with self.lock:
            for p in self.items:
                if p["id"] == pid:
                    p.update({"gains": gains, "phantom": phantom, "names": names, "console": info or {},
                              "created": datetime.now().isoformat(timespec="seconds")})
                    self._write()
                    return True
        return False

    def rename(self, pid, name):
        with self.lock:
            for p in self.items:
                if p["id"] == pid:
                    p["name"] = name
                    self._write()
                    return True
        return False

    def delete(self, pid):
        with self.lock:
            n = len(self.items)
            self.items = [p for p in self.items if p["id"] != pid]
            if len(self.items) != n:
                self._write()
                return True
        return False

    def import_items(self, items):
        added = 0
        with self.lock:
            have = {p["id"] for p in self.items}
            for p in items:
                if not isinstance(p, dict) or "gains" not in p or "name" not in p:
                    continue
                q = {"id": p.get("id") if p.get("id") not in have and p.get("id") else uuid.uuid4().hex[:12],
                     "name": str(p["name"])[:60], "note": str(p.get("note", ""))[:200],
                     "created": p.get("created", datetime.now().isoformat(timespec="seconds")),
                     "console": p.get("console", {}),
                     "gains": {str(int(k)): quantize(float(v)) for k, v in p["gains"].items() if 0 <= int(k) < N_HA},
                     "phantom": {str(int(k)): 1 if v else 0 for k, v in p.get("phantom", {}).items() if 0 <= int(k) < N_HA},
                     "names": p.get("names", {})}
                self.items.append(q); have.add(q["id"]); added += 1
            if added:
                self._write()
        return added


# --------------------------------------------------------------------------
#  Serveur HTTP local + API
# --------------------------------------------------------------------------
CLIENT = X32Client()
STORE = None
SIM = None
ALLOWED_HOSTS = set()


def start_sim():
    global SIM
    if SIM and SIM.is_alive():
        return True, ""
    try:
        SIM = X32Sim()
    except OSError as e:
        return False, "Impossible de demarrer le simulateur (port %d occupe ?) : %s" % (X32_PORT, e)
    SIM.start()
    return True, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "X32GainRecall/1.0"

    def log_message(self, *a):
        pass

    def _host_ok(self):
        return self.headers.get("Host", "") in ALLOWED_HOSTS  # anti DNS-rebinding

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "host refuse"}, 403)
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/state":
            self._json(CLIENT.snapshot())
        elif path == "/api/presets":
            self._json({"presets": STORE.all(), "path": STORE.path})
        elif path == "/api/export":
            body = json.dumps({"version": 1, "presets": STORE.all()}, ensure_ascii=False, indent=1).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="x32_presets_export.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "introuvable"}, 404)

    def do_POST(self):
        if not self._host_ok():
            return self._json({"error": "host refuse"}, 403)
        # application/json impose un "preflight" CORS pour un site tiers -> bloque les requetes cross-site
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self._json({"error": "content-type"}, 415)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            d = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return self._json({"error": "json invalide"}, 400)
        try:
            self._route(self.path.split("?")[0], d)
        except (KeyError, ValueError, TypeError) as e:
            self._json({"error": "requete invalide : %s" % e}, 400)

    def _capture(self):
        s = CLIENT.snapshot()
        gains = {str(i): g for i, g in enumerate(s["gains"]) if g is not None}
        phantom = {str(i): p for i, p in enumerate(s["phantom"]) if p is not None}
        names = {str(i): n for i, n in enumerate(s["names"]) if n}
        return gains, phantom, names, s["info"]

    def _route(self, p, d):
        if p == "/api/connect":
            ip = str(d["ip"]).strip()
            try:
                socket.inet_aton(ip)
            except OSError:
                try:
                    ip = socket.gethostbyname(ip)
                except OSError:
                    return self._json({"ok": False, "error": "Adresse IP invalide"})
            ok = CLIENT.connect(ip)
            CLIENT.demo = ip == "127.0.0.1"
            return self._json({"ok": ok, "error": CLIENT.error})
        if p == "/api/demo":
            ok, err = start_sim()
            if not ok:
                return self._json({"ok": False, "error": err})
            CLIENT.connect("127.0.0.1")
            CLIENT.demo = True
            return self._json({"ok": True})
        if p == "/api/disconnect":
            CLIENT.disconnect()
            return self._json({"ok": True})
        if p == "/api/refresh":
            threading.Thread(target=CLIENT.request_all, daemon=True).start()
            return self._json({"ok": True})
        if p == "/api/gain":
            v = CLIENT.set_gain(int(d["idx"]), float(d["db"]))
            return self._json({"ok": v is not None, "db": v})
        if p == "/api/phantom":
            CLIENT.set_phantom(int(d["idx"]), bool(d["on"]))
            return self._json({"ok": True})
        if p == "/api/presets/save":
            gains, phantom, names, info = self._capture()
            if not gains:
                return self._json({"ok": False, "error": "Aucune valeur de gain lue : connectez-vous d'abord."})
            if d.get("overwrite_id"):
                ok = STORE.overwrite(d["overwrite_id"], gains, phantom, names, info)
                return self._json({"ok": ok, "error": "" if ok else "Scene introuvable"})
            name = str(d.get("name", "")).strip()[:60] or datetime.now().strftime("Scene %d/%m %H:%M")
            pr = STORE.add(name, gains, phantom, names, info, str(d.get("note", ""))[:200])
            return self._json({"ok": True, "id": pr["id"]})
        if p == "/api/presets/recall":
            pr = STORE.get(d["id"])
            if not pr:
                return self._json({"ok": False, "error": "Scene introuvable"})
            if not CLIENT.snapshot()["connected"]:
                return self._json({"ok": False, "error": "Non connecte a la console"})
            idx = set(int(i) for i in d["indices"]) if d.get("indices") else None
            r = CLIENT.recall(pr, idx, bool(d.get("phantom")))
            return self._json({"ok": True, "result": r})
        if p == "/api/presets/undo":
            return self._json({"ok": CLIENT.do_undo()})
        if p == "/api/presets/rename":
            return self._json({"ok": STORE.rename(d["id"], str(d["name"]).strip()[:60] or "Sans nom")})
        if p == "/api/presets/delete":
            return self._json({"ok": STORE.delete(d["id"])})
        if p == "/api/import":
            return self._json({"ok": True, "added": STORE.import_items(d.get("presets", []))})
        self._json({"error": "introuvable"}, 404)


# --------------------------------------------------------------------------
#  Interface (HTML/CSS/JS embarques) - direction artistique inspiree de Waves eMotion LV1
# --------------------------------------------------------------------------
HTML = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>X32 Gain Recall</title>
<style>
:root{
  --bg:#08090a; --panel:#111213; --panel2:#17191b; --line:#2c2f33; --line2:#3a3e43;
  --teal:#13a9af; --teal-d:#0c7d83; --blue:#31b6f7; --blue-d:#1668e6;
  --lite:#e7e9eb; --txt:#e9edf0; --mut:#8c939a; --cyan:#3fd0ff; --warn:#ff5b4d; --amber:#f2b63b; --ok:#3ddc84;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);
  font:13px/1.25 "Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;overflow:hidden;user-select:none}
button{font:inherit;color:inherit;cursor:pointer}
#app{display:grid;grid-template-rows:56px 1fr 26px;height:100vh}

/* ---- barre du haut ---- */
#top{display:flex;align-items:center;gap:8px;padding:8px 10px;background:#0d0e0f;border-bottom:1px solid var(--line)}
.pill{background:var(--lite);color:#111;border:0;border-radius:6px;height:38px;padding:0 18px;font-weight:600;font-size:15px}
.pill.on{background:var(--blue);color:#001a2a}
.pill:disabled{opacity:.4;cursor:default}
.sel{background:var(--teal);color:#032;border-radius:6px;height:38px;padding:0 16px;border:0;font-weight:700;font-size:15px;min-width:210px;text-align:left}
.screen{background:#000;border:1px solid var(--line2);border-radius:5px;height:38px;padding:0 10px;display:flex;align-items:center;gap:8px}
.screen input{background:transparent;border:0;color:var(--cyan);font:600 14px "Consolas","Segoe UI",monospace;width:130px;outline:none;user-select:text}
.led{width:10px;height:10px;border-radius:50%;background:#555;box-shadow:0 0 0 1px #000 inset}
.led.ok{background:var(--ok);box-shadow:0 0 8px var(--ok)}
.led.try{background:var(--amber);animation:bl 1s infinite}
@keyframes bl{50%{opacity:.25}}
.mini{background:#1c1e20;border:1px solid var(--line2);border-radius:6px;height:38px;padding:0 12px;font-weight:600}
.mini:hover{border-color:var(--blue)}
.mini.act{background:var(--blue);color:#001a2a;border-color:var(--blue)}
.mini.lock.act{background:var(--warn);border-color:var(--warn);color:#fff}
.spacer{flex:1}
.logo{font-weight:800;letter-spacing:.06em;font-size:20px;color:#dfe5ea;text-align:right;line-height:1}
.logo small{display:block;font-size:9px;letter-spacing:.25em;color:var(--mut);font-weight:600;margin-top:2px}

/* ---- zone principale ---- */
#main{display:grid;grid-template-columns:1fr 310px;min-height:0}
#stripwrap{padding:8px 6px 8px 10px;min-width:0;overflow-x:auto;overflow-y:hidden}
#strips{display:grid;grid-template-columns:repeat(16,minmax(70px,1fr));gap:3px;height:100%;min-width:1180px}
.strip{display:flex;flex-direction:column;background:var(--panel);border:1px solid #000;border-radius:3px;min-height:0}
.strip .hd{background:var(--teal);color:#021;font-weight:700;text-align:center;padding:5px 2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.strip.na .hd{background:#39424a;color:#9aa4ac}
.strip .ph{margin:5px 5px 3px;height:26px;background:#25282b;border:1px solid var(--line2);border-radius:4px;font-weight:700;color:#aeb6bd}
.strip .ph.on{background:var(--blue);color:#001a2a;border-color:var(--blue)}
.strip .ph:disabled{opacity:.35}
.bar{position:relative;flex:1;margin:3px 10px;background:#000;border:1px solid #222;border-radius:3px;cursor:ns-resize;min-height:80px;touch-action:none}
.bar .fill{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#17c4cc,var(--teal-d));opacity:.85}
.bar .zero{position:absolute;left:0;right:0;height:1px;background:#ffffff55}
.bar .tgt{position:absolute;left:-6px;right:-6px;height:0;border-top:2px solid var(--amber);display:none;pointer-events:none}
.bar .tgt::after{content:"";position:absolute;right:-2px;top:-6px;border:5px solid transparent;border-right-color:var(--amber)}
.strip.na .bar{cursor:default;opacity:.35}
.tickl{position:absolute;left:3px;font-size:9px;color:#6d757c;pointer-events:none;transform:translateY(-50%)}
.kn{display:flex;justify-content:center;margin:2px 0 0;cursor:ns-resize;touch-action:none}
.kn svg{width:min(64px,90%);height:auto}
.val{margin:1px 8px 0;background:#000;border:1px solid #26292c;border-radius:3px;color:var(--cyan);text-align:center;
  font:700 15px "Consolas","Segoe UI",monospace;width:auto;padding:3px 0;outline:none;user-select:text}
.val:focus{border-color:var(--blue)}
.step{display:flex;gap:3px;margin:3px 8px 0}
.step button{flex:1;height:22px;background:#202326;border:1px solid var(--line2);border-radius:3px;font-weight:700;font-size:14px;line-height:1;padding:0}
.step button:hover{border-color:var(--blue)}
.dl{height:16px;margin:2px 4px 0;text-align:center;font-size:10.5px;color:var(--mut);white-space:nowrap;overflow:hidden}
.dl.d{color:var(--amber);font-weight:700}
.strip .ft{margin-top:4px;background:var(--teal);color:#021;text-align:right;padding:3px 7px;font-weight:800;font-size:14px}
.strip.na .ft{background:#39424a;color:#9aa4ac}
body.locked .strip .bar,body.locked .strip .kn,body.locked .strip .step,body.locked .strip .ph,body.locked .strip .val{opacity:.4;pointer-events:none}

/* ---- colonne droite ---- */
#side{display:flex;flex-direction:column;gap:8px;padding:8px 10px 8px 4px;min-height:0;border-left:1px solid #000}
.h{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);text-align:center;margin:2px 0}
#banks{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.bank{background:#0d0e0f;border:1px solid var(--line2);border-radius:6px;padding:7px 4px;font-weight:700;font-size:13px;height:40px}
.bank.on{background:#0a2a45;border:2px solid var(--blue);color:#fff}
#scenes{display:flex;flex-direction:column;min-height:0;flex:1;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px;gap:6px}
#plist{flex:1;overflow:auto;display:flex;flex-direction:column;gap:4px;min-height:60px}
.pi{background:#0d0e0f;border:1px solid var(--line2);border-radius:5px;padding:6px 8px;cursor:pointer}
.pi.on{border-color:var(--blue);background:#0a2a45}
.pi b{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pi span{color:var(--mut);font-size:11px}
.row{display:flex;gap:5px}
.row>*{flex:1}
.btn{background:#1c1e20;border:1px solid var(--line2);border-radius:5px;padding:7px 4px;font-weight:600;font-size:12.5px}
.btn:hover:not(:disabled){border-color:var(--blue)}
.btn:disabled{opacity:.35;cursor:default}
.btn.go{background:var(--blue);color:#001a2a;border-color:var(--blue);font-weight:800;font-size:14px;padding:10px}
.btn.dng:hover:not(:disabled){border-color:var(--warn);color:var(--warn)}
.inp{background:#000;border:1px solid var(--line2);border-radius:5px;padding:7px 8px;color:var(--txt);font:inherit;width:100%;outline:none;user-select:text}
.inp:focus{border-color:var(--blue)}
.opt{display:flex;align-items:center;gap:7px;color:#c5cbd0;font-size:12px}
.opt input{accent-color:var(--blue)}
.opt.warn{color:var(--amber)}
select.inp{padding:6px}

/* ---- barre d'etat ---- */
#status{display:flex;align-items:center;gap:14px;padding:0 12px;background:#0d0e0f;border-top:1px solid var(--line);color:var(--mut);font-size:12px;white-space:nowrap;overflow:hidden}
#status b{color:var(--txt);font-weight:600}
.good{color:var(--ok)} .bad{color:var(--warn)}

/* ---- modale / toast ---- */
#modal{position:fixed;inset:0;background:#000a;display:none;align-items:center;justify-content:center;z-index:10}
#modal .box{background:#15171a;border:1px solid var(--line2);border-radius:8px;padding:18px 20px;max-width:520px;width:calc(100% - 30px)}
#modal h3{margin:0 0 8px;font-size:16px}
#modal p{margin:6px 0;color:#c9cfd4;line-height:1.4;user-select:text}
#modal .row{margin-top:14px;justify-content:flex-end}
#modal .row .btn{flex:0 0 auto;padding:8px 16px}
#toast{position:fixed;left:14px;bottom:38px;background:#15171a;border:1px solid var(--line2);border-left:4px solid var(--blue);
  border-radius:5px;padding:9px 13px;max-width:520px;display:none;z-index:9;box-shadow:0 4px 18px #000a}
#toast.err{border-left-color:var(--warn)} #toast.ok{border-left-color:var(--ok)}
#welcome{position:absolute;left:20px;top:80px;max-width:560px;color:#aab2b8;line-height:1.55;font-size:14px;pointer-events:none}
#welcome b{color:#fff}
</style></head>
<body>
<div id="app">
  <div id="top">
    <div class="sel" style="display:flex;align-items:center">Gains &middot; <span id="bankname" style="margin-left:6px">Local 1-16</span></div>
    <div class="screen"><span class="led" id="led"></span><input id="ip" placeholder="IP de la X32" spellcheck="false"></div>
    <button class="pill on" id="bconn">Connecter</button>
    <button class="pill" id="bdemo" title="Simulateur de X32 en local pour essayer l'appli sans console">D&eacute;mo</button>
    <button class="mini" id="bref" title="Relire tous les gains depuis la console">&#8635; Relire</button>
    <button class="mini lock" id="block" title="Verrouille l'&eacute;dition (comme le cadenas du LV1)">&#128274; Verrou</button>
    <div class="spacer"></div>
    <div class="logo">X32 GAIN RECALL<small>OSC &middot; UDP 10023</small></div>
  </div>

  <div id="main">
    <div id="stripwrap"><div id="strips"></div><div id="welcome"></div></div>
    <div id="side">
      <div class="h">Banques d'entr&eacute;es</div>
      <div id="banks"></div>
      <div class="h" style="margin-top:6px">Sc&egrave;nes de gains</div>
      <div id="scenes">
        <div class="row"><input class="inp" id="pname" placeholder="Nom de la nouvelle sc&egrave;ne" maxlength="60">
          <button class="btn" id="psave" style="flex:0 0 96px">Sauver</button></div>
        <div id="plist"></div>
        <div class="row">
          <select class="inp" id="pscope"><option value="all">Tout rappeler</option><option value="bank">Banque affich&eacute;e seule</option></select>
        </div>
        <label class="opt warn"><input type="checkbox" id="pphan"> Inclure l'alim. fantôme 48V</label>
        <button class="btn go" id="precall" disabled>Rappeler la sc&egrave;ne</button>
        <div class="row">
          <button class="btn" id="pover" disabled>&Eacute;craser</button>
          <button class="btn" id="pren" disabled>Renommer</button>
          <button class="btn dng" id="pdel" disabled>Suppr.</button>
        </div>
        <button class="btn" id="pundo" disabled>&#8630; Annuler le dernier rappel</button>
        <div class="row">
          <button class="btn" id="pexp">Exporter</button>
          <button class="btn" id="pimp">Importer</button>
          <input type="file" id="pfile" accept=".json,application/json" style="display:none">
        </div>
      </div>
    </div>
  </div>
  <div id="status"></div>
</div>
<div id="modal"><div class="box"><h3 id="mt"></h3><div id="mb"></div><div class="row" id="mr"></div></div></div>
<div id="toast"></div>

<script>
"use strict";
const $=s=>document.querySelector(s);
const BANKS=[["Local 1-16",0],["Local 17-32",16],["AES50-A 1-16",32],["AES50-A 17-32",48],["AES50-A 33-48",64],
             ["AES50-B 1-16",80],["AES50-B 17-32",96],["AES50-B 33-48",112]];
const GMIN=-12,GMAX=60;
let S={gains:Array(128).fill(null),phantom:Array(128).fill(null),names:Array(32).fill(null),connected:false,trying:false,info:{},known:0};
let bank=0, presets=[], selId=null, locked=false, L={};   // L: valeurs locales recentes (evite le clignotement)
let presetPath="";

function label(i){return i<32?String(i+1):(i<80?"A"+(i-31):"B"+(i-79));}
function fmt(v){return (v>0?"+":"")+v.toFixed(1);}
function clamp(v){return Math.max(GMIN,Math.min(GMAX,Math.round(v*2)/2));}
function api(p,body){
  const o=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)};
  return fetch(p,o).then(r=>r.json());
}
function toast(msg,kind,ms){const t=$("#toast");t.textContent=msg;t.className=kind||"";t.style.display="block";
  clearTimeout(toast.h);toast.h=setTimeout(()=>t.style.display="none",ms||4200);}
function modal(title,html,buttons){
  $("#mt").textContent=title;$("#mb").innerHTML=html;const r=$("#mr");r.innerHTML="";
  buttons.forEach(b=>{const e=document.createElement("button");e.className="btn"+(b.go?" go":"");e.textContent=b.t;
    e.onclick=()=>{$("#modal").style.display="none";b.f&&b.f();};r.appendChild(e);});
  $("#modal").style.display="flex";
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

/* ---------- pastilles / knob ---------- */
function pol(cx,cy,r,deg){const a=(deg-90)*Math.PI/180;return [cx+r*Math.cos(a),cy+r*Math.sin(a)];}
function arc(cx,cy,r,a0,a1){const [x0,y0]=pol(cx,cy,r,a0),[x1,y1]=pol(cx,cy,r,a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 ${(a1-a0)>180?1:0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;}
function knobSVG(){return `<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="22" fill="#1a1c1e" stroke="#000" stroke-width="2"/>
  <path class="ktrack" d="${arc(32,32,27,-135,135)}" fill="none" stroke="#2b2f33" stroke-width="4" stroke-linecap="round"/>
  <path class="kval" d="" fill="none" stroke="#13a9af" stroke-width="4" stroke-linecap="round"/>
  <line class="kptr" x1="32" y1="32" x2="32" y2="12" stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg>`;}

/* ---------- construction des strips ---------- */
function buildStrips(){
  const box=$("#strips");box.innerHTML="";
  for(let k=0;k<16;k++){
    const i=BANKS[bank][1]+k;
    const el=document.createElement("div");el.className="strip na";el.dataset.i=i;
    el.innerHTML=`<div class="hd"></div><button class="ph" title="Alimentation fantôme +48 V">48V</button>
      <div class="bar"><div class="fill"></div><div class="zero"></div><div class="tgt"></div></div>
      <div class="kn">${knobSVG()}</div><input class="val" value="—" spellcheck="false">
      <div class="step"><button data-d="-0.5">&minus;</button><button data-d="0.5">+</button></div>
      <div class="dl"></div><div class="ft">${label(i)}</div>`;
    box.appendChild(el);
    wire(el,i);
  }
  $("#bankname").textContent=BANKS[bank][0];
  document.querySelectorAll(".bank").forEach((b,n)=>b.classList.toggle("on",n===bank));
  update();
}
function cur(i){const l=L[i];if(l&&performance.now()-l.t<900)return l.db;const v=S.gains[i];return v===undefined?null:v;}

/* envoi limite en cadence (evite d'inonder la console) */
const pend={},lastSent={};
function queueSend(i,db){
  pend[i]=db;const now=performance.now(),dt=now-(lastSent[i]||0);
  const go=()=>{if(pend[i]===undefined)return;const v=pend[i];delete pend[i];lastSent[i]=performance.now();
    api("/api/gain",{idx:i,db:v}).catch(()=>{});};
  if(dt>=35){go();}else if(!queueSend.t||!queueSend.t[i]){queueSend.t=queueSend.t||{};
    queueSend.t[i]=setTimeout(()=>{queueSend.t[i]=null;go();},35-dt);}
}
function setGain(i,db){
  if(locked||!S.connected)return;db=clamp(db);
  if(cur(i)===db)return;L[i]={db,t:performance.now()};queueSend(i,db);updateStrip(i);
}
function wire(el,i){
  const bar=el.querySelector(".bar"),kn=el.querySelector(".kn"),val=el.querySelector(".val");
  function drag(target,perPx){
    target.addEventListener("pointerdown",ev=>{
      if(locked||cur(i)===null)return;target.setPointerCapture(ev.pointerId);
      const y0=ev.clientY,v0=cur(i);let acc=v0;
      const mv=e=>{const k=perPx(target)*(e.shiftKey?0.2:1);acc=v0+(y0-e.clientY)*k;setGain(i,acc);};
      const up=()=>{target.removeEventListener("pointermove",mv);target.removeEventListener("pointerup",up);
        target.removeEventListener("pointercancel",up);};
      target.addEventListener("pointermove",mv);target.addEventListener("pointerup",up);target.addEventListener("pointercancel",up);
      ev.preventDefault();
    });
  }
  // deplacement RELATIF : un simple clic ne change jamais le gain (securite en live)
  drag(bar,t=>(GMAX-GMIN)/Math.max(60,t.clientHeight));
  drag(kn,()=>(GMAX-GMIN)/220);
  el.addEventListener("wheel",ev=>{if(locked||cur(i)===null)return;ev.preventDefault();
    setGain(i,cur(i)+(ev.deltaY<0?1:-1)*(ev.shiftKey?5:0.5));},{passive:false});
  el.querySelectorAll(".step button").forEach(b=>b.onclick=ev=>{if(cur(i)!==null)setGain(i,cur(i)+parseFloat(b.dataset.d)*(ev.shiftKey?10:1));});
  val.addEventListener("keydown",e=>{if(e.key==="Enter"){const v=parseFloat(val.value.replace(",","."));
    if(!isNaN(v))setGain(i,v);val.blur();}else if(e.key==="Escape"){val.blur();updateStrip(i);}});
  val.addEventListener("blur",()=>updateStrip(i));
  val.addEventListener("focus",()=>val.select());
  el.querySelector(".ph").onclick=()=>{
    if(locked||!S.connected)return;const on=S.phantom[i]!==1;
    const send=()=>{S.phantom[i]=on?1:0;updateStrip(i);api("/api/phantom",{idx:i,on});};
    if(on){modal("Activer le +48 V ?","<p>Voie <b>"+label(i)+"</b> : vérifiez qu'aucun micro ruban / dynamique non protégé n'est branché.</p>",
      [{t:"Annuler"},{t:"Activer +48 V",go:1,f:send}]);}else send();
  };
}
function updateStrip(i){
  const el=document.querySelector(`.strip[data-i="${i}"]`);if(!el)return;
  const v=cur(i),known=v!==null;
  el.classList.toggle("na",!known);
  const nm=i<32?(S.names[i]||"Ch "+(i+1)):(i<80?"AES50-A "+(i-31):"AES50-B "+(i-79));
  el.querySelector(".hd").textContent=nm;el.querySelector(".hd").title=nm;
  const val=el.querySelector(".val");if(document.activeElement!==val)val.value=known?fmt(v):"—";
  const p=known?(v-GMIN)/(GMAX-GMIN):0;
  el.querySelector(".fill").style.height=(p*100)+"%";
  el.querySelector(".zero").style.bottom=((0-GMIN)/(GMAX-GMIN)*100)+"%";
  const a=-135+270*p;el.querySelector(".kval").setAttribute("d",known&&a>-134?arc(32,32,27,-135,a):"");
  const pt=pol(32,32,20,a);el.querySelector(".kptr").setAttribute("x2",pt[0]);el.querySelector(".kptr").setAttribute("y2",pt[1]);
  const ph=el.querySelector(".ph");ph.classList.toggle("on",S.phantom[i]===1);ph.disabled=S.phantom[i]==null;
  // apercu de la scene selectionnee : repere ambre + delta
  const tg=el.querySelector(".tgt"),dl=el.querySelector(".dl");
  const pr=presets.find(x=>x.id===selId);const t=pr&&pr.gains[String(i)];
  if(pr&&t!==undefined&&known){const tp=(t-GMIN)/(GMAX-GMIN);tg.style.display="block";tg.style.bottom=(tp*100)+"%";
    const d=t-v;if(Math.abs(d)<0.01){dl.className="dl";dl.textContent="= scène";}
    else{dl.className="dl d";dl.textContent="→ "+fmt(t)+" ("+(d>0?"+":"")+d.toFixed(1)+")";}}
  else{tg.style.display="none";dl.className="dl";dl.textContent="";}
}
function update(){
  document.querySelectorAll(".strip").forEach(el=>updateStrip(+el.dataset.i));
  // etat de connexion
  const led=$("#led");led.className="led"+(S.connected?" ok":(S.trying?" try":""));
  $("#bconn").textContent=(S.connected||S.trying)?"Déconnecter":"Connecter";
  $("#bconn").className="pill"+((S.connected||S.trying)?"":" on");
  ["#bref"].forEach(s=>$(s).disabled=!S.connected);
  const w=$("#welcome");
  if(S.connected){w.style.display="none";}
  else{w.style.display="block";w.innerHTML=S.trying?"<b>Connexion en cours…</b><br>En attente d'une réponse de la console sur "+esc(S.ip)+" (UDP 10023). Si rien n'arrive : vérifiez l'IP (X32 : Setup → Network), que le PC est sur le même réseau/sous-réseau, et le pare-feu Windows."
    :"<b>1.</b> Sur la X32 : <b>Setup → Network</b> pour lire son adresse IP.<br><b>2.</b> Entrez-la en haut puis <b>Connecter</b>.<br><b>3.</b> Réglez les gains, sauvez une scène, rappelez-la plus tard.<br><br>Pas de console sous la main ? Le bouton <b>Démo</b> lance une X32 simulée.";}
  renderStatus();renderPresetButtons();
}
function renderStatus(){
  const i=S.info||{};const c=S.connected?`<b class="good">● Connecté</b> ${esc(i.model||"X32")} ${esc(i.name||"")} ${i.fw?"· fw "+esc(i.fw):""} · ${S.known}/128 gains lus`+(S.demo?' · <b style="color:var(--amber)">SIMULATEUR</b>':""):
    (S.trying?'<b style="color:var(--amber)">● Connexion…</b>':"○ Non connecté");
  let r="";const lr=S.last_recall;
  if(lr){r=` · Dernier rappel « ${esc(lr.name)} » : ${lr.sent_gain} gains`+(lr.sent_phantom?`, ${lr.sent_phantom} 48V`:"")+" envoyés — "+
    (lr.verified===null?"vérification…":(lr.verified?'<b class="good">confirmé par relecture ✓</b>':`<b class="bad">${lr.bad.length} écart(s) à la relecture : ${lr.bad.slice(0,8).map(label).join(", ")}</b>`));}
  $("#status").innerHTML=c+r+(S.error?` · <b class="bad">${esc(S.error)}</b>`:"")+'<span class="spacer"></span><span>Shift = pas fin/gros · molette = ±0,5 dB</span>';
}

/* ---------- scenes ---------- */
function loadPresets(){return api("/api/presets").then(r=>{presets=r.presets;presetPath=r.path;if(!presets.find(p=>p.id===selId))selId=null;renderPresets();update();});}
function renderPresets(){
  const l=$("#plist");l.innerHTML="";
  if(!presets.length){l.innerHTML='<div style="color:var(--mut);padding:8px">Aucune scène. Réglez vos gains puis « Sauver ».</div>';return;}
  presets.forEach(p=>{const d=document.createElement("div");d.className="pi"+(p.id===selId?" on":"");
    const n=Object.keys(p.gains).length;const dt=(p.created||"").replace("T"," ").slice(0,16);
    d.innerHTML=`<b>${esc(p.name)}</b><span>${n} gains · ${dt}</span>`;
    d.onclick=()=>{selId=(selId===p.id?null:p.id);renderPresets();update();};l.appendChild(d);});
}
function renderPresetButtons(){
  const has=!!selId;$("#precall").disabled=!(has&&S.connected&&!locked);$("#pover").disabled=!(has&&S.connected&&!locked);
  $("#pren").disabled=!has;$("#pdel").disabled=!has;$("#psave").disabled=!S.connected;$("#pundo").disabled=!(S.can_undo&&S.connected);
}
function scopeIdx(){return $("#pscope").value==="bank"?Array.from({length:16},(_,k)=>BANKS[bank][1]+k):null;}
$("#psave").onclick=()=>{
  api("/api/presets/save",{name:$("#pname").value}).then(r=>{
    if(!r.ok)return toast(r.error,"err");$("#pname").value="";selId=r.id;toast("Scène sauvegardée","ok");loadPresets();});
};
$("#pover").onclick=()=>{const p=presets.find(x=>x.id===selId);if(!p)return;
  modal("Écraser la scène ?","<p>Remplacer le contenu de <b>"+esc(p.name)+"</b> par les gains actuellement lus sur la console ?</p>",
   [{t:"Annuler"},{t:"Écraser",go:1,f:()=>api("/api/presets/save",{overwrite_id:p.id}).then(r=>{toast(r.ok?"Scène mise à jour":r.error,r.ok?"ok":"err");loadPresets();})}]);};
$("#pren").onclick=()=>{const p=presets.find(x=>x.id===selId);if(!p)return;
  modal("Renommer","<input class='inp' id='rn' value='"+esc(p.name)+"' maxlength='60'>",
   [{t:"Annuler"},{t:"OK",go:1,f:()=>api("/api/presets/rename",{id:p.id,name:$("#rn").value}).then(loadPresets)}]);
  setTimeout(()=>{const e=$("#rn");if(e){e.focus();e.select();}},30);};
$("#pdel").onclick=()=>{const p=presets.find(x=>x.id===selId);if(!p)return;
  modal("Supprimer ?","<p>Supprimer définitivement la scène <b>"+esc(p.name)+"</b> ?</p>",
   [{t:"Annuler"},{t:"Supprimer",go:1,f:()=>api("/api/presets/delete",{id:p.id}).then(()=>{selId=null;loadPresets();})}]);};
$("#precall").onclick=()=>{
  const p=presets.find(x=>x.id===selId);if(!p||locked)return;
  const idx=scopeIdx(),wp=$("#pphan").checked;let n=0,big=0,bi=-1,nph=0;
  for(const k in p.gains){const i=+k;if(idx&&!idx.includes(i))continue;const c=S.gains[i];
    if(c===null||c===undefined||Math.abs(c-p.gains[k])>1e-6){n++;const d=c==null?0:Math.abs(p.gains[k]-c);if(d>big){big=d;bi=i;}}}
  if(wp)for(const k in p.phantom){const i=+k;if(idx&&!idx.includes(i))continue;if(S.phantom[i]!==p.phantom[k])nph++;}
  const html=`<p>Rappeler <b>${esc(p.name)}</b> (${idx?"banque affichée":"toutes les entrées"}) :</p>
   <p>• <b>${n}</b> gain(s) vont changer`+(bi>=0?`, plus grand écart <b>${big.toFixed(1)} dB</b> (voie ${label(bi)})`:"")+`<br>
   • 48 V : `+(wp?`<b>${nph}</b> changement(s)`:"non touché")+`</p>
   <p style="color:var(--mut)">Un bouton « Annuler le dernier rappel » restaure les valeurs précédentes.</p>`;
  if(n===0&&nph===0)return toast("Rien à changer : la console est déjà dans cet état.");
  modal("Confirmer le rappel",html,[{t:"Annuler"},{t:"Rappeler",go:1,f:()=>
    api("/api/presets/recall",{id:p.id,indices:idx,phantom:wp}).then(r=>toast(r.ok?"Rappel envoyé — vérification en cours…":r.error,r.ok?"ok":"err"))}]);
};
$("#pundo").onclick=()=>locked?toast("Verrouillé","err"):api("/api/presets/undo",{}).then(r=>toast(r.ok?"Valeurs précédentes restaurées":"Rien à annuler",r.ok?"ok":"err"));
$("#pexp").onclick=()=>{location.href="/api/export";};
$("#pimp").onclick=()=>$("#pfile").click();
$("#pfile").onchange=e=>{const f=e.target.files[0];if(!f)return;const rd=new FileReader();
  rd.onload=()=>{let j;try{j=JSON.parse(rd.result);}catch(_){return toast("Fichier JSON invalide","err");}
    api("/api/import",{presets:j.presets||[]}).then(r=>{toast(r.added+" scène(s) importée(s)","ok");loadPresets();});};
  rd.readAsText(f);e.target.value="";};

/* ---------- barre du haut ---------- */
$("#bconn").onclick=()=>{
  if(S.connected||S.trying)return api("/api/disconnect",{});
  const ip=$("#ip").value.trim();if(!ip)return toast("Entrez l'adresse IP de la X32","err");
  try{localStorage.setItem("x32ip",ip);}catch(_){}
  api("/api/connect",{ip}).then(r=>{if(!r.ok)toast(r.error||"Échec","err");});
};
$("#ip").addEventListener("keydown",e=>{if(e.key==="Enter")$("#bconn").click();});
$("#bdemo").onclick=()=>{$("#ip").value="127.0.0.1";api("/api/demo",{}).then(r=>{if(!r.ok)toast(r.error,"err");});};
$("#bref").onclick=()=>{api("/api/refresh",{});toast("Relecture des gains…");};
$("#block").onclick=()=>{locked=!locked;document.body.classList.toggle("locked",locked);$("#block").classList.toggle("act",locked);
  $("#block").innerHTML=locked?"&#128274; Verrouillé":"&#128274; Verrou";update();};

/* ---------- init ---------- */
(function(){
  const b=$("#banks");BANKS.forEach((x,n)=>{const e=document.createElement("button");e.className="bank";e.textContent=x[0].replace("AES50-","");
    e.title=x[0];e.onclick=()=>{bank=n;buildStrips();};b.appendChild(e);});
  try{const ip=localStorage.getItem("x32ip");if(ip)$("#ip").value=ip;}catch(_){}
  buildStrips();loadPresets();
  let rev=-1;
  async function poll(){
    try{const s=await api("/api/state");
      if(s.rev!==rev||s.connected!==S.connected||s.trying!==S.trying){rev=s.rev;S=s;update();}
    }catch(_){S.connected=false;S.trying=false;update();}
    setTimeout(poll,150);
  }
  poll();
})();
</script></body></html>
"""


# --------------------------------------------------------------------------
#  Main
# --------------------------------------------------------------------------
def pick_data_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
    for d in (base, os.path.expanduser("~")):
        try:
            test = os.path.join(d, ".x32_write_test")
            with open(test, "w") as f:
                f.write("x")
            os.remove(test)
            return os.path.join(d, "x32_presets.json")
        except OSError:
            continue
    return "x32_presets.json"


def main():
    global STORE, X32_PORT
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--version", action="version", version="%s %s" % (APP_NAME, APP_VERSION))
    ap.add_argument("--ip", help="adresse IP de la X32 (pre-remplit le champ)")
    ap.add_argument("--sim", action="store_true", help="demarre un simulateur de X32 et s'y connecte")
    ap.add_argument("--web-port", type=int, default=8032, help="port de l'interface web locale (defaut 8032)")
    ap.add_argument("--no-browser", action="store_true", help="n'ouvre pas le navigateur")
    ap.add_argument("--data", help="chemin du fichier de scenes (defaut : x32_presets.json a cote du script)")
    a = ap.parse_args()

    STORE = PresetStore(a.data or pick_data_path())

    srv = None
    for port in range(a.web_port, a.web_port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        print("Impossible d'ouvrir un port local pour l'interface.")
        sys.exit(1)
    port = srv.server_address[1]
    ALLOWED_HOSTS.update({"127.0.0.1:%d" % port, "localhost:%d" % port})
    url = "http://127.0.0.1:%d/" % port

    if a.sim:
        ok, err = start_sim()
        if not ok:
            print(err)
            sys.exit(1)
        CLIENT.connect("127.0.0.1")
        CLIENT.demo = True
    elif a.ip:
        CLIENT.connect(a.ip)

    print("%s v%s  -  interface : %s" % (APP_NAME, APP_VERSION, url))
    print("Scenes : %s" % STORE.path)
    print("Ctrl+C pour quitter.")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CLIENT.disconnect()


if __name__ == "__main__":
    main()
