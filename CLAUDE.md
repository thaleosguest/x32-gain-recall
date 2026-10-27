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

## État actuel : v3.1.0 publiée (2026-10-20)

Release : https://github.com/thaleosguest/x32-gain-recall/releases/tag/v3.1.0 ; PR #15 (dev-3.1, fusionnée par Joseph),
tag v3.1.0 posé sur main. 3.1.0 = STAGE PATCH (patch map + faces des boîtiers, feuilles + export / import, renommage
automatique et couleurs par clics des canaux LV1) + exe en administrateur (Lancer avec Windows = tâche planifiée).
Détails : sections « PATCH MAP » et « PATCH DE SCÈNE ».

### Avant : v3.0.1 (2026-10-16)

Release : https://github.com/thaleosguest/x32-gain-recall/releases/tag/v3.0.1 ; PR #13 (v3.0.0) puis PR 3.0.1.

3.0.1 (branche `dev-3.0`) : plus de navigateur au lancement (`--browser` pour l'ouvrir ; `show_app` = float seul),
tuile « X32 Routing » sur la page Patch (`PatchButton`, `PATCH_BOX` 1782,110 96x96 /1920x1080, style des tuiles
d'appareils : bandeau (68,138,255), contour 160 / 56,201,255), panneau Routing en boutons texte + routing actif
(`remember_routing` / `routing_active` par IP dans les settings, `consoles[].routing_active`), z-order : autre
appli active -> `place_bottom` (HWND_BOTTOM) au lieu de « sous l'appli active » (float vu au-dessus de Reaper),
`SetWinEventHook` (fenêtre active, réduction) -> `follow_lv1` immédiat, `raise_now` à l'ouverture des menus /
panneaux, `TOOL_TAP_PX` 28.
Puis (même 3.0.1) : z-order corrigé = **juste au-dessus de la LV1** quand une autre appli est active
(`_window_above` : 1re fenêtre visible non topmost au-dessus de la LV1 via GW_HWNDPREV, `place_after` dessous ;
HWND_BOTTOM cachait les gains dès qu'une appli était devant, vérifié chez Joseph avec Reaper) ; lecture d'écran
à deux vitesses (`TAB_EVERY` 60 ms pour l'onglet, `FULL_EVERY` 300 ms, signal `_Poke` -> `follow_lv1`) ;
**i18n** : `x32_i18n.py` (`T()`, dictionnaire FR -> EN, anglais par défaut, `settings["lang"]`, `/api/lang`,
`snap["lang"]`) ; textes entourés de `T()` par script AST (attention : un nouveau texte d'interface doit passer
par `T()` et être ajouté à `EN`) ; page web PAS encore traduite ; bouton « X32 Gains » page Show (`ShowButton`,
`SHOW_BOX` 17,884 92x54) ; message de démarrage (`Toast`, bas à droite, une fois).

Release : https://github.com/thaleosguest/x32-gain-recall/releases/tag/v3.0.0 (`XM32_Gain_Recall_LV1.exe` + `.sha256`).
Branche `dev-3.0` ; avant : #12 (v2.7.1), #11 (v2.7.0), #9 (v2.6.0), #8 (v2.5.0)...
3.0.0 = float réécrit en Qt (multi-touch), calé au pixel, fixe, suit la section Input (Top/Middle/Bottom),
languette dans la barre du haut, menu maison, panneaux tactiles. **Mono-écran** (choix de Joseph, « LV1
classique ») : pages détachées sur un 2e écran NON prises en charge en 3.0 (code gardé, non garanti). Float tk
en secours : `--tk-float` (et automatique si PySide6 ne se charge pas). Joseph : « en vrai c'est une v1 » —
il reste des choses à régler. Détails : section « v3 en Qt ».
2.7.0 = look du float (potards lisses, arc à la couleur du canal LV1, 48V rouge), croix du panneau Scènes gardée
après un chargement + croix de la barre Console, « Lancer avec Windows » plus réécrit tout seul (Defender).
2.6.0 = plusieurs consoles (une carte LV1 chacune : float, routing par console, scènes multi-consoles, panneau
⋮ → Consoles…), profils M32C + X32 stage box (AES50 A / B), panneau du float fermé par ✕ seulement.
2.5.0 = pages détachées (un float par Mixer détaché, onglets lus avec la liste réduite), page Channel (canal lu à
l'écran, chiffres relevés par taille, vérifié contre le patch), 48V au style du float, bulle des dB, lectures
d'écran sur un fil à part (potards fluides). Ressources mesurées : ~0,3 % CPU de la machine, ~100 Mo en tout.
2.4.0 = routing : profils X32R + S16 A + S16 B et M32C + S16 A + S16 B, éditeur libre (page + float) en
matrice avec aide à la visée ou en listes ; float plus tactile (⋮, menu 13 pt, panneau fermé par ✕ ou en
touchant la LV1) (détails : section « Routing (2.4.0) »).
2.3.0 = plug and play : mode d'emploi (`MODE_EMPLOI.md`), float ouvert et calé tout seul, 1re connexion
automatique + reconnexion, navigateur réduit, LV1 au premier plan, pas de code sur le PC, icône près de
l'horloge (exe sans console), une seule instance, Lancer avec Windows, float caché LV1 fermée, tranche
sélectionnée en mode Edit, avis de mise à jour (détails : section « Démarrage, plug and play »).
2.1.0 = nom « X/M32 Gain Recall for eMotion LV1 », logo, X-WSG, vue LV1, float qui suit couches et
modes de la LV1, calage par écran, float lié à la LV1.
2.2.0 = float intégré à la LV1 : languette à gauche (plus de barre), caché hors Mixer 1/2 (onglet lu à
l'écran), Mixer 2, colonnes sans préampli transparentes, flip A/B, Talk Back, couches des 4
configurations (16/32/64/80), mono/stéréo harmonisés (détails dans les sections plus bas).
Nommer les branches `dev-X.Y` (pas `vX.Y.Z` : même nom que le tag -> `git push` ambigu, vu en 2.1.0).


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
- **Sections Top / Middle / Bottom + Big Fader (relevé 2026-10-14)** : `ovv_page_data` (une ligne par page, comme le
  mode) a `section_mapping_type_top_bay` / `_middle_bay` / `_bottom_bay` et `big_faders` ; valeurs par défaut de
  chaque mode dans les mêmes colonnes de `ovv_modes_presets` ; libellés dans `ovv_section_mapping_type` (0 Input,
  1 DynEQ, 2 Rack, 3 RouteGrp, 4 RouteMain, 5 Fx_1_8, 6 Mon_1_8, 7 Mon_9_16, 8 Channel, 9 Dugan, 10 Aux_1_16,
  11 Aux_9_24, 12 Mon_17_24, 13 IEM, 14 Fader). Ex. Home = top Rack, middle Input, bottom Fader, big faders.
  **Écrits en direct** (enregistreur, < 1 s, chaque réglage seul). La LV1 échange les sections entre rangées.
  **Big Fader masque Middle et Bottom** (seul Top reste) ; **faders (14) en Middle = débordent sur le Bottom** et y
  cachent les cadres Preamp (seuls Polarity / Trim visibles). Cadres Preamp : y 184..315 en Top, **505..636 en
  Middle**, **781..912 en Bottom** (mêmes x). `lv1/layers.py` : `bays` (top, middle, bottom, big) + `input_bay`
  ("top" / "middle" / "bottom" / None) + `input_covered` (Bottom sous des faders en Middle : rails jusqu'à y 892) ;
  float Qt : déplié aussi dans ce cas, posé sur les cadres du bas par-dessus le bas des faders (choix de Joseph) ;
  float Qt : déplié quand `input_bay` existe (au lieu de SndChk/Setup), calé sur `BAY_Y0[input_bay]`.
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
- **Configurations 16/32/64/80 (relevé complet 2026-10-12)** : 16, 32, 64 -> mode Factory (0), mêmes 8
  pages (0-3 Ch 1-16..49-64, 4 Grp/Fx, 5 Monitor, 6 Masters, 7 Link DCA) ; 80 -> modes InptChn (4,
  pages 0-4) et BussChn (5 : Groups, Fx, Mon 1-16, Mon 17-24, Masters, Link DCA). `config_info` (track_type
  = cluster_type) donne le nombre configuré (0 Input : 16/32/64/80, 1 Group, 25 Mon...), pas utile
  pour le float : le mode suffit. Après retour en 80, la LV1 peut rester en mode 0 jusqu'au prochain clic.
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
- Plusieurs cartes / consoles : traité le 2026-10-14 (voir « Plusieurs consoles »).

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
- Une scène ne contient que les consoles (gains, 48V, noms ; toutes les consoles connectées depuis la 2.6.0) ;
  rien de la LV1, qui sauvegarde sa propre session.

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
- Pas de barre en haut depuis la 2.2.0 (languette à gauche) ; la barre de connexion s'ouvre SOUS les voies
  (⋮ → Console, auto tant que non connecté) pour ne jamais décaler les voies calées sur la LV1.
- **Calage manuel** (depuis la 2.3.0 le calage est automatique, `auto_place`) : `strip_w` = largeur moyenne à virgule ; `_col_widths()` répartit les pixels (somme exacte).
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

- **Defender (2026-10-14)** : `Behavior:Win32/Persistence.A!ml` sur l'exe téléchargé de la CI = l'appli réécrivait
  d'elle-même la clé Run (exe déplacé) ; Defender a bloqué l'exe ET effacé la valeur. Corrigé en 2.7.0 (plus de
  réécriture automatique). Ne jamais réécrire la clé Run sans action de l'utilisateur.
- Compiler en local marche (PyInstaller installé dans le Python 3.15 de Joseph) : `--distpath`/`--workpath`/
  `--specpath` dans le scratchpad, `--icon` en chemin ABSOLU (sinon cherché relatif au specpath). Exe de test
  copié dans `dist\<version>-test` (ignoré par git) ; un exe en cours d'exécution est verrouillé -> autre dossier.

- `gh` n'est pas dans le PATH : `& "C:\Program Files\GitHub CLI\gh.exe"` (connecté en `thaleosguest`).
- Pas d'identité git globale : commits avec
  `git -c user.name="Claude" -c user.email="thaleosguest@users.noreply.github.com" commit ...`
  (identité de l'historique du repo) ; messages longs via `-F fichier`, pas en argument PowerShell.
- Joseph n'a que `py` (pas `python`) dans son terminal PowerShell : lui donner des commandes `py ...`
  (et `& "chemin"` pour lancer un exe dont le chemin est entre guillemets).
- `gh auth login` ne marche pas dans le panneau Terminal de l'app : le faire dans une vraie
  fenêtre PowerShell.
- argparse : un `%` dans un `help=` doit être écrit `%%` (sinon l'appli plante au démarrage).

## Démarrage, plug and play (2.3.0)

- Au lancement : navigateur ouvert puis **réduit** (`_push_browser_back` : toute fenêtre dont le titre
  contient `APP_NAME`, après 0,8 s, surveillée 4 s — Brave remet au premier plan une fenêtre réduite trop
  tôt), puis float (`launch_float_window`, un seul par clé : `FLOAT_PROCS["main"]`, + un par Mixer détaché). Reconnexion à `last_ip`
  (settings). Pas de code d'accès pour 127.0.0.1/::1 SI le Host est dans `ALLOWED_HOSTS` (anti
  DNS-rebinding). Serveur fermé : le float quitte (port refusé ~4 s), l'onglet fait `window.close()`.
- **LV1 au premier plan au démarrage** : c'est le float (`--lv1-front`, option cachée passée par
  `_startup_windows`) qui fait `SetForegroundWindow(LV1)`, car il a le premier plan en s'ouvrant. Essayé
  depuis le serveur (même avec `AttachThreadInput`) : refusé par Windows (serveur en arrière-plan).
  Test réaliste = lancer via `explorer.exe fichier.bat` (sinon le processus hérite des droits de Claude).
- Arrêter un serveur de test par sa ligne de commande (`*8091*`) tue aussi le shell dont la commande
  contient ce texte : filtrer sur `x32_gain_recall.py --web-port`.
- **Tranche sélectionnée (mode Edit)** : PAS dans la base (enregistreur : aucune écriture pendant 3
  sélections). Lue à l'écran (`lv1_selected_column`) : fond (120,120,120) de la zone de fader de la tranche
  sélectionnée (autres : 17), lignes 800/880/960 sur 1080, 1re tranche x=143/1920, pas 96, largeur 92 ;
  ~5 ms. Réglage posé dans le cadre vide du bloc Input (`SEL_BOX` : x 32, y 183, 92x133 sur 1920x1080),
  fenêtre `sel_win` du float. Canal -> colonne par `lv1_layers[surface].channels`.
- **Calage auto du float** (`auto_place`, défaut) : `AUTO_X0/Y0` = 142/1920, 184/1080, pas 96/1920, hauteur
  133/1080 (cadres vides des tranches en SndChk ; Setup a la même section du haut, type 0 dans
  `ovv_modes_presets`). Mesuré = calage manuel de Joseph au pixel près. Geste manuel -> `auto_place` False.
- **1re connexion** : `_first_connect()` (pas de `last_ip`) : `scan_network()` toutes les 10 s / 2 min, une
  seule console -> connexion + `remember_console`. Testé avec la X32 de Joseph (X32RACK-JS, 192.168.1.201).
- **Sans console (2.3.0)** : PyInstaller `--noconsole` ; `tray.py` = icône de notification en ctypes pur
  (Shell_NotifyIconW, fenêtre cachée + boucle de messages sur son thread). Journal : `redirect_output_to_log`
  (après le test « déjà lancé », sinon un 2e lancement vide le journal du 1er). Quitter : `quit_app()`
  (SERVER.shutdown + float terminé) ; `/api/quit`, `/api/autostart`, `/api/show` réservés à 127.0.0.1.
  Instance unique : `already_running()` POST `/api/show` sur le port, en-tête `Server: X32GainRecall`.
  CI : exe fenêtré -> `Start-Process -Wait -PassThru` + code de sortie (PowerShell n'attend pas sinon).
- **Lancer avec Windows** : HKCU `...\CurrentVersion\Run`, valeur « XM32 Gain Recall LV1 » = `"exe" --at-login`
  (exe seulement) ; `--at-login` = pas de navigateur + float `--wait-lv1` (caché tant que pas de LV1).
- **Avis de mise à jour** : `check_update()` (GitHub API `releases/latest`, User-Agent obligatoire), au lancement +5 s
  puis toutes les 24 h ; `UPDATE` -> `/api/state.update`, entrée de l'icône (libellé fonction ; None = masquée),
  bulle `TrayIcon.notify`, menu ⋯ du float, lien `#bupd` de la page. Test : forcer `APP_VERSION = "2.1.0"`.
- Captures d'écran sans Pillow : BitBlt + PNG en Python pur (script `grab.py` refait dans le scratchpad).
- Tests : l'exe de Joseph tourne souvent sur 8032 (et prend le port 10023 du simulateur) → tester sur
  `--web-port 8091` sans `--sim`, avec `APPDATA` temporaire.

## Routing (2.4.0)

- L'appli lit/écrit TOUT le routing X32 par OSC (`/node` pour lire, `/` pour écrire) : `/config/routing/*`
  (blocs IN, AES50A/B, CARD, OUT, PLAY), `/config/userrout/in` (32) et `/out` (48), `/outputs/*`.
- Console de Joseph (relevé 2026-10-13) = « Routing LV1 » à l'identique : User In 1-16 = Local 1-16, 17-32 =
  A 1-16 ; CARD = User In 1-32 (EXP n = User In n) ; User Out 1-16 = Carte 1-16 ; X32R OUT 1-16 et AES50 A
  1-16 = User Out 1-16. Sa S16 a son sélecteur de sorties sur 9-16 -> sort EXP 9-16 (X32R sort EXP 1-8).
- Éditeur : modèle `{"in": 32 valeurs (source de EXP n), "out": 48 (X32 OUT 1-16, AES50 A 1-16, AES50 B
  1-16)}` en valeurs de patch utilisateur (`_user_name`, 129-160 = retours EXP). `routing_nodes_from_model`
  : blocs fixes `ROUT_FIXED` (OUT = UOUT1-16, AES50A = UOUT17-32, AES50B = UOUT33-48, voies 17-48 répétées).
  `routing_model_from_nodes` (via `port_names`, `name_to_value`) : conversion fidèle de n'importe quel profil
  ou de la console (vérifié sur « Routing LV1 »). Profils intégrés en modèle : `_builtin_models()`,
  ajoutés une fois chacun (`seeded_keys` dans x32_routings.json). Choix de Joseph : sorties S16 doublées
  sur les voies 1-8 ET 9-16 (sélecteur indifférent) ; éditeur libre (pas d'exceptions), page ET float.

- (Historique) Panneau du float fermé en touchant ailleurs : `GetAsyncKeyState` ne voit PAS les clics sur la LV1
  (administrateur) ; essayé ensuite « la fenêtre active change d'appli » (`_watch_outside`) : RETIRÉ en 2.6.0, il
  fermait le panneau pendant la saisie au clavier tactile. Aujourd'hui : croix ✕ seulement.

## Mixer détaché (2026-10-14)

- LV1 V17 : une page détachée = fenêtre top-level du même processus, titre = nom de la page en majuscules
  (relevés : **« MIXER1 »**, **« MIXER2 »**, **« CHANNEL »**). Joseph : jamais plus de 4 pages détachées.
  Avec les deux Mixers détachés, la fenêtre principale n'a plus que « All, Show, Patch, Setup » (vérifié) :
  son float reste caché, chaque Mixer a le sien. Mixer détaché : même disposition que la page
  Mixer (mêmes fractions AUTO_*/SEL_*/SEL_ROWS), une seule touche d'onglet. La fenêtre principale perd les
  onglets détachés (vu : « Mixer 1, All, Show, Patch, Setup » avec Mixer 2 + Channel détachés) ->
  `lv1_tab(hwnd, names)` avec la liste réduite (`_detached_now` = toutes les pages détachées). Relevé : écran 1 fenêtre principale 1728x970, écran 2
  MIXER2 1728x972 (bureau virtuel 3840x1080).
- `lv1_windows()` -> {"main", "MIXER1", "MIXER2"}. Serveur : `_watch_detached_mixers()` (2 s) lance un float
  `--lv1-window MIXER2` par fenêtre détachée (`FLOAT_PROCS[clé]`) ; ce float a une surface fixe, ne lit pas
  d'onglet, se ferme 4 s après la disparition de sa fenêtre, config `x32_float_config_MIXER2.json`.

## Page Channel et sélection (2026-10-14)

- Canal affiché par la page Channel : PAS dans la base (surfaces 0-5 : Common, Setup, OVV1, OVV2, FIT, OVVAll ;
  aucune propriété de sélection), PAS dans l'accessibilité Windows (UIA : 5 panneaux vides, interface dessinée).
- 1er essai (écarté par Joseph) : apprendre la case « canal sélectionné » sur une page Mixer -> avec « > » on
  tombe sur un canal jamais vu, plus d'accès au préampli.
- Solution retenue : **lecture des chiffres à l'écran** (`lv1_channel_page`, fil `_screen_reader`) :
  « Channel N: » (bandeau du bas, texte (17,17,17) sur la couleur du canal, `CH_REG_BAS`) et « … EXP N »
  (source, texte clair, `CH_REG_SRC`). Découpe en caractères (masque strict : sépare les chiffres collés),
  image en gris normalisée 8x12, comparée aux modèles de `lv1/digits.py` PAR TAILLE d'interface
  (`ui_scale_key` = min(w/1920, h/1080) x 100 : 100 et 90 relevés le 2026-10-14 en faisant défiler les canaux
  1→12/23 avec « > ») ; un chiffre n'est retenu que s'il est quasi identique (écart ≤ 3/96, 2e ≥ +6) : d'une
  taille à l'autre la LV1 dessine autrement (testé : inutilisable). `_resolve_channel` : canal+EXP lus ->
  EXP ∈ sources(canal) ; un seul lu -> patch + couleur du bandeau (exacte) ; sinon rien. Chiffres manquants
  appris (`x32_digits_learned.json`) quand l'autre numéro est lu (ex. « 8 » d'EXP 18 en fenêtre). Testé :
  canaux 1→24 et retour, tous justes (14/15 sans X32 : vides).
- Tranche sélectionnée sur une page Mixer : **liseré jaune pur (255,242,0)** en haut de sa case de source
  (y 100/1080, tous les modes ; canaux jaunes = (243,250,29)) -> `lv1_selected_column_top` (cadre Edit).
- Captures d'écran : 15-45 ms CHACUNE (GDI) -> une seule capture par lecture (`screen_rows`, `screen_bytes`),
  sur le fil `_screen_reader`, suspendu pendant un glisser de potard (`_dragging`) : c'était la cause des
  « potards moins précis ». Zone Channel `CH_BOX` (7..213/1728, 27 %..52 %).
- `PreampBox` (cadre Edit + cadre Channel), `confirm_float` (48V), `ValuePop` (bulle des dB au glisser, se place
  une fois puis ne change que le chiffre ; option `value_pop` du menu ⋮).

## X32 en stage box d'une Core (2026-10-14)

- X32 pleine taille reliée en AES50 A à une X32/M32 Core (carte DN32-WSG) : sur la X32 de scène, *Setup →
  Preamps* « HA REMOTE : AES50 Port A » (photo de Joseph) -> la Core pilote ses préamplis comme ceux d'une S16
  (AES50-A 1-32) : pas besoin de connecter l'appli aux deux consoles. « HA Gain Split » décoché.
- Correction de Joseph : rien à charger sur la X32 de scène ; tout se règle sur la M32C (maître, carte), port A
  OU B. Profils `m32c_x32stage_a` / `_b` (A|B 1-32 -> EXP 1-32, EXP 1-16 -> A|B 1-16). Les profils de la version
  de test (« Core + X32 stage box », « Stage box — X32 vers Core ») sont retirés des listes (`RETIRED_BUILTINS`).
  `_builtin_nodes()` (profils en lignes brutes) reste disponible, vide. Pas encore testé sur le matériel.

## Plusieurs consoles (2026-10-14)

- Chaque route LV1 porte la position de sa carte (`slot` = `device.assign` + 1, le « 2- » de « 2-EX 1 ») ;
  `session_patch.load_cards()` liste les appareils du rack (transportés dans `layer["_cards"]`).
  `pick_sources(card_map={slot: console k})` : seules les cartes associées comptent, EXP global = k*1000 + voie.
- Serveur : `CLIENT` = console 1 ; `EXTRA` = consoles 2.. ({client, ip, card}) ; `PRIMARY["card"]`. Préampli
  global = k*N_HA + i ; `merged_snapshot()` / `merged_meters()` concatènent ; `/api/gain|phantom` -> `console_for`.
  `/api/consoles/add|remove|card`. Settings : `card`, `consoles`. `auto_assign_cards()` (2 s) : carte dont le nom
  LV1 (sans « (IOBox) ») est contenu dans le nom de la console ou l'inverse, si unique. Carte map vide (une
  console, pas de carte choisie) = comportement d'origine.
- Float : `strip_tag` « 2·A 5 », `exp_txt` « 2·15 », panneau ⋮ → Consoles… ; page Channel : EXP lu = voie (% 1000).
- Testé : console 1 = X32 de Joseph (carte 1, auto par le nom), console 2 = simulateur (carte 2) : tranche 64 ->
  préamplis 128/129 « 2·1/2·2 », gain envoyé à la console 2 seulement.
- Routing par console : paramètre `target` (n° 0-based) sur `/api/routings/preview|apply|undo|model` (dans
  `_routing_route`, `client = console_for(target * N_HA)`) ; `consoles[]` de l'état porte `routing_last` /
  `routing_can_undo` ; page : sélecteur `#rcons` (si > 1 console) ; float : `_pick_console()`. Testé sur le
  simulateur en console 2 (envoi, vérification, EXP relus, annulation), console 1 intacte.
- Scènes multi-consoles : `_capture` via `merged_snapshot` (clés globales, console 1 inchangée, `console.consoles`
  = consoles de la scène) ; `recall_all` découpe par console (absente -> `skipped`) ; `/api/presets/undo` sur
  toutes ; `merged_recall_state` fusionne `last_recall` / `can_undo`. Testé sur le simulateur.
- Panneau du float : fermeture automatique (fenêtre active) SUPPRIMÉE, croix ✕ seulement : le clavier tactile de
  Windows est une autre appli et fermait le panneau pendant la saisie (Joseph, 2026-10-14).

## Look du float (2.7.0)

- Piste « liseré LV1 » choisie par Joseph parmi 3 (cartes / anneau couleur / liseré) : liseré = pastille du haut de
  colonne (existait déjà), potard à **arc de la couleur du canal** qui suit le gain (gris si couleur inconnue),
  dB en blanc sur le fond, 48V entouré, rouge `PH_ON` quand actif (bleu avant).
- Potard = image calculée pixel par pixel avec anti-crénelage (`knob_image`, Python pur : Tk ne lisse pas sous
  Windows, pas de Pillow) ; géométrie par taille + images en cache (44 px ~3 ms, 130 px ~27 ms la 1re fois).
- Question de Joseph « mieux que tk ? » : réponse donnée = rester sur tk pour la 2.7 (tout le calage LV1, la
  transparence `-transparentcolor` et le z-order y sont réglés) ; Qt (PySide6) possible pour une 3.0.
- Tester les colonnes : script qui crée des `Strip` avec un faux `owner` (locked, sensitivity, send_gain, label,
  value_pop, root) + capture BitBlt ; le float `--direct --sim` n'a pas d'EXP (colonnes transparentes).

## v3 en Qt (branche `dev-3.0`, décidée le 2026-10-14)

- Raison : la LV1 est pensée multi-touch ; tk ne reçoit qu'un doigt (toucher = clic souris). Test
  `tools/qt_touch_test.py` (exe `XM32_Qt_Touch_Test.exe`, 46 Mo, ~2 s au lancement) : **4 doigts = 4 potards en
  même temps, OK chez Joseph** ; fluidité identique à tk (mesuré : ~0,6 ms par colonne dans les deux cas).
- Fenêtre Qt : `FramelessWindowHint | Tool | WindowStaysOnTopHint | WindowDoesNotAcceptFocus`,
  `WA_TranslucentBackground` (colonnes vides = alpha 0), `WA_AcceptTouchEvents` (un point = un potard),
  `QT_ENABLE_HIGHDPI_SCALING=0` (pixels = pixels écran pour le calage).
- **Étape 1 faite (3.0.0-a1)** : `x32_qt_float.py` (classe `QtFloat`, fenêtre `FloatWindow` tout dessinée, `Link` =
  lectures/envois sur des fils, `Dialog`, `ValuePop`) ; reprend la logique de `x32_gain_float` (import, pas de copie
  des fonctions sans interface). Lancement : appli avec l'option cachée `--qt-float` -> floats lancés avec
  `--float --qt`. Même fichier de config que le float tk. Tests : `QTest.touchEvent` prend des coordonnées ÉCRAN
  (`mapToGlobal`), et la LV1 de ce PC cache le float -> remplacer `x32_qt_float.lv1_windows` par `lambda: {}`.
- **Calage v3 (2026-10-14)** : cartes DANS les cadres des tranches (`CARD_L/CARD_R` = 1/96 et 93/96 du pas, hauteur
  `QT_AUTO_H` 132/1080), relevé au pixel sur la LV1 de Joseph (1920x1080 et fenêtré OK). **Float fixe** (choix de
  Joseph) : plus de déplacement ni de redimensionnement à la main, toujours calé ; menu « Recaler sur la LV1 ».
  Languette = `ToolBar` dans l'espace vide de la barre du haut (`TOOL_BOX`, entre Setup et le cadenas) : logo
  (gris = pas de console, couleur = connectée), chevron (repli animé `FOLD_MS`), hamburger (menu).
- **Étapes 2 et 3 faites (3.0.0-a4)** : `Canvas` commun (FloatWindow 16 colonnes, BoxWindow cadres Edit / Channel) ;
  lectures d'écran et vérification EMPRUNTÉES au float tk (`_screen_reader = xf.FloatApp._screen_reader`, etc. :
  attributs de même nom) ; panneaux dans `x32_qt_panels.py` (Panel : scenes / routing / consoles / console,
  RoutingEditor + MatrixView, pick_console). Animations : AUCUNE sauf le 48V (fondu `PH_MS`, rouge lumineux avec
  halo) — dépli et glissement de couche essayés puis retirés à la demande de Joseph ; languette au style du cadenas LV1 (fond 17, contour 160).
- **Menu maison** (`x32_qt_panels.MenuPopup`) : le QMenu de Qt (popup) se refermait aussitôt / au hasard, la LV1
  restant la fenêtre active. Ne pas revenir à QMenu. Piège PySide : `clicked` envoie un booléen qui écrase le 1er
  argument par défaut d'un lambda (`lambda sub=act: ...`) -> toujours `lambda _checked=False, ...`.
- Écrans : un écran OK (Edit et Channel validés par Joseph le 2026-10-14) ; deux écrans : soucis à voir ensemble.
- **Étape 4 faite (3.0.0)** : Qt par défaut (`FLOAT_QT = True`, `--tk-float` / `--float --tk` pour le tk), PySide6-Essentials
  + `--hidden-import x32_qt_float x32_qt_panels PySide6.QtWidgets PySide6.QtSvg` dans `build.yml` et
  `Compiler_en_exe.bat`. Pages détachées / 2 écrans : hors périmètre 3.0.
- (Historique, test) Pas encore porté dans le test : `_follow_lv1` (le test reste devant toutes les fenêtres, remarqué par Joseph),
  couches/onglets/modes, calage manuel et par écran, cadres Edit/Channel, panneaux, Mixers détachés, 48V.

## PATCH MAP (branche `dev-3.1`, commencé le 20/10/2026)

- Demande de Joseph : retrouver quelle entrée X32 est derrière chaque EXP (« A1 = EXP 11 », la LV1 ne laisse pas
  renommer ses sources : elle affiche « X32RACK Dg EXP n », noms venus de la carte, table `device_channel_info` vide).
- Fait : `x32_gain_float.patch_map_rows` (+ `source_long`) = EXP -> préampli (exp_map) -> canal X32 (`names` par
  préampli, VIDES chez Joseph : X32 en stage box) -> canal(aux) LV1 (lv1_sources, lv1_channels, côtés L/R) ; panneau
  Qt `patchmap` (menu du float « Patch map… », recherche qui masque les lignes), textes dans `x32_i18n.EN`. Test
  `tests/test_patch_map.py`. Piège : l'état du float est dans `app.link.snap` (pas `app.snap`). Vu par Joseph : « pas
  mal », à peaufiner. Exe de test : `dist\3.1-test2`.
- Reste : étiquettes « A1 · P170 ST » posées sur la page Patch de la LV1 (maquette validée, sur la colonne « Device
  Name » de la vue où les sources EXP sont en lignes) : il faut une capture plein écran de cette vue (géométrie,
  zoom, défilement). Version : publiée en 3.1.0.

## PATCH DE SCÈNE (branche `dev-3.1`, commencé le 20/10/2026)

- Demande de Joseph (croquis sur la face d'une S16) : nommer / colorer les PRISES physiques (S16 IN 1 = « Kick ») ; le
  nom suit la prise -> préampli -> EXP (exp_map) -> canal LV1, qui est **renommé automatiquement** dans la LV1.
- Décisions de Joseph : renommage AUTOMATIQUE ; **feuilles de patch par spectacle, séparées des scènes de gains** ;
  canal stéréo = nom de la voie **gauche** (OV en 2 mono = deux noms, piano stéréo = « Piano L ») ; appareils :
  S16, X32 Rack, X32, M32C seulement.
- `x32_stage.py` (sans Qt) : `DEVICES` (faces dessinées en fractions ; S16 vue AVANT, X32 / X32R vue ARRIÈRE donc IN 1
  à droite), clés de prise `slot:io:n` (slot local / A / B), `port_preamp` (Local 0-31, A 32-79, B 80-127, + k·128),
  `StageStore` (`x32_stage_patch.json` à côté des scènes : feuilles, active, `auto`, `applied`), `lv1_renames()`.
  Appareils par défaut selon le modèle /info tant que rien n'est choisi (`devices_set`).
- Règles du renommage (`lv1_renames`, priorité revue par Joseph le 20/10 : « c'est lui qui prend la priorité ») :
  l'ÉTIQUETTE GAGNE quand le canal reçoit la source (nouvelle prise ou 1re fois vue, `applied[ch]["src"]`) ou quand
  l'étiquette change (`applied[ch]["label"]`), même sur un nom tapé à la main (ex. canal « test » + EXP 4) ; nom d'avant
  gardé (`prev_name`) ; ensuite, même source + même étiquette : nom retapé à la main RESPECTÉ (pas de bras de fer) ;
  CLEAR (étiquette effacée, même prise toujours branchée) -> piste par défaut « Channel N » + couleur n° 13 (Joseph ; marque
  `cleared` gardée dans applied, `lv1_color_targets(..., applied)` via `stage_state()["applied"]` -> bouton Couleurs) ;
  AUTRE source sans étiquette -> nom d'avant (« test ») sinon « Channel N », + couleur d'avant ;
  canal plus patché -> laissé ; pas de renvoi pendant 5 s ; rien tant qu'une console n'est pas connectée avec son
  routing lu (`stage_exp_map`). Serveur : `stage_loop` (1 s), `/api/stage`, `/api/stage/port|device|sheet|auto`.
- `lv1/remote.py` : télécommande OSC de la LV1 (protocole MyFOH). **Découverte vérifiée** : annonce `/zDNS` en UDP
  multicast 225.1.1.1:13337 (port TCP qui change à chaque session, 51557 le 20/10). Lecture vérifiée (`--dump` : noms
  via `/Channels`, couleur via `/Notify/TrackColor [groupe, canal, n° de palette, r, g, b]` = même palette que
  `channelinfo.PALETTE`). Écriture du NOM : `/Set/TrackName [0, canal-1, nom]`, **vérifié chez Joseph** (In 80).
  **Couleur : IMPOSSIBLE à distance en LV1 V17** (20/10/2026) : MyMonService.dll (ProgramData\Waves Audio\RemoteServices)
  accepte `/Set/TrackColor [i, i, i, f, f, f]` (rgb × 255) mais `WCRx_ExternalService::SetTrackColor`
  (MixerController_MyMon_Control.dll, exporté) = `return 6` (non implémenté). Essayé : rien dans l'OSC ni la base.
  Ne pas rechercher de nouveau (sauf nouvelle version LV1 : redésassembler cette fonction). À la place : repère orange
  « ! » sur la prise quand la couleur du canal LV1 diffère de l'étiquette (`StagePatch.color_differs`).
- **Fenêtre unique STAGE PATCH** (2e version, demande de Joseph du 20/10 : « regrouper patch map et stage patch », « remplir
  la patch map vite : In 2 -> renommer -> couleur -> In 3 ») : `x32_qt_stage.StagePatch` = éditeur (palette 4 x 8 dans
  l'ordre / la disposition de la fenêtre couleur de la LV1, champ du nom à la couleur choisie, ‹ ›) + PATCH MAP (lignes
  dessinées `PatchList`, recherche) à gauche, faces à droite. Entrée / › / ↓ = enregistrer + ligne suivante, ↑ / ‹ =
  précédente, toucher une couleur = enregistrée (avec le nom tapé) sans quitter le champ. Prise sans étiquette dont le
  canal LV1 est renommé : nom + couleur LV1 en pâle (`auto_label`, rien d'enregistré). L'ancien panneau `patchmap` du
  float est supprimé ; menu : une seule entrée « Stage patch… ».
- **Feuilles = sauvegarde / rappel** (déjà là : enregistrement à chaque saisie ; rappel = choisir la feuille, les noms
  partent dans la LV1, couleurs par le bouton). **Export / Import d'une feuille** (demande de Joseph, 20/10) : boutons
  « Exporter… / Importer… » -> `<nom>.stagepatch.json` (`EXPORT_TYPE` « x32-stage-patch », `StageStore.export_sheet` /
  `import_sheet` : nouvel id, nom libre « (2) », active ; `clean_consoles` garde le valable d'un fichier bricolé),
  `/api/stage/export|import`, fenêtres de fichier Windows rattachées à STAGE PATCH (toujours devant), dossier retenu
  (`cfg["stage_dir"]`, défaut Documents). Faces : `_size_faces` refait la mise en page (chevauchement après un import).
- **Style LV1** (relevé sur captures de Joseph, 1920x1080) : fond (71,71,71), panneaux (17,17,17), boutons fond 17 +
  liseré (160,160,160) + texte (231,231,231) gras, actif (56,201,255) texte 17, fenêtre type dialogue (54,54,54) bord
  (160,160,160), flèches (43,43,43), séparateur (120,120,120). `LV1_CSS`.
- **Page Patch** : bouton « Stage Patch » (`StageButton`, `STAGE_BTN_BOX` 18,973 92x54) EN BAS de la colonne Input A /
  Input B (2e capture de Joseph ; 1er essai sous Input B à y 407, tombé au pixel près) ; ouvre la fenêtre posée sur la zone liste + grille (`STAGE_BOX` 124,225 1781x845),
  cachée quand la LV1 quitte la page Patch (`docked`) ; depuis le menu : visible partout. Dans `_windows()` (z-order).
- **Exe en ADMINISTRATEUR (décision de Joseph, 20/10 : « comme XTouch-LV1 », choisi contre « admin si besoin »)** :
  `--uac-admin` (Compiler_en_exe.bat, build.yml ; CI : runners déjà admin). « Lancer avec Windows » = TÂCHE PLANIFIÉE
  `TASK_NAME` « XM32 Gain Recall LV1 » (Windows bloque à l'ouverture de session une clé Run qui exige l'admin) :
  `autostart_task_xml` (ouverture de session de CET utilisateur, HighestAvailable, batterie OK, ExecutionTimeLimit PT0S,
  Priority 4), `schtasks /Create /XML` (vérifié : accepté et relu, tâche d'essai supprimée), créée / supprimée SEULEMENT
  par la case ; ancienne valeur Run (<= 3.0.1) retirée quand on coche / décoche, jamais toute seule. Pages web :
  `open_url` (x32_gain_recall) / `xf.open_url` -> explorer.exe si admin (navigateur aux droits normaux, comme XTouch).
  `snap["admin"]`. Essai de l'exe sans UAC depuis Claude : `$env:__COMPAT_LAYER='RunAsInvoker'`. XTouch-LV1 (admin)
  lance Gain Recall par Popen -> OK ; il le retrouve aussi par la clé Run « XM32 Gain Recall LV1 » (plus écrite).
- **Couleurs -> LV1 par clics (FAIT, VÉRIFIÉ chez Joseph le 20/10 : 10 canaux colorés, relus dans la base)** : idée de Joseph ; il a vérifié (20/10) : page Patch ->
  Input A, clic sur la bande de couleur d'un canal = fenêtre « Select a Color from the Pallete Below », ‹ › changent de
  canal SANS la fermer, couleur appliquée TOUT DE SUITE. `lv1/colorclick.py` : géométrie relevée sur sa capture plein
  écran (1920x1080 ; Input A (60,282) bleu ; 1re ligne In 1 (141,360), pas 7 ; fenêtre x 708..1197 y 270..754 fond
  (54,54,54) ; palette 1re case (802,360), pas 101x31, même ordre que PALETTE ; champ du nom (819,638) = FOND à la
  couleur du canal ; ‹ (1022,638), › (1070,638), OK (1120,716)), `ColorJob` (ouvre sur In 1, › jusqu'au canal, clic
  couleur, OK à la fin), `post_click` (PostMessage à la fenêtre enfant, souris immobile, comme XTouch-LV1) dans la fenêtre LV1 la plus en avant
  au point (`lv1_window_at` : « Color Picker » est une fenêtre À PART, Qt624QWindow ; 1er essai : clics perdus dans la
  fenêtre principale, bloquée par la Color Picker modale -> rien modifié, vérifié dans la base).
  Garde-fous : Input A (sinon clic dessus), 1re ligne = couleur d'In 1, fenêtre reconnue par 6 cases, fond du champ =
  couleur actuelle du canal visé, changement vu sur CE canal (OSC /Notify/TrackColor d'une connexion dédiée
  `LV1Remote.color_events`, sinon base de la LV1 ~1 s) ; mauvais canal -> remis + arrêt. UI : bouton « Couleurs → LV1
  (n) » de STAGE PATCH (`x32_stage.lv1_color_targets` : voie gauche d'abord, déjà bonne = rien ; `ColorRunner` = fil,
  fenêtre cachée pendant les clics, refus si pas admin / pas page Patch). Test `tests/test_colorclick.py` (LV1 simulée).
  **Messages toujours devant (Joseph : « sinon je vais être bloqué »)** : résultats / erreurs de STAGE PATCH = notification
  en bas à droite (`StagePatch.notify` -> `app.toast`, hauteur selon le texte), plus de confirmation avant les couleurs ;
  saisies restantes (feuilles) = `Dialog`, enregistrée dans `app._modal` pendant `ask()` ; `_windows()` dans l'ordre de
  passage au premier plan : STAGE PATCH en premier, toast et message en dernier. (`parent` d'un Dialog = fenêtre où se
  centrer, PAS un parent Qt : cadre Windows vu chez Joseph.) Champ du nom relu jusqu'à 0,8 s (2e essai : arrêt « pas In
  1 » juste après l'ouverture), couleurs lues / attendues dans le message.
- Test : `tests/test_stage.py [--image f.png]` (QT_QPA_PLATFORM=windows pour les polices) ; float piloté par script sur
  un serveur de test (port 8091, APPDATA temporaire, `qf.lv1_windows = lambda: {}`). Exe de test : `dist\3.1-stage-test10`.
- Reste : sorties (OUT 7 = Genelec) = repère seulement, pas encore le chemin LV1 ->
  carte -> User Out -> AES50 ; sélecteur de sorties 1-8 / 9-16 de la S16 ; page web.

## TABLETTE TOUCHOSC (branche `dev-3.2`, commencé le 27/10/2026)

- Demande de Joseph : TouchOSC (Hexler, version actuelle, fichiers `.tosc`) sur sa tablette **Doogee R10** (Android 13,
  10,36", 2000 x 1200) = calque de Gain Recall (gains sur les canaux LV1, scènes, routing, stage patch) + contrôle de la
  LV1 « comme MyFOH ». Plan validé (27/10) : **tout dans Gain Recall** (indépendant de la X-Touch ; la LV1 accepte
  plusieurs télécommandes), phases 0 socle / 1 pont / 2 page GAINS / 3 SCÈNES + ROUTING / 4 STAGE PATCH / 5 contrôle
  LV1 (`lv1/model.py` repris du `handle` de XTouch-LV1) / 6 livraison (3.2.0 + template ; Total Control 0.8).
- `touchosc/` : `tosc.py` (écriture / lecture `.tosc` = XML `lexml version='3'` compressé zlib, format relevé dans les
  chaînes de TouchOSC.exe ; propriétés typées s/b/i/f/c/r ; ID = uuid5 du chemin -> fichier identique à chaque
  génération), `build_tosc.py` (`py -m touchosc.build_tosc [sortie]`, défaut `dist/touchosc/`), `template/root.lua`
  (TOUTE la logique côté tablette en Lua : pas de `<messages>` à décrire), `protocol.py` (PROTO, ports, messages ;
  fonctions pures), `bridge.py` (fil UDP, tablettes par IP, réponse sur PORT_OUT de la tablette).
- Ports : Gain Recall écoute **UDP 9300** (`--touchosc-port`, 0 = coupé ; 127.0.0.1 avec `--local-only`), la tablette
  **9301**. Réglage TouchOSC : Connections > OSC UDP, Host = IP du PC, Send 9300, Receive 9301.
- **Phase 0 faite (3.2.0-a1)** : `/xgr/hello [i proto, s nom]` toutes les secondes -> `/xgr/welcome [i proto, s version,
  s console, s ok|old_template|new_template]` ; page présence (voyant bleu LV1, état, consigne de réglage). Test
  `tests/test_touchosc.py` (fausse tablette UDP) ; vérifié sur un serveur de test ET sur l'exe (RunAsInvoker).
  **Validé chez Joseph le 27/10** dans TouchOSC du PC (« Connected… 3.2.0-a1 », console X32RACK-07-BF-17). Ne jamais
  charger un fichier dans SON TouchOSC ouvert (il travaille peut-être dessus) : il l'ouvre lui-même.
  Idée de Joseph : TouchOSC du PC en **SERVEUR** (template + Lua + OSC en 127.0.0.1), tablette en **CLIENT** (Connections
  > Client : rien à copier sur la tablette, elle affiche la surface du PC). Contours : `outline` False ; alignement / forme
  posés en Lua (`AlignH.LEFT`, `Shape.CIRCLE`) faute de connaître les valeurs numériques du fichier.
  **R10 en client validée le 27/10** (Wi-Fi 192.168.1.20 -> serveur TouchOSC du PC, **TCP 6666**). Blocage d'abord
  (« connecting… » sur Wi-Fi ET Tailscale) : Wi-Fi classé **Public** + aucune règle pare-feu pour TouchOSC ; Joseph a passé
  le Wi-Fi en Privé et autorisé TouchOSC (commandes admin données, pas exécutées par Claude : réglage de sécurité).
  Tailscale (PC 100.113.68.110) : pas de découverte automatique (multicast), adresse à entrer à la main.
  Piège Windows : UDP -> `ConnectionResetError` (WSAECONNRESET) quand l'autre côté n'écoute pas encore : ignoré.
  Exe de test : `dist\3.2.0-a1-test` (+ le `.tosc`).
- **Lua de TouchOSC (a13-a17, 27-28/10)** : **PAS de `pcall`** (« CONTROL(ROOT) RUNTIME ERROR: attempt to call global
  'pcall' (a nil value) » : script racine arrêté dès init, plus de hello = « ne se connecte pas »). Erreurs : journal de
  TouchOSC (mode édition). Banc `tests/lua_bench.py` (lupa **lua51** comme TouchOSC, `py -3.14 tests/lua_bench.py <scratchpad>/luaenv`) SANS
  pcall. **Manuel Hexler résumé : skill utilisateur `touchosc`** (`~/.claude/skills/touchosc/`) : Lua 5.1, base
  réduite à error/ipairs/next/pairs/print/select/tonumber/tostring/unpack/type, API mal utilisée = script arrêté,
  Shared Scripts (`require`) pour répartir un gros script, serveur MCP intégré (1.5.4+, seulement avec l'accord de Joseph). Taille : a13 (17,7 Ko) muet, cause non prouvée (pcall ajouté juste après) ; `build_tosc` retire commentaires
  / indentation et refuse > 16 000 octets par script ; racine ~15 Ko -> la répartir avant d'en ajouter.
- **Phase 1 faite (3.2.0-a2, 27/10)** : décision de Joseph = **mode serveur par défaut** (pont en 127.0.0.1, TouchOSC du PC
  en serveur, OSC Host 127.0.0.1) ; réseau direct en option seulement : `--touchosc-lan` + `--touchosc-allow IP,IP`
  (le PC toujours accepté, inconnu refusé et signalé une fois au journal). Moteur d'état : `protocol.state_messages(état)`
  -> {adresse: arguments}, le pont (10 Hz) n'envoie à chaque tablette que ce qui a changé POUR ELLE (`sent`), tout à
  l'arrivée et sur `/xgr/sync` (bouton SYNC). Actions : `protocol.parse_action` (liste fermée) -> `actions` {nom: fonction}
  fournies par x32_gain_recall ; une chaîne rendue = erreur -> `/xgr/notify` (ligne orange, 6 s). L'état vient de
  `merged_snapshot` DANS le processus (les poignées HTTP sont minces : mêmes fonctions, sans le détour HTTP). Mesuré :
  ~1 % d'un cœur avec une tablette. En mode serveur, Gain Recall ne voit QU'UN client (TouchOSC du PC), pas les tablettes
  clientes (ligne « TOUCHOSC »). Page : CONSOLE / LV1 / TOUCHOSC. Exe de test `dist\3.2.0-a2-test` (+ .tosc).
- **CORRECTION (27/10, essai de Joseph sur la R10)** : le « serveur » de TouchOSC est le RÉSEAU DE L'ÉDITEUR (manuel Hexler,
  Editor · Network) : il pousse le DOCUMENT aux clients, mais chaque client est une surface autonome (ses scripts, SES
  connexions OSC ; valeurs envoyées une fois à la connexion). Ce n'est PAS un miroir : la tablette cliente affichait
  « Looking for… » (son hello partait vers elle-même). Claude l'avait mal décrit -> la décision « mode serveur par défaut »
  reposait sur une erreur. Bon usage : serveur de l'éditeur = distribuer le template ; la tablette parle à Gain Recall
  par le RÉSEAU (Host = IP du PC) -> il faut le mode réseau + autorisation des tablettes + pare-feu UDP 9300.
  **R10 en réseau VALIDÉE le 27/10 (3.2.0-a3)** : exe lancé `--touchosc-lan --touchosc-allow 192.168.1.20`, règle pare-feu
  UDP 9300 entrante (profil Privé, créée par Joseph en admin), R10 : Connections > OSC UDP Host 192.168.1.16 Send 9300
  Receive 9301 (elle n'était PAS configurée : 0 paquet reçu) + Client vers 192.168.1.16 port 6666 entré à la main (le
  serveur n'apparaissait pas dans la liste). Diagnostic : `/api/state["touchosc"]` (écoute, autorisées, tablettes,
  refusées, `rx`, dernier expéditeur ; lisible depuis le PC sans code). À corriger : en mode réseau, le PC lui-même est
  refusé quand il passe par son adresse réseau (seul 127.x est toujours accepté) -> corrigé en a4.
- **Autorisation des tablettes (3.2.0-a4, décision de Joseph du 27/10)** : RÉSEAU par défaut (`--touchosc-local` = 127.0.0.1
  seulement ; `--touchosc-lan` supprimé), seules les tablettes autorisées. PC toujours accepté (127.x + ses adresses,
  `local_addresses()`). Inconnue -> `pending` (welcome « pending » : la page affiche « Waiting for approval », rien
  d'autre envoyé, gestes ignorés) ; le float (pas une page détachée) demande « Autoriser la tablette X (nom) ? »
  (`_ask_tablets`, Dialog Autoriser / Refuser, une fois par tablette et par lancement du float) -> POST
  `/api/touchosc/allow` (PC seulement) -> `touchosc_decide` : oui = `settings["touchosc_allow"]` (retenu), non =
  `denied` jusqu'au prochain lancement (rien d'enregistré ; retire l'adresse si elle était retenue). `--touchosc-allow`
  ajoute des adresses d'office. Règle de pare-feu UDP 9300 : par l'installeur Total Control (UAC), phase 6.
  **Validé chez Joseph le 27/10** (R10 en attente -> question du float -> Allow -> Connected).
- **Phase 2a faite (3.2.0-a5, 27/10) : page GAINS en lecture seule** = calque du float sur la couche LV1 de **Mixer 1**.
  `touchosc/views.py` (pur) : `gain_page(état)` -> titre de couche (« Ch 49-64 », « Custom 3 ») + 16 tranches {canal,
  label, couleur RRGGBB, src « A 1/2  EXP 1/2 », voies [{idx, db, phantom}]} ; canal -> EXP (lv1_sources) -> préampli
  (exp_map inversée), EXP sans préampli = pas de voie (« no X32 preamp »), tranche sans canal vide. `strip_tag` /
  `exp_txt` RECOPIÉS de x32_gain_float (l'importer depuis le pont relancerait x32_gain_recall, qui tourne en __main__).
  Messages : `/xgr/g/title`, `/xgr/g/k/{name,color,src,units}`, voies `/xgr/g/k/{m|l|r}/{gain,db,48v}` (mono « m »
  pleine largeur, stéréo « l » + « r » ; voies absentes non envoyées, cachées par Lua). Template : barre d'état compacte
  sous l'en-tête, titre de couche en bleu, 16 tranches (pas 120 px : bandeau, nom, source, RADIAL + dB + 48V rouge
  (209,52,59) comme PH_ON) pré-créées en m / l / r (TouchOSC ne crée pas de contrôle en Lua : visibilité), panneau
  de connexion PAR-DESSUS, caché une fois connecté. Vérifié sur les données réelles de Joseph (Ch 49-64, FireRoom
  L 15/16 EXP 31/32 à 12 dB) et sur l'exe. **Vu par Joseph le 27/10 sur le PC ET la R10** (identiques ; « TouchOSC: 2 »).
  Retouche demandée (a6) : stéréo EMPILÉE (« l » au-dessus de « r », pleine largeur, repères L / R) au lieu de deux
  petits potards côte à côte. Moitié basse de l'écran gardée libre (contrôle LV1, phase 5). Phase 2b prévue : banques
  1-16 … 65-80 en boutons directs + FOLLOW LV1 (défaut), vue PAR TABLETTE (la couche de la LV1 ne bouge pas).
- **Phase 2b faite (3.2.0-a7, 27/10) : contrôle depuis la tablette.** Vue PAR TABLETTE (`tablets[ip]["view"]` : None =
  suit Mixer 1, ou banque 0..4 ; `views.gain_page(état, bank=…)`, `bank_count` d'après `lv1_count`, banques au-delà
  grisées) ; `/xgr/view/bank i`, `/xgr/view/follow` ; messages `/xgr/view/{follow,bank,banks}`. Gestes : `/xgr/g/k/u/gain f`
  (dB voulu, borné -12..60) et `/xgr/g/k/u/48v` (bascule) traduits en préampli d'après la PAGE de CETTE tablette
  (`views.unit_idx`, voie disparue -> « This strip just changed ») -> `touchosc_gain` / `touchosc_phantom` (x32_gain_recall :
  `console_for` + `set_gain` / `set_phantom`, comme l'API ; 48V d'état INCONNU (None) refusé : basculer l'allumerait).
  Template : `knob.lua` (RADIAL `response` 1 + `Response.RELATIVE` en Lua ; envoi par pas de 0,5 dB pendant le toucher ;
  saut > 3 dB d'un coup = geste bloqué), retour de la console ignoré sous le doigt puis potard recalé (200 ms) ;
  `phantom.lua` (BUTTON transparent sur la case : « OK? » 3 s puis 2e appui) ; banques + FOLLOW LV1 dans l'en-tête, titre
  de couche dans la barre d'état ; `paintBanks` (bank / banks arrivent dans un ordre quelconque). Valeurs d'énumération
  déduites des chaînes de TouchOSC.exe : listées À L'ENVERS de leur valeur (MOMENTARY=0 … ; ABSOLUTE=0, RELATIVE=1).
  **Retour de Joseph sur l'a7 (PC et R10) : potards « erratiques »** (valeur qui revient au départ, trop rapide) : potard
  rond en relatif = tourner autour d'un petit potard (72 dB en un geste) + garde-fou anti-saut (> 3 dB) qui annulait
  les gestes rapides. **a8 : glisser VERTICAL** (`drag.lua` sur un BUTTON transparent pleine largeur posé sur le potard,
  `onPointer` + `PointerState`, 5 px par pas de 0,5 dB `DRAG_STEP_PX`, à partir de la valeur affichée : aucun saut
  possible ; potard et dB mis à jour sous le doigt) ; potard = affichage (non interactif, `knob.lua` supprimé).
  Script racine : retours de la console ignorés pendant le glisser ET 1 s après (`HOLD_MS`, comme le float 800 ms),
  puis potard et dB recalés sur la console ; `_drag` et `_48b` cachés avec leur voie.
  **a8 validée par Joseph le 27/10** (« bien mieux »). Piège vu : il testait l'exe a8 avec le template a7 encore ouvert
  dans TouchOSC (même nom de fichier dans chaque dossier de test) : toujours lui faire rouvrir le .tosc du BON dossier.
  48V (OK? puis confirmation) et banques / FOLLOW LV1 **validés par Joseph le 27/10**.
- **DA voulue par Joseph (27/10, capture de sa page Mixer 1 en SndChk avec le float)** : le template doit ressembler à une
  page Mixer de la LV1, tranche par tranche, de haut en bas : bouton de source (fond teal, « 1- EX 1 », 2 lignes en
  stéréo, rouge = couleur du canal), A / B, cadre préampli (le float : « A1 = EXP 1 », potard, dB, 48V ; stéréo côte à
  côte), Ø + Trim (valeur bleue + potard), bandeau du nom à la couleur du canal, « A » + potard de pan, MUTE, valeur du
  fader (bleu) + crête du vumètre, fader avec échelle +10…−∞ et vumètre, numéro + bouton casque (cue) ; tranche LR à
  droite (C / M, Master) ; rangée des User keys en haut. Proposé : « phase 2c » = cette disposition, le non-branché
  (Ø, Trim, pan, MUTE, fader, cue, LR) dessiné grisé jusqu'à la phase 5.
- **Phase 2c faite (3.2.0-a9, 27/10) : template en page Mixer de la LV1.** 16 tranches (pas 116) + LR, rangées SRC, AB,
  PRE, PHASE, TRIM, NAME, PAN, MUTE, FVAL, PEAK, FADER, NUM, CUE (constantes de build_tosc). Actif : bouton de source
  (`views.input_name` : « 1- EX 15 », place de la carte = `consoles[k].card`, sinon « EX 15 » ; une ligne par voie),
  cadre préampli (« A 7/8 = EXP 7/8 » comme le float, stéréo CÔTE À CÔTE, glisser par voie), bandeau du nom (nom LV1
  brut « Channel 1 »), bandeau du numéro ; source / nom / numéro à la couleur du canal, texte INK (17,17,17).
  Joseph : « phase, trim, pan, mute sont des touches LV1 » -> Ø, Trim, pan, MUTE, fader, cue, A / B, LR = `lv1_key` /
  contrôles non interactifs gris (OFF 90,90,90) jusqu'à la phase 5. Banques / FOLLOW / SYNC dans la rangée du haut (à
  la place des User keys), état en bas. Messages ajoutés : `/xgr/g/k/ch`, `/xgr/g/k/input`. 902 contrôles (62 ko) :
  fluidité : **« ça a l'air de rester fluide » (Joseph, 27/10)** — sinon réduire les graduations des faders (136).
- **Phase 5a faite (3.2.0-a10, 27/10) : commandes de la LV1 AFFICHÉES en direct (lecture seule).** Décisions de Joseph :
  **LR en lecture seule** (comme la X-Touch), **A / B = indicateur** (aucune commande OSC connue par canal ; lu dans la
  base : param 0, `session_patch.read_session` -> `info[ch]["input"]`). `lv1/model.py` (`LV1Mixer.handle`, repris de
  XTouch-LV1 : /Channels avec purge des pistes disparues, Track/Out/Gain, Out/Mute, Solo, Track/Pan /45, TrackTrim et
  PhaseState par voie, StemFormatForSource, Meters ~23/s sans abonnement, `METER_STALE` 1 s) ; connexion DÉDIÉE
  (`start_mixer` : LV1Remote + `listeners`, ajout dans lv1/remote.py) lancée avec le pont. Écoute du 27/10 : à la connexion
  la LV1 envoie /Channels, trims, phases, faders, vumètres ; PAS les pans -> lus dans la base (`channelinfo` param 436,
  /45, `lv1_channels[ch]["pan"]`). `touchosc_state()` = merged_snapshot + `lv1_mixer` + `lv1_live`. Vue :
  `views.mix_info`, `fader_frac` (courbe relevée sur la capture : 0 dB à 0,765) ; messages `/xgr/g/k/{fader,fval,peak,
  meter,mute,solo,pan,trim,trimv,phase,ab}`, `/xgr/lr/{fader,fval,peak,meter,mute}`, `/xgr/live` (fval « -144.0 » comme la
  LV1, crête au dB près sous -60 pour ne pas inonder). Lua : `setMix` / `setLive` (MUTE rouge, CUE / Ø / entrée bleus,
  tout gris sans LV1) ; vumètre = FADER lecture seule vert. Vérifié sur la vraie LV1 (P170 CUE, LR -0.2, faders -144).
  `--hidden-import lv1.model`. Test `tests/test_lv1_model.py`. **Vu par Joseph le 27/10 : « ça suit »** (capture Ch 49-64).
  Retouches a11 : TouchOSC n'affiche pas le retour à la ligne -> source stéréo « 1- EX 31/32 » (`views.input_names`) ;
  cadre préampli « L15/16 = EXP 31/32 » (sans espace après la lettre, comme le float ; texte 12) ; banques / FOLLOW en
  contour plein (`OutlineStyle.FULL` : par défaut des coins, vus comme des crochets).
- **Phase 5b faite (3.2.0-a12, 27/10) : commandes de la LV1 depuis la tablette.** Adresses de COMMANDE à part :
  `/xgr/g/k/set/{fader f dB, pan f -1..1, trim f dB, mute, solo, phase}` (bornées ; rien pour LR : lecture seule) ; le
  pont prend le canal de la tranche k de la PAGE de la tablette -> `touchosc_lv1(ch, champ, valeur)` (x32_gain_recall) :
  `/Set/Track/Out/Gain [g c d]`, `/Set/Track/Pan [g c d pan*45]` (pas 1/45), `/SetTrackTrim [g c stéréo f]` (±30, pas
  0,5), `/Set/Track/Out/Mute [g c T|F]` (encode_message gère maintenant T / F), `/Set/Solo [g c i]`,
  `/SetTrackPhaseState [g c stéréo i]` = celles de XTouch-LV1 ; bascules d'après l'état annoncé, refusées s'il est
  inconnu. `LV1Remote.send`. Template : `fader.lua` (glisser vertical 1:1 sur la colonne, courbe LV1 -> dB au dixième),
  `pan.lua` (horizontal, 120 px centre -> côté), `trim.lua` (vertical, 6 px / 0,5 dB) : envois espacés de 30 ms, valeur
  finale au lâcher ; MUTE / CUE / Ø = boutons transparents (`tap`). Racine : `DRAG_OF` + `busyCtl` (retours ignorés
  pendant le geste et 1 s après) + recalage 200 ms (`applyMix`). Vérifié : test (décodage, LR refusé, canal par page)
  et faux mixer (commandes exactes). **Validé par Joseph le 27/10 (« top »).**
- **Décision de Joseph (27/10) : TOUTES les phases avant de publier** (3 scènes + routing, 4 Stage Patch, puis livraison :
  template dans la release, annonce Bonjour / DNS-SD pour « Browse » de TouchOSC, pare-feu par l'installeur + entrée du
  float, Total Control 0.8).
- **Phase 3a faite (3.2.0-a13, 27/10) : onglets + page SCENES.** Template en PAGES : groupes `page_mixer` (tranches + LR),
  `page_scenes`, `page_routing` (vide, 3b) ; onglets MIXER / SCENES / ROUTING (`tab.lua`, sur la tablette seulement ;
  banques / FOLLOW / titre de couche sur MIXER seulement) ; titre déplacé en bas. Les scripts des contrôles d'une page
  trouvent leurs voisins par `self.parent` (= le groupe de la page). Page SCENES : liste entière envoyée par Gain Recall
  (`touchosc_state()["presets"]` -> `views.scene_page` -> `/xgr/sc/count`, `/xgr/sc/n/{name,info,id}`, `/xgr/sc/last`,
  `/xgr/sc/canundo`) ; pagination (12 lignes) et sélection SUR LA TABLETTE via des libellés cachés (`hidden()` : sc_sel,
  sc_off, sc_selid, sc_ph, sc_count : variables partagées entre scripts, sans `notify`) ; sélection gardée par id.
  RECALL (`recall.lua` : « OK? » 3 s puis 2e appui, « SELECT A SCENE » sans sélection) + « + 48V » ; UNDO ; SAVE NEW (nom
  auto « Scene 27/10 14:32 »). Actions `/xgr/sc/{recall s id i ph, undo, save}` -> `touchosc_scene` : appelle l'API
  LOCALE (`api_local`, mêmes vérifications que le float) sur un fil, résultat à TOUTES les tablettes (`notify_all`,
  `recall_text`). Vérifié : tests + SAVE / UNDO de bout en bout (serveur de test, APPDATA temporaire ; aucun rappel sur
  la vraie X32). Pas d'interpréteur Lua sur ce PC (lupa : sources seulement) : Lua vérifié dans TouchOSC par Joseph.
- **Toutes les couches LV1 sur la page Mixer (3.2.0-a14, 27/10, demande de Joseph : groupes, Fx, Mon, Masters, DCA ; 80 ch
  = mode Mix, 64 ch = dans Factory ; Custom ; Spill).** Source = `/Notify/Layers` (vue, drapeau 1 = Custom, couches :
  nom + (groupe, canal), -1/-1 vide) + `/Notify/CurrentLayer` (règle XTouch-LV1 : jeu « affiché » adopté seulement au
  CurrentLayer qui le suit). `lv1/model.py` : `parse_layers`, `set_kind` (custom / mix « Groups » / input « Ch … » /
  factory « Ch … + Masters / Link DCA » / None = Spill, jamais mémorisé), `sets` (factory, input, mix, custom0, custom1),
  `shown` par vue, `pal` (couleur des bus, /Notify/TrackColor). **Sonde du 27/10** : `/Get/Layers [vue, 0]` ne rend QUE le
  jeu affiché de ce Mixer (args 1..6 : rien) ; envoi spontané à la connexion PAS fiable ; demande ignorée si trop tôt ->
  `start_mixer.keep` : `/Get/Layers` 2 s après la connexion puis toutes les 5 s tant qu'un Mixer n'a pas de couche ;
  jeux vus gardés dans `lv1_layers_seen.json` (APPDATA ; en 80 ch, Mix connu dès qu'il a été vu sur un des Mixers).
  Vue : `views.layer_sets` (jeu de secours « input » d'après `lv1_count` sans télécommande ; factory -> pas d'input / mix),
  `shown_layer` (FOLLOW = Mixer 1, Custom et Spill compris ; repli base), `gain_page(état, view=(mode, n°))`, tranche =
  entrée « in » / bus « bus » / master « ro » (LR, C, M : `MASTERS_RO`, décision de Joseph : lecture seule) ; `key` =
  (groupe, canal). Messages : `/xgr/nav/{kinds,kind,index,n/name}`, `/xgr/g/k/kind` ; action `/xgr/view/layer s mode i n°`
  (remplace les banques) ; commandes LV1 -> `touchosc_lv1(g, c, …)` (masters refusés par le pont ET le serveur ; Trim / Ø
  entrées seulement). Template : rangée des couches dans la page Mixer (INPUT ou FACTORY / MIX / CUSTOM + 8 couches aux
  noms LV1, `nav_row`), tranches descendues de 50 px (fader 424), Lua `paintNav` / `setKind` (bus : pas de A/B, Ø, Trim ;
  ro : gestes coupés). Vérifié sur la vraie LV1 (FOLLOW = Masters de Mixer 1 : LR / Center / Mono en ro, Cue / Talk Back
  en bus ; Mix Groups ; Input). Spill propre à la tablette : plus tard (membres des DCA).

## Reste à faire / idées

- **Signature de l'exe : écartée** par Joseph (2026-10-13 ; payante : Azure Trusted Signing ~10 $/mois ou
  certificat 100-300 €/an). L'avertissement SmartScreen reste, expliqué dans le mode d'emploi. Ne pas reproposer.
- Rien de bloquant. À revérifier après une mise à jour de la LV1 : écriture en direct de
  `CurrentLV1.dat`, paramètre couleur 592 et palette.
- Le choix du dossier des scènes n'existe que dans le navigateur (pas dans le float).
- À revérifier aussi après une mise à jour LV1 : couches / modes (`lv1/layers.py`).

## Environnement cible

- PC hôte : laptop "portable-js" (i7-8750H, 16 Go RAM, Windows 10 IoT
  Enterprise LTSC 2021) ou tour i5-3570K — hôtes dédiés LV1.
- LV1 V17.
- Toolbox Reaper annexe (ReaScript) déjà existante pour l'intégration LV1,
  sans lien direct avec ce projet mais dans le même écosystème studio.
