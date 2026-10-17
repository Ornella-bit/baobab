"""Verifie DataCompass (etape 4A) sur les donnees generees. Usage : python check_quality.py -> « OK ».
Les resultats sont compares a data/_verite_terrain.json (nombre exact de defauts places a la generation)."""
import json

from core import pii, quality
from core.loader import DATA, PARAMS, load_all

verite = json.loads((DATA / "_verite_terrain.json").read_text(encoding="utf-8"))
data = load_all()

avant = quality.all_scores(data)
print("Notes avant :", {f: s for f, s in avant.items()}, "| globale :", quality.global_score(avant))

issues = {f: quality.list_issues(df, f) for f, df in data.items()}
par_type = {f: {} for f in data}
for f, lst in issues.items():
    for i in lst:
        par_type[f][i["type"]] = par_type[f].get(i["type"], 0) + 1
print("Problèmes :", par_type)
sains = {f: round(100 * quality.healthy_rate(df, issues[f]), 1) for f, df in data.items()}
print("Lignes saines (%) :", sains)

# doublons : on doit retrouver ceux qui ont ete places
d_cli = par_type["clients"].get("doublon", 0)
d_emp = par_type["employes"].get("doublon", 0)
assert abs(d_cli - verite["clients"]["doublons"]) <= 15, d_cli
assert d_emp == verite["employes"]["doublons"], d_emp
# valeurs de stock mal saisies
q_stock = [i for i in issues["stocks"] if i["colonne"] == "quantite"]
assert len(q_stock) == verite["stocks"]["valeurs_mal_saisies"], len(q_stock)
# e-mails manquants
assert par_type["clients"].get("manquant", 0) == verite["clients"]["emails_manquants"]
# donnees personnelles
sens = {f: pii.detect_pii(df) for f, df in data.items()}
assert set(sens["employes"].values()) >= {"nom", "salaire", "telephone", "email", "date_naissance"}, sens["employes"]
assert set(sens["clients"].values()) >= {"nom", "telephone", "email"}, sens["clients"]
print("Données personnelles :", pii.count_pii(data), "colonnes,", pii.count_pii_cells(data), "valeurs")

# validation de toutes les corrections proposees (on repete tant qu'il en reste : une correction
# peut en reveler une autre, par exemple une quantite corrigee dont l'unite est aussi a convertir)
corriges = dict(data)
for passage in range(3):
    reste = 0
    for f, df in corriges.items():
        lst = quality.list_issues(df, f)
        for i in lst:
            if i["correction"] is not None:
                i["statut"] = "valide"
                reste += 1
        corriges[f] = quality.apply_corrections(df, lst)
    print(f"Passage {passage + 1} : {reste} corrections appliquées")
    if reste == 0:
        break
assert reste == 0
sains2 = {f: round(100 * quality.healthy_rate(corriges[f], quality.list_issues(corriges[f], f)), 1) for f in data}
print("Lignes saines après (%) :", sains2)
apres = quality.all_scores(corriges)
print("Notes après :", {f: s for f, s in apres.items()}, "| globale :", quality.global_score(apres))
assert quality.global_score(apres) > quality.global_score(avant)
poids = {f: len(df) for f, df in data.items()}
assert sum(sains2[f] * len(corriges[f]) for f in data) / sum(len(corriges[f]) for f in data) > \
    sum(sains[f] * poids[f] for f in data) / sum(poids.values()) + 8   # les lignes saines progressent nettement
assert len(corriges["clients"]) == len(data["clients"]) - d_cli

# les lignes du scenario ne doivent pas etre touchees
st = corriges["stocks"].copy()
st["quantite"] = st["quantite"].map(float)
m = st[(st["matiere"] == PARAMS["scenario"]["matiere"]) & (st["unite"] == "unites")]
assert m[m["lieu"] == "Ligne 2"]["quantite"].sum() == PARAMS["scenario"]["stock_ligne"]
# unites uniformes pour le sucre (sauf les lots dont la quantite reste a ressaisir par un humain)
s = corriges["stocks"]
s = s[(s["matiere"] == "sucre") & s["quantite"].map(lambda v: quality._num(v) is not None and 0 < quality._num(v) <= 50_000)]
assert set(s["unite"]) == {"kg"}, set(s["unite"])
# l'original n'a pas ete modifie
assert len(data["clients"]) == verite["clients"]["lignes"]
print("\nOK : DataCompass retrouve les défauts placés, corrige sans toucher au scénario, et la note monte.")
