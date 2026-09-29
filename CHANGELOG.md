# Changelog

Format : [SemVer](https://semver.org/lang/fr/). Historique reconstitué à partir des étapes de développement.

## [1.3.0]
- **L'interface est accessible au réseau local par défaut** (tablette, téléphone, autre PC), sans rien à taper au lancement. Nouvelle option `--local-only` pour revenir à l'ancien comportement (versions ≤ 1.2 : accessible uniquement depuis cette machine, 127.0.0.1).
- Accès protégé par défaut par un **code à 4 chiffres**, saisi une fois sur un petit écran de connexion (clavier numérique tactile, pas de copier-coller) ; une fois validé, une session en mémoire (cookie) garde l'accès. Code sauvegardé dans `x32_lan_config.json` (jamais versionné) ; nouveau code avec `--lan-nouveau-code`. Limitation des tentatives après 5 codes faux (pause croissante, jusqu'à 15 min).
- `--lan-sans-mdp` désactive volontairement cette protection pour qui préfère l'usage sans mot de passe des applis officielles Behringer (X-AIR Edit, M32-Edit) sur un réseau de confiance.
- Numéro de version affiché directement dans l'interface (en haut à droite), plus seulement via `--version`.

## [1.2.0]
- Onglet Routing : chargement direct d'un routing X32 (profil « Routing LV1 » intégré : X32 Rack + DN32-WSG + S16), aperçu des différences, vérification par relecture, annulation.
- Import de scènes .scn (seules les lignes de routing sont utilisées).

## [1.1.0]
- Vumètre d'entrée discret sur chaque voie (on/off), correspondance headamp/voie via /-ha/NN/index.

## [1.0.0]
- Réglage, sauvegarde et rappel des gains de préampli (128 headamps), 48 V protégé, verrou, annulation, simulateur intégré.
