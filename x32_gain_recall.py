#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X32 GAIN RECALL
===============
Petit outil pour regler, sauvegarder et rappeler les GAINS (preamps / headamps)
d'une Behringer X32 / Midas M32 via le protocole OSC (UDP, port 10023).

- Aucune dependance : Python 3.8+ (bibliotheque standard uniquement).
- L'interface s'ouvre dans le navigateur, accessible aussi depuis le reseau local (tablette, telephone),
  protegee par un code a 4 chiffres affiche au demarrage. Option --local-only pour desactiver cet acces reseau.
- Les scenes de gains sont stockees dans x32_presets.json a cote du script.

Usage :
    python x32_gain_recall.py              # lance l'appli (accessible au reseau local, code a 4 chiffres)
    python x32_gain_recall.py --sim        # lance avec une X32 simulee (test sans console)
    python x32_gain_recall.py --ip 192.168.1.50
    python x32_gain_recall.py --local-only # accessible uniquement depuis cette machine (comme avant la 1.3)

Sources du protocole : "UNOFFICIAL X32/M32 OSC REMOTE PROTOCOL" (P.-G. Maillot), v4.02.
  - /headamp/[000..127]/gain    : float 0..1  <->  -12..+60 dB, pas de 0,5 dB (145 valeurs)
  - /headamp/[000..127]/phantom : int 0/1
  - 000-031 = entrees locales XLR, 032-079 = AES50 A, 080-127 = AES50 B
  - /xremote a renouveler avant 10 s pour recevoir les changements faits sur la console
"""
import argparse
import hmac
import json
import math
import os
import random
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from brand_icon import LOGO_SVG
from lv1.companion import CompanionPoller, DEFAULT_URL as COMPANION_URL
from lv1.patchmap import PatchMap, MANUAL_FILENAME, DEFAULT_DEVICES, LIVE_DB

APP_NAME = "X/M32 Gain Recall for eMotion LV1"
APP_SHORT = "X/M32 Gain Recall"
APP_AUTHOR = "Joseph Savigny"
APP_VERSION = "2.2.0"
X32_PORT = 10023
GAIN_MIN, GAIN_MAX, GAIN_STEP = -12.0, 60.0, 0.5
N_HA = 128
LV1 = None            # lv1.patchmap.PatchMap (table EXP -> canal LV1), creee dans main() ou par le float en --direct
LV1_COMPANION = None  # lv1.companion.CompanionPoller (couleur + nom des canaux LV1), idem


LV1_NO_COLORS = False  # --no-colors : ni couleurs ni noms LV1
BROWSE_LOCK = threading.Lock()  # une seule fenetre « choisir un dossier » a la fois


def lv1_channels_snapshot(client):
    """{canal LV1: {"color", "name", "label"}} pour les canaux qui recoivent un preampli X32 : lus dans la
    base de la LV1 (lv1/channelinfo.py, sans Companion) ; si Companion est active (--companion), ses
    valeurs passent en priorite."""
    if not LV1 or LV1_NO_COLORS:
        return {}
    # tous les canaux connus de la LV1 (la vue LV1 affiche aussi ceux sans preampli X32, pour rester
    # alignee sur ses tranches), plus ceux en service absents de la session (table manuelle)
    out = LV1.channel_info(set(LV1.channel_info()) | lv1_channels_in_use(client))
    if LV1_COMPANION:
        for ch, v in LV1_COMPANION.snapshot().items():
            if ch in out:
                for k in ("color", "name", "label"):
                    if v.get(k):
                        out[ch][k] = v[k]
    return out


def lv1_channels_in_use(client):
    """Canaux LV1 qui recoivent en ce moment un preampli X32 (EXP lu sur la console -> table LV1) : ceux
    dont on demande couleur et nom a Companion."""
    if not LV1:
        return set()
    m = LV1.exp_to_channel()
    return {m.get(e) for e in list(client.exp_map.values()) if e} - {None}


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
            args.append(bytes(data[pos + 4:pos + 4 + n]))
            pos += 4 + ((n + 3) & ~3)
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
#  Routing : lecture d'un fichier .scn, description lisible, ecriture par "nodes" OSC
# --------------------------------------------------------------------------
ROUTING_GROUPS = {"io": "Routing E/S (blocs + patchs utilisateur)", "out": "Patch de sortie console (/outputs)"}
SEED_SCN = r'''#4.0# "Routing LV1" "" %000000000 1
/config/userrout/out 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
/config/userrout/in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48
/config/routing REC
/config/routing/IN UIN1-8 UIN9-16 UIN17-24 UIN25-32 UIN1-6
/config/routing/AES50A UOUT1-8 UOUT9-16 UOUT17-24 UOUT25-32 UOUT33-40 UOUT41-48
/config/routing/AES50B A17-24 A25-32 A17-24 OUT9-16 P161-8 P169-16
/config/routing/CARD UIN1-8 UIN9-16 UIN17-24 UIN25-32
/config/routing/OUT UOUT1-4 UOUT5-8 UOUT9-12 UOUT13-16
/config/routing/PLAY CARD1-8 CARD9-16 CARD17-24 CARD25-32 AUX1-4
/outputs/main/01 4 POST OFF
/outputs/main/01/delay OFF 0.3
/outputs/main/02 5 POST OFF
/outputs/main/02/delay OFF 0.3
/outputs/main/03 6 POST OFF
/outputs/main/03/delay OFF 0.3
/outputs/main/04 7 POST OFF
/outputs/main/04/delay OFF 0.3
/outputs/main/05 8 POST OFF
/outputs/main/05/delay OFF 0.3
/outputs/main/06 9 POST OFF
/outputs/main/06/delay OFF 0.3
/outputs/main/07 10 POST OFF
/outputs/main/07/delay OFF 0.3
/outputs/main/08 11 POST OFF
/outputs/main/08/delay OFF 0.3
/outputs/main/09 12 POST OFF
/outputs/main/09/delay OFF 0.3
/outputs/main/10 13 POST OFF
/outputs/main/10/delay OFF 0.3
/outputs/main/11 14 POST OFF
/outputs/main/11/delay OFF 0.3
/outputs/main/12 15 POST OFF
/outputs/main/12/delay OFF 0.3
/outputs/main/13 16 POST OFF
/outputs/main/13/delay OFF 0.3
/outputs/main/14 17 POST OFF
/outputs/main/14/delay OFF 0.3
/outputs/main/15 18 POST OFF
/outputs/main/15/delay OFF 0.3
/outputs/main/16 19 POST OFF
/outputs/main/16/delay OFF 0.3
/outputs/aux/01 0 POST OFF
/outputs/aux/02 0 POST OFF
/outputs/aux/03 0 POST OFF
/outputs/aux/04 0 POST OFF
/outputs/aux/05 54 IN/LC+M OFF
/outputs/aux/06 55 IN/LC+M OFF
/outputs/p16/01 26 <-EQ OFF
/outputs/p16/01/iQ OFF none Linear 0
/outputs/p16/02 27 <-EQ OFF
/outputs/p16/02/iQ OFF none Linear 0
/outputs/p16/03 28 <-EQ OFF
/outputs/p16/03/iQ OFF none Linear 0
/outputs/p16/04 29 <-EQ OFF
/outputs/p16/04/iQ OFF none Linear 0
/outputs/p16/05 30 <-EQ OFF
/outputs/p16/05/iQ OFF none Linear 0
/outputs/p16/06 31 <-EQ OFF
/outputs/p16/06/iQ OFF none Linear 0
/outputs/p16/07 32 <-EQ OFF
/outputs/p16/07/iQ OFF none Linear 0
/outputs/p16/08 33 <-EQ OFF
/outputs/p16/08/iQ OFF none Linear 0
/outputs/p16/09 34 <-EQ OFF
/outputs/p16/09/iQ OFF none Linear 0
/outputs/p16/10 35 <-EQ OFF
/outputs/p16/10/iQ OFF none Linear 0
/outputs/p16/11 36 <-EQ OFF
/outputs/p16/11/iQ OFF none Linear 0
/outputs/p16/12 37 <-EQ OFF
/outputs/p16/12/iQ OFF none Linear 0
/outputs/p16/13 38 <-EQ OFF
/outputs/p16/13/iQ OFF none Linear 0
/outputs/p16/14 39 <-EQ OFF
/outputs/p16/14/iQ OFF none Linear 0
/outputs/p16/15 40 <-EQ OFF
/outputs/p16/15/iQ OFF none Linear 0
/outputs/p16/16 41 <-EQ OFF
/outputs/p16/16/iQ OFF none Linear 0
/outputs/aes/01 1 POST OFF
/outputs/aes/02 2 POST OFF
/outputs/rec/01 1 <-EQ
/outputs/rec/02 2 <-EQ'''


def norm_val(v):
    return " ".join(str(v).split())


def same_val(a, b):
    return a is not None and b is not None and norm_val(a).lower() == norm_val(b).lower()


def parse_scn(text):
    """Extrait d'une scene X32 (.scn) uniquement les lignes de routing. Renvoie (nom, version, {groupe: {chemin: valeurs}})."""
    name, fw = None, None
    nodes = {"io": {}, "out": {}}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") and name is None:
            m = re.match(r'^#([\d.]+)#\s+"([^"]*)"', line)
            if m:
                fw, name = m.group(1), m.group(2)
            continue
        if not line.startswith("/"):
            continue
        parts = line.split(None, 1)
        path, val = parts[0], (norm_val(parts[1]) if len(parts) > 1 else "")
        if path.startswith("/config/routing") or path.startswith("/config/userrout"):
            nodes["io"][path] = val
        elif path.startswith("/outputs/"):
            nodes["out"][path] = val
    return name, fw, nodes


def _user_name(v, kind):
    if v == 0:
        return "OFF"
    if 1 <= v <= 32:
        return "Local In %d" % v
    if 33 <= v <= 80:
        return "AES50-A %d" % (v - 32)
    if 81 <= v <= 128:
        return "AES50-B %d" % (v - 80)
    if 129 <= v <= 160:
        return "Carte In %d" % (v - 128)
    if 161 <= v <= 166:
        return "Aux In %d" % (v - 160)
    if v == 167:
        return "Talkback int."
    if v == 168:
        return "Talkback ext."
    if kind == "out":
        if 169 <= v <= 184:
            return "Sortie console %d" % (v - 168)
        if 185 <= v <= 200:
            return "P16 %d" % (v - 184)
        if 201 <= v <= 206:
            return "Aux %d" % (v - 200)
        if v == 207:
            return "Monitor L"
        if v == 208:
            return "Monitor R"
    return "?%d" % v


def _split_num(name):
    m = re.match(r"^(.*?)(\d+)$", name)
    return (m.group(1), int(m.group(2))) if m else (name, None)


def compress(names):
    out, i, n = [], 0, len(names)
    while i < n:
        pre, num = _split_num(names[i])
        j = i
        if num is not None:
            while j + 1 < n:
                p2, n2 = _split_num(names[j + 1])
                if p2 == pre and n2 is not None and n2 == _split_num(names[j])[1] + 1:
                    j += 1
                else:
                    break
            label = names[i] if j == i else "%s%d–%d" % (pre, num, _split_num(names[j])[1])
        else:
            while j + 1 < n and names[j + 1] == names[i]:
                j += 1
            label = names[i]
        out.append({"a": i + 1, "b": j + 1, "src": label})
        i = j + 1
    return out


_BLOCKS = {"IN": ["1-8", "9-16", "17-24", "25-32", "AUX"],
           "AES50A": ["1-8", "9-16", "17-24", "25-32", "33-40", "41-48"],
           "AES50B": ["1-8", "9-16", "17-24", "25-32", "33-40", "41-48"],
           "CARD": ["1-8", "9-16", "17-24", "25-32"],
           "OUT": ["1-4", "5-8", "9-12", "13-16"]}
_LAB = {"CARD": "Carte In ", "OUT": "Sortie console ", "P16": "P16 ", "AUX": "Aux ", "AN": "Local In ", "A": "AES50-A ", "B": "AES50-B "}


def _tok_names(tok, count, uin, uout):
    m = re.match(r"^(UOUT|UIN|CARD|OUT|P16|AUX|AN|A|B)(\d+)-(\d+)", tok)
    if not m:
        return [tok] * count
    pre, a, b = m.group(1), int(m.group(2)), int(m.group(3))
    nums = list(range(a, b + 1))[:count]
    if pre == "UOUT":
        return [uout[k - 1] if 0 < k <= len(uout) else "?" for k in nums]
    if pre == "UIN":
        return [uin[k - 1] if 0 < k <= len(uin) else "?" for k in nums]
    return [_LAB[pre] + str(k) for k in nums]


