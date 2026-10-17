"""DataCompass : note de qualite, doublons, problemes et corrections.

Un « probleme » (issue) est un dictionnaire :
  {"id", "fichier", "type": "doublon|format|valeur_aberrante|manquant|unite", "ligne": etiquette de l'index,
   "colonne", "valeur", "correction": valeur | dict {colonne: valeur} | None, "note", "statut": "a_valider|valide|refuse"}
- correction None : aucun correctif automatique possible, un humain doit traiter (ex. e-mail manquant).
- doublon : la correction consiste a supprimer la ligne (on garde la ligne la plus complete du groupe).
"""
import re
import unicodedata
from collections import defaultdict

import pandas as pd

from core.loader import PARAMS
from core.trust import score_from_parts

try:
    from rapidfuzz import fuzz

    def _ratio(a, b):
        return fuzz.token_sort_ratio(a, b)
except ImportError:  # repli (tests sans rapidfuzz)
    from difflib import SequenceMatcher

    def _ratio(a, b):
        return 100 * SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()

COLONNE_NOM = {"clients": "nom_complet", "employes": "nom"}
COLONNE_ID = {"clients": "client_id", "employes": "id", "stocks": "lot_id", "commandes": "commande_id"}
TEL_STANDARD = re.compile(r"^\+225 \d{2} \d{2} \d{2} \d{2} \d{2}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALEURS_VIDES = {"", "nan", "none", "n/a", "na"}


# ------------------------------------------------------------------ utilitaires
def _vide(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip().lower() in VALEURS_VIDES


def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def _norm_nom(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", _sans_accent(s).lower().replace("'", "")).split())


def _meme_personne(a, b, seuil):
    na, nb = _norm_nom(a), _norm_nom(b)
    if _ratio(na, nb) >= seuil:
        return True
    ta, tb = na.split(), nb.split()
    for t in list(ta):
        if t in tb:
            ta.remove(t)
            tb.remove(t)
    if len(ta) == 1 and len(tb) == 1:  # « J. Kouassi » = « Jean Kouassi »
        x, y = sorted((ta[0], tb[0]), key=len)
        return len(x) == 1 and y.startswith(x)
    return False


def _chiffres_tel(v):
    c = re.sub(r"\D", "", str(v))
    return c[3:] if c.startswith("225") and len(c) == 13 else c


def _tel_valide(v):
    return len(_chiffres_tel(v)) == 10


def _tel_standard(v):
    c = _chiffres_tel(v)
    return f"+225 {c[0:2]} {c[2:4]} {c[4:6]} {c[6:8]} {c[8:10]}"


def _signature(v):
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", str(v)))


def _num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


def _date_iso(v):
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}"
    m = re.match(r"^(\d{2})-(\d{2})-(\d{2})$", s)
    if m:
        annee = 2000 + int(m[3])
        annee = annee - 100 if annee > 2026 else annee
        return f"{annee}-{m[2]}-{m[1]}"
    return None


def _colonnes_donnees(df, fichier):
    ident = COLONNE_ID.get(fichier)
    return [c for c in df.columns if c != ident and not str(c).endswith("_id")]


# ------------------------------------------------------------------ colonnes
def classify_columns(df):
    """Retourne {colonne: categorie} : identite, contact, argent, date, produit, quantite ou autre."""
    out = {}
    for c in df.columns:
        n = str(c).lower()
        if n.startswith("nom") or n in ("client", "fournisseur"):
            out[c] = "identite"
        elif "tel" in n or "mail" in n:
            out[c] = "contact"
        elif "salaire" in n or "prix" in n:
            out[c] = "argent"
        elif "date" in n:
            out[c] = "date"
        elif n in ("matiere", "produit", "ligne", "lieu", "poste", "ville"):
            out[c] = "produit"
        elif n in ("quantite", "conso_par_jour", "delai_moyen_jours", "fiabilite_pct"):
            out[c] = "quantite"
        else:
            out[c] = "autre"
    return out


# ------------------------------------------------------------------ doublons
def _groupes(df, colonne, seuil):
    """Groupes de lignes (etiquettes) qui sont la meme personne : meme telephone ET nom proche."""
    if colonne not in df.columns or "telephone" not in df.columns:
        return [], []
    blocs = defaultdict(list)
    for label, tel in df["telephone"].items():
        cle = _chiffres_tel(tel)[-8:]
        if len(cle) == 8 and not _vide(tel):
            blocs[cle].append(label)
    parents = {}

    def trouve(x):
        while parents.get(x, x) != x:
            parents[x] = parents.get(parents[x], parents[x])
            x = parents[x]
        return x

    paires = []
    for labels in blocs.values():
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = labels[i], labels[j]
                if _meme_personne(df.at[a, colonne], df.at[b, colonne], seuil):
                    paires.append((a, b, round(_ratio(_norm_nom(df.at[a, colonne]), _norm_nom(df.at[b, colonne])), 1)))
                    parents[trouve(b)] = trouve(a)
    groupes = defaultdict(list)
    for a, b, _ in paires:
        for x in (a, b):
            if x not in groupes[trouve(x)]:
                groupes[trouve(x)].append(x)
    return list(groupes.values()), paires


def find_duplicates(df, colonne, seuil=90):
    """Quasi-doublons : meme telephone et noms proches (rapidfuzz token_sort_ratio >= seuil, initiales
    acceptees). Retourne un DataFrame [ligne_a, ligne_b, similarite]."""
    _, paires = _groupes(df, colonne, seuil)
    return pd.DataFrame(paires, columns=["ligne_a", "ligne_b", "similarite"])


def _lignes_en_trop(df, fichier):
    """Pour chaque groupe de doublons, on garde la ligne la plus complete ; les autres sont « en trop »."""
    colonne = COLONNE_NOM.get(fichier)
    if not colonne:
        return {}
    en_trop = {}
    for groupe in _groupes(df, colonne, 90)[0]:
        completes = {x: sum(not _vide(v) for v in df.loc[x]) for x in groupe}
        garde = max(groupe, key=lambda x: (completes[x], -list(df.index).index(x)))
        for x in groupe:
            if x != garde:
                en_trop[x] = garde
    return en_trop


# ------------------------------------------------------------------ mesures et note
def measures(df, fichier):
    """Retourne {completude, unicite, validite, coherence}, chacune entre 0 et 1."""
    cols = _colonnes_donnees(df, fichier)
    n = max(len(df), 1)
    cases = df[cols]
    completude = 1 - sum(cases[c].map(_vide).sum() for c in cols) / max(n * len(cols), 1)

    if COLONNE_NOM.get(fichier):
        unicite = 1 - len(_lignes_en_trop(df, fichier)) / n
    else:
        ident = COLONNE_ID.get(fichier)
        unicite = 1 - (df[ident].duplicated().sum() / n if ident else 0)

    ok = total = 0
    for c in cols:
        serie = df[c][~df[c].map(_vide)]
        n_c = c.lower()
        if "tel" in n_c:
            ok += serie.map(_tel_valide).sum(); total += len(serie)
        elif "mail" in n_c:
            ok += serie.astype(str).map(lambda v: bool(EMAIL.match(v))).sum(); total += len(serie)
        elif n_c in ("quantite",) and fichier == "stocks":
            # les cases vides comptent aussi comme invalides ici (saisie manquante)
            vals = df[c].map(lambda v: _num(v) if not _vide(v) else None)
            ok += vals.map(lambda x: x is not None and 0 < x <= 50_000).sum(); total += len(df)
        elif "salaire" in n_c:
            ok += serie.map(lambda v: (_num(v) or 0) > 0 and (_num(v) or 0) < 10_000_000).sum(); total += len(serie)
        elif "date" in n_c:
            ok += serie.map(lambda v: _date_iso(v) is not None).sum(); total += len(serie)
        elif n_c in ("quantite", "conso_par_jour", "delai_moyen_jours"):
            ok += serie.map(lambda v: (_num(v) or 0) > 0).sum(); total += len(serie)
        elif n_c == "fiabilite_pct":
            ok += serie.map(lambda v: 0 <= (_num(v) or -1) <= 100).sum(); total += len(serie)
    validite = ok / total if total else 1.0

    ok = total = 0
    for c in cols:
        serie = df[c][~df[c].map(_vide)]
        n_c = c.lower()
        if "tel" in n_c:
            ok += serie.map(lambda v: bool(TEL_STANDARD.match(str(v)))).sum(); total += len(serie)
        elif "date" in n_c:
            ok += serie.map(lambda v: bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)))).sum(); total += len(serie)
    if "unite" in df.columns and "matiere" in df.columns:
        cible = PARAMS["unite_cible"]
        ok += sum(u == cible.get(m) for m, u in zip(df["matiere"], df["unite"])); total += len(df)
    coherence = ok / total if total else 1.0
    return {"completude": float(completude), "unicite": float(unicite), "validite": float(validite),
            "coherence": float(coherence)}


