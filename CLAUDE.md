# X/M32 Gain Recall for eMotion LV1 — repère pour Claude Code

> Court exprès (tokens). Historique complet, mesures et pièges : `docs/CONTEXTE_DETAILLE.md` (chercher la section
> avec Grep avant toute recherche : beaucoup de choses y sont déjà établies). État du moment : `../ETAT.md`.

## Produit

Rappel / réglage des gains et 48V des préamplis **X32 / M32** (OSC UDP 10023) pour un mixage sur **Waves eMotion LV1** :
fenêtre flottante Qt posée au pixel SUR la LV1 (colonnes = canaux LV1, couleur et nom lus dans la LV1), scènes de
gains, routing X32, Stage Patch (prises nommées -> canaux LV1 renommés), tablette TouchOSC. Un seul exe Windows
`XM32_Gain_Recall_LV1.exe`, en **administrateur**, sans console (icône près de l'horloge). Nom : `APP_NAME`,
signature « by Joseph Savigny ». Repo `thaleosguest/x32-gain-recall`, branches `dev-X.Y` (jamais `vX.Y.Z`).

## Fichiers principaux

- `x32_gain_recall.py` : appli (serveur HTTP local 8032 + page web, OSC X32, scènes, routing, consoles multiples,
  `APP_VERSION`, Lancer avec Windows = tâche planifiée, avis de mise à jour, pont TouchOSC).
- `x32_qt_float.py` (float Qt par défaut, multi-touch), `x32_qt_panels.py` (panneaux, `MenuPopup` maison : ne pas
  revenir à QMenu), `x32_qt_stage.py` (fenêtre STAGE PATCH), `x32_gain_float.py` (logique commune + ancien float tk,
  `--tk-float`), `x32_stage.py` (Stage Patch sans Qt), `x32_i18n.py` (`T()`, dictionnaire FR -> EN : tout nouveau
  texte d'interface passe par `T()` et s'ajoute à `EN`), `tray.py`, `brand_icon.py` (généré par `tools/make_icon.py`).
- `lv1/` : tout ce qui touche la LV1 — `patchmap.py` (EXP -> canal LV1, relu 0,5 s), `session_patch.py` (routes,
  `open_copy()`), `channelinfo.py` (noms, palette 32 couleurs, pans, couleurs des bus), `layers.py` (couches, modes,
  sections Top/Middle/Bottom), `remote.py` (télécommande OSC MyFOH, découverte /zDNS), `model.py` (état mixer pour la
  tablette), `colorclick.py` (couleurs posées par clics simulés), `digits.py` (chiffres lus à l'écran).
- `touchosc/` : `tosc.py` (format .tosc), `build_tosc.py`, `template/*.lua`, `protocol.py`, `bridge.py` (UDP 9300 /
  tablette 9301), `views.py`, `mdns.py` (annonce Zeroconf).
- `tests/` : scripts autonomes (`py tests/test_x.py`) ; `tests/lua_bench.py` (Lua 5.1 via lupa).

## Faits LV1 indispensables (détails : CONTEXTE_DETAILLE)

- Patch, noms, couleurs, couches, modes, sections : lus dans `CurrentLV1.dat` (écrit en direct par la LV1, ~1 s),
  TOUJOURS sur copie. Aucun OSC de patch n'existe (ne pas rechercher).
- Couleur canal = param 592 (n° de palette, défaut 13 teal) ; entrée A/B = param 0 (1.0 = B) ; mono/stéréo =
  `chainer.num_inputs` (ignorer `dst_channel_index >= num_inputs`) ; `routes.status` : NE PAS s'en servir.
- Carte X32 reconnue par `device.description` DN32-WSG / X-WSG ; seule la carte X32 compte (TracksLive ignoré).
- Un EXP sur plusieurs canaux -> canal au plus petit numéro (décision de Joseph). EXP sur aucun canal = gris, jamais deviné.
- Onglet LV1 (Mixer 1/2, Channel, Patch…), tranche sélectionnée, page Channel : PAS dans la base -> lus à l'écran
  (captures GDI coûteuses : une par lecture, fil `_screen_reader`, suspendu pendant un glisser).
- Nom de canal écrit par OSC `/Set/TrackName` ; **couleur impossible par OSC en V17** (fonction non implémentée,
  vérifié au désassemblage) -> clics simulés (`lv1/colorclick.py`, vérifié chez Joseph).
- Float calé par fractions de l'écran 1920x1080 (`AUTO_*`, `BAY_Y0`, `TOOL_BOX`, `STAGE_BTN_BOX`…), mono-écran
  (choix de Joseph). z-order : juste au-dessus de la LV1 quand une autre appli est active (`_window_above`).

## TouchOSC (3.2.0, en cours)

- Charger le skill `touchosc` avant tout Lua. **Lua 5.1 SANS `pcall`** (script racine arrêté = « ne se connecte pas »).
  `build_tosc` retire commentaires / indentation et refuse > 16 000 octets par script.
- Tablette en RÉSEAU (le « serveur » de l'éditeur TouchOSC ne fait que pousser le document) : Host = IP du PC,
  Send 9300, Receive 9301 ; tablettes autorisées par une question du float (`settings["touchosc_allow"]`).
- Pont : n'envoie que ce qui a changé par tablette (`MAX_BURST` 120, `REFRESH_PER_TICK` 15 en tournant).
- Actuellement : page Mixer seule (gains X32 + commandes LV1 fader / pan / trim / mute / solo / phase, masters en
  lecture seule, toutes les couches LV1). Template généré par l'exe (menu du float « TouchOSC template… »).

## Données

`%APPDATA%\X32 Gain Recall` (scènes, routings, settings, config du float, Stage Patch, chiffres appris). Une scène =
consoles seulement (gains, 48V, noms), rien de la LV1. JSON lus en `utf-8-sig`.

## Publier une version

1. `APP_VERSION` + section dans `CHANGELOG.md` (+ `MODE_EMPLOI.md` si besoin).
2. PR vers `main` (Joseph fusionne), tag annoté `vX.Y.Z` = `APP_VERSION`, `git push origin vX.Y.Z`.
3. CI `build.yml` : compile, `--version` / `--help`, publie la release (exe + `.sha256` + template TouchOSC).
   `gh workflow run build.yml --ref <branche>` = exe de test sans publier (artefact).
- Compiler en local : `Compiler_en_exe.bat` ou PyInstaller (`--distpath/--workpath/--specpath` dans le scratchpad,
  `--icon` en chemin ABSOLU, `--uac-admin`, hidden-imports listés dans le .bat ET build.yml : les garder en phase).
  Exe de test -> `dist\<version>-test` (un exe lancé est verrouillé : autre dossier).

## Tester

- Serveur de test : `py x32_gain_recall.py --web-port 8091` (sans `--sim`), `APPDATA` temporaire ; l'exe de Joseph
  occupe souvent 8032 et le port 10023 du simulateur. Arrêter par sa ligne de commande `x32_gain_recall.py --web-port`.
- Float : le piloter par script (`argparse.Namespace(port=…)`), remplacer `x32_qt_float.lv1_windows` par
  `lambda: {}` ; sauvegarder puis remettre `%APPDATA%\X32 Gain Recall\x32_float_config.json`.
  `QTest.touchEvent` prend des coordonnées ÉCRAN ; `QT_QPA_PLATFORM=windows` pour les polices.
- Simulateur `--sim` : pas d'EXP tant que le profil « Routing LV1 » n'est pas appliqué (`POST /api/routings/apply`).
- Méthodes qui marchent pour la base LV1 : « enregistreur » (copie à chaque écriture du `-wal` + diff horodaté
  pendant que Joseph manipule) ; demander l'état VISIBLE à un instant donné (un avant/après ne tranche pas un sens).
- Captures d'écran sans Pillow : BitBlt + PNG en Python pur (script `grab.py` à refaire dans le scratchpad).
- Test réaliste de lancement : `explorer.exe fichier.bat` (sinon droits hérités de Claude).

## Index de docs/CONTEXTE_DETAILLE.md

Objectif / versions passées · Patch canal → source · Nom et couleur des canaux (couches, modes, sections, Talk Back)
· Schéma `routes` · Nom et signature · Données · Fenêtre flottante · Publier · Pièges de ce PC · Démarrage plug and
play · Routing (2.4.0) · Mixer détaché · Page Channel et sélection · X32 en stage box d'une Core · Plusieurs consoles
· Look du float · v3 en Qt · PATCH MAP · PATCH DE SCÈNE (Stage Patch, couleurs par clics) · TABLETTE TOUCHOSC (phases
0 à 5, a1 à a21) · Reste à faire.
