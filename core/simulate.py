"""SupplyMind : couverture de stock, simulation de retard fournisseur, trois solutions.

Avec les donnees fournies (scenario Delta, voir config/params.json) : couverture 4 jours, arret J+4,
manque 1 200 unites, commandes CMD004/CMD005/CMD007, clients B et C.
Toutes les valeurs sont calculees par du code ; le modele de langage ne fait que les reformuler.
"""
from datetime import date

import pandas as pd

from core.loader import PARAMS

MAX_PLAUSIBLE = 50_000


def _stock(data, lieu, matiere):
    """Stock d'une matiere dans un lieu, exprime dans l'unite cible. Les valeurs invalides sont ignorees
    et les unites melangees converties (tonnes -> kg, cartons -> unites)."""
    conv = PARAMS["conversions"]
    cible = PARAMS["unite_cible"][matiere]
    facteurs = {(cible, cible): 1, ("tonnes", "kg"): conv["tonnes_vers_kg"],
                ("cartons", "unites"): conv["bouteilles_par_carton"]}
    s = data["stocks"]
    s = s[(s["lieu"] == lieu) & (s["matiere"] == matiere)]
    total = 0.0
    for q, unite in zip(pd.to_numeric(s["quantite"], errors="coerce"), s["unite"]):
        f = facteurs.get((unite, cible))
        if f and pd.notna(q) and 0 < q <= MAX_PLAUSIBLE:
            total += q * f
    return total


def stock_coverage(data, ligne, matiere):
    """Retourne {"stock", "conso_par_jour", "jours"} pour une ligne et une matiere."""
    p = data["production"]
    conso = float(p[(p["ligne"] == ligne) & (p["matiere"] == matiere)]["conso_par_jour"].iloc[0])
    stock = _stock(data, ligne, matiere)
    return {"stock": round(stock), "conso_par_jour": round(conso), "jours": stock / conso}


def scenario_par_defaut(data):
    """(fournisseur, retard en jours) du scenario de la fiche ; si ce fournisseur n'existe pas dans les donnees
    (fichiers importes), le fournisseur dont un retard fait le plus de degats."""
    sc = PARAMS["scenario"]
    noms = sorted(data["fournisseurs"]["fournisseur"].unique())
    if sc["fournisseur_en_retard"] in noms or not noms:
        return sc["fournisseur_en_retard"], sc["retard_jours"]
    pire = max(noms, key=lambda f: (simulate_supplier_delay(data, f, sc["retard_jours"])["manque"], f))
    return pire, sc["retard_jours"]