def describe_routing(io):
    """Description lisible du routing : qui alimente quoi (patchs utilisateur + blocs)."""
    def ints(path):
        try:
            return [int(x) for x in io.get(path, "").split()]
        except ValueError:
            return []
    uin_raw, uout_raw = ints("/config/userrout/in"), ints("/config/userrout/out")
    uin = [_user_name(v, "in") for v in uin_raw]
    uout = [_user_name(v, "out") for v in uout_raw]
    d = {"mode": io.get("/config/routing", ""), "userin": compress(uin) if uin else [], "userout": compress(uout) if uout else [], "ports": {}}
    for port, labels in _BLOCKS.items():
        toks = io.get("/config/routing/" + port, "").split()
        if len(toks) < len(labels):
            continue
        names = []
        for tok, lab in zip(toks, labels):
            cnt = 6 if lab == "AUX" else (int(lab.split("-")[1]) - int(lab.split("-")[0]) + 1)
            names += _tok_names(tok, cnt, uin, uout)
        d["ports"][port] = compress(names)
    return d


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
        self.ha_map = [None] * 32      # canal -> index de headamp (/-ha/NN/index), -1 = source interne
        self.meters_on = True
        self.meters_lin = [0.0] * 32   # niveaux d'entree lineaires (0..1 = pleine echelle), canaux 1..32
        self.meter_ts = 0.0            # date de la derniere trame de meters recue
        self.meter_req_ts = 0.0
        self.meter_variant = 0
        self.node_cache = {}           # chemin -> valeurs (reponses /node)
        self.routing_last = None
        self.routing_undo = None
        self.exp_map = {}              # idx global (0-127) -> numero Carte/EXP (1-32), d'apres le patch REEL (voir refresh_exp_map)

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
                "names": self._names_by_headamp(),
                "meters_on": self.meters_on,
                "routing_last": self.routing_last,
                "routing_can_undo": self.routing_undo is not None,
                "known": sum(1 for g in self.gains if g is not None),
                "demo": self.demo,
                "last_recall": self.last_recall,
                "can_undo": self.undo is not None,
                "error": self.error,
                "exp_map": dict(self.exp_map),
                # numero EXP -> canal LV1 ("In N") : table manuelle et/ou session .emo, voir lv1/patchmap.py.
                # Vide si rien n'est configure - jamais de correspondance devinee.
                "lv1_map": LV1.exp_to_channel() if LV1 else {},
                # vue LV1 : canal -> [EXP voie G, EXP voie D] (un EXP peut alimenter plusieurs canaux)
                "lv1_sources": LV1.channel_sources() if LV1 else {},
                "lv1_count": LV1.channel_count() if LV1 else 0,
                # couche affichee sur la LV1 (bank = 0 pour Ch 1-16...) : le float la suit en vue LV1
                "lv1_layer": LV1.layer() if LV1 else None,
                # couches des deux vues de la LV1 (le float suit celle de l'onglet affiche, Mixer 1 ou 2)
                "lv1_layers": LV1.layers() if LV1 else {},
                "lv1": LV1.status() if LV1 else None,
                # couleur / nom / libelle a afficher par canal LV1, partages par le navigateur et le float
                # (base LV1, + Companion si active) - voir lv1_channels_snapshot()
                "lv1_channels": lv1_channels_snapshot(self),
                "companion_ok": LV1_COMPANION.reachable if LV1_COMPANION else None,
            }

    def ch_of_ha(self, idx):
        """Canal d'entree alimente par le headamp idx (via /-ha/NN/index). Tant que la console n'a
        repondu pour aucun canal, on suppose un patch 1:1 (headamp n = canal n+1) pour les 32 entrees locales."""
        if all(v is None for v in self.ha_map):
            return idx if 0 <= idx < 32 else None
        for ch, v in enumerate(self.ha_map):
            if v == idx:
                return ch
        return None

    def _names_by_headamp(self):
        out = [None] * N_HA
        for i in range(N_HA):
            ch = self.ch_of_ha(i)
            if ch is not None:
                out[i] = self.names[ch]
        return out

    def meters_snapshot(self):
        with self.lock:
            live = self.meters_on and self.sock is not None and (time.time() - self.meter_ts) < 1.5
            v = [None] * N_HA
            if live:
                for i in range(N_HA):
                    ch = self.ch_of_ha(i)
                    if ch is not None:
                        lin = self.meters_lin[ch]
                        v[i] = round(20.0 * math.log10(lin), 1) if lin > 1e-4 else -80.0
            return {"on": self.meters_on, "live": bool(live), "v": v}

    def set_meters(self, on):
        with self.lock:
            self.meters_on = bool(on)
            self.meter_ts = 0.0
            self._bump()
        if on:
            self._send_meters_request()

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
            self.ha_map = [None] * 32
            self.meters_lin = [0.0] * 32
            self.meter_ts = 0.0
            self.meter_variant = 0
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

    def _parse_meters(self, args):
        # /meters/1 : blob = <nb de floats : int32 little-endian> puis <floats little-endian>
        # 96 valeurs : 32 entrees (niveau lineaire), 32 reductions de gate, 32 reductions de comp.
        try:
            blob = args[0]
            n = struct.unpack("<i", blob[:4])[0]
            if n < 32 or len(blob) < 4 + 4 * n:
                return
            vals = struct.unpack("<%df" % n, blob[4:4 + 4 * n])
        except Exception:
            return
        self.meters_lin = [max(0.0, float(x)) for x in vals[:32]]
        self.meter_ts = time.time()

    def _handle(self, addr, args):
        if addr in ("node", "/node") and args and isinstance(args[0], str):
            parts = args[0].strip().split(None, 1)
            if parts:
                self.node_cache[parts[0]] = norm_val(parts[1]) if len(parts) > 1 else ""
            return
        if addr == "/meters/1" and args and isinstance(args[0], (bytes, bytearray)):
            self._parse_meters(args)
            return
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
            elif addr.startswith("/-ha/") and addr.endswith("/index") and args and isinstance(args[0], int):
                try:
                    n = int(addr.split("/")[2])
                except ValueError:
                    return
                if 0 <= n < 32:
                    self.ha_map[n] = args[0]; self._bump()
            elif addr == "/xinfo" and len(args) >= 4:
                self.info = {"ip": args[0], "name": args[1], "model": args[2], "fw": args[3]}; self._bump()
            elif addr == "/info" and len(args) >= 4 and not self.info:
                self.info = {"name": args[1], "model": args[2], "fw": args[3]}; self._bump()

    def _keepalive_loop(self, gen):
        # /xremote expire au bout de 10 s cote console : on renouvelle toutes les 5 s.
        while self.gen == gen:
            self._send("/xremote")
            self._send("/info")
            self._send_meters_request()
            for k in range(10):
                if self.gen != gen:
                    return
                time.sleep(0.5)
                if self.gen != gen:
                    return
                # pas de trame de meters apres ~1,5 s : on essaie l'autre variante de requete
                if k == 3 and self.meters_on and self.last_rx > 0 and self.meter_ts < self.meter_req_ts:
                    self.meter_variant = (self.meter_variant + 1) % 2
                    self._send_meters_request()

    def _send_meters_request(self):
        """/meters/1 : 32 entrees + reductions gate/comp. La console envoie ~200 trames en 10 s : on renouvelle
        toutes les 5 s. Le format exact de la requete est reconstitue d'apres la doc (2 variantes essayees)."""
        if not self.meters_on or not self.sock:
            return
        self.meter_req_ts = time.time()
        if self.meter_variant == 0:
            self._send("/meters", "/meters/1", 0, 0, 1)
        else:
            self._send("/meters", "/meters/1")

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
            if not only_missing or self.ha_map[n - 1] is None:
                self._send("/-ha/%02d/index" % (n - 1))
            time.sleep(0.003)

    # -- routing (nodes X32 : /node pour lire, / pour ecrire) ---------------
    def get_nodes(self, paths, timeout=2.0):
        for p in paths:
            self.node_cache.pop(p, None)
        t0 = time.time()
        sent = 0.0
        while time.time() - t0 < timeout:
            if time.time() - sent > 0.7:      # (re)demande ce qui manque : UDP peut perdre des paquets
                for p in paths:
                    if p not in self.node_cache:
                        self._send("/node", p.lstrip("/"))
                        time.sleep(0.004)
                sent = time.time()
            if all(p in self.node_cache for p in paths):
                break
            time.sleep(0.05)
        return {p: self.node_cache.get(p) for p in paths}

    def routing_diff(self, nodes):
        cur = self.get_nodes(list(nodes))
        rows = [{"path": p, "current": cur[p], "target": v, "same": same_val(cur[p], v)} for p, v in nodes.items()]
        return rows

    def apply_routing(self, nodes, label=""):
        rows = self.routing_diff(nodes)
        changed = [r for r in rows if not r["same"]]
        if changed:  # une application "a vide" ne doit pas ecraser le point d'annulation precedent
            with self.lock:
                self.routing_undo = {"label": label, "lines": {r["path"]: r["current"] for r in changed if r["current"] is not None}}
        for r in changed:
            self._send("/", "%s %s" % (r["path"], r["target"]))
            time.sleep(0.03)
        res = {"t": time.time(), "name": label, "sent": len(changed), "total": len(rows),
               "unreadable": [r["path"] for r in changed if r["current"] is None], "verified": None, "bad": []}
        self.routing_last = res
        self._bump()
        threading.Thread(target=self._verify_routing, args=(res, {r["path"]: r["target"] for r in changed}), daemon=True).start()
        return res

    def _verify_routing(self, res, targets):
        time.sleep(0.6)
        new = self.get_nodes(list(targets))
        with self.lock:
            res["bad"] = [p for p, v in targets.items() if not same_val(new.get(p), v)]
            res["verified"] = len(res["bad"]) == 0
            self._bump()

    def undo_routing(self):
        with self.lock:
            u, self.routing_undo = self.routing_undo, None
        if not u or not u["lines"]:
            return False
        for p, v in u["lines"].items():
            self._send("/", "%s %s" % (p, v))
            time.sleep(0.03)
        with self.lock:
            self.routing_last = {"t": time.time(), "name": "Annulation : " + u["label"], "sent": len(u["lines"]),
                                 "total": len(u["lines"]), "unreadable": [], "verified": None, "bad": []}
            self._bump()
        res = self.routing_last
        threading.Thread(target=self._verify_routing, args=(res, dict(u["lines"])), daemon=True).start()
        return True

    def refresh_exp_map(self, timeout=1.2):
        """Interroge EN DIRECT, sur la console connectee, /config/routing/CARD + /config/userrout/in|out,
        et en deduit quel numero Carte/EXP (1-32, celui affiche dans le menu de patch de la LV1) recoit
        chaque preampli - d'apres le patch REELLEMENT charge sur la console en ce moment (pas une
        supposition sur un profil particulier). Reutilise describe_routing(), deja utilise par l'onglet
        Routing pour comparer un profil au patch courant. A appeler apres connexion/Demo, apres
        « Relire », et apres l'envoi d'un routing - jamais en boucle (chaque appel interroge la
        console, ~1 s).

        Limite assumee : seuls les prefixes "Local In ", "AES50-A " et "AES50-B " (gains/preamplis)
        sont traduits en numero EXP. Un canal patche vers la carte depuis une autre source (Carte In
        en boucle, Aux, Talkback...) n'a pas de numero de gain a afficher et est ignore - case vide,
        pas un numero invente. Idem si la lecture echoue (deconnecte, firmware different, timeout) :
        exp_map reste vide plutot que de garder un ancien resultat potentiellement faux."""
        nodes = self.get_nodes(["/config/routing/CARD", "/config/userrout/in", "/config/userrout/out"], timeout=timeout)
        m = {}
        if nodes.get("/config/routing/CARD") and nodes.get("/config/userrout/in"):
            desc = describe_routing(nodes)
            rng = re.compile(r"^(.*?)(\d+)(?:–(\d+))?$")
            for seg in desc["ports"].get("CARD", []):
                mo = rng.match(seg["src"])
                if not mo:
                    continue
                prefix, n0 = mo.group(1), int(mo.group(2))
                n1 = int(mo.group(3)) if mo.group(3) else n0
                for off, n in enumerate(range(n0, n1 + 1)):
                    idx = None
                    if prefix == "Local In ":
                        idx = n - 1
                    elif prefix == "AES50-A ":
                        idx = 31 + n
                    elif prefix == "AES50-B ":
                        idx = 79 + n
                    if idx is not None:
                        m[idx] = seg["a"] + off
        with self.lock:
            self.exp_map = m
            self._bump()

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
        self.sock.settimeout(0.05)
        self.meter_clients = {}
        self.t0 = time.time()
        rnd = random.Random(32)
        self.gain = [quantize(rnd.uniform(8, 42)) for _ in range(N_HA)]
        self.phantom = [1 if i in (6, 7, 11) else 0 for i in range(N_HA)]
        self.names = {i + 1: n for i, n in enumerate(self.NAMES)}
        self.stop = False
        # etat "usine" du routing (different du profil LV1) + patch de sortie
        _n = parse_scn(SEED_SCN)[2]
        self.nodes = dict(_n["out"])
        self.nodes.update({
            "/config/routing": "REC",
            "/config/routing/IN": "AN1-8 AN9-16 A1-8 A9-16 AN1-6",
            "/config/routing/AES50A": "OUT1-8 OUT9-16 A17-24 A25-32 A33-40 A41-48",
            "/config/routing/AES50B": "B1-8 B9-16 B17-24 B25-32 B33-40 B41-48",
            "/config/routing/CARD": "CARD1-8 CARD9-16 CARD17-24 CARD25-32",
            "/config/routing/OUT": "OUT1-4 OUT5-8 OUT9-12 OUT13-16",
            "/config/routing/PLAY": "AN1-8 AN9-16 AN17-24 AN25-32 AUX1-4",
            "/config/userrout/in": " ".join(str(i) for i in range(1, 33)),
            "/config/userrout/out": " ".join(["0"] * 48)})
        self.node_log = []

    def _meter_tick(self):
        now = time.time()
        for peer, st in list(self.meter_clients.items()):
            if now > st[0]:
                del self.meter_clients[peer]
                continue
            if now < st[2]:
                continue
            st[2] = now + 0.05 * st[1]
            t = now - self.t0
            vals = []
            for c in range(32):
                amp = 0.05 * (1.0 + (c % 5)) if c < 16 else 0.0004
                v = amp * 10 ** ((self.gain[c] - 20.0) / 20.0) * (0.55 + 0.45 * abs(math.sin(t * (2.0 + c * 0.37))))
                vals.append(min(v, 8.0))
            vals += [0.0] * 64
            blob = struct.pack("<i", len(vals)) + struct.pack("<%df" % len(vals), *vals)
            pkt = _pad(b"/meters/1") + _pad(b",b") + struct.pack(">i", len(blob)) + blob
            try:
                self.sock.sendto(pkt, peer)
            except OSError:
                pass

    def run(self):
        while not self.stop:
            try:
                data, peer = self.sock.recvfrom(4096)
                a, args = osc_decode(data)
            except socket.timeout:
                self._meter_tick()
                continue
            except OSError:
                continue
            except Exception:
                continue
            self._meter_tick()
            send = lambda *m: self.sock.sendto(osc_encode(*m), peer)
            if a == "/" and args and isinstance(args[0], str):
                parts = args[0].strip().split(None, 1)
                if parts and parts[0] in self.nodes:
                    self.nodes[parts[0]] = norm_val(parts[1]) if len(parts) > 1 else ""
                    self.node_log.append(parts[0])
            elif a == "/node" and args and isinstance(args[0], str):
                path = "/" + args[0].lstrip("/")
                if path in self.nodes:
                    send("node", "%s %s\n" % (path, self.nodes[path]))
            elif a == "/meters" and args and args[0] == "/meters/1":
                tf = args[3] if len(args) >= 4 and isinstance(args[3], int) and 1 <= args[3] <= 99 else 1
                self.meter_clients[peer] = [time.time() + 10, tf, 0.0]
            elif a.startswith("/-ha/") and a.endswith("/index") and not args:
                try:
                    send(a, int(a.split("/")[2]))
                except ValueError:
                    pass
            elif a == "/info":
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
            with open(self.path, "r", encoding="utf-8-sig") as f:
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


