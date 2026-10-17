"""Graphe de la chaine (A FAIRE, etape 4B). Utilise networkx (import dans les fonctions)."""


def build_graph(data):
    """Construit un networkx.DiGraph. Noeuds : fournisseur, matiere, ligne, produit, commande, client
    (attribut « type »). Liens : fournisseur->matiere (livre), matiere->ligne (consomme, attribut
    conso_par_jour), ligne->produit (fabrique), produit->commande (concerne), commande->client (pour)."""
    raise NotImplementedError


def downstream(graph, noeud):
    """Tous les noeuds touches en aval d'un noeud (ex. un fournisseur). Retourne une liste de (nom, type)."""
    raise NotImplementedError
