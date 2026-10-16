<img src="assets/logo.svg" width="96" alt="Logo">

# X/M32 Gain Recall for eMotion LV1

*by Joseph Savigny*

Les **préamplis d'une Behringer X32 / Midas M32 directement sur l'écran de la Waves eMotion LV1** : gain et
48V posés au-dessus de chaque tranche, aux couleurs des canaux LV1, plus le rappel de gains par scène et le
routing de la console. Un seul exe Windows, sans installation.

Version courante : **3.0.0** (voir [CHANGELOG](CHANGELOG.md)). Première fois ? Voir le
**[mode d'emploi pas à pas](MODE_EMPLOI.md)**.

## Pourquoi

Quand la LV1 reçoit les micros d'une X32 / M32 par sa carte SoundGrid (**DN32-WSG** ou **X-WSG**, voies
« EXP 1-32 »), les préamplis restent sur la console : pour régler un gain ou un 48V, il faut quitter la LV1
et retrouver de tête quel micro arrive sur quelle tranche. L'appli fait ce lien toute seule et met les
réglages sur la tranche LV1 concernée.

## Fonctions

**Sur la LV1 (le « float »)**
- **Multi-touch** (3.0) : un doigt par potard, plusieurs potards en même temps, au milieu de la LV1.
- Potards de gain (−12 à +60 dB) et 48V **calés au pixel** dans les cadres Preamp des 16 tranches, quelle que
  soit la taille de l'écran ou de la fenêtre LV1 ; suit la **section Input** où qu'elle soit (Top / Middle /
  Bottom). Languette (logo, repli, menu) dans la barre du haut de la LV1.
- Suit la **couche** affichée (Ch 1-16…, Custom, Talk Back), le **mode**, l'**entrée A/B** de chaque canal,
  les configurations 16 à 80 canaux, mono et stéréo ; une tranche sans préampli X32 reste transparente.
- **Mode Edit** : réglage de la tranche sélectionnée dans le bloc Input. **Page Channel** : réglage du canal
  affiché (suit « < » / « > »).
- **Plusieurs consoles** (une carte chacune dans le rack de la LV1) : le float règle les préamplis de toutes.
- Tactile : grosses zones de toucher, bulle des dB pendant le réglage, confirmation du 48V avec voyant,
  panneaux (scènes, routing, consoles) qui défilent au doigt.

**Scènes et routing**
- **Scènes de gains** : enregistrer / rappeler (vérification par relecture, annulation), sur toutes les
  consoles connectées ; le 48V n'est jamais rappelé par défaut.
- **Routing** de la console : profils prêts à charger (X32R + S16, X32R + 2 S16, M32C + 2 S16, M32C + X32 en
  stage box) et **éditeur en matrice** pour un routing à soi, EXP par EXP ; aperçu, vérification, annulation,
  console par console.

**Plug and play**
- Trouve la console sur le réseau et s'y reconnecte ; lit patch, noms et couleurs **dans la LV1** (rien à
  configurer côté LV1 : ni Companion, ni MyRemote).
- Icône près de l'horloge (Ouvrir la page, Afficher le float, Lancer avec Windows, Quitter), une seule
  instance, avis de mise à jour.
- Page web locale, utilisable aussi depuis une tablette / un téléphone (code à 4 chiffres).

## Démarrage rapide (PC de la LV1)

1. Télécharger **`XM32_Gain_Recall_LV1.exe`** (onglet *Releases*) et le lancer.
2. Premier lancement : **SmartScreen** (« Windows a protégé votre ordinateur », exe non signé) →
   *Informations complémentaires* → *Exécuter quand même* ; **pare-feu** : autoriser les réseaux **privés**.
3. C'est tout : l'appli trouve la console, ouvre le float calé sur la LV1, ouvre la page web réduite dans la
   barre des tâches et remet la LV1 au premier plan.

Conditions : l'appli tourne sur **le même PC que la LV1** (sinon gains, scènes et routing marchent, sans
couleurs ni intégration LV1) ; testé sur **LV1 V17** ; **un seul écran** (pages détachées sur un 2e écran : pas
prises en charge en 3.0, rester en 2.7.1).

## Comment ça marche

- **Côté console** : OSC (UDP 10023) — gains, 48V, vumètres, et tout le routing (`/config/routing/*`,
  `/config/userrout/*`, `/outputs/*`). Le numéro EXP de chaque préampli est relu en direct dans le routing.
- **Côté LV1** : lecture de sa base de travail `C:\Users\Public\Waves Audio\eMotion\Sessions\CurrentLV1.dat`
  (SQLite, réécrite ~1 s après chaque changement, sans sauvegarde) : patch canal ← carte/voie, noms, couleurs,
  entrée A/B, couches, mode affiché, sections Top / Middle / Bottom et Big Fader. Toujours sur une **copie** (jamais de verrou sur les fichiers de la LV1).
  Aucun message OSC de la LV1 ne donne le patch (vérifié).
