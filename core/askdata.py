"""Questions libres sur les donnees : « combien de commandes avant le 8 novembre ? », « quel client a le plus
commande ? », « delai moyen de Sigma ? », « quels lots de sucre depassent 1000 kg ? »...

Comment ca marche (sans Internet, sans cle d'API, sans reponses pre-ecrites) :
  1. la question est decoupee et reliee au SCHEMA des donnees (tables, colonnes, valeurs reelles : Delta, Ligne 2, Client B...) ;
  2. elle devient un PLAN (table, operation, filtres, regroupement, tri) ;
  3. le plan est traduit en requete SQL, executee en LECTURE sur une copie en memoire des donnees ;
  4. la reponse est redigee a partir du resultat reel. Rien n'est invente : si le plan est impossible, on le dit.
Protection des donnees personnelles : la copie en memoire ne contient NI noms, NI telephones, NI e-mails de clients,
NI le fichier des salaries. Ces informations ne peuvent donc pas sortir, quelle que soit la question.
Les quantites de stock sont nettoyees comme dans SupplyMind (valeurs invalides ignorees, unites converties) :
le copilote repond sur des donnees propres et signale ce qu'il a ignore.
"""
import re
import sqlite3
from datetime import date, timedelta

import pandas as pd

from core import nlu
from core.loader import PARAMS
from core.simulate import MAX_PLAUSIBLE

MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
NOM_MOIS = {v: k for k, v in MOIS.items()}
ORDRE_TABLES = ["commandes", "stocks", "fournisseurs", "clients", "production"]

SCHEMA = {
    "commandes": {
        "mots": ["commande", "cmd", "livraison"], "singulier": "commande", "pluriel": "commandes",
        "mesure": "quantite", "date": "date_livraison", "id": "commande_id",
        "cols": {
            "commande_id": {"type": "id", "mots": ["numero", "identifiant", "reference"], "label": "numéro"},
            "client": {"type": "cat", "mots": ["client"], "label": "client"},
            "produit": {"type": "cat", "mots": ["produit"], "label": "produit"},
            "quantite": {"type": "num", "mots": ["quantite", "volume", "unite", "exemplaire"], "label": "quantité", "unite": "unités"},
            "date_livraison": {"type": "date", "mots": ["livraison", "livre", "livree", "echeance", "date"], "label": "date de livraison"},
            "jours_avant_livraison": {"type": "num", "mots": ["jours avant", "dans combien de jours", "delai avant"],
                                      "label": "jours avant la livraison", "unite": "jours"},
        }},
    "stocks": {
        "mots": ["stock", "lot", "inventaire", "entrepot", "reception"], "singulier": "lot", "pluriel": "lots",
        "mesure": "quantite", "date": "date_reception", "id": "lot_id",
        "cols": {
            "lot_id": {"type": "id", "mots": ["numero", "identifiant", "reference"], "label": "lot"},
            "lieu": {"type": "cat", "mots": ["lieu", "entrepot", "emplacement", "endroit"], "label": "lieu"},
            "matiere": {"type": "cat", "mots": ["matiere", "ingredient"], "label": "matière"},
            "quantite": {"type": "num", "mots": ["quantite", "volume", "unite", "combien"], "label": "quantité", "unite": None},
            "unite": {"type": "cat", "mots": ["unite"], "label": "unité d'origine"},
            "date_reception": {"type": "date", "mots": ["reception", "recu", "recue", "recus", "arrive", "arrivee", "date"], "label": "date de réception"},
        }},
    "fournisseurs": {
        "mots": ["fournisseur"], "singulier": "fournisseur", "pluriel": "fournisseurs", "mesure": None, "date": None, "id": "fournisseur",
        "cols": {
            "fournisseur": {"type": "cat", "mots": ["fournisseur"], "label": "fournisseur"},
            "matiere": {"type": "cat", "mots": ["matiere", "ingredient", "livre", "fournit"], "label": "matière"},
            "delai_moyen_jours": {"type": "num", "mots": ["delai", "rapidite", "livraison"], "label": "délai de livraison", "unite": "jours"},
            "fiabilite_pct": {"type": "num", "mots": ["fiabilite", "fiable", "fiabilites"], "label": "fiabilité", "unite": "%"},
            "prix_relatif": {"type": "num", "mots": ["prix", "cout", "tarif", "cher"], "label": "prix relatif", "unite": None},
        }},
    "production": {
        "mots": ["production", "ligne", "produit", "fabrique", "fabrication", "fabriquer"], "singulier": "ligne", "pluriel": "lignes",
        "mesure": "conso_par_jour", "date": None, "id": None,
        "cols": {
            "ligne": {"type": "cat", "mots": ["ligne"], "label": "ligne"},
            "produit": {"type": "cat", "mots": ["produit"], "label": "produit"},
            "matiere": {"type": "cat", "mots": ["matiere", "ingredient", "consomme", "utilise"], "label": "matière"},
            "conso_par_jour": {"type": "num", "mots": ["consommation", "consomme", "conso", "consommee"], "label": "consommation par jour", "unite": "par jour"},
        }},
    "clients": {
        "mots": ["client"], "singulier": "client", "pluriel": "clients", "mesure": None, "date": None, "id": "client_id",
        "cols": {
            "client_id": {"type": "id", "mots": ["identifiant"], "label": "client"},
            "ville": {"type": "cat", "mots": ["ville", "villes", "habite", "situe"], "label": "ville"},
            "email_manquant": {"type": "missing", "mots": ["email", "mail", "courriel", "e"], "label": "e-mail"},
            "telephone_manquant": {"type": "missing", "mots": ["telephone", "portable", "numero"], "label": "téléphone"},
        }},
}
# liens entre tables (pour filtrer une table avec une valeur qui appartient a une autre) : (table, colonne, table, colonne)
LIENS = [("commandes", "produit", "production", "produit"), ("production", "matiere", "fournisseurs", "matiere"),
         ("production", "matiere", "stocks", "matiere"), ("production", "ligne", "stocks", "lieu")]
ROLES = {"delai": {"fournisseurs": "delai_moyen_jours"}, "fiabilite": {"fournisseurs": "fiabilite_pct"},
         "prix": {"fournisseurs": "prix_relatif"},
         "quantite": {"commandes": "quantite", "stocks": "quantite", "production": "conso_par_jour"},
         "date": {"commandes": "date_livraison", "stocks": "date_reception"}}
ADJECTIFS = {"rapide": ("delai", "min"), "vite": ("delai", "min"), "court": ("delai", "min"), "lent": ("delai", "max"),
             "long": ("delai", "max"), "fiable": ("fiabilite", "max"), "cher": ("prix", "max"), "chere": ("prix", "max"),
             "economique": ("prix", "min"), "gros": ("quantite", "max"), "grosse": ("quantite", "max"),
             "grand": ("quantite", "max"), "grande": ("quantite", "max"), "important": ("quantite", "max"),
             "importante": ("quantite", "max"), "petit": ("quantite", "min"), "petite": ("quantite", "min"),
             "ancien": ("date", "min"), "ancienne": ("date", "min"), "vieux": ("date", "min"),
             "recent": ("date", "max"), "recente": ("date", "max"), "proche": ("date", "min"), "urgent": ("date", "min"),
             "urgente": ("date", "min"), "lointain": ("date", "max"), "tard": ("date", "max")}
MOTS_MESURE = {"unite", "unites", "quantite", "quantites", "volume", "volumes", "bouteille", "bouteilles", "kg", "tonne", "tonnes", "carton", "cartons"}
PII = {"nom", "noms", "telephone", "email", "mail", "adresse"}


# ------------------------------------------------------------------ copie de travail (sans donnees personnelles)
def _stocks_propres(data):
    """Stocks avec une quantite nettoyee dans l'unite cible (comme SupplyMind) ; NULL si invalide."""
    conv = PARAMS["conversions"]
    cible = PARAMS["unite_cible"]
    st = data["stocks"].copy()
    q = pd.to_numeric(st["quantite"], errors="coerce")
    facteurs = {("kg", "kg"): 1, ("tonnes", "kg"): conv["tonnes_vers_kg"], ("unites", "unites"): 1,
                ("cartons", "unites"): conv["bouteilles_par_carton"]}
    vals = []
    for qq, m, u in zip(q, st["matiere"], st["unite"]):
        f = facteurs.get((u, cible.get(m)))
        vals.append(qq * f if (f and pd.notna(qq) and 0 < qq <= MAX_PLAUSIBLE) else None)
    out = pd.DataFrame({"lot_id": st["lot_id"], "lieu": st["lieu"], "matiere": st["matiere"], "quantite": vals,
                        "unite": st["unite"], "unite_cible": [cible.get(m) for m in st["matiere"]],
                        "date_reception": st["date_reception"]})
    return out


def _date_iso(v):
    try:
        return str(pd.to_datetime(str(v), format="%Y-%m-%d").date())
    except Exception:
        return None


