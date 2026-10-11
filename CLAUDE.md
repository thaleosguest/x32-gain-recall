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

## État actuel (v1.8.0)

- La fonctionnalité "pastille de couleur par voie" dans la fenêtre flottante
  est **déjà implémentée**, via l'API HTTP du module Companion Waves LV1
  (pas via un pont OSC direct — voir plus bas pourquoi).
- Companion tourne en continu sur le PC pendant les prestations, et sert de
  pont fiable pour récupérer les couleurs de canaux de la LV1 (elles arrivent
  dès la connexion et se mettent à jour en direct quand on les change dans
  la LV1).

## Limitation confirmée — couleur indexée par canal, pas par source physique

Lecture complète du code source du module Companion officiel
(`bitfocus/companion-module-waves-lv1`) + sniff OSC en direct (3 repatchs
testés manuellement) :

- La couleur LV1 est indexée **par canal de mixage** (ex. `in19_color`), **pas**
  par source physique/EXP.
- **Aucun message OSC de patch/routage canal → source physique n'existe** dans
  le protocole LV1 (ni dans le module Companion, ni observé en sniffant le flux
  OSC brut pendant des repatchs réels).
- Conclusion actée : impossible de suivre dynamiquement, par OSC, quelle
  source EXP alimente quel canal. **Décision retenue : construire à la main**
  une table de correspondance canal → sources physiques dans l'appli (ex.
  canal 19 (stéréo) → EXP 21 + EXP 22), plutôt que d'attendre une information
  que la LV1 ne fournit jamais par ce biais.

## Découverte technique annexe — fichiers de session LV1 (`.emo`)

Un fichier de session Waves eMotion LV1 (`.emo`) est en réalité une base
**SQLite**. La table `routes` contient la matrice de patch complète :

- `dst_cluster_type = 0` → "Input" (canaux de la console)
- `src_cluster_type = 10` → "Inputs" (devices sources : X32RACK, TracksLive-FL/EXP, etc.)
- `status = 1` → route active

Cette info *est* exploitable statiquement (à partir d'un fichier `.emo` sauvegardé),
contrairement au flux OSC live qui n'expose jamais ce lien. Vérifié sur un cas réel :
canal 19 ↔ device "TracksLive-FL" (assign=2, 96 canaux EXP), `src_channel_index` 20 et 21
(0-based) = EXP 21 et EXP 22 — cohérent avec l'affichage LV1.

Script écrit pour extraire cette matrice : `lv1_session_patch_export.py`
(usage ponctuel sur un fichier, ou mode `--watch-dir` sur le dossier `History`
si "Auto Save Every X Minutes" est activé dans la LV1 — régénère un JSON à
chaque nouvelle sauvegarde).

Piste explorée mais écartée pour le live : écoute brute du flux OSC-sur-TCP
(`lv1_osc_sniffer.py`, reproduit le protocole du module Companion : framing
4 octets longueur + 8 octets en-tête + payload OSC, handshake "MyFOH",
keep-alive ping/pong) — confirmé qu'aucune adresse OSC de patch n'y transite.

## À faire

1. Cloner le repo dans `x32-gain-recall-workspace` (`git clone ... .`).
2. Créer un sous-dossier `lv1/` et y placer :
   - `lv1_session_patch_export.py`
   - `lv1_osc_sniffer.py`
3. **Décision d'architecture à prendre** : regrouper le tracker de couleurs LV1
   et l'appli X32 en **une seule appli** (pas deux outils séparés) — c'est le
   souhait exprimé, reste à définir comment (module importé dans
   `x32_gain_recall.py`, ou processus séparé communiquant par fichier/IPC).
4. Construire la table de correspondance canal → sources EXP à la main
   (cf. limitation ci-dessus) et la câbler à l'affichage de couleur déjà
   existant dans la fenêtre flottante.

## Environnement cible

- PC hôte : laptop "portable-js" (i7-8750H, 16 Go RAM, Windows 10 IoT
  Enterprise LTSC 2021) ou tour i5-3570K — hôtes dédiés LV1.
- LV1 V17.
- Toolbox Reaper annexe (ReaScript) déjà existante pour l'intégration LV1,
  sans lien direct avec ce projet mais dans le même écosystème studio.
