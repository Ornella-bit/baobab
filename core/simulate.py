"""SupplyMind : couverture, simulation de retard, trois solutions (A FAIRE, etape 4B).

Resultat attendu avec les donnees fournies (scenario Delta, voir config/params.json) :
couverture 4 jours, arret J+4, manque 1 200 unites, commandes CMD004/CMD005/CMD007, clients B et C.
"""


def stock_coverage(data, ligne, matiere):
    """Retourne {"stock": int, "conso_par_jour": int, "jours": float}. N'utilise que l'unite « unites »."""
    raise NotImplementedError


def simulate_supplier_delay(data, fournisseur, retard_jours, ligne=None, matiere=None):
    """Retourne {"arret_jour": int|None, "manque": int, "commandes": [ids], "clients": [noms],
    "couverture_jours": float, "ligne": str, "matiere": str}."""
    raise NotImplementedError


def list_options(data, simulation):
    """Retourne exactement 3 options :
    {"code": "A|B|C", "libelle": str, "surcout_pct": float, "risque": "faible|moyen|eleve", "faisable": bool}
    A = transferer depuis l'entrepot Nord (0 %, moyen) ; B = commande express chez Sigma (+6 %, faible) ;
    C = reporter la production de la Ligne 2 (+2 %, eleve)."""
    raise NotImplementedError