def construire_base(data):
    """Base SQLite en memoire : jamais de noms, telephones, e-mails ni de salaries."""
    con = sqlite3.connect(":memory:")
    ref = date.fromisoformat(PARAMS["date_reference"])
    cmd = data["commandes"].copy()
    cmd["date_livraison"] = cmd["date_livraison"].map(_date_iso)
    cmd["jours_avant_livraison"] = [(date.fromisoformat(d) - ref).days if d else None for d in cmd["date_livraison"]]
    cmd.to_sql("commandes", con, index=False)
    st = _stocks_propres(data)
    st["date_reception"] = st["date_reception"].map(_date_iso)
    st.to_sql("stocks", con, index=False)
    data["fournisseurs"].to_sql("fournisseurs", con, index=False)
    data["production"].to_sql("production", con, index=False)
    cl = data["clients"]
    pd.DataFrame({"client_id": cl["client_id"], "ville": cl["ville"],
                  "email_manquant": cl["email"].isna() | (cl["email"].astype(str).str.strip() == ""),
                  "telephone_manquant": cl["telephone"].isna() | (cl["telephone"].astype(str).str.strip() == "")}
                 ).astype({"email_manquant": int, "telephone_manquant": int}).to_sql("clients", con, index=False)
    return con


# ------------------------------------------------------------------ index des valeurs (Delta, Ligne 2, Client B...)
def _alias_produit(p):
    return re.sub(r"\s*\d+\s*l$", "", nlu.normaliser(p))


def index_valeurs(data):
    """Liste {alias, table, col, val} : tout ce qu'on peut nommer dans une question."""
    ent = []

    def ajoute(alias, table, col, val):
        alias = nlu.normaliser(alias)
        if alias and alias not in ("unites", "unite"):
            ent.append({"alias": alias, "table": table, "col": col, "val": val})

    for t, d in SCHEMA.items():
        df = data["clients"] if t == "clients" else data[t]
        for c, meta in d["cols"].items():
            if meta["type"] != "cat" or c not in df.columns:
                continue
            for v in df[c].dropna().unique():
                v = str(v)
                ajoute(v, t, c, v)
                if c == "matiere":
                    ajoute(v.replace("concentre_", ""), t, c, v)
                    ajoute(v.rstrip("s"), t, c, v)
                if c == "produit":
                    ajoute(_alias_produit(v), t, c, v)
                    for mot in _alias_produit(v).split():
                        if len(mot) >= 4 and mot not in ("avec", "pour"):
                            ajoute(mot, t, c, v)
                    ajoute("jus", t, c, v) if "jus" in nlu.normaliser(v) else None
                if c in ("lieu", "ligne"):
                    ajoute(nlu.normaliser(v).replace("entrepot ", ""), t, c, v) if "entrepot" in nlu.normaliser(v) else None
                if c == "client":
                    ajoute(v.replace("Client ", ""), t, c, v) if False else None
    return ent


def _est_pluriel_de(token, alias):
    return token == alias or token.rstrip("s") == alias.rstrip("s")


def reperer_valeurs(toks, index):
    """Mentions de valeurs dans la question : [(debut, fin, [candidats])]. Les plus longues d'abord, avec 1 faute tolerée."""
    mentions, pris = [], [False] * len(toks)
    par_alias = {}
    for e in index:
        par_alias.setdefault(e["alias"], []).append(e)
    for n in (3, 2, 1):
        for i in range(len(toks) - n + 1):
            if any(pris[i:i + n]):
                continue
            gram = " ".join(toks[i:i + n])
            cands = par_alias.get(gram) or (par_alias.get(gram.rstrip("s")) if n == 1 and len(gram) > 3 else None)
            if cands and n == 2 and gram.startswith("client ") and len(gram) == 8 and \
                    i + n < len(toks) and toks[i + n] in ("le", "la", "les", "passe", "commande", "plus", "moins", "des", "du", "de", "un", "une",
                                                          "ete", "eu", "fait", "ete", "achete", "recu", "ete", "coute", "paye", "l"):
                cands = None  # « quel client a le plus… » : « a » est le verbe avoir
            if not cands and n == 1 and len(gram) >= 5 and not gram.startswith("manqu"):
                for alias, es in par_alias.items():
                    if " " not in alias and len(alias) >= 5 and nlu.distance(gram, alias) <= 1 and gram[0] == alias[0]:
                        cands = es
                        break
            if cands and not (n == 1 and len(gram) < 3):
                mentions.append((i, i + n, cands))
                for k in range(i, i + n):
                    pris[k] = True
    return sorted(mentions)


# ------------------------------------------------------------------ dates
def pretraiter(question):
    """Remplace les dates ecrites (2026-11-08, 8/11, « 8 novembre ») par des jetons « dateiso20261108 »."""
    t = question.lower()
    ref = date.fromisoformat(PARAMS["date_reference"])

    def iso(y, m, d):
        try:
            return " dateiso%04d%02d%02d " % (y, m, d) if date(y, m, d) else ""
        except ValueError:
            return " "
    t = re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", lambda m: iso(int(m[1]), int(m[2]), int(m[3])), t)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b",
               lambda m: iso((int(m[3]) + (2000 if m[3] and len(m[3]) == 2 else 0)) if m[3] else ref.year, int(m[2]), int(m[1])), t)
    tn = nlu.normaliser(t)
    for mot, delta in (("apres demain", 2), ("avant hier", -2), ("hier", -1), ("aujourd hui", 0), ("demain", 1)):
        j = ref + timedelta(days=delta)
        tn = re.sub(r"\b" + mot + r"\b", " dateiso%04d%02d%02d " % (j.year, j.month, j.day), tn)
    tn = re.sub(r"\bclients? ([abc]) (et|ou|vs|avec|contre|ainsi que) (?:le |les )?(?:clients? )?([abc])\b", r"client \1 \2 client \3", tn)
    tn = re.sub(r"(\d)\s+(\d{3})\b", r"\1\2", tn)  # « 2 000 » -> « 2000 »
    mois = "|".join(MOIS)
    tn = re.sub(r"\bentre (?:le )?(\d{1,2}) et (?:le )?(\d{1,2}) (" + mois + r")( \d{4})?", r"entre \1 \3\4 et \2 \3\4", tn)
    tn = re.sub(r"\b(\d{1,2})(?:er)? (?:er )?(" + mois + r")(?: (\d{4}))?\b",
                lambda m: iso(int(m[3]) if m[3] else ref.year, MOIS[m[2]], int(m[1])), tn)
    tn = re.sub(r"\ben (" + mois + r")(?: (\d{4}))?\b", lambda m: f" moisxx{MOIS[m[1]]:02d}{m[2] or ref.year} ", tn)
    return re.sub(r"\s+", " ", tn).strip()


def _jeton_date(tok):
    m = re.fullmatch(r"dateiso(\d{4})(\d{2})(\d{2})", tok)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def _fin_mois(y, m):
    return date(y + (m == 12), m % 12 + 1, 1)


# ------------------------------------------------------------------ analyse de la question
def _mots_colonne(table, col):
    return SCHEMA[table]["cols"][col]["mots"]


def trouver_colonne(mots, table, types=("cat", "num", "date", "id", "missing")):
    """Colonne de la table designee par un des mots (avec tolerance aux fautes)."""
    for c, meta in SCHEMA[table]["cols"].items():
        if meta["type"] in types and any(len(s) > 1 and nlu.mot_proche(w, s) for w in mots for s in meta["mots"]):
            return c
    return None


def _score_tables(q, toks, mentions, pris):
    sc = {t: 0 for t in SCHEMA}
    libres = [w for i, w in enumerate(toks) if not pris[i]]
    for t, d in SCHEMA.items():
        for w in libres:
            if any(nlu.mot_proche(w, m) or w.rstrip("s") == m for m in d["mots"]):
                sc[t] += 3
        for c, meta in d["cols"].items():
            if any(len(s) > 3 and any(nlu.mot_proche(w, s) for w in libres) for s in meta["mots"]):
                sc[t] += 2
    for _, _, cands in mentions:
        for t in {c["table"] for c in cands}:
            sc[t] += 1
    # regles de bon sens
    if any(w.startswith("command") for w in libres):
        sc["commandes"] += 3
    if re.search(r"\bclients? (a|ont|avec|dont)\b.*\b(plus|moins)\b|\bclient b\b", q) or any(c["col"] == "client" for _, _, cs in mentions for c in cs):
        sc["commandes"] += 3
    if any(c["col"] == "ville" for _, _, cs in mentions for c in cs) or any(w.startswith("ville") for w in libres):
        sc["clients"] += 4
    if any(w.startswith(("email", "mail", "courriel", "telephone")) for w in libres):
        sc["clients"] += 3
    if any(w in ("fournit", "livre", "livrent", "fournissent", "fournisseur", "fournisseurs") for w in libres):
        sc["fournisseurs"] += 2
    if any(w.startswith(("fabriqu", "consomm")) for w in libres):
        sc["production"] += 3
    return sc


def _direction(toks, i_adj, adj):
    """« le plus rapide » -> min de delai ; « le moins cher » -> min de prix."""
    role, sens = ADJECTIFS[adj]
    moins = (i_adj >= 1 and toks[i_adj - 1] == "moins") or (i_adj >= 2 and toks[i_adj - 2] == "moins")
    if moins:
        sens = "min" if sens == "max" else "max"
    return role, sens


