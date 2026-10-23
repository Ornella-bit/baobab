"""Comprehension des questions en francais, sans Internet et sans modele de langage.

- normaliser : minuscules, sans accents ni ponctuation (« D'où vient… ? » -> « d ou vient »)
- tolerance aux fautes de frappe : distance d'edition (« retrad », « dleta », « stok », « confience »)
- nombres ecrits en lettres (« cinq jours », « deux semaines »)
- intention : quelle est la question ? (retard, stock, confiance, qualite...)
- entites : fournisseur, nombre de jours, ligne, matiere, produit, fichier, commande, option A/B/C
Ce module ne calcule rien : il lit la question et rend des mots-cles. Les chiffres viennent de core/simulate.py.
"""
import re
import unicodedata

NOMBRES = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
           "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
           "vingt": 20, "trente": 30}

# mots (radicaux, sans accents) qui revelent l'intention. L'ordre de PRIORITE departage les egalites.
LEXIQUE = {
    "classement": ["risque", "risqu", "dangereu", "classement", "fragil", "vulnerab", "critique"],
    "reco": ["recommand", "conseill", "meilleur", "choisir", "laquelle", "preferable", "privilegi"],
    "retard": ["retard", "arret", "rupture", "bloqu", "panne", "penurie", "solution", "option", "livraison",
               "decaler", "perturb", "manque", "alternative", "plan b"],
    "stock": ["stock", "couverture", "autonomie", "inventaire", "reste", "epuis", "tient", "tiendra"],
    "passeport": ["passeport", "tracab", "provenance", "origine", "compos", "vient", "venir", "ingredient"],
    "confiance": ["confian", "certain"],
    "qualite": ["qualit", "note", "score", "probleme", "doublon", "erreur", "anomalie", "propre", "corrig",
                "nettoy", "ameliorer", "ameliore", "sain", "mauvais", "donnees", "fichier", "pii"],
    "resume": ["resume", "bilan", "situation", "briefing", "synthese", "etat", "apercu", "panorama"],
    "commande": ["commande", "cmd", "client"],
    "aide": ["aide", "bonjour", "salut", "bonsoir", "hello", "merci", "capable", "fonctionnalite", "sais"],
}
PRIORITE = ["classement", "reco", "retard", "stock", "passeport", "confiance", "qualite", "resume", "commande", "aide"]

EXPLIQUER = ["pourquoi", "comment", "explique", "expliquer", "detaille", "detailler", "justifie", "calcule", "calcul",
             "precise", "preciser", "montre", "raison"]
SUIVI = ["pareil", "idem", "aussi", "meme chose", "et pour", "et si", "et avec", "et en cas", "dans ce cas"]

FICHIERS = {"stocks": ["stock", "lots", "lot"], "production": ["production", "lignes", "ligne"],
            "fournisseurs": ["fournisseur"], "commandes": ["commande"], "clients": ["client"],
            "employes": ["employe", "salarie", "personnel"]}
MATIERES = {"concentre_mangue": ["mangue"], "concentre_orange": ["orange"], "sucre": ["sucre"],
            "bouteilles": ["bouteille", "emballage", "verre"]}


ABREVIATIONS = {"cb": "combien", "cmb": "combien", "combein": "combien", "qte": "quantite", "qt": "quantite", "nb": "nombre",
                "moy": "moyenne", "fourn": "fournisseur", "fournisseurss": "fournisseurs", "stk": "stock", "ptt": "petit"}


def normaliser(texte):
    t = unicodedata.normalize("NFD", str(texte).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9+ ]", " ", t)  # apostrophes et traits d'union deviennent des espaces
    t = re.sub(r"\s+", " ", t).strip()
    return " ".join(ABREVIATIONS.get(w, w) for w in t.split())


