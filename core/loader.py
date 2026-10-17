"""Chargement des fichiers de data/ (utilise par l'application et par les scripts de verification)."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PARAMS = json.loads((ROOT / "config" / "params.json").read_text(encoding="utf-8"))


def load_all():
    """Retourne un dictionnaire {nom: DataFrame}. Les contrats PDF sont listes a part (voir list_contracts)."""
    return {
        "employes": pd.read_excel(DATA / "employes.xlsx"),
        "clients": pd.read_csv(DATA / "clients.csv"),
        "stocks": pd.read_csv(DATA / "stocks.csv"),
        "fournisseurs": pd.read_csv(DATA / "fournisseurs.csv"),
        "production": pd.read_csv(DATA / "production.csv"),
        "commandes": pd.read_csv(DATA / "commandes.csv"),
    }


def list_contracts():
    return sorted((DATA / "contrats").glob("*.pdf"))


def data_ready():
    return (DATA / "clients.csv").exists()
