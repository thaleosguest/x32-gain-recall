<img src="assets/logo.svg" width="72" alt="Logo">

# Mode d'emploi — X/M32 Gain Recall for eMotion LV1 (v2.6.0)

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
| **Plusieurs consoles** | Possible : une carte DN32-WSG / X-WSG par console dans le rack de la LV1 (voir chapitre 7) |
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

1. Au lancement :
   - le **float** s'ouvre, la petite fenêtre des potards (voir plus bas) ;
   - la **page de l'appli** s'ouvre dans le navigateur, **réduite dans la barre des tâches** pour ne pas
     passer devant la LV1 : cliquez-la pour l'ouvrir. Sur ce PC, pas de code à taper ;
   - une **icône** apparaît près de l'horloge (au besoin dans la flèche ˄ des icônes cachées) : c'est
     l'appli. Clic droit : *Ouvrir la page*, *Afficher le float*, *Lancer avec Windows*, *Quitter*.
     Double-clic : ouvre la page.

   Une fois le float ouvert, **la LV1 repasse au premier plan** toute seule (si elle est lancée).
   Relancer l'exe alors que l'appli tourne déjà ré-affiche simplement la page et le float.
2. La première fois, l'appli **cherche la console toute seule** sur le réseau. Si elle en trouve une, elle
   s'y connecte : rien à faire. Si la console n'est pas encore allumée, elle réessaie pendant 2 minutes.
   - Plusieurs consoles sur le réseau, ou aucune trouvée ? Dans la page (ou ⋮ → Console dans le float) :
     **Scanner**, choisissez la console, puis **Connecter**. Ou tapez son IP (sur la X32 :
     *Setup → Network*).
3. Les potards prennent les gains de la console (point vert dans la languette du float). C'est connecté.
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

### Sa place : rien à faire
Dans la LV1, en mode **SndChk** (ou Setup), le float **se cale tout seul** dans les cadres vides
« Preamp / Gain / 48 » des 16 tranches, quelle que soit la taille de l'écran ou de la fenêtre de la LV1.

Vous préférez le placer vous-même ? Déplacez-le avec le **point vert** de la languette, ajustez avec le
**coin en bas à droite** ou **⋮ → Plus large / Plus étroit** : il passe alors en calage manuel, mémorisé
par résolution d'écran. **⋮ → Caler sur la LV1 (auto)** le remet en place automatiquement.

### Ce qu'il fait tout seul
- **Suit la couche** affichée dans la LV1 (Ch 1-16, 17-32…, Custom, Masters pour le Talk Back),
  en 16, 32, 64 ou 80 canaux.
- **Se déplie** en mode **SndChk** ou **Setup**, **se replie** dans les autres modes
  (il ne reste que le point vert et la flèche).
- **Disparaît** quand la LV1 est fermée, réduite, ou affiche un autre onglet que Mixer 1 / Mixer 2.
- **Mixer détaché** (Mixer 1 ou 2 ouvert dans sa propre fenêtre, sur un 2e écran par exemple) : un
  **2e float** s'ouvre tout seul pour cette fenêtre et s'y cale ; il disparaît quand vous la refermez.
- Reste **devant la LV1 mais derrière les autres applis** (il ne vous gêne pas dans le navigateur).
- **Suit l'entrée A/B** de chaque canal : un canal basculé sur B (TracksLive, virtual soundcheck)
  n'a pas de préampli X32 à afficher.
- Une colonne **sans préampli X32 est transparente** : vous voyez et cliquez la LV1 en dessous.
- Un canal **stéréo** montre ses deux préamplis côte à côte (deux potards, deux 48 V). Les deux
  gains restent indépendants sur la X32.

### En mode Edit : la tranche sélectionnée
En mode **Edit**, le float se replie, mais le réglage de la **tranche sélectionnée** apparaît dans le
cadre vide du bloc **Input** de la LV1 (sous les boutons A / B) : potard de gain et 48 V, deux pour un
canal stéréo. Sélectionnez une autre tranche : il suit. Le cadre reste vide si la tranche ne reçoit
aucun préampli X32 (entrée B, TracksLive, groupe…).

