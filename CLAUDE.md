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

## État actuel : v2.1.0 publiée (2026-10-12)

Release : https://github.com/thaleosguest/x32-gain-recall/releases/tag/v2.1.0 (`XM32_Gain_Recall_LV1.exe` + `.sha256`).
PR thaleosguest/x32-gain-recall#4 (v2.1.0) fusionnée dans `main` ; avant : #1, #2 (v2.0.0), #3.
2.1.0 = nom « X/M32 Gain Recall for eMotion LV1 », logo, X-WSG, vue LV1, float qui suit couches et
modes de la LV1, calage par écran, float lié à la LV1 (détails dans les sections plus bas).
Joseph a encore « plein de choses à ajouter » : suite dans une 2.2.0.


- **Plug and play (v2.0.0)** : patch, couleurs ET noms des canaux LV1 sont lus dans la
  base de la LV1 — **Companion n'est plus nécessaire** (facultatif : `--companion [URL]`,
  prioritaire s'il est demandé). Objectif de Joseph : télécharger l'exe, le lancer, c'est tout.
- Couleurs/noms fournis par l'appli principale via `/api/state` (`lv1_channels`), affichés
  dans le float (pastille + « L 15 = EXP 15 » + nom) ET le navigateur (bandeau du haut).
- **Architecture décidée : une seule appli.** Tout ce qui touche la LV1 est dans le
  package `lv1/`, importé par `x32_gain_recall.py` (même `.exe`) :
  - `lv1/patchmap.py` : table EXP → canal LV1, relue à chaud (0,5 s) sur un thread,
    exposée dans `/api/state` (`lv1_map`, état dans `lv1`) ;
  - `lv1/session_patch.py` (ex `lv1_session_patch_export.py`) : lecture des routes
    (sur copie), `python -m lv1.session_patch --live` pour voir le patch actuel ;
  - `lv1/channelinfo.py` : noms + palette des couleurs ;
  - `lv1/companion.py` : interrogation Companion, facultative ;
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
- **Couche affichée (établi le 2026-10-12)** : `surface_property_int` (surface 2 = `eSurface_OVV1`
  « Mixer 1 », 3 = OVV2) ; propriété 12 `eProp_LayersMode` (0 = Factory), 14 `eProp_LayersPage`
  (Factory : 0-3 = Ch 1-16..49-64, 4 = Grp/Fx). Libellés dans `surface_type` / `surface_property_type`.
  Écrit aussitôt, sans sauvegarde. `lv1/layers.py` ; le float suit en vue LV1 (pas le navigateur).
  Mode = `ovv_track_mapping_type` : 0 Factory (≤ 64 canaux), 1 CustomL (pages 0-7 = `ovv_layer`
  surface_type 2 par id, tranches dans `ovv_layer_track`), 4 InptChn (config 80 canaux : pages 0-4 =
  Ch 1-16..65-80), 5 BussChn. `config_info` (track_type 0) = nombre de canaux d'entrée configuré.
- **Mode affiché (panneau « Modes »)** : `ovv_page_data.selected_mode_preset_id` (-> `ovv_modes_presets` :
  1 Home, 2 Setup, 3 SndChk, 4 Edit, 5 Fx, 6 Monitor, 7 Status, 8 Dugan) ; 8 lignes par
  `ovv_track_mode` (surface + mode de couche), une par page, ordre des id. Custom : par page ; couches
  d'entrée : les 8 pages changent ensemble. Float : déplié en SndChk/Setup, replié sinon (`AUTO_OPEN_MODES`).
- **Mixer 2** = surface 3 (`eSurface_OVV2`), mêmes propriétés/tables que Mixer 1 (`read_layers`).
- **Onglet du haut (Mixer 1/2, All, Channel, Show, Patch, Setup) : PAS dans la base** (enregistreur : rien
  pendant les clics). Lu à l'écran (`lv1_tab()` : ligne à 14/1080 de la zone client ; 7 boutons de
  ~4,7 % de largeur, gris (231,231,231), actif bleu (56,201,255)) ; validé sur captures plein écran et
  en direct (LV1 fenêtrée 1728x970), ~15 ms. Lu seulement quand la LV1 est la fenêtre active.