class RoutingStore:
    """Profils de routing (extraits de scenes .scn), stockes en JSON. Un profil integre 'Routing LV1' est cree au 1er lancement."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.items, self.seeded = [], False
        self.load()
        if not self.seeded:
            name, fw, nodes = parse_scn(SEED_SCN)
            self._add(name or "Routing LV1", fw, nodes, "intégré (Routing_LV1.scn)")
            self.seeded = True
            self._write()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            self.items, self.seeded = d.get("profiles", []), bool(d.get("seeded"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            try:
                os.replace(self.path, self.path + ".corrompu-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            except OSError:
                pass

    def _write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "seeded": self.seeded, "profiles": self.items}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def _add(self, name, fw, nodes, source):
        pr = {"id": uuid.uuid4().hex[:12], "name": name[:60], "created": datetime.now().isoformat(timespec="seconds"),
              "source": source, "fw": fw, "nodes": nodes}
        self.items.append(pr)
        return pr

    def add(self, name, fw, nodes, source):
        with self.lock:
            pr = self._add(name, fw, nodes, source)
            self._write()
            return pr

    def get(self, pid):
        with self.lock:
            return next((json.loads(json.dumps(x)) for x in self.items if x["id"] == pid), None)

    def summaries(self):
        with self.lock:
            return [{"id": x["id"], "name": x["name"], "created": x["created"], "source": x.get("source", ""), "fw": x.get("fw"),
                     "counts": {g: len(x["nodes"].get(g, {})) for g in ROUTING_GROUPS},
                     "desc": describe_routing(x["nodes"].get("io", {}))} for x in self.items]

    def rename(self, pid, name):
        with self.lock:
            for x in self.items:
                if x["id"] == pid:
                    x["name"] = name
                    self._write()
                    return True
        return False

    def delete(self, pid):
        with self.lock:
            n = len(self.items)
            self.items = [x for x in self.items if x["id"] != pid]
            if len(self.items) != n:
                self._write()
                return True
        return False


# --------------------------------------------------------------------------
#  Serveur HTTP local + API
# --------------------------------------------------------------------------
CLIENT = X32Client()
STORE = None
ROUTINGS = None
SIM = None
ALLOWED_HOSTS = set()
ALLOW_ANY_HOST = False  # active par --lan : accepte tout Host: (protection deplacee sur le code de connexion)
LAN_CODE = None  # code a 4 chiffres requis pour se connecter en --lan ; None = --lan-sans-mdp (aucune protection)
WEB_PORT = 8032  # port reellement utilise par ce serveur (peut differer de --web-port si deja pris) ; pour le bouton "Lancer Float"
CODE_PATH = None  # chemin du fichier x32_lan_config.json ; None si --lan-sans-mdp ou --local-only (code non geré sur disque)
LOCAL_URL = ""  # http://127.0.0.1:PORT/ ; affiche dans l'UI (demande : "version + ip:port + code visibles")
LAN_URLS = []  # une par adresse IPv4 locale detectee, affichees dans l'UI pour la connexion tablette
LAN_COOKIE = "x32lansess"
SESSIONS = set()  # jetons de session valides, en memoire seulement (perdus a l'arret du script)
LOGIN_ATTEMPTS = {}  # ip -> {"fails": int, "locked_until": epoch, "seen": epoch} - limite le brute-force du code
LOGIN_MAX_TRACKED_IPS = 500  # purge grossiere si depasse (usage reseau local, pas cense arriver)


def load_or_create_lan_config(path, regenerate=False):
    """Fichier de config JSON {"code": "1234"} conservant le code d'acces entre deux lancements en --lan.
    Cree un nouveau code a 4 chiffres si le fichier n'existe pas, est illisible, ou si regenerate=True."""
    if not regenerate:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            code = data.get("code")
            if isinstance(code, str) and code.isdigit() and len(code) == 4:
                return code
        except (OSError, ValueError):
            pass
    code = "%04d" % secrets.randbelow(10000)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"code": code, "cree_le": datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False, indent=1)
        try:
            os.chmod(path, 0o600)  # best-effort : illisible par les autres comptes de la machine
        except OSError:
            pass
    except OSError as e:
        print("Attention : code --lan non sauvegarde sur disque (%s). Il changera au prochain lancement." % e)
    return code


def _local_ipv4_addresses():
    """Best-effort : liste des adresses IPv4 locales (hors 127.0.0.1), pour affichage et allowlist."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # n'envoie rien, sert juste a choisir l'interface de sortie
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def scan_network(timeout=1.5, port=X32_PORT):
    """Decouvre les consoles X32/M32 sur le reseau local : diffuse /xinfo en broadcast UDP sur le port OSC
    (10023) et collecte les reponses pendant `timeout` secondes.
    /xinfo est la requete d'identification documentee du protocole OSC X32 (deja utilisee ailleurs dans ce
    fichier, par ex. a la connexion manuelle). Le broadcast lui-meme n'est pas documente officiellement, mais
    une capture Wireshark independante (forum ControlBooth, utilisateur StradivariusBone, sujet "What ports
    does X32 Edit need?") montre que X32-Edit procede ainsi : il envoie sur l'adresse de broadcast, meme port,
    et attend une reponse. Je n'ai pas de source confirmant le format exact du paquet d'X32-Edit : ce qui suit
    est une reconstruction (broadcast + /xinfo), pas une capture de son trafic reel."""
    found = {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(("", 0))
        s.settimeout(0.2)
    except OSError:
        return []
    pkt = osc_encode("/xinfo")
    targets = {"255.255.255.255"}
    for ip in _local_ipv4_addresses():
        parts = ip.split(".")
        if len(parts) == 4:
            targets.add(".".join(parts[:3]) + ".255")  # broadcast dirige /24 : passe mieux certains pare-feux/VPN
    try:
        for t in targets:
            try:
                s.sendto(pkt, (t, port))
            except OSError:
                pass
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                data, (ip, _rp) = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                addr, args = osc_decode(data)
            except Exception:
                continue
            if addr == "/xinfo" and len(args) >= 4:
                found[ip] = {"ip": ip, "name": str(args[1]), "model": str(args[2]), "fw": str(args[3])}
    finally:
        s.close()
    return sorted(found.values(), key=lambda x: tuple(int(p) for p in x["ip"].split(".")))


FLOAT_PROC = None  # float lance par cette appli (un seul a la fois)


def launch_float_window():
    """Lance la fenetre flottante en tant que processus separe, SUR CETTE MACHINE.

    Depuis la 1.5.0, plus de second .exe a gerer : la fenetre flottante est integree au meme
    executable (XM32_Gain_Recall_LV1.exe --float), et ce bouton relance simplement ce meme
    executable/script avec ce drapeau interne. Sous Windows, CREATE_NO_WINDOW evite qu'une
    deuxieme fenetre de console (noire, vide) n'apparaisse a cote de la fenetre flottante.

    Important : ce lancement se fait du cote serveur, pas du cote de l'appareil qui a clique
    le bouton. Si le navigateur qui a clique est sur une tablette connectee a ce serveur via le
    reseau local, la fenetre flottante s'ouvre quand meme ICI (sur le PC qui fait tourner ce
    script), jamais sur la tablette - une tablette ne peut pas executer un .exe/.py de toute
    facon. Ce bouton n'a donc d'utilite que pour qui clique depuis le navigateur de CETTE
    machine (cas typique : PC qui heberge aussi la LV1).
    """
    global FLOAT_PROC
    if FLOAT_PROC is not None and FLOAT_PROC.poll() is None:
        return True, ""  # deja ouvert (au demarrage ou par un clic precedent) : pas de deuxieme float
    frozen = getattr(sys, "frozen", False)
    here = os.path.dirname(os.path.abspath(sys.executable if frozen else __file__))
    if frozen:
        cmd = [sys.executable, "--float", "--port", str(WEB_PORT)]
    else:
        cmd = [sys.executable, os.path.abspath(__file__), "--float", "--port", str(WEB_PORT)]
    if ALLOW_ANY_HOST and LAN_CODE:
        # Quiconque clique ce bouton est deja authentifie dans le navigateur (sinon la page de
        # connexion s'affiche avant meme de voir ce bouton) : on lui offre une session toute prete
        # plutot que de lui faire retaper le code d'acces --lan dans la fenetre flottante separee.
        tok = secrets.token_urlsafe(24)
        SESSIONS.add(tok)
        cmd += ["--session-token", tok]
    kwargs = {"cwd": here}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        FLOAT_PROC = subprocess.Popen(cmd, **kwargs)
    except OSError as e:
        return False, "Lancement impossible : %s" % e
    return True, ""


def _push_browser_back(timeout=15.0):
    """Windows : le navigateur s'ouvre au premier plan, devant la LV1. Des que sa fenetre affiche la page (titre
    = APP_NAME, apres le chargement), on la reduit : la LV1 et le float restent devant. Reduite trop tot, elle
    revient toute seule (vu avec Brave) : on surveille encore 4 s et on reduit toute fenetre de la page."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def page_windows():
            found = []

            def cb(hwnd, _):
                buf = ctypes.create_unicode_buffer(512)
                if (user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd)
                        and user32.GetWindowTextW(hwnd, buf, 512) and APP_NAME in buf.value):
                    found.append(hwnd)
                return True
            user32.EnumWindows(proc(cb), 0)
            return found

        end, seen = time.monotonic() + timeout, False
        while time.monotonic() < end:
            wins = page_windows()
            if wins and not seen:
                seen, end = True, time.monotonic() + 4.8
                time.sleep(0.8)
                wins = page_windows()
            for hwnd in wins:
                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE (n'exige pas d'etre au premier plan)
            time.sleep(0.1)
    except Exception:
        pass


