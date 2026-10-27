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


def parse_layers(args):
    """/Notify/Layers : vue (0 = Mixer 1, 1 = Mixer 2), drapeau (1 = pages Custom), nb, puis par couche : nom, n,
    (groupe, canal) x n, (-1, -1) = tranche vide (XTouch-LV1 parse_layers). -> (vue, drapeau, [(nom, [(g, c) | None])])."""
    if len(args) < 3 or any(a[0] != "i" for a in args[:3]):
        return None, None, []
    view, flag, count = args[0][1], args[1][1], args[2][1]
    layers, i = [], 3
    for _ in range(max(0, min(count, 32))):
        if i + 1 >= len(args) or args[i][0] != "s" or args[i + 1][0] != "i":
            break
        name, n = args[i][1], args[i + 1][1]
        i += 2
        entries = []
        for _ in range(max(0, n)):
            if i + 1 >= len(args):
                break
            g, c = args[i][1], args[i + 1][1]
            i += 2
            entries.append(None if (g == -1 and c == -1) else (g, c))
        layers.append((name.strip(), entries))
    return view, flag, layers


def set_kind(flag, layers):
    """Mode d'un jeu de couches (relevé le 27/10 sur la LV1 de Joseph, 80 canaux : Mixer 1 en Mix, Mixer 2 en Input) :
    "custom" (drapeau 1, pages Custom), "mix" (Groups, Fx, Mon…, Masters, Link DCA : mode Mix du 80 canaux), "input"
    (que des Ch : mode Input du 80 canaux), "factory" (16 / 32 / 64 canaux : Ch… puis Grp/Fx, Monitor, Masters, Link
    DCA), None sinon (Spill : affiché si la LV1 le montre, jamais mémorisé)."""
    if flag == 1:
        return "custom"
    names = [n for n, e in layers if any(e)]
    if names and names[0] == "Groups":
        return "mix"
    if names and all(n.startswith("Ch ") for n in names):
        return "input"
    if any(n.startswith("Ch ") for n in names) and ("Masters" in names or "Link DCA" in names):
        return "factory"
    return None


class LV1Mixer:
    def __init__(self):
        self.lock = threading.Lock()
        self.tracks = {}          # (g, c) -> {"name", "fader", "mute", "solo", "stereo", "pan", "trim": {voie: dB},
        #                                      "phase": {voie: bool}, "pal": n° de palette (couleur)}
        self.meters = {}          # (g, c, voie) -> (dB, instant)
        self.channels_at = 0.0    # dernier /Channels complet
        # Couches (tablette, 27/10) : jeux vus par mode (mémorisés : en 80 canaux la LV1 n'envoie que le mode affiché
        # sur chaque Mixer, /Get/Layers ne donne que celui-là) ; « custom » est propre à chaque Mixer (custom0 / custom1)
        self.sets = {}            # "factory" | "input" | "mix" | "custom0" | "custom1" -> [(nom, [(g, c) | None])]
        self.sets_rev = 0         # +1 à chaque jeu nouveau ou changé (enregistrement de la mémoire)
        self.pending = {}         # vue -> (drapeau, couches) reçu, adopté au /Notify/CurrentLayer qui le suit
        self.shown = {}           # vue -> {"kind", "layers", "index"} : ce que montre ce Mixer

    def track(self, g, c):
        return self.tracks.setdefault((g, c), {"name": None, "fader": None, "mute": None, "solo": None,
                                               "stereo": None, "pan": None, "trim": {}, "phase": {}, "pal": None})

    def _remember(self, view, flag, layers):
        kind = set_kind(flag, layers)
        if kind is None:
            return None
        key = "custom%d" % view if kind == "custom" else kind
        if self.sets.get(key) != layers:
            self.sets[key] = layers
            self.sets_rev += 1
        return kind

    def load_sets(self, sets):
        """Mémoire des jeux (fichier de Gain Recall) : {clé: [[nom, [[g, c] | None…]]…]} ; ce qui est reçu en direct
        remplace."""
        with self.lock:
            for key, layers in (sets or {}).items():
                if key in ("factory", "input", "mix", "custom0", "custom1") and key not in self.sets:
                    try:
                        self.sets[key] = [(str(n), [tuple(e) if e else None for e in ents]) for n, ents in layers]
                    except (TypeError, ValueError):
                        pass

    def layers_snapshot(self):
        """{"sets": {clé: [(nom, entrées)]}, "shown": {vue: {"kind", "layers", "index"}}, "rev"} pour le pont."""
        with self.lock:
            return {"sets": {k: list(v) for k, v in self.sets.items()},
                    "shown": {v: dict(s) for v, s in self.shown.items()}, "rev": self.sets_rev}

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
            elif address == "/Notify/TrackColor" and len(args) >= 3 and args[2][0] == "i":
                self.track(v[0], v[1])["pal"] = v[2]
            elif address == "/Notify/Layers":
                # adopté comme « affiché » SEULEMENT s'il est suivi de /Notify/CurrentLayer pour la même vue (règle de
                # XTouch-LV1, bug du 15/10 : à la connexion, les pages Custom arrivent en dernier SANS CurrentLayer) ;
                # mémorisé dans tous les cas (mode reconnu)
                view, flag, layers = parse_layers(args)
                if layers:
                    self._remember(view, flag, layers)
                    self.pending[view] = (flag, layers)
            elif address == "/Notify/CurrentLayer" and len(args) >= 2 and args[1][0] == "i":
                view, index = v[0], v[1]
                pend = self.pending.pop(view, None)
                if pend:
                    self.shown[view] = {"kind": set_kind(*pend), "layers": pend[1], "index": index}
                elif view in self.shown:
                    self.shown[view]["index"] = index

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
