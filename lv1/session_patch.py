#!/usr/bin/env python3
"""
lv1/session_patch.py (ex lv1_session_patch_export.py) — Extrait automatiquement le patch (canal -> sources
physiques) depuis un fichier de session Waves eMotion LV1 (.emo).

DECOUVERTE : un fichier .emo est en réalité une base SQLite. La table `routes`
contient la matrice de patch complète : pour chaque canal de la console
(dst_cluster_type=0, "Input"), elle indique quelle(s) voie(s) d'un périphérique
source (src_cluster_type=10, "Inputs" : les devices du Rack A/B SoundGrid) l'alimentent.

Sens des colonnes, établi sur une vraie session (STUDIO_PAVJS_i5_3570_20261011_231513.emo) :
  - dst_cluster_type_index : canal LV1, 0-based (18 = In 19)
  - dst_section_index      : ENTRÉE A (0) ou B (1) du canal — le sélecteur A/B de la LV1
  - dst_channel_index      : voie gauche/droite d'un canal stéréo
  - src_cluster_type_index : `assign` du device source (table device)
  - src_channel_index      : numéro de voie du device, 0-based
  - status                 : PAS "la route existe" : sur cette session, In 16 à In 19 ont leur entrée
                             A sur X32RACK en status 0 et leur entrée B sur TracksLive-FL en status 1
                             (vraisemblablement l'entrée sélectionnée). On garde donc toutes les routes,
                             quel que soit le status, et on l'affiche à titre indicatif.
Exemple vérifié : In 19 = A : X32RACK 21,22 / B : TracksLive-FL 21,22 — mêmes numéros des deux côtés
sur cette session-là (pas une règle générale, voir plus bas), et cohérent avec l'affichage
LV1 ("EX 21" / "EX 22").

Pour l'appli (lv1/patchmap.py), on choisit pour chaque canal la source d'après une liste de devices par
ordre de priorité, "NOM" ou "NOM:A" / "NOM:B" pour n'accepter ce device que sur une entrée. Défaut :
X32RACK SEUL (la carte DN32-WSG de la X32 : sa voie N est l'EXP N côté X32). TracksLive n'est PAS pris
par défaut : il ne rejoue pas forcément les voies X32 avec les mêmes numéros (vu en live : X32RACK 1
en A d'In 1, mais TracksLive 1 en B d'In 2), et en entrée A c'est une vraie source de lecture (In 65 <-
TracksLive 1,2). L'ajouter (--device X32RACK,TracksLive:B) seulement si ce miroir est garanti.

Usage (session EN DIRECT de la LV1 qui tourne sur ce PC, voir LIVE_DB) :
    python -m lv1.session_patch --live

Usage (un seul fichier, depuis la racine du repo) :
    python -m lv1.session_patch STUDIO_PAVJS_i5_3570.emo                   # toutes les routes, A et B
    python -m lv1.session_patch STUDIO_PAVJS_i5_3570.emo --json out.json   # table canal -> EXP (format lv1_patch_map.json)
    python -m lv1.session_patch STUDIO_PAVJS_i5_3570.emo --device X32RACK,TracksLive:B --json out.json  # + repli TracksLive

Usage (mode surveillance — nécessite "Auto Save Every X Minutes" activé dans
la LV1, qui écrit un nouveau .emo horodaté dans le dossier History à chaque
sauvegarde) : repère tout seul le fichier le plus récent du dossier et
régénère out.json à chaque fois qu'un nouveau fichier apparaît.
    python -m lv1.session_patch --watch-dir "C:\\Users\\Public\\Waves Audio\\eMotion\\History" --json out.json
    python -m lv1.session_patch --watch-dir "...\\History" --json out.json --poll 5
"""

import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

from .channelinfo import read_channel_info
from .layers import read_layers

