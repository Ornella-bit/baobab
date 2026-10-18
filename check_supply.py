"""Verifie SupplyMind (etape 4B). Usage : python check_supply.py -> « OK »."""
from core import quality
from core.graph import build_graph, downstream
from core.loader import PARAMS, load_all
from core.simulate import list_options, simulate_supplier_delay, stock_coverage

data = load_all()

# couverture
c = stock_coverage(data, "Ligne 2", "concentre_mangue")
assert (c["stock"], c["conso_par_jour"], c["jours"]) == (4800, 1200, 4.0), c

# scenario Delta : retard de 5 jours
sim = simulate_supplier_delay(data, "Delta", 5)
assert sim["arret_jour"] == 4 and sim["manque"] == 1200, sim
assert sim["ligne"] == "Ligne 2" and sim["matiere"] == "concentre_mangue"
assert sim["commandes"] == ["CMD004", "CMD005", "CMD007"], sim["commandes"]
assert sim["clients"] == ["Client B", "Client C"]
assert {d["ligne"] for d in sim["details"]} == {"Ligne 1", "Ligne 2"}   # Delta fournit aussi le concentre d'orange
print(f"Delta +5 j : arret J+{sim['arret_jour']}, manque {sim['manque']}, commandes {sim['commandes']}, clients {sim['clients']}")

# les trois options
o = {x["code"]: x for x in list_options(data, sim)}
assert (o["A"]["faisable"], o["A"]["surcout_pct"], o["A"]["risque"]) == (True, 0.0, "moyen"), o["A"]
assert (o["B"]["faisable"], o["B"]["surcout_pct"], o["B"]["risque"]) == (True, 6.0, "faible"), o["B"]
assert (o["C"]["faisable"], o["C"]["surcout_pct"], o["C"]["risque"]) == (True, 2.0, "eleve"), o["C"]
for x in o.values():
    print(f"  option {x['code']} : {x['libelle']} | +{x['surcout_pct']} % | risque {x['risque']}")

# retard court : aucun arret, aucune option
court = simulate_supplier_delay(data, "Delta", 3)
assert court["arret_jour"] is None and court["manque"] == 0 and court["commandes"] == [] and list_options(data, court) == []

# retard plus long : plus de lignes et de commandes touchees
long_ = simulate_supplier_delay(data, "Delta", 10)
assert long_["manque"] > sim["manque"] and len(long_["commandes"]) >= len(sim["commandes"])
assert {d["ligne"] for d in long_["details"] if d["arret_jour"] is not None} == {"Ligne 1", "Ligne 2"}

# un fournisseur qui n'alimente pas la ligne en retard
assert simulate_supplier_delay(data, "Sigma", 2)["arret_jour"] is None

# graphe
g = build_graph(data)
aval = dict(downstream(g, "Delta"))
assert aval["Ligne 2"] == "ligne" and aval["CMD004"] == "commande" and aval["Client B"] == "client", aval
assert "Alpha" not in aval and "Sigma" not in aval
print(f"Graphe : {g.number_of_nodes()} noeuds, {g.number_of_edges()} liens ; en aval de Delta : {len(aval)} noeuds")

# memes resultats apres correction des donnees (les lignes du scenario ne sont pas touchees)
corriges = dict(data)
for _ in range(3):
    for f, df in corriges.items():
        lst = quality.list_issues(df, f)
        for i in lst:
            if i["correction"] is not None:
                i["statut"] = "valide"
        corriges[f] = quality.apply_corrections(df, lst)
apres = simulate_supplier_delay(corriges, "Delta", PARAMS["scenario"]["retard_jours"])
assert (apres["arret_jour"], apres["manque"], apres["commandes"]) == (4, 1200, ["CMD004", "CMD005", "CMD007"])
print("\nOK : SupplyMind reproduit le scénario Delta (arrêt J+4, manque 1 200, 3 commandes, 3 options).")