- **Disposition 2.2.0** : languette `TAB_W` à gauche (plus de barre en haut) ; Scènes/Routing dans le
  menu ⋯ (dock en bas à gauche essayé puis retiré à la demande de Joseph), panneau = Toplevel sous le
  float, même z-order. Colonne sans préampli = trou (`HOLE` + `-transparentcolor` : invisible ET
  traversable au clic). Vue LV1 sans nom de canal, repère sur une ligne (sinon potards désalignés).
  Potard = place restante mesurée (`winfo_reqheight`) : 48V toujours visible. Glisser 0,05 dB/px.
  Calage d'avant (`layout` absent) converti : x − TAB_W, y + OLD_TITLE_H.
- Languette : 14 px, fond transparent (HOLE), bloc point/flèche/⋯ au MILIEU de la hauteur (sur le vide
  entre « Gain » et « 48 » de la LV1 ; à 22 px en haut, elle cachait « Preamp/Local »), même position
  replié ou déplié. `layout` 3 ; conversion depuis 2 : x + (22 − 14).
- **Talk Back** : routes `dst_cluster_type = 8` (TalkBack), objet `obj_type 8` (A/B : param 0, comme un
  canal). Clé TALKBACK = -8 dans les tables canal -> sources. Position dans les couches : Masters =
  mode 5 (BussChn) page 4, tranche 5 (`BUS_PAGE_INPUTS`, disposition fixe de la LV1, relevée sur
  capture en 80 canaux) ; Custom : obj_type 8. EXP partagé : le canal d'entrée garde la couleur.
- Méthode « enregistreur » (meilleure que photo/diff manuel) : copie de la base à chaque écriture du
  `-wal` et journal des différences horodaté, pendant que Joseph enchaîne plusieurs manipulations.
- **La LV1 tourne en administrateur** : `SetWindowPos`/`GWLP_HWNDPARENT` relatifs à sa fenêtre →
  accès refusé (5) / paramètre invalide (87). Se placer « juste au-dessus de la LV1 » ne tenait pas
  (un clic dans la LV1 la repassait devant, HWND_TOP refusé à une appli en arrière-plan). Solution
  retenue (`_follow_lv1`, 100 ms) : fenêtre active = LV1 ou float → HWND_TOPMOST ; autre appli active →
  HWND_NOTOPMOST puis juste sous elle ; LV1 réduite → float caché.
- Tests du float : piloter `FloatApp` dans un script (voir harness : `argparse.Namespace(port=…)`) plutôt
  qu'à la souris ; sauvegarder puis remettre `%APPDATA%\X32 Gain Recall\x32_float_config.json`.
