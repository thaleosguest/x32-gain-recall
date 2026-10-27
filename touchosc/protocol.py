"""touchosc/protocol.py — langage OSC entre la tablette (template TouchOSC) et Gain Recall. Fonctions pures, testées.

Chaque TouchOSC (PC ou tablette) fait tourner le template et parle LUI-MÊME à Gain Recall : le « serveur » de TouchOSC
(réseau de l'éditeur) ne sert qu'à distribuer le document. Réglage (Connections > OSC, UDP) : Host = IP du PC de la LV1
(127.0.0.1 sur ce PC), Send Port = PORT_IN, Receive Port = PORT_OUT.
Décision de Joseph (27/10/2026) : Gain Recall écoute sur le RÉSEAU par défaut, mais n'accepte que les tablettes
autorisées (le PC lui-même toujours) ; une inconnue est « en attente » jusqu'à la réponse à « Autoriser la tablette ? »
(retenue si oui ; refus valable jusqu'au prochain lancement). --touchosc-local : écoute en 127.0.0.1 seulement.
Gain Recall répond à l'IP de l'expéditeur sur PORT_OUT (TouchOSC n'envoie pas forcément depuis son port de réception).

Protocole PROTO (le template envoie le sien dans /xgr/hello : écart -> « template à mettre à jour ») :
  tablette -> Gain Recall
    /xgr/hello      i proto, s nom de l'appareil      toutes les secondes (présence) ; 1er hello -> tout l'état
    /xgr/sync                                          renvoyer tout l'état
  Gain Recall -> tablette
    /xgr/welcome    i proto, s version, s console, s ok|old_template|new_template|pending
                    pending : tablette pas encore autorisée (rien d'autre ne lui est envoyé)
    état (envoyé quand il change, tout à l'arrivée et sur /xgr/sync) : voir state_messages()
    /xgr/notify     s texte                            message ponctuel (erreur d'une action…)
"""
PROTO = 1
PORT_IN = 9300          # Gain Recall écoute ici (Send Port de TouchOSC)
PORT_OUT = 9301         # la tablette écoute ici (Receive Port de TouchOSC)
LOST_S = 4.0            # tablette oubliée sans hello depuis ce délai

HELLO, WELCOME, SYNC, NOTIFY = "/xgr/hello", "/xgr/welcome", "/xgr/sync", "/xgr/notify"


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
    """Texte court de la console 1 d'après l'état : « X32RACK-JS » / « No console »."""
    state = state or {}
    if not state.get("connected"):
        return "No console"
    info = state.get("info") or {}
    return str(info.get("name") or info.get("model") or "X32")


def welcome(proto, version, state, pending=False):
    return WELCOME, [("i", PROTO), ("s", version), ("s", console_text(state) if not pending else ""),
                     ("s", "pending" if pending else template_state(proto))]


def state_messages(state, tablets=1):
    """État de Gain Recall (merged_snapshot) -> {adresse: (arguments OSC…)} à tenir à jour sur la tablette. Le pont
    n'envoie que les adresses dont les arguments ont changé. Phase 1 : barre d'état (console, LV1, tablettes)."""
    state = state or {}
    consoles = state.get("consoles") or []
    up = sum(1 for c in consoles if c.get("connected"))
    if state.get("connected"):
        console = console_text(state) + (" + %d more" % (up - 1) if up > 1 else "")
    elif state.get("trying"):
        console = "Connecting to %s..." % (state.get("ip") or "console")
    else:
        console = "No console"
    exp = len(state.get("exp_map") or {})
    n = state.get("lv1_count") or 0
    lv1 = ("%d LV1 channels known, %d X32 sources on EXP" % (n, exp)) if n else "No LV1 session read"
    return {
        "/xgr/console": (("s", console),),
        "/xgr/console/ok": (("i", 1 if state.get("connected") else 0),),
        "/xgr/lv1": (("s", lv1),),
        "/xgr/tablets": (("i", int(tablets)),),
    }


def parse_action(address, args):
    """Message de la tablette -> action de la liste fermée : (nom, paramètres…), ou None (ignoré). Phase 1 : sync."""
    if address == SYNC:
        return ("sync",)
    return None


def allowed(ip, allow, own=()):
    """Expéditeur accepté ? Le PC lui-même toujours (127.x, ou une de ses adresses réseau `own`) ; sinon la liste."""
    return ip.startswith("127.") or ip == "::1" or ip in (own or ()) or ip in (allow or ())