def _startup_windows(url, browser, float_win):
    """Au lancement : navigateur (en arriere-plan), puis le float, qui est l'outil de tous les jours."""
    time.sleep(0.6)
    if browser:
        webbrowser.open(url)
        _push_browser_back()
    if float_win:
        ok, err = launch_float_window()
        if not ok:
            print(err)


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
        if ALLOW_ANY_HOST:  # mode --lan : Host: variable (tablette, telephone...) - securite deplacee sur le jeton
            return True
        return self.headers.get("Host", "") in ALLOWED_HOSTS  # anti DNS-rebinding

    def _session_token(self):
        for part in self.headers.get("Cookie", "").split(";"):
            part = part.strip()
            if part.startswith(LAN_COOKIE + "="):
                return part[len(LAN_COOKIE) + 1:]
        return None

    def _auth_ok(self):
        if not ALLOW_ANY_HOST or not LAN_CODE:
            # pas de --lan (deja protege par 127.0.0.1), ou --lan-sans-mdp assume explicitement
            return True
        if self.client_address[0] in ("127.0.0.1", "::1") and self.headers.get("Host", "") in ALLOWED_HOSTS:
            # le PC de l'appli lui-meme : pas de code (seuls tablettes / telephones le tapent). Host verifie :
            # une page web piegee qui viserait 127.0.0.1 par DNS-rebinding arrive avec SON nom d'hote.
            return True
        tok = self._session_token()
        return tok is not None and tok in SESSIONS

    def _reject_auth_api(self):
        self._json({"error": "session --lan manquante ou expiree, se reconnecter avec le code"}, 401)

    def _login_rate_limited(self, ip, now):
        e = LOGIN_ATTEMPTS.get(ip)
        if not e:
            return None
        if e["locked_until"] > now:
            return e["locked_until"] - now
        return None

    def _login_record_fail(self, ip, now):
        if len(LOGIN_ATTEMPTS) > LOGIN_MAX_TRACKED_IPS:
            for k, v in list(LOGIN_ATTEMPTS.items()):
                if now - v["seen"] > 3600:
                    del LOGIN_ATTEMPTS[k]
        e = LOGIN_ATTEMPTS.setdefault(ip, {"fails": 0, "locked_until": 0, "seen": now})
        e["fails"] += 1
        e["seen"] = now
        if e["fails"] >= 5:
            # verrou croissant : 30 s, 60 s, 120 s ... plafonne a 15 min - ralentit un brute-force du code 4 chiffres
            e["locked_until"] = now + min(900, 30 * (2 ** (e["fails"] - 5)))

    def _login_record_success(self, ip):
        LOGIN_ATTEMPTS.pop(ip, None)

    def _do_login(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            d = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return self._json({"error": "requete invalide"}, 400)
        ip = self.client_address[0]
        now = time.time()
        wait = self._login_rate_limited(ip, now)
        if wait is not None:
            return self._json({"error": "trop de tentatives, reessayer plus tard", "retry_after": int(wait) + 1}, 429)
        code = str(d.get("code", ""))
        if LAN_CODE and hmac.compare_digest(code, LAN_CODE):
            self._login_record_success(ip)
            tok = secrets.token_urlsafe(24)
            SESSIONS.add(tok)
            self._json({"ok": True}, 200, set_cookie="%s=%s; Path=/; Max-Age=2592000; SameSite=Strict" % (LAN_COOKIE, tok))
        else:
            self._login_record_fail(ip, now)
            self._json({"error": "code incorrect"}, 401)

    def _json(self, obj, code=200, set_cookie=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "host refuse"}, 403)
        path = self.path.split("?")[0]
        needs_login = ALLOW_ANY_HOST and LAN_CODE and not self._auth_ok()
        if path in ("/", "/index.html"):
            body = (LOGIN_HTML if needs_login else HTML).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if needs_login:
            return self._reject_auth_api()
        if path == "/api/state":
            snap = CLIENT.snapshot()
            # Affiche dans l'UI (deja protege par needs_login ci-dessus) : code, adresses, et si le
            # code peut etre change a chaud depuis cette page (seulement en --lan avec code actif).
            snap["lan_code"] = LAN_CODE
            snap["local_url"] = LOCAL_URL
            snap["lan_urls"] = LAN_URLS
            snap["code_rotatable"] = bool(ALLOW_ANY_HOST and CODE_PATH)
            self._json(snap)
        elif path == "/api/meters":
            self._json(CLIENT.meters_snapshot())
        elif path == "/api/routings":
            self._json({"profiles": ROUTINGS.summaries(), "groups": ROUTING_GROUPS, "path": ROUTINGS.path})
        elif path == "/api/presets":
            self._json({"presets": STORE.all(), "path": STORE.path})
        elif path == "/api/scenes-dir":
            d = os.path.dirname(os.path.abspath(STORE.path))
            self._json(dict(scenes_dir_info(d), default=app_data_dir(),
                            is_default=os.path.normcase(d) == os.path.normcase(os.path.abspath(app_data_dir()))))
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
        path = self.path.split("?")[0]
        if path == "/api/login":
            return self._do_login()
        if ALLOW_ANY_HOST and LAN_CODE and not self._auth_ok():
            return self._reject_auth_api()
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

    def _routing_nodes(self, d):
        pr = ROUTINGS.get(d["id"])
        if not pr:
            return None, None
        groups = [g for g in d.get("groups", ["io"]) if g in ROUTING_GROUPS]
        nodes = {}
        for g in groups:
            nodes.update(pr["nodes"].get(g, {}))
        return pr, nodes

    def _routing_route(self, p, d):
        if p == "/api/routings/import":
            name, fw, nodes = parse_scn(str(d.get("text", "")))
            if not nodes["io"]:
                return self._json({"ok": False, "error": "Aucune ligne de routing (/config/routing, /config/userrout) trouvee : est-ce bien une scene X32 (.scn) ?"})
            fname = os.path.splitext(str(d.get("filename", "")))[0]
            pr = ROUTINGS.add(name or fname or "Routing importe", fw, nodes, "import : %s" % (d.get("filename") or "?"))
            return self._json({"ok": True, "id": pr["id"], "io": len(nodes["io"]), "out": len(nodes["out"])})
        if p == "/api/routings/rename":
            return self._json({"ok": ROUTINGS.rename(d["id"], str(d["name"]).strip()[:60] or "Sans nom")})
        if p == "/api/routings/delete":
            return self._json({"ok": ROUTINGS.delete(d["id"])})
        if p == "/api/routings/undo":
            if not CLIENT.snapshot()["connected"]:
                return self._json({"ok": False, "error": "Non connecte a la console"})
            ok = CLIENT.undo_routing()
            if ok:
                # petite pause : laisse la console digerer les ecritures OSC qui viennent de partir
                # avant de relire le routing, sinon on risque de lire un etat transitoire
                threading.Thread(target=lambda: (time.sleep(0.7), CLIENT.refresh_exp_map()), daemon=True).start()
            return self._json({"ok": ok})
        pr, nodes = self._routing_nodes(d)
        if not pr or not nodes:
            return self._json({"ok": False, "error": "Profil introuvable ou aucun groupe selectionne"})
        if not CLIENT.snapshot()["connected"]:
            return self._json({"ok": False, "error": "Non connecte a la console"})
        if p == "/api/routings/preview":
            rows = CLIENT.routing_diff(nodes)
            return self._json({"ok": True, "name": pr["name"], "rows": rows,
                               "changed": sum(1 for r in rows if not r["same"]),
                               "unreadable": sum(1 for r in rows if r["current"] is None)})
        if p == "/api/routings/apply":
            result = CLIENT.apply_routing(nodes, pr["name"])
            threading.Thread(target=lambda: (time.sleep(0.7), CLIENT.refresh_exp_map()), daemon=True).start()
            return self._json({"ok": True, "result": result})
        self._json({"error": "introuvable"}, 404)

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
            if ok:
                threading.Thread(target=CLIENT.refresh_exp_map, daemon=True).start()
                if not CLIENT.demo:
                    remember_console(ip)
            return self._json({"ok": ok, "error": CLIENT.error})
        if p == "/api/demo":
            ok, err = start_sim()
            if not ok:
                return self._json({"ok": False, "error": err})
            CLIENT.connect("127.0.0.1")
            CLIENT.demo = True
            threading.Thread(target=CLIENT.refresh_exp_map, daemon=True).start()
            return self._json({"ok": True})
        if p == "/api/disconnect":
            CLIENT.disconnect()
            return self._json({"ok": True})
        if p == "/api/meters":
            CLIENT.set_meters(bool(d.get("on")))
            return self._json({"ok": True})
        if p.startswith("/api/routings/"):
            return self._routing_route(p, d)
        if p == "/api/refresh":
            threading.Thread(target=CLIENT.request_all, daemon=True).start()
            threading.Thread(target=CLIENT.refresh_exp_map, daemon=True).start()
            return self._json({"ok": True})
        if p == "/api/scan":
            return self._json({"ok": True, "found": scan_network()})
        if p == "/api/launch-float":
            ok, err = launch_float_window()
            return self._json({"ok": ok, "error": err})
        if p == "/api/lan/new-code":
            global LAN_CODE
            if not (ALLOW_ANY_HOST and CODE_PATH):
                return self._json({"ok": False, "error": "Code non actif sur ce serveur (mode --local-only ou --lan-sans-mdp) : rien a changer."})
            LAN_CODE = load_or_create_lan_config(CODE_PATH, regenerate=True)
            # Garde la session de QUI vient de faire ce changement (reste connecte sans re-taper le
            # code qu'il vient lui-meme de generer) ; deconnecte tous les autres appareils deja
            # connectes - c'est le but de l'operation (ex. fin de contrat, code vu par un tiers).
            keep = self._session_token()
            SESSIONS.clear()
            if keep:
                SESSIONS.add(keep)
            return self._json({"ok": True, "code": LAN_CODE})
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
        if p == "/api/scenes-dir":
            # browse : fenetre de choix sur le PC de l'appli ; check : etat d'un dossier sans rien changer ;
            # apply : bascule (copy = y recopier les scenes actuelles si le dossier n'en a pas)
            try:
                if d.get("browse"):
                    with BROWSE_LOCK:
                        chosen = browse_folder(d.get("initial") or os.path.dirname(os.path.abspath(STORE.path)))
                    return self._json({"ok": True, "path": chosen})
                target = app_data_dir() if d.get("reset") else str(d.get("path") or "")
                if not target.strip():
                    return self._json({"ok": False, "error": "Indiquez un dossier"})
                if d.get("check"):
                    target = os.path.abspath(os.path.expanduser(target.strip().strip('"')))
                    return self._json(dict(scenes_dir_info(target), ok=True,
                                           current_count=len(STORE.all())))
                return self._json(dict(set_scenes_dir(target, bool(d.get("copy"))), ok=True))
            except Exception as e:   # dialogue indisponible, dossier refuse, copie impossible...
                return self._json({"ok": False, "error": str(e)})
        self._json({"error": "introuvable"}, 404)


# --------------------------------------------------------------------------
#  Page de connexion --lan : code a 4 chiffres, clavier tactile, pas de copier-coller
# --------------------------------------------------------------------------
LOGIN_HTML = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>__APP_NAME__</title>
<link rel="icon" type="image/svg+xml" href="__APP_ICON__">
<style>
:root{--bg:#0b0c0d;--panel:#171819;--line:#2a2c2e;--cyan:#38d0e0;--mut:#8a9096;--danger:#e0555a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:#eee;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:28px 26px;width:100%;max-width:340px;text-align:center}
h1{font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:0 0 4px;font-weight:600}
h2{font-size:13px;color:var(--mut);margin:0 0 22px;font-weight:400}
#code{width:100%;font-size:34px;letter-spacing:.5em;text-align:center;background:#0d0e0f;border:1px solid var(--line);
  border-radius:8px;color:var(--cyan);padding:14px 0 14px 0.5em;font-family:Consolas,monospace}
#code:focus{outline:2px solid var(--cyan)}
button{width:100%;margin-top:16px;background:var(--cyan);color:#04262b;border:0;border-radius:8px;
  font-size:16px;font-weight:700;padding:14px 0;cursor:pointer}
button:disabled{opacity:.5}
#msg{min-height:20px;margin-top:12px;font-size:13px;color:var(--danger)}
</style></head>
<body>
<div class="card">
  <h1>__APP_SHORT__</h1>
  <h2 style="margin:-2px 0 18px">for eMotion LV1 &middot; by __APP_AUTHOR__</h2>
  <h2>Acces reseau local &middot; code a 4 chiffres</h2>
  <form id="f" autocomplete="off">
    <input id="code" inputmode="numeric" pattern="[0-9]*" maxlength="4" placeholder="&middot;&middot;&middot;&middot;" autofocus>
    <button id="go" type="submit">Entrer</button>
  </form>
  <div id="msg"></div>
