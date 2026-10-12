<img src="assets/logo.svg" width="96" alt="Logo">

# X/M32 Gain Recall for eMotion LV1

*by Joseph Savigny*

Petit outil pour **régler, sauvegarder et rappeler les gains** (et le routing, dès la v1.2) d'une Behringer X32 / Midas M32 par le réseau (OSC, UDP 10023). Interface web locale, style Waves eMotion LV1. Aucune dépendance : Python 3.8+ (bibliothèque standard).

Version courante : **2.3.0** (voir [CHANGELOG](CHANGELOG.md)).

## Fonctions
- Réglage des gains (−12 à +60 dB, pas de 0,5) des 128 préamplis : entrées locales, AES50-A, AES50-B.
- Numéro EXP (menu de patch de la LV1) affiché sur chaque voie, **lu en direct sur la console connectée** (`/config/routing/CARD` + `/config/userrout/in`) — reflète le patch réellement chargé, pas un profil supposé. Vide tant que non connecté, ou pour une voie non patchée vers la carte.
- Scènes de gains : sauvegarder, rappeler (avec confirmation, relecture de vérification et annulation), export/import JSON.
- +48 V : confirmation à l'activation, jamais rappelé par défaut. Verrou d'édition. Déplacement relatif (un clic ne change rien).
- Vumètre d'entrée discret sur chaque voie (on/off).
- Onglet Routing : charger en un clic un routing X32 (profil « Routing LV1 » intégré), avec aperçu des différences, vérification et annulation.
- Bouton « Scanner » : recherche les X32/M32 sur le réseau local (broadcast `/xinfo`, voir [CHANGELOG](CHANGELOG.md)) ; la saisie manuelle de l'IP reste toujours possible si le scan ne trouve rien.
- Accès depuis une tablette/téléphone sur le réseau local (`--lan`), protégé par un jeton d'accès.
- Interface web **responsive** (depuis la 1.7.0) : sous ~980px de large, la colonne latérale (banques/scènes) passe sous les voies au lieu d'à côté, et la barre du haut passe à la ligne. Les voies elles-mêmes gardent leur défilement horizontal (seize potards côte à côte reste le principe, même sur petit écran).

## Démarrage rapide (PC de la LV1)
Première fois ? Voir le **[mode d'emploi pas à pas](MODE_EMPLOI.md)**.

1. Télécharger **`XM32_Gain_Recall_LV1.exe`** (onglet *Releases*) et le lancer. Aucune installation, pas de Python, **pas de Companion** à configurer.
2. Au premier lancement, Windows peut afficher :
   - **SmartScreen** (« Windows a protégé votre ordinateur ») : l'exe n'est pas signé → *Informations complémentaires* → *Exécuter quand même*. Pour vérifier le fichier, comparer son empreinte avec le `.sha256` de la release.
   - **Pare-feu** : autoriser l'accès sur les réseaux **privés**, nécessaire pour piloter depuis une tablette et pour le bouton *Scanner*.
3. C'est tout (2.3.0) : l'appli **trouve la console** sur le réseau et s'y connecte (puis s'y reconnecte à chaque lancement), ouvre le **float déjà calé sur les tranches de la LV1**, ouvre la page dans le navigateur **réduite** et remet la LV1 au premier plan. Elle vit dans une **icône près de l'horloge** (plus de fenêtre noire) : Ouvrir la page, Afficher le float, **Lancer avec Windows**, Quitter. Pas de code d'accès sur ce PC (seulement pour les tablettes, bouton 🔑 de la page).
4. Si la LV1 tourne sur ce PC, chaque voie affiche tout de suite le **canal LV1** qui reçoit ce préampli : nom, couleur, « L 15 = EXP 15 », et suit les repatchs en 1 à 2 s. En mode **Edit** de la LV1, le réglage de la tranche sélectionnée apparaît dans le cadre vide du bloc Input. Une version plus récente publiée est signalée (icône, float, page).

### Le donner à quelqu'un d'autre
L'exe suffit, sans rien à configurer côté LV1 : **ni MyRemote, ni adresse IP, ni port, ni Companion**. L'appli lit le fichier que la LV1 tient à jour sur son propre PC (`C:\Users\Public\Waves Audio\eMotion\Sessions\CurrentLV1.dat`, même emplacement sur toute installation). Conditions :
- l'appli tourne sur **le même PC que la LV1** (sinon : gains, scènes et routing X32 marchent, mais sans couleurs ni noms LV1) ;
- la X32/M32 arrive dans la LV1 par sa **carte SoundGrid DN32-WSG ou X-WSG**, reconnue par son modèle, quel que soit le nom donné à l'appareil ;
- testé sur **LV1 V17** : une autre version pourrait ranger ses données autrement, auquel cas l'état est signalé au lancement et la table manuelle `lv1_patch_map.json` sert de secours.

