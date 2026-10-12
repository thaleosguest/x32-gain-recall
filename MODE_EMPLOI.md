<img src="assets/logo.svg" width="72" alt="Logo">

# Mode d'emploi — X/M32 Gain Recall for eMotion LV1 (v2.2.0)

*Pour ceux qui découvrent l'appli. Comptez 10 minutes la première fois, ensuite c'est un double-clic.*

---

## À quoi ça sert ?

La LV1 ne pilote pas les préamplis d'une X32 / M32 branchée sur sa carte SoundGrid. Cette appli
**affiche les gains et le 48 V de la X32 directement sur l'écran de la LV1**, au-dessus de chaque
tranche, avec le nom et la couleur du canal LV1. Elle sert aussi à **sauvegarder et rappeler** des
scènes de gains (une par groupe ou par date, par exemple).

## Ce qu'il faut avoir

| | |
|---|---|
| **Console** | Behringer X32 ou Midas M32, avec une carte **DN32-WSG** ou **X-WSG** branchée au réseau SoundGrid |
| **LV1** | Waves eMotion LV1 **V17**, sur un PC Windows |
| **Réseau** | Le PC de la LV1 et la X32 sur le **même réseau** (câble Ethernet de la X32, prise *Remote*) |
| **À installer** | Rien. Ni Python, ni Companion, ni MyRemote. |

> L'appli doit tourner **sur le même PC que la LV1**. Sur un autre PC, gains et scènes marchent,
> mais sans les noms ni les couleurs de la LV1.

---

## 1. Installer (une seule fois)

1. Sur la page [Releases](https://github.com/thaleosguest/x32-gain-recall/releases/latest),
   téléchargez **`XM32_Gain_Recall_LV1.exe`**.
2. Rangez-le où vous voulez (Bureau, `Documents`…). Vos réglages sont gardés ailleurs
   (`%APPDATA%\X32 Gain Recall`) : vous pourrez remplacer l'exe par une version plus récente
   sans rien perdre.
3. Double-cliquez dessus. La première fois, Windows pose deux questions :
   - **« Windows a protégé votre ordinateur »** (l'exe n'est pas signé) :
     *Informations complémentaires* → *Exécuter quand même*.
   - **Pare-feu** : cochez **Réseaux privés** puis *Autoriser*. Sans ça, *Scanner* ne trouvera
     pas la console et la tablette ne pourra pas se connecter.

## 2. Connecter la X32

1. Au lancement, trois fenêtres s'ouvrent :
   - le **float**, la petite fenêtre des potards (voir plus bas) ;
   - la **page de l'appli** dans le navigateur, **réduite dans la barre des tâches** pour ne pas passer
     devant la LV1 : cliquez-la pour l'ouvrir. Sur ce PC, pas de code à taper ;
   - une **fenêtre noire** de journal : **ne la fermez pas**, c'est l'appli. La fermer ferme aussi le
     float et l'onglet du navigateur.

   Une fois le float ouvert, **la LV1 repasse au premier plan** toute seule (si elle est lancée).
2. La première fois, dans la page : cliquez **Scanner** : la X32 apparaît dans la liste. Choisissez-la puis **Connecter**.
   - Rien trouvé ? Tapez l'IP de la console (sur la X32 : *Setup → Network*) puis **Connecter**.
3. Les potards de la page prennent les gains de la console. C'est connecté.
4. Les fois suivantes, l'appli **se reconnecte toute seule** à la dernière console. Si elle n'est pas
   encore allumée, l'appli attend et se connecte dès qu'elle répond (point orange, puis vert).

Pas de console sous la main ? **Démo** lance une X32 simulée pour essayer.

## 3. Vérifier que la LV1 est vue

Lancez la LV1 avec votre session. En haut de chaque voie de la page, vous devez voir apparaître le
**canal LV1** qui reçoit ce préampli : sa couleur, son nom, et un repère du type
**« L 15 = EXP 15 »** (canal LV1 15 = entrée 15 de la carte X32).

- Repatchez un canal dans la LV1 : la page suit en 1 à 2 secondes, sans sauvegarder la session.
- Une voie **grise et sans nom** = ce préampli n'arrive sur aucun canal LV1 (ou n'est pas routé
  vers la carte). C'est voulu : l'appli ne devine jamais.

## 4. Le float, la fenêtre posée sur la LV1

C'est l'outil de tous les jours. Il s'ouvre **tout seul au lancement**. Fermé par erreur ? Bouton
**Float** en haut de la page du navigateur.

### Le caler une fois pour toutes
1. Dans la LV1, affichez **Mixer 1**, mode **SndChk** (ou Setup) : le float s'y affiche, déplié.
2. **Déplacer** : attrapez le **point vert** dans la languette à gauche et posez le float entre la
   rangée du haut (Gain / Preamp) et les faders, la première colonne au-dessus de la tranche 1.
3. **Ajuster** : tirez le **coin en bas à droite** pour que les 16 colonnes tombent pile sur les
   16 tranches (largeur et hauteur). Menu **⋯ → Plus large / Plus étroit** pour un réglage fin.
4. C'est mémorisé **par résolution d'écran** : sur un autre écran, recalez une fois et chaque
   écran garde le sien.

### Ce qu'il fait tout seul
- **Suit la couche** affichée dans la LV1 (Ch 1-16, 17-32…, Custom, Masters pour le Talk Back),
  en 16, 32, 64 ou 80 canaux.
- **Se déplie** en mode **SndChk** ou **Setup**, **se replie** dans les autres modes
  (il ne reste que le point vert et la flèche).
