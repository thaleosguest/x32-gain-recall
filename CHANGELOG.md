# Changelog

Format : [SemVer](https://semver.org/lang/fr/). Historique reconstitué à partir des étapes de développement.

## [1.3.0]
- Nouvelle option `--lan` : ouvre l'interface au réseau local (tablette, téléphone, autre PC), au lieu de la seule machine qui exécute le script.
- Accès protégé par défaut par un jeton généré automatiquement (`?token=...` puis cookie), sauvegardé dans `x32_lan_config.json` (jamais versionné). Nouveau jeton avec `--lan-nouveau-jeton`.
- `--lan-sans-mdp` désactive volontairement cette protection pour qui préfère l'usage sans mot de passe des applis officielles Behringer (X-AIR Edit, M32-Edit) sur un réseau de confiance.
- Le mode par défaut (sans `--lan`) est inchangé : écoute uniquement sur cette machine (127.0.0.1), sans jeton.

## [1.2.0]
- Onglet Routing : chargement direct d'un routing X32 (profil « Routing LV1 » intégré : X32 Rack + DN32-WSG + S16), aperçu des différences, vérification par relecture, annulation.
- Import de scènes .scn (seules les lignes de routing sont utilisées).

## [1.1.0]
- Vumètre d'entrée discret sur chaque voie (on/off), correspondance headamp/voie via /-ha/NN/index.

## [1.0.0]
- Réglage, sauvegarde et rappel des gains de préampli (128 headamps), 48 V protégé, verrou, annulation, simulateur intégré.
