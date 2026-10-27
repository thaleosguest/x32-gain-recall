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
    /xgr/view/bank  i banque (0 = Ch 1-16 … 4 = 65-80)  vue fixe de CETTE tablette (la LV1 ne bouge pas)
    /xgr/view/follow                                   la tablette suit de nouveau la couche de la LV1
    /xgr/g/k/u/gain f dB voulu                         voie u de la tranche k de la page de CETTE tablette
    /xgr/g/k/u/48v                                     bascule du 48V (déjà confirmée sur la tablette)
  Gain Recall -> tablette
    /xgr/welcome    i proto, s version, s console, s ok|old_template|new_template|pending
                    pending : tablette pas encore autorisée (rien d'autre ne lui est envoyé)
    état (envoyé quand il change, tout à l'arrivée et sur /xgr/sync) : voir state_messages()
      barre d'état : /xgr/console s, /xgr/console/ok i, /xgr/lv1 s, /xgr/tablets i
      vue (phase 2b, PAR TABLETTE) : /xgr/view/follow i (1 = suit la LV1), /xgr/view/bank i (0..4, -1 = couche
        sans banque), /xgr/view/banks i (banques proposées)
      page GAINS (phase 2a, calque du float sur la couche LV1 de Mixer 1) : /xgr/g/title s ; tranche k = 1..16 :
        /xgr/g/k/name s (nom LV1), /xgr/g/k/ch i (n° du canal, 0 = tranche vide), /xgr/g/k/input s (source LV1
        « 1- EX 1 », une ligne par voie), /xgr/g/k/color s (« RRGGBB » ou ""), /xgr/g/k/src s, /xgr/g/k/units i (0, 1 = « m », 2 =
        « l » + « r ») ; voie u : /xgr/g/k/u/gain f (0..1 de -12..+60 dB), /xgr/g/k/u/db s, /xgr/g/k/u/48v i
    /xgr/notify     s texte                            message ponctuel (erreur d'une action…)
"""
from . import views

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


def state_messages(state, tablets=1, page=None):
    """État de Gain Recall (merged_snapshot) -> {adresse: (arguments OSC…)} à tenir à jour sur une tablette. Le pont
    n'envoie que les adresses dont les arguments ont changé. page : views.gain_page de CETTE tablette (sa vue)."""
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
    out = {
        "/xgr/console": (("s", console),),
        "/xgr/console/ok": (("i", 1 if state.get("connected") else 0),),
        "/xgr/lv1": (("s", lv1),),
        "/xgr/tablets": (("i", int(tablets)),),
    }
    out.update(gain_messages(page if page is not None else views.gain_page(state)))
    return out


def gain_messages(page):
    """Page GAINS (views.gain_page) -> messages. Les voies absentes ne sont pas envoyées (cachées sur la tablette)."""
    out = {"/xgr/g/title": (("s", page["title"]),),
           "/xgr/view/follow": (("i", 1 if page.get("follow", True) else 0),),
           "/xgr/view/bank": (("i", -1 if page.get("bank") is None else int(page["bank"])),),
           "/xgr/view/banks": (("i", int(page.get("banks", 4))),)}
    for k, st in enumerate(page["strips"], 1):
        base = "/xgr/g/%d" % k
        out[base + "/name"] = (("s", st["name"]),)
        out[base + "/ch"] = (("i", st["ch"] if st["ch"] > 0 else 0),)
        out[base + "/input"] = (("s", st["input"]),)
        out[base + "/color"] = (("s", st["color"]),)
        out[base + "/src"] = (("s", st["src"]),)
        out[base + "/units"] = (("i", len(st["units"])),)
        for u, unit in zip(views.unit_names(len(st["units"])), st["units"]):
            out["%s/%s/gain" % (base, u)] = (("f", round(views.gain_frac(unit["db"]), 4)),)
            out["%s/%s/db" % (base, u)] = (("s", views.db_text(unit["db"])),)
            out["%s/%s/48v" % (base, u)] = (("i", 1 if unit["phantom"] else 0),)
    return out


def parse_action(address, args):
    """Message de la tablette -> action de la liste fermée : (nom, paramètres…), ou None (ignoré).
    ("sync",) ; ("bank", n) ; ("follow",) ; ("gain", k, u, dB) ; ("phantom", k, u) — k = tranche 1..16, u = m / l / r."""
    vals = arg_values(args)
    num = vals[0] if vals and isinstance(vals[0], (int, float)) and not isinstance(vals[0], bool) else None
    if address == SYNC:
        return ("sync",)
    if address == "/xgr/view/follow":
        return ("follow",)
    if address == "/xgr/view/bank":
        return ("bank", int(num)) if num is not None and 0 <= num <= 4 else None
    parts = address.split("/")                       # ["", "xgr", "g", k, u, champ]
    if len(parts) == 6 and parts[1:3] == ["xgr", "g"] and parts[3].isdigit() and parts[4] in ("m", "l", "r"):
        k, u = int(parts[3]), parts[4]
        if not 1 <= k <= views.STRIPS:
            return None
        if parts[5] == "gain" and num is not None:
            return ("gain", k, u, max(views.GAIN_MIN, min(views.GAIN_MAX, float(num))))
        if parts[5] == "48v":
            return ("phantom", k, u)
    return None


def allowed(ip, allow, own=()):
    """Expéditeur accepté ? Le PC lui-même toujours (127.x, ou une de ses adresses réseau `own`) ; sinon la liste."""
    return ip.startswith("127.") or ip == "::1" or ip in (own or ()) or ip in (allow or ())
