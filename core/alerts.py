"""Alertes du tableau de bord : ce qui demande l'attention du directeur, du plus urgent au moins urgent.

Rien n'est invente : chaque alerte vient d'une fonction de calcul existante (simulation, couverture de stock,
notes de qualite, fiabilite des fournisseurs, dates de livraison). Les seuils sont ici, en haut du fichier.
"""
from datetime import date

from core import quality
from core.loader import PARAMS
from core.simulate import scenario_par_defaut, simulate_supplier_delay, stock_coverage

COUVERTURE_ROUGE = 3        # jours de stock : en dessous, alerte rouge
COUVERTURE_ORANGE = 7       # en dessous, alerte orange
FIABILITE_MINIMALE = 85     # % : un fournisseur moins fiable est signale
LIVRAISON_PROCHE = 7        # jours : les commandes a livrer d'ici la sont signalees
ORDRE_NIVEAU = {"rouge": 0, "orange": 1, "vert": 2}


def couvertures(data):
    """Couverture en jours de chaque couple (ligne, matiere), de la plus courte a la plus longue."""
    out = []
    for _, r in data["production"].iterrows():
        c = stock_coverage(data, r["ligne"], r["matiere"])
        out.append({"ligne": r["ligne"], "matiere": r["matiere"], "stock": c["stock"],
                    "conso_par_jour": c["conso_par_jour"], "jours": round(c["jours"], 1)})
    return sorted(out, key=lambda c: c["jours"])


def _matiere(m):
    return str(m).replace("concentre", "concentré").replace("_", " ")


def _n(x):
    return f"{int(round(x)):,}".replace(",", " ")


def compute_alerts(data, scores, issues=None, fournisseur=None, retard_jours=None):
    """Liste d'alertes [{niveau, titre, detail, page}] triee : rouge, orange, puis vert.
    fournisseur / retard_jours : scenario simule (par defaut celui de la fiche de presentation)."""
    sc = PARAMS["scenario"]
    defaut = scenario_par_defaut(data)
    fournisseur = fournisseur or defaut[0]
    retard_jours = defaut[1] if retard_jours is None else retard_jours
    alertes = []

    # 1) le scenario de retard fournisseur
    sim = simulate_supplier_delay(data, fournisseur, retard_jours)
    if sim["arret_jour"] is not None:
        alertes.append({"niveau": "rouge", "page": "Chaîne",
                        "titre": f"La {sim['ligne']} s'arrêterait à J+{sim['arret_jour']} si {fournisseur} a {retard_jours} jours de retard",
                        "detail": f"Il manquerait {_n(sim['manque'])} unités de {_matiere(sim['matiere'])} ; "
                                  f"{len(sim['commandes'])} commandes et {len(sim['clients'])} clients seraient touchés. Trois solutions sont chiffrées."})
    else:
        alertes.append({"niveau": "vert", "page": "Chaîne",
                        "titre": f"Aucun arrêt prévu si {fournisseur} a {retard_jours} jours de retard",
                        "detail": "Les stocks couvrent le retard annoncé."})

    # 2) couverture de stock
    for c in couvertures(data):
        if c["jours"] < COUVERTURE_ROUGE:
            niveau = "rouge"
        elif c["jours"] < COUVERTURE_ORANGE:
            niveau = "orange"
        else:
            continue
        alertes.append({"niveau": niveau, "page": "Chaîne",
                        "titre": f"Stock court : {_matiere(c['matiere'])} sur la {c['ligne']} ({c['jours']:g} jours)".replace(".", ","),
                        "detail": f"{_n(c['stock'])} en stock pour {_n(c['conso_par_jour'])} consommés par jour."})

    # 3) qualite des donnees
    seuils = PARAMS["seuils_confiance"]
    for f, note in sorted(scores.items(), key=lambda t: t[1]):
        if note >= seuils["vert"]:
            continue
        niveau = "rouge" if note < seuils["orange"] else "orange"
        n = len(issues[f]) if issues and f in issues else None
        alertes.append({"niveau": niveau, "page": "Données",
                        "titre": f"Données « {f} » peu fiables : note {note:g} sur 100".replace(".", ","),
                        "detail": (f"{n} problèmes détectés. " if n else "") + "Les réponses qui s'appuient sur ce fichier sont à confirmer."})
    if issues:
        corrigeables = sum(1 for f in issues for i in issues[f] if i["correction"] is not None)
        if corrigeables:
            alertes.append({"niveau": "orange", "page": "Données",
                            "titre": f"{_n(corrigeables)} corrections prêtes à valider",
                            "detail": "Les valider dans la page Données fait monter la note de qualité et la confiance du copilote."})

    # 4) fournisseurs peu fiables
    four = data["fournisseurs"]
    for f, fiab in four.groupby("fournisseur")["fiabilite_pct"].mean().sort_values().items():
        if fiab < FIABILITE_MINIMALE:
            alertes.append({"niveau": "orange", "page": "Chaîne",
                            "titre": f"{f} : fiabilité moyenne de {fiab:.0f} %",
                            "detail": f"Sous le seuil de {FIABILITE_MINIMALE} %. Prévoir un fournisseur de secours pour ses matières."})

    # 5) livraisons proches
    ref = date.fromisoformat(PARAMS["date_reference"])
    proches = [(r["commande_id"], (date.fromisoformat(str(r["date_livraison"])) - ref).days) for _, r in data["commandes"].iterrows()]
    proches = [p for p in proches if 0 <= p[1] <= LIVRAISON_PROCHE]
    if proches:
        alertes.append({"niveau": "orange", "page": "Chaîne",
                        "titre": f"{len(proches)} commandes à livrer d'ici {LIVRAISON_PROCHE} jours",
                        "detail": "Les plus proches : " + ", ".join(f"{c} (J+{j})" for c, j in sorted(proches, key=lambda p: p[1])[:4]) + "."})

    alertes.sort(key=lambda a: ORDRE_NIVEAU[a["niveau"]])
    return alertes


def resume_alertes(alertes):
    """{rouge: n, orange: n, vert: n}."""
    return {n: sum(1 for a in alertes if a["niveau"] == n) for n in ORDRE_NIVEAU}