### Sur la page Channel
Sur la page **Channel** de la LV1, le réglage du préampli X32 du canal affiché apparaît dans la zone grisée
« Preamp / Gain / 48V » du bloc **Channel Input**, et suit « < » / « > ». L'appli lit à l'écran le numéro
du canal et de son EXP, et vérifie qu'ils concordent avec le patch de la LV1 : en cas de doute, la zone reste
vide (l'appli n'affiche jamais le préampli d'un autre canal). Canal sans préampli X32 : zone vide.
Lu en plein écran (1920x1080) et dans la fenêtre 1728x970 ; une autre taille de fenêtre LV1 n'est pas lue.

### Régler un gain
- **Glisser** le potard vers le haut ou le bas (0,05 dB par pixel). Un simple clic ne change rien. La
  valeur s'affiche en gros au-dessus du potard pendant qu'on le tourne (visible même avec le doigt dessus).
- **Cliquer sur la valeur en dB** pour taper un chiffre exact.
- **48 V** : bouton sous le potard, avec confirmation (voyant rouge) avant d'allumer.

### Le menu ⋮ (dans la languette)
| Entrée | Rôle |
|---|---|
| **Banque** | *LV1 Ch 1-16…* (une colonne par tranche LV1, le mode normal) ou *Local / A / B 1-16* (une colonne par préampli X32, pour un préampli qui n'arrive sur aucun canal) |
| **Bulle des dB en réglant** | Affiche (ou non) la valeur en gros pendant qu'on tourne un potard |
| **Caler sur la LV1 (auto)** | Remet le float en place tout seul sur les tranches |
| **Plus large / Plus étroit** | Calage fin à la main des colonnes |
| **Scènes…** | Sauvegarder, rappeler, renommer, écraser, supprimer une scène de gains |
| **Routing…** | Charger un profil de routing, en créer ou modifier un (✎) |
| **Consoles…** | Ajouter / retirer des consoles, choisir la carte LV1 de chacune (chapitre 7) |
| **Console (IP, connexion)** | Barre IP / Connecter / Scanner, sous les voies |
| **Verrouiller l'édition** | Plus aucun gain modifiable (pendant le show) |
| **Fond de la fenêtre** | Anthracite (défaut), Noir, Or, Bleu nuit |
| **Mise à jour… disponible** | Affiché seulement quand une version plus récente est publiée |
| **Fermer le float** | Ferme le float seulement (l'appli continue) |
| **Lancer avec Windows** | Démarrage automatique à l'ouverture de session |
| **Quitter l'appli** | Arrête tout : float, page, connexion |

Les panneaux **Scènes…**, **Routing…** et **Consoles…** se ferment avec leur croix **✕** (en haut à droite).

## 5. Le routing de la console

L'appli charge sur la X32 / M32 un **routing tout prêt** pour la LV1 : quelles entrées partent vers la
carte (EXP 1-32), et quels retours de la LV1 sortent où. Page : onglet **Routing** ; float : **⋮ →
Routing…**. Avant l'envoi, l'appli montre ce qui va changer ; après, elle relit la console pour
confirmer, et **Annuler le dernier routing** remet l'état d'avant. À faire hors signal.

Profils fournis :

| Profil | Entrées → EXP | Retours EXP → sorties |
|---|---|---|
| **Routing LV1** (X32R + S16 sur AES50 A) | X32R 1-16 → EXP 1-16, S16 A 1-16 → EXP 17-32 | EXP 1-16 → X32R OUT, EXP 1-8 / 9-16 → S16 (selon son sélecteur) |
| **LV1 — X32R + S16 A + S16 B** | S16 A 1-16 → EXP 1-16, S16 B 1-16 → EXP 17-32 | EXP 1-8 → X32R OUT 1-8, EXP 9-16 → S16 A, EXP 17-24 → S16 B |
| **LV1 — M32C + S16 A + S16 B** | S16 A 1-16 → EXP 1-16, S16 B 1-16 → EXP 17-32 | EXP 1-8 → S16 A, EXP 9-16 → S16 B |
| **LV1 — M32C + X32 stage box (AES50 A)** | X32 de scène 1-32 (A 1-32) → EXP 1-32 | EXP 1-16 → A 1-16 |
| **LV1 — M32C + X32 stage box (AES50 B)** | X32 de scène 1-32 (B 1-32) → EXP 1-32 | EXP 1-16 → B 1-16 |

**X32 pleine taille en stage box** d'une M32C (la M32C est maître et a la carte) : sur la X32 de scène,
*Setup → Preamps*, cocher **HA Remote** sur le port AES50 qui la relie à la M32C (et laisser **HA Gain Split**
décoché) : la M32C pilote ses préamplis, le float les règle comme ceux d'une S16. Tout le reste se règle sur la
M32C : chargez le profil du port utilisé (A ou B), l'appli connectée à la M32C.

Pour les profils avec deux S16, les retours sortent des S16 **quelle que soit la position de leur sélecteur
de sorties** (1-8 ou 9-16).

### Un routing à vous (éditeur libre)
Pour mettre, par exemple, **L1 sur EXP 1 et A18 sur EXP 2** (une source de la scène plus proche du S16) :
**✎ Modifier…** sur un profil (ou **Depuis la console…** pour partir du routing actuel), choisissez la
source de chaque EXP et le retour de chaque sortie, puis **Enregistrer** : c'est un profil de plus, qui se
charge comme les autres.

Vue **Matrice** (par défaut) : une colonne par EXP, une ligne par source (ou par sortie). Touchez une case
pour router, retouchez-la pour couper. La ligne et la colonne visées s'allument et le texte au-dessus dit
ce que vous allez faire (« AES50-A 18 → EXP 2 ») ; dans le float, gardez le doigt posé pour viser, glissez
au besoin, la case est routée quand vous relevez le doigt. Vue **Listes** : un menu déroulant par EXP et
par sortie. Pour revenir au standard, rechargez simplement un autre profil. Les couleurs et
noms LV1 du float suivent tout seuls (EXP 2 affichera le préampli A18).

## 6. Les scènes de gains

Une scène ne contient **que les consoles** (X32 / M32) : gains, 48 V, noms des voies, de toutes les consoles
connectées. La LV1 garde sa propre session, comme d'habitude.

- **Sauvegarder** : *Scènes…* → donnez un nom → *Sauvegarder*.
- **Rappeler** : choisissez la scène → *Charger* → confirmez. L'appli relit la console pour
  vérifier, et propose **Annuler** si besoin.
- Le **48 V n'est jamais rappelé par défaut** (sécurité micros / rubans). Pour le rappeler aussi,
  passez par la page du navigateur, qui en a l'option.
- **Changer de dossier** (clé USB, dossier synchronisé) : seulement dans la page du navigateur,
  panneau *Scènes* → **Dossier…**.
- Export / import JSON : page du navigateur aussi.

## 7. Plusieurs consoles (une carte chacune dans le rack de la LV1)
Avec plusieurs X32 / M32 qui ont chacune leur carte dans le rack de la LV1 : float **⋮ → Consoles…**.
- **Ajouter** les consoles 2, 3… (adresse IP, ou *Scanner le réseau*). La console 1 est celle de la barre
  de connexion.
- **Carte LV1** de chaque console : sa position dans le rack (le « 2- » de « 2-EX 1 » dans la LV1). Choisie
  toute seule si le nom de la carte dans la LV1 reprend celui de la console (ex. « X32-FOH »).
- Le float règle alors les préamplis de **toutes** les consoles, chacun sur sa tranche LV1 ; ceux de la
  console 2 sont repérés « 2·A 5 = EXP 2·5 ». Une console sans carte choisie : ses tranches restent sans
  potard (jamais le préampli d'une autre console).
- **Routing** : avec plusieurs consoles, choisissez la console visée (sélecteur *Console* dans l'onglet
  Routing de la page ; dans le float, l'appli demande la console au moment de charger). Aperçu, vérification
  et *Annuler le dernier routing* se font console par console.
- **Scènes de gains** : une scène enregistre et rappelle les gains de **toutes** les consoles connectées
  (laissez-les connectées en même temps) ; une console absente au rappel est signalée et laissée de côté.

## 8. Depuis une tablette ou un téléphone (facultatif)

1. Tablette sur le **même réseau** que le PC.
2. Le code n'est demandé **qu'aux tablettes et téléphones** (pas sur le PC de l'appli). Sur la page
   du PC, bouton **🔑 Code** en haut à droite : il affiche l'adresse à ouvrir
   (`http://192.168.x.x:8032/`) et un **code à 4 chiffres**.
3. Ouvrez l'adresse sur la tablette, tapez le code. Il est retenu 30 jours.

Connexion non chiffrée : réseau de confiance seulement, pas le Wi-Fi public d'un festival.

---

## Lancer avec Windows

Clic droit sur l'icône près de l'horloge (ou menu **⋮** du float) → **Lancer avec Windows**. L'appli
démarre alors toute seule à l'ouverture de la session Windows, sans ouvrir le navigateur ; le float
reste caché jusqu'au lancement de la LV1, puis s'y pose. Décochez pour arrêter.

## Mises à jour

Au lancement (puis une fois par jour), l'appli regarde sur GitHub si une version plus récente est
publiée. Si oui : une bulle près de l'horloge, une entrée **Mise à jour… disponible** dans le menu de
l'icône et dans le menu **⋮** du float, et un lien **⬆ disponible** en haut de la page. Ils ouvrent la
page de téléchargement : rien ne s'installe tout seul. Pour mettre à jour : quitter l'appli, remplacer
l'exe par le nouveau, relancer (scènes et réglages sont gardés).

## Quitter l'appli

Clic droit sur l'icône près de l'horloge → **Quitter**, ou menu **⋮** du float → **Quitter l'appli**.
Le float, la page et la connexion à la console s'arrêtent. (*Fermer le float* ne ferme que le float :
l'appli continue, l'icône aussi.)

## Avant chaque prestation

1. Lancer la LV1 et sa session.
2. Double-clic sur `XM32_Gain_Recall_LV1.exe` (inutile avec *Lancer avec Windows*) : le float s'ouvre à
   sa place et se connecte tout seul à la dernière console.
3. Rappeler la scène de gains du groupe, si vous en avez une.
4. **⋮ → Verrouiller l'édition** une fois les balances faites.

## Quand ça ne marche pas

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| *Scanner* ne trouve rien | Autoriser l'appli dans le pare-feu (réseaux privés), vérifier le câble réseau de la X32, ou taper son IP |
| Voies toutes grises, sans nom LV1 | La LV1 tourne-t-elle sur **ce** PC ? La X32 arrive-t-elle par une carte DN32-WSG / X-WSG ? Regarder le journal `x32_gain_recall.log` dans le dossier de l'appli (voir plus bas) |
| Une seule voie grise | Ce préampli n'est patché sur aucun canal LV1, ou le canal est sur l'entrée **B** |
| Le float a disparu | Normal hors Mixer 1 / Mixer 2, LV1 réduite ou fermée : il revient avec la LV1, sur Mixer 1 |
| Le float est replié | Normal hors SndChk / Setup. Cliquez la flèche pour le déplier |
| Colonnes décalées par rapport aux tranches | **⋮ → Caler sur la LV1 (auto)** |
| Plusieurs consoles : les tranches d'une console restent sans potard | **⋮ → Consoles…** : la console est-elle connectée (point vert) et a-t-elle la bonne **Carte LV1** ? |
| Page Channel : zone vide | Canal sans préampli X32, ou LV1 dans une taille de fenêtre non relevée (plein écran ou fenêtre 1728x970) |
| Un correctif « ne change rien » | Un ancien exe est peut-être encore ouvert : icône près de l'horloge → *Quitter* (et vérifiez qu'il n'en reste pas une 2e), relancez |
| Après une mise à jour de la LV1 | L'appli est testée sur LV1 V17 : si les couleurs ou les couches ne suivent plus, signalez-le (onglet *Issues* du dépôt) |

## Où sont mes fichiers ?

Tout est dans `%APPDATA%\X32 Gain Recall` (collez ce chemin dans la barre de l'Explorateur) :
scènes, routings, code tablette, position du float, et le journal de la dernière session
(`x32_gain_recall.log`, `x32_float.log`). Sauvegardez ce dossier pour tout garder.

---

*X/M32 Gain Recall for eMotion LV1 — by Joseph Savigny. Outil indépendant, non affilié à
Behringer, Midas ni Waves. Testé contre un simulateur et en conditions réelles sur LV1 V17 :
faites un essai hors show avant le premier usage en live.*
