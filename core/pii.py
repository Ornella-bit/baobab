"""Detection des donnees personnelles (colonnes sensibles)."""
import re

import pandas as pd

TEL = re.compile(r"^[\s+()\d.-]{8,20}x?$")
MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _vides(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def detect_pii(df):
    """Retourne {colonne: type} avec type dans nom, telephone, email, salaire, date_naissance."""
    trouve = {}
    for col in df.columns:
        nom = str(col).lower()
        valeurs = df[col][~_vides(df[col])].astype(str)
        part = lambda rx: valeurs.str.match(rx).mean() if len(valeurs) else 0
        if "salaire" in nom:
            trouve[col] = "salaire"
        elif "naissance" in nom:
            trouve[col] = "date_naissance"
        elif nom in ("nom", "nom_complet") or nom.startswith("nom_"):
            trouve[col] = "nom"
        elif "mail" in nom or part(MAIL) > 0.6:
            trouve[col] = "email"
        elif "tel" in nom or part(TEL) > 0.6:
            trouve[col] = "telephone"
    return trouve


def count_pii(data):
    """data = {fichier: DataFrame}. Nombre de colonnes sensibles dans l'ensemble des fichiers."""
    return sum(len(detect_pii(df)) for df in data.values())


def count_pii_cells(data):
    """Nombre de valeurs (cases non vides) qui sont des donnees personnelles."""
    total = 0
    for df in data.values():
        for col in detect_pii(df):
            total += int((~_vides(df[col])).sum())
    return total