def quality_score(df, fichier):
    m = measures(df, fichier)
    return score_from_parts(m["completude"], m["unicite"], m["validite"], m["coherence"])


def all_scores(data):
    """{fichier: note} pour tous les DataFrames."""
    return {f: quality_score(df, f) for f, df in data.items()}


def global_score(scores):
    return round(sum(scores.values()) / len(scores), 1)


# ------------------------------------------------------------------ problemes
def list_issues(df, fichier):
    """Liste des problemes detectes (format en tete du fichier)."""
    issues = []

    def ajoute(type_, ligne, colonne, valeur, correction=None, note=""):
        issues.append({"id": f"{fichier[:3]}-{len(issues)+1:05d}", "fichier": fichier, "type": type_,
                       "ligne": ligne, "colonne": colonne, "valeur": valeur, "correction": correction,
                       "note": note, "statut": "a_valider"})

    nom_col = COLONNE_NOM.get(fichier)
    for label, garde in _lignes_en_trop(df, fichier).items():
        ajoute("doublon", label, nom_col, df.at[label, nom_col], "supprimer la ligne",
               f"doublon de la ligne {garde} ({df.at[garde, nom_col]})")

    for c in _colonnes_donnees(df, fichier):
        n_c = c.lower()
        for label, v in df[c].items():
            if "tel" in n_c and not _vide(v) and not TEL_STANDARD.match(str(v)):
                if _tel_valide(v):
                    ajoute("format", label, c, v, _tel_standard(v), "format de téléphone normalisé")
                else:
                    ajoute("valeur_aberrante", label, c, v, None, "numéro incomplet : à confirmer avec la personne")
            elif "mail" in n_c and _vide(v):
                ajoute("manquant", label, c, "", None, "e-mail à demander")
            elif "mail" in n_c and not EMAIL.match(str(v)):
                ajoute("valeur_aberrante", label, c, v, None, "e-mail invalide")
            elif "date" in n_c and not _vide(v) and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)):
                iso = _date_iso(v)
                ajoute("format", label, c, v, iso, "date au format AAAA-MM-JJ") if iso else \
                    ajoute("valeur_aberrante", label, c, v, None, "date illisible")

    if fichier == "stocks":
        conv = PARAMS["conversions"]
        for label, row in df.iterrows():
            q = _num(row["quantite"]) if not _vide(row["quantite"]) else None
            if _vide(row["quantite"]):
                ajoute("manquant", label, "quantite", row["quantite"], None, "quantité à ressaisir")
                continue
            if q is None:
                corr = _num(str(row["quantite"]).upper().replace("O", "0"))
                ajoute("valeur_aberrante", label, "quantite", row["quantite"], corr, "lettre O prise pour un zéro")
                continue
            if q <= 0 or q > 50_000:
                ajoute("valeur_aberrante", label, "quantite", row["quantite"], abs(q) if q < 0 else None,
                       "signe inversé ?" if q < 0 else "valeur invraisemblable : à vérifier")
                continue
            cible = PARAMS["unite_cible"].get(row["matiere"])
            if cible and row["unite"] != cible:
                if row["unite"] == "tonnes" and cible == "kg":
                    f = conv["tonnes_vers_kg"]; note = "1 tonne = 1000 kg"
                elif row["unite"] == "cartons" and cible == "unites":
                    f = conv["bouteilles_par_carton"]
                    note = f"hypothèse : {f} bouteilles par carton (config/params.json)"
                else:
                    continue
                ajoute("unite", label, "unite", row["unite"], {"quantite": round(q * f, 1), "unite": cible}, note)
    return issues