- **Ce que la LV1 n'écrit nulle part** (onglet affiché, tranche sélectionnée, canal de la page Channel, pages
  détachées) est **lu à l'écran**, sur un fil séparé, et toujours vérifié contre le patch.
- **Jamais deviné** : un préampli qui n'arrive sur aucun canal reste gris ; en cas de doute, rien n'est
  affiché plutôt que le préampli d'un autre canal.
- **Plusieurs consoles** : chaque route LV1 porte la position de sa carte dans le rack (le « 2- » de
  « 2-EX 1 ») ; chaque console est associée à sa carte (par le nom, ou choisie dans ⋮ → Consoles…).

Sources de secours pour le patch LV1 :
- **Table manuelle** `lv1_patch_map.json` (dans le dossier des données ; modèle :
  [`lv1_patch_map.example.json`](lv1_patch_map.example.json)), format `{"19": [21, 22], "1": [1]}` (canal LV1 →
  EXP), relue à chaud, prioritaire canal par canal.
- `--lv1-session FICHIER.emo` ou un dossier (ex. `History`) ; `--lv1-sans-session` : table manuelle seulement.

```
python -m lv1.session_patch --live                                    # voir le patch actuel de la LV1
python -m lv1.session_patch MA_SESSION.emo --json lv1_patch_map.json  # amorcer une table manuelle
```

## Données

Dans **`%APPDATA%\X32 Gain Recall`** (séparé de l'exe : une nouvelle version ne perd rien) : scènes
(`x32_presets.json`), routings (`x32_routings.json`), code tablette, réglages du float, consoles et cartes
(`x32_gain_recall_settings.json`), chiffres appris de la page Channel, journaux (`x32_gain_recall.log`,
`x32_float.log`). Le dossier des scènes peut être déplacé (page web, panneau Scènes → *Dossier…*).

## Accès tablette / téléphone

Ouvert au réseau local par défaut, protégé par un **code à 4 chiffres** (bouton 🔑 de la page du PC, qui
donne aussi l'adresse à ouvrir). Pas de code sur le PC de l'appli lui-même. Connexion **http non chiffrée** :
réseau de confiance seulement. Au-delà de 5 codes faux, pause croissante.

## Utilisation avec Python (développement)

```
python x32_gain_recall.py            # appli complète (serveur, page web, float, icône)
python x32_gain_recall.py --sim      # avec une X32 simulée, sans console
python x32_qt_float.py --direct --ip 192.168.1.50     # float seul, connexion directe à la console
python x32_gain_recall.py --tk-float # avec l'ancien float (tk, 2.x)
```

Options utiles de `x32_gain_recall.py` : `--ip`, `--web-port` (défaut 8032), `--no-browser`, `--no-float`,
`--no-update-check`, `--data`, `--local-only` (pas d'accès réseau), `--lan-sans-mdp`, `--lan-nouveau-code`,
`--lv1-map`, `--lv1-session`, `--lv1-sans-session`, `--lv1-device`, `--companion [URL]` (facultatif),
`--no-colors`. Float : `--port`, `--direct`, `--ip`, `--sim`, `--sensitivity`, `--clip-db`.
Python 3.8+ ; float : PySide6 (`pip install PySide6-Essentials`), sinon l'ancien float tk est utilisé. La diode de niveau du float est un seuil sur le
niveau mesuré, pas le détecteur de clip de la console.

## Publier une version

1. `APP_VERSION` dans `x32_gain_recall.py` et section dans `CHANGELOG.md`.
2. Fusionner dans `main`, tag annoté `vX.Y.Z` (= `APP_VERSION`), `git push origin vX.Y.Z`.
3. GitHub Actions compile l'exe (sans console), le teste et publie la release avec son `.sha256`.

## Limites

- Windows seulement ; la LV1 sur le même PC pour l'intégration ; un seul écran (3.0).
- Testé sur LV1 V17 : une mise à jour de la LV1 peut demander une adaptation.
- Page Channel lue en plein écran 1920x1080 et en fenêtre 1728x970 (autre taille : zone vide).
- Plusieurs consoles : testé avec une X32 et le simulateur, pas encore avec trois consoles réelles.

## Avertissement

Projet indépendant, non affilié à Behringer / Midas / Music Tribe ni à Waves. X32, M32, eMotion LV1 et
SoundGrid sont des marques de leurs propriétaires. Protocole : [UNOFFICIAL X32/M32 OSC REMOTE
PROTOCOL](https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf) (P.-G. Maillot).

Licence : à définir par l'auteur.