def distance(a, b):
    """Distance d'edition avec transposition (« dleta » -> « delta » = 1)."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cout = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cout)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def _tolerance(n):
    return 0 if n < 5 else 1 if n < 9 else 2


def mot_proche(token, mot):
    """Vrai si le mot de la question ressemble a « mot » (debut identique, ou 1 a 2 fautes selon la longueur)."""
    if token.startswith(mot):
        return True
    if len(mot) < 5 or len(token) < len(mot) - 1:
        return False
    tol = _tolerance(len(mot))
    return distance(token[:len(mot)], mot) <= tol or distance(token, mot) <= tol


def _contient(q, toks, mots):
    return sum(1 for m in mots if (" " in m and m in q) or any(mot_proche(t, m) for t in toks if " " not in m))


def tokens(q):
    return q.split()


def _nombre(mot):
    return int(mot) if mot.isdigit() else NOMBRES.get(mot)


def extraire_jours(q):
    """« 5 jours », « cinq jours », « 2 semaines », « retard de 7 »."""
    m = re.search(r"\b(\d+|" + "|".join(NOMBRES) + r")\s*(jours?|j|semaines?)\b", q)
    if m:
        n = _nombre(m.group(1))
        return n * (7 if m.group(2).startswith("semaine") else 1)
    m = re.search(r"\bretard\D{0,14}?(\d+)\b", q)
    if m:
        return int(m.group(1))
    return None


def extraire(q, data):
    """Retourne les entites trouvees : fournisseur, retard_jours, ligne, matiere, produit, fichier, commande, client, option, nombre."""
    toks = tokens(q)
    ent = {}
    noms = {_f: normaliser(_f) for _f in data["fournisseurs"]["fournisseur"].unique()}
    for t in toks:
        for brut, nf in noms.items():
            if t == nf or (len(t) >= 4 and distance(t, nf) <= 1):
                ent["fournisseur"] = brut
    jours = extraire_jours(q)
    if jours is not None:
        ent["retard_jours"] = jours
    m = re.search(r"\bligne\s*(1|2|un|deux)\b", q) or re.search(r"\bl([12])\b", q)
    if m:
        ent["ligne"] = "Ligne " + str(_nombre(m.group(1)))
    toks_val = [t for t in toks if not t.startswith("manqu")]  # « manquer » ressemble a « mangue » : faux ami
    for mat, mots in MATIERES.items():
        if any(mot_proche(t, mot) for t in toks_val for mot in mots):
            ent["matiere"] = mat
    produits = list(data["production"]["produit"].unique())
    for p in produits:
        if any(mot in toks_val or any(mot_proche(t, mot) for t in toks_val) for mot in [x for x in normaliser(p).split() if len(x) > 4 and x not in ("nectar",)]):
            ent["produit"] = p
    if "nectar" in toks:
        ent["produit"] = next((p for p in produits if "nectar" in normaliser(p)), ent.get("produit"))
    for f, mots in FICHIERS.items():
        if any(t.startswith(mot) or mot_proche(t, mot) for t in toks for mot in mots if len(mot) > 3):
            ent["fichier"] = f
    if re.search(r"\blots?\b", q):
        ent["fichier"] = "stocks"
    m = re.search(r"\bcmd\s*0*(\d{1,3})\b", q)
    if m:
        ent["commande"] = f"CMD{int(m.group(1)):03d}"
    m = re.search(r"\bclient\s+([abc])\b", q)
    if m:
        ent["client"] = f"Client {m.group(1).upper()}"
    m = re.search(r"\b(?:solution|option|plan|choix)\s+([abc])\b", q)
    if m:
        ent["option"] = m.group(1).upper()
    nombres = re.findall(r"\b\d+\b", q)
    if nombres:
        ent["nombre"] = int(nombres[0])
    return ent


def intentions(q):
    """Score de chaque intention (nombre de mots du lexique reconnus) + phrases-types."""
    toks = tokens(q)
    sc = {i: _contient(q, toks, mots) for i, mots in LEXIQUE.items()}
    if re.search(r"\b(le|la|les|quel|quelle|quels)\b.*\b(plus|moins)\b.*\b(risque|risques|fragile|dangereux|critique)", q) or \
            re.search(r"\bquel(le)? fournisseur\b", q) or "classe" in q:
        sc["classement"] += 2
    if re.search(r"\bque faire\b|\bque se passe\b|\bse passerait\b|\bque va t il se passer\b|\bsi .{0,25}retard", q):
        sc["retard"] += 2
    if re.search(r"\bcombien de (jours|j)\b", q) and not sc["retard"]:
        sc["stock"] += 2
    if re.search(r"\bdonnees?\b.*\bfiables?\b|\bfiables?\b.*\b(donnees?|reponses?|resultats?|chiffres?)\b|\b(te|vous) fier\b|\bfiabilite (des|de tes|de vos) (donnees|reponses|resultats)", q):
        sc["confiance"] += 2
    if re.search(r"\b(quel|quelle|quels|quelles)\b.*\b(manquer|epuis|finir|critique|bas|court|urgent|premier)", q) and not re.search(r"fournisseur|commandes?\b|\blots?\b|\bclients?\b", q):
        sc["stock"] += 3
        sc["classement"] = 0
    if re.search(r"\bd ou vient|\bd ou viennent|\bou est fabrique", q):
        sc["passeport"] += 2
    if re.search(r"\bcombien (de|d)\s+\w+", q) and compte_cible(q):
        sc["comptage"] = 3
    if re.search(r"\b(qui es tu|que sais tu|que peux tu|tu peux faire|tu sais faire|a quoi sers|aide moi)\b", q):
        sc["aide"] += 3
    return sc


COMPTAGE = {"clients": ["client", "clients"], "commandes": ["commande", "commandes"], "lots": ["lot", "lots"],
            "fournisseurs": ["fournisseur", "fournisseurs"], "produits": ["produit", "produits"],
            "doublons": ["doublon", "doublons"], "problemes": ["probleme", "problemes", "erreur", "erreurs", "anomalie", "anomalies"],
            "lignes": ["ligne", "lignes"]}


def compte_cible(q):
    """« combien de clients ? » -> « clients » ; « combien de jours de stock » -> None."""
    m = re.search(r"\bcombien (?:de la |de |d |des |du )?(\w+)", q)
    if not m:
        return None
    for cle, formes in COMPTAGE.items():
        if m.group(1) in formes:
            return cle
    return None


def choisir_intention(q, ent, memoire):
    """Retourne (intention, est_suivi, expliquer). est_suivi = la question complete la precedente (« Et pour Sigma ? »)."""
    toks = tokens(q)
    sc = intentions(q)
    expliquer = any(m in toks for m in EXPLIQUER) or bool(re.search(r"\bd ou vient (ce|cette|le) (chiffre|nombre|resultat|score|note)", q))
    suivi = q.startswith("et ") or q.startswith("mais ") or any(s in q for s in SUIVI)
    ordre = PRIORITE + ["comptage"]
    meilleur = max(ordre, key=lambda i: (sc.get(i, 0), -ordre.index(i)))
    if sc.get(meilleur, 0) > 0:
        # « pourquoi 98 ? » : un nombre egal a la derniere confiance affichee parle de la confiance
        return meilleur, suivi, expliquer
    # aucun mot-cle : on regarde les entites, puis ce dont on parlait
    derniere = (memoire or {}).get("intention")
    if "fournisseur" in ent or "retard_jours" in ent:
        return ("classement" if derniere == "classement" and "fournisseur" not in ent else "retard"), True, expliquer
    if "ligne" in ent or "matiere" in ent:
        return ("passeport" if derniere == "passeport" and "produit" in ent else "stock"), True, expliquer
    if "produit" in ent:
        return "passeport", True, expliquer
    if "commande" in ent or "client" in ent:
        return "commande", True, expliquer
    if "option" in ent:
        return "reco", True, expliquer
    if "fichier" in ent:
        return "qualite", True, expliquer
    if expliquer and derniere:
        return "expliquer", True, True
    if "nombre" in ent and derniere in ("retard", "classement") and len(toks) <= 4:
        return derniere, True, False
    return None, suivi, expliquer