def simulate_supplier_delay(data, fournisseur, retard_jours, ligne=None, matiere=None):
    """Simule le retard d'un fournisseur. Retourne :
    arret_jour (int ou None), manque (unites), commandes (ids), clients (noms), couverture_jours,
    ligne, matiere (la ligne la plus touchee), details (une entree par ligne et matiere concernees),
    commandes_detail (liste de dictionnaires), noeuds_impactes (pour colorer le graphe)."""
    four, prod, cmd = data["fournisseurs"], data["production"], data["commandes"]
    matieres = sorted(four[four["fournisseur"] == fournisseur]["matiere"].unique())
    details = []
    for m in matieres:
        if matiere and m != matiere:
            continue
        for _, r in prod[prod["matiere"] == m].iterrows():
            if ligne and r["ligne"] != ligne:
                continue
            c = stock_coverage(data, r["ligne"], m)
            arret = int(c["jours"]) if retard_jours > c["jours"] else None
            details.append({"ligne": r["ligne"], "matiere": m, "stock": c["stock"],
                            "conso_par_jour": c["conso_par_jour"], "couverture_jours": round(c["jours"], 1),
                            "arret_jour": arret,
                            "manque": round(max(0.0, retard_jours - c["jours"]) * c["conso_par_jour"])})
    res = {"fournisseur": fournisseur, "retard_jours": retard_jours, "ligne": None, "matiere": None,
           "couverture_jours": None, "arret_jour": None, "manque": 0, "commandes": [], "clients": [],
           "commandes_detail": [], "details": details, "noeuds_impactes": []}
    if not details:
        return res
    arretes = [d for d in details if d["arret_jour"] is not None]
    principal = max(arretes, key=lambda d: d["manque"]) if arretes else min(details, key=lambda d: d["couverture_jours"])
    res.update(ligne=principal["ligne"], matiere=principal["matiere"],
               couverture_jours=principal["couverture_jours"], arret_jour=principal["arret_jour"],
               manque=principal["manque"])
    if not arretes:
        return res

    j0 = date.fromisoformat(PARAMS["date_reference"])
    menacees, produits = [], set()
    for d in arretes:
        prods = set(prod[prod["ligne"] == d["ligne"]]["produit"])
        produits |= prods
        for _, o in cmd[cmd["produit"].isin(prods)].iterrows():
            jour = (date.fromisoformat(str(o["date_livraison"])) - j0).days
            if jour >= d["arret_jour"]:
                menacees.append({"commande_id": o["commande_id"], "client": o["client"], "produit": o["produit"],
                                 "quantite": int(o["quantite"]), "date_livraison": str(o["date_livraison"]),
                                 "jour": jour})
    uniques = {}
    for o in menacees:  # une commande touchee par deux arrets n'est comptee qu'une fois (la plus precoce)
        if o["commande_id"] not in uniques or o["jour"] < uniques[o["commande_id"]]["jour"]:
            uniques[o["commande_id"]] = o
    menacees = list(uniques.values())
    menacees.sort(key=lambda o: o["commande_id"])
    res["commandes_detail"] = menacees
    res["commandes"] = [o["commande_id"] for o in menacees]
    res["clients"] = sorted({o["client"] for o in menacees})
    res["noeuds_impactes"] = ([fournisseur] + sorted({d["matiere"] for d in arretes}) + sorted({d["ligne"] for d in arretes})
                              + sorted(produits) + res["commandes"] + res["clients"])
    return res


def list_options(data, simulation):
    """Les trois solutions quand un arret est prevu (liste vide sinon) :
    A = transferer depuis l'entrepot Nord, B = commande express chez un autre fournisseur,
    C = reporter la production de la ligne. Chaque option : code, libelle, surcout_pct, risque, faisable."""
    manque = simulation["manque"]
    if manque <= 0:
        return []
    m, ligne, arret = simulation["matiere"], simulation["ligne"], simulation["arret_jour"]
    unite = PARAMS["unite_cible"][m].replace("unites", "unités")
    nord = round(_stock(data, "Entrepot Nord", m))
    options = [{"code": "A", "faisable": nord >= manque, "surcout_pct": 0.0, "risque": "moyen",
                "libelle": f"Transférer {manque:,} {unite} depuis l'entrepôt Nord ({nord:,} en stock)".replace(",", " ")}]

    four = data["fournisseurs"]
    ref = four[(four["fournisseur"] == simulation["fournisseur"]) & (four["matiere"] == m)]
    autres = four[(four["fournisseur"] != simulation["fournisseur"]) & (four["matiere"] == m)]
    if len(autres):
        alt = autres.sort_values("delai_moyen_jours").iloc[0]
        prix_ref = float(ref["prix_relatif"].iloc[0]) if len(ref) else 1.0
        options.append({"code": "B", "faisable": alt["delai_moyen_jours"] <= arret,
                        "surcout_pct": round((alt["prix_relatif"] / prix_ref - 1) * 100, 1), "risque": "faible",
                        "libelle": f"Commander {manque:,} {unite} en express chez {alt['fournisseur']} "
                                   f"(livraison en {int(alt['delai_moyen_jours'])} jours)".replace(",", " ")})
    else:
        options.append({"code": "B", "faisable": False, "surcout_pct": 0.0, "risque": "faible",
                        "libelle": "Aucun autre fournisseur pour cette matière"})
    options.append({"code": "C", "faisable": True,
                    "surcout_pct": float(PARAMS["scenario"]["surcout_report_production_pct"]), "risque": "eleve",
                    "libelle": f"Reporter la production de la {ligne} en attendant la livraison"})
    return options