def comprendre(question, data, plan_precedent=None, index=None):
    """Retourne un plan (dict) ou None. Voir l'en-tete du module pour le vocabulaire."""
    q = pretraiter(question)
    toks = q.split()
    if not toks:
        return None
    index = index if index is not None else index_valeurs(data)
    mentions = reperer_valeurs(toks, index)
    pris = [False] * len(toks)
    for a, b, _ in mentions:
        for k in range(a, b):
            pris[k] = True
    sc = _score_tables(q, toks, mentions, pris)
    meilleur = max(ORDRE_TABLES, key=lambda t: (sc[t], -ORDRE_TABLES.index(t)))
    suivi = bool(plan_precedent) and (q.startswith(("et ", "mais ", "pareil", "idem")) or sc[meilleur] <= (1 if mentions else 0) or
                                      (len(toks) <= 4 and bool(re.match(r"(en|au|par|avec|sans|pour|dans) ", q)) and not mentions))
    table = meilleur if sc[meilleur] > 0 else None
    court = bool(plan_precedent) and len(toks) <= 4 and bool(re.match(r"(en|au|par|avec|sans|pour|dans) ", q)) and not mentions
    if court:
        table = plan_precedent["table"]
    elif table is None and plan_precedent:
        table = plan_precedent["table"]
    elif suivi and plan_precedent and plan_precedent["table"] in SCHEMA and sc[plan_precedent["table"]] >= sc[meilleur] - 1:
        table = plan_precedent["table"]
    if table is None:
        return None
    d = SCHEMA[table]
    cols = d["cols"]
    plan = {"table": table, "op": None, "mesure": None, "agg": None, "groupes": [], "filtres": [], "tri": None,
            "limite": None, "distinct": None, "ignores": 0}

    # ---------- filtres de valeurs (Delta, Ligne 2, Client B, mangue...)
    prefere_matiere = bool(re.search(r"matiere|concentre|consomm|ingredient|bouteille|sucre", q))
    for a, b, cands in mentions:
        choix = None
        propres = [c for c in cands if c["table"] == table]
        if len(propres) > 1:  # ex. « mangue » dans production : produit ou matiere ?
            propres.sort(key=lambda c: 0 if (c["col"] == "matiere") == prefere_matiere else 1)
        if propres:
            choix = propres[0]
        else:
            # valeur d'une autre table : on filtre par le lien (« commandes de la Ligne 2 »)
            pivot = ["production", "commandes", "fournisseurs", "stocks", "clients"]
            autres = sorted(cands, key=lambda c: (pivot.index(c["table"]), 0 if c["col"] != "matiere" or prefere_matiere else 1))
            choix = autres[0]
        f = {"table": choix["table"], "col": choix["col"], "op": "=", "val": choix["val"]}
        if f not in plan["filtres"]:
            plan["filtres"].append(f)
    for tok in toks:  # identifiants : CMD004, L0014
        m = re.fullmatch(r"cmd0*(\d{1,3})", tok)
        if m:
            plan["filtres"].append({"table": "commandes", "col": "commande_id", "op": "=", "val": f"CMD{int(m[1]):03d}"})
            table = plan["table"] = "commandes"
        m = re.fullmatch(r"l0*(\d{1,4})", tok)
        if m and "stocks" in SCHEMA:
            plan["filtres"].append({"table": "stocks", "col": "lot_id", "op": "=", "val": f"L{int(m[1]):04d}"})
            table = plan["table"] = "stocks"
    d, cols = SCHEMA[table], SCHEMA[table]["cols"]

    if table == "stocks" and re.search(r"quantites? (invalides?|incorrectes?|manquantes?|erronees?|aberrantes?|illisibles?)|(invalides?|aberrant\w*|erron\w*|illisibles?)|\bsans quantite|quantites? (negatives?|nulles?|vides?|absentes?)|\bnegati\w*", q) \
            and not re.search(r"\bpas invalide", q):
        plan["filtres"].append({"table": "stocks", "col": "quantite", "op": "isnull", "val": 1})

    # ---------- manquants (« sans e-mail »)
    if re.search(r"\b(sans|pas d|n ont pas d|aucun) (e mail|email|mail|courriel)", q) or re.search(r"\b(e mail|email|mail)s? manquants?", q):
        plan["table"] = table = "clients"
        plan["filtres"].append({"table": "clients", "col": "email_manquant", "op": "=", "val": 1})
    elif re.search(r"\b(avec|ayant) (un |une )?(e mail|email|mail|courriel)", q):
        plan["table"] = table = "clients"
        plan["filtres"].append({"table": "clients", "col": "email_manquant", "op": "=", "val": 0})
    if re.search(r"\b(sans|pas de|manque de) telephone", q):
        plan["table"] = table = "clients"
        plan["filtres"].append({"table": "clients", "col": "telephone_manquant", "op": "=", "val": 1})
    d, cols = SCHEMA[table], SCHEMA[table]["cols"]

    if table == "stocks" and re.search(r"\bentrepots?\b", q) and not any(f["col"] == "lieu" for f in plan["filtres"]):
        plan["filtres"].append({"table": "stocks", "col": "lieu", "op": "like", "val": "Entrepot%"})

    # ---------- comparaisons numeriques et dates
    def col_pour(mots, types):
        c = trouver_colonne(mots, table, types)
        if c:
            return c
        if "num" in types and d["mesure"]:
            return d["mesure"]
        if "date" in types:
            return d["date"]
        return None

    nombre = r"(\d+(?:[.,]\d+)?)"
    jeton = r"(dateiso\d{8}|moisxx\d{6})"
    comparateurs = [("entre", r"entre " + nombre + r" et " + nombre, "between"),
                    ("entre_d", r"entre " + jeton + r" et " + jeton, "between_d"),
                    (">", r"(?:plus de|plus que|superieure? a|superieurs? a|au dessus de|depasse(?:nt)?|depassant|strictement plus de) " + nombre, ">"),
                    (">=", r"(?:au moins|minimum de|a partir de|egale? ou superieure? a) " + nombre, ">="),
                    ("<", r"(?:moins de|moins que|inferieure? a|inferieurs? a|en dessous de|sous les|sous) " + nombre, "<"),
                    ("<=", r"(?:au plus|maximum de|jusqu a) " + nombre, "<="),
                    ("=", r"(?:egale? a|exactement|egal a) " + nombre, "=")]
    deja = []
    for _, motif, op in comparateurs:
        for m in re.finditer(motif, q):
            if any(m.start() < e and m.end() > s for s, e in deja):
                continue
            deja.append((m.start(), m.end()))
            avant = q[:m.start()].split()[-5:]
            apres = q[m.end():].split()[:2]
            if op == "between_d":
                c = d["date"]
                if c:
                    plan["filtres"].append({"table": table, "col": c, "op": "between", "val": [_jeton_date(m[1]), _jeton_date(m[2])]})
                continue
            c = col_pour(avant + apres, ("num",)) if True else None
            if c is None:
                continue
            if op == "between":
                plan["filtres"].append({"table": table, "col": c, "op": "between", "val": [float(m[1].replace(",", ".")), float(m[2].replace(",", "."))]})
            else:
                plan["filtres"].append({"table": table, "col": c, "op": op, "val": float(m[1].replace(",", "."))})
    # dates : avant / apres / le / en <mois>
    for m in re.finditer(r"\b(avant|d ici|anterieur(?:e)? a|apres|depuis|a partir de|posterieur(?:e)? a|le|du|au)\s+(?:le\s+)?(dateiso\d{8})", q):
        if any(m.start() < e and m.end() > s for s, e in deja):
            continue
        c = d["date"]
        if c is None:
            continue
        j = _jeton_date(m[2])
        mot = m[1]
        op = "<" if mot in ("avant", "d ici") or mot.startswith("anterieur") else \
            (">" if mot == "apres" or mot.startswith("posterieur") else (">=" if mot in ("depuis", "a partir de") else "="))
        plan["filtres"].append({"table": table, "col": c, "op": op, "val": j})
    for m in re.finditer(r"moisxx(\d{2})(\d{4})", q):
        c = d["date"]
        if c is None:
            continue
        mm, yy = int(m[1]), int(m[2])
        plan["filtres"].append({"table": table, "col": c, "op": "between_incl",
                                "val": [f"{yy}-{mm:02d}-01", str(_fin_mois(yy, mm))]})
    if not any(f["col"] == d["date"] for f in plan["filtres"]) and d["date"]:
        for tok in toks:  # date seule sans mot-cle : « livrées le 8 novembre » est deja traite ; ici « 8 novembre » nu
            j = _jeton_date(tok)
            if j:
                plan["filtres"].append({"table": table, "col": d["date"], "op": "=", "val": j})

    # ---------- operation
    nombres_mots = {**{k: v for k, v in nlu.NOMBRES.items() if k not in ("un", "une")}}
    m_top = re.search(r"\b(?:les|top)\s+(\d+|" + "|".join(nombres_mots) + r")\s+(?:plus|premiers?|derniers?|meilleurs?|pires?|moins)", q) or \
        re.search(r"\btop\s+(\d+|" + "|".join(nombres_mots) + r")\b", q)
    if m_top:
        plan["limite"] = int(m_top[1]) if m_top[1].isdigit() else nombres_mots[m_top[1]]

    sup = None  # (role, sens) ou (« nombre de X », sens)
    for i, w in enumerate(toks):
        for adj in ADJECTIFS:
            if w == adj or (len(adj) > 4 and w not in ("faible", "faibles") and nlu.distance(w, adj) <= 1):
                if i >= 1 and toks[i - 1] in ("plus", "moins") or (i >= 2 and toks[i - 2] in ("plus", "moins")) or w in ("recent", "proche") and "plus" in toks:
                    sup = _direction(toks, i, adj)
    for i, w in enumerate(toks):
        if w in ("derniere", "dernier", "premiere", "premier") and i + 1 < len(toks) and toks[i + 1] in ("commande", "lot", "livraison", "reception", "arrivage"):
            sup = ("date", "max" if w.startswith("dern") else "min")
    m_plus_de = re.search(r"\ble (plus|moins) (?:de|d|des)\s+(\w+)", q)
    rep_plus = re.search(r"\b(?:le|la|les) (plus|moins) (?:represent|frequen|courant|present|commun|nombreu)\w*", q)
    par_mesure = None
    for mm in re.finditer(r"\b(?:par|selon|en fonction de|classes? par|trie par)\s+(?:la |le |les |l )?(\w+)", q):
        c = trouver_colonne([mm[1]], table, ("num",))
        if c:
            par_mesure = c
    mot_quantite = re.search(r"\b(plus|moins) (?:de )?(?:grand|grande|gros|grosse|haut|haute|eleve|elevee|petit|petite|bas|basse|faible)\b", q)
    pourcent = re.search(r"pourcentage|proportion|\bpart\b|%", q)
    moyenne = re.search(r"\bmoyenn|\bmoyen\b|\bmoyens\b", q)
    total = re.search(r"\btotal|\bsomme\b|au total|cumul|\bglobal", q)
    exist = re.search(r"^(est ce que|y a t il|existe t il|a t on|avons nous|ya t il|il y a t il)", q)
    combien = re.search(r"\bcombien (?:de |d |des |du )?(\w+)?", q)
    nombre_de = re.search(r"\bnombre (?:de |d |des )?(\w+)", q)
    liste = re.search(r"\b(liste|lister|montre|affiche|donne|quels|quelles|quel|quelle|lesquels|lesquelles|qui|nom des|noms des)\b", q)
    par = None
    for mm in re.finditer(r"\b(?:par|pour chaque|chaque|selon)\s+(\w+)", q):
        if trouver_colonne([mm[1]], table, ("cat",)) or (mm[1].startswith("ligne") and table == "commandes"):
            par = mm
            break

    op_defaut = False
    mesure = d["mesure"]
    meilleur_mot = re.search(r"\b(meilleur|meilleure|pire)\b", q)
    # colonne numerique designee par un mot de la question (« fiabilite », « delai », « prix »)
    mot_col = trouver_colonne([w for i, w in enumerate(toks) if not pris[i]], table, ("num",))
    if mot_col and mot_col != "jours_avant_livraison":
        mesure = mot_col
    if re.search(r"jours avant|dans combien de jours|jours restants|reste.{0,12}jours", q) and table == "commandes":
        mesure = "jours_avant_livraison"

    comparer = None
    if re.search(r"\bcompar|par rapport a|\bversus\b|\bvs\b|difference entre|differences? de|mieux que|meilleur que|plutot que|ou bien", q):
        multi = {}
        for f in plan["filtres"]:
            if f["op"] == "=" and isinstance(f["val"], str) and f["table"] == table:
                multi.setdefault(f["col"], []).append(f["val"])
        multi = {c: v for c, v in multi.items() if len(v) > 1}
        if multi:
            comparer = max(multi, key=lambda c: len(multi[c]))
    if comparer:
        plan["op"], plan["groupes"] = "compare", [comparer]
    elif exist:
        plan["op"] = "exists"
    elif pourcent:
        plan["op"] = "percent"
    elif moyenne:
        plan["op"] = "avg"
        plan["mesure"] = mesure
    elif par_mesure and (m_top or re.search(r"classement|classe|trie|ordre", q)) and \
            any(trouver_colonne([w], table, ("cat",)) for i, w in enumerate(toks) if not pris[i]):
        col = next(trouver_colonne([w], table, ("cat",)) for i, w in enumerate(toks) if not pris[i] and trouver_colonne([w], table, ("cat",)))
        plan["op"], plan["agg"], plan["groupes"], plan["mesure"] = "group", "sum", [col], par_mesure
        plan["tri"] = "asc" if re.search(r"\bmoins\b|derniers|pires|plus petit", q) else "desc"
    elif meilleur_mot and mot_col in ("delai_moyen_jours", "prix_relatif", "fiabilite_pct", "quantite"):
        bon_bas = mot_col in ("delai_moyen_jours", "prix_relatif")
        plan["op"] = ("min" if bon_bas else "max") if meilleur_mot[1].startswith("meilleur") else ("max" if bon_bas else "min")
        plan["mesure"] = mot_col
    elif sup and not m_plus_de:
        role, sens = sup
        col = ROLES.get(role, {}).get(table)
        if col is None:  # ex. « le plus rapide » mais la table n'a pas de delai : on cherche la table qui l'a
            for t2 in ORDRE_TABLES:
                if t2 in ROLES.get(role, {}) and sc.get(t2, 0) >= 0 and t2 == table:
                    col = ROLES[role][t2]
            if col is None and role in ROLES and len(ROLES[role]) >= 1 and table not in ROLES[role]:
                t2 = next(iter(ROLES[role]))
                plan["table"] = table = t2
                d, cols = SCHEMA[table], SCHEMA[table]["cols"]
                col = ROLES[role][t2]
        plan["op"] = sens
        plan["mesure"] = col
        # « quel client a la plus grosse commande » -> ligne ; « quel produit est le plus commande » -> regroupement
    elif m_plus_de and table == "production" and re.search(r"consomm|utilis", q):
        plan["op"] = "max" if m_plus_de[1] == "plus" else "min"
        plan["mesure"] = "conso_par_jour"
    elif rep_plus:
        plan["op"], plan["agg"] = "group", "count"
        plan["tri"] = "desc" if rep_plus[1] == "plus" else "asc"
        plan["limite"] = plan["limite"] or 1
    elif m_plus_de or (re.search(r"\ble (plus|moins) (commande|livre|fournit|consomme|achete)", q)):
        plan["op"] = "group"
        plan["agg"] = "count" if m_plus_de else "sum"
        plan["tri"] = "desc" if "plus" in (m_plus_de.group(1) if m_plus_de else re.search(r"(plus|moins)", q)[1]) else "asc"
        if m_plus_de and m_plus_de[2].rstrip("s") in MOTS_MESURE:
            plan["agg"] = "sum"
        plan["limite"] = plan["limite"] or 1
    elif mot_quantite:
        sens = "min" if re.search(r"(plus|moins)", mot_quantite[0]) and re.search(r"petit|bas|faible", mot_quantite[0]) else "max"
        plan["op"] = sens
        plan["mesure"] = mesure
    elif re.search(r"\b(maximum|minimum|maximale?|minimale?)\b", q):
        plan["op"] = "max" if re.search(r"maxim", q) else "min"
        plan["mesure"] = mesure
    elif total or (combien and combien[1] and combien[1].rstrip("s") in MOTS_MESURE) or re.search(r"\b(quelle|quel) (est )?(la |le )?(quantite|volume)\b", q) and table in ("stocks", "commandes"):
        plan["op"] = "sum"
        plan["mesure"] = mesure
    elif re.search(r"\b(quantite|volume)s?\b", q) and table in ("stocks", "commandes") and not par and \
            not any(f["op"] == "isnull" for f in plan["filtres"]) and \
            not re.search(r"\b(liste|lister|montre|affiche|quels|quelles|lesquels)\b", q):
        plan["op"] = "sum"
        plan["mesure"] = mesure
    elif combien or nombre_de:
        plan["op"] = "count"
    elif liste or plan["filtres"] or par:
        plan["op"] = "list"
        op_defaut = True
    else:
        plan["op"] = None

    # regroupement : « par ville », « pour chaque client »
    if par and plan["op"] in ("count", "sum", "avg", "max", "min", "list", "percent", None, "group"):
        col = trouver_colonne([par[1]], table, ("cat",))
        if col is None and par[1] in ("ligne", "lignes") and table == "commandes":
            col = "ligne"
        if col:
            plan["groupes"] = [col]
            if plan["op"] in ("list", None):
                plan["op"] = "group"
                plan["agg"] = "count"
                if mesure and re.search(r"\b(quantite|quantites|volume|volumes|total|combien d|kg|tonnes?)\b", q) and table in ("stocks", "commandes", "production"):
                    plan["agg"], plan["mesure"] = "sum", mesure
            elif plan["op"] in ("count", "sum", "avg", "max", "min"):
                plan["agg"], plan["op"] = plan["op"], "group"
    if plan["op"] == "group" and not plan["groupes"]:
        # « quel client a le plus de commandes ? » : on regroupe par la colonne nommee juste apres « quel / quelle »
        m = re.match(r"(?:et )?(?:quel|quelle|quels|quelles|qui)\s+(?:est\s+)?(?:le |la |les |l )?(\w+)", q)
        col = trouver_colonne([m[1]], table, ("cat",)) if m else None
        if col is None:
            for w in toks:
                col = trouver_colonne([w], table, ("cat",))
                if col:
                    break
        if col:
            plan["groupes"] = [col]
        else:
            plan["op"] = None
    if plan["op"] == "group" and plan["agg"] in (None, "sum") and mesure:
        plan["mesure"] = mesure
    if plan["op"] == "group" and plan["agg"] == "count" and re.search(r"le plus commande|plus commande", q) and mesure and table == "commandes":
        plan["agg"], plan["mesure"] = "sum", mesure
    if plan["op"] in ("max", "min") and plan["mesure"] is None:
        plan["mesure"] = mesure
    if plan["op"] in ("max", "min") and plan["mesure"] and re.search(r"quel(?:le)?s? (\w+) (?:a|ont|est|sont|possede)", q):
        pass

    # entite comptee : « combien de produits / de lignes / de villes »
    if plan["op"] == "count":
        mot = (combien and combien[1]) or (nombre_de and nombre_de[1]) or ""
        col = trouver_colonne([mot], table, ("cat",)) if mot else None
        if col and col not in ("client",) or (col == "client" and table == "commandes"):
            plan["distinct"] = col
        if table == "fournisseurs" and not plan["distinct"]:
            plan["distinct"] = "fournisseur"
        if table == "production" and not plan["distinct"]:
            plan["distinct"] = "ligne" if re.search(r"\blignes?\b", q) else ("produit" if re.search(r"\bproduits?\b", q) else None)
        if table == "commandes" and re.search(r"\bclients?\b", q) and re.search(r"command", q) and not plan["distinct"] and mot.startswith("client"):
            plan["distinct"] = "client"
    if plan["op"] == "list":
        m = re.search(r"\b(?:quels|quelles|quel|quelle|lesquels|lesquelles) (\w+)", q)
        col = trouver_colonne([m[1]], table, ("cat",)) if m else None
        if col and col not in [f["col"] for f in plan["filtres"] if f["op"] == "="] or (col and plan["filtres"] and table == "clients"):
            plan["distinct"] = col
    if plan["op"] == "list" and not plan["distinct"]:
        m = re.search(r"\b(?:liste|lister|montre|affiche|donne|enumere)(?: moi)? (?:(?:la|le|les|l|des|de|d|du|toutes|tous) )*(\w+)", q)
        col = trouver_colonne([m[1]], table, ("cat",)) if m else None
        if col and (col != d["id"] or table == "fournisseurs") and not any(f["col"] == col for f in plan["filtres"]) and (m[1].rstrip("s") != d["singulier"] or table == "fournisseurs"):
            plan["distinct"] = col
    if m_top and plan["op"] in ("list", None) and sup:
        plan["op"] = "list"
        plan["tri"] = "asc" if sup[1] == "min" else "desc"
        plan["mesure"] = ROLES[sup[0]].get(table) or mesure
    elif m_top and plan["op"] in ("max", "min"):
        plan["op"], plan["tri"] = "list", ("asc" if plan["op"] == "min" else "desc")
    elif m_top and plan["op"] == "group":
        plan["tri"] = plan["tri"] or "desc"
    if plan["op"] == "percent":
        plan["agg"] = "count"

    signal = bool(mentions) or bool(plan["filtres"]) or plan["op"] not in (None, "list") or bool(mot_col) or bool(par)
    if suivi and not signal:
        return None
    # fusion avec le plan precedent (« et pour le client B ? », « et en moyenne ? »)
    if plan_precedent and suivi:
        prec = plan_precedent
        if plan["table"] == prec["table"] or plan["op"] is None:
            plan["table"] = table = prec["table"]
            for cle in ("op", "mesure", "agg", "groupes", "tri", "limite", "distinct"):
                if plan.get(cle) in (None, [], 0) or (op_defaut and not par):
                    plan[cle] = prec.get(cle)
            nouvelles = {f["col"] for f in plan["filtres"]}
            plan["filtres"] = plan["filtres"] + [f for f in prec["filtres"] if f["col"] not in nouvelles]
    a_id = any(f["col"] in ("commande_id", "lot_id") for f in plan["filtres"])
    if a_id and plan["op"] in ("sum", "avg", "max", "min", "count") and mot_col:
        plan["op"], plan["mesure"] = "list", mot_col
        plan["distinct"] = None
    if mesure == "jours_avant_livraison" and table == "commandes" and plan["op"] in ("count", "list", None):
        plan["op"], plan["mesure"], plan["mesure_dite"] = "list", "jours_avant_livraison", "jours_avant_livraison"
    elif plan["op"] == "list" and mot_col and (table in ("fournisseurs", "production") or a_id) and \
            not any(f["col"] == mot_col and f["op"] != "=" for f in plan["filtres"]):
        plan["mesure_dite"] = mot_col
    if suivi and plan["op"] == "count" and re.search(r"\ben (quantite|volume|unites|total)\b|\bau total\b", q):
        plan["op"], plan["mesure"] = "sum", SCHEMA[plan["table"]]["mesure"]
        plan["distinct"] = None
    if plan["op"] is None:
        return None
    if plan["op"] in ("sum", "avg", "max", "min") and plan["mesure"] is None:
        plan["mesure"] = SCHEMA[plan["table"]]["mesure"]
    if plan["op"] in ("sum", "avg", "max", "min") and plan["mesure"] is None:
        return None
    return plan