# La carte SoundGrid de la X32/M32 est reconnue par son MODELE (device.description = "DN32-WSG", vu sur
# une vraie base ; "X-WSG", la carte Waves pour X32, ajoutée sur la foi de son nom commercial, pas encore
# vue dans une base), pas seulement par son nom ("X32RACK" ici, mais chacun peut renommer son appareil) :
# indispensable pour que l'appli marche telle quelle chez quelqu'un d'autre. Recherche par sous-chaîne :
# "X-WSG-1", "X-WSG-2"... (plusieurs cartes dans le rack) sont reconnues aussi.
DEFAULT_DEVICES = ("DN32-WSG", "X-WSG", "X32RACK")
INPUT_NAMES = {0: "A", 1: "B"}

# Base de travail EN DIRECT de la LV1 (même schéma qu'un .emo, en mode WAL). Vérifié en live le
# 2026-10-12 (LV1 V17) : un repatch NON sauvegardé y apparaît ~1 s plus tard (écrit dans
# CurrentLV1.dat-wal), alors que la sauvegarde History faite juste avant ne l'avait pas. C'est le seul
# "retour" du patch canal -> source disponible : aucun message OSC ne le donne.
LIVE_DB = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"),
                       "Waves Audio", "eMotion", "Sessions", "CurrentLV1.dat")