</div>
<script>
const f=document.getElementById("f"),c=document.getElementById("code"),m=document.getElementById("msg"),go=document.getElementById("go");
c.addEventListener("input",()=>{c.value=c.value.replace(/\D/g,"").slice(0,4);});
f.addEventListener("submit",e=>{
  e.preventDefault();
  if(c.value.length!==4){m.textContent="Code a 4 chiffres.";return;}
  go.disabled=true;m.textContent="";
  fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:c.value})})
    .then(r=>r.json().then(j=>({status:r.status,j})))
    .then(({status,j})=>{
      if(status===200){location.reload();return;}
      go.disabled=false;c.value="";c.focus();
      m.textContent=status===429?("Trop de tentatives, reessayer dans "+j.retry_after+" s."):"Code incorrect.";
    })
    .catch(()=>{go.disabled=false;m.textContent="Connexion au serveur impossible.";});
});
</script></body></html>
"""


# --------------------------------------------------------------------------
#  Interface (HTML/CSS/JS embarques) - direction artistique inspiree de Waves eMotion LV1
# --------------------------------------------------------------------------
HTML = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__APP_NAME__</title>
<link rel="icon" type="image/svg+xml" href="__APP_ICON__">
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
.sel{background:var(--teal);color:#032;border-radius:6px;height:38px;padding:0 16px;border:0;font-weight:700;font-size:15px;min-width:180px;text-align:left}
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
.logo{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.06em;font-size:20px;color:#dfe5ea;text-align:right;line-height:1}
.logo svg{width:38px;height:38px;flex:none}
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
.bw{display:flex;flex:1;gap:3px;margin:3px 8px;min-height:80px}
.bar{position:relative;flex:1;background:#000;border:1px solid #222;border-radius:3px;cursor:ns-resize;touch-action:none}
.vu{position:relative;width:7px;background:#050606;border:1px solid #1f2224;border-radius:2px;overflow:hidden;opacity:.8}
.vu .lv{position:absolute;inset:0;clip-path:inset(100% 0 0 0);
  background:linear-gradient(to top,#1fa35a 0%,#1fa35a 68%,#d3ae3a 76%,#d3ae3a 90%,#e5483b 92%,#e5483b 100%)}
.vu .pk{position:absolute;left:0;right:0;height:2px;background:#e9edf0;display:none;transform:translateY(1px)}
.vu.clip{border-color:var(--warn);box-shadow:0 0 5px #ff5b4d99}
.strip.na .vu{opacity:.25}
.bar .fill{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#17c4cc,var(--teal-d));opacity:.85}
.bar .zero{position:absolute;left:0;right:0;height:1px;background:#ffffff55}
.bar .tgt{position:absolute;left:-6px;right:-6px;height:0;border-top:2px solid var(--amber);display:none;pointer-events:none}
.bar .tgt::after{content:"";position:absolute;right:-2px;top:-6px;border:5px solid transparent;border-right-color:var(--amber)}
.strip.na .bar{cursor:default;opacity:.35}
.tickl{position:absolute;left:3px;font-size:9px;color:#6d757c;pointer-events:none;transform:translateY(-50%)}
/* hauteurs FIXES sous la barre (potard, valeur, pied) : les potards de toutes les voies restent alignes,
   meme quand une voie est etroite (stereo) ou que son pied passe sur 2 lignes (2.1.0) */
.kn{display:flex;justify-content:center;align-items:center;height:60px;margin:2px 0 0;cursor:ns-resize;touch-action:none}
.kn svg{height:100%;width:auto;max-width:92%}
.strip>.ph,.strip>.kn,.strip>.val,.strip>.step,.strip>.dl,.strip>.ft{flex:none}
.val{margin:1px 8px 0;background:#000;border:1px solid #26292c;border-radius:3px;color:var(--cyan);text-align:center;
  font:700 15px "Consolas","Segoe UI",monospace;width:auto;height:26px;padding:0;outline:none;user-select:text}
.val:focus{border-color:var(--blue)}
.step{display:flex;gap:3px;margin:3px 8px 0}
.step button{flex:1;height:22px;background:#202326;border:1px solid var(--line2);border-radius:3px;font-weight:700;font-size:14px;line-height:1;padding:0}
.step button:hover{border-color:var(--blue)}
.dl{height:16px;margin:2px 4px 0;text-align:center;font-size:10.5px;color:var(--mut);white-space:nowrap;overflow:hidden}
.dl.d{color:var(--amber);font-weight:700}
.strip .ft{margin-top:4px;background:var(--teal);color:#021;display:flex;flex-wrap:wrap;justify-content:center;align-content:center;column-gap:4px;
  padding:3px 4px;font-weight:800;font-size:12px;line-height:1.2;height:36px;overflow:hidden}
.strip .ft span{white-space:nowrap}
.strip .hd.nolv1{background:#39424a;color:#c3cbd2}
/* vue LV1 : colonne = canal LV1 ; bandeau du canal en haut, 1 ou 2 preamplis dessous (stereo en demi-largeur) */
.grp{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--panel);border:1px solid #000;border-radius:3px}
.grp>.hd{font-weight:700;text-align:center;padding:5px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.gb{display:flex;flex:1;min-height:0;gap:2px}
.grp .strip{flex:1;min-width:0;border:0;border-radius:0}
.grp .strip .hd{display:none}
.grp.st .bw{margin:3px 3px}
.grp.st .val{margin:1px 2px 0;font-size:12px}
.grp.st .step{margin:3px 2px 0}
.grp.st .ph{margin:5px 2px 3px}
.grp.st .strip .ft{font-size:10px;padding:3px 1px}
.gempty{flex:1;display:flex;align-items:center;justify-content:center;text-align:center;color:#5d646b;font-size:11px;padding:4px}
.strip.na .ft{background:#39424a;color:#9aa4ac}
.pdirrow{align-items:center}
.pdir{flex:1;min-width:0;font-size:11px;color:var(--mut);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl;text-align:left}
body.locked .strip .bar,body.locked .strip .kn,body.locked .strip .step,body.locked .strip .ph,body.locked .strip .val{opacity:.4;pointer-events:none}

/* ---- colonne droite ---- */
#side{display:flex;flex-direction:column;gap:8px;padding:8px 10px 8px 4px;min-height:0;border-left:1px solid #000}
.h{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);text-align:center;margin:2px 0}
#banks{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.bank{background:#0d0e0f;border:1px solid var(--line2);border-radius:6px;padding:7px 4px;font-weight:700;font-size:13px;height:40px}
.bank.on{background:#0a2a45;border:2px solid var(--blue);color:#fff}
.bank.lv{border-color:#6b5a2e}
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
#gone{position:fixed;inset:0;background:#000c;display:flex;align-items:center;justify-content:center;z-index:30}
#modal .box,#gone .box{background:#15171a;border:1px solid var(--line2);border-radius:8px;padding:18px 20px;max-width:520px;width:calc(100% - 30px)}
#modal h3{margin:0 0 8px;font-size:16px}
#modal p{margin:6px 0;color:#c9cfd4;line-height:1.4;user-select:text}
#modal .row{margin-top:14px;justify-content:flex-end}
#modal .row .btn{flex:0 0 auto;padding:8px 16px}
#toast{position:fixed;left:14px;bottom:38px;background:#15171a;border:1px solid var(--line2);border-left:4px solid var(--blue);
  border-radius:5px;padding:9px 13px;max-width:520px;display:none;z-index:9;box-shadow:0 4px 18px #000a}
#toast.err{border-left-color:var(--warn)} #toast.ok{border-left-color:var(--ok)}
#welcome{position:absolute;left:20px;top:80px;max-width:560px;color:#aab2b8;line-height:1.55;font-size:14px;pointer-events:none}
#welcome b{color:#fff}

/* ---- onglet Routing ---- */
#rview{grid-column:1/-1;display:none;grid-template-columns:290px 1fr 330px;gap:10px;padding:10px;min-height:0;overflow:hidden}
body.v-rout #stripwrap,body.v-rout #side{display:none}
body.v-rout #rview{display:grid}
.rcol{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px;display:flex;flex-direction:column;gap:8px;min-height:0;overflow:auto}
.rgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:8px;align-content:start}
.rsec{background:#0d0e0f;border:1px solid var(--line2);border-radius:5px;padding:8px 10px}
.rsec h4{margin:0 0 6px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--mut);font-weight:600}
.rrow{display:flex;gap:10px;padding:3px 0;border-top:1px solid #1a1c1e;font-size:13px}
.rrow:first-of-type{border-top:0}
.rrow .rg{flex:0 0 66px;color:var(--cyan);font:700 13px Consolas,monospace}
.rrow.off .rs{color:#6b737a}
.rnote{margin-top:6px;color:var(--mut);font-size:11.5px;line-height:1.35}
.rmeta{color:#b9c0c6;font-size:12.5px;margin-bottom:8px}
.diflist{max-height:260px;overflow:auto;background:#0d0e0f;border:1px solid var(--line2);border-radius:5px;padding:6px 8px;font:12px Consolas,monospace;margin:8px 0;user-select:text}
.dif{margin-bottom:7px;color:#c9cfd4}.dif code{color:var(--cyan)}
#rlast{font-size:12.5px;color:#c9cfd4;line-height:1.4;min-height:34px}
@media(max-width:1500px){.logo{display:none}}
/* Tactile (tablette/telephone) : agrandit les cibles tactiles sans toucher a l'affichage souris/trackpad. */
@media (hover:none) and (pointer:coarse){
  .pill,.mini{height:46px;padding:0 16px}
  .step button{height:34px;font-size:16px}
  .strip .ph{height:36px}
  .btn{padding:11px 6px;font-size:13.5px}
  .inp{padding:11px 10px}
  #modal .row .btn{padding:12px 18px}
  .pi{padding:10px 10px}
  .bank{height:46px}
  .kn{height:70px}
}
/* Ecrans etroits (tablette en portrait, telephone) : la mise en page fixe (grille 56px/1fr/26px, colonne
   laterale de 310px cote a cote avec les voies) deborde sur un ecran de moins de ~980px de large - avant
   la 1.7.0, rien ne gerait ce cas, l'appli etait pensee pour un PC/tablette en paysage. Ici on empile la
   colonne laterale (scenes/banques) SOUS les voies au lieu d'a cote, et on laisse la barre du haut passer
   a la ligne. Les 16 voies elles-memes restent cote a cote (min-width:1180px sur #strips, voir plus haut)
   avec defilement horizontal : les reduire en-dessous d'une largeur lisible au doigt n'aurait pas de sens
   sur une console de mixage, le defilement horizontal est le compromis assume ici.*/
@media(max-width:980px){
  #app{grid-template-rows:auto 1fr auto}
  #top{flex-wrap:wrap;height:auto;row-gap:6px}
  .spacer{flex:1 1 100%;height:0}
  #main{grid-template-columns:1fr;grid-auto-rows:minmax(0,auto);overflow-y:auto}
  #stripwrap{min-height:280px;flex:0 0 auto}
  #side{border-left:0;border-top:1px solid #000;max-height:52vh}
  #rview{grid-template-columns:1fr;grid-auto-rows:auto;overflow-y:auto}
  .rcol{max-height:none}
  .screen input{width:100px}
}
@media(max-width:560px){
  .sel{min-width:0;flex:1 1 auto}
  .screen input{width:80px}
  #welcome{left:10px;right:10px;max-width:none}
}
</style></head>
<body>
<div id="app">
  <div id="top">
    <div class="sel" style="display:flex;align-items:center"><span id="selg">Gains &middot; <span id="bankname">Local 1-16</span></span><span id="selr" style="display:none">Routing</span></div>
    <button class="pill on" id="tgains">Gains</button><button class="pill" id="trout">Routing</button>
    <div class="screen"><span class="led" id="led"></span><input id="ip" placeholder="IP de la X32" spellcheck="false"></div>
    <button class="pill on" id="bconn">Connecter</button>
    <button class="pill" id="bdemo" title="Simulateur de X32 en local pour essayer l'appli sans console">D&eacute;mo</button>
    <button class="mini" id="bscan" title="Chercher les X32/M32 sur le r&eacute;seau local (diffusion /xinfo)">&#128269; Scanner</button>
    <button class="mini" id="bref" title="Relire tous les gains depuis la console">&#8635; Relire</button>
    <button class="mini" id="bfloat" title="Ouvre la fenêtre flottante compagnon sur CETTE machine (pas sur la tablette, si vous consultez cette page depuis une tablette)">&#128433; Float</button>
    <button class="mini act" id="bvu" title="Vumètre d'entrée discret sur chaque voie">&#9646; Vumètre</button>
    <button class="mini lock" id="block" title="Verrouille l'&eacute;dition (comme le cadenas du LV1)">&#128274; Verrou</button>
    <div class="spacer"></div>
    <button id="lancode" class="mini" style="display:none" title="Version, adresses et code d'accès"></button>
    <div class="logo">__APP_LOGO__<div>X/M32 GAIN RECALL<small>FOR EMOTION LV1 &middot; v__APP_VERSION__</small></div></div>
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
        <div class="row pdirrow"><span id="pdir" class="pdir"></span><button class="btn" id="pdirb" style="flex:0 0 88px">Dossier&hellip;</button></div>
      </div>
    </div>
    <div id="rview">
      <div class="rcol">
        <div class="h">Profils de routing</div>
        <div id="rlist" style="display:flex;flex-direction:column;gap:4px"></div>
        <button class="btn" id="rimp">Importer une scène .scn…</button>
        <input type="file" id="rfile" accept=".scn,.txt" style="display:none">
        <div class="row"><button class="btn" id="rren" disabled>Renommer</button><button class="btn dng" id="rdel" disabled>Suppr.</button></div>
        <div class="rnote">Seules les lignes de routing sont lues dans la scène (mixage, EQ, faders… ne sont jamais envoyés).</div>
      </div>
      <div class="rcol" id="rdetail"></div>
      <div class="rcol">
        <div class="h">Charger sur la console</div>
        <label class="opt"><input type="checkbox" id="rio" checked disabled> Routing E/S : blocs + patchs utilisateur</label>
        <label class="opt warn"><input type="checkbox" id="rout"> Patch de sortie console (/outputs)</label>
        <button class="btn go" id="rload" disabled>Charger ce routing</button>
        <button class="btn" id="rundo" disabled>&#8630; Annuler le dernier routing</button>
        <div id="rlast"></div>
        <div class="rnote">Avant l'envoi, l'appli lit le routing actuel et vous montre les lignes qui changent. Après l'envoi, elle relit la console pour confirmer. Les réglages du S16 (encodeur des sorties) ne font pas partie d'une scène : à régler sur le boîtier.</div>
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
// Vue LV1 (depuis la 2.1.0) : une colonne par canal LV1 (couches « Ch 1-16 »... de la LV1)
const LV1_BANKS=[["LV1 Ch 1-16",1],["LV1 Ch 17-32",17],["LV1 Ch 33-48",33],["LV1 Ch 49-64",49],["LV1 Ch 65-80",65]];
let gview="lv1", lv1bank=0;
let bank=0, presets=[], selId=null, locked=false, L={};   // L: valeurs locales recentes (evite le clignotement)
let presetPath="";

function label(i){return i<32?String(i+1):(i<80?"A"+(i-31):"B"+(i-79));}
/* Numero EXP (menu de patch LV1) : LU EN DIRECT sur la console (CLIENT.refresh_exp_map cote Python,
   via /config/routing/CARD + /config/userrout/in), jamais suppose. Vide si non connecte, si la
   lecture a echoue, ou si ce canal n'est pas patche vers la carte en ce moment - jamais un numero
   invente. Se met a jour apres connexion, "Relire", ou l'envoi d'un routing. */
function expLabel(i){const v=(S.exp_map||{})[i];return v?("EXP "+v):"";}
/* Repere avec la source, comme dans le float : "L 15" (Local), "A 1" / "B 3" (AES50-A/B). */
function tag(i){return i<32?"L "+(i+1):(i<80?"A "+(i-31):"B "+(i-79));}
function footLabel(i){const e=expLabel(i);return e?tag(i)+" = "+e:tag(i);}
/* meme texte, en deux morceaux insecables : passe sur 2 lignes (« L 15 » / « = EXP 15 ») si la voie
   est trop etroite, au lieu de couper le numero EXP */
function footHTML(i){const e=expLabel(i);return "<span>"+tag(i)+"</span>"+(e?"<span>= "+e+"</span>":"");}
/* Canal LV1 qui recoit ce preampli (table EXP -> canal, lv1/patchmap.py) et sa couleur / son nom lus
   via Companion par le serveur (lv1/companion.py). null si la voie n'arrive sur aucun canal LV1 :
   jamais de canal devine. */
function lv1Of(i){const e=(S.exp_map||{})[i];if(!e)return null;const ch=(S.lv1_map||{})[e];if(!ch)return null;
  const inf=(S.lv1_channels||{})[ch]||{};return {ch,color:inf.color||null,label:inf.label||("In "+ch)};}
function inkFor(hex){const n=parseInt(hex.slice(1),16),r=n>>16&255,g=n>>8&255,b=n&255;
  return (0.299*r+0.587*g+0.114*b)>150?"#05080a":"#ffffff";}
function fmt(v){return (v>0?"+":"")+v.toFixed(1);}
function clamp(v){return Math.max(GMIN,Math.min(GMAX,Math.round(v*2)/2));}
function api(p,body){
  const o=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)};
  return fetch(p,o).then(r=>{
    if(r.status===401){location.reload();return new Promise(()=>{});} // session --lan expiree -> retour a l'ecran de code
    return r.json();
  });
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
function makeStrip(i){
  const el=document.createElement("div");el.className="strip na";el.dataset.i=i;
  el.innerHTML=`<div class="hd"></div><button class="ph" title="Alimentation fantôme +48 V">48V</button>
    <div class="bw"><div class="bar"><div class="fill"></div><div class="zero"></div><div class="tgt"></div></div>
    <div class="vu" title="Niveau d'entrée après préampli (dBFS) · vert jusqu'à −18, ambre jusqu'à −6, rouge au-delà"><i class="lv"></i><b class="pk"></b></div></div>
    <div class="kn">${knobSVG()}</div><input class="val" value="—" spellcheck="false">
    <div class="step"><button data-d="-0.5">&minus;</button><button data-d="0.5">+</button></div>
    <div class="dl"></div><div class="ft">${footHTML(i)}</div>`;
  wire(el,i);return el;
}
/* Vue LV1 (2.1.0) : une colonne par canal LV1 de la banque, alignee sur les tranches de la LV1. Un canal
   stereo regroupe ses deux preamplis (gains NON lies sur la X32 : regroupes seulement a l'ecran). Preampli
   retrouve par son numero EXP lu en direct sur la X32 ; canal sans preampli X32 = colonne vide. */
function lv1Layout(){
  const e2i={};Object.entries(S.exp_map||{}).forEach(([i,e])=>{if(e)e2i[e]=+i;});
  const src=S.lv1_sources||{},start=LV1_BANKS[lv1bank][1],out=[];
  for(let ch=start;ch<start+16;ch++){const exps=src[ch]||[];out.push([ch,exps.filter(e=>e in e2i).map(e=>e2i[e]),exps]);}
  return out;
}
let layoutKey="";
function buildStrips(){
  const box=$("#strips");box.innerHTML="";
  if(gview==="lv1"){
    const lay=lv1Layout();layoutKey=JSON.stringify(lay);
    lay.forEach(([ch,idxs])=>{
      const g=document.createElement("div");g.className="grp"+(idxs.length>1?" st":"");g.dataset.ch=ch;
      g.innerHTML=`<div class="hd"></div><div class="gb"></div>`;const gb=g.querySelector(".gb");
      if(idxs.length)idxs.forEach(i=>gb.appendChild(makeStrip(i)));
      else gb.innerHTML=`<div class="gempty">Aucun préampli X32</div>`;
      box.appendChild(g);
    });
    // colonne stereo plus large (2 preamplis lisibles) : le navigateur n'est pas pose sur la LV1, pas
    // besoin d'y garder des colonnes de largeur egale comme dans le float
    const cols=lay.map(([,idxs])=>idxs.length>1?[124,1.7]:[70,1]);
    box.style.gridTemplateColumns=cols.map(([m,f])=>`minmax(${m}px,${f}fr)`).join(" ");
    box.style.minWidth=(cols.reduce((a,[m])=>a+m,0)+3*15)+"px";
    $("#bankname").textContent=LV1_BANKS[lv1bank][0];
  }else{
    layoutKey="";box.style.gridTemplateColumns="";box.style.minWidth="";
    for(let k=0;k<16;k++)box.appendChild(makeStrip(BANKS[bank][1]+k));
    $("#bankname").textContent=BANKS[bank][0];
  }
  document.querySelectorAll(".bank").forEach(b=>b.classList.toggle("on",b.dataset.v===gview&&+b.dataset.n===(gview==="lv1"?lv1bank:bank)));
  try{localStorage.setItem("x32view",JSON.stringify({view:gview,bank,lv1bank}));}catch(_){}
  update();
}
function updateGroups(){
  document.querySelectorAll(".grp").forEach(g=>{
    const ch=+g.dataset.ch,inf=(S.lv1_channels||{})[ch]||{},hd=g.querySelector(".hd"),lb=inf.label||("In "+ch);
    const exps=(S.lv1_sources||{})[ch]||[];
    hd.textContent=lb;hd.title=lb+" — canal LV1 In "+ch+(exps.length?" · EXP "+exps.join("/"):" · aucune entrée X32");
    hd.style.background=inf.color||"#39424a";hd.style.color=inf.color?inkFor(inf.color):"#e9edf0";
  });
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
/* un meme preampli peut apparaitre dans deux colonnes en vue LV1 (EXP qui alimente deux canaux LV1) */
function updateStrip(i){document.querySelectorAll(`.strip[data-i="${i}"]`).forEach(el=>updateStripEl(el,i));}
function updateStripEl(el,i){
  const v=cur(i),known=v!==null;
  el.classList.toggle("na",!known);
  const nm=S.names[i]||(i<32?"Ch "+(i+1):(i<80?"AES50-A "+(i-31):"AES50-B "+(i-79)));
  // Bandeau du haut : nom + couleur du canal LV1 qui recoit ce preampli (comme les etiquettes de nom de
  // la LV1) ; sinon, comme avant, le nom X32 sur fond teal.
  const hd=el.querySelector(".hd"),lv=lv1Of(i);
  if(lv){hd.textContent=lv.label;hd.title=lv.label+" — canal LV1 In "+lv.ch+" · X32 : "+nm;
    hd.style.background=lv.color||"#39424a";hd.style.color=lv.color?inkFor(lv.color):"#e9edf0";}
  else{hd.textContent=nm;hd.style.background="";hd.style.color="";
    // LV1 suivie mais cette voie n'arrive sur aucun de ses canaux : bandeau gris (le teal se confondrait
    // avec la couleur par defaut des canaux LV1)
    const unassigned=Object.keys(S.lv1_map||{}).length>0;hd.classList.toggle("nolv1",unassigned);
    hd.title=unassigned?nm+" — n'arrive sur aucun canal LV1":nm;}
  if(lv)hd.classList.remove("nolv1");
  const val=el.querySelector(".val");if(document.activeElement!==val)val.value=known?fmt(v):"—";
  const p=known?(v-GMIN)/(GMAX-GMIN):0;
  el.querySelector(".fill").style.height=(p*100)+"%";
  el.querySelector(".zero").style.bottom=((0-GMIN)/(GMAX-GMIN)*100)+"%";
  const a=-135+270*p;el.querySelector(".kval").setAttribute("d",known&&a>-134?arc(32,32,27,-135,a):"");
  const pt=pol(32,32,20,a);el.querySelector(".kptr").setAttribute("x2",pt[0]);el.querySelector(".kptr").setAttribute("y2",pt[1]);
  const ph=el.querySelector(".ph");ph.classList.toggle("on",S.phantom[i]===1);ph.disabled=S.phantom[i]==null;
  const ft=el.querySelector(".ft"),fh=footHTML(i);if(ft.innerHTML!==fh)ft.innerHTML=fh;ft.title=footLabel(i);
  // apercu de la scene selectionnee : repere ambre + delta
  const tg=el.querySelector(".tgt"),dl=el.querySelector(".dl");
  const pr=presets.find(x=>x.id===selId);const t=pr&&pr.gains[String(i)];
  if(pr&&t!==undefined&&known){const tp=(t-GMIN)/(GMAX-GMIN);tg.style.display="block";tg.style.bottom=(tp*100)+"%";
    const d=t-v;if(Math.abs(d)<0.01){dl.className="dl";dl.textContent="= scène";}
    else{dl.className="dl d";dl.textContent="→ "+fmt(t)+" ("+(d>0?"+":"")+d.toFixed(1)+")";}}
  else{tg.style.display="none";dl.className="dl";dl.textContent="";}
}
function update(){
  document.querySelectorAll(".strip").forEach(el=>updateStripEl(el,+el.dataset.i));
  updateGroups();
  // etat de connexion
  const led=$("#led");led.className="led"+(S.connected?" ok":(S.trying?" try":""));
  $("#bconn").textContent=(S.connected||S.trying)?"Déconnecter":"Connecter";
  $("#bconn").className="pill"+((S.connected||S.trying)?"":" on");
  ["#bref"].forEach(s=>$(s).disabled=!S.connected);
  $("#bvu").classList.toggle("act",!!S.meters_on);
  const w=$("#welcome");
  if(S.connected){w.style.display="none";}
  else{w.style.display="block";w.innerHTML=S.trying?"<b>Connexion en cours…</b><br>En attente d'une réponse de la console sur "+esc(S.ip)+" (UDP 10023). Si rien n'arrive : vérifiez l'IP (X32 : Setup → Network), que le PC est sur le même réseau/sous-réseau, et le pare-feu Windows."
    :"<b>1.</b> Sur la X32 : <b>Setup → Network</b> pour lire son adresse IP.<br><b>2.</b> Entrez-la en haut puis <b>Connecter</b>.<br><b>3.</b> Réglez les gains, sauvez une scène, rappelez-la plus tard.<br><br>Pas de console sous la main ? Le bouton <b>Démo</b> lance une X32 simulée.";}
  renderStatus();renderPresetButtons();routingButtons();
  const lc=$("#lancode");lc.style.display="";
  lc.innerHTML=S.lan_code?("&#128273; Code : <b>"+esc(S.lan_code)+"</b>"):
    ((S.lan_urls&&S.lan_urls.length)?"&#127760; Accès réseau":"&#127760; Accès");
}
function openNetInfo(){
  const urls=(S.lan_urls||[]).map(u=>`<div class="pi" style="cursor:default"><b>${esc(u)}</b></div>`).join("")
    || '<div style="color:var(--mut)">Aucune adresse réseau locale détectée (accès limité à cet ordinateur ; relancer avec --lan si ce n\'est pas voulu).</div>';
  const code=S.lan_code?`<p style="margin-top:10px">Code d'accès tablette/téléphone : <b style="font-size:22px;letter-spacing:2px">${esc(S.lan_code)}</b></p>`:"";
  const btns=[{t:"Fermer"}];
  if(S.code_rotatable)btns.unshift({t:"Nouveau code…",f:confirmNewCode});
  modal("Accès réseau",
    `<p><b>__APP_NAME__</b> v__APP_VERSION__<br>by __APP_AUTHOR__</p><p>Adresse locale (cet ordinateur) : <b>${esc(S.local_url||"—")}</b></p>${urls}${code}`,
    btns);
}
function confirmNewCode(){
  modal("Générer un nouveau code ?",
    "<p>Tous les appareils déjà connectés avec l'ancien code (sauf cette page) devront retaper le nouveau pour continuer. À utiliser si le code actuel a pu être vu par quelqu'un qui ne doit plus avoir accès (ex. fin de contrat).</p>",
    [{t:"Annuler"},{t:"Générer le nouveau code",go:1,f:()=>{
      api("/api/lan/new-code",{}).then(r=>{
        if(r.ok)modal("Nouveau code généré",`<p>Code d'accès : <b style="font-size:26px;letter-spacing:2px">${esc(r.code)}</b></p><p style="color:var(--mut)">À communiquer aux appareils qui doivent s'y reconnecter.</p>`,[{t:"OK"}]);
        else toast(r.error,"err");
      });
    }}]);
}
function renderStatus(){
  const i=S.info||{};const c=S.connected?`<b class="good">● Connecté</b> ${esc(i.model||"X32")} ${esc(i.name||"")} ${i.fw?"· fw "+esc(i.fw):""} · ${S.known}/128 gains lus`+(S.demo?' · <b style="color:var(--amber)">SIMULATEUR</b>':""):
    (S.trying?'<b style="color:var(--amber)">● Connexion…</b>':"○ Non connecté");
  let r="";const lr=S.last_recall;
  if(lr){r=` · Dernier rappel « ${esc(lr.name)} » : ${lr.sent_gain} gains`+(lr.sent_phantom?`, ${lr.sent_phantom} 48V`:"")+" envoyés — "+
    (lr.verified===null?"vérification…":(lr.verified?'<b class="good">confirmé par relecture ✓</b>':`<b class="bad">${lr.bad.length} écart(s) à la relecture : ${lr.bad.slice(0,8).map(label).join(", ")}</b>`));}
  $("#status").innerHTML=c+r+routingMsg()+(vuDead?' · <b class="bad">vumètre : aucune donnée reçue</b>':"")+(S.error?` · <b class="bad">${esc(S.error)}</b>`:"")+'<span class="spacer"></span><span>Shift = pas fin/gros · molette = ±0,5 dB</span><span>v__APP_VERSION__ · by __APP_AUTHOR__</span>';
}

/* ---------- scenes ---------- */
function loadPresets(){renderDir();return api("/api/presets").then(r=>{presets=r.presets;presetPath=r.path;if(!presets.find(p=>p.id===selId))selId=null;renderPresets();update();});}
/* ---------- dossier des scenes (depuis la 2.0.0) : defaut %APPDATA%\X32 Gain Recall, ou au choix ---------- */
let sdir=null;
function renderDir(){return api("/api/scenes-dir").then(r=>{sdir=r;const e=$("#pdir");
  e.textContent=(r.is_default?"Dossier par défaut : ":"Dossier : ")+r.path;e.title=r.path;});}
function openDirDialog(val){
  const cur=sdir?sdir.path:"";
  modal("Dossier des scènes",
    `<p>Les scènes et profils de routing sont enregistrés dans :</p><p><b style="word-break:break-all">${esc(cur)}</b>${sdir&&sdir.is_default?" (par défaut)":""}</p>
     <p style="margin-top:10px">Nouveau dossier :</p><input class="inp" id="dirin" style="width:100%" value="${esc(val===undefined?cur:val)}" spellcheck="false">
     <p style="color:var(--mut);font-size:12px;margin-top:6px">« Parcourir » ouvre la fenêtre de choix sur le PC qui fait tourner l'appli (pas sur une tablette).</p>`,
    [{t:"Annuler"},{t:"Parcourir…",f:browseDir},{t:"Dossier par défaut",f:()=>chooseDir(sdir?sdir.default:"")},
     {t:"Utiliser ce dossier",go:1,f:()=>chooseDir($("#dirin").value)}]);
}
function browseDir(){
  const v=$("#dirin")?$("#dirin").value:"";toast("Fenêtre de choix ouverte sur le PC de l'appli…","ok");
  api("/api/scenes-dir",{browse:true,initial:v}).then(r=>{
    if(!r.ok){toast(r.error,"err");return openDirDialog(v);}openDirDialog(r.path||v);});
}
function chooseDir(path){
  path=(path||"").trim();if(!path)return toast("Indiquez un dossier","err");
  api("/api/scenes-dir",{path,check:true}).then(r=>{
    if(!r.ok)return toast(r.error,"err");
    if(!r.exists)return toast("Dossier introuvable : "+path,"err");
    if(!r.writable)return toast("Impossible d'écrire dans ce dossier","err");
    if(r.count<0)return toast("Le fichier de scènes de ce dossier est illisible","err");
    const apply=copy=>api("/api/scenes-dir",{path:r.path,copy}).then(a=>{
      if(!a.ok)return toast(a.error,"err");toast("Scènes : "+a.path,"ok");selId=null;loadPresets();loadRoutings();});
    if(r.has_file)modal("Utiliser ce dossier ?",`<p><b style="word-break:break-all">${esc(r.path)}</b> contient déjà <b>${r.count}</b> scène(s) : elles remplaceront dans l'appli les ${r.current_count} scène(s) actuelles (qui restent dans l'ancien dossier).</p>`,
      [{t:"Annuler"},{t:"Utiliser ces scènes",go:1,f:()=>apply(false)}]);
    else modal("Nouveau dossier de scènes",`<p><b style="word-break:break-all">${esc(r.path)}</b> ne contient pas encore de scènes.</p><p>Y copier vos ${r.current_count} scène(s) actuelles (et profils de routing) ?</p>`,
      [{t:"Annuler"},{t:"Partir de zéro",f:()=>apply(false)},{t:"Copier mes scènes",go:1,f:()=>apply(true)}]);
  });
}
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
function scopeIdx(){return $("#pscope").value==="bank"?[...new Set([...document.querySelectorAll(".strip")].map(el=>+el.dataset.i))]:null;}
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
$("#pdirb").onclick=()=>{renderDir().then(()=>openDirDialog());};
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
$("#bscan").onclick=()=>{
  const b=$("#bscan");b.disabled=true;b.textContent="Recherche…";
  api("/api/scan",{}).then(r=>{
    b.disabled=false;b.innerHTML="&#128269; Scanner";
    const list=r.found||[];
    if(!list.length)return modal("Aucune console trouvée",
      "<p>Rien n'a répondu au scan réseau. Causes possibles : la X32 est sur un autre sous-réseau/VLAN, "+
      "un pare-feu bloque le broadcast UDP, ou le Wi-Fi/switch filtre le broadcast entre appareils. "+
      "Entrez l'IP manuellement (Setup → Network sur la console).</p>",[{t:"OK",go:1}]);
    const rows=list.map(c=>`<div class="pi" data-ip="${esc(c.ip)}" style="cursor:pointer"><b>${esc(c.name||"?")} — ${esc(c.ip)}</b><span>${esc(c.model||"?")} · fw ${esc(c.fw||"?")}</span></div>`).join("");
    modal("Console(s) trouvée(s)",`<div style="display:flex;flex-direction:column;gap:6px">${rows}</div>`,[{t:"Annuler"}]);
    document.querySelectorAll("#modal .pi").forEach(el=>el.onclick=()=>{$("#ip").value=el.dataset.ip;$("#modal").style.display="none";});
  }).catch(()=>{b.disabled=false;b.innerHTML="&#128269; Scanner";});
};
$("#bref").onclick=()=>{api("/api/refresh",{});toast("Relecture des gains…");};
$("#lancode").onclick=openNetInfo;
$("#bfloat").onclick=()=>{
  const b=$("#bfloat");b.disabled=true;
  api("/api/launch-float",{}).then(r=>{
    b.disabled=false;
    if(r.ok)toast("Fenêtre flottante lancée sur cette machine","ok");
    else modal("Lancement impossible",`<p>${esc(r.error||"Erreur inconnue")}</p><p style="color:var(--mut)">Rappel : ce bouton ouvre la fenêtre flottante sur la machine qui fait tourner ce serveur — pas sur l'appareil où cette page est affichée. Si vous consultez cette page depuis une tablette, la fenêtre s'ouvre (ou tente de s'ouvrir) sur le PC, pas sur la tablette.</p>`,[{t:"OK",go:1}]);
  }).catch(()=>{b.disabled=false;toast("Erreur réseau","err");});
};
$("#bvu").onclick=()=>api("/api/meters",{on:!S.meters_on});
$("#block").onclick=()=>{locked=!locked;document.body.classList.toggle("locked",locked);$("#block").classList.toggle("act",locked);
  $("#block").innerHTML=locked?"&#128274; Verrouillé":"&#128274; Verrou";update();};

/* ---------- onglet Routing ---------- */
let RP=[],rsel=null,view="gains";
function setView(v){
  view=v;document.body.classList.toggle("v-rout",v==="routing");
  $("#tgains").classList.toggle("on",v==="gains");$("#trout").classList.toggle("on",v==="routing");
  $("#selg").style.display=v==="gains"?"":"none";$("#selr").style.display=v==="routing"?"":"none";
  if(v==="routing")loadRoutings();
}
function loadRoutings(){return api("/api/routings").then(r=>{RP=r.profiles;if(!RP.find(p=>p.id===rsel))rsel=RP.length?RP[0].id:null;renderRouting();});}
function rrows(list){return (list||[]).map(r=>`<div class="rrow${r.src==="OFF"?" off":""}"><span class="rg">${r.a===r.b?r.a:r.a+"\u2013"+r.b}</span><span class="rs">${esc(r.src)}</span></div>`).join("")||'<div style="color:var(--mut)">\u2014</div>';}
function detailHTML(p){
  const d=p.desc,P=d.ports||{};
  const sec=(t,l,n)=>`<div class="rsec"><h4>${t}</h4>${rrows(l)}${n?`<div class="rnote">${n}</div>`:""}</div>`;
  return `<div class="h" style="text-align:left">${esc(p.name)}</div><div class="rmeta">Mode de routage : <b>${esc(d.mode||"?")}</b> · scène fw ${esc(p.fw||"?")} · ${p.counts.io} lignes E/S · ${p.counts.out} lignes de patch de sortie</div><div class="rgrid">`+
    sec("Entrées utilisateur (User In 1–32)",d.userin,"Ce que la X32 utilise comme entrées 1–32 (Local = XLR de la X32, AES50-A = S16).")+
    sec("Départs vers la carte (→ LV1)",P.CARD,"Ce que la carte envoie à la LV1, canal par canal.")+
    sec("Sorties XLR locales (OUT 1–16)",P.OUT,"La X32 Rack n'a que 8 XLR de sortie : seules les 8 premières sont physiques.")+
    sec("Sorties AES50-A (→ S16)",P.AES50A,"Le S16 choisit ses 8 sorties avec son encodeur (blocs 1–8, 9–16…).")+
    sec("Voies internes de la X32 (IN)",P.IN,"Voies 1–32 puis Aux 1–6 de la X32.")+
    sec("Sorties utilisateur (User Out 1–48)",d.userout,"« Carte In » = retours venant de la carte.")+
    (P.AES50B?sec("Sorties AES50-B",P.AES50B,"Non utilisé si rien n'est branché sur AES50-B."):"")+`</div>`;
}
function renderRouting(){
  const l=$("#rlist");l.innerHTML="";
  RP.forEach(p=>{const d=document.createElement("div");d.className="pi"+(p.id===rsel?" on":"");
    d.innerHTML=`<b>${esc(p.name)}</b><span>${p.counts.io} lignes E/S · ${p.counts.out} sorties · ${esc(p.source)}</span>`;
    d.onclick=()=>{rsel=p.id;renderRouting();};l.appendChild(d);});
  const p=RP.find(x=>x.id===rsel);
  $("#rdetail").innerHTML=p?detailHTML(p):'<div style="color:var(--mut);padding:12px">Aucun profil. Importez une scène X32 (.scn).</div>';
  routingButtons();
}
function routingMsg(){
  const rl=S.routing_last;if(!rl)return"";
  return ` · Routing « ${esc(rl.name)} » : ${rl.sent}/${rl.total} lignes envoyées — `+(rl.verified===null?"vérification…":(rl.verified?'<b class="good">confirmé par relecture ✓</b>':`<b class="bad">${rl.bad.length} écart(s) : ${rl.bad.map(esc).join(", ")}</b>`));
}
function routingButtons(){
  const has=!!RP.find(x=>x.id===rsel);
  $("#rren").disabled=!has;$("#rdel").disabled=!has;
  $("#rload").disabled=!(has&&S.connected&&!locked);$("#rundo").disabled=!(S.routing_can_undo&&S.connected&&!locked);
  const rl=S.routing_last;
  $("#rlast").innerHTML=rl?routingMsg().replace(/^ · /,""):"";
}
$("#tgains").onclick=()=>setView("gains");$("#trout").onclick=()=>setView("routing");
$("#rimp").onclick=()=>$("#rfile").click();
$("#rfile").onchange=e=>{const f=e.target.files[0];if(!f)return;const rd=new FileReader();
  rd.onload=()=>api("/api/routings/import",{text:String(rd.result),filename:f.name}).then(r=>{
    if(!r.ok)return toast(r.error,"err");rsel=r.id;toast("Routing importé : "+r.io+" lignes E/S, "+r.out+" lignes de sortie","ok");loadRoutings();});
  rd.readAsText(f);e.target.value="";};
$("#rren").onclick=()=>{const p=RP.find(x=>x.id===rsel);if(!p)return;
  modal("Renommer","<input class='inp' id='rn2' value='"+esc(p.name)+"' maxlength='60'>",
   [{t:"Annuler"},{t:"OK",go:1,f:()=>api("/api/routings/rename",{id:p.id,name:$("#rn2").value}).then(loadRoutings)}]);
  setTimeout(()=>{const e=$("#rn2");if(e){e.focus();e.select();}},30);};
$("#rdel").onclick=()=>{const p=RP.find(x=>x.id===rsel);if(!p)return;
  modal("Supprimer ?","<p>Supprimer le profil <b>"+esc(p.name)+"</b> ?</p>",
   [{t:"Annuler"},{t:"Supprimer",go:1,f:()=>api("/api/routings/delete",{id:p.id}).then(()=>{rsel=null;loadRoutings();})}]);};
$("#rload").onclick=async()=>{
  const p=RP.find(x=>x.id===rsel);if(!p||locked)return;
  const groups=["io"].concat($("#rout").checked?["out"]:[]);
  toast("Lecture du routing actuel de la console…");
  const r=await api("/api/routings/preview",{id:p.id,groups});
  if(!r.ok)return toast(r.error,"err");
  if(r.changed===0)return toast("Rien à changer : la console a déjà ce routing.","ok");
  const sh=x=>x===null?"<i>non lu</i>":esc(x.length>48?x.slice(0,48)+"…":x);
  const list=r.rows.filter(x=>!x.same).map(x=>`<div class="dif"><code>${esc(x.path)}</code><br>${sh(x.current)} <b>→</b> ${sh(x.target)}</div>`).join("");
  modal("Charger « "+p.name+" » ?",`<p><b>${r.changed}</b> ligne(s) sur ${r.rows.length} vont changer.`+(r.unreadable?` <span class="bad">${r.unreadable} non lue(s) : pas d'annulation possible pour celles-ci.</span>`:"")+`</p><div class="diflist">${list}</div>
    <p style="color:var(--amber)">À faire de préférence hors signal : un changement de routing peut couper ou perturber l'audio en cours. « Annuler le dernier routing » remet les valeurs lues à l'instant.</p>`,
   [{t:"Annuler"},{t:"Charger le routing",go:1,f:()=>api("/api/routings/apply",{id:p.id,groups}).then(x=>toast(x.ok?"Routing envoyé — vérification en cours…":x.error,x.ok?"ok":"err"))}]);
};
$("#rundo").onclick=()=>locked?toast("Verrouillé","err"):api("/api/routings/undo",{}).then(r=>toast(r.ok?"Routing précédent restauré":(r.error||"Rien à annuler"),r.ok?"ok":"err"));

/* ---------- vumetre (poll leger ~16 Hz, attaque instantanee, retombee 24 dB/s, crete 1,2 s) ---------- */
const VU={};let vuDead=false,lastLive=performance.now();
function drawMeters(m){
  const now=performance.now(),pc=x=>Math.max(0,Math.min(1,(x+60)/60))*100;
  document.querySelectorAll(".strip").forEach(el=>{
    const i=+el.dataset.i,lv=el.querySelector(".lv"),pk=el.querySelector(".pk"),vu=el.querySelector(".vu");
    const v=(m&&m.live)?m.v[i]:null;
    if(v===null||v===undefined){lv.style.clipPath="inset(100% 0 0 0)";pk.style.display="none";vu.classList.remove("clip");delete VU[i];return;}
    const st=VU[i]||(VU[i]={lvl:v,pk:v,pt:now,t:now});
    const dt=Math.min(0.5,(now-st.t)/1000);st.t=now;
    st.lvl=v>=st.lvl?v:Math.max(v,st.lvl-24*dt);
    if(v>=st.pk){st.pk=v;st.pt=now;}else if(now-st.pt>1200){st.pk=Math.max(v,st.pk-30*dt);}
    lv.style.clipPath="inset("+(100-pc(st.lvl))+"% 0 0 0)";
    pk.style.display="block";pk.style.bottom=pc(st.pk)+"%";
    vu.classList.toggle("clip",st.pk>-1);
  });
}
async function meterLoop(){
  const active=S.connected&&S.meters_on;let m=null;
  if(active){try{m=await api("/api/meters");}catch(_){}}
  const now=performance.now();
  if(!active||(m&&m.live))lastLive=now;
  const dead=active&&now-lastLive>4000;if(dead!==vuDead){vuDead=dead;renderStatus();}
  drawMeters(m);
  setTimeout(meterLoop,active?60:300);
}

/* ---------- init ---------- */
(function(){
  const b=$("#banks");
  const addBank=(v,x,n)=>{const e=document.createElement("button");e.className="bank"+(v==="lv1"?" lv":"");
    e.textContent=x[0].replace("AES50-","");e.dataset.v=v;e.dataset.n=n;
    e.title=v==="lv1"?x[0]+" : une colonne par canal LV1, paires stéréo regroupées":x[0]+" : une colonne par préampli X32";
    e.onclick=()=>{gview=v;if(v==="lv1")lv1bank=n;else bank=n;buildStrips();};b.appendChild(e);};
  LV1_BANKS.forEach((x,n)=>addBank("lv1",x,n));
  if(LV1_BANKS.length%2)b.appendChild(document.createElement("span"));
  BANKS.forEach((x,n)=>addBank("x32",x,n));
  try{const ip=localStorage.getItem("x32ip");if(ip)$("#ip").value=ip;}catch(_){}
  try{const sv=JSON.parse(localStorage.getItem("x32view")||"null");
    if(sv){gview=sv.view==="x32"?"x32":"lv1";bank=Math.min(BANKS.length-1,Math.max(0,sv.bank|0));
      lv1bank=Math.min(LV1_BANKS.length-1,Math.max(0,sv.lv1bank|0));}}catch(_){}
  buildStrips();loadPresets();meterLoop();
  let rev=-1,lv1sig="",downSince=0;
  async function poll(){
    try{const s=await api("/api/state");
      // rev ne bouge qu'avec l'etat X32 : un repatch / une couleur / un nom change dans la LV1 doit aussi
      // redessiner les voies (sinon le navigateur restait fige sur l'ancien patch LV1)
      const sig=JSON.stringify([s.exp_map,s.lv1_map,s.lv1_channels,s.lv1_sources]);
      if(s.rev!==rev||sig!==lv1sig||s.connected!==S.connected||s.trying!==S.trying){rev=s.rev;lv1sig=sig;S=s;
        // vue LV1 : un repatch (LV1 ou X32) change les colonnes elles-memes
        if(gview==="lv1"&&JSON.stringify(lv1Layout())!==layoutKey)buildStrips();else update();}
      if(downSince){location.reload();return;} // appli relancee : repartir d'une page neuve
    }catch(e){S.connected=false;S.trying=false;update();
      // appli principale arretee (fenetre noire fermee) : fetch echoue (TypeError), pas une simple reponse
      // invalide. Sur ce PC, on ferme l'onglet ; ailleurs (tablette) ou si le navigateur refuse, on le dit.
      if(e instanceof TypeError){
        if(!downSince)downSince=Date.now();
        else if(Date.now()-downSince>2000&&!$("#gone")){
          if(/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname))window.close();
          const g=document.createElement("div");g.id="gone";
          g.innerHTML="<div class='box'><h3>Appli arrêtée</h3><p>La fenêtre de l'appli a été fermée. "+
            "Vous pouvez fermer cet onglet ; il se recharge tout seul si l'appli est relancée.</p></div>";
          document.body.appendChild(g);}
      }}
    setTimeout(poll,downSince?1000:150);
  }
  poll();
})();
</script></body></html>
"""
def _brand(html):
    """Nom, auteur, version et logo (brand_icon.py, généré par tools/make_icon.py) dans les pages HTML."""
    for k, v in (("__APP_NAME__", APP_NAME), ("__APP_SHORT__", APP_SHORT), ("__APP_AUTHOR__", APP_AUTHOR),
                 ("__APP_VERSION__", APP_VERSION), ("__APP_LOGO__", LOGO_SVG),
                 ("__APP_ICON__", "data:image/svg+xml," + urllib.parse.quote(LOGO_SVG))):
        html = html.replace(k, v)
    return html