# ------------------------------------------------------------------ plan -> SQL
def _lit(v):
    if isinstance(v, (int, float)):
        return repr(int(v)) if float(v).is_integer() else repr(float(v))
    return "'" + str(v).replace("'", "''") + "'"


def _cond(table, f):
    col = f"{table}.{f['col']}"
    op, v = f["op"], f["val"]
    if op == "between":
        return f"{col} BETWEEN {_lit(v[0])} AND {_lit(v[1])}"
    if op == "in":
        return f"{col} IN (" + ", ".join(_lit(x) for x in v) + ")"
    if op == "isnull":
        return f"{col} IS NULL"
    if op == "like":
        return f"{col} LIKE {_lit(v)}"
    if op == "between_incl":
        return f"{col} >= {_lit(v[0])} AND {col} < {_lit(v[1])}"
    return f"{col} {op} {_lit(v)}"


def _chemin(src, dst):
    """Suite de liens pour aller de la table src a la table dst."""
    vus, file = {src}, [(src, [])]
    while file:
        t, chem = file.pop(0)
        if t == dst:
            return chem
        for a, ca, b, cb in LIENS:
            for (x, cx, y, cy) in ((a, ca, b, cb), (b, cb, a, ca)):
                if x == t and y not in vus:
                    vus.add(y)
                    file.append((y, chem + [(x, cx, y, cy)]))
    return None


