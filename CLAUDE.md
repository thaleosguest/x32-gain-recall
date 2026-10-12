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

## État actuel (v2.0.0 — PR thaleosguest/x32-gain-recall#2, pas encore fusionnée)

- **Plug and play (v2.0.0)** : patch, couleurs ET noms des canaux LV1 sont lus dans la
  base de la LV1 — **Companion n'est plus nécessaire** (facultatif : `--companion [URL]`,
  prioritaire s'il est demandé). Objectif de Joseph : télécharger l'exe, le lancer, c'est tout.
- Couleurs/noms fournis par l'appli principale via `/api/state` (`lv1_channels`), affichés
  dans le float (pastille + « L 15 = EXP 15 » + nom) ET le navigateur (bandeau du haut).
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

## Nom et couleur des canaux dans la base LV1 (établi le 2026-10-12, LV1 V17)

- Nom : `snapshot_chainer.name` (`snapshot_id = -1` = état courant), `chainer_id = object.id`
  (`object.obj_type = 0`, `obj_index` = canal 0-based). Nom par défaut « Channel N » → affiché « In N ».
- Couleur : `snapshot_chainer_params.param_value` pour `param_id = 592` (`snapshot_id = -1`) =
  **numéro dans la palette fixe de 32 couleurs** (`lv1/channelinfo.py`). Pas de ligne = n° 13
  (teal `#0FA2AB`, couleur par défaut). Palette relevée en donnant les 32 couleurs aux canaux
  In 33-64 et en lisant Companion ; vérifiée identique à Companion sur 64/64 canaux.
- Companion n'expose que In 1-64 ; la base donne aussi In 65-80.
- Méthode qui marche pour trouver un réglage : photo de toutes les tables de la base (sur copie),
  Joseph change UN réglage dans la LV1, nouvelle photo, diff.

## Schéma `routes` d'un `.emo` / `CurrentLV1.dat` (établi sur données réelles)

- `dst_cluster_type = 0` → canaux ; `dst_cluster_type_index` = canal 0-based (18 = In 19)
- `dst_section_index` = **entrée A (0) ou B (1)** du canal
- `dst_channel_index` = voie G/D d'un canal stéréo
- `src_cluster_type = 10` → devices du Rack A/B SoundGrid ; `src_cluster_type_index`
  = `assign` du device (table `device`, nom via `device_name` par mac + gender) ;
  `src_channel_index` = voie 0-based
- `status` : **pas** l'existence de la route — semble indiquer l'entrée sélectionnée
  (routes A X32RACK en 0 quand B est active). Ne pas filtrer dessus.
- **Largeur mono/stéréo** : `chainer.num_inputs` (1 ou 2) de l'objet canal
  (`chainer.obj_id = object.id`, `object.obj_type = 0`, `object.obj_index` = canal 0-based).
  Trouvé en comparant la base avant/après un passage mono → stéréo. **Indispensable** :
  repasser un canal en mono laisse sa route de voie droite dans `routes` (bug vu : EXP 18
  coloré comme In 17 au lieu d'In 21). Ignorer `dst_channel_index >= num_inputs`.
- Un serveur SGS peut avoir le même `assign` qu'un device d'E/S : exclure SGS/Host.
- Setup réel (portable-js) : **A = X32RACK** (carte DN32-WSG de la X32 : voie N = EXP N),
  B = souvent TracksLive-FL (virtual soundcheck). **Seul X32RACK compte par défaut** :
  TracksLive n'est PAS un miroir fiable des numéros X32 (vu : X32RACK 1 sur In 1 mais
  TracksLive 1 sur In 2), et en entrée A c'est une vraie source de lecture (In 65 ←
  TracksLive 1,2). Repli possible : `--lv1-device X32RACK,TracksLive:B`, avec un rang
  global (un repli ne l'emporte jamais sur une route X32RACK d'un autre canal).
- Souhait explicite de Joseph : une entrée X32 qui n'arrive (plus) sur aucun canal LV1
  doit rester **sans couleur** — jamais deviner.
- **Décision de Joseph (2026-10-12)** : un EXP qui alimente plusieurs canaux LV1 (ex. EXP 5
  sur In 5 et sur In 6 stéréo « Bass ») prend le canal **au plus petit numéro**. Ne pas changer
  (options écartées : afficher les deux noms, ou priorité au canal stéréo).
- Le navigateur doit redessiner aussi quand seul le côté LV1 change : la page compare
  `exp_map`/`lv1_map`/`lv1_channels`, pas seulement `rev` (qui ne suit que la X32).

## Reste à faire / à vérifier

- Couleurs vues fonctionner avec le vrai Companion (capture de Joseph). Reste : revérifier
  EXP 18 après le correctif mono, puis fusionner la PR #2, tagger `v1.9.0` (le tag doit
  égaler `APP_VERSION`) et vérifier le build `.exe` (PyInstaller doit embarquer `lv1/`,
  import statique : a priori OK).
- Joseph n'a que `py` (pas `python`) dans son terminal PowerShell : lui donner des
  commandes `py ...`.
## Environnement cible

- PC hôte : laptop "portable-js" (i7-8750H, 16 Go RAM, Windows 10 IoT
  Enterprise LTSC 2021) ou tour i5-3570K — hôtes dédiés LV1.
- LV1 V17.
- Toolbox Reaper annexe (ReaScript) déjà existante pour l'intégration LV1,
  sans lien direct avec ce projet mais dans le même écosystème studio.
