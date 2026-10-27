"""touchosc/protocol.py — langage OSC entre la tablette (template TouchOSC) et Gain Recall. Fonctions pures, testées.

Réglage de TouchOSC (Connections > OSC, UDP) : Host = IP du PC de la LV1, Send Port = PORT_IN, Receive Port = PORT_OUT.
Gain Recall répond à l'IP de la tablette sur PORT_OUT (TouchOSC n'envoie pas forcément depuis son port de réception).

Protocole PROTO (le template envoie le sien dans /xgr/hello : écart -> « template à mettre à jour ») :
  tablette -> Gain Recall
    /xgr/hello      i proto, s nom de l'appareil        toutes les secondes (présence)
  Gain Recall -> tablette
    /xgr/welcome    i proto, s version de Gain Recall, s console, s état
                    état : "ok" | "old_template" | "new_template"
Phase 0 (27/10/2026) : présence seulement. Gains, couches, scènes… dans les phases suivantes (docs/TOUCHOSC.md).
"""
PROTO = 1
PORT_IN = 9300          # Gain Recall écoute ici (Send Port de TouchOSC)
PORT_OUT = 9301         # la tablette écoute ici (Receive Port de TouchOSC)
LOST_S = 4.0            # tablette oubliée sans hello depuis ce délai

HELLO, WELCOME = "/xgr/hello", "/xgr/welcome"


def arg_values(args):
    """[(type, valeur)] OSC -> [valeur] (TouchOSC envoie un entier Lua en « i » ou en « f » selon le cas)."""
    return [v for _t, v in args]


def parse_hello(args):
    """(proto, nom) d'un /xgr/hello, ou None s'il est mal formé."""
    vals = arg_values(args)
    if not vals or not isinstance(vals[0], (int, float)):
        return None
    name = vals[1] if len(vals) > 1 and isinstance(vals[1], str) else "TouchOSC"
    return int(vals[0]), name[:40]


def template_state(proto):
    if proto == PROTO:
        return "ok"
    return "old_template" if proto < PROTO else "new_template"


def console_text(state):
    """Texte court de la console 1 d'après /api/state : « X32RACK-JS » / « No console »."""
    state = state or {}
    if not state.get("connected"):
        return "No console"
    info = state.get("info") or {}
    return str(info.get("name") or info.get("model") or "X32")


def welcome(proto, version, state):
    return WELCOME, [("i", PROTO), ("s", version), ("s", console_text(state)), ("s", template_state(proto))]