def _clause(ancre, f):
    """Condition sur la table d'ancrage, par sous-requetes si le filtre vient d'une autre table."""
    if f["table"] == ancre:
        return _cond(ancre, f)
    chem = _chemin(ancre, f["table"])
    if not chem:
        return None
    interne = f"SELECT {chem[-1][3]} FROM {chem[-1][2]} WHERE {_cond(chem[-1][2], f)}"
    for (x, cx, y, cy) in reversed(chem[:-1]):
        interne = f"SELECT {cy} FROM {y} WHERE {cy} IN ({interne})" if False else f"SELECT {cx} FROM {x} WHERE {cx} IN ({interne})"
    return f"{ancre}.{chem[0][1]} IN ({interne})"


# colonnes comparees : (colonne, fonction, alias, libelle, sens du « mieux » : -1 plus petit, +1 plus grand, 0 aucun, unite)
COMPARE = {"fournisseurs": [("delai_moyen_jours", "AVG", "delai", "délai moyen", -1), ("fiabilite_pct", "AVG", "fiabilite", "fiabilité moyenne", 1),
                            ("prix_relatif", "AVG", "prix", "prix relatif moyen", -1)],
           "commandes": [(None, "COUNT", "nb", "nombre de commandes", 0), ("quantite", "SUM", "quantite", "quantité totale", 0)],
           "stocks": [(None, "COUNT", "nb", "nombre de lots", 0), ("quantite", "SUM", "quantite", "quantité totale", 0)],
           "production": [("conso_par_jour", "SUM", "conso", "consommation par jour", 0)],
           "clients": [(None, "COUNT", "nb", "nombre de clients", 0)]}
UNITES_COMPARE = {"delai": " jours", "fiabilite": " %", "prix": "", "nb": "", "quantite": "", "conso": ""}