## Utilisation
**Avec Python** : `python x32_gain_recall.py` (ou double-clic sur `Lancer_X32_Gain_Recall.bat`), puis entrer l'IP de la X32 (Setup → Network) et *Connecter*, ou *Scanner* pour la trouver automatiquement sur le réseau local. Option `--sim` : X32 simulée, sans console.

**Exécutable Windows** : **un seul fichier**, `XM32_Gain_Recall_LV1.exe`, dans l'onglet *Releases* du dépôt (généré automatiquement par GitHub Actions à chaque tag `vX.Y.Z`) — depuis la 1.5.0, il n'y a plus de second exe à télécharger ni à ranger au même endroit : la fenêtre flottante est intégrée au même fichier. Non signé : Windows SmartScreen / antivirus peuvent le signaler ; comparer avec le fichier `.sha256` fourni. **Installation : télécharger ce seul fichier, double-clic dessus — rien d'autre.**

### Fenêtre compagnon (mode réduit, toujours au premier plan)
Bouton **« Float »** dans la barre du haut du navigateur : lance la fenêtre flottante sans quitter le navigateur ni chercher aucun fichier (depuis la 1.5.0, c'est littéralement le même exécutable qui se relance lui-même avec un drapeau interne `--float` — plus un second `.exe` à gérer). **À réserver au cas où le navigateur et le serveur tournent sur la même machine** (PC qui héberge aussi la LV1) : ce bouton lance le processus sur la machine qui exécute `x32_gain_recall.py`, pas sur l'appareil où la page est affichée — cliqué depuis une tablette connectée au serveur via le réseau local, il ouvre la fenêtre sur le PC, pas sur la tablette (qui ne peut de toute façon pas exécuter de script Python ni d'exe Windows).

`x32_gain_float.py` (ou `Lancer_X32_Gain_Float.bat` pour l'usage Python source, ou `XM32_Gain_Recall_LV1.exe --float` pour l'exe) ouvre une petite fenêtre sans bordure, toujours visible par-dessus les autres applis, avec juste les potards de gain + 48V + une diode de niveau d'une banque de 16 voies — sans les faders. Faite pour être posée **sur** la LV1, dans l'espace entre la rangée A/B et la rangée Ø : glisser le point vert pour la placer, le coin en bas à droite pour caler largeur et hauteur sur les 16 tranches (réglage mémorisé par écran). Depuis la 2.2.0, plus de barre en haut : une **languette à gauche** des voies, avec le point vert (poignée), la flèche de repli et le menu **⋯** (banque, largeur, Scènes, Routing, console, verrou, fond Anthracite / Noir / Or / Bleu nuit, version, fermer).

**Intégrée à la LV1** (2.2.0) : devant la LV1 mais derrière les autres applis ; cachée quand la LV1 est réduite ou affiche un autre onglet que Mixer 1 / Mixer 2 ; suit la couche affichée (Ch 1-16 …, Custom, Talk Back sur Masters ; configurations 16 à 80 canaux), le mode (dépliée en SndChk / Setup, repliée ailleurs) et l'entrée A/B de chaque canal ; une colonne sans préampli X32 est transparente (on voit et on clique la LV1 en dessous).

**Vue LV1 / vue X32** (menu des banques, depuis la 2.1.0) :
- **LV1 Ch 1-16, 17-32…** : une colonne par **canal LV1**, dans l'ordre des tranches de la LV1. Posé sur la LV1, chaque potard tombe au-dessus de son canal. Un canal **stéréo** montre ses deux préamplis dans sa colonne (deux petits potards, deux petits 48V, « L 8/9 = EXP 8/9 ») ; les deux gains restent indépendants sur la X32. Un canal qui ne reçoit rien de la X32 garde une colonne vide. Les colonnes suivent les repatchs en direct.
- **Local 1-16, A 1-16…** : une colonne par **préampli X32**, comme avant (utile pour un préampli qui n'arrive sur aucun canal LV1).

Le navigateur a les mêmes banques (panneau *Banques d'entrées*).

**Fenêtre repliée** (flèche ◂) : il ne reste que le point de connexion et la flèche, à gauche du canal 1. Le point vert sert de poignée pour déplacer la fenêtre.

Depuis la 1.7.0, la **barre de connexion** (IP, Connecter, Scanner, Démo) est **en haut**, et la barre de titre (repli/zoom, banque, Scènes, Routing, verrou) juste en dessous — ordre inversé par rapport aux versions précédentes, à la demande. Les deux barres ont leur propre zone de glisser-déposer dédiée (pointillés ⋯), toujours large, pour déplacer la fenêtre au doigt même repliée (quand elle n'est plus qu'un simple bandeau de titre). Boutons de repli (▾/▸) et de taille (−/+) regroupés à **gauche** de la barre de titre, agrandis pour le doigt, depuis la 1.5.0. Boutons globalement plus contrastés (couleurs par rôle, contours visibles) depuis la 1.7.0 — précision : tkinter ne fait pas de vrais bords arrondis sur un bouton natif, l'effet est simulé par un contour, pas un arrondi réel.

**Par défaut, c'est la même appli que dans le navigateur** : la fenêtre flottante se connecte en HTTP à `x32_gain_recall.py` déjà lancé sur la même machine (port 8032 par défaut) — même connexion OSC, même état. **Il faut donc avoir lancé `x32_gain_recall.py` (ou son `.exe`) avant d'ouvrir la fenêtre flottante.** Une barre de connexion (IP, Connecter, Scanner, Démo) est directement intégrée à la fenêtre flottante — pas besoin de garder l'onglet navigateur ouvert, se connecter depuis l'un connecte aussi l'autre :
```
python x32_gain_float.py                  # se connecte à x32_gain_recall.py sur 127.0.0.1:8032
python x32_gain_float.py --port 8033      # si l'appli principale a pris un autre port (affiché dans son terminal)
```
Si l'appli principale tourne avec son code d'accès réseau local (par défaut depuis la 1.3), la fenêtre flottante le demande automatiquement au premier lancement.

Pour se passer complètement du navigateur, `--direct` fait une connexion OSC indépendante à la console (reprend l'ancien comportement de la 1.4.0) :
```
python x32_gain_float.py --direct --ip 192.168.1.50
python x32_gain_float.py --direct --sim
```

**Nécessite tkinter**, inclus par défaut avec l'installeur officiel python.org (case « tcl/tk and IDLE » cochée par défaut) — pas une dépendance à installer séparément, mais à ne pas décocher à l'installation. L'exécutable Windows des Releases n'a pas ce problème (tkinter est inclus dedans).

**Couleurs et noms des canaux LV1** : une pastille en haut de chaque voie du float (et le bandeau du haut dans le navigateur) prend la couleur du canal LV1 qui reçoit ce préampli, avec son nom (ex. « FireRoom », ou « In N » si le canal n'a pas été renommé). Depuis la 2.0.0, tout est lu **directement dans la LV1** (sa base de travail, voir plus bas), sans [Bitfocus Companion](https://bitfocus.io/companion). Companion reste utilisable en option (`--companion [URL]`, défaut `http://127.0.0.1:8000`, module communautaire `companion-module-waves-lv1`) : ses valeurs passent alors en priorité. `--no-colors` masque couleurs et noms. Pastille grise tant que la couleur n'est pas connue — jamais une couleur inventée.

**Patch LV1 suivi en direct (EXP → canal), depuis la 1.9.0.** La LV1 range ses couleurs par *canal* (« In 19 »), alors que la X32 ne connaît que le numéro *EXP* de chaque préampli ; le lien entre les deux, c'est le patch LV1, qu'**aucun message OSC n'expose** (vérifié). Exemple réel : In 19 (stéréo) ← EXP 21 + EXP 22, et EXP 1 → In 2. La 1.8.0 supposait « EXP N → In N » et affichait donc souvent la couleur d'un autre canal.

**Rien à configurer quand la LV1 tourne sur le même PC** : la LV1 écrit son patch en continu, **sans sauvegarde**, dans sa base de travail `C:\Users\Public\Waves Audio\eMotion\Sessions\CurrentLV1.dat` (même format SQLite qu'une session `.emo`). Un repatch y apparaît environ **1 seconde** plus tard (mesuré sur LV1 V17), et l'appli la relit à chaque écriture : la table suit les repatchs toute seule. L'appli lit toujours une **copie** de ce fichier, jamais l'original, pour ne rien verrouiller ni créer dans les dossiers de la LV1.

Seules les routes depuis la **carte DN32-WSG ou X-WSG** de la X32 comptent (reconnue par son modèle, ou par le nom « X32RACK » ; sa voie N = EXP N), en entrée A ou B, quelle que soit celle qui est sélectionnée. La **voie droite d'un canal mono** est ignorée : repasser un canal stéréo en mono ne supprime pas sa vieille route dans la base de la LV1 (la largeur est lue dans la table `chainer`). Un EXP qui n'arrive sur aucun canal reste **sans couleur**. TracksLive n'est pas pris par défaut, car il ne rejoue pas forcément les voies X32 avec les mêmes numéros ; `--lv1-device X32RACK,TracksLive:B` l'ajoute en repli, sans jamais l'emporter sur une route X32RACK.

Autres sources, si besoin :
- **Table manuelle** `lv1_patch_map.json` à côté des scènes (non versionné ; partir de [`lv1_patch_map.example.json`](lv1_patch_map.example.json)), au format `{"19": [21, 22], "1": [1]}` — canal LV1 → numéro(s) EXP. Relue à chaud, **prioritaire** canal par canal : pour forcer un canal. Autre emplacement : `--lv1-map CHEMIN`.
- **Autre session** : `--lv1-session FICHIER.emo`, ou `--lv1-session DOSSIER` (ex. le dossier `History`) pour relire la sauvegarde la plus récente — utile si la LV1 tourne sur un autre PC dont on partage le dossier. `--lv1-sans-session` : table manuelle seulement.
```
python -m lv1.session_patch --live                                    # voir le patch actuel de la LV1 (toutes les routes A/B)
python -m lv1.session_patch MA_SESSION.emo --json lv1_patch_map.json  # amorcer une table manuelle depuis une session
```
L'état de la table (source lue, erreurs, EXP affectés à plusieurs canaux) est affiché au lancement dans le terminal et renvoyé par `/api/state` (champ `lv1`). La table est tenue par l'appli principale ; le float la lit via elle (ou lit lui-même les mêmes sources en `--direct`). Le dossier [`lv1/`](lv1/) contient aussi `osc_sniffer.py`, l'outil de diagnostic qui a permis de confirmer l'absence d'info de patch dans le flux OSC (pas utilisé par l'appli).

Boutons **Scènes** et **Routing** dans la barre de titre : ouvrent un panneau (la fenêtre s'agrandit) pour sauvegarder, rappeler, **renommer, supprimer ou écraser** une scène de gains (ces trois derniers depuis la 1.7.0 — avant, seul « Charger » était disponible ici, il fallait repasser par le navigateur), ou charger un profil de routing, avec confirmation avant tout envoi/écrasement/suppression. Reste simplifié par rapport au navigateur sur deux points précis : pas d'option 48V au rappel, pas de patch de sortie console, pas d'import de `.scn` — pour ça, utiliser le navigateur. Le fichier `x32_presets.json` est partagé avec le navigateur : une scène sauvegardée, renommée, écrasée ou supprimée depuis l'un se reflète dans l'autre. Bouton **▾/▸** pour replier toute la fenêtre en une simple barre de titre et libérer de la place sur l'écran de la LV1. Le glisser sur un potard est volontairement moins sensible que dans la 1.4.1 pour le tactile (`--sensitivity` pour ajuster) ; cliquer sur la valeur en dB permet de taper le chiffre exact.

Pas d'alignement automatique avec la fenêtre LV1 réelle : ça dépend de votre résolution d'écran et du zoom de la LV1, qu'on ne peut pas deviner depuis ici — à régler à la main une fois, puis c'est mémorisé. La diode de niveau n'est pas le vrai détecteur de clip de la console (voir [CHANGELOG](CHANGELOG.md)), c'est une approximation par seuil sur le niveau mesuré.

### Où sont mes données ?
Depuis la 2.0.0, dans **`%APPDATA%\X32 Gain Recall`** (séparé de l'exe : on peut télécharger une nouvelle version n'importe où sans perdre ses scènes) :
- `x32_presets.json` (scènes de gains) et `x32_routings.json` (profils de routing) ;
- `x32_lan_config.json` (code d'accès tablette), `x32_float_config.json` (position/taille du float), `lv1_patch_map.json` (facultatif) ;
- `x32_gain_recall_settings.json` (dossier des scènes choisi).

**Choisir un autre dossier pour les scènes** (clé USB, dossier synchronisé…) : panneau *Scènes* du navigateur → **Dossier…** — taper un chemin ou *Parcourir…* (la fenêtre de choix s'ouvre sur le PC de l'appli). Si le dossier contient déjà des scènes, elles sont utilisées ; sinon l'appli propose d'y copier les scènes actuelles. *Dossier par défaut* ramène à `%APPDATA%\X32 Gain Recall`. Le choix est mémorisé.

Au premier lancement de la 2.0.0, les fichiers que les versions précédentes rangeaient à côté de l'exe y sont **recopiés** (pas déplacés). `--data FICHIER` force un fichier de scènes pour une session. Fichiers non versionnés (voir `.gitignore`).

### Accès depuis une tablette ou un téléphone
Depuis la 1.3, l'interface est accessible au réseau local **par défaut**, sans rien à taper au lancement : elle génère un **code à 4 chiffres** et l'affiche dans le terminal avec une adresse par appareil réseau détecté :
```
CODE D'ACCES : 6187
Accessible depuis une tablette/telephone sur le meme reseau :
  - http://192.168.x.x:8032/
```
Depuis la 1.5.0, ce code est aussi affiché **directement dans l'interface web** (bouton en haut à droite, « 🔑 Code : 6187 »), visible depuis le PC qui héberge le serveur — plus besoin d'aller chercher la fenêtre du terminal pour le retrouver. Ce bouton ouvre un panneau avec la version, l'adresse locale, les adresses réseau et le code (depuis la 1.6.0) ; il permet aussi de **générer un nouveau code sans relancer le serveur** (« Nouveau code… ») — déconnecte tous les appareils déjà connectés avec l'ancien code, sauf la page qui a fait le changement.

Sur la tablette, ouvre simplement ce lien (rien à copier-coller) : un écran de connexion avec un clavier numérique demande le code. Une fois tapé, un cookie garde l'accès pour ce navigateur (jusqu'à 30 jours), sans avoir à ressaisir le code à chaque fois — sauf si le script est relancé (les sessions ne sont gardées qu'en mémoire, pas sur disque).

Le code est sauvegardé dans `x32_lan_config.json` (non versionné, comme les scènes) et reste le même d'un lancement à l'autre, sauf relance avec `--lan-nouveau-code` (par exemple en fin de contrat, ou si le code a été vu par quelqu'un qui ne devrait plus avoir accès). Au-delà de 5 codes faux d'affilée depuis une même adresse, l'appli impose une pause croissante (30 s, 1 min, 2 min...) avant de réessayer, pour ralentir un brute-force du code.

`--lan-sans-mdp` désactive cette protection pour qui préfère l'usage sans mot de passe des applis officielles Behringer (X-AIR Edit, M32-Edit). `--local-only` revient à l'ancien comportement (avant la 1.3) : accessible seulement depuis cette machine, sans code. Dans tous les cas où le réseau est ouvert, la connexion reste en **http, non chiffrée** : à réserver à un réseau de confiance (pas un Wi-Fi public de festival), jamais exposé directement sur Internet. Un code à 4 chiffres (10 000 combinaisons) protège d'un tiers qui tomberait sur l'interface par hasard, pas d'un attaquant déterminé qui a déjà accès à ce réseau : c'est un compromis d'usage assumé, pas un vrai mot de passe.

## Limites connues (non vérifiées sur console réelle)
Développé d'après la documentation OSC non officielle de la X32 et testé uniquement contre un simulateur : les formats de requête (meters, nodes de routing) restent à valider sur une vraie X32. L'appli relit la console après chaque envoi et signale les écarts. Faire un essai hors show avant tout usage en live.

## Versionner / publier une version
1. Modifier `APP_VERSION` dans `x32_gain_recall.py` et compléter `CHANGELOG.md`.
2. `git commit`, puis `git tag vX.Y.Z` et `git push --follow-tags`.
3. GitHub Actions compile l'`.exe` sous Windows et l'attache à la release (le tag doit être égal à `APP_VERSION`).

## Avertissement
Projet indépendant, non affilié à Behringer / Music Tribe ni à Waves. « X32 », « M32 », « LV1 » et « eMotion » appartiennent à leurs propriétaires. Protocole : [UNOFFICIAL X32/M32 OSC REMOTE PROTOCOL](https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf) (P.-G. Maillot).

Licence : à définir par l'auteur.

---
Outil indépendant, non affilié à Behringer, Midas ni Waves. X32, M32, eMotion LV1 et SoundGrid sont des marques de leurs propriétaires respectifs.
