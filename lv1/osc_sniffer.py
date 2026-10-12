#!/usr/bin/env python3
"""
lv1/osc_sniffer.py (ex lv1_osc_sniffer.py) — Écoute brute du flux OSC-sur-TCP de la Waves eMotion LV1.

Reproduit EXACTEMENT le protocole trouvé dans le code source du module
Companion officiel (bitfocus/companion-module-waves-lv1, src/osc-tcp.ts + src/osc.ts) :

  - Framing : [4 octets longueur BE][8 octets en-tête propriétaire][payload OSC]
    (la longueur ne couvre QUE le payload OSC, pas les 8 octets d'en-tête)
  - Poignée de main style "MyFOH" (iPad) : envoi batché de /handshake + /device_name
    dans UNE seule écriture TCP, attente de l'ACK /handshake
  - Keep-alive : la LV1 envoie /ping toutes les ~1s ; si on ne répond pas par /pong
    avec les mêmes arguments, elle coupe le lien après ~5s

But : logger TOUTES les adresses OSC reçues en temps réel, pour repérer un éventuel
message de routage/patch (canal -> entrées physiques EXP) que le module Companion
n'expose pas en variable. Repatchez un canal dans la fenêtre Patch de la LV1 pendant
que ce script tourne, et regardez ce qui apparaît.

OUTIL DE DIAGNOSTIC UNIQUEMENT, pas utilisé par l'appli : c'est avec lui qu'on a confirmé qu'aucune
adresse OSC de patch ne transite (d'où lv1/patchmap.py, qui prend le patch ailleurs).

Usage (depuis la racine du repo) :
    python -m lv1.osc_sniffer 192.168.1.5 55646
    python -m lv1.osc_sniffer 192.168.1.5 55646 --filter=patch,assign,input,route
"""

import socket
import struct
import sys
import threading
import time
import uuid as uuid_mod

HEADER = bytes([0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00])
HEADER_LEN = 8


# ───────────────────────── OSC 1.0 encode/decode (port fidèle de osc.ts) ─────────────────────────

def pad4(n: int) -> int:
    return (4 - (n % 4)) % 4


def encode_string(s: str) -> bytes:
    b = s.encode("utf-8") + b"\x00"
    return b + b"\x00" * pad4(len(b))


def encode_message(address: str, args):
    """args: liste de tuples (type_char, value). Types gérés : i, f, s, h, d."""
    tag = "," + "".join(t for t, _ in args)
    parts = [encode_string(address), encode_string(tag)]
    for t, v in args:
        if t == "i":
            parts.append(struct.pack(">i", int(v)))
        elif t == "f":
            parts.append(struct.pack(">f", float(v)))
        elif t == "h":
            parts.append(struct.pack(">q", int(v)))
        elif t == "d":
            parts.append(struct.pack(">d", float(v)))
        elif t == "s":
            parts.append(encode_string(str(v)))
        else:
            raise ValueError(f"type OSC non géré en écriture : {t}")
    return b"".join(parts)


def read_osc_string(buf: bytes, offset: int):
    end = buf.index(b"\x00", offset)
    s = buf[offset:end].decode("utf-8", errors="replace")
    total = end - offset + 1
    return s, offset + total + pad4(total)


def decode_message(buf: bytes):
    address, off = read_osc_string(buf, 0)
    if off >= len(buf):
        return address, []
    tag, off = read_osc_string(buf, off)
    if not tag.startswith(","):
        return address, []
    args = []
    for t in tag[1:]:
        if t == "i":
            args.append(("i", struct.unpack_from(">i", buf, off)[0])); off += 4
        elif t == "f":
            args.append(("f", struct.unpack_from(">f", buf, off)[0])); off += 4
        elif t == "h":
            args.append(("h", struct.unpack_from(">q", buf, off)[0])); off += 8
        elif t == "d":
            args.append(("d", struct.unpack_from(">d", buf, off)[0])); off += 8
        elif t == "s":
            s, off = read_osc_string(buf, off)
            args.append(("s", s))
        elif t == "b":
            blen = struct.unpack_from(">i", buf, off)[0]; off += 4
            args.append(("b", buf[off:off + blen])); off += blen + pad4(blen)
        elif t == "T":
            args.append(("T", True))
        elif t == "F":
            args.append(("F", False))
        elif t == "N":
            args.append(("N", None))
        elif t == "I":
            args.append(("I", float("inf")))
        else:
            break  # type inconnu — on arrête, le reste serait mal aligné
    return address, args


