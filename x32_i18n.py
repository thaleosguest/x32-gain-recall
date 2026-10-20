"""Langue de l'interface (3.0.1) : anglais par défaut, français au choix (demande de Joseph).

Les textes sont écrits en français dans le code et passés par T() à l'affichage : T() rend la traduction anglaise
quand la langue est "en". Choix enregistré dans x32_gain_recall_settings.json (« lang ») par l'appli principale,
transmis au float par /api/state ; float en --direct : dans sa propre configuration.
"""

LANG = "en"
LANGS = (("en", "English"), ("fr", "Français"))


def set_lang(lang):
    global LANG
    LANG = lang if lang in ("en", "fr") else "en"
    return LANG


def T(text):
    """Texte à afficher dans la langue choisie (le français est la langue du code)."""
    if LANG == "fr" or not isinstance(text, str):
        return text
    return EN.get(text, text)


EN = {
    # --- float : potards, 48V, saisie
    "Gain ": "Gain ",
    "Annuler": "Cancel",
    "Activer le +48 V ?": "Turn on +48 V?",
    "Voie %s : vérifiez qu'aucun micro ruban / dynamique non protégé n'est branché avant d'activer "
    "l'alimentation fantôme.": "Channel %s: make sure no ribbon / unprotected dynamic mic is plugged in before "
                               "turning on phantom power.",
    "Activer +48 V": "Turn on +48 V",
    "Gain — voie %s": "Gain — channel %s",
    "Valeur en dB (%.0f à +%.0f) :": "Value in dB (%.0f to +%.0f):",
    "« %s » n'est pas un nombre valide.": "“%s” is not a valid number.",
    "Code d'accès": "Access code",
    "Code d'accès de l'appli (affiché sur la page) :": "App access code (shown on the web page):",
    "OK": "OK",
    # --- menu
    "  (défaut)": "  (default)",
    "Banque : %s": "Bank: %s",
    "Recaler sur la LV1": "Re-align on the LV1",
    "Bulle des dB en réglant": "Show dB bubble while adjusting",
    "Scènes…": "Scenes…",
    "Routing…": "Routing…",
    "Consoles…": "Consoles…",
    "Console (IP, connexion)": "Console (IP, connection)",
    "Ouvrir la page dans le navigateur": "Open the web page",
    "Verrouiller l'édition": "Lock editing",
    "Fond de la fenêtre": "Background",
    "⬆ Mise à jour %s disponible…": "⬆ Update %s available…",
    "Fermer le float": "Close the float",
    "Lancer avec Windows": "Start with Windows",
    "Quitter l'appli": "Quit the app",
    "Quitter l'appli ?": "Quit the app?",
    "Le float, la page et la connexion à la console s'arrêtent.":
        "The float, the web page and the console connection will stop.",
    "Quitter": "Quit",
    "Langue": "Language",
    "◂  Retour": "◂  Back",
    "Anthracite": "Charcoal",
    "Noir": "Black",
    "Or": "Gold",
    "Bleu nuit": "Midnight blue",
    # --- panneaux : titres
    "SCÈNES DE GAINS": "GAIN SCENES",
    "PROFILS DE ROUTING": "ROUTING PROFILES",
    "CONSOLES": "CONSOLES",
    "CONSOLE": "CONSOLE",
    "ACTIVE": "ACTIVE",
    "ACTIF": "ACTIVE",
    # --- scènes
    "Nom de la nouvelle scène": "New scene name",
    "Sauvegarder": "Save",
    "Aucune scène pour l'instant — tapez un nom ci-dessus et « Sauvegarder » pour créer la première, à partir des "
    "gains actuels.": "No scene yet — type a name above and tap “Save” to create the first one from the "
                     "current gains.",
    "Charger": "Load",
    "Écraser": "Overwrite",
    "Renommer": "Rename",
    "Supprimer": "Delete",
    "Entrez un nom pour la scène.": "Enter a name for the scene.",
    "Sauvegarder cette scène ?": "Save this scene?",
    "Sauvegarder « %s » avec TOUS les gains actuellement lus sur la console (pas seulement la banque affichée) ?":
        "Save “%s” with ALL the gains currently read from the console (not only the displayed bank)?",
    "Scène « %s » sauvegardée": "Scene “%s” saved",
    "Rappeler la scène ?": "Recall this scene?",
    "Rappeler « %s » ? Seuls les gains sont rappelés (pas le 48V, comme dans le navigateur par défaut).":
        "Recall “%s”? Only the gains are recalled (not the 48V, as in the web page by default).",
    "Rappeler": "Recall",
    "Scène « %s » rappelée": "Scene “%s” recalled",
    "Écraser la scène ?": "Overwrite this scene?",
    "Remplacer le contenu de « %s » par les gains actuellement lus sur la console (TOUS les gains) ? Cette action "
    "est irréversible.": "Replace the content of “%s” with the gains currently read from the console "
                         "(ALL the gains)? This cannot be undone.",
    "Scène « %s » mise à jour": "Scene “%s” updated",
    "Renommer la scène": "Rename the scene",
    "Nouveau nom :": "New name:",
    "Le nom ne peut pas être vide.": "The name cannot be empty.",
    "Scène renommée en « %s »": "Scene renamed to “%s”",
    "Supprimer définitivement ?": "Delete permanently?",
    "Supprimer la scène « %s » ? Cette action est irréversible.":
        "Delete the scene “%s”? This cannot be undone.",
    "Scène « %s » supprimée": "Scene “%s” deleted",
    # --- routing
    "Partir du routing de quelle console ?": "Start from the routing of which console?",
    "Créer un nouveau routing": "Create a new routing",
    "Aucun profil (ou appli principale non connectée).": "No profile (or main app not connected).",
    "Modifier": "Edit",
    "%d lignes E/S · %s": "%d I/O lines · %s",
    "Charger « %s » sur quelle console ?": "Load “%s” on which console?",
    " sur la console %d": " on console %d",
    "Charger ce routing ?": "Load this routing?",
    "Charger « %s »%s ? Seul le routing E/S est touché (pas le patch de sortie). À faire de préférence hors "
    "signal : ça peut couper l'audio en cours.": "Load “%s”%s? Only the I/O routing is changed (not the "
                                                "output patch). Preferably do this without signal: it may cut the "
                                                "audio.",
    "Routing « %s » envoyé": "Routing “%s” sent",
    "Renommer le routing": "Rename the routing",
    "Routing renommé en « %s »": "Routing renamed to “%s”",
    "Renommage impossible": "Rename failed",
    "Supprimer le routing « %s » de la liste ? La console n'est pas touchée. Cette action est irréversible.":
        "Remove the routing “%s” from the list? The console is not changed. This cannot be undone.",
    "Routing « %s » supprimé": "Routing “%s” deleted",
    "Suppression impossible": "Delete failed",
    " (console %s)": " (console %s)",
    "intégré": "built-in",
    "éditeur": "editor",
    # --- consoles / connexion
    "  (non connectée)": "  (not connected)",
    "Console %d — %s%s": "Console %d — %s%s",
    "Console %d — %s (%s)": "Console %d — %s (%s)",
    "(automatique / non choisie)": "(automatic / not chosen)",
    "Retirer": "Remove",
    "Carte LV1 :": "LV1 card:",
    "Adresse IP d'une autre console": "IP address of another console",
    "Ajouter": "Add",
    "Scanner le réseau": "Scan the network",
    "Chaque console règle les préamplis de SA carte (position dans le rack de la LV1, le « 2- » de « 2-EX 1 »). "
    "Carte choisie automatiquement si son nom dans la LV1 reprend celui de la console.":
        "Each console controls the preamps of ITS card (position in the LV1 rack, the “2-” of "
        "“2-EX 1”). The card is chosen automatically when its LV1 name contains the console name.",
    "Recherche…": "Searching…",
    "Aucune autre console trouvée sur le réseau.": "No other console found on the network.",
    "Impossible": "Not possible",
    "Adresse IP de la console": "Console IP address",
    "Connecter": "Connect",
    "Scanner": "Scan",
    "Démo": "Demo",
    "Appli principale non trouvée sur le port %d": "Main app not found on port %d",
    "Non connecté à la console": "Not connected to the console",
    "Entrez une IP": "Enter an IP",
    "Connexion…": "Connecting…",
    "Démo (simulateur)": "Demo (simulator)",
    "Rien trouvé — IP manuelle": "Nothing found — enter the IP",
    "%d console(s) trouvée(s)": "%d console(s) found",
    "Choisir": "Choose",
    "Échec": "Failed",
    # --- éditeur de routing
    "ENTRÉES → LV1 : une case par EXP (colonne)": "INPUTS → LV1: one cell per EXP (column)",
    "SORTIES ← RETOURS LV1 : une case par sortie (ligne)": "OUTPUTS ← LV1 RETURNS: one cell per output (row)",
    "%s → EXP %d     (EXP %d reçoit aujourd'hui : %s)": "%s → EXP %d     (EXP %d currently receives: %s)",
    "EXP %d → %s     (%s reçoit aujourd'hui : %s)": "EXP %d → %s     (%s currently receives: %s)",
    "Éditeur de routing — %s": "Routing editor — %s",
    "Routing perso": "Custom routing",
    " (perso)": " (custom)",
    "Nom": "Name",
    "Matrice": "Matrix",
    "Listes": "Lists",
    "Toutes les sources (+ AES50 33-48, Aux, Talkback)": "All sources (+ AES50 33-48, Aux, Talkback)",
    "X32R : seules OUT 1-8 sont physiques. S16 : voies 1-8 ou 9-16 selon son sélecteur de sorties (même retour "
    "sur les deux = marche dans les deux positions). L'enregistrement ne touche pas la console : « Charger » "
    "ensuite.": "X32R: only OUT 1-8 are physical. S16: channels 1-8 or 9-16 depending on its output selector "
                "(same return on both = works in both positions). Saving does not change the console: "
                "“Load” it afterwards.",
    "Enregistrer": "Save",
    "Enregistrer comme nouveau profil": "Save as a new profile",
    "Enregistrer sous…": "Save as…",
    "Fermer": "Close",
    "Routing « %s » enregistré": "Routing “%s” saved",
    "Fermer sans enregistrer ?": "Close without saving?",
    "Éditeur indisponible": "Editor unavailable",
    "ENTRÉES → LV1": "INPUTS → LV1",
    "SORTIES ← RETOURS LV1": "OUTPUTS ← LV1 RETURNS",
    # --- tuiles LV1 et message de démarrage
    "Gains\nX32": "X32\nGains",
    "X/M32 Gain Recall est actif": "X/M32 Gain Recall is active",
    "Connecté à %s (%s)": "Connected to %s (%s)",
    "%d consoles connectées": "%d consoles connected",
    "Aucune console trouvée pour l'instant : menu → Console.": "No console found yet: menu → Console.",
    "Recherche de la console…": "Looking for the console…",
    # --- PATCH MAP (3.1)
    "PATCH MAP": "PATCH MAP",
    "EXP": "EXP",
    "EXP ": "EXP ",
    "SOURCE X32": "X32 SOURCE",
    "CANAL X32": "X32 CHANNEL",
    "CANAL LV1": "LV1 CHANNEL",
    "(sans nom)": "(no name)",
    "non patché": "not patched",
    "Aucune correspondance.": "No match.",
    "Routing de la console pas encore lu : sources inconnues (menu → Console).":
        "Console routing not read yet: sources unknown (menu → Console).",
    # --- PATCH DE SCÈNE (3.1)
    "Stage patch…": "Stage patch…",
    "Couleurs → LV1": "Colors → LV1",
    "Les canaux LV1 ont déjà les couleurs des prises.": "The LV1 channels already have the socket colors.",
    "Il faut lancer X32 Gain Recall en administrateur (la LV1 l'est) : sinon Windows bloque les clics.":
        "X32 Gain Recall must run as administrator (the LV1 does): otherwise Windows blocks the clicks.",
    "Affichez la page Patch de la LV1 (vue Input A, liste en haut), puis recommencez.":
        "Show the LV1 Patch page (Input A view, list scrolled to the top), then try again.",
    "Donner leur couleur à %d canaux LV1 (%s) ? La fenêtre se cache quelques secondes : ne touchez pas la LV1 pendant ce temps.":
        "Give their color to %d LV1 channels (%s)? This window hides for a few seconds: do not touch the LV1 meanwhile.",
    "Appliquer": "Apply",
    "Exporter…": "Export…",
    "Importer…": "Import…",
    "Exporter": "Export",
    "Importer": "Import",
    "Exporter la feuille": "Export the sheet",
    "Importer une feuille": "Import a sheet",
    "Feuille de patch (*.stagepatch.json)": "Patch sheet (*.stagepatch.json)",
    "Feuille de patch (*.stagepatch.json *.json)": "Patch sheet (*.stagepatch.json *.json)",
    "Feuille exportée": "Sheet exported",
    "Feuille importée": "Sheet imported",
    "« %s » (%d prises) : feuille active.": "“%s” (%d sockets): active sheet.",
    "Fichier illisible : %s": "Unreadable file: %s",
    "Étiquette effacée": "Label cleared",
    "%s : piste par défaut (« Channel N »). Couleur par défaut : bouton « Couleurs → LV1 ».":
        "%s: default track (“Channel N”). Default color: “Colors → LV1” button.",
    "%d canaux en cours… ne touchez pas la LV1.": "%d channels in progress… do not touch the LV1.",
    "%d couleur(s) appliquée(s) dans la LV1.": "%d color(s) applied in the LV1.",
    "Arrêt : %s": "Stopped: %s",
    "Stage patch — %s": "Stage patch — %s",
    "STAGE PATCH": "STAGE PATCH",
    "Stage\nPatch": "Stage\nPatch",
    "NOM": "NAME",
    "Rechercher : canal, EXP, source (A1, L3…)": "Search: channel, EXP, source (A1, L3…)",
    "Renommer les canaux LV1": "Rename LV1 channels",
    "Choisissez une ligne ou une prise": "Pick a row or a socket",
    "Entrée ou › : enregistrer et passer à la suivante. ↑ ↓ aussi. Toucher une couleur l'enregistre.":
        "Enter or ›: save and go to the next one. ↑ ↓ too. Tapping a color saves it.",
    "Patch de scène": "Stage patch",
    "Patch de scène — %s": "Stage patch — %s",
    "Patch de scène indisponible (appli principale injoignable).": "Stage patch unavailable (main app unreachable).",
    "Disponible avec l'appli principale (pas en --direct).": "Available with the main app (not in --direct).",
    "Feuille": "Sheet",
    "Feuille de patch": "Patch sheet",
    "Nouvelle": "New",
    "Dupliquer": "Duplicate",
    "Effacer": "Clear",
    " (copie)": " (copy)",
    "Nom de la nouvelle feuille (spectacle, studio…) :": "Name of the new sheet (show, studio…):",
    "Nom de la copie :": "Name of the copy:",
    "Supprimer la feuille « %s » ?": "Delete sheet “%s”?",
    "Renommer les canaux LV1 automatiquement": "Rename LV1 channels automatically",
    "Renommage automatique désactivé.": "Automatic renaming is off.",
    "LV1 reliée (OSC %s:%s) : les canaux LV1 prennent le nom de la prise qui les alimente.":
        "LV1 linked (OSC %s:%s): LV1 channels take the name of the socket feeding them.",
    "LV1 pas encore reliée (%s).": "LV1 not linked yet (%s).",
    "Les canaux LV1 prendront le nom de la prise qui les alimente.":
        "LV1 channels will take the name of the socket feeding them.",
    "Dernier : In %d → « %s ».": "Last: In %d → “%s”.",
    "Console %d — %s": "Console %d — %s",
    "PRISES DE LA CONSOLE": "CONSOLE SOCKETS",
    "PORT AES50 A": "AES50 PORT A",
    "PORT AES50 B": "AES50 PORT B",
    "— rien —": "— nothing —",
    "face avant": "front panel",
    "face arrière": "rear panel",
    "Nom (Kick, Snare, OV L…)": "Name (Kick, Snare, OH L…)",
    "Couleur (palette de la LV1)": "Color (LV1 palette)",
    "Sans couleur": "No color",
    "Cette entrée n'arrive sur aucun EXP (routing de la console).":
        "This input reaches no EXP (console routing).",
    "aucun canal LV1": "no LV1 channel",
    "Sortie : le nom sert de repère sur la face (pas envoyé à la LV1).":
        "Output: the name is a marker on the panel (not sent to the LV1).",
    "%s : « %s »": "%s: “%s”",
    "%s : étiquette effacée": "%s: label cleared",
    "Couleur différente dans la LV1 : à régler à la main (la LV1 ne laisse pas changer la couleur à distance).":
        "Different color in the LV1: set it by hand (the LV1 does not allow remote color changes).",
    "● orange : couleur LV1 différente, à régler à la main.": "● orange: different LV1 color, set it by hand.",
    # --- icône près de l'horloge
    "Ouvrir la page": "Open the web page",
    "Afficher le float": "Show the float",
    "Mise a jour %s disponible...": "Update %s available...",
}
