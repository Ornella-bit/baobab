"""SupplyMind : graphe de la chaine (fournisseur -> matiere -> ligne -> produit -> commande -> client)."""
import networkx as nx

ORDRE = ["fournisseur", "matiere", "ligne", "produit", "commande", "client"]


def build_graph(data):
    """Construit un networkx.DiGraph. Chaque noeud a un attribut « type » (voir ORDRE).
    Liens : livre, consomme (conso_par_jour), fabrique, concerne, pour."""
    g = nx.DiGraph()
    for _, r in data["fournisseurs"].iterrows():
        g.add_node(r["fournisseur"], type="fournisseur")
        g.add_node(r["matiere"], type="matiere")
        g.add_edge(r["fournisseur"], r["matiere"], relation="livre", delai_moyen_jours=r["delai_moyen_jours"])
    for _, r in data["production"].iterrows():
        g.add_node(r["ligne"], type="ligne")
        g.add_node(r["produit"], type="produit")
        g.add_edge(r["matiere"], r["ligne"], relation="consomme", conso_par_jour=r["conso_par_jour"])
        g.add_edge(r["ligne"], r["produit"], relation="fabrique")
    for _, r in data["commandes"].iterrows():
        g.add_node(r["commande_id"], type="commande")
        g.add_node(r["client"], type="client")
        g.add_edge(r["produit"], r["commande_id"], relation="concerne")
        g.add_edge(r["commande_id"], r["client"], relation="pour")
    return g


def downstream(graph, noeud):
    """Tous les noeuds touches en aval d'un noeud, tries par type puis par nom : liste de (nom, type)."""
    touches = [(n, graph.nodes[n]["type"]) for n in nx.descendants(graph, noeud)]
    return sorted(touches, key=lambda t: (ORDRE.index(t[1]), t[0]))
