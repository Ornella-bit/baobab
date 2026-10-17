"""Droits par role, masquage des donnees sensibles et journal des actions (implemente)."""
import csv
from datetime import datetime
from pathlib import Path

ROLES = ["Directeur général", "Stagiaire logistique"]
MASQUE = "●●●●"
COLONNES_MASQUEES = {
    "Stagiaire logistique": {
        "employes": ["nom", "salaire_fcfa", "telephone", "email", "date_naissance"],
        "clients": ["nom_complet", "telephone", "email"],
    },
}
JOURNAL = Path(__file__).resolve().parent.parent / "cache" / "audit.csv"


def can_validate(role):
    """Seul le directeur general peut valider une correction."""
    return role == "Directeur général"


def apply_role(df, fichier, role):
    """Retourne une copie de df dont les colonnes sensibles sont masquees pour ce role."""
    out = df.copy()
    for col in COLONNES_MASQUEES.get(role, {}).get(fichier, []):
        if col in out.columns:
            out[col] = MASQUE
    return out


def log_action(role, action, detail="", path=None):
    """Ajoute une ligne au journal : horodatage, role, action, detail."""
    path = Path(path) if path else JOURNAL
    path.parent.mkdir(parents=True, exist_ok=True)
    neuf = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if neuf:
            w.writerow(["horodatage", "role", "action", "detail"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), role, action, detail])


def read_log(path=None):
    import pandas as pd
    path = Path(path) if path else JOURNAL
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["horodatage", "role", "action", "detail"])
