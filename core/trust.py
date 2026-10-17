"""Score de confiance d'une reponse (implemente : la formule est fixee par SPECS.md)."""
from core.loader import PARAMS


def score_from_parts(completude, unicite, validite, coherence):
    """Note de qualite d'un fichier, de 0 a 100. Les 4 mesures sont entre 0 et 1."""
    return round(100 * (0.30 * completude + 0.30 * unicite + 0.20 * validite + 0.20 * coherence), 1)


def couleur(score):
    seuils = PARAMS["seuils_confiance"]
    if score >= seuils["vert"]:
        return "vert"
    if score >= seuils["orange"]:
        return "orange"
    return "rouge"


def trust_score(sources, scores, poids=None):
    """Confiance dans une reponse.

    sources : noms des fichiers utilises, ex. ["stocks", "production"]
    scores  : note de qualite de chaque fichier, ex. {"stocks": 55, "production": 90}
    poids   : importance de chaque fichier (1 par defaut)

    confiance = min(moyenne ponderee des notes, note la plus faible + 15)
    Retourne {"score": int, "couleur": "vert|orange|rouge", "a_confirmer": bool, "plus_faible": str}.
    """
    if not sources:
        raise ValueError("Au moins une source est necessaire.")
    poids = poids or {}
    total = sum(poids.get(s, 1) for s in sources)
    moyenne = sum(scores[s] * poids.get(s, 1) for s in sources) / total
    plus_faible = min(sources, key=lambda s: scores[s])
    score = round(min(moyenne, scores[plus_faible] + 15))
    c = couleur(score)
    return {"score": score, "couleur": c, "a_confirmer": c == "rouge", "plus_faible": plus_faible}
