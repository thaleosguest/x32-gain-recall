# X32 Gain Recall

Petit outil pour **régler, sauvegarder et rappeler les gains** (et le routing, dès la v1.2) d'une Behringer X32 / Midas M32 par le réseau (OSC, UDP 10023). Interface web locale, style Waves eMotion LV1. Aucune dépendance : Python 3.8+ (bibliothèque standard).

Version courante : **1.3.0** (voir [CHANGELOG](CHANGELOG.md)).

## Fonctions
- Réglage des gains (−12 à +60 dB, pas de 0,5) des 128 préamplis : entrées locales, AES50-A, AES50-B.
- Scènes de gains : sauvegarder, rappeler (avec confirmation, relecture de vérification et annulation), export/import JSON.
- +48 V : confirmation à l'activation, jamais rappelé par défaut. Verrou d'édition. Déplacement relatif (un clic ne change rien).
- Vumètre d'entrée discret sur chaque voie (on/off).
- Onglet Routing : charger en un clic un routing X32 (profil « Routing LV1 » intégré), avec aperçu des différences, vérification et annulation.
- Accès depuis une tablette/téléphone sur le réseau local (`--lan`), protégé par un jeton d'accès.

## Utilisation
**Avec Python** : `python x32_gain_recall.py` (ou double-clic sur `Lancer_X32_Gain_Recall.bat`), puis entrer l'IP de la X32 (Setup → Network) et *Connecter*. Option `--sim` : X32 simulée, sans console.

**Exécutable Windows** : dans l'onglet *Releases* du dépôt (généré automatiquement par GitHub Actions à chaque tag `vX.Y.Z`). Non signé : Windows SmartScreen / antivirus peuvent le signaler ; comparer avec le fichier `.sha256` fourni.

Les scènes sont enregistrées à côté du programme (`x32_presets.json`, `x32_routings.json`), non versionnées (voir `.gitignore`).

### Accès depuis une tablette ou un téléphone (`--lan`)
Par défaut, l'interface n'écoute que sur la machine qui exécute le script (`127.0.0.1`) : aucun autre appareil ne peut s'y connecter, même sur le même Wi-Fi.

`python x32_gain_recall.py --lan` ouvre l'interface au réseau local, génère un **code à 4 chiffres** et l'affiche dans le terminal avec une adresse par appareil réseau détecté :
```
CODE D'ACCES : 6187
Accessible depuis une tablette/telephone sur le meme reseau :
  - http://192.168.x.x:8032/
```
Sur la tablette, ouvre simplement ce lien (rien à copier-coller) : un écran de connexion avec un clavier numérique demande le code. Une fois tapé, un cookie garde l'accès pour ce navigateur (jusqu'à 30 jours), sans avoir à ressaisir le code à chaque fois — sauf si le script est relancé (les sessions ne sont gardées qu'en mémoire, pas sur disque).

Le code est sauvegardé dans `x32_lan_config.json` (non versionné, comme les scènes) et reste le même d'un lancement à l'autre, sauf relance avec `--lan-nouveau-code` (par exemple en fin de contrat, ou si le code a été vu par quelqu'un qui ne devrait plus avoir accès). Au-delà de 5 codes faux d'affilée depuis une même adresse, l'appli impose une pause croissante (30 s, 1 min, 2 min...) avant de réessayer, pour ralentir un brute-force du code.

`--lan-sans-mdp` désactive cette protection pour qui préfère l'usage sans mot de passe des applis officielles Behringer (X-AIR Edit, M32-Edit). Dans les deux cas, la connexion reste en **http, non chiffrée** : à réserver à un réseau de confiance (pas un Wi-Fi public de festival), jamais exposé directement sur Internet. Un code à 4 chiffres (10 000 combinaisons) protège d'un tiers qui tomberait sur l'interface par hasard, pas d'un attaquant déterminé qui a déjà accès à ce réseau : c'est un compromis d'usage assumé, pas un vrai mot de passe.

## Limites connues (non vérifiées sur console réelle)
Développé d'après la documentation OSC non officielle de la X32 et testé uniquement contre un simulateur : les formats de requête (meters, nodes de routing) restent à valider sur une vraie X32. L'appli relit la console après chaque envoi et signale les écarts. Faire un essai hors show avant tout usage en live.

## Versionner / publier une version
1. Modifier `APP_VERSION` dans `x32_gain_recall.py` et compléter `CHANGELOG.md`.
2. `git commit`, puis `git tag vX.Y.Z` et `git push --follow-tags`.
3. GitHub Actions compile l'`.exe` sous Windows et l'attache à la release (le tag doit être égal à `APP_VERSION`).

## Avertissement
Projet indépendant, non affilié à Behringer / Music Tribe ni à Waves. « X32 », « M32 », « LV1 » et « eMotion » appartiennent à leurs propriétaires. Protocole : [UNOFFICIAL X32/M32 OSC REMOTE PROTOCOL](https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf) (P.-G. Maillot).

Licence : à définir par l'auteur.
