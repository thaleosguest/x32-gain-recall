# -*- coding: utf-8 -*-
"""
lv1/patchmap.py — Table de correspondance EXP -> canal LV1 ("In N"), pour savoir de quel canal LV1
afficher la couleur sur une voie X32.

POURQUOI : la couleur LV1 (variable Companion in<N>_color) est indexée par CANAL de mixage, et la X32 ne
connaît que le numéro EXP (carte) de chaque préampli. Le lien entre les deux, c'est le patch LV1 — et
AUCUN message OSC ne l'expose (vérifié en lisant le module Companion et en sniffant le flux OSC pendant
des repatchs, cf. lv1/osc_sniffer.py). Exemple réel : canal 19 (stéréo) <- EXP 21 + EXP 22. Supposer
"EXP N -> In N" (comportement de la v1.8.0) affiche alors la couleur d'un AUTRE canal.

SOLUTION RETENUE (depuis le 2026-10-12) : la LV1 écrit son patch EN DIRECT, sans sauvegarde, dans sa base
de travail Sessions/CurrentLV1.dat (SQLite, même schéma qu'un .emo) — un repatch y apparaît ~1 s plus
tard (mesuré). C'est la source par défaut quand elle existe (lv1.session_patch.LIVE_DB), relue à chaque
écriture : la table suit les repatchs sans rien figer.

DEUX SOURCES, combinées :
  1) Table manuelle (dépannage / forçage) : lv1_patch_map.json à côté des scènes, au format
         {"19": [21, 22], "1": [1], "2": 2}       canal LV1 -> numéro(s) EXP
     Les clés commençant par "_" sont ignorées (commentaires). Le JSON produit par
     `python -m lv1.session_patch ... --json` ({"19": {"device": ..., "sources": [21, 22]}}) est aussi
     accepté tel quel, pour pouvoir partir d'une session et corriger à la main.
  2) Automatique : la session LV1 — par défaut la base en direct CurrentLV1.dat, sinon un .emo, ou un
     dossier (le dossier History avec "Auto Save Every X Minutes") dont on relit le .emo le plus récent.
     Pour chaque canal, on prend la source du premier device de `devices` qui l'alimente (défaut :
     X32RACK seul — la carte DN32-WSG de la X32, dont la voie N est l'EXP N côté X32 ; voir
     lv1/session_patch.py pour pourquoi TracksLive n'est pas pris par défaut). Quel que soit le status
     de la route, et en ignorant la voie droite des canaux mono.
  La table manuelle est prioritaire : un canal qu'elle décrit remplace ce que dit la session.

Les deux sont relues à chaud (contrôle toutes les `poll` secondes, sur un thread ; la session n'est
recopiée et relue que si le fichier ou son journal -wal a changé) : rien à relancer.

Jamais de correspondance devinée : un EXP absent de la table n'a pas de canal (pastille neutre).
"""
import json
import os
import sqlite3
import threading
import time

from .channelinfo import display_name
from .session_patch import DEFAULT_DEVICES, LIVE_DB, file_signature, newest_emo, parse_devices, pick_sources, read_session  # noqa: F401 (LIVE_DB re-exporte)
MANUAL_FILENAME = "lv1_patch_map.json"


def parse_manual(data):
    """dict JSON -> {canal (int): [exp (int), ...]}. Lève ValueError sur une entrée incompréhensible
    (mieux vaut refuser le fichier entier et le signaler que d'en appliquer une partie en silence)."""
    if not isinstance(data, dict):
        raise ValueError("le fichier doit contenir un objet JSON {canal: [EXP, ...]}")
    out = {}
    for key, val in data.items():
        if str(key).startswith("_"):
            continue
        try:
            ch = int(key)
        except ValueError:
            raise ValueError("canal %r : doit être un numéro" % key)
        if isinstance(val, dict):          # format de lv1.session_patch --json
            val = val.get("sources", [])
        if isinstance(val, int) and not isinstance(val, bool):
            val = [val]
        if not isinstance(val, list) or not all(isinstance(v, int) and not isinstance(v, bool) for v in val):
            raise ValueError("canal %s : attendu un numéro EXP ou une liste de numéros EXP" % key)
        if ch < 1 or any(v < 1 for v in val):
            raise ValueError("canal %s : les numéros commencent à 1" % key)
        out[ch] = list(val)
    return out


def build_exp_map(channels, ranks=None):
    """{canal: [exp, ...]} -> ({exp: canal}, [exp alimentant plusieurs canaux]). Un même EXP peut
    alimenter plusieurs canaux dans la LV1 : on garde alors le plus petit numéro de canal (choix
    arbitraire mais stable) et on le signale.
    ranks : {canal: rang} optionnel (0 = source la plus fiable). Un EXP déjà placé par un rang meilleur
    n'est pas un conflit : la source moins fiable est simplement écartée (ex. le repli TracksLive en
    entrée B qui annonce encore EXP 8 sur In 9 alors que X32RACK 8 est patché sur In 7)."""
    ranks = ranks or {}
    exp_to_ch, exp_rank, conflicts = {}, {}, set()
    for ch in sorted(channels, key=lambda c: (ranks.get(c, 0), c)):
        r = ranks.get(ch, 0)
        for exp in channels[ch]:
            if exp in exp_to_ch:
                if exp_to_ch[exp] != ch and exp_rank[exp] == r:
                    conflicts.add(exp)
                continue
            exp_to_ch[exp], exp_rank[exp] = ch, r
    return exp_to_ch, sorted(conflicts)