def file_signature(db_path):
    """(mtime, taille) du fichier et de son journal -wal : change à chaque écriture de la LV1, même quand
    seul le journal bouge (cas de CurrentLV1.dat)."""
    sig = []
    for p in (db_path, db_path + "-wal"):
        try:
            st = os.stat(p)
            sig.append((st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append(None)
    return tuple(sig)


def open_copy(db_path):
    """Copie le fichier (+ son journal -wal s'il existe) dans un dossier temporaire et ouvre la copie.
    On n'ouvre JAMAIS directement un fichier de la LV1 : même en lecture seule, SQLite crée des fichiers
    -shm/-wal à côté (constaté dans History) et prendrait des verrous sur la base vivante de la LV1.
    Renvoie (connexion, dossier temporaire à supprimer)."""
    tmp = tempfile.mkdtemp(prefix="lv1_")
    try:
        copy = os.path.join(tmp, "session.emo")
        shutil.copyfile(db_path, copy)
        if os.path.exists(db_path + "-wal"):
            shutil.copyfile(db_path + "-wal", copy + "-wal")
        return sqlite3.connect(copy, timeout=2), tmp
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def load_device_labels(con):
    """assign (= src_cluster_type_index dans `routes`) -> libellé lisible du device source.
    Seuls les devices d'E/S (Rack A/B : IOBox, DAW) sont pris : un serveur SoundGrid (SGS) peut avoir
    le même `assign` qu'un device d'E/S (vu sur une vraie session : SG Server et X32RACK tous deux en
    assign 0) et écrasait alors son libellé."""
    cur = con.cursor()
    cur.execute("""
        SELECT d.assign, d.description, dg.name, dn.name
        FROM device d
        LEFT JOIN device_gender dg ON dg.id = d.device_gender
        LEFT JOIN device_name dn ON dn.mac = d.mac AND dn.gender = d.device_gender
        WHERE d.assign IS NOT NULL AND COALESCE(dg.name, '') NOT IN ('SGS', 'Host')
        ORDER BY d.assign, d.id
    """)
    labels = {}
    for assign, description, gender_name, friendly_name in cur.fetchall():
        label = friendly_name or description or f"device#{assign}"
        if gender_name:
            label = f"{label} ({gender_name})"
        labels.setdefault(assign, (label, description or ""))
    return labels


def load_channel_widths(con):
    """{canal idx 0-based: 1 (mono) ou 2 (stéréo)}, ou {} si la session n'a pas cette info.
    La largeur est chainer.num_inputs de l'objet canal (object.obj_type = 0, obj_index = canal) —
    établi en passant un canal de mono à stéréo dans une LV1 V17 en cours (seul num_inputs 1 -> 2 et
    les plugins M -> S changent). Nécessaire car repasser un canal en mono NE supprime PAS la route de
    sa voie droite dans `routes` (vu : In 17 remis en mono gardait « voie D -> X32RACK 18 »)."""
    try:
        return dict(con.execute("""
            SELECT o.obj_index, ch.num_inputs FROM chainer ch JOIN object o ON o.id = ch.obj_id
            WHERE o.obj_type = 0
        """).fetchall())
    except sqlite3.Error:
        return {}


def extract_routes(db_path):
    """Voir read_session() ; ne renvoie que les routes."""
    return read_session(db_path)[0]


def read_session(db_path):
    """(routes, infos, couche) lus sur UNE copie de la session :
    infos = {canal: {"name", "color"}} (lv1/channelinfo.py) ;
    couche = couches affichées sur la LV1, {"mixer1", "mixer2"} (lv1/layers.py) ;
    routes = {canal LV1 (1-based): [{"input": "A"/"B", "device": libellé, "sources": [voie 1-based, ...],
    "active": bool}, ...]} — toutes les routes vers les canaux, entrées A et B, quel que soit le status
    ("active" = au moins une voie en status 1). Les voies au-delà de la largeur du canal (voie droite
    d'un canal mono, restes d'un ancien patch stéréo) sont ignorées."""
    con, tmp = open_copy(db_path)
    try:
        cur = con.cursor()
        device_labels = load_device_labels(con)
        widths = load_channel_widths(con)
        info = read_channel_info(con)
        layer = read_layers(con)
        cur.execute("""
            SELECT id, dst_cluster_type_index, dst_section_index, dst_channel_index,
                   src_cluster_type_index, src_channel_index, status
            FROM routes
            WHERE dst_cluster_type = 0 AND src_cluster_type = 10
        """)
        rows = cur.fetchall()
    finally:
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)

    # Plusieurs lignes pour la même (canal, entrée, voie) : on garde l'id le plus élevé (la plus récente).
    latest = {}
    for row_id, ch_idx, section, slot, assign, src_idx, status in rows:
        if slot >= widths.get(ch_idx, 2):
            continue
        key = (ch_idx, section, slot)
        if key not in latest or row_id > latest[key][0]:
            latest[key] = (row_id, assign, src_idx, status)

    groups = {}   # (canal, entrée, assign) -> {"input", "device", "sources", "active"}
    for (ch_idx, section, slot), (row_id, assign, src_idx, status) in sorted(latest.items()):
        label, model = device_labels.get(assign, (f"device#{assign}", ""))
        g = groups.setdefault((ch_idx + 1, section, assign), {
            "input": INPUT_NAMES.get(section, str(section)),
            "device": label, "model": model,
            "sources": [], "active": False})
        g["sources"].append(src_idx + 1)
        g["active"] = g["active"] or status == 1

    channels = {}
    for (ch, section, assign), g in sorted(groups.items()):
        channels.setdefault(ch, []).append(g)
    return channels, info, layer


def _matches(spec, group):
    """spec "NOM" ou "NOM:A"/"NOM:B" (NOM = sous-chaîne du nom OU du modèle du device, insensible à la casse)."""
    name, _, inp = spec.partition(":")
    name = name.strip().lower()
    hit = name in group["device"].lower() or name in group.get("model", "").lower()
    return hit and (not inp or inp.strip().upper() == group["input"])


def extract_patch(db_path, devices=DEFAULT_DEVICES):
    """{canal LV1: {"device", "input", "sources"}} : pour chaque canal, la source du premier device de
    `devices` (voir _matches, par ordre de priorité) qui l'alimente, entrée A avant B. Canal absent si
    aucun de ces devices ne l'alimente. devices=None : n'importe quel device, l'entrée active d'abord."""
    return pick_sources(extract_routes(db_path), devices)


def pick_sources(routes, devices=DEFAULT_DEVICES, follow_ab=True):
    """Comme extract_patch(), à partir de routes déjà lues (read_session).
    follow_ab (2.2.0, demande de Joseph) : seule l'entrée SÉLECTIONNÉE (A ou B) de chaque canal compte.
    Établi le 2026-10-12 avec l'enregistreur : chaque bascule A/B d'un canal (et FlipAB, pour tous les
    canaux) réécrit routes.status : 1 sur les routes de l'entrée sélectionnée, 0 (ou 4) sur l'autre.
    Canal sur B (TracksLive, virtual soundcheck) : aucun préampli X32 ne l'alimente -> absent."""
    out = {}
    for ch, groups in routes.items():
        if follow_ab:
            groups = [g for g in groups if g["active"]]
            if not groups:
                continue
        rank = 0
        if devices:
            pick = next(((r, g) for r, d in enumerate(devices) for g in groups if _matches(d, g)), None)
            rank, pick = pick if pick else (0, None)
        else:
            pick = next((g for g in groups if g["active"]), groups[0])
        if pick:
            # rank = position du device retenu dans devices (0 = le plus fiable), utilisé par
            # lv1/patchmap.py pour qu'un repli (TracksLive) ne l'emporte jamais sur X32RACK ailleurs
            out[ch] = {"device": pick["device"], "input": pick["input"], "sources": list(pick["sources"]),
                       "rank": rank}
    return out


def print_routes(routes):
    print(f"{'Canal':>6}  {'Ent.':<4}  {'Device source':<28}  {'Voies (1-based)':<16}  Status")
    print("-" * 72)
    for ch in sorted(routes):
        for g in routes[ch]:
            srcs = ",".join(str(s) for s in g["sources"])
            print(f"{ch:>6}  {g['input']:<4}  {g['device']:<28}  {srcs:<16}  {'actif' if g['active'] else '-'}")


def process_one(path, json_out, devices=DEFAULT_DEVICES):
    print_routes(extract_routes(path))
    if json_out:
        channels = extract_patch(path, devices)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"\n[+] {len(channels)} canaux (devices : {', '.join(devices) if devices else 'tous'}) écrits dans {json_out}")