# ───────────────────────── Client TCP LV1 ─────────────────────────

class LV1Sniffer:
    def __init__(self, host, port, device_name="lv1-sniffer", name_filter=None):
        self.host = host
        self.port = port
        self.device_name = device_name
        self.uuid = str(uuid_mod.uuid4()).upper()
        self.sock = None
        self.rxbuf = b""
        self.registered = False
        self.name_filter = name_filter  # liste de sous-chaînes (lowercase) à surligner

    def connect(self):
        print(f"[+] Connexion à {self.host}:{self.port} ...")
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(None)
        print("[+] Connecté. Poignée de main (style MyFOH)...")
        self.send_batch([
            ("/handshake", [("i", 1), ("i", -1), ("i", 1)]),
            ("/device_name", [("s", self.device_name), ("s", self.uuid)]),
        ])

    def send(self, address, args):
        self.send_batch([(address, args)])

    def send_batch(self, messages):
        frames = []
        for address, args in messages:
            packet = encode_message(address, args)
            frames.append(struct.pack(">I", len(packet)) + HEADER + packet)
        self.sock.sendall(b"".join(frames))

    def run(self):
        self.connect()
        buf = b""
        while True:
            chunk = self.sock.recv(65536)
            if not chunk:
                print("[-] Connexion fermée par la LV1.")
                return
            buf += chunk
            while len(buf) >= 4 + HEADER_LEN:
                size = struct.unpack_from(">I", buf, 0)[0]
                if size == 0 or size > 16 * 1024 * 1024:
                    buf = buf[1:]  # resync
                    continue
                total = 4 + HEADER_LEN + size
                if len(buf) < total:
                    break
                payload = buf[4 + HEADER_LEN:total]
                buf = buf[total:]
                try:
                    address, args = decode_message(payload)
                except Exception as e:
                    print(f"[!] Erreur de décodage : {e}")
                    continue
                self.handle(address, args)

    def handle(self, address, args):
        if address == "/ping":
            # keep-alive obligatoire : on renvoie /pong avec les mêmes arguments
            self.send("/pong", args)
            return  # ne pas logger le bruit du ping

        if address == "/handshake" and not self.registered:
            if args and args[0] == ("i", 1):
                self.registered = True
                print("[+] Handshake OK — enregistré auprès de la LV1.\n")

        if address in ("/Notify/Meters", "/Notify/NetworkCongestion", "/Notify/TempoBlink"):
            return  # bruit haute fréquence, sans rapport avec le patch — on l'ignore

        line = f"{time.strftime('%H:%M:%S')}  {address}  {args}"
        if self.name_filter and any(f in address.lower() for f in self.name_filter):
            print(f">>> {line}")  # mise en évidence
        else:
            print(line)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    name_filter = None
    for arg in sys.argv[3:]:
        if arg.startswith("--filter="):
            name_filter = [s.strip().lower() for s in arg.split("=", 1)[1].split(",")]
        elif arg == "--filter" and len(sys.argv) > sys.argv.index(arg) + 1:
            pass  # forme "--filter a,b" gérée via --filter= de préférence

    sniffer = LV1Sniffer(host, port, name_filter=name_filter)
    try:
        sniffer.run()
    except KeyboardInterrupt:
        print("\n[+] Arrêt demandé (Ctrl+C).")
    except (ConnectionRefusedError, OSError) as e:
        print(f"[!] Impossible de se connecter à {host}:{port} — {e}")
        print("    Vérifiez que le port est le bon (il peut changer à chaque session LV1).")


if __name__ == "__main__":
    main()
