"""Verifie le contrat de l'etape 3 : formules, droits, et presence des fonctions annoncees.
Usage : python check_specs.py   -> doit finir par « OK ».
Les fonctions « A FAIRE » ne sont pas appelees ici : on verifie seulement qu'elles existent.
"""
import importlib
import tempfile
from pathlib import Path

import pandas as pd

from core import rbac, trust

# 1) formule de la note de qualite
assert trust.score_from_parts(1, 1, 1, 1) == 100
assert trust.score_from_parts(0.9, 0.8, 1, 0.5) == 81.0   # 100*(0.27+0.24+0.20+0.10)

# 2) score de confiance : plafonne par la source la plus faible + 15
t = trust.trust_score(["stocks", "production", "fournisseurs"], {"stocks": 55, "production": 90, "fournisseurs": 88})
assert t["score"] == 70 and t["couleur"] == "orange" and t["plus_faible"] == "stocks", t
t = trust.trust_score(["production", "fournisseurs"], {"production": 90, "fournisseurs": 88})
assert t["score"] == 89 and t["couleur"] == "vert", t
t = trust.trust_score(["clients"], {"clients": 40})
assert t["couleur"] == "rouge" and t["a_confirmer"], t

# 3) droits par role et masquage
df = pd.DataFrame({"nom": ["A B"], "poste": ["x"], "salaire_fcfa": [500000], "telephone": ["0102"],
                   "email": ["a@b.c"], "date_naissance": ["01/01/1990"]})
assert rbac.can_validate("Directeur général") and not rbac.can_validate("Stagiaire logistique")
assert rbac.apply_role(df, "employes", "Directeur général").equals(df)
m = rbac.apply_role(df, "employes", "Stagiaire logistique")
assert (m["salaire_fcfa"] == rbac.MASQUE).all() and m["poste"].iloc[0] == "x"
assert df["salaire_fcfa"].iloc[0] == 500000          # l'original n'est pas modifie

# 4) journal des actions
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "audit.csv"
    rbac.log_action("Directeur général", "valider_correction", "clients lignes 12-13", path=p)
    rbac.log_action("Stagiaire logistique", "question", "retard Delta", path=p)
    log = rbac.read_log(p)
    assert len(log) == 2 and list(log.columns) == ["horodatage", "role", "action", "detail"]

# 5) les fonctions du contrat existent
CONTRAT = {
    "core.quality": ["classify_columns", "measures", "quality_score", "find_duplicates", "list_issues", "apply_corrections"],
    "core.pii": ["detect_pii", "count_pii"],
    "core.graph": ["build_graph", "downstream"],
    "core.simulate": ["stock_coverage", "simulate_supplier_delay", "list_options"],
    "core.copilot": ["get_stock_coverage", "get_passport", "ask"],
    "core.trust": ["score_from_parts", "trust_score"],
    "core.rbac": ["can_validate", "apply_role", "log_action", "read_log"],
}
for module, fonctions in CONTRAT.items():
    mod = importlib.import_module(module)
    for f in fonctions:
        assert callable(getattr(mod, f, None)), f"{module}.{f} manque"

print("OK : formules, droits, journal et contrat de fonctions conformes à SPECS.md.")
