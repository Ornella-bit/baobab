"""Import de fichiers CSV / Excel : detecter de quelle table il s'agit, relier les colonnes, controler, puis remplacer.

Rien n'est applique sans controle : le jeu de donnees complet est d'abord essaye (qualite, graphe, simulation, alertes).
S'il fait planter l'analyse, l'import est refuse avec une explication, et les donnees en cours ne sont pas touchees.
Les fichiers de salaries ne sont pas importables (donnees personnelles sensibles).
"""
import csv
import difflib
import io
from pathlib import Path

import pandas as pd

from core import nlu
from core.loader import PARAMS

TAILLE_MAX = 5 * 1024 * 1024
LIGNES_MAX = 50_000
FORMATS = (".csv", ".txt", ".xlsx", ".xls")

# colonnes de chaque table : nom attendu -> (type, synonymes normalises sans accents)
TABLES = {
    "stocks": {"label": "Stocks (lots en entrepôt et sur les lignes)", "colonnes": {
        "lot_id": ("texte", ["lot", "numero lot", "n lot", "id lot", "identifiant", "reference", "ref"]),
        "lieu": ("texte", ["lieu", "entrepot", "emplacement", "site", "localisation", "endroit"]),
        "matiere": ("texte", ["matiere", "matiere premiere", "ingredient", "produit brut", "article"]),
        "quantite": ("texte", ["quantite", "qte", "qt", "volume", "stock", "quantite en stock"]),
        "unite": ("texte", ["unite", "unit", "unite de mesure", "um"]),
        "date_reception": ("texte", ["date reception", "date de reception", "reception", "date", "recu le", "date arrivee"])}},
    "fournisseurs": {"label": "Fournisseurs (délai, fiabilité, prix)", "colonnes": {
        "fournisseur": ("texte", ["fournisseur", "nom fournisseur", "supplier", "societe"]),
        "matiere": ("texte", ["matiere", "matiere fournie", "ingredient", "produit", "article"]),
        "delai_moyen_jours": ("nombre", ["delai", "delai moyen", "delai jours", "delai de livraison", "lead time", "delai moyen jours"]),
        "fiabilite_pct": ("nombre", ["fiabilite", "fiabilite pct", "fiabilite %", "taux de fiabilite", "reliability"]),
        "prix_relatif": ("nombre", ["prix", "prix relatif", "cout", "tarif", "indice prix"])}},
    "production": {"label": "Production (lignes, produits, consommation)", "colonnes": {
        "ligne": ("texte", ["ligne", "ligne de production", "atelier", "line"]),
        "produit": ("texte", ["produit", "produit fini", "article", "product"]),
        "matiere": ("texte", ["matiere", "matiere premiere", "ingredient", "intrant"]),
        "conso_par_jour": ("nombre", ["conso", "consommation", "conso par jour", "consommation par jour", "consommation journaliere", "conso jour"])}},
    "commandes": {"label": "Commandes clients", "colonnes": {
        "commande_id": ("texte", ["commande", "numero commande", "n commande", "id commande", "cmd", "reference", "identifiant"]),
        "client": ("texte", ["client", "nom client", "customer"]),
        "produit": ("texte", ["produit", "article", "product"]),
        "quantite": ("nombre", ["quantite", "qte", "qt", "volume", "quantite commandee"]),
        "date_livraison": ("texte", ["date livraison", "date de livraison", "livraison", "echeance", "date", "livre le", "delivery"])}},
    "clients": {"label": "Clients (identifiant, ville, contacts)", "colonnes": {
        "client_id": ("texte", ["id client", "identifiant client", "client id", "identifiant", "numero client", "id", "code client"]),
        "nom_complet": ("texte", ["nom complet", "nom", "nom et prenom", "client", "name"]),
        "ville": ("texte", ["ville", "localite", "commune", "city"]),
        "telephone": ("texte", ["telephone", "tel", "portable", "mobile", "numero de telephone", "phone"]),
        "email": ("texte", ["email", "e mail", "mail", "courriel", "adresse mail", "adresse email"])}},
}
EXEMPLES = {
    "stocks": [["L9001", "Entrepot Nord", "sucre", "1200", "kg", "2026-10-20"], ["L9002", "Ligne 1", "concentre_orange", "5300", "unites", "2026-10-25"]],
    "fournisseurs": [["Omega", "sucre", 5, 91, 1.02], ["Omega", "bouteilles", 7, 88, 0.98]],
    "production": [["Ligne 1", "Jus d'orange 1 L", "concentre_orange", 900], ["Ligne 1", "Jus d'orange 1 L", "sucre", 300]],
    "commandes": [["CMD101", "Client A", "Jus d'orange 1 L", 1800, "2026-11-05"], ["CMD102", "Client B", "Nectar de mangue 1 L", 2400, "2026-11-07"]],
    "clients": [["C90001", "Prénom Nom", "Abidjan", "+225 07 00 00 00 00", "exemple@exemple.com"]],
}
UNITES = {"kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramme": "kg", "kilogrammes": "kg", "tonnes": "tonnes", "tonne": "tonnes", "t": "tonnes",
          "unites": "unites", "unite": "unites", "u": "unites", "pieces": "unites", "bouteilles": "unites", "cartons": "cartons", "carton": "cartons"}


