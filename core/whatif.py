"""Simulation « Et si… ? » : on change un parametre (consommation, stock, retard) et on compare avant / apres.

Aucune donnee d'origine n'est modifiee : chaque scenario travaille sur une copie. Les chiffres viennent de
core/simulate.py, comme partout ailleurs dans l'application.
"""
import pandas as pd

from core.loader import PARAMS
from core.simulate import simulate_supplier_delay, stock_coverage


def sensibilite(data, fournisseur, jours_max=14):
    """Pour chaque retard de 0 a jours_max : arret (jour ou None), manque, nombre de commandes et de clients touches."""
    out = []
    for j in range(jours_max + 1):
        s = simulate_supplier_delay(data, fournisseur, j)
        out.append({"jours": j, "arret_jour": s["arret_jour"], "manque": s["manque"],
                    "commandes": len(s["commandes"]), "clients": len(s["clients"])})
    return out


def carte_des_risques(data, jours_max=10):
    """Manque (unites) de chaque fournisseur pour chaque retard : {fournisseur: [manque a 0 jour, a 1 jour, ...]}."""
    return {f: [simulate_supplier_delay(data, f, j)["manque"] for j in range(jours_max + 1)]
            for f in sorted(data["fournisseurs"]["fournisseur"].dropna().unique())}


def retard_supportable(data, fournisseur):
    """Nombre de jours de retard que la chaine encaisse sans arret (couverture la plus courte parmi les matieres du fournisseur)."""
    prod, four = data["production"], data["fournisseurs"]
    matieres = set(four[four["fournisseur"] == fournisseur]["matiere"])
    jours = [stock_coverage(data, r["ligne"], r["matiere"])["jours"] for _, r in prod.iterrows() if r["matiere"] in matieres]
    return round(min(jours), 1) if jours else None


def modifier(data, conso_pct=0, stock_supplementaire=0, ligne=None, matiere=None):
    """Copie des donnees avec : consommation changee de conso_pct % et un lot supplementaire de stock sur (ligne, matiere)."""
    copie = {k: v.copy() for k, v in data.items()}
    prod = copie["production"]
    masque = pd.Series(True, index=prod.index)
    if ligne:
        masque &= prod["ligne"] == ligne
    if matiere:
        masque &= prod["matiere"] == matiere
    if conso_pct:
        prod.loc[masque, "conso_par_jour"] = (prod.loc[masque, "conso_par_jour"] * (1 + conso_pct / 100)).round()
    if stock_supplementaire and ligne and matiere:
        unite = PARAMS["unite_cible"][matiere]
        lot = pd.DataFrame([{"lot_id": "L_WHATIF", "lieu": ligne, "matiere": matiere, "quantite": str(int(stock_supplementaire)),
                             "unite": unite, "date_reception": PARAMS["date_reference"]}])
        copie["stocks"] = pd.concat([copie["stocks"], lot], ignore_index=True)
    return copie


def comparer(data, fournisseur, retard_jours, conso_pct=0, stock_supplementaire=0, ligne=None, matiere=None):
    """{"avant": simulation, "apres": simulation modifiee, "gain_manque": unites evitees, "commandes_sauvees": n}."""
    avant = simulate_supplier_delay(data, fournisseur, retard_jours)
    ligne = ligne or avant["ligne"]
    matiere = matiere or avant["matiere"]
    apres = simulate_supplier_delay(modifier(data, conso_pct, stock_supplementaire, ligne, matiere), fournisseur, retard_jours)
    return {"avant": avant, "apres": apres, "gain_manque": avant["manque"] - apres["manque"],
            "commandes_sauvees": len(avant["commandes"]) - len(apres["commandes"]), "ligne": ligne, "matiere": matiere}
