"""Copilote : modele de langage + fonctions (A FAIRE, etape 4D). Le modele ne calcule jamais."""

OUTILS = ["get_stock_coverage", "simulate_supplier_delay", "list_options", "get_trust", "get_passport"]


def get_stock_coverage(ligne, matiere="concentre_mangue"):
    raise NotImplementedError


def get_passport(produit):
    """Fournisseurs, lots et controles d'un produit. Retourne un dictionnaire."""
    raise NotImplementedError


def ask(question, role, data, scores):
    """Retourne {"texte": str, "sources": [fichiers], "confiance": {score, couleur, ...}, "options": [...]|None}.
    Si le service du modele est indisponible, retourne la reponse de cache/answers.json."""
    raise NotImplementedError
