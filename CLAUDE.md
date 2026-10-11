# x32-gain-recall — contexte projet

> Ce fichier est destiné à Claude Code, exécuté en local sur le PC de Joseph.
> Il résume l'état du projet et les décisions déjà prises, pour éviter de refaire
> les recherches déjà faites dans une discussion précédente (hors Claude Code).

## Objectif du projet

Outil de rappel de gains X32 / Waves eMotion LV1, avec une fenêtre flottante qui
affiche en direct l'état des canaux (y compris leur couleur telle que définie
dans la LV1). L'app tourne sur le PC qui héberge aussi `x32_gain_recall.py`
pendant les prestations.

Repo : `https://github.com/thaleosguest/x32-gain-recall.git`
Workspace local : `C:\Users\Joseph\Documents\x32-gain-recall-workspace`

## État actuel (v1.9.0 — PR thaleosguest/x32-gain-recall#2)

- La pastille de couleur par voie du float lit les couleurs via l'API HTTP du
  module Companion Waves LV1 (`in<N>_color`). Companion tourne en continu sur le
  PC pendant les prestations.
- **Architecture décidée : une seule appli.** Tout ce qui touche la LV1 est dans le
  package `lv1/`, importé par `x32_gain_recall.py` (même `.exe`) :
  - `lv1/patchmap.py` : table EXP → canal LV1, relue à chaud sur un thread,
    exposée dans `/api/state` (`lv1_map`, état dans `lv1`) ;
  - `lv1/session_patch.py` (ex `lv1_session_patch_export.py`) : lecture des routes ;
  - `lv1/osc_sniffer.py` (ex `lv1_osc_sniffer.py`) : diagnostic uniquement.
- Le float cherche la couleur du canal LV1 qui reçoit l'EXP de chaque préampli
  (EXP lu en direct sur la X32 via `exp_map`). Un EXP sur aucun canal reste gris :
  jamais de « EXP N → In N » supposé (c'était le bug de la 1.8.0 : EXP 1 → In 2 en réalité).

## Patch canal → source : PAS d'OSC, mais un fichier écrit en direct

- La couleur LV1 est indexée **par canal** (`in19_color`), pas par source.
- **Aucun message OSC de patch n'existe** (code du module Companion lu en entier +
  sniff OSC pendant des repatchs réels). Ne pas rechercher de nouveau par là.
- **Découverte du 2026-10-12** : la LV1 écrit son patch en continu, **sans
  sauvegarde**, dans sa base de travail
  `C:\Users\Public\Waves Audio\eMotion\Sessions\CurrentLV1.dat` (SQLite, même
  schéma qu'un `.emo`, mode WAL). Mesuré sur LV1 V17 : un repatch y apparaît
  ~1 s plus tard (écrit dans `CurrentLV1.dat-wal`), alors que la sauvegarde
  `History` faite juste avant ne l'avait pas. **C'est la source par défaut de l'appli.**
  Comportement interne non documenté par Waves : à revérifier après une mise à jour LV1.
- Ne **jamais** ouvrir directement un fichier de la LV1, même en `mode=ro` : SQLite
  crée des `-shm`/`-wal` à côté et prend des verrous. Toujours lire une copie
  (fichier + `-wal`), comme `session_patch.open_copy()`.
- Secours : table manuelle `lv1_patch_map.json` (prioritaire), `--lv1-session`
  (autre `.emo` ou dossier `History`), `--lv1-sans-session`.

## Schéma `routes` d'un `.emo` / `CurrentLV1.dat` (établi sur données réelles)

- `dst_cluster_type = 0` → canaux ; `dst_cluster_type_index` = canal 0-based (18 = In 19)
- `dst_section_index` = **entrée A (0) ou B (1)** du canal
- `dst_channel_index` = voie G/D d'un canal stéréo
- `src_cluster_type = 10` → devices du Rack A/B SoundGrid ; `src_cluster_type_index`
  = `assign` du device (table `device`, nom via `device_name` par mac + gender) ;
  `src_channel_index` = voie 0-based
- `status` : **pas** l'existence de la route — semble indiquer l'entrée sélectionnée
  (routes A X32RACK en 0 quand B est active). Ne pas filtrer dessus.
- Un serveur SGS peut avoir le même `assign` qu'un device d'E/S : exclure SGS/Host.
- Setup réel (portable-js) : **A = X32RACK** (carte DN32-WSG de la X32 : voie N = EXP N),
  **B = TracksLive-FL** avec les mêmes numéros (virtual soundcheck). TracksLive en
  entrée A = vraie source de lecture (ex. In 65 ← TracksLive 1,2), à ignorer.
  D'où le défaut `--lv1-device X32RACK,TracksLive:B`.

## Reste à faire / à vérifier

- Tester les couleurs avec le vrai Companion en prestation, et un `.exe` compilé
  (PyInstaller doit embarquer `lv1/`, import statique : a priori OK).
- In 2 à In 15 n'avaient que TracksLive en B, sans route X32RACK en A, dans la session
  observée : à confirmer avec Joseph que c'est voulu.
## Environnement cible

- PC hôte : laptop "portable-js" (i7-8750H, 16 Go RAM, Windows 10 IoT
  Enterprise LTSC 2021) ou tour i5-3570K — hôtes dédiés LV1.
- LV1 V17.
- Toolbox Reaper annexe (ReaScript) déjà existante pour l'intégration LV1,
  sans lien direct avec ce projet mais dans le même écosystème studio.
