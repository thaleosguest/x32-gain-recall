# X32 Gain Recall

Petit outil pour **régler, sauvegarder et rappeler les gains** (et le routing, dès la v1.2) d'une Behringer X32 / Midas M32 par le réseau (OSC, UDP 10023). Interface web locale, style Waves eMotion LV1. Aucune dépendance : Python 3.8+ (bibliothèque standard).

Version courante : **1.1.0** (voir [CHANGELOG](CHANGELOG.md)).

## Fonctions
- Réglage des gains (−12 à +60 dB, pas de 0,5) des 128 préamplis : entrées locales, AES50-A, AES50-B.
- Scènes de gains : sauvegarder, rappeler (avec confirmation, relecture de vérification et annulation), export/import JSON.
- +48 V : confirmation à l'activation, jamais rappelé par défaut. Verrou d'édition. Déplacement relatif (un clic ne change rien).
- Vumètre d'entrée discret sur chaque voie (on/off).

## Utilisation
**Avec Python** : `python x32_gain_recall.py` (ou double-clic sur `Lancer_X32_Gain_Recall.bat`), puis entrer l'IP de la X32 (Setup → Network) et *Connecter*. Option `--sim` : X32 simulée, sans console.

**Exécutable Windows** : dans l'onglet *Releases* du dépôt (généré automatiquement par GitHub Actions à chaque tag `vX.Y.Z`). Non signé : Windows SmartScreen / antivirus peuvent le signaler ; comparer avec le fichier `.sha256` fourni.

Les scènes sont enregistrées à côté du programme (`x32_presets.json`, `x32_routings.json`), non versionnées (voir `.gitignore`).

## Limites connues (non vérifiées sur console réelle)
Développé d'après la documentation OSC non officielle de la X32 et testé uniquement contre un simulateur : les formats de requête (meters, nodes de routing) restent à valider sur une vraie X32. L'appli relit la console après chaque envoi et signale les écarts. Faire un essai hors show avant tout usage en live.

## Versionner / publier une version
1. Modifier `APP_VERSION` dans `x32_gain_recall.py` et compléter `CHANGELOG.md`.
2. `git commit`, puis `git tag vX.Y.Z` et `git push --follow-tags`.
3. GitHub Actions compile l'`.exe` sous Windows et l'attache à la release (le tag doit être égal à `APP_VERSION`).

## Avertissement
Projet indépendant, non affilié à Behringer / Music Tribe ni à Waves. « X32 », « M32 », « LV1 » et « eMotion » appartiennent à leurs propriétaires. Protocole : [UNOFFICIAL X32/M32 OSC REMOTE PROTOCOL](https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf) (P.-G. Maillot).

Licence : à définir par l'auteur.
