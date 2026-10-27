"""lv1/model.py — état du mixer de la LV1 (faders, mutes, solos, pans, trims, phases, mono / stéréo, vumètres), tenu à
jour par les notifications OSC de la télécommande (protocole MyFOH, lv1/remote.py). Tablette TouchOSC, phase 5 (27/10/2026).

Repris de XTouch-LV1 (xtouch_lv1_display.handle, vérifié sur la LV1 de Joseph), formats relevés en direct le 27/10 :
  /Channels i:N puis N x 19 valeurs : nom, groupe, canal, fader (dB, -144 = -inf), pan?, 12 entiers (1er solo, 2e mute,
            12e : 1 mono / 2 stéréo), h, d. Liste COMPLÈTE : les pistes absentes ont disparu (passage 80 -> 64
            canaux, correctif XTouch-LV1 du 20/10) ; liste tronquée : rien n'est retiré.
  /Notify/Track/Out/Gain g c d:dB [T]   /Notify/Track/Out/Mute g c i [T]   /Notify/Solo g c i i
  /Notify/Track/Pan g c f (-45..+45)    /Notify/TrackTrim g c voie f:dB    /Notify/PhaseState g c voie état i
  /Notify/StemFormatForSource g c 100|101 1|2 (mono / stéréo, à chaque changement)
  /Notify/Meters i:N puis N x (g, c, voie, f:dB), ~23 trames / s, sans abonnement.
À la connexion la LV1 envoie d'elle-même /Channels, les trims et les phases ; PAS les pans (lus dans la base :
lv1/channelinfo.py, paramètre 436). Groupes : 0 entrées, 1 groupes, 2 Fx, 3 LR, 4 C, 5 M, 12 DCA, 25 Mon.
"""
import threading
import time

METER_STALE = 1.0          # s : vumètre plus reçu depuis ce délai = pas de signal connu (voie droite d'un canal remis
#                            en mono, par exemple : la LV1 ne l'envoie plus)


class LV1Mixer:
    def __init__(self):
        self.lock = threading.Lock()
        self.tracks = {}          # (g, c) -> {"name", "fader", "mute", "solo", "stereo", "pan", "trim": {voie: dB},
        #                                      "phase": {voie: bool}}
        self.meters = {}          # (g, c, voie) -> (dB, instant)
        self.channels_at = 0.0    # dernier /Channels complet

    def track(self, g, c):
        return self.tracks.setdefault((g, c), {"name": None, "fader": None, "mute": None, "solo": None,
                                               "stereo": None, "pan": None, "trim": {}, "phase": {}})

    def handle(self, address, args):
        """Une notification de la LV1 (args = [(type, valeur)]). Les autres adresses sont ignorées."""
        if address == "/Notify/Meters":
            now = time.time()
            with self.lock:
                for i in range(1, len(args) - 3, 4):
                    g, c, s, d = args[i], args[i + 1], args[i + 2], args[i + 3]
                    if g[0] == "i" and c[0] == "i" and s[0] == "i" and d[0] in "fd":
                        self.meters[(g[1], c[1], s[1])] = (d[1], now)
            return
        v = [x for _t, x in args]
        with self.lock:
            if address == "/Channels" and args and args[0][0] == "i":
                self._channels(args)
            elif address == "/Notify/Track/Out/Gain" and len(args) >= 3 and args[2][0] in "fdi":
                self.track(v[0], v[1])["fader"] = float(v[2])
            elif address == "/Notify/Track/Out/Mute" and len(args) >= 3 and args[2][0] == "i":
                self.track(v[0], v[1])["mute"] = v[2] != 0
            elif address == "/Notify/Solo" and len(args) >= 3 and args[2][0] == "i":
                self.track(v[0], v[1])["solo"] = v[2] != 0
            elif address == "/Notify/Track/Pan" and len(args) >= 3 and args[2][0] in "fd":
                self.track(v[0], v[1])["pan"] = max(-1.0, min(1.0, float(v[2]) / 45.0))
            elif address == "/Notify/TrackTrim" and len(args) >= 4 and args[3][0] in "fd":
                self.track(v[0], v[1])["trim"][v[2]] = float(v[3])
            elif address == "/Notify/PhaseState" and len(args) >= 4 and args[3][0] == "i":
                self.track(v[0], v[1])["phase"][v[2]] = v[3] != 0
            elif address == "/Notify/StemFormatForSource" and len(args) >= 4 and all(a[0] == "i" for a in args[:4]):
                self.track(v[0], v[1])["stereo"] = v[3] == 2

    def _channels(self, args):
        count = args[0][1]
        seen, whole = set(), 0 < count <= 256
        for k in range(max(0, min(count, 256))):
            base = 1 + k * 19
            if base + 6 >= len(args):
                whole = False
                break
            n, g, c, f = args[base], args[base + 1], args[base + 2], args[base + 3]
            if n[0] != "s" or g[0] != "i" or c[0] != "i":
                continue
            seen.add((g[1], c[1]))
            t = self.track(g[1], c[1])
            t["name"] = n[1]
            if f[0] == "d":
                t["fader"] = float(f[1])
            so, mu = args[base + 5], args[base + 6]
            if so[0] == "i":
                t["solo"] = so[1] != 0
            if mu[0] == "i":
                t["mute"] = mu[1] != 0
            if base + 16 < len(args) and args[base + 16][0] == "i":
                t["stereo"] = args[base + 16][1] == 2
        if whole and seen:
            for key in [k for k in self.tracks if k not in seen]:
                del self.tracks[key]
        self.channels_at = time.time()

    def meter(self, g, c, now=None):
        """Niveau (dB) le plus haut des voies de la piste, ou None (rien de récent)."""
        now = time.time() if now is None else now
        with self.lock:
            vals = [d for (mg, mc, _s), (d, t) in self.meters.items() if mg == g and mc == c and now - t <= METER_STALE]
        return max(vals) if vals else None

    def snapshot(self):
        """{(g, c): copie de la piste + "meter" (dB ou None)} pour le pont TouchOSC."""
        now = time.time()
        with self.lock:
            levels = {}
            for (g, c, _s), (d, t) in self.meters.items():
                if now - t <= METER_STALE and ((g, c) not in levels or d > levels[(g, c)]):
                    levels[(g, c)] = d
            return {key: dict(t, trim=dict(t["trim"]), phase=dict(t["phase"]), meter=levels.get(key))
                    for key, t in self.tracks.items()}
