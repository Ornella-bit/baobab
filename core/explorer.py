"""Explorer la chaine : la fiche d'un element du graphe (fournisseur, matiere, ligne, produit, commande, client).

Chaque fiche ne contient que des faits calcules (stock, couverture, delais, quantites) et la liste des elements relies.
"""
import networkx as nx

from core.graph import ORDRE
from core.loader import PARAMS
from core.simulate import simulate_supplier_delay, stock_coverage

TITRES = {"fournisseur": "Fournisseur", "matiere": "Matière", "ligne": "Ligne de production", "produit": "Produit",
          "commande": "Commande", "client": "Client"}


def _n(x):
    return f"{int(round(x)):,}".replace(",", " ")


def _mat(m):
    return str(m).replace("concentre", "concentré").replace("_", " ")


def type_de(graph, noeud):
    return graph.nodes[noeud]["type"]


def noeuds_par_type(graph):
    return {t: sorted(n for n, d in graph.nodes(data=True) if d["type"] == t) for t in ORDRE}


def liees(graph, noeud):
    """(amont, aval) : tous les elements relies avant et apres, tries par type."""
    cle = lambda n: (ORDRE.index(graph.nodes[n]["type"]), n)
    return sorted(nx.ancestors(graph, noeud), key=cle), sorted(nx.descendants(graph, noeud), key=cle)


def fiche(data, graph, noeud):
    """{type, titre, faits: [(libelle, valeur)], alerte: texte ou None, amont: [...], aval: [...]}"""
    t = type_de(graph, noeud)
    faits, alerte = [], None
    sc = PARAMS["scenario"]
    if t == "fournisseur":
        f = data["fournisseurs"][data["fournisseurs"]["fournisseur"] == noeud]
        faits = [("Matières livrées", ", ".join(_mat(m) for m in f["matiere"])),
                 ("Délai moyen", f"{f['delai_moyen_jours'].mean():.1f} jours".replace(".", ",")),
                 ("Fiabilité moyenne", f"{f['fiabilite_pct'].mean():.0f} %"),
                 ("Prix relatif moyen", f"{f['prix_relatif'].mean():.2f}".replace(".", ","))]
        s = simulate_supplier_delay(data, noeud, sc["retard_jours"])
        if s["arret_jour"] is not None:
            alerte = (f"Avec {sc['retard_jours']} jours de retard : arrêt de la {s['ligne']} à J+{s['arret_jour']}, "
                      f"manque de {_n(s['manque'])} unités, {len(s['commandes'])} commandes touchées.")
        else:
            alerte = f"Avec {sc['retard_jours']} jours de retard : aucun arrêt de production."
    elif t == "matiere":
        p = data["production"][data["production"]["matiere"] == noeud]
        lignes = []
        for _, r in p.iterrows():
            c = stock_coverage(data, r["ligne"], noeud)
            lignes.append(f"{r['ligne']} : {_n(c['stock'])} en stock, {c['jours']:.1f} jours".replace(".", ","))
        faits = [("Fournisseurs", ", ".join(sorted(data["fournisseurs"][data["fournisseurs"]["matiere"] == noeud]["fournisseur"]))),
                 ("Unité de référence", PARAMS["unite_cible"].get(noeud, "?").replace("unites", "unités")),
                 ("Stock et couverture", " | ".join(lignes) if lignes else "non utilisée en production")]
    elif t == "ligne":
        p = data["production"][data["production"]["ligne"] == noeud]
        faits = [("Produits fabriqués", ", ".join(sorted(p["produit"].unique())))]
        courtes = sorted(((stock_coverage(data, noeud, r["matiere"])["jours"], r["matiere"]) for _, r in p.iterrows()))
        faits += [("Matière la plus juste", f"{_mat(courtes[0][1])} ({courtes[0][0]:.1f} jours)".replace(".", ","))]
        faits += [("Consommation par jour", " | ".join(f"{_mat(r['matiere'])} {_n(r['conso_par_jour'])}" for _, r in p.iterrows()))]
    elif t == "produit":
        p = data["production"][data["production"]["produit"] == noeud]
        c = data["commandes"][data["commandes"]["produit"] == noeud]
        faits = [("Fabriqué sur", ", ".join(sorted(p["ligne"].unique()))), ("Matières", ", ".join(sorted(_mat(m) for m in p["matiere"].unique()))),
                 ("Commandes", f"{len(c)} commandes, {_n(c['quantite'].sum())} unités")]
    elif t == "commande":
        r = data["commandes"][data["commandes"]["commande_id"] == noeud].iloc[0]
        faits = [("Client", r["client"]), ("Produit", r["produit"]), ("Quantité", _n(r["quantite"])), ("Livraison", str(r["date_livraison"]))]
        s = simulate_supplier_delay(data, sc["fournisseur_en_retard"], sc["retard_jours"])
        if noeud in s["commandes"]:
            alerte = f"Menacée si {sc['fournisseur_en_retard']} a {sc['retard_jours']} jours de retard."
    elif t == "client":
        c = data["commandes"][data["commandes"]["client"] == noeud]
        faits = [("Commandes", ", ".join(c["commande_id"])), ("Quantité totale", f"{_n(c['quantite'].sum())} unités")]
        s = simulate_supplier_delay(data, sc["fournisseur_en_retard"], sc["retard_jours"])
        n = sum(1 for x in c["commande_id"] if x in s["commandes"])
        if n:
            alerte = f"{n} de ses commandes seraient menacées si {sc['fournisseur_en_retard']} a {sc['retard_jours']} jours de retard."
    amont, aval = liees(graph, noeud)
    return {"type": t, "titre": f"{TITRES[t]} : {_mat(noeud) if t == 'matiere' else noeud}", "faits": faits, "alerte": alerte,
            "amont": amont, "aval": aval}