class PatchMap:
    def __init__(self, manual_path=None, session_path=None, devices=DEFAULT_DEVICES, poll=0.5):
        self.manual_path = manual_path
        self.session_path = session_path
        self.devices = parse_devices(devices) if isinstance(devices, str) else (tuple(devices) if devices else None)
        self.poll = poll
        self._manual = {}          # {canal: [exp]}
        self._session = {}         # {canal: [exp]}
        self._session_ranks = {}   # {canal: rang du device retenu dans self.devices}
        self._manual_sig = None    # (mtime, taille) du dernier fichier manuel lu
        self._session_sig = None   # (chemin, signature fichier + -wal) de la derniere session lue
        self._session_file = None
        self.session_read_at = None    # date de la derniere relecture reussie de la session
        self._info = {}                # {canal: {"name", "color"}} lus dans la session (lv1/channelinfo.py)
        self.errors = {}           # "manual" / "session" -> message
        self._exp_to_ch, self._conflicts = {}, []
        self._lock = threading.Lock()
        self.refresh()

    # -- lecture des sources ------------------------------------------------
    def _refresh_manual(self):
        p = self.manual_path
        if not p or not os.path.exists(p):
            changed = bool(self._manual) or "manual" in self.errors
            self._manual, self._manual_sig = {}, None
            self.errors.pop("manual", None)
            return changed
        st = os.stat(p)
        sig = (st.st_mtime, st.st_size)
        if sig == self._manual_sig:
            return False
        self._manual_sig = sig
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                self._manual = parse_manual(json.load(f))
            self.errors.pop("manual", None)
        except (OSError, ValueError) as e:
            # fichier en cours d'édition ou faux : on n'applique RIEN de ce fichier plutôt qu'une
            # ancienne version ou une moitié - signalé dans status()
            self._manual = {}
            self.errors["manual"] = "%s : %s" % (os.path.basename(p), e)
        return True

    def _refresh_session(self):
        sp = self.session_path
        if not sp:
            return False
        f = newest_emo(sp) if os.path.isdir(sp) else (sp if os.path.exists(sp) else None)
        if not f:
            self.errors["session"] = ("LV1 pas (encore) lancée sur ce PC : %s introuvable" % sp if sp == LIVE_DB
                                      else "aucun fichier .emo trouvé : %s" % sp)
            self._session, self._session_sig, self._session_file = {}, None, None
            return True
        sig = (f, file_signature(f))
        if sig == self._session_sig:
            return False
        try:
            routes, info = read_session(f)
            chans = pick_sources(routes, self.devices)
        except (sqlite3.Error, OSError) as e:
            # souvent : copie prise pendant une écriture de la LV1 - on garde le résultat précédent et on
            # réessaie au prochain contrôle (sig non mémorisée)
            self.errors["session"] = "%s illisible pour l'instant (%s)" % (os.path.basename(f), e)
            return False
        self._session_sig, self._session_file = sig, f
        self._session = {ch: list(info["sources"]) for ch, info in chans.items()}
        self._session_ranks = {ch: c.get("rank", 0) for ch, c in chans.items()}
        self._info = info
        self.session_read_at = time.time()
        if self._session:
            self.errors.pop("session", None)
        else:
            self.errors["session"] = ("%s : aucun canal patché depuis %s"
                                      % (os.path.basename(f), ", ".join(self.devices or ("un device",))))
        return True

    def refresh(self):
        """Relit les sources si elles ont changé. Renvoie True si la table a pu changer."""
        with self._lock:
            changed = self._refresh_manual()
            changed = self._refresh_session() or changed
            if changed:
                merged = dict(self._session)
                merged.update(self._manual)   # la table manuelle a le dernier mot, canal par canal
                # rangs : table manuelle (-1) > 1er device de self.devices (0) > suivants
                ranks = {ch: self._session_ranks.get(ch, 0) for ch in self._session}
                ranks.update({ch: -1 for ch in self._manual})
                self._exp_to_ch, self._conflicts = build_exp_map(merged, ranks)
            return changed

    def start(self):
        """Thread de relecture à chaud (démon)."""
        def loop():
            while True:
                time.sleep(self.poll)
                try:
                    self.refresh()
                except Exception as e:   # ne jamais tuer le thread pour un fichier bizarre
                    self.errors["refresh"] = "%s: %s" % (type(e).__name__, e)
        threading.Thread(target=loop, daemon=True, name="lv1-patchmap").start()
        return self

    # -- lecture de la table ------------------------------------------------
    def exp_to_channel(self):
        """{numéro EXP: canal LV1} (copie)."""
        with self._lock:
            return dict(self._exp_to_ch)

    def channel_info(self, channels=None):
        """{canal: {"color", "name", "label"}} d'après la session LV1 (sans Companion), pour les canaux
        demandés (tous si None). Canal absent de la session : couleur inconnue, libellé « In N »."""
        info = self._info
        chans = info.keys() if channels is None else channels
        out = {}
        for ch in chans:
            i = info.get(ch, {})
            out[ch] = {"color": i.get("color"), "name": i.get("name"), "label": display_name(ch, i.get("name"))}
        return out

    def status(self):
        with self._lock:
            return {
                "manual_file": self.manual_path,
                "manual_channels": len(self._manual),
                "session_source": self.session_path,
                "session_file": self._session_file,
                "session_channels": len(self._session),
                "session_read_at": self.session_read_at,
                "live": self._session_file == LIVE_DB,
                "devices": list(self.devices or []),
                "conflicts": list(self._conflicts),
                "errors": dict(self.errors),
            }
