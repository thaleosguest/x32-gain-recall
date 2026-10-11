# X32 Gain Recall

Petit outil pour **régler, sauvegarder et rappeler les gains** (et le routing, dès la v1.2) d'une Behringer X32 / Midas M32 par le réseau (OSC, UDP 10023). Interface web locale, style Waves eMotion LV1. Aucune dépendance : Python 3.8+ (bibliothèque standard).

Version courante : **1.6.0** (voir [CHANGELOG](CHANGELOG.md)).

## Fonctions
- Réglage des gains (−12 à +60 dB, pas de 0,5) des 128 préamplis : entrées locales, AES50-A, AES50-B.
- Numéro EXP (menu de patch de la LV1) affiché sur chaque voie, **lu en direct sur la console connectée** (`/config/routing/CARD` + `/config/userrout/in`) — reflète le patch réellement chargé, pas un profil supposé. Vide tant que non connecté, ou pour une voie non patchée vers la carte.
- Scènes de gains : sauvegarder, rappeler (avec confirmation, relecture de vérification et annulation), export/import JSON.
- +48 V : confirmation à l'activation, jamais rappelé par défaut. Verrou d'édition. Déplacement relatif (un clic ne change rien).
- Vumètre d'entrée discret sur chaque voie (on/off).
- Onglet Routing : charger en un clic un routing X32 (profil « Routing LV1 » intégré), avec aperçu des différences, vérification et annulation.
- Bouton « Scanner » : recherche les X32/M32 sur le réseau local (broadcast `/xinfo`, voir [CHANGELOG](CHANGELOG.md)) ; la saisie manuelle de l'IP reste toujours possible si le scan ne trouve rien.
- Accès depuis une tablette/téléphone sur le réseau local (`--lan`), protégé par un jeton d'accès.

## Utilisation
**Avec Python** : `python x32_gain_recall.py` (ou double-clic sur `Lancer_X32_Gain_Recall.bat`), puis entrer l'IP de la X32 (Setup → Network) et *Connecter*, ou *Scanner* pour la trouver automatiquement sur le réseau local. Option `--sim` : X32 simulée, sans console.

**Exécutable Windows** : **un seul fichier**, `X32_Gain_Recall.exe`, dans l'onglet *Releases* du dépôt (généré automatiquement par GitHub Actions à chaque tag `vX.Y.Z`) — depuis la 1.5.0, il n'y a plus de second exe à télécharger ni à ranger au même endroit : la fenêtre flottante est intégrée au même fichier. Non signé : Windows SmartScreen / antivirus peuvent le signaler ; comparer avec le fichier `.sha256` fourni. **Installation : télécharger ce seul fichier, double-clic dessus — rien d'autre.**

### Fenêtre compagnon (mode réduit, toujours au premier plan)
Bouton **« Float »** dans la barre du haut du navigateur : lance la fenêtre flottante sans quitter le navigateur ni chercher aucun fichier (depuis la 1.5.0, c'est littéralement le même exécutable qui se relance lui-même avec un drapeau interne `--float` — plus un second `.exe` à gérer). **À réserver au cas où le navigateur et le serveur tournent sur la même machine** (PC qui héberge aussi la LV1) : ce bouton lance le processus sur la machine qui exécute `x32_gain_recall.py`, pas sur l'appareil où la page est affichée — cliqué depuis une tablette connectée au serveur via le réseau local, il ouvre la fenêtre sur le PC, pas sur la tablette (qui ne peut de toute façon pas exécuter de script Python ni d'exe Windows).

`x32_gain_float.py` (ou `Lancer_X32_Gain_Float.bat` pour l'usage Python source, ou `X32_Gain_Recall.exe --float` pour l'exe) ouvre une petite fenêtre sans bordure, toujours visible par-dessus les autres applis, avec juste les potards de gain + 48V + une diode de niveau d'une banque de 16 voies — sans les faders. Faite pour être glissée et redimensionnée (boutons −/+ en haut à gauche, ou glisser le coin en bas à droite) dans l'espace vide de l'interface Waves eMotion LV1, entre la rangée A/B et la rangée Ø. Position, taille et banque affichée sont mémorisées dans `x32_float_config.json` (non versionné) pour le prochain lancement.

Barre de titre pensée pour le tactile (depuis la 1.5.0) : boutons de repli (▾/▸) et de taille (−/+) regroupés à **gauche**, agrandis pour le doigt ; le reste de la barre (pointillés ⋯) est une zone de glisser-déposer dédiée, toujours large, pour déplacer la fenêtre au doigt même repliée (quand elle n'est plus qu'un simple bandeau de titre).

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

Boutons **Scènes** et **Routing** dans la barre de titre : ouvrent un panneau (la fenêtre s'agrandit) pour sauvegarder ou rappeler une scène de gains, ou charger un profil de routing, avec confirmation — version simplifiée de ce que propose le navigateur (pas d'option 48V, pas de renommer/supprimer/importer, pas de patch de sortie). Le fichier `x32_presets.json` est partagé avec le navigateur : une scène sauvegardée depuis l'un apparaît dans l'autre. Bouton **▾/▸** pour replier toute la fenêtre en une simple barre de titre et libérer de la place sur l'écran de la LV1. Le glisser sur un potard est volontairement moins sensible que dans la 1.4.1 pour le tactile (`--sensitivity` pour ajuster) ; cliquer sur la valeur en dB permet de taper le chiffre exact.

Pas d'alignement automatique avec la fenêtre LV1 réelle : ça dépend de votre résolution d'écran et du zoom de la LV1, qu'on ne peut pas deviner depuis ici — à régler à la main une fois, puis c'est mémorisé. La diode de niveau n'est pas le vrai détecteur de clip de la console (voir [CHANGELOG](CHANGELOG.md)), c'est une approximation par seuil sur le niveau mesuré.

Les scènes sont enregistrées à côté du programme (`x32_presets.json`, `x32_routings.json`), non versionnées (voir `.gitignore`).

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