def construire_sql(plan):
    """Retourne (sql, colonnes_affichees) ou (None, motif) si le plan n'est pas realisable."""
    t, op = plan["table"], plan["op"]
    conds = []
    groupes_egal = {}
    for f in plan["filtres"]:
        if f["op"] == "=" and isinstance(f["val"], str):
            groupes_egal.setdefault((f["table"], f["col"]), []).append(f)
    filtres = []
    deja = set()
    for f in plan["filtres"]:
        cle = (f["table"], f["col"])
        if f["op"] == "=" and isinstance(f["val"], str) and len(groupes_egal[cle]) > 1:
            if cle in deja:
                continue
            deja.add(cle)
            filtres.append({"table": f["table"], "col": f["col"], "op": "in", "val": [g["val"] for g in groupes_egal[cle]]})
        else:
            filtres.append(f)
    for f in filtres:
        c = _clause(t, f)
        if c is None:
            return None, f"je ne sais pas relier {f['col']} à {t}"
        conds.append(c)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    jointure = ""
    grp = list(plan["groupes"])
    exprs = {}
    if "ligne" in grp and t == "commandes":
        jointure = " JOIN (SELECT DISTINCT produit, ligne FROM production) pl ON pl.produit = commandes.produit"
        exprs["ligne"] = "pl.ligne"
    gsql = ", ".join(exprs.get(g, f"{t}.{g}") for g in grp)
    m = plan.get("mesure")
    if op == "count":
        cible = f"COUNT(DISTINCT {t}.{plan['distinct']})" if plan.get("distinct") else "COUNT(*)"
        return f"SELECT {cible} AS valeur FROM {t}{jointure}{where}", ["valeur"]
    if op == "exists":
        return f"SELECT COUNT(*) AS valeur FROM {t}{jointure}{where}", ["valeur"]
    if op == "percent":
        if grp:
            return (f"SELECT {gsql} AS groupe, COUNT(*) AS valeur FROM {t}{jointure}{where} GROUP BY {gsql} ORDER BY valeur DESC",
                    ["groupe", "valeur"])
        return (f"SELECT (SELECT COUNT(*) FROM {t}{jointure}{where}) AS valeur, (SELECT COUNT(*) FROM {t}) AS total", ["valeur", "total"])
    if op in ("sum", "avg") and not grp:
        fonction = "SUM" if op == "sum" else "AVG"
        return (f"SELECT {fonction}({t}.{m}) AS valeur, COUNT({t}.{m}) AS n_valides, COUNT(*) AS n_total "
                f"FROM {t}{jointure}{where}", ["valeur"])
    if op == "group":
        agg = plan.get("agg") or "count"
        if agg == "count":
            expr = f"COUNT(DISTINCT {t}.{plan['distinct']})" if plan.get("distinct") else "COUNT(*)"
        else:
            expr = f"{agg.upper()}({t}.{m})"
        sens = "ASC" if plan.get("tri") == "asc" else "DESC"
        sql = f"SELECT {gsql} AS groupe, {expr} AS valeur FROM {t}{jointure}{where} GROUP BY {gsql} ORDER BY valeur {sens}, groupe"
        return sql, ["groupe", "valeur"]
    if op == "compare":
        selects = ", ".join(f"{fn}({(t + '.' + c) if c else '*'}) AS {a}" for c, fn, a, _, _ in COMPARE[t])
        return (f"SELECT {gsql} AS groupe, {selects} FROM {t}{jointure}{where} GROUP BY {gsql} ORDER BY groupe",
                ["groupe"] + [a for _, _, a, _, _ in COMPARE[t]])
    if op in ("max", "min", "list"):
        affiche = _colonnes_affichees(plan)
        tri = plan.get("tri") or ("desc" if op == "max" else "asc" if op == "min" else None)
        ordre = f" ORDER BY {t}.{m} {tri.upper()}" if (m and tri) else ""
        dist = "DISTINCT " if plan.get("distinct") else ""
        cols = [plan["distinct"]] if plan.get("distinct") else affiche
        select = ", ".join(f"{t}.{c}" for c in cols)
        lim = f" LIMIT {plan['limite']}" if plan.get("limite") and op != "max" and op != "min" else ""
        return f"SELECT {dist}{select} FROM {t}{jointure}{where}{ordre}{lim}", cols
    return None, "opération inconnue"


def _colonnes_affichees(plan):
    t = plan["table"]
    cols = [c for c, meta in SCHEMA[t]["cols"].items() if meta["type"] != "missing"]
    if t == "stocks":
        cols = ["lot_id", "lieu", "matiere", "quantite", "unite_cible", "date_reception"]
    if t == "commandes":
        cols = ["commande_id", "client", "produit", "quantite", "date_livraison"]
        if plan.get("mesure") == "jours_avant_livraison":
            cols.append("jours_avant_livraison")
    if t == "clients":
        cols = ["client_id", "ville"]
    return cols


# ------------------------------------------------------------------ mise en forme
def _n(x):
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
    return f"{int(round(x)):,}".replace(",", " ")


def _date_fr(s):
    try:
        d = date.fromisoformat(str(s))
        return f"{d.day}{'er' if d.day == 1 else ''} {NOM_MOIS[d.month]} {d.year}"
    except ValueError:
        return str(s)


def _matiere(m):
    return str(m).replace("concentre", "concentré").replace("_", " ")