def healthy_rate(df, issues):
    """Part des lignes sans aucun probleme (entre 0 et 1). Pour un doublon, seule la ligne en trop compte."""
    if len(df) == 0:
        return 1.0
    return 1 - len({i["ligne"] for i in issues}) / len(df)


def apply_corrections(df, issues):
    """Nouveau DataFrame ou seuls les problemes au statut « valide » sont appliques."""
    out = df.copy()
    for i in issues:  # les colonnes modifiees peuvent recevoir des nombres ou du texte
        if i["statut"] == "valide" and i["type"] != "doublon" and i["correction"] is not None:
            for col in (i["correction"] if isinstance(i["correction"], dict) else [i["colonne"]]):
                if col in out.columns and out[col].dtype != object:
                    out[col] = out[col].astype(object)
    a_supprimer = [i["ligne"] for i in issues if i["statut"] == "valide" and i["type"] == "doublon"]
    for i in issues:
        if i["statut"] != "valide" or i["type"] == "doublon" or i["correction"] is None or i["ligne"] not in out.index:
            continue
        if isinstance(i["correction"], dict):
            for col, val in i["correction"].items():
                out.at[i["ligne"], col] = val
        else:
            out.at[i["ligne"], i["colonne"]] = i["correction"]
    return out.drop(index=[x for x in a_supprimer if x in out.index])