- **Disparaît** quand la LV1 est réduite ou affiche un autre onglet que Mixer 1 / Mixer 2.
- Reste **devant la LV1 mais derrière les autres applis** (il ne vous gêne pas dans le navigateur).
- **Suit l'entrée A/B** de chaque canal : un canal basculé sur B (TracksLive, virtual soundcheck)
  n'a pas de préampli X32 à afficher.
- Une colonne **sans préampli X32 est transparente** : vous voyez et cliquez la LV1 en dessous.
- Un canal **stéréo** montre ses deux préamplis côte à côte (deux potards, deux 48 V). Les deux
  gains restent indépendants sur la X32.

### Régler un gain
- **Glisser** le potard vers le haut ou le bas (0,05 dB par pixel). Un simple clic ne change rien.
- **Cliquer sur la valeur en dB** pour taper un chiffre exact.
- **48 V** : bouton sous le potard, avec confirmation avant d'allumer.

### Le menu ⋯ (dans la languette)
| Entrée | Rôle |
|---|---|
| **Banque** | *LV1 Ch 1-16…* (une colonne par tranche LV1, le mode normal) ou *Local / A / B 1-16* (une colonne par préampli X32, pour un préampli qui n'arrive sur aucun canal) |
| **Plus large / Plus étroit** | Calage fin des colonnes |
| **Scènes…** | Sauvegarder, rappeler, renommer, écraser, supprimer une scène de gains |
| **Routing…** | Charger un routing X32 (profil « Routing LV1 » fourni) |
| **Console** | Barre IP / Connecter / Scanner, sous les voies |
| **Verrouiller l'édition** | Plus aucun gain modifiable (pendant le show) |
| **Fond de la fenêtre** | Anthracite (défaut), Noir, Or, Bleu nuit |
| **Fermer le float** | La page du navigateur reste ouverte |

## 5. Les scènes de gains

Une scène ne contient **que la X32** : gains, 48 V, noms des voies X32. La LV1 garde sa propre
session, comme d'habitude.

- **Sauvegarder** : *Scènes…* → donnez un nom → *Sauvegarder*.
- **Rappeler** : choisissez la scène → *Charger* → confirmez. L'appli relit la console pour
  vérifier, et propose **Annuler** si besoin.
- Le **48 V n'est jamais rappelé par défaut** (sécurité micros / rubans). Pour le rappeler aussi,
  passez par la page du navigateur, qui en a l'option.
- **Changer de dossier** (clé USB, dossier synchronisé) : seulement dans la page du navigateur,
  panneau *Scènes* → **Dossier…**.
- Export / import JSON : page du navigateur aussi.

## 6. Depuis une tablette ou un téléphone (facultatif)

1. Tablette sur le **même réseau** que le PC.
2. Le code n'est demandé **qu'aux tablettes et téléphones** (pas sur le PC de l'appli). Sur la page
   du PC, bouton **🔑 Code** en haut à droite : il affiche l'adresse à ouvrir
   (`http://192.168.x.x:8032/`) et un **code à 4 chiffres**.
3. Ouvrez l'adresse sur la tablette, tapez le code. Il est retenu 30 jours.

Connexion non chiffrée : réseau de confiance seulement, pas le Wi-Fi public d'un festival.

---

## Avant chaque prestation

1. Lancer la LV1 et sa session.
2. Double-clic sur `XM32_Gain_Recall_LV1.exe` : le float s'ouvre à sa place et se connecte tout seul
   à la dernière console.
3. Rappeler la scène de gains du groupe, si vous en avez une.
4. **⋯ → Verrouiller l'édition** une fois les balances faites.

## Quand ça ne marche pas

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| *Scanner* ne trouve rien | Autoriser l'appli dans le pare-feu (réseaux privés), vérifier le câble réseau de la X32, ou taper son IP |
| Voies toutes grises, sans nom LV1 | La LV1 tourne-t-elle sur **ce** PC ? La X32 arrive-t-elle par une carte DN32-WSG / X-WSG ? Regarder le message au démarrage dans la fenêtre noire |
| Une seule voie grise | Ce préampli n'est patché sur aucun canal LV1, ou le canal est sur l'entrée **B** |
| Le float a disparu | Normal hors Mixer 1 / Mixer 2, ou LV1 réduite. Revenez sur Mixer 1 |
| Le float est replié | Normal hors SndChk / Setup. Cliquez la flèche pour le déplier |
| Colonnes décalées par rapport aux tranches | Recaler (coin en bas à droite, ⋯ → Plus large / étroit). Après un changement de zoom ou de résolution, c'est à refaire une fois |
| Un correctif « ne change rien » | Un ancien exe est peut-être encore ouvert : fermez toutes les fenêtres de l'appli (et sa fenêtre noire), relancez |
| Après une mise à jour de la LV1 | L'appli est testée sur LV1 V17 : si les couleurs ou les couches ne suivent plus, signalez-le (onglet *Issues* du dépôt) |

## Où sont mes fichiers ?

Tout est dans `%APPDATA%\X32 Gain Recall` (collez ce chemin dans la barre de l'Explorateur) :
scènes, routings, code tablette, position du float. Sauvegardez ce dossier pour tout garder.

---

*X/M32 Gain Recall for eMotion LV1 — by Joseph Savigny. Outil indépendant, non affilié à
Behringer, Midas ni Waves. Testé contre un simulateur et en conditions réelles sur LV1 V17 :
faites un essai hors show avant le premier usage en live.*
