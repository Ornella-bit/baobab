"""Verifie que les donnees fictives donnent bien le scenario de demo Delta :
arret de la Ligne 2 a J+4, manque de 1 200 unites, commandes B et C menacees.
Usage : python check_scenario.py   (apres python generate_data.py)
"""
from datetime import date, timedelta

import pandas as pd

from core.loader import PARAMS, load_all

sc = PARAMS["scenario"]
J0 = date.fromisoformat(PARAMS["date_reference"])
d = load_all()

stocks = d["stocks"].copy()
stocks["quantite"] = pd.to_numeric(stocks["quantite"], errors="coerce")
mat = stocks[(stocks["matiere"] == sc["matiere"]) & (stocks["unite"] == "unites")]
stock_ligne = mat[mat["lieu"] == sc["ligne"]]["quantite"].sum()
stock_nord = mat[mat["lieu"] == "Entrepot Nord"]["quantite"].sum()

prod = d["production"]
conso = prod[(prod["ligne"] == sc["ligne"]) & (prod["matiere"] == sc["matiere"])]["conso_par_jour"].iloc[0]

couverture = stock_ligne / conso                      # jours de stock restant
arret_jour = int(couverture) if sc["retard_jours"] > couverture else None
manque = max(0, sc["retard_jours"] - couverture) * conso

produits_ligne = prod[prod["ligne"] == sc["ligne"]]["produit"].unique()
cmd = d["commandes"].copy()
cmd["jour"] = (pd.to_datetime(cmd["date_livraison"]).dt.date - J0).apply(lambda t: t.days)
menacees = cmd[cmd["produit"].isin(produits_ligne) & (cmd["jour"] >= couverture)]

print(f"Stock Ligne 2 : {stock_ligne:,.0f} unites | consommation : {conso}/jour | couverture : {couverture:.0f} jours")
print(f"Retard {sc['fournisseur_en_retard']} : {sc['retard_jours']} jours -> arret a J+{arret_jour}, manque {manque:,.0f} unites")
print(f"Commandes menacees : {', '.join(menacees['commande_id'])} (clients : {', '.join(sorted(menacees['client'].unique()))})")
print(f"Stock Entrepot Nord : {stock_nord:,.0f} unites -> option A possible : {stock_nord >= manque}")

assert couverture == 4, couverture
assert arret_jour == 4
assert manque == 1200, manque
assert sorted(menacees["client"].unique()) == ["Client B", "Client C"]
assert len(menacees) == 3
assert stock_nord >= manque
print("\nOK : le scenario Delta est coherent avec la fiche (arret J+4, manque 1 200, 2 clients, 3 commandes).")