HTML = _brand(HTML)  # nom, auteur, version visibles dans l'interface
LOGIN_HTML = _brand(LOGIN_HTML)


# --------------------------------------------------------------------------
#  Main
# --------------------------------------------------------------------------
# --- Dossiers de donnees (depuis la 2.0.0) -----------------------------------------------------------
# Par defaut, TOUT va dans %APPDATA%\X32 Gain Recall (dossier "appli"), separe de l'exe : on peut
# telecharger une nouvelle version n'importe ou sans perdre ses scenes. Les SCENES (et profils de
# routing) peuvent etre deplacees dans un autre dossier choisi depuis l'interface (panneau Scenes ->
# "Dossier...") ; ce choix est memorise dans x32_gain_recall_settings.json du dossier appli. Le code
# d'acces, la config du float et la table LV1 manuelle restent dans le dossier appli.
APP_DIR_NAME = "X32 Gain Recall"
SETTINGS_FILE = "x32_gain_recall_settings.json"
SCENES_FILE = "x32_presets.json"
ROUTINGS_FILE = "x32_routings.json"
# fichiers que les versions <= 1.9 rangeaient a cote de l'exe/du script : recopies une fois au 1er lancement
LEGACY_FILES = (SCENES_FILE, ROUTINGS_FILE, "x32_lan_config.json", "x32_float_config.json", "lv1_patch_map.json")