- Joseph a déjà testé par erreur un ancien exe resté ouvert : vérifier les processus
  (`Get-CimInstance Win32_Process`, chemin de l'exe) quand un correctif « ne marche pas ».
- Méthode qui marche pour trouver un réglage : photo de toutes les tables de la base (sur copie),
  Joseph change UN réglage dans la LV1, nouvelle photo, diff.

## Schéma `routes` d'un `.emo` / `CurrentLV1.dat` (établi sur données réelles)

- `dst_cluster_type = 0` → canaux ; `dst_cluster_type_index` = canal 0-based (18 = In 19)
- `dst_section_index` = **entrée A (0) ou B (1)** du canal
- `dst_channel_index` = voie G/D d'un canal stéréo
- `src_cluster_type = 10` → devices du Rack A/B SoundGrid ; `src_cluster_type_index`
  = `assign` du device (table `device`, nom via `device_name` par mac + gender) ;
  `src_channel_index` = voie 0-based
- `status` : ni l'existence de la route, ni l'entrée sélectionnée. **Piège (2026-10-12)** : lu une 1re
  fois comme « 1 = entrée sélectionnée » -> float inversé ; en fait 1 sur l'entrée NON sélectionnée
  (0 ou 4 sinon). Ne pas s'en servir.
- **Entrée A/B sélectionnée** = `snapshot_chainer_params` param_id **0** (snapshot -1, chainer = object
  du canal) : 1.0 = B, pas de ligne = A ; réécrit aussitôt (bascule A/B, FlipAB). Vérifié dans les
  deux sens avec captures. `load_input_select()` ; depuis la 2.2.0 `pick_sources(follow_ab=True)` ne
  garde que l'entrée sélectionnée (demande de Joseph ; canal sur B/TracksLive = pas de préampli X32).
- Leçon : un essai « avant/après » ne suffit pas à trancher un sens (on ne connaît pas l'état de
  départ) : toujours demander l'état visible à l'écran à un instant donné et le comparer à la base.
- **Largeur mono/stéréo** : `chainer.num_inputs` (1 ou 2) de l'objet canal
  (`chainer.obj_id = object.id`, `object.obj_type = 0`, `object.obj_index` = canal 0-based).
  Trouvé en comparant la base avant/après un passage mono → stéréo. **Indispensable** :
  repasser un canal en mono laisse sa route de voie droite dans `routes` (bug vu : EXP 18
  coloré comme In 17 au lieu d'In 21). Ignorer `dst_channel_index >= num_inputs`.
- Un serveur SGS peut avoir le même `assign` qu'un device d'E/S : exclure SGS/Host.
- La carte de la X32/M32 est reconnue par son **modèle** `device.description = "DN32-WSG"`
  ou `"X-WSG"` (défaut `--lv1-device DN32-WSG,X-WSG,X32RACK`, sous-chaîne : « X-WSG-1 », « X-WSG-2 »
  aussi). X-WSG ajouté sur la foi de son nom (Joseph n'en a pas pour tester) : pas encore vu dans une base : « X32RACK » n'est que le nom que Joseph a donné
  à l'appareil, il peut être différent chez quelqu'un d'autre.
- Setup réel (portable-js) : **A = X32RACK** (carte DN32-WSG de la X32 : voie N = EXP N),
  B = souvent TracksLive-FL (virtual soundcheck). **Seule la carte X32 compte par défaut** :
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

## Nom et signature (décidés le 2026-10-12, v2.1.0)

- Nom : **X/M32 Gain Recall for eMotion LV1** (`APP_NAME`), court `X/M32 Gain Recall` (`APP_SHORT`),
  signature **by Joseph Savigny** (`APP_AUTHOR`) — dans `x32_gain_recall.py`, repris par le float.
  Pages HTML : jetons `__APP_NAME__`/`__APP_SHORT__`/`__APP_AUTHOR__`/`__APP_VERSION__` (`_brand()`).
- « Tandem » envisagé puis écarté : Joseph veut un nom explicite. Exe : `XM32_Gain_Recall_LV1.exe` (choix de Joseph,
  spécifique LV1). Le dossier `%APPDATA%\X32 Gain Recall` garde l'ancien nom (pas de migration).
- **Logo = piste C « pont »** (choisie le 2026-10-12 parmi potard / potard+rappel / pont / monogramme) :
  bloc gris X/M32 (potard = disque plein + index incliné, PAS vertical : sinon ça lit « marche/arrêt »)
  relié au bloc ambre `#F2B63B` LV1 (vumètre), fond anthracite `#2B2E33`. Pas de teal (= couleur de canal LV1).
  Source unique : `tools/make_icon.py` (Python pur, pas de Pillow sur ce PC) → `assets/logo.svg`,
  `assets/icon.ico` (`--icon` de PyInstaller), `brand_icon.py` (généré : `LOGO_SVG`, `ICON_PNG_B64`).
- Une seule carte X32 par rack LV1 supportée (choix de Joseph) : avec deux cartes (X-WSG-1/-2 = deux
  consoles), la voie N de chacune serait prise pour l'EXP N de la console connectée. Pas traité.

## Données de l'appli (depuis la 2.0.0)

- Par défaut tout est dans `%APPDATA%\X32 Gain Recall` (choix de Joseph : séparé de l'exe) :
  scènes, routings, code d'accès, config du float, `lv1_patch_map.json`, et
  `x32_gain_recall_settings.json` (dossier des scènes choisi + `legacy_migrated`).
- Le dossier des **scènes** (et routings) se choisit dans le navigateur : panneau Scènes →
  « Dossier… » (chemin, ou Parcourir = fenêtre tkinter sur le PC de l'appli). Reprend les scènes
  déjà présentes ou propose d'y copier les actuelles.
- Au 1er lancement, les fichiers des versions ≤ 1.9 rangés à côté de l'exe sont **recopiés**
  (jamais supprimés) dans `%APPDATA%`.
- JSON lus en `utf-8-sig` (fichiers enregistrés par le Bloc-notes avec BOM).
- Une scène ne contient que la X32 (gains, 48V, noms X32) ; rien de la LV1, qui sauvegarde
  sa propre session.

## Fenêtre flottante

- Fond au choix (bouton ◐) : **Anthracite** par défaut (le noir d'origine se confondait avec la
  LV1), Noir, Or, Bleu nuit. Implémenté par correspondance des gris d'origine (`_CANON`) →
  teintes du thème (`apply_theme()` sur tout l'arbre + `tc()` pour les couleurs posées en cours
  de route). Toute nouvelle couleur sombre en dur doit être ajoutée à `_CANON` et aux thèmes.
- Ligne « L 15 = EXP 15 » puis nom LV1 en plus gros ; tout tient sur une ligne dès ~60 px.
- **Vue LV1 (float 2.7.0 / appli 2.1.0, demande de Joseph)** : Joseph pose le float SUR la LV1, entre
  la rangée du haut et les faders, chaque colonne au-dessus de sa tranche LV1. Donc colonne = canal
  LV1 (banques « LV1 Ch 1-16 »…), pas préampli : sinon un EXP non patché (EXP 7) décale tout.
  Stéréo = 2 `Unit` demi-largeur dans un `Strip` ; gains NON liés (regroupement visuel seulement).
  Canal sans préampli X32 = colonne vide (alignement). Préampli retrouvé par EXP (`exp_map` inversée),
  canal → EXP par `lv1_sources` (`PatchMap.channel_sources()`). Vue X32 conservée (choix de Joseph :
  vue au choix, même menu de banques). Navigateur : idem (`.grp`), colonnes stéréo plus larges.
- **Replié** : seulement le point de connexion (= poignée de déplacement) + la flèche (demande de Joseph).
- **Une seule barre** en haut (demande de Joseph) : la barre de connexion s'ouvre SOUS les voies (bouton
  « Console », auto tant que non connecté) pour ne jamais décaler les voies calées sur la LV1.
- **Calage** : `strip_w` = largeur moyenne à virgule ; `_col_widths()` répartit les pixels (somme exacte).
  Profils par résolution dans `x32_float_config.json` (`screens`, `last_screen`) ; écran inconnu = dernier
  profil mis à l'échelle. Écrans de Joseph de tailles différentes : c'est la raison.
- Tester le float : il enregistre sa config dans `%APPDATA%` → la sauvegarder avant et la remettre après.
  Le simulateur (`--sim`) n'a pas d'EXP tant qu'on n'y applique pas le profil « Routing LV1 »
  (`POST /api/routings/apply`).

## Publier une version

1. `APP_VERSION` dans `x32_gain_recall.py` + section dans `CHANGELOG.md`.
2. Fusionner dans `main`, puis tag annoté `vX.Y.Z` (doit égaler `APP_VERSION`) et `git push origin vX.Y.Z`.
3. GitHub Actions (`build.yml`) compile l'exe, lance `--version` et `--help` (normal et `--float`),
   publie la release. `gh workflow run build.yml --ref <branche>` compile une branche **sans**
   publier (artefact « XM32_Gain_Recall_LV1-windows ») : pratique pour faire tester l'exe à Joseph.

## Pièges de ce PC

- `gh` n'est pas dans le PATH : `& "C:\Program Files\GitHub CLI\gh.exe"` (connecté en `thaleosguest`).
- Pas d'identité git globale : commits avec
  `git -c user.name="Claude" -c user.email="thaleosguest@users.noreply.github.com" commit ...`
  (identité de l'historique du repo) ; messages longs via `-F fichier`, pas en argument PowerShell.
- Joseph n'a que `py` (pas `python`) dans son terminal PowerShell : lui donner des commandes `py ...`
  (et `& "chemin"` pour lancer un exe dont le chemin est entre guillemets).
- `gh auth login` ne marche pas dans le panneau Terminal de l'app : le faire dans une vraie
  fenêtre PowerShell.
- argparse : un `%` dans un `help=` doit être écrit `%%` (sinon l'appli plante au démarrage).

## Reste à faire / idées

- Rien de bloquant. À revérifier après une mise à jour de la LV1 : écriture en direct de
  `CurrentLV1.dat`, paramètre couleur 592 et palette.
- Le choix du dossier des scènes n'existe que dans le navigateur (pas dans le float).
- À revérifier aussi après une mise à jour LV1 : couches / modes (`lv1/layers.py`).
- Non traité : deux cartes X32 dans le même rack (deux consoles) ; vue « Mixer 2 » (surface 3) non suivie.

## Environnement cible

- PC hôte : laptop "portable-js" (i7-8750H, 16 Go RAM, Windows 10 IoT
  Enterprise LTSC 2021) ou tour i5-3570K — hôtes dédiés LV1.
- LV1 V17.
- Toolbox Reaper annexe (ReaScript) déjà existante pour l'intégration LV1,
  sans lien direct avec ce projet mais dans le même écosystème studio.
