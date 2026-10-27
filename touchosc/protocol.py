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
    /xgr/g/k/set/fader f dB | pan f -1..1 | trim f dB  commandes de la LV1 du canal de la tranche k (phase 5b)
    /xgr/g/k/set/mute | solo | phase                   bascules (d'après l'état annoncé par la LV1)
    (rien pour LR : lecture seule, décision de Joseph du 27/10)
    /xgr/sc/recall  s id, i 48V (0|1)                  rappel d'une scène (déjà confirmé sur la tablette)
    /xgr/sc/undo                                       annule le dernier rappel
    /xgr/sc/save                                       enregistre une scène (nom automatique, à renommer sur le PC)
  Gain Recall -> tablette
    /xgr/welcome    i proto, s version, s console, s ok|old_template|new_template|pending
                    pending : tablette pas encore autorisée (rien d'autre ne lui est envoyé)
    état (envoyé quand il change, tout à l'arrivée et sur /xgr/sync) : voir state_messages()
      barre d'état : /xgr/console s, /xgr/console/ok i, /xgr/lv1 s, /xgr/tablets i
      page SCENES (phase 3a) : /xgr/sc/count i ; scène n = 1..count : /xgr/sc/n/name s, /xgr/sc/n/info s (date),
        /xgr/sc/n/id s ; /xgr/sc/last s (dernier rappel), /xgr/sc/canundo i
      vue (phase 2b, PAR TABLETTE) : /xgr/view/follow i (1 = suit la LV1), /xgr/view/bank i (0..4, -1 = couche
        sans banque), /xgr/view/banks i (banques proposées)
      page GAINS (phase 2a, calque du float sur la couche LV1 de Mixer 1) : /xgr/g/title s ; tranche k = 1..16 :
        /xgr/g/k/name s (nom LV1), /xgr/g/k/ch i (n° du canal, 0 = tranche vide), /xgr/g/k/input s (source LV1
        « 1- EX 1 », stéréo « 1- EX 31/32 »), /xgr/g/k/color s (« RRGGBB » ou ""), /xgr/g/k/src s, /xgr/g/k/units i (0, 1 = « m », 2 =
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
    out.update(scene_messages(views.scene_page(state)))
    return out


def scene_messages(sp):
    """Page SCENES -> messages (la liste entière : la tablette pagine et sélectionne elle-même)."""
    out = {"/xgr/sc/count": (("i", len(sp["items"])),), "/xgr/sc/last": (("s", sp["last"]),),
           "/xgr/sc/canundo": (("i", 1 if sp["can_undo"] else 0),)}
    for n, it in enumerate(sp["items"], 1):
        out["/xgr/sc/%d/name" % n] = (("s", it["name"]),)
        out["/xgr/sc/%d/info" % n] = (("s", it["info"]),)
        out["/xgr/sc/%d/id" % n] = (("s", it["id"]),)
    return out


TRIM_SPAN = 20.0         # potard de Trim : ±20 dB sur sa course (affichage seulement ; la valeur exacte est écrite)


def peak_text(db):
    """Crête du vumètre : au dixième au-dessus de -60 dB, au dB près en dessous (le bruit de fond ne fait pas défiler les
    chiffres à chaque trame), « -Inf » sans signal."""
    if db is None or db <= -143.9:
        return "-Inf"
    return "%.1f" % db if db > -60 else "%.0f" % db


def mix_messages(base, mix, lr=False):
    """Commandes de la LV1 d'une tranche (phase 5a, lecture seule) : fader, valeur, crête, vumètre, MUTE ; tranches
    d'entrée en plus : CUE, pan, Trim, Ø, A / B. mix None (LV1 pas connectée, tranche vide) : tout à « - » / 0."""
    m = mix or {}
    out = {base + "/fader": (("f", views.fader_frac(m.get("fader"))),),
           base + "/fval": (("s", "%.1f" % m["fader"] if m.get("fader") is not None else "-"),),   # « -144.0 » (LV1)
           base + "/meter": (("f", round(views.fader_frac(m.get("meter")), 2)),),
           base + "/peak": (("s", peak_text(m.get("meter")) if mix else "-"),),
           base + "/mute": (("i", 1 if m.get("mute") else 0),)}
    if lr:
        return out
    trim = m.get("trim")
    out.update({base + "/solo": (("i", 1 if m.get("solo") else 0),),
                base + "/pan": (("f", round((max(-1.0, min(1.0, m.get("pan") or 0.0)) + 1) / 2, 4)),),
                base + "/trim": (("f", round(max(0.0, min(1.0, ((trim or 0.0) + TRIM_SPAN) / (2 * TRIM_SPAN))), 4)),),
                base + "/trimv": (("s", ("%.1f" % trim) if trim is not None else "-"),),
                base + "/phase": (("i", 1 if m.get("phase") else 0),),
                base + "/ab": (("s", m.get("input") or "" if mix else ""),)})
    return out


def gain_messages(page):
    """Page GAINS (views.gain_page) -> messages. Les voies absentes ne sont pas envoyées (cachées sur la tablette)."""
    out = {"/xgr/g/title": (("s", page["title"]),),
           "/xgr/view/follow": (("i", 1 if page.get("follow", True) else 0),),
           "/xgr/view/bank": (("i", -1 if page.get("bank") is None else int(page["bank"])),),
           "/xgr/view/banks": (("i", int(page.get("banks", 4))),),
           "/xgr/live": (("i", 1 if page.get("live") else 0),)}
    out.update(mix_messages("/xgr/lr", page.get("lr"), lr=True))
    for k, st in enumerate(page["strips"], 1):
        base = "/xgr/g/%d" % k
        out[base + "/name"] = (("s", st["name"]),)
        out[base + "/ch"] = (("i", st["ch"] if st["ch"] > 0 else 0),)
        out[base + "/input"] = (("s", st["input"]),)
        out[base + "/color"] = (("s", st["color"]),)
        out[base + "/src"] = (("s", st["src"]),)
        out[base + "/units"] = (("i", len(st["units"])),)
        out.update(mix_messages(base, st.get("mix")))
        for u, unit in zip(views.unit_names(len(st["units"])), st["units"]):
            out["%s/%s/gain" % (base, u)] = (("f", round(views.gain_frac(unit["db"]), 4)),)
            out["%s/%s/db" % (base, u)] = (("s", views.db_text(unit["db"])),)
            out["%s/%s/48v" % (base, u)] = (("i", 1 if unit["phantom"] else 0),)
    return out


def parse_action(address, args):
    """Message de la tablette -> action de la liste fermée : (nom, paramètres…), ou None (ignoré).
    ("sync",) ; ("bank", n) ; ("follow",) ; ("gain", k, u, dB) ; ("phantom", k, u) ; ("lv1", k, champ, valeur) —
    k = tranche 1..16, u = m / l / r, champ = fader / pan / trim (valeur) ou mute / solo / phase (bascule, None)."""
    vals = arg_values(args)
    num = vals[0] if vals and isinstance(vals[0], (int, float)) and not isinstance(vals[0], bool) else None
    if address == SYNC:
        return ("sync",)
    if address == "/xgr/sc/recall":
        if not vals or not isinstance(vals[0], str) or not vals[0]:
            return None
        ph = vals[1] if len(vals) > 1 and isinstance(vals[1], (int, float)) else 0
        return ("scene_recall", vals[0][:40], bool(ph))
    if address == "/xgr/sc/undo":
        return ("scene_undo",)
    if address == "/xgr/sc/save":
        return ("scene_save",)
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
    if len(parts) == 6 and parts[1:3] == ["xgr", "g"] and parts[3].isdigit() and parts[4] == "set":
        k, field = int(parts[3]), parts[5]
        if not 1 <= k <= views.STRIPS:
            return None
        if field == "fader" and num is not None:
            return ("lv1", k, "fader", max(-144.0, min(10.0, float(num))))
        if field == "pan" and num is not None:
            return ("lv1", k, "pan", max(-1.0, min(1.0, float(num))))
        if field == "trim" and num is not None:
            return ("lv1", k, "trim", float(num))
        if field in ("mute", "solo", "phase"):
            return ("lv1", k, field, None)
    return None


def allowed(ip, allow, own=()):
    """Expéditeur accepté ? Le PC lui-même toujours (127.x, ou une de ses adresses réseau `own`) ; sinon la liste."""
    return ip.startswith("127.") or ip == "::1" or ip in (own or ()) or ip in (allow or ())