class ErreurImport(Exception):
    """Probleme de fichier explique en francais a l'utilisateur."""


# ------------------------------------------------------------------ lecture
def lire_fichier(contenu, nom):
    """Octets + nom de fichier -> DataFrame de texte (aucune interpretation de type a ce stade)."""
    ext = Path(nom).suffix.lower()
    if ext not in FORMATS:
        raise ErreurImport(f"Format « {ext or 'inconnu'} » non pris en charge. Utilisez un fichier .csv ou .xlsx.")
    if len(contenu) > TAILLE_MAX:
        raise ErreurImport(f"Fichier trop gros ({len(contenu) // 1024 // 1024} Mo) : la limite de la démo est {TAILLE_MAX // 1024 // 1024} Mo.")
    if not contenu.strip():
        raise ErreurImport("Le fichier est vide.")
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(contenu), dtype=str)
        else:
            texte = None
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    texte = contenu.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            try:
                sep = csv.Sniffer().sniff(texte[:4096], delimiters=",;\t|").delimiter
            except csv.Error:
                sep = ";" if texte.count(";") > texte.count(",") else ","
            df = pd.read_csv(io.StringIO(texte), sep=sep, dtype=str, keep_default_na=False, na_values=[""])
    except ErreurImport:
        raise
    except Exception as e:  # fichier illisible ou corrompu
        raise ErreurImport(f"Impossible de lire le fichier ({type(e).__name__}). Vérifiez qu'il s'agit bien d'un CSV ou d'un classeur Excel.") from e
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 2:
        raise ErreurImport("Aucune ligne exploitable : le fichier doit contenir une ligne d'en-têtes puis des données.")
    if len(df) > LIGNES_MAX:
        raise ErreurImport(f"Trop de lignes ({len(df)}) : la limite de la démo est {LIGNES_MAX}.")
    return df.reset_index(drop=True)


# ------------------------------------------------------------------ detection
def _nom(c):
    return nlu.normaliser(str(c).replace("_", " "))


def _score_colonne(col_fichier, cible, synonymes):
    a = _nom(col_fichier)
    cands = [_nom(cible)] + synonymes
    if a in cands:
        return 1.0
    return max(difflib.SequenceMatcher(None, a, c).ratio() for c in cands)


def relier_colonnes(df, table):
    """Meilleure correspondance {colonne attendue: colonne du fichier ou None}, sans reutiliser une colonne deux fois."""
    attendues = TABLES[table]["colonnes"]
    paires = []
    for cible, (_, syn) in attendues.items():
        for c in df.columns:
            s = _score_colonne(c, cible, syn)
            if s >= 0.78:
                paires.append((s, cible, c))
    paires.sort(key=lambda p: -p[0])
    lien, pris = {c: None for c in attendues}, set()
    for s, cible, c in paires:
        if lien[cible] is None and c not in pris:
            lien[cible] = c
            pris.add(c)
    return lien


def detecter_table(df):
    """Retourne [(table, part des colonnes retrouvees)] du plus probable au moins probable."""
    res = []
    for t in TABLES:
        lien = relier_colonnes(df, t)
        res.append((t, sum(v is not None for v in lien.values()) / len(lien)))
    return sorted(res, key=lambda r: -r[1])


def refus_confidentialite(df):
    """Message si le fichier ressemble a des donnees de salaries (non importables), sinon None."""
    noms = {_nom(c) for c in df.columns}
    if noms & {"salaire", "salaire fcfa", "remuneration", "date naissance", "date de naissance", "salaire brut", "salaire net", "paie"}:
        return "Ce fichier contient des salaires ou des dates de naissance : les données de salariés ne sont pas importables dans la démo."
    return None


# ------------------------------------------------------------------ preparation
def _canon_matiere(v):
    if pd.isna(v):
        return v
    s = nlu.normaliser(str(v)).replace(" ", "_")
    for m in PARAMS["unite_cible"]:
        if s == m or s == m.replace("concentre_", "") or s.rstrip("s") == m.rstrip("s"):
            return m
    return str(v).strip()


