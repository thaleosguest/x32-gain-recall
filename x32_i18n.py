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
    "Patch map…": "Patch map…",
    "Rechercher : canal, EXP, source (A1, L3…)": "Search: channel, EXP, source (A1, L3…)",
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
    # --- icône près de l'horloge
    "Ouvrir la page": "Open the web page",
    "Afficher le float": "Show the float",
    "Mise a jour %s disponible...": "Update %s available...",
}