def _valeur(col, v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if col in ("date_livraison", "date_reception"):
        return _date_fr(v)
    if col == "matiere":
        return _matiere(v)
    if isinstance(v, (int, float)) or hasattr(v, "dtype"):
        try:
            return _n(float(v))
        except (TypeError, ValueError):
            pass
    return str(v)


def _phrase_filtre(f, ancre=None):
    c, v, op = f["col"], f["val"], f["op"]
    if op == "like":
        return "dans les entrepôts"
    if c == "client":
        return f"pour le {v}"
    if c == "produit":
        return f"pour le {v}"
    if c == "matiere":
        return f"de {_matiere(v)}"
    if c in ("lieu",):
        return f"dans « {v} »"
    if c == "ligne":
        return f"sur la {v}"
    if c == "fournisseur":
        return f"chez {v}" if ancre in (None, "fournisseurs") else f"de matières fournies par {v}"
    if c == "ville":
        return f"à {v}"
    if c == "unite":
        return f"exprimés en {v}"
    if c in ("commande_id", "lot_id"):
        return f"« {v} »"
    if c == "quantite" and op == "isnull":
        return "dont la quantité est invalide ou manquante"
    if c == "email_manquant":
        return "sans e-mail" if v == 1 else "avec e-mail"
    if c == "telephone_manquant":
        return "sans téléphone" if v == 1 else "avec téléphone"
    if op == "like":
        return "dans les entrepôts"
    sens = {">": "au-dessus de", ">=": "d'au moins", "<": "en dessous de", "<=": "d'au plus", "=": "égal à"}
    nom = next((meta["label"] for t in SCHEMA.values() for k, meta in t["cols"].items() if k == c), c)
    if c.startswith("date"):
        mots = {"<": "avant le", ">": "après le", ">=": "à partir du", "<=": "jusqu'au", "=": "le"}
        if op in ("between", "between_incl"):
            if op == "between_incl":
                debut = date.fromisoformat(v[0])
                return f"en {NOM_MOIS[debut.month]} {debut.year}"
            pre = {"date_reception": "avec réception ", "date_livraison": "avec livraison "}.get(c, "")
            return f"{pre}entre le {_date_fr(v[0])} et le {_date_fr(v[1])}"
        pre = {"date_reception": "avec réception ", "date_livraison": "avec livraison "}.get(c, "")
        return f"{pre}{mots[op]} {_date_fr(v)}"
    if op == "between":
        return f"avec {nom} entre {_n(v[0])} et {_n(v[1])}"
    return f"avec {nom} {sens[op]} {_n(v)}"


def decrire_filtres(plan, sans=()):
    multi, vus, ph = {}, set(), []
    for f in plan["filtres"]:
        if f["op"] == "=" and isinstance(f["val"], str):
            multi.setdefault((f["table"], f["col"]), []).append(f["val"])
    for f in plan["filtres"]:
        if f["col"] in sans:
            continue
        cle = (f["table"], f["col"])
        if f["op"] == "=" and isinstance(f["val"], str):
            if cle in vus:
                continue
            vus.add(cle)
            ph.append(_phrase_filtre({**f, "val": " ou ".join(multi[cle])}, plan["table"]))
        else:
            ph.append(_phrase_filtre(f, plan["table"]))
    return (" " + " ".join(ph)) if ph else ""


FEMININS = {"commande", "ligne", "ligne de production", "ville", "matière"}


def _aucun(sing):
    return ("Aucune " if sing in FEMININS else "Aucun ") + sing


def _pluriel(n, sing, plur):
    return sing if n == 1 else plur


def _unite_de(plan, df=None):
    t, m = plan["table"], plan.get("mesure")
    if not m:
        return ""
    meta = SCHEMA[t]["cols"].get(m, {})
    if t == "stocks" and m == "quantite":
        mats = {f["val"] for f in plan["filtres"] if f["col"] == "matiere"}
        unites = {PARAMS["unite_cible"].get(x) for x in mats}
        return (" " + ("unités" if unites == {"unites"} else "kg")) if len(unites) == 1 else ""
    u = meta.get("unite")
    return f" {u}" if u and u not in ("%",) else (" %" if u == "%" else "")


def _label_mesure(plan):
    t, m = plan["table"], plan.get("mesure")
    if not m:
        return ""
    return SCHEMA[t]["cols"][m]["label"]


def _libelle_ligne(plan, row):
    """Une ligne de resultat en phrase : « CMD004 (Client B, 2 400 × Nectar de mangue 1 L, livraison le 7 novembre 2026) »."""
    t = plan["table"]
    r = row
    if t == "commandes":
        return (f"{r['commande_id']} ({r['client']}, {_n(float(r['quantite']))} × {r['produit']}, "
                f"livraison le {_date_fr(r['date_livraison'])})")
    if t == "stocks":
        q = "quantité invalide" if r["quantite"] is None or pd.isna(r["quantite"]) else f"{_n(float(r['quantite']))} {str(r['unite_cible']).replace('unites', 'unités')}"
        return f"{r['lot_id']} ({_matiere(r['matiere'])}, {r['lieu']}, {q}, reçu le {_date_fr(r['date_reception'])})"
    if t == "fournisseurs":
        return (f"{r['fournisseur']} pour {_matiere(r['matiere'])} (délai {_n(float(r['delai_moyen_jours']))} jours, "
                f"fiabilité {_n(float(r['fiabilite_pct']))} %, prix relatif {_n(float(r['prix_relatif']))})")
    if t == "production":
        return f"{r['ligne']} : {r['produit']}, {_matiere(r['matiere'])} ({_n(float(r['conso_par_jour']))} par jour)"
    if t == "clients":
        return f"{r['client_id']} ({r['ville']})"
    return " ; ".join(f"{k} {v}" for k, v in r.items())


def noms_colonnes(plan, cols):
    t = plan["table"]
    out = {}
    for c in cols:
        meta = SCHEMA[t]["cols"].get(c)
        out[c] = meta["label"] if meta else {"valeur": "valeur", "groupe": "groupe", "unite_cible": "unité", "total": "total", "delai": "délai moyen (jours)",
                                             "fiabilite": "fiabilité moyenne (%)", "prix": "prix relatif moyen", "nb": "nombre", "quantite": "quantité",
                                             "conso": "consommation par jour"}.get(c, c)
    return out


# ------------------------------------------------------------------ execution et reponse
def repondre(question, data, plan_precedent=None, con=None):
    """Retourne un dict {texte, tableau, requete, plan, comprehension, tables, explication} ou None si la question n'est pas comprise."""
    plan = comprendre(question, data, plan_precedent)
    if plan is None:
        return None
    return executer(plan, data, con)


def executer(plan, data, con=None):
    sql, cols = construire_sql(plan)
    if sql is None:
        return {"texte": f"Je ne peux pas répondre à cette question avec les données disponibles : {cols}.", "tableau": None,
                "requete": None, "plan": plan, "tables": set(), "explication": [], "impossible": True}
    con = con or construire_base(data)
    df = pd.read_sql_query(sql, con)
    t, op = plan["table"], plan["op"]
    tables = {t} | {f["table"] for f in plan["filtres"]}
    desc = decrire_filtres(plan)
    d = SCHEMA[t]
    notes = []
    notes_ign = 0
    if t == "stocks" and plan.get("mesure") == "quantite" or (t == "stocks" and op == "list"):
        conds = [c for c in (_clause("stocks", f) for f in plan["filtres"]) if c]
        w = (" WHERE " + " AND ".join(conds)) if conds else ""
        notes_ign = int(pd.read_sql_query(f"SELECT COUNT(*) AS n FROM stocks{w} {'AND' if w else 'WHERE'} quantite IS NULL", con)["n"][0])
        if notes_ign and not any(f["op"] == "isnull" for f in plan["filtres"]):
            notes.append(f"{notes_ign} lot{'s' if notes_ign > 1 else ''} ignoré{'s' if notes_ign > 1 else ''} (quantité invalide ou manquante)"
                         if op != "list" else f"{notes_ign} lot{'s ont' if notes_ign > 1 else ' a'} une quantité invalide (affichée « — »)")
    tableau, texte = None, ""
    sing, plur = d["singulier"], d["pluriel"]
    if t == "production" and plan.get("distinct") == "produit":
        sing, plur = "produit", "produits"
    if plan.get("distinct") == "ligne":
        sing, plur = "ligne de production", "lignes de production"
    if plan.get("distinct") == "ville":
        sing, plur = "ville", "villes"
    if plan.get("distinct") == "client":
        sing, plur = "client", "clients"
    if plan.get("distinct") in ("matiere",):
        sing, plur = "matière", "matières"
    if plan.get("distinct") == "fournisseur":
        sing, plur = "fournisseur", "fournisseurs"

    if op == "count":
        n = int(df["valeur"][0])
        if plan.get("distinct") or True:
            texte = f"Il y a {_n(n)} {_pluriel(n, sing, plur)}{desc}." if n else f"Il n'y a {_aucun(sing).lower()}{desc}."
    elif op == "exists":
        n = int(df["valeur"][0])
        texte = (f"Oui : {_n(n)} {_pluriel(n, sing, plur)}{desc}." if n else f"Non : {_aucun(sing).lower()}{desc}.")
    elif op in ("sum", "avg"):
        v = df["valeur"][0]
        mot = "total" if op == "sum" else "moyenne"
        unite = _unite_de(plan)
        lab = _label_mesure(plan)
        if v is None or pd.isna(v):
            texte = f"Je n'ai aucune valeur valide pour calculer ce résultat{desc}."
        else:
            n_total, n_valides = int(df["n_total"][0]), int(df["n_valides"][0])
            texte = f"{'Le total' if op == 'sum' else 'La moyenne'} de {lab}{desc} est de {_n(float(v))}{unite}"
            texte += f" (sur {_n(n_valides)} {_pluriel(n_valides, 'valeur', 'valeurs') if t in ('fournisseurs', 'production') else _pluriel(n_valides, sing, plur)})." if n_total > 1 else "."
            if t == "production" and op == "sum" and len({f['col'] for f in plan['filtres']} & {"matiere"}) == 0:
                texte += " Attention : ce total additionne des matières d'unités différentes ; précisez une matière pour un chiffre exploitable."
    elif op in ("max", "min"):
        if len(df) == 0:
            texte = f"{_aucun(sing)} ne correspond à la question ({desc.strip()})." if desc else f"{_aucun(sing)} ne correspond."
        else:
            m = plan["mesure"]
            meilleur = df[m].dropna()
            if len(meilleur) == 0:
                texte = f"Aucune valeur valide{desc}."
            else:
                top = meilleur.iloc[0]
                ex = df[df[m] == top]
                lab = _label_mesure(plan)
                est_date = m in ("date_livraison", "date_reception")
                masc = lab in ("délai de livraison", "prix relatif")
                mot = {("max", False): "maximal" if masc else "maximale", ("min", False): "minimal" if masc else "minimale",
                       ("max", True): "la plus tardive", ("min", True): "la plus proche" if m == "date_livraison" else "la plus ancienne"}[(op, est_date)]
                unite = "" if est_date else _unite_de(plan)
                lignes = " ; ".join(_libelle_ligne(plan, r) for _, r in ex.head(5).iterrows())
                egalite = f" ({len(ex)} {plur} à égalité)" if len(ex) > 1 else ""
                texte = (f"{lab[0].upper() + lab[1:]} {mot}{desc} : {_valeur(m, top)}{unite}{egalite}. "
                         f"{'Concernés' if len(ex) > 1 else 'Concerné'} : {lignes}" + (f" (et {len(ex) - 5} autres)" if len(ex) > 5 else "") + ".")
                tableau = ex.head(10)
    elif op == "group":
        if len(df) == 0:
            texte = f"Aucun résultat{desc}."
        else:
            g = plan["groupes"][0]
            agg = plan.get("agg") or "count"
            unite = _unite_de(plan) if agg != "count" else ""
            if plan.get("limite") == 1:
                top = df["valeur"].iloc[0]
                ex = df[df["valeur"] == top]
                noms = _liste_fr([_valeur(g, x) for x in ex["groupe"]])
                quoi = (f"{_n(float(top))} {plur}" if agg == "count" else f"{_n(float(top))}{unite}")
                lab_g = SCHEMA[t]["cols"].get(g, {"label": g})["label"]
                sup = "le plus" if plan.get("tri") != "asc" else "le moins"
                texte = f"{'Les' if len(ex) > 1 else ('La' if lab_g in ('ville', 'matière', 'ligne') else 'Le')} {lab_g}{'s' if len(ex) > 1 else ''} avec {sup} de {'commandes' if agg == 'count' and t == 'commandes' else (plur if agg == 'count' else _label_mesure(plan))}{desc} : {noms} ({quoi}{' chacun' if len(ex) > 1 else ''})."
                tableau = df.head(10)
            else:
                lim = plan.get("limite")
                vue = df.head(lim) if lim else df
                items = ", ".join(f"{_valeur(g, a)} : {_n(float(v))}{unite}" for a, v in zip(vue['groupe'], vue['valeur']))
                lab = f"nombre de {plur}" if agg == "count" else f"{_label_mesure(plan)} ({'total' if agg == 'sum' else 'moyenne' if agg == 'avg' else agg})"
                lab_g = SCHEMA[t]["cols"].get(g, {"label": g})["label"]
                texte = f"{lab[0].upper() + lab[1:]}{desc}, par {lab_g} : {items}."
                tableau = vue.head(30)
    elif op == "compare":
        if len(df) < 2:
            texte = f"Je n'ai pas assez de données pour comparer{desc}."
        else:
            g = plan["groupes"][0]
            morceaux = []
            for _, r in df.iterrows():
                vals = ", ".join(f"{lib} {_n(float(r[a]))}{UNITES_COMPARE[a]}" for _, _, a, lib, _ in COMPARE[t] if pd.notna(r[a]))
                morceaux.append(f"{_valeur(g, r['groupe'])} : {vals}")
            texte = "Comparaison — " + " ; ".join(morceaux) + "."
            verdicts = []
            for _, _, a, lib, sens in COMPARE[t]:
                if sens and df[a].notna().all() and df[a].nunique() > 1:
                    gagnant = df.loc[df[a].idxmin() if sens < 0 else df[a].idxmax(), "groupe"]
                    verdicts.append({"delai": "le plus rapide", "fiabilite": "le plus fiable", "prix": "le moins cher"}[a] + f" : {_valeur(g, gagnant)}")
            if verdicts:
                texte += " " + ", ".join(verdicts)[0].upper() + ", ".join(verdicts)[1:] + "."
            tableau = df
    elif op == "percent":
        if "groupe" in df.columns:
            tot = float(df["valeur"].sum()) or 1
            items = ", ".join(f"{_valeur(plan['groupes'][0], a)} : {100 * float(v) / tot:.1f} %".replace(".", ",") for a, v in zip(df["groupe"], df["valeur"]))
            texte = f"Répartition des {plur}{desc} : {items}."
            tableau = df.head(30)
        else:
            a, b = int(df["valeur"][0]), int(df["total"][0])
            texte = (f"{(100 * a / b if b else 0):.1f} %".replace(".", ",") + f" des {plur} : {_n(a)} {_pluriel(a, sing, plur)} sur {_n(b)}{desc}.")
    elif op == "list" and plan.get("mesure_dite") and 0 < len(df) <= 8 and not plan.get("distinct"):
        m = plan["mesure_dite"]
        lab = SCHEMA[t]["cols"][m]["label"]
        cle = lambda r: {"fournisseurs": f"{r.get('fournisseur')} ({_matiere(r.get('matiere'))})" if "fournisseur" in r else "",
                         "production": f"{r.get('ligne')}, {_matiere(r.get('matiere'))}",
                         "commandes": str(r.get("commande_id")), "stocks": str(r.get("lot_id"))}.get(t, "")
        u = SCHEMA[t]["cols"][m].get("unite")
        suffixe = lambda r: (" " + str(r["unite_cible"]) if t == "stocks" and m == "quantite" and pd.notna(r["quantite"]) else
                             (" " + u if u and u != "%" else (" %" if u == "%" else "")))
        morceaux = [f"{cle(r)} : " + ("invalide ou manquante" if m == "quantite" and t == "stocks" and pd.isna(r["quantite"]) else _valeur(m, r[m]) + suffixe(r)) for _, r in df.iterrows()]
        desc2 = decrire_filtres(plan, sans=("fournisseur", "commande_id", "lot_id") if t != "production" else ())
        texte = f"{lab[0].upper() + lab[1:]}{desc2} : " + " ; ".join(morceaux) + "."
        tableau = df.head(10)
    else:  # list
        if len(df) == 0:
            texte = f"{_aucun(sing)} ne correspond à la question ({desc.strip()})." if desc else f"{_aucun(sing)} ne correspond."
        else:
            tab = df.copy()
            n = len(tab)
            if plan.get("distinct"):
                valeurs = [_valeur(plan["distinct"], x) for x in tab[plan["distinct"]]]
                texte = f"{_n(n)} {_pluriel(n, sing, plur)}{desc} : {_liste_fr(valeurs[:12])}{' …' if n > 12 else ''}."
            else:
                echant = " ; ".join(_libelle_ligne(plan, r) for _, r in tab.head(5).iterrows())
                texte = f"{_n(n)} {_pluriel(n, sing, plur)}{desc}. " + ("Les premiers : " if n > 5 else "") + echant + (" …" if n > 5 else ".")
            tableau = tab.head(30)
    if notes:
        texte += " (" + " ; ".join(notes) + ".)"
    comp = _comprehension(plan)
    expl = ["Question comprise comme : " + comp, "Requête exécutée en lecture seule sur une copie nettoyée des données : " + sql]
    if tableau is not None:
        tableau = tableau.rename(columns=noms_colonnes(plan, list(tableau.columns))).copy()
        for c in list(tableau.columns):
            tableau[c] = [_valeur(next((k for k, v in noms_colonnes(plan, [k for k in SCHEMA[t]["cols"]]).items() if v == c), c), x) if not isinstance(x, str) or True else x
                          for x in tableau[c]]
    return {"texte": texte, "tableau": tableau, "requete": sql, "plan": plan, "tables": tables, "comprehension": comp,
            "explication": expl, "ignores": notes_ign}


def _liste_fr(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " et " + items[-1]


def _comprehension(plan):
    t, op = plan["table"], plan["op"]
    ops = {"count": "compter", "sum": "additionner", "avg": "faire la moyenne de", "max": "trouver le maximum de",
           "min": "trouver le minimum de", "list": "lister", "group": "regrouper", "percent": "calculer la part de",
           "exists": "vérifier l'existence de", "compare": "comparer"}
    cibles = {"count": f"les {SCHEMA[t]['pluriel']}"}
    cible = cibles.get(op) or (SCHEMA[t]["cols"][plan["mesure"]]["label"] if plan.get("mesure") else f"les {SCHEMA[t]['pluriel']}")
    s = f"{ops[op]} {cible} (données « {t} »)"
    if plan["groupes"]:
        s += f", par {plan['groupes'][0]}"
    if plan["filtres"]:
        s += ", filtres :" + decrire_filtres(plan)
    return s


def decrire_schema(data):
    """Reponse a « quelles données as-tu ? » : tables, colonnes, nombre de lignes (jamais de contenu personnel)."""
    parts = []
    for t, d in SCHEMA.items():
        df = data[t]
        cols = [m["label"] for c, m in d["cols"].items() if m["type"] not in ("missing",) and c != "jours_avant_livraison"]
        if t == "clients":
            cols = ["identifiant", "ville", "e-mail et téléphone (seulement présents ou manquants)"]
        parts.append(f"{t} ({len(df)} lignes) : {', '.join(cols)}")
    return ("Voici les données auxquelles j'ai accès : " + " | ".join(parts) +
            ". Je n'ai pas accès aux salariés, ni aux noms, téléphones et e-mails des clients.")


def suggestions(plan, data, question=""):
    """Questions de suite adaptees a la table interrogee (et « Et pour X ? » avec une autre valeur)."""
    t = plan["table"]
    base = {"commandes": ["Quantité commandée par client", "Quelle est la plus grosse commande ?", "Combien de commandes en novembre ?"],
            "stocks": ["Quantité de stock par matière", "Quel est le lot le plus ancien ?", "Combien de lots ont une quantité invalide ?"],
            "fournisseurs": ["Quel fournisseur est le plus rapide ?", "Compare Delta et Sigma", "Fiabilité moyenne des fournisseurs"],
            "clients": ["Répartition des clients par ville", "Combien de clients n'ont pas d'e-mail ?", "Quelle ville a le plus de clients ?"],
            "production": ["Quels produits sont fabriqués sur la ligne 1 ?", "Quelle est la consommation de mangue par jour ?",
                           "Quelle matière va manquer en premier ?"]}[t]
    out = []
    for f in plan["filtres"]:
        if f["op"] == "=" and isinstance(f["val"], str) and f["col"] in ("client", "fournisseur", "ville", "lieu", "ligne", "produit", "matiere"):
            df = data["clients"] if t == "clients" else data[f["table"]]
            deja_la = {g["val"] for g in plan["filtres"] if g["col"] == f["col"]}
            vals = sorted(str(v) for v in df[f["col"]].dropna().unique() if str(v) not in deja_la)
            if vals:
                out.append(f"Et pour {'le ' + vals[0] if f['col'] == 'client' else (vals[0] if f['col'] == 'fournisseur' else ('à ' + vals[0] if f['col'] == 'ville' else _valeur(f['col'], vals[0])))} ?")
            break
    if plan["op"] == "count" and SCHEMA[t]["mesure"]:
        out.append("Et en quantité totale ?")
    elif plan["op"] in ("sum", "group") and not plan["groupes"]:
        out.append("Et la moyenne ?")
    out += [b for b in base if b.lower().rstrip(" ?") != question.lower().rstrip(" ?")]
    return out[:3]