def _writable_dir(d):
    try:
        os.makedirs(d, exist_ok=True)
        test = os.path.join(d, ".x32_write_test")
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return True
    except OSError:
        return False


def legacy_dir():
    """Dossier de l'exe (ou du script) : emplacement des donnees jusqu'a la 1.9."""
    return os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()


def app_data_dir():
    """%APPDATA%/X32 Gain Recall, cree au besoin ; a defaut le dossier personnel, puis celui de l'exe."""
    candidates = []
    if os.environ.get("APPDATA"):
        candidates.append(os.path.join(os.environ["APPDATA"], APP_DIR_NAME))
    candidates += [os.path.join(os.path.expanduser("~"), "." + APP_DIR_NAME.lower().replace(" ", "_")), legacy_dir()]
    for d in candidates:
        if _writable_dir(d):
            return d
    return os.getcwd()


def load_settings():
    try:
        with open(os.path.join(app_data_dir(), SETTINGS_FILE), "r", encoding="utf-8-sig") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(s):
    path = os.path.join(app_data_dir(), SETTINGS_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def remember_console(ip):
    """Derniere console demandee, reconnectee au prochain lancement (x32_gain_recall_settings.json)."""
    s = load_settings()
    if s.get("last_ip") != ip:
        s["last_ip"] = ip
        try:
            save_settings(s)
        except OSError:
            pass


def scenes_dir():
    """Dossier des scenes : celui choisi dans l'interface s'il existe encore, sinon le dossier appli."""
    d = load_settings().get("scenes_dir")
    if d and os.path.isdir(d):
        return d
    return app_data_dir()


def migrate_legacy_files():
    """Une seule fois : recopie (sans les supprimer) les fichiers rangés à côté de l'exe par les versions
    <= 1.9 vers le dossier appli, s'ils n'y sont pas déjà. Renvoie la liste des fichiers recopiés."""
    src, dst = legacy_dir(), app_data_dir()
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return []
    s = load_settings()
    if s.get("legacy_migrated"):
        return []
    copied = []
    for name in LEGACY_FILES:
        a, b = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isfile(a) and not os.path.exists(b):
            try:
                shutil.copy2(a, b)
                copied.append(name)
            except OSError:
                pass
    s["legacy_migrated"] = True
    try:
        save_settings(s)
    except OSError:
        pass
    return copied


def pick_data_path():
    """Chemin du fichier de scenes (nom conserve : utilise aussi par le float)."""
    return os.path.join(scenes_dir(), SCENES_FILE)


def scenes_dir_info(d):
    """Etat d'un dossier candidat pour les scenes : existe, modifiable, nombre de scenes deja dedans."""
    info = {"path": d, "exists": os.path.isdir(d), "writable": False, "count": 0, "has_file": False}
    if info["exists"]:
        info["writable"] = _writable_dir(d)
        f = os.path.join(d, SCENES_FILE)
        if os.path.isfile(f):
            info["has_file"] = True
            try:
                with open(f, "r", encoding="utf-8-sig") as fh:
                    data = json.load(fh)
                info["count"] = len(data.get("presets", [])) if isinstance(data, dict) else 0
            except (OSError, ValueError):
                info["count"] = -1      # fichier illisible
    return info


def set_scenes_dir(d, copy_current):
    """Bascule les scenes (et profils de routing) vers le dossier d. Si d contient deja des scenes, on les
    utilise ; sinon, copy_current=True y recopie les fichiers actuels (sinon on y part de zero). Le choix
    est memorise (retour au dossier appli = on oublie le choix). Renvoie scenes_dir_info(d)."""
    global STORE, ROUTINGS
    d = os.path.abspath(os.path.expanduser(d.strip().strip('"')))
    info = scenes_dir_info(d)
    if not info["exists"]:
        raise ValueError("Dossier introuvable : %s" % d)
    if not info["writable"]:
        raise ValueError("Impossible d'écrire dans ce dossier : %s" % d)
    if info["count"] == -1:
        raise ValueError("Le fichier %s de ce dossier est illisible : choisissez un autre dossier" % SCENES_FILE)
    if copy_current and not info["has_file"]:
        for name, cur in ((SCENES_FILE, STORE.path), (ROUTINGS_FILE, ROUTINGS.path)):
            dst = os.path.join(d, name)
            if os.path.isfile(cur) and not os.path.exists(dst):
                shutil.copy2(cur, dst)
    STORE = PresetStore(os.path.join(d, SCENES_FILE))
    ROUTINGS = RoutingStore(os.path.join(d, ROUTINGS_FILE))
    s = load_settings()
    if os.path.normcase(d) == os.path.normcase(os.path.abspath(app_data_dir())):
        s.pop("scenes_dir", None)
    else:
        s["scenes_dir"] = d
    save_settings(s)
    return scenes_dir_info(d)


def browse_folder(initial):
    """Fenetre Windows « choisir un dossier », ouverte sur le PC qui fait tourner l'appli (pas sur la
    tablette qui a clique). Renvoie le dossier choisi ou None. Tkinter importe ici seulement."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        d = filedialog.askdirectory(parent=root, initialdir=initial or app_data_dir(), mustexist=True,
                                    title="Dossier des scènes — " + APP_SHORT)
    finally:
        root.destroy()
    return os.path.normpath(d) if d else None


def main():
    global STORE, ROUTINGS, X32_PORT
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--version", action="version", version="%s %s - by %s" % (APP_NAME, APP_VERSION, APP_AUTHOR))
    ap.add_argument("--ip", help="adresse IP de la X32 (pre-remplit le champ)")
    ap.add_argument("--sim", action="store_true", help="demarre un simulateur de X32 et s'y connecte")
    ap.add_argument("--web-port", type=int, default=8032, help="port de l'interface web locale (defaut 8032)")
    ap.add_argument("--no-browser", action="store_true", help="n'ouvre pas le navigateur")
    ap.add_argument("--no-float", action="store_true", help="n'ouvre pas la fenetre flottante au demarrage")
    ap.add_argument("--data", help="chemin du fichier de scenes (defaut : dossier choisi dans l'interface, sinon %%APPDATA%%/X32 Gain Recall)")
    ap.add_argument(
        "--local-only",
        action="store_true",
        help=(
            "n'ouvre PAS l'interface au reseau local : accessible seulement depuis cette machine (127.0.0.1), "
            "sans code d'acces. Comportement des versions 1.2 et anterieures."
        ),
    )
    ap.add_argument(
        "--lan-sans-mdp",
        action="store_true",
        help="desactive le code d'acces du mode reseau local. AUCUNE protection, a reserver a un reseau vraiment de confiance.",
    )
    ap.add_argument(
        "--lan-nouveau-code",
        action="store_true",
        help="regenere le code d'acces du mode reseau local (deconnecte tous les appareils deja connectes).",
    )
    ap.add_argument(
        "--lv1-map",
        help="table manuelle canal LV1 -> numeros EXP (defaut : %s dans le dossier de donnees de l'appli), relue a chaud" % MANUAL_FILENAME,
    )
    ap.add_argument(
        "--lv1-session",
        default=LIVE_DB,
        help=(
            "d'ou lire le patch LV1 (table EXP -> canal) : par defaut la session EN DIRECT de la LV1 lancee sur ce PC "
            "(%(default)s, mise a jour ~1 s apres chaque repatch, sans sauvegarde) ; sinon un .emo, ou un dossier "
            "dont le .emo le plus recent est relu. La table manuelle reste prioritaire."
        ),
    )
    ap.add_argument(
        "--lv1-sans-session",
        action="store_true",
        help="ne lit aucune session LV1 : table manuelle seulement",
    )
    ap.add_argument(
        "--companion",
        nargs="?", const=COMPANION_URL, default=None, metavar="URL",
        help="FACULTATIF : interroge aussi Bitfocus Companion (module companion-module-waves-lv1) pour la couleur et "
             "le nom des canaux LV1 (sinon lus directement dans la LV1). Sans URL : %s" % COMPANION_URL,
    )
    ap.add_argument("--no-colors", action="store_true", help="n'affiche ni la couleur ni le nom des canaux LV1")
    ap.add_argument("--color-poll", type=float, default=1.0, help="intervalle (s) d'interrogation de Companion (defaut 1.0)")
    ap.add_argument(
        "--lv1-device",
        default=",".join(DEFAULT_DEVICES),
        help=(
            "avec --lv1-session : devices LV1 dont le numero de voie = numero EXP de la X32, par priorite, "
            "separes par des virgules (defaut %(default)s ; voir lv1/session_patch.py)"
        ),
    )
    a = ap.parse_args()
    a.lan = not a.local_only  # accessible au reseau local par defaut depuis la 1.3 ; --local-only revient a l'ancien comportement

    global ALLOW_ANY_HOST, LAN_CODE, WEB_PORT, CODE_PATH, LOCAL_URL, LAN_URLS
    ALLOW_ANY_HOST = bool(a.lan)

    migrated = [] if a.data else migrate_legacy_files()
    STORE = PresetStore(a.data or pick_data_path())
    ROUTINGS = RoutingStore(os.path.join(os.path.dirname(os.path.abspath(STORE.path)), ROUTINGS_FILE))

    global LV1
    LV1 = PatchMap(
        manual_path=a.lv1_map or os.path.join(app_data_dir(), MANUAL_FILENAME),
        session_path=None if a.lv1_sans_session else a.lv1_session,
        devices=a.lv1_device,
    ).start()
    global LV1_COMPANION, LV1_NO_COLORS
    LV1_NO_COLORS = a.no_colors
    if a.companion and not a.no_colors:
        LV1_COMPANION = CompanionPoller(a.companion, lambda: lv1_channels_in_use(CLIENT), a.color_poll).start()

    code_path = None
    if a.lan and not a.lan_sans_mdp:
        code_path = os.path.join(app_data_dir(), "x32_lan_config.json")
        LAN_CODE = load_or_create_lan_config(code_path, regenerate=a.lan_nouveau_code)

    bind_host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = None
    for port in range(a.web_port, a.web_port + 20):
        try:
            srv = ThreadingHTTPServer((bind_host, port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        print("Impossible d'ouvrir un port local pour l'interface.")
        sys.exit(1)
    port = srv.server_address[1]
    WEB_PORT = port
    ALLOWED_HOSTS.update({"127.0.0.1:%d" % port, "localhost:%d" % port})
    url = "http://127.0.0.1:%d/" % port

    lan_urls = []
    if a.lan:
        for ip in _local_ipv4_addresses():
            ALLOWED_HOSTS.add("%s:%d" % (ip, port))
            lan_urls.append("http://%s:%d/" % (ip, port))
    LOCAL_URL, LAN_URLS = url, lan_urls
    CODE_PATH = code_path

    if a.sim:
        ok, err = start_sim()
        if not ok:
            print(err)
            sys.exit(1)
        CLIENT.connect("127.0.0.1")
        CLIENT.demo = True
    elif a.ip:
        CLIENT.connect(a.ip)
    elif load_settings().get("last_ip"):
        # derniere console : connect() ne bloque pas et retente tout seul, la console peut arriver plus tard
        CLIENT.connect(load_settings()["last_ip"])
        threading.Thread(target=CLIENT.refresh_exp_map, daemon=True).start()

    print("%s v%s  -  by %s  -  interface : %s" % (APP_NAME, APP_VERSION, APP_AUTHOR, url))
    if a.lan:
        print("")
        if LAN_CODE:
            print("Accessible au reseau local, protege par un code (pas de https : reseau de confiance recommande).")
            print("+---------------------+")
            print("|  CODE D'ACCES : %s |" % LAN_CODE)
            print("+---------------------+")
            print("(aussi affiche dans l'interface web, en haut a droite ; sauvegarde dans %s ; pour un nouveau code : relancer avec --lan-nouveau-code)" % code_path)
        else:
            print("!!! --lan-sans-mdp actif : AUCUNE protection, AUCUN chiffrement (http, pas https). !!!")
            print("!!! Toute personne sur ce reseau peut piloter la console via cette adresse.               !!!")
        if lan_urls:
            print("Accessible depuis une tablette/telephone sur le meme reseau :")
            for u in lan_urls:
                print("  - %s" % u)
            if LAN_CODE:
                print("(ouvrir simplement ce lien, puis taper le code ci-dessus sur l'ecran de connexion)")
        else:
            print("Aucune adresse reseau locale detectee automatiquement (verifier la connexion Wi-Fi/Ethernet).")
        print("")
    print("Donnees : %s" % app_data_dir())
    print("Scenes : %s" % STORE.path)
    if migrated:
        print("  (recopie depuis le dossier de l'exe, version precedente : %s)" % ", ".join(migrated))
    st = LV1.status()
    print("Patch LV1 (EXP -> canal) : %d EXP connus  [table manuelle : %s (%d canaux)%s]" % (
        len(LV1.exp_to_channel()), st["manual_file"], st["manual_channels"],
        ("  [session : %s (%d canaux)]" % (st["session_file"] or st["session_source"], st["session_channels"])) if st["session_source"] else ""))
    for err in st["errors"].values():
        print("  ! %s" % err)
    print("Ctrl+C pour quitter.")
    threading.Thread(target=_startup_windows, args=(url, not a.no_browser, not a.no_float), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CLIENT.disconnect()


if __name__ == "__main__":
    if "--float" in sys.argv:
        # Drapeau interne (jamais tape par l'utilisateur a la main - utilise par le bouton "Float" du
        # navigateur et par launch_float_window() ci-dessus) : delegue entierement a la fenetre
        # flottante, importee ici seulement (et non en haut du fichier) pour que ce script continue a
        # demarrer sans tkinter quand on ne s'en sert pas comme fenetre flottante.
        sys.argv.remove("--float")
        import x32_gain_float
        x32_gain_float.main()
    else:
        main()
