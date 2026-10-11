# -*- coding: utf-8 -*-
"""
lv1/companion.py — Couleur et nom des canaux LV1, lus EN DIRECT via l'API HTTP de Bitfocus Companion
(module communautaire companion-module-waves-lv1 : variables in<N>_color et in<N>_name de la connexion
"LV1"). Protocole LV1 rétro-ingénié par ce module, pas une spec Waves officielle.

Un seul interrogateur, tenu par l'appli principale (ou par le float en --direct) : le navigateur et la
fenêtre flottante lisent le même résultat dans /api/state (champ lv1_channels), au lieu que chacun
interroge Companion de son côté. Tourne sur un thread séparé : quelques requêtes HTTP par seconde ne
doivent jamais bloquer la boucle de gains.

Jamais de couleur inventée : Companion injoignable, variable absente ou réponse mal formée = inconnue.
"""
import re
import threading
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000"   # port HTTP par défaut de Companion v5.0


def display_name(channel, name):
    """Nom à afficher pour le canal LV1 ``channel`` : son nom s'il a été renommé, sinon « In N » (nom par
    défaut « Channel N » de la LV1, ou nom inconnu : le numéro vient de la table de patch, pas de
    Companion). "" si la voie n'arrive sur aucun canal."""
    if not channel:
        return ""
    name = (name or "").strip()
    if not name or re.fullmatch(r"Channel\s*%d" % int(channel), name, re.I):
        return "In %d" % int(channel)
    return name


class CompanionPoller:
    def __init__(self, base_url=DEFAULT_URL, channels_fn=lambda: (), interval=1.0, connection="LV1",
                 timeout=0.6):
        """channels_fn() -> canaux LV1 (int) à suivre, rappelée à chaque tour (ceux qui reçoivent un
        préampli X32 en ce moment)."""
        self.base_url = base_url.rstrip("/")
        self.channels_fn = channels_fn
        self.interval = max(0.3, interval)
        self.connection = connection
        self.timeout = timeout
        self.reachable = None        # None = pas encore interrogé
        self._data = {}              # {canal: {"color": "#RRGGBB" | None, "name": str | None}}

    def fetch_var(self, channel, var):
        """Texte brut de in<channel>_<var>, ou None si Companion est injoignable / la variable absente."""
        url = "%s/api/variable/%s/in%d_%s/value" % (self.base_url, self.connection, channel, var)
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:
                return r.read().decode("utf-8", "replace").strip()
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return None

    def poll_once(self):
        chans = sorted(set(int(c) for c in self.channels_fn() if c))
        old = self._data
        data, any_ok = {}, False
        for ch in chans:
            prev = old.get(ch, {})
            color = self.fetch_var(ch, "color")
            name = self.fetch_var(ch, "name")
            any_ok = any_ok or color is not None or name is not None
            if color is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                color = None
            # échec ponctuel : on garde la dernière valeur connue de CE canal ; un canal qui n'est plus
            # suivi disparaît (sinon une pastille resterait collée après un repatch)
            data[ch] = {"color": color if color is not None else prev.get("color"),
                        "name": name if name is not None else prev.get("name")}
        if chans:
            self.reachable = any_ok
        self._data = data            # réaffectation complète : lecture sans verrou depuis les autres threads

    def start(self):
        def loop():
            while True:
                try:
                    self.poll_once()
                except Exception:    # ne jamais tuer le thread (channels_fn pendant une reconnexion, etc.)
                    pass
                time.sleep(self.interval)
        threading.Thread(target=loop, daemon=True, name="lv1-companion").start()
        return self

    def snapshot(self):
        """{canal: {"color", "name", "label"}} — label = display_name(), prêt à afficher."""
        return {ch: dict(v, label=display_name(ch, v.get("name"))) for ch, v in self._data.items()}