def preparer(df, table, lien):
    """Construit le DataFrame au format attendu. Retourne (DataFrame, rapport)."""
    attendues = TABLES[table]["colonnes"]
    manquantes = [c for c in attendues if not lien.get(c)]
    rapport = {"lignes": len(df), "manquantes": manquantes, "ignorees": [c for c in df.columns if c not in set(lien.values())],
               "illisibles": {}, "inconnues": {}, "avertissements": []}
    if manquantes:
        return None, rapport
    out = pd.DataFrame({cible: df[lien[cible]].astype("string").str.strip() for cible in attendues})
    for cible, (typ, _) in attendues.items():
        if typ == "nombre":
            brut = out[cible].str.replace(",", ".", regex=False).str.replace(r"\s", "", regex=True)
            nb = pd.to_numeric(brut, errors="coerce")
            rapport["illisibles"][cible] = int((nb.isna() & out[cible].notna()).sum())
            out[cible] = nb
    if "matiere" in out.columns:
        out["matiere"] = out["matiere"].map(_canon_matiere)
        inconnues = sorted({str(m) for m in out["matiere"].dropna() if m not in PARAMS["unite_cible"]})
        if inconnues:
            rapport["inconnues"]["matiere"] = inconnues
    if table == "stocks":
        out["unite"] = out["unite"].map(lambda u: UNITES.get(nlu.normaliser(str(u)), str(u).strip()) if pd.notna(u) else u)
    for c in out.columns:
        if str(out[c].dtype) == "string":
            out[c] = out[c].astype(object).where(out[c].notna(), None)
    for c, n in rapport["illisibles"].items():
        if n:
            rapport["avertissements"].append(f"{n} valeur(s) de « {c} » ne sont pas des nombres : elles seront signalées comme problèmes de qualité.")
    if rapport["inconnues"]:
        rapport["avertissements"].append("Matières inconnues de la démo : " + ", ".join(rapport["inconnues"]["matiere"]) +
                                         ". Attendues : " + ", ".join(PARAMS["unite_cible"]) + ".")
    return out, rapport


def tester_jeu(data):
    """Essaie tout le programme sur le jeu de donnees. Retourne None si tout passe, sinon un message d'erreur lisible."""
    from core import alerts, askdata, quality
    from core.graph import build_graph
    from core.simulate import list_options, simulate_supplier_delay
    try:
        scores = quality.all_scores(data)
        issues = {f: quality.list_issues(df, f) for f, df in data.items()}
        build_graph(data)
        for f in data["fournisseurs"]["fournisseur"].dropna().unique():
            list_options(data, simulate_supplier_delay(data, f, PARAMS["scenario"]["retard_jours"]))
        alerts.compute_alerts(data, scores, issues)
        askdata.construire_base(data)
    except KeyError as e:
        return f"Les fichiers ne s'accordent pas entre eux : « {e.args[0]} » est introuvable (matière, ligne ou produit absent d'un des fichiers)."
    except (IndexError, ValueError, TypeError) as e:
        return ("Les fichiers ne s'accordent pas entre eux (par exemple une ligne de production sans stock, ou une date illisible). "
                f"Détail technique : {type(e).__name__}.")
    except Exception as e:
        return f"L'analyse a échoué avec ce fichier ({type(e).__name__}). Les données en cours n'ont pas été modifiées."
    return None


def appliquer(data, table, nouveau, mode="remplacer"):
    """mode : « remplacer » (le fichier devient la table) ou « ajouter » (ses lignes s'ajoutent a la table).
    Retourne (nouveau jeu de donnees, message d'erreur ou None). Ne modifie pas `data`."""
    candidat = {k: v.copy() for k, v in data.items()}
    if mode == "ajouter":
        candidat[table] = pd.concat([data[table], nouveau], ignore_index=True)
    else:
        candidat[table] = nouveau.reset_index(drop=True)
    return candidat, tester_jeu(candidat)


# ------------------------------------------------------------------ modeles et exemples
def modele_csv(table):
    cols = list(TABLES[table]["colonnes"])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    w.writerows(EXEMPLES[table])
    return buf.getvalue().encode("utf-8-sig")


def fichier_exemple_stocks():
    """Un fichier volontairement « sale » (en-têtes libres, ponctuation, unités variées) pour montrer la détection."""
    lignes = [["N° lot", "Entrepôt", "Matière première", "Qté", "Unité", "Date de réception"]]
    base = [("Entrepot Nord", "Sucre", "1 250", "kg", "2026-10-21"), ("Entrepot Nord", "Sucre", "2,4", "tonnes", "2026-10-23"),
            ("Ligne 1", "concentré orange", "5300", "unités", "2026-10-25"), ("Ligne 2", "Concentré mangue", "4800", "unités", "2026-10-28"),
            ("Entrepot Sud", "bouteilles", "40", "cartons", "2026-10-27"), ("Ligne 1", "Sucre", "", "kg", "2026-10-26"),
            ("Ligne 2", "Bouteilles", "29000", "unités", "2026-10-29"), ("Ligne 1", "Bouteilles", "32 000", "unités", "2026-10-30")]
    for i, (lieu, mat, q, u, d) in enumerate(base, 1):
        lignes.append([f"L{8000 + i}", lieu, mat, q, u, d])
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", lineterminator="\n").writerows(lignes)
    return buf.getvalue().encode("utf-8-sig"), "stocks_export_erp.csv"