def newest_emo(folder):
    files = glob.glob(os.path.join(folder, "*.emo"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def watch(folder, json_out, poll_seconds, devices=DEFAULT_DEVICES):
    print(f"[+] Surveillance de {folder} (toutes les {poll_seconds}s)... Ctrl+C pour arrêter.")
    last_seen = None
    while True:
        latest = newest_emo(folder)
        if latest and latest != last_seen:
            print(f"\n[+] Nouveau fichier détecté : {os.path.basename(latest)}")
            try:
                process_one(latest, json_out, devices)
            except sqlite3.Error as e:
                # Le fichier peut être en cours d'écriture par la LV1 au moment où on le lit.
                print(f"[!] Lecture échouée ({e}) — nouvel essai au prochain poll.")
            else:
                last_seen = latest
        time.sleep(poll_seconds)


def parse_devices(text):
    """"X32RACK,TracksLive" -> ("X32RACK", "TracksLive") ; vide -> None (tous les devices)."""
    items = tuple(s.strip() for s in (text or "").split(",") if s.strip())
    return items or None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_file", nargs="?", help="Fichier de session LV1 (.emo)")
    ap.add_argument("--live", action="store_true", help="Lit la session en cours de la LV1 (%s)" % LIVE_DB)
    ap.add_argument("--json", metavar="FILE", help="Écrit aussi la table canal -> EXP dans un fichier JSON")
    ap.add_argument("--watch-dir", metavar="DIR", help="Surveille ce dossier (ex: le dossier History) et régénère --json à chaque nouveau .emo")
    ap.add_argument("--poll", type=int, default=5, help="Intervalle de vérification en secondes pour --watch-dir (défaut: 5)")
    ap.add_argument("--device", metavar="LISTE", default=",".join(DEFAULT_DEVICES),
                    help="Devices à prendre pour --json, par priorité, séparés par des virgules "
                         "(défaut: %(default)s ; vide = tous)")
    args = ap.parse_args()
    devices = parse_devices(args.device)

    if args.live:
        args.session_file = LIVE_DB
    if args.watch_dir:
        watch(args.watch_dir, args.json, args.poll, devices)
    elif args.session_file:
        process_one(args.session_file, args.json, devices)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
