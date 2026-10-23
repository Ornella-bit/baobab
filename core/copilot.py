"""Copilote : un modele de langage qui APPELLE des fonctions (il ne calcule jamais), avec un moteur de
secours hors ligne qui reutilise exactement les memes fonctions.

Etape 12 : le moteur hors ligne comprend mieux les questions (fautes de frappe, mots de la vie courante, nombres
en lettres), se souvient de la conversation (« Et pour Sigma ? », « Et si c'était 7 jours ? »), explique ses
notes (« Pourquoi cette confiance ? ») et sait faire le classement des fournisseurs, le bilan de la situation,
le rapport qualite d'un fichier, le detail d'une commande ou une recommandation.

ask(question, role, data, scores) retourne :
  {"texte", "sources" (fichiers utilises), "confiance" ({score, couleur, a_confirmer, plus_faible} ou None),
   "options" (liste A/B/C ou None), "outils" (fonctions appelees), "mode" ("llm", "hors_ligne"...),
   "memoire" (a renvoyer a la question suivante), "suggestions" (questions de suite), "explication" (etapes du calcul)}
Si la cle d'API manque, si Internet est coupe ou si le service est en panne, on bascule seul sur le mode hors ligne.
"""
import json
import os
import re
from collections import Counter

from core import askdata, nlu, quality, rbac
from core.loader import PARAMS, ROOT
from core.simulate import _stock, list_options, simulate_supplier_delay, stock_coverage, scenario_par_defaut
from core.trust import couleur, trust_score

try:  # la cle se lit dans le fichier .env (jamais publie sur GitHub)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

MODELE = os.getenv("BAOBAB_MODELE", "claude-sonnet-5-5")
OUTILS = ["get_stock_coverage", "simulate_supplier_delay", "list_options", "get_trust", "get_passport",
          "explain_trust", "get_quality_report", "rank_suppliers", "get_briefing", "query_data", "get_order"]
TOUS = ["stocks", "production", "fournisseurs", "commandes"]
FICHIERS_PAR_OUTIL = {
    "get_stock_coverage": {"stocks", "production"},
    "simulate_supplier_delay": set(TOUS),
    "list_options": set(TOUS),
    "get_passport": set(TOUS),
    "rank_suppliers": set(TOUS),
    "get_briefing": set(TOUS),
    "get_order": {"commandes"},
    "query_data": set(),  # les tables interrogees sont ajoutees dynamiquement
    "get_trust": set(),
    "explain_trust": set(),
    "get_quality_report": set(),  # le fichier etudie est ajoute dynamiquement
}
POIDS_MESURES = {"completude": 0.30, "unicite": 0.30, "validite": 0.20, "coherence": 0.20}
NOM_MESURE = {"completude": "complétude (cases remplies)", "unicite": "unicité (pas de doublons)",
              "validite": "validité (valeurs plausibles)", "coherence": "cohérence (formats et unités)"}
RISQUE_RANG = {"faible": 0, "moyen": 1, "eleve": 2}

SYSTEME = """Tu es le copilote de Baobab Sève, une plateforme qui aide une usine de jus de fruits (Délice SA) à fiabiliser \
ses données et à anticiper les ruptures de sa chaîne de production.
Règles :
- Réponds en français simple, pour quelqu'un qui n'est pas spécialiste. Au plus 6 phrases.
- Tu ne calcules JAMAIS toi-même : pour tout chiffre, appelle un outil et n'utilise que ce qu'il renvoie.
- Si aucun outil ne permet de répondre, dis « Je ne sais pas : ce n'est pas dans mes données » et n'invente rien.
- Quand un arrêt de production est prévu, présente les trois solutions A, B et C avec leur surcoût et leur risque.
- La décision finale revient toujours à un humain : tu proposes, tu ne décides pas.
- Ne donne jamais de salaires ni d'informations personnelles : tu n'y as pas accès.
- Ne parle pas du score de confiance : l'application l'affiche elle-même, sauf si on te demande de l'expliquer (outil explain_trust)."""

_FOURNI = {"fournisseur": {"type": "string", "description": "Alpha, Delta ou Sigma"},
           "retard_jours": {"type": "integer", "description": "retard annoncé en jours"}}
SCHEMAS = [
    {"name": "get_stock_coverage",
     "description": "Jours de stock restants pour une matière sur une ligne de production.",
     "input_schema": {"type": "object", "properties": {
         "ligne": {"type": "string", "description": "Ligne 1 ou Ligne 2"},
         "matiere": {"type": "string", "description": "concentre_mangue, concentre_orange, sucre ou bouteilles"}},
         "required": ["ligne", "matiere"]}},
    {"name": "simulate_supplier_delay",
     "description": "Simule le retard d'un fournisseur : jour d'arrêt, manque, commandes et clients touchés.",
     "input_schema": {"type": "object", "properties": _FOURNI, "required": ["fournisseur", "retard_jours"]}},
    {"name": "list_options",
     "description": "Les trois solutions chiffrées (A, B, C) si le retard d'un fournisseur provoque un arrêt.",
     "input_schema": {"type": "object", "properties": _FOURNI, "required": ["fournisseur", "retard_jours"]}},
    {"name": "get_trust",
     "description": "Score de confiance (0 à 100) d'une réponse construite à partir de ces fichiers.",
     "input_schema": {"type": "object", "properties": {
         "sources": {"type": "array", "items": {"type": "string"},
                     "description": "stocks, production, fournisseurs, commandes, clients ou employes"}},
         "required": ["sources"]}},
    {"name": "get_passport",
     "description": "Passeport d'un produit : ligne, matières, fournisseurs, lots en stock, commandes.",
     "input_schema": {"type": "object", "properties": {
         "produit": {"type": "string", "description": "ex. Nectar de mangue 1 L"}}, "required": ["produit"]}},
    {"name": "explain_trust",
     "description": "Explique le calcul du score de confiance : note de chaque fichier, moyenne, plafond, fichier le plus faible.",
     "input_schema": {"type": "object", "properties": {"sources": {"type": "array", "items": {"type": "string"}}},
                      "required": ["sources"]}},
    {"name": "get_quality_report",
     "description": "Rapport de qualité d'un fichier : note, les 4 mesures, types de problèmes, corrections possibles.",
     "input_schema": {"type": "object", "properties": {"fichier": {"type": "string"}}, "required": ["fichier"]}},
    {"name": "rank_suppliers",
     "description": "Classe les fournisseurs du plus risqué au moins risqué pour un retard donné.",
     "input_schema": {"type": "object", "properties": {"retard_jours": {"type": "integer"}}, "required": ["retard_jours"]}},
    {"name": "get_briefing",
     "description": "Bilan de la situation : note des données, stocks les plus courts, risque du scénario en cours.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "query_data",
     "description": "Répond à n'importe quelle question chiffrée sur les données (combien, total, moyenne, plus grand, liste, "
                    "regroupement par client / produit / ville / fournisseur / lieu, filtres sur une date ou un seuil). "
                    "Écris la question en français dans « question ». Utilise-le pour toute question de données sans outil dédié.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "get_order",
     "description": "Détail d'une commande (ou des commandes d'un client) et menace éventuelle selon le scénario.",
     "input_schema": {"type": "object", "properties": {"commande_id": {"type": "string"}, "client": {"type": "string"}}}},
]


# ------------------------------------------------------------------ fonctions de calcul (les « outils »)
def get_stock_coverage(data, ligne, matiere):
    c = stock_coverage(data, ligne, matiere)
    return {"ligne": ligne, "matiere": matiere, "stock": c["stock"], "conso_par_jour": c["conso_par_jour"],
            "jours": round(c["jours"], 1)}


def get_passport(data, produit):
    """Passeport d'un produit : ligne, matieres, fournisseurs (delai, fiabilite), lots en stock, commandes."""
    prod, four, stocks, cmd = data["production"], data["fournisseurs"], data["stocks"], data["commandes"]
    p = prod[prod["produit"] == produit]
    if p.empty:
        return {"erreur": f"produit inconnu : {produit}"}
    ligne = p["ligne"].iloc[0]
    matieres = []
    for m in p["matiere"]:
        lots = stocks[(stocks["lieu"] == ligne) & (stocks["matiere"] == m)]["lot_id"].tolist()
        fs = four[four["matiere"] == m]
        matieres.append({"matiere": m, "nb_lots": len(lots), "lots_exemples": lots[:3],
                         "fournisseurs": [{"nom": r["fournisseur"], "delai_jours": int(r["delai_moyen_jours"]),
                                           "fiabilite_pct": int(r["fiabilite_pct"])} for _, r in fs.iterrows()]})
    c = cmd[cmd["produit"] == produit]
    return {"produit": produit, "ligne": ligne, "matieres": matieres,
            "commandes": c["commande_id"].tolist(), "clients": sorted(c["client"].unique())}


def _problemes(ctx, fichier):
    """Problemes detectes d'un fichier (fournis par l'application, sinon calcules une fois)."""
    cache = ctx.setdefault("_problemes", {})
    if fichier not in cache:
        fournis = (ctx.get("problemes") or {}).get(fichier)
        cache[fichier] = fournis if fournis is not None else quality.list_issues(ctx["data"][fichier], fichier)
    return cache[fichier]


def get_quality_report(ctx, fichier):
    """Note d'un fichier, ses 4 mesures, les points perdus par mesure, les problemes par type."""
    if fichier not in ctx["data"]:
        return {"erreur": f"fichier inconnu : {fichier}"}
    df = ctx["data"][fichier]
    m = quality.measures(df, fichier)
    pertes = {k: round(100 * POIDS_MESURES[k] * (1 - m[k]), 1) for k in m}
    issues = _problemes(ctx, fichier)
    corrigeables = sum(1 for i in issues if i["correction"] is not None)
    return {"fichier": fichier, "lignes": len(df), "note": ctx["scores"].get(fichier),
            "mesures_pct": {k: round(100 * v, 1) for k, v in m.items()}, "points_perdus": pertes,
            "cause_principale": max(pertes, key=pertes.get) if any(pertes.values()) else None,
            "problemes_par_type": dict(Counter(i["type"] for i in issues)), "total_problemes": len(issues),
            "corrigeables_en_un_clic": corrigeables, "a_traiter_par_un_humain": len(issues) - corrigeables}


def explain_trust(ctx, sources):
    """Detail du calcul de la confiance : moyenne, plafond (note la plus faible + 15), valeur retenue."""
    sources = [s for s in sources if s in ctx["scores"]]
    if not sources:
        return {"erreur": "aucune source connue"}
    notes = {s: ctx["scores"][s] for s in sources}
    moyenne = sum(notes.values()) / len(notes)
    faible = min(sources, key=lambda s: notes[s])
    plafond = notes[faible] + 15
    t = trust_score(sources, ctx["scores"])
    issues = _problemes(ctx, faible)
    return {"score": t["score"], "couleur": t["couleur"], "notes": notes, "moyenne": round(moyenne, 1),
            "plus_faible": faible, "plafond": round(plafond, 1),
            "retenu_par": "plafond" if plafond < moyenne else "moyenne",
            "problemes_plus_faible": len(issues),
            "corrigeables_plus_faible": sum(1 for i in issues if i["correction"] is not None)}


def rank_suppliers(data, retard_jours):
    """Classe les fournisseurs : arret prevu d'abord, plus gros manque d'abord, puis couverture la plus courte."""
    lignes = []
    for f in sorted(data["fournisseurs"]["fournisseur"].unique()):
        sim = simulate_supplier_delay(data, f, retard_jours)
        fiab = data["fournisseurs"][data["fournisseurs"]["fournisseur"] == f]["fiabilite_pct"].mean()
        lignes.append({"fournisseur": f, "ligne": sim["ligne"], "matiere": sim["matiere"],
                       "couverture_jours": sim["couverture_jours"], "arret_jour": sim["arret_jour"],
                       "manque": sim["manque"], "commandes_menacees": len(sim["commandes"]),
                       "fiabilite_moyenne_pct": round(float(fiab))})
    lignes.sort(key=lambda r: (r["arret_jour"] is None, -r["manque"],
                               r["couverture_jours"] if r["couverture_jours"] is not None else 999))
    return {"retard_jours": retard_jours, "classement": lignes}


def _couvertures(data):
    """Couverture en jours de chaque couple (ligne, matiere), de la plus courte a la plus longue."""
    out = []
    for _, r in data["production"].iterrows():
        c = stock_coverage(data, r["ligne"], r["matiere"])
        out.append({"ligne": r["ligne"], "matiere": r["matiere"], "jours": round(c["jours"], 1), "stock": c["stock"],
                    "conso_par_jour": c["conso_par_jour"]})
    return sorted(out, key=lambda c: c["jours"])


def get_briefing(ctx):
    sc = PARAMS["scenario"]
    data, scores = ctx["data"], ctx["scores"]
    faible = min(scores, key=scores.get)
    sim = simulate_supplier_delay(data, *scenario_par_defaut(data))
    return {"note_globale": quality.global_score(scores), "fichier_le_plus_faible": faible,
            "note_la_plus_faible": scores[faible], "couvertures": _couvertures(data)[:3],
            "scenario": {"fournisseur": scenario_par_defaut(data)[0], "retard_jours": scenario_par_defaut(data)[1],
                         "ligne": sim["ligne"], "arret_jour": sim["arret_jour"], "manque": sim["manque"],
                         "commandes": sim["commandes"], "clients": sim["clients"]}}


def get_order(data, commande_id=None, client=None):
    cmd = data["commandes"]
    sel = cmd[cmd["commande_id"] == commande_id] if commande_id else cmd[cmd["client"] == client]
    if sel.empty:
        return {"erreur": "commande ou client inconnu"}
    sc = PARAMS["scenario"]
    sim = simulate_supplier_delay(data, *scenario_par_defaut(data))
    return {"scenario": f"{sc['fournisseur_en_retard']}, {sc['retard_jours']} jours de retard",
            "commandes": [{"commande_id": r["commande_id"], "client": r["client"], "produit": r["produit"],
                           "quantite": int(r["quantite"]), "date_livraison": str(r["date_livraison"]),
                           "menacee": r["commande_id"] in sim["commandes"]} for _, r in sel.iterrows()]}


def _executer(nom, args, ctx):
    data = ctx["data"]
    if nom == "get_stock_coverage":
        return get_stock_coverage(data, args["ligne"], args["matiere"])
    if nom == "simulate_supplier_delay":
        return simulate_supplier_delay(data, args["fournisseur"], int(args["retard_jours"]))
    if nom == "list_options":
        sim = simulate_supplier_delay(data, args["fournisseur"], int(args["retard_jours"]))
        ctx["options"] = list_options(data, sim)
        return {"arret_jour": sim["arret_jour"], "manque": sim["manque"], "options": ctx["options"]}
    if nom == "get_trust":
        sources = [s for s in args["sources"] if s in ctx["scores"]]
        return trust_score(sources, ctx["scores"]) if sources else {"erreur": "aucune source connue"}
    if nom == "get_passport":
        return get_passport(data, args["produit"])
    if nom == "explain_trust":
        return explain_trust(ctx, args["sources"])
    if nom == "get_quality_report":
        ctx["fichiers"].add(args["fichier"])
        return get_quality_report(ctx, args["fichier"])
    if nom == "rank_suppliers":
        return rank_suppliers(data, int(args["retard_jours"]))
    if nom == "get_briefing":
        return get_briefing(ctx)
    if nom == "get_order":
        return get_order(data, args.get("commande_id"), args.get("client"))
    if nom == "query_data":
        r = askdata.repondre(args["question"], data, ctx.get("plan"))
        if r is None:
            return {"erreur": "question non comprise : reformuler avec le nom d'une table (commandes, stocks, fournisseurs, production, clients)"}
        ctx["fichiers"] |= set(r["tables"])
        ctx["plan"] = r["plan"]
        return {"reponse": r["texte"], "requete": r["requete"]}
    return {"erreur": f"outil inconnu : {nom}"}


def _json(o):
    return json.dumps(o, ensure_ascii=False, default=lambda x: x.item() if hasattr(x, "item") else str(x))


# ------------------------------------------------------------------ utilitaires de texte
def _norm(s):
    return nlu.normaliser(s)


def _n(x):
    return f"{x:,}".replace(",", " ")


def _d(x):
    """Nombre decimal a la francaise : 93.8 -> « 93,8 », 100.0 -> « 100 »."""
    return f"{x:g}".replace(".", ",")


def _matiere(m):
    return m.replace("concentre", "concentré").replace("_", " ")


def _texte_options(options):
    risque = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}
    return " ".join(f"{o['code']}) {o['libelle']} (surcoût {_d(o['surcout_pct'])} %, risque {risque[o['risque']]}"
                    f"{'' if o['faisable'] else ', impossible'})." for o in options)


def _liste(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


# ------------------------------------------------------------------ moteur hors ligne
class Rep(dict):
    """Reponse du moteur hors ligne : texte, explication (etapes), suggestions, memoire a retenir."""


def _fusion(ent, memoire, cles):
    """Entites de la question, completees par la memoire de la conversation."""
    return {k: ent[k] if k in ent else (memoire or {}).get(k) for k in cles}


def _rep_retard(ctx, e, ent):
    data, sc = ctx["data"], PARAMS["scenario"]
    four = e["fournisseur"] or scenario_par_defaut(data)[0]
    n = int(e["retard_jours"]) if e["retard_jours"] is not None else sc["retard_jours"]
    sim = _executer("simulate_supplier_delay", {"fournisseur": four, "retard_jours": n}, ctx)
    ctx["outils"].append("simulate_supplier_delay")
    mem = {"intention": "retard", "fournisseur": four, "retard_jours": n, "ligne": sim["ligne"], "matiere": sim["matiere"],
           "options": None}
    memes = data["fournisseurs"][(data["fournisseurs"]["matiere"] == sim["matiere"]) & (data["fournisseurs"]["fournisseur"] != four)]["fournisseur"]
    autre = next(iter(sorted(memes.unique())), None) or next((f for f in sorted(data["fournisseurs"]["fournisseur"].unique()) if f != four), None)
    if sim["ligne"] is None:
        return Rep(texte=f"{four} ne fournit aucune matière utilisée par une ligne de production.", memoire=mem,
                   explication=[], suggestions=[f"Et pour {autre} ?"] if autre else [])
    c = sim["couverture_jours"]
    d = next(x for x in sim["details"] if x["ligne"] == sim["ligne"] and x["matiere"] == sim["matiere"])
    expl = [f"Stock de {_matiere(sim['matiere'])} sur la {sim['ligne']} : {_n(d['stock'])} unités (seuls les lots valides comptent, les unités sont converties).",
            f"Couverture = stock ÷ consommation par jour = {_d(c)} jours.",
            f"Retard annoncé : {n} jours, {'plus long' if n > c else 'plus court'} que la couverture."]
    if sim["arret_jour"] is None:
        return Rep(texte=(f"Avec {n} jours de retard chez {four}, aucun arrêt n'est prévu : la {sim['ligne']} a "
                          f"{sim['couverture_jours']:g} jours de stock de {_matiere(sim['matiere'])}, ce qui couvre le retard."),
                   memoire=mem, explication=expl + ["Le stock tient jusqu'à la livraison : pas d'arrêt, pas de manque."],
                   suggestions=[f"Et si c'était {n + 4} jours ?", "Quel fournisseur est le plus risqué ?",
                                "Pourquoi cette confiance ?"])
    r = _executer("list_options", {"fournisseur": four, "retard_jours": n}, ctx)
    ctx["outils"].append("list_options")
    mem["options"] = r["options"]
    ids = ", ".join(sim["commandes"]) or "aucune"
    expl += [f"Arrêt prévu à J+{sim['arret_jour']} (jour où le stock tombe à zéro).",
             f"Manque = (retard − couverture) × consommation = ({n} − {_d(c)}) × {_n(d['conso_par_jour'])} = {_n(sim['manque'])} unités.",
             "Commandes menacées = celles dont la date de livraison tombe après le jour d'arrêt, sur les produits de cette ligne.",
             "Solutions : A = transfert depuis l'entrepôt Nord, B = commande express chez un autre fournisseur, "
             "C = report de production (surcoûts fixés dans config/params.json)."]
    sug = [f"Et si c'était {n + 2} jours ?", "Quelle solution recommandes-tu ?"]
    if autre:
        sug.append(f"Et pour {autre} ?")
    texte = (f"Avec {n} jours de retard chez {four}, la {sim['ligne']} s'arrêterait à J+{sim['arret_jour']} faute de "
             f"{_matiere(sim['matiere'])}. Il manquerait {_n(sim['manque'])} unités. {len(sim['commandes'])} commandes sont "
             f"menacées ({ids}), pour {', '.join(sim['clients'])}. Trois solutions : {_texte_options(r['options'])} "
             "La décision revient au directeur général.")
    return Rep(texte=texte, memoire=mem, explication=expl, suggestions=sug)


def _rep_stock(ctx, e, ent, q):
    data, sc = ctx["data"], PARAMS["scenario"]
    prod = data["production"]
    cles = nlu.extraire(q, data)
    # « quelle matière va manquer en premier ? » : on classe toutes les lignes et matieres
    if "ligne" not in cles and "matiere" not in cles and re.search(r"premier|manquer|epuis|critique|bas\b|court|urgent|finir", q):
        cv = _couvertures(data)
        ctx["outils"].append("get_stock_coverage")
        top = cv[0]
        suite = ", ".join(f"{_matiere(c['matiere'])} ({c['ligne']}) {_d(c['jours'])} j" for c in cv[1:3])
        mem = {"intention": "stock", "ligne": top["ligne"], "matiere": top["matiere"]}
        return Rep(texte=(f"La matière qui s'épuise en premier est le {_matiere(top['matiere'])} de la {top['ligne']} : "
                          f"{_n(top['stock'])} unités en stock, {_n(top['conso_par_jour'])} consommées par jour, soit "
                          f"{_d(top['jours'])} jours de couverture. Ensuite : {suite}."),
                   memoire=mem, explication=["Pour chaque ligne et chaque matière : couverture = stock valide ÷ consommation par jour.",
                                             "On classe de la couverture la plus courte à la plus longue."],
                   suggestions=[f"Que se passe-t-il si Delta a {sc['retard_jours']} jours de retard ?", "Pourquoi cette confiance ?"])
    ligne, matiere = e["ligne"], e["matiere"]
    if "ligne" in ent and "matiere" not in ent and e["matiere"] is not None:  # « et la ligne 1 ? » : la matiere d'avant n'existe peut-etre pas sur cette ligne
        if prod[(prod["ligne"] == ligne) & (prod["matiere"] == matiere)].empty:
            matiere = None
    if ligne is None and matiere:
        ligne = prod[prod["matiere"] == matiere]["ligne"].iloc[0]
    if ligne is None:
        ligne = sc["ligne"]
    if matiere is None:
        cands = prod[prod["ligne"] == ligne]["matiere"]
        matiere = min(cands, key=lambda m: stock_coverage(data, ligne, m)["jours"]) if ligne != sc["ligne"] else sc["matiere"]
    lignes_mat = list(prod[prod["matiere"] == matiere]["ligne"].unique())
    if "ligne" not in ent and "ligne" not in cles and len(lignes_mat) > 1 and "matiere" in cles:  # « stock de sucre » : une matiere utilisee sur plusieurs lignes
        morceaux, expl = [], []
        for lg in lignes_mat:
            rr = _executer("get_stock_coverage", {"ligne": lg, "matiere": matiere}, ctx)
            morceaux.append(f"la {lg} : {_n(rr['stock'])} unités en stock, {_n(rr['conso_par_jour'])} consommées par jour, soit {_d(rr['jours'])} jours")
            expl.append(f"{lg} : {_n(rr['stock'])} ÷ {_n(rr['conso_par_jour'])} par jour = {_d(rr['jours'])} jours.")
        ctx["outils"].append("get_stock_coverage")
        return Rep(texte=f"Couverture de stock de {_matiere(matiere)} : " + " ; ".join(morceaux) + ".",
                   memoire={"intention": "stock", "ligne": lignes_mat[0], "matiere": matiere},
                   explication=["Couverture = stock valide ÷ consommation par jour, ligne par ligne."] + expl,
                   suggestions=["Quelle matière va manquer en premier ?", "Pourquoi cette confiance ?"])
    if prod[(prod["ligne"] == ligne) & (prod["matiere"] == matiere)].empty:  # « sucre » sur une ligne ou il n'est pas utilise
        ligne = prod[prod["matiere"] == matiere]["ligne"].iloc[0]
    r = _executer("get_stock_coverage", {"ligne": ligne, "matiere": matiere}, ctx)
    ctx["outils"].append("get_stock_coverage")
    mem = {"intention": "stock", "ligne": ligne, "matiere": matiere}
    autre_ligne = "Ligne 1" if ligne == "Ligne 2" else "Ligne 2"
    return Rep(texte=(f"La {ligne} a {_n(r['stock'])} unités de {_matiere(matiere)} en stock et en consomme {_n(r['conso_par_jour'])} par jour : "
                      f"cela représente {_d(r['jours'])} jours de couverture."),
               memoire=mem,
               explication=[f"Stock de {_matiere(matiere)} sur la {ligne} : somme des lots valides, unités converties (tonnes → kg, cartons → bouteilles) = {_n(r['stock'])}.",
                            f"Couverture = {_n(r['stock'])} ÷ {_n(r['conso_par_jour'])} par jour = {r['jours']:g} jours."],
               suggestions=[f"Et pour la {autre_ligne} ?", "Quelle matière va manquer en premier ?", "Pourquoi cette confiance ?"])


def _rep_passeport(ctx, e):
    produit = e["produit"] or next(iter(ctx["data"]["production"]["produit"].unique()))
    r = _executer("get_passport", {"produit": produit}, ctx)
    ctx["outils"].append("get_passport")
    parts = []
    for m in r["matieres"]:
        fs = ", ".join(f"{f['nom']} (fiabilité {f['fiabilite_pct']} %, délai {f['delai_jours']} jours)" for f in m["fournisseurs"])
        parts.append(f"{_matiere(m['matiere'])} : {fs} ; {m['nb_lots']} lots en stock sur la ligne")
    autres = [p for p in ctx["data"]["production"]["produit"].unique() if p != produit]
    return Rep(texte=(f"Le {r['produit']} est fabriqué sur la {r['ligne']}. " + " | ".join(parts) +
                      f". Il est commandé par {', '.join(r['clients'])} ({len(r['commandes'])} commandes)."),
               memoire={"intention": "passeport", "produit": produit, "ligne": r["ligne"]},
               explication=["On suit le chemin inverse : produit → ligne → matières consommées → fournisseurs de chaque matière → lots en stock → commandes.",
                            "Fiabilité et délai viennent du fichier fournisseurs ; les lots viennent du fichier stocks."],
               suggestions=[f"Et le {autres[0].split(' 1')[0].lower()} ?"] * bool(autres) +
                           [f"Que se passe-t-il si Delta a {PARAMS['scenario']['retard_jours']} jours de retard ?"])


def _rep_expliquer_confiance(ctx, memoire, ent, q):
    """« Pourquoi cette confiance ? » : le calcul, fichier par fichier."""
    sources = list(ctx.get("sources_precedentes") or [])
    if "fichier" in ent and ent["fichier"] in ctx["scores"]:
        sources = [ent["fichier"]]
    if not sources:
        sources = [s for s in TOUS if s in ctx["scores"]]
    ctx["outils"].append("explain_trust")
    r = _executer("explain_trust", {"sources": sources}, ctx)
    notes = " ; ".join(f"{s} {_d(v)}" for s, v in r["notes"].items())
    seuils = PARAMS["seuils_confiance"]
    retenu = "le plafond" if r["retenu_par"] == "plafond" else "la moyenne"
    texte = (f"La confiance est de {r['score']} % ({r['couleur']}). Elle repose sur les notes de qualité des fichiers utilisés : {notes}. "
             f"La moyenne est {_d(r['moyenne'])}. Le plafond est la note du fichier le plus faible ({r['plus_faible']}, "
             f"{_d(r['notes'][r['plus_faible']])}) + 15, soit {_d(r['plafond'])}. On garde le plus petit des deux : {retenu}.")
    if r["problemes_plus_faible"]:
        texte += (f" Le fichier « {r['plus_faible']} » compte {_n(r['problemes_plus_faible'])} problèmes, dont "
                  f"{_n(r['corrigeables_plus_faible'])} corrigeables en un clic dans la page Données : les valider fait monter la confiance.")
    texte += f" Repères : vert dès {seuils['vert']}, orange de {seuils['orange']} à {seuils['vert'] - 1}, rouge en dessous (« à confirmer »)."
    return Rep(texte=texte, memoire={"intention": "confiance", "fichiers": sources, "confiance_score": r["score"]},
               explication=["confiance = min(moyenne des notes, note la plus faible + 15)",
                            "note d'un fichier = 100 × (0,30 × complétude + 0,30 × unicité + 0,20 × validité + 0,20 × cohérence)"],
               suggestions=[f"Quels sont les problèmes dans les {r['plus_faible']} ?" if r["plus_faible"] != "production" else "Résume la situation",
                            "Résume la situation"])


def _rep_qualite(ctx, e, ent, q, memoire):
    data, scores = ctx["data"], ctx["scores"]
    f = ent.get("fichier")
    if f in ("production", "lignes") or f not in data:
        f = None if f not in data else f
    if f is None and "fichier" in (memoire or {}) and False:
        f = memoire.get("fichier")
    if f is None:  # vue d'ensemble : tous les fichiers
        ordre = sorted(scores, key=scores.get)
        ctx["outils"].append("get_quality_report")
        total = sum(len(_problemes(ctx, x)) for x in data)
        corr = sum(1 for x in data for i in _problemes(ctx, x) if i["correction"] is not None)
        liste = " ; ".join(f"{x} {_d(scores[x])}" for x in ordre)
        faible = ordre[0]
        return Rep(texte=(f"La note globale des données est de {_d(quality.global_score(scores))} sur 100. Fichier par fichier, du plus faible au plus fort : {liste}. "
                          f"{_n(total)} problèmes sont détectés, dont {_n(corr)} corrigeables en un clic dans la page Données ; "
                          f"le plus utile à traiter d'abord est « {faible} »."),
                   memoire={"intention": "qualite", "fichier": faible},
                   explication=["Chaque fichier a une note sur 100 = 0,30 × complétude + 0,30 × unicité + 0,20 × validité + 0,20 × cohérence.",
                                "La note globale est la moyenne des notes des fichiers."],
                   suggestions=[f"Quels sont les problèmes dans les {faible} ?", "Pourquoi cette confiance ?"],
                   fichiers=set())
    ctx["outils"].append("get_quality_report")
    r = _executer("get_quality_report", {"fichier": f}, ctx)
    mes = ", ".join(f"{NOM_MESURE[k].split(' ')[0]} {_d(v)} %" for k, v in r["mesures_pct"].items())
    texte = f"Le fichier « {f} » ({_n(r['lignes'])} lignes) a une note de {_d(r['note'])} sur 100. Mesures : {mes}."
    if r["total_problemes"]:
        types = ", ".join(f"{_n(v)} {k.replace('_', ' ')}" for k, v in sorted(r["problemes_par_type"].items(), key=lambda t: -t[1]))
        texte += (f" Problèmes détectés : {_n(r['total_problemes'])} ({types}). {_n(r['corrigeables_en_un_clic'])} sont corrigeables en un clic dans la page Données ; "
                  f"{_n(r['a_traiter_par_un_humain'])} demandent un humain (par exemple un e-mail à redemander).")
    else:
        texte += " Aucun problème détecté."
    if r["cause_principale"] and r["points_perdus"][r["cause_principale"]] > 0:
        texte += (f" Ce qui coûte le plus de points : la {NOM_MESURE[r['cause_principale']]}, "
                  f"−{_d(r['points_perdus'][r['cause_principale']])} point{'s' if r['points_perdus'][r['cause_principale']] >= 2 else ''}.")
    return Rep(texte=texte, memoire={"intention": "qualite", "fichier": f, "fichiers": [f]},
               explication=["note = 100 × (0,30 × complétude + 0,30 × unicité + 0,20 × validité + 0,20 × cohérence)",
                            "Points perdus par mesure = poids × (1 − mesure) × 100 : "
                            + ", ".join(f"{k} −{_d(v)}" for k, v in r["points_perdus"].items())],
               suggestions=["Pourquoi cette confiance ?", "Résume la situation"], fichiers={f})


def _rep_classement(ctx, e):
    n = int(e["retard_jours"]) if e["retard_jours"] is not None else PARAMS["scenario"]["retard_jours"]
    r = _executer("rank_suppliers", {"retard_jours": n}, ctx)
    ctx["outils"].append("rank_suppliers")
    cl = r["classement"]
    lignes = []
    for i, x in enumerate(cl, 1):
        if x["ligne"] is None:
            lignes.append(f"{i}. {x['fournisseur']} : aucune matière utilisée.")
        elif x["arret_jour"] is None:
            lignes.append(f"{i}. {x['fournisseur']} : pas d'arrêt ({_d(x['couverture_jours'])} jours de stock de {_matiere(x['matiere'])} sur la {x['ligne']}).")
        else:
            lignes.append(f"{i}. {x['fournisseur']} : arrêt à J+{x['arret_jour']} sur la {x['ligne']}, manque {_n(x['manque'])} unités, "
                          f"{x['commandes_menacees']} commandes menacées.")
    top = cl[0]
    return Rep(texte=f"Pour un retard de {n} jours, du plus risqué au moins risqué : " + " ".join(lignes) +
                     " Hypothèse : le même retard chez chacun ; la décision revient au directeur général.",
               memoire={"intention": "classement", "retard_jours": n, "fournisseur": top["fournisseur"]},
               explication=[f"On simule un retard de {n} jours chez chaque fournisseur.",
                            "Tri : arrêt prévu d'abord, puis plus gros manque, puis couverture de stock la plus courte."],
               suggestions=[f"Que se passe-t-il si {top['fournisseur']} a {n} jours de retard ?", "Quelle solution recommandes-tu ?"])


def _rep_reco(ctx, e, memoire):
    sc = PARAMS["scenario"]
    four = e["fournisseur"] or scenario_par_defaut(data)[0]
    n = int(e["retard_jours"]) if e["retard_jours"] is not None else sc["retard_jours"]
    sim = _executer("simulate_supplier_delay", {"fournisseur": four, "retard_jours": n}, ctx)
    ctx["outils"].append("simulate_supplier_delay")
    if sim["arret_jour"] is None:
        return Rep(texte=f"Avec {n} jours de retard chez {four}, aucun arrêt n'est prévu : aucune solution n'est nécessaire.",
                   memoire={"intention": "reco", "fournisseur": four, "retard_jours": n}, explication=[],
                   suggestions=[f"Et si c'était {n + 4} jours ?"])
    r = _executer("list_options", {"fournisseur": four, "retard_jours": n}, ctx)
    ctx["outils"].append("list_options")
    ok = [o for o in r["options"] if o["faisable"]]
    mem = {"intention": "reco", "fournisseur": four, "retard_jours": n, "options": r["options"]}
    if not ok:
        return Rep(texte="Aucune des trois solutions n'est faisable telle quelle : il faut une décision humaine (par exemple renégocier avec le fournisseur).",
                   memoire=mem, explication=[], suggestions=["Pourquoi cette confiance ?"])
    risque = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}
    moins_cher = min(ok, key=lambda o: (o["surcout_pct"], RISQUE_RANG[o["risque"]]))
    plus_sur = min(ok, key=lambda o: (RISQUE_RANG[o["risque"]], o["surcout_pct"]))
    if len(ok) == 1:
        texte = (f"Une seule solution est faisable : {moins_cher['code']} ({moins_cher['libelle']}), surcoût {_d(moins_cher['surcout_pct'])} %, "
                 f"risque {risque[moins_cher['risque']]}.")
    elif moins_cher["code"] == plus_sur["code"]:
        texte = (f"La solution {moins_cher['code']} est à la fois la moins chère (surcoût {_d(moins_cher['surcout_pct'])} %) "
                 f"et la moins risquée (risque {risque[moins_cher['risque']]}) : {moins_cher['libelle']}.")
    else:
        texte = (f"Cela dépend de votre priorité. Pour payer le moins : solution {moins_cher['code']} (surcoût {_d(moins_cher['surcout_pct'])} %, "
                 f"risque {risque[moins_cher['risque']]}) : {moins_cher['libelle']}. Pour prendre le moins de risque : solution {plus_sur['code']} "
                 f"(surcoût {_d(plus_sur['surcout_pct'])} %, risque {risque[plus_sur['risque']]}) : {plus_sur['libelle']}.")
    impossibles = [o["code"] for o in r["options"] if not o["faisable"]]
    if impossibles:
        texte += f" Écartée{'s' if len(impossibles) > 1 else ''} car impossible{'s' if len(impossibles) > 1 else ''} : {_liste(impossibles)}."
    texte += " Je propose, je ne décide pas : le choix revient au directeur général."
    return Rep(texte=texte, memoire=mem,
               explication=["On ne garde que les solutions faisables.", "Moins chère = plus petit surcoût ; moins risquée = niveau de risque le plus bas (faible < moyen < élevé).",
                            "Surcoûts et risques viennent de list_options (config/params.json) : je ne les invente pas."],
               suggestions=["Détaille la solution " + (moins_cher["code"]), f"Et si c'était {n + 2} jours ?"], options=r["options"])


def _rep_option(ctx, e, ent, memoire):
    """« Détaille la solution B » : explique pourquoi une option est faisable ou non."""
    code = ent["option"]
    options = (memoire or {}).get("options")
    four, n = e["fournisseur"] or scenario_par_defaut(ctx["data"])[0], e["retard_jours"] or PARAMS["scenario"]["retard_jours"]
    sim = _executer("simulate_supplier_delay", {"fournisseur": four, "retard_jours": int(n)}, ctx)
    ctx["outils"].append("simulate_supplier_delay")
    if sim["arret_jour"] is None:
        return Rep(texte=f"Avec {n} jours de retard chez {four}, aucun arrêt n'est prévu : il n'y a pas de solution à détailler.",
                   memoire={"intention": "reco", "fournisseur": four, "retard_jours": n}, explication=[], suggestions=[])
    opts = _executer("list_options", {"fournisseur": four, "retard_jours": int(n)}, ctx)["options"]
    ctx["outils"].append("list_options")
    o = next((x for x in opts if x["code"] == code), None)
    if o is None:
        return Rep(texte="Les solutions sont A, B et C.", memoire=memoire or {}, explication=[], suggestions=[])
    risque = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}[o["risque"]]
    m, manque = sim["matiere"], sim["manque"]
    if code == "A":
        nord = round(_stock(ctx["data"], "Entrepot Nord", m))
        pourquoi = (f"L'entrepôt Nord a {_n(nord)} unités et il en faut {_n(manque)} : " + ("c'est suffisant." if nord >= manque else "c'est insuffisant."))
    elif code == "B":
        pourquoi = "Elle est faisable si la livraison express arrive avant le jour d'arrêt (J+%d)." % sim["arret_jour"] if o["faisable"] else \
            "Elle n'est pas faisable : la livraison arriverait après le jour d'arrêt, ou aucun autre fournisseur n'existe."
    else:
        pourquoi = "Toujours possible, mais c'est la plus risquée : on décale des livraisons et on peut perdre des clients."
    return Rep(texte=f"Solution {code} : {o['libelle']}. Surcoût {_d(o['surcout_pct'])} %, risque {risque}, {'faisable' if o['faisable'] else 'impossible'}. {pourquoi} La décision revient au directeur général.",
               memoire={"intention": "reco", "fournisseur": four, "retard_jours": int(n), "options": opts},
               explication=[pourquoi], suggestions=["Quelle solution recommandes-tu ?", "Pourquoi cette confiance ?"], options=opts)


def _rep_briefing(ctx):
    r = _executer("get_briefing", {}, ctx)
    ctx["outils"].append("get_briefing")
    cv = ", ".join(f"{_matiere(c['matiere'])} ({c['ligne']}) {_d(c['jours'])} j" for c in r["couvertures"])
    s = r["scenario"]
    risque = (f"Scénario en cours ({s['fournisseur']}, {s['retard_jours']} jours de retard) : arrêt de la {s['ligne']} à J+{s['arret_jour']}, "
              f"manque de {_n(s['manque'])} unités, {len(s['commandes'])} commandes menacées ({', '.join(s['commandes'])})."
              if s["arret_jour"] is not None else f"Scénario en cours ({s['fournisseur']}, {s['retard_jours']} jours de retard) : aucun arrêt prévu.")
    return Rep(texte=(f"Bilan : la note globale des données est de {_d(r['note_globale'])} sur 100 (le fichier le plus faible est « {r['fichier_le_plus_faible']} », "
                      f"{_d(r['note_la_plus_faible'])}). Les stocks les plus courts : {cv}. {risque} Les trois solutions sont dans la page Chaîne."),
               memoire={"intention": "resume", "fournisseur": s["fournisseur"], "retard_jours": s["retard_jours"]},
               explication=["Note globale = moyenne des notes des fichiers.", "Stocks les plus courts = les 3 plus petites couvertures (stock ÷ consommation par jour).",
                            "Scénario = celui de config/params.json."],
               suggestions=["Quelle solution recommandes-tu ?", "Quel fournisseur est le plus risqué ?", "Pourquoi cette confiance ?"])


def _rep_commande(ctx, e, ent):
    r = _executer("get_order", {"commande_id": ent.get("commande"), "client": ent.get("client")}, ctx)
    ctx["outils"].append("get_order")
    if "erreur" in r:
        return None
    lignes = [f"{c['commande_id']} : {c['client']}, {_n(c['quantite'])} × {c['produit']}, livraison le {c['date_livraison']}"
              f"{' — MENACÉE' if c['menacee'] else ''}" for c in r["commandes"]]
    menacees = sum(c["menacee"] for c in r["commandes"])
    texte = (" ; ".join(lignes) + f". Selon le scénario en cours ({r['scenario']}), " +
             (f"{menacees} commande{'s' if menacees > 1 else ''} sur {len(r['commandes'])} {'sont' if menacees > 1 else 'est'} menacée{'s' if menacees > 1 else ''}." if menacees else "aucune n'est menacée."))
    return Rep(texte=texte, memoire={"intention": "commande"},
               explication=["Une commande est menacée si son produit sort d'une ligne qui s'arrête et si sa date de livraison tombe après le jour d'arrêt."],
               suggestions=[f"Que se passe-t-il si Delta a {PARAMS['scenario']['retard_jours']} jours de retard ?"])


def _rep_comptage(ctx, q):
    data = ctx["data"]
    cible = nlu.compte_cible(q)
    if cible is None:
        return None
    ctx["fichiers"].clear()
    if cible == "clients":
        n, ctx["fichiers"] = len(data["clients"]), {"clients"}
        texte = f"Il y a {_n(n)} lignes dans le fichier clients."
    elif cible == "commandes":
        n = len(data["commandes"]); ctx["fichiers"] = {"commandes"}
        texte = f"Il y a {n} commandes en cours."
    elif cible == "lots":
        mat = nlu.extraire(q, data).get("matiere")
        st = data["stocks"] if mat is None else data["stocks"][data["stocks"]["matiere"] == mat]
        ctx["fichiers"] = {"stocks"}
        texte = f"Il y a {_n(len(st))} lots en stock" + (f" de {_matiere(mat)}" if mat else "") + "."
    elif cible == "fournisseurs":
        ctx["fichiers"] = {"fournisseurs"}
        texte = f"Il y a {data['fournisseurs']['fournisseur'].nunique()} fournisseurs : {_liste(sorted(data['fournisseurs']['fournisseur'].unique()))}."
    elif cible in ("produits", "lignes"):
        ctx["fichiers"] = {"production"}
        texte = (f"Il y a {data['production']['produit'].nunique()} produits sur {data['production']['ligne'].nunique()} lignes de production : "
                 f"{_liste(sorted(data['production']['produit'].unique()))}.")
    else:  # doublons, problemes
        fich = {f: _problemes(ctx, f) for f in data}
        if cible == "doublons":
            par = {f: sum(1 for i in v if i["type"] == "doublon") for f, v in fich.items()}
            texte = "Doublons à supprimer : " + ", ".join(f"{f} {_n(v)}" for f, v in par.items() if v) + "."
        else:
            par = {f: len(v) for f, v in fich.items()}
            texte = f"{_n(sum(par.values()))} problèmes détectés : " + ", ".join(f"{f} {_n(v)}" for f, v in par.items() if v) + "."
    return Rep(texte=texte, memoire={"intention": "comptage"}, explication=["Comptage direct dans les données (aucune estimation)."],
               suggestions=["Résume la situation"])


def _rep_aide(q):
    if any(m in q.split() for m in ("merci", "super", "parfait")):
        return Rep(texte="Avec plaisir ! Je reste là si vous voulez simuler un autre retard ou comprendre une note.", memoire={}, explication=[], suggestions=["Résume la situation"])
    if any(m in q for m in ("bonjour", "salut", "bonsoir", "hello")):
        debut = "Bonjour ! "
    else:
        debut = ""
    return Rep(texte=debut + "Je suis le copilote de Baobab Sève. Je sais : simuler le retard d'un fournisseur et proposer trois solutions, "
                           "dire combien de jours de stock il reste, classer les fournisseurs par risque, résumer la situation, détailler une commande, "
                           "montrer d'où vient un produit, et expliquer la note de qualité et la confiance de chaque réponse. "
                           "Je me souviens de la conversation : vous pouvez écrire « Et pour Sigma ? » ou « Et si c'était 7 jours ? ». "
                           "Je ne donne jamais de salaires ni de données personnelles.",
               memoire={}, explication=[], suggestions=["Résume la situation", "Quel fournisseur est le plus risqué ?",
                                                        f"Que se passe-t-il si Delta a {PARAMS['scenario']['retard_jours']} jours de retard ?"])


SPECIALISE = {
    "retard": r"retard|arret|rupture|panne|penurie|solution|que faire|que se passe|se passerait|decal|perturb|alternative|plan b|bloqu",
    "reco": r"recommand|conseill|quelle solution|quelle option|laquelle|que choisir|a choisir|preferable|privilegi",
    "classement": r"risque|risqu|dangereu|fragil|vulnerab|classement(?!.*(produit|client|commande|lot\\b|lots|ville|matiere|quantite|ligne))",
    "stock": r"\bjours?\b|couverture|autonomie|epuis|manquer|premier|tient|tiendra|finir",
    "passeport": r"passeport|tracab|provenance|origine|\bvient\b|viennent|composition|ingredient",
    "qualite": r"probleme|doublon|\bnotes?\b|score|qualite|corrig|ameliore|erreur|anomalie|propre|nettoy|mauvais|\bsain",
}


def _est_specialise(q, intention):
    """Vrai si la question releve d'une fonction dediee (simulation, confiance, bilan...) plutot que des questions libres."""
    if intention in ("confiance", "resume", "aide", "expliquer"):
        return True
    return bool(intention in SPECIALISE and re.search(SPECIALISE[intention], q))


def _rep_donnees(ctx, question, memoire):
    """Questions libres sur les donnees : plan -> SQL en lecture seule -> reponse redigee (core/askdata.py)."""
    r = askdata.repondre(question, ctx["data"], memoire.get("plan"))
    if r is None:
        return None
    ctx["outils"].append("query_data")
    ctx["plan"] = r["plan"]
    sug = askdata.suggestions(r["plan"], ctx["data"], question) if not r.get("impossible") else []
    return Rep(texte=r["texte"], memoire={"intention": "donnees", "plan": r["plan"]}, explication=r["explication"],
               suggestions=sug, fichiers=set(r["tables"]), tableau=r["tableau"], requete=r["requete"])


def _hors_ligne(question, ctx, memoire):
    """Comprend la question, appelle les fonctions de calcul et retourne une Rep (ou None si incomprise)."""
    data, q = ctx["data"], _norm(question)
    ent = nlu.extraire(q, data)
    intention, suivi, expliquer = nlu.choisir_intention(q, ent, memoire)
    memoire = memoire or {}
    ctx["intention"] = intention

    # suite d'une question « dediee » (« Et pour la Ligne 1 ? » apres une couverture de stock) : on reste sur la meme fonction
    suite_dediee = (max(nlu.intentions(q).values(), default=0) == 0 and intention == memoire.get("intention")
                    and intention in ("stock", "retard", "classement", "passeport", "reco", "qualite"))
    # 1) question libre sur les donnees (sauf si une fonction dediee est visee)
    if not _est_specialise(q, intention) and not suite_dediee and not (expliquer and intention == "expliquer"):
        if nlu.compte_cible(q) not in ("doublons", "problemes"):
            rep = _rep_donnees(ctx, question, memoire)
            if rep is not None:
                ctx["intention"] = "donnees"
                return rep

    # « pourquoi cette confiance ? » ou « pourquoi 98 ? » : on explique le calcul de la derniere confiance
    conf_ref = memoire.get("confiance_score")
    if intention == "confiance" or (expliquer and conf_ref is not None and ent.get("nombre") == conf_ref):
        return _rep_expliquer_confiance(ctx, memoire, ent, q)

    if intention == "expliquer":
        etapes = memoire.get("explication")
        if not etapes:
            return Rep(texte="Je n'ai encore rien calculé dans cette conversation : posez-moi d'abord une question, puis demandez-moi « comment as-tu obtenu ce résultat ? ».",
                       memoire=memoire, explication=[], suggestions=["Résume la situation"])
        return Rep(texte="Voici comment j'ai obtenu ce résultat : " + " ".join(f"({i}) {s}" for i, s in enumerate(etapes, 1)),
                   memoire=memoire, explication=etapes, suggestions=["Pourquoi cette confiance ?"], garder_sources=True)

    cles = ["fournisseur", "retard_jours", "ligne", "matiere", "produit"]
    e = _fusion(ent, memoire, cles)
    if intention == "retard":
        if ent.get("option"):
            return _rep_option(ctx, e, ent, memoire)
        return _rep_retard(ctx, e, ent)
    if intention == "reco":
        if ent.get("option"):
            return _rep_option(ctx, e, ent, memoire)
        return _rep_reco(ctx, e, memoire)
    if intention == "stock":
        return _rep_stock(ctx, e, ent, q)
    if intention == "passeport":
        # « mangue » seul dans une question de provenance designe le produit, pas la matiere
        if "produit" not in ent and ent.get("matiere") in ("concentre_mangue", "concentre_orange"):
            mot = "mangue" if ent["matiere"] == "concentre_mangue" else "orange"
            e["produit"] = next((p for p in data["production"]["produit"].unique() if mot in _norm(p)), e["produit"])
        return _rep_passeport(ctx, e)
    if intention == "classement":
        return _rep_classement(ctx, e)
    if intention == "qualite":
        return _rep_qualite(ctx, e, ent, q, memoire)
    if intention == "resume":
        return _rep_briefing(ctx)
    if intention == "commande":
        return _rep_commande(ctx, e, ent)
    if intention == "comptage":
        return _rep_comptage(ctx, q)
    if intention == "aide":
        return _rep_aide(q)
    return None


# ------------------------------------------------------------------ boucle avec le modele de langage
def _llm(question, role, ctx, client, historique=None):
    msgs = [dict(m) for m in (historique or [])][-8:]
    while msgs and msgs[0].get("role") != "user":  # l'API exige de commencer par un message de l'utilisateur
        msgs.pop(0)
    msgs.append({"role": "user", "content": f"[Rôle de l'utilisateur : {role}] {question}"})
    for _ in range(5):
        rep = client.messages.create(model=MODELE, max_tokens=1024, system=SYSTEME, tools=SCHEMAS, messages=msgs)
        if rep.stop_reason != "tool_use":
            return "".join(b.text for b in rep.content if b.type == "text").strip()
        msgs.append({"role": "assistant", "content": rep.content})
        resultats = []
        for b in rep.content:
            if b.type == "tool_use":
                ctx["outils"].append(b.name)
                resultats.append({"type": "tool_result", "tool_use_id": b.id,
                                  "content": _json(_executer(b.name, dict(b.input), ctx))})
        msgs.append({"role": "user", "content": resultats})
    raise RuntimeError("trop d'appels d'outils")


def _client():
    """Client du modele de langage, ou None si la cle ou la bibliotheque manque."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        return anthropic.Anthropic(timeout=20.0, max_retries=1)
    except ImportError:
        return None


# ------------------------------------------------------------------ garde-fous (droits)
MOTS_RH = ("salaire", "salaires", "remuneration", "paie", "naissance", "employe", "employes", "salarie", "salaries",
           "effectif", "effectifs", "personnel", "rh")
MOTS_CONTACT = ("telephone", "tel", "mail", "email", "e-mail", "adresse", "coordonnees", "portable", "whatsapp")


def _garde_fou(q, role):
    """Retourne le texte de refus si la question vise des donnees personnelles, sinon None."""
    mots = [m[:-1] if m.endswith("s") and m[:-1] in MOTS_CONTACT + ("noms",) else m for m in q.split()]
    if any(m in mots for m in MOTS_RH) or any(nlu.mot_proche(m, "salaire") for m in mots):
        if role != "Directeur général":
            return "Vous n'avez pas accès à cette information.", True
        return "Je ne sais pas : les données des salariés ne sont pas accessibles au copilote dans ce prototype.", False
    agregat = bool(re.search(r"\b(combien|nombre|pourcentage|proportion|part|sans|manquants?|manque|n ont pas|pas de|pas d)\b", q)) and \
        not re.search(r"\b(donne|donnez|montre|affiche|quel est|quels sont|liste)\b.*\b(telephone|tel|mail|email|adresse|coordonnees|portable)s?\b(?!.*\b(sans|manquant))", q)
    if (any(m in mots for m in MOTS_CONTACT) and any(m in mots for m in ("client", "clients", "fournisseur", "contact")) and not agregat) or \
            (any(m in mots for m in ("nom", "noms", "prenom", "prenoms")) and any(m in mots for m in ("client", "clients"))):
        if role != "Directeur général":
            return "Vous n'avez pas accès à cette information.", True
        return ("Je ne communique pas de données personnelles dans la conversation (noms, téléphones, e-mails). "
                "Elles se consultent dans la page Données, sous votre responsabilité."), False
    return None


# ------------------------------------------------------------------ point d'entree
def ask(question, role, data, scores, mode="auto", client=None, journaliser=True, log_fn=None,
        memoire=None, problemes=None, historique=None):
    """mode : « auto » (IA si possible, sinon hors ligne), « llm » (IA seulement), « hors_ligne ».
    memoire : celle renvoyee par la question precedente (pour « Et pour Sigma ? »).
    problemes : problemes deja detectes par l'application (evite de les recalculer).
    historique : messages precedents [{"role", "content"}] pour le modele de langage."""
    memoire = dict(memoire or {})
    ctx = {"data": data, "scores": scores, "outils": [], "options": None, "fichiers": set(), "problemes": problemes,
           "sources_precedentes": memoire.get("sources"), "plan": memoire.get("plan")}
    q = _norm(question)
    journal = log_fn or rbac.log_action  # dans l'application, le journal est celui de la base du visiteur
    if journaliser:
        journal(role, "question", question[:120])

    def reponse(texte, mode_, rep=None, forcer_sources=None):
        sources = set(forcer_sources or ())
        for o in ctx["outils"]:
            sources |= FICHIERS_PAR_OUTIL.get(o, set())
        sources |= ctx["fichiers"]
        sources = sorted(s for s in sources if s in scores)
        rep = rep or {}
        mem = dict(memoire)
        mem.update({k: v for k, v in (rep.get("memoire") or {}).items()})
        if rep.get("memoire") is not None and rep.get("memoire") != {} and not rep.get("garder_sources"):
            mem["explication"] = rep.get("explication") or []
        if sources:
            mem["sources"] = sources
        conf = trust_score(sources, scores) if sources else None
        if conf:
            mem["confiance_score"] = conf["score"]
        return {"texte": texte, "sources": sources, "confiance": conf, "options": rep.get("options", ctx["options"]),
                "outils": list(ctx["outils"]), "mode": mode_, "memoire": mem,
                "suggestions": list(rep.get("suggestions") or []), "explication": list(rep.get("explication") or []),
                "intention": ctx.get("intention"), "tableau": rep.get("tableau"), "requete": rep.get("requete")}

    refus = _garde_fou(q, role)
    if refus:
        texte, acces = refus
        if acces and journaliser:
            journal(role, "acces_refuse", question[:120])
        return reponse(texte, "garde-fou")

    if mode != "hors_ligne":
        client = client or _client()
        if client is not None:
            try:
                return reponse(_llm(question, role, ctx, client, historique), "llm")
            except Exception:  # service indisponible, pas d'Internet, delai depasse...
                ctx["outils"].clear()
                ctx["options"] = None
                ctx["fichiers"].clear()
        if mode == "llm":
            return reponse("Le modèle de langage n'est pas disponible pour le moment.", "indisponible")
    rep = _hors_ligne(question, ctx, memoire)
    if rep is not None and rep.get("garder_sources"):
        ctx["fichiers"] |= set(memoire.get("sources") or [])
    if rep is None:
        return reponse("Je ne sais pas : ce n'est pas dans mes données. Essaie par exemple : « Que se passe-t-il si Delta a 5 jours "
                       "de retard ? », « Combien de jours de stock reste-t-il à la Ligne 2 ? » ou « D'où vient le nectar de mangue ? ».",
                       "hors_ligne", {"suggestions": ["Résume la situation", "Quel fournisseur est le plus risqué ?",
                                                      "Que se passe-t-il si Delta a 5 jours de retard ?"]})
    if rep.get("fichiers") is not None:
        ctx["fichiers"] = set(rep["fichiers"]) | ctx["fichiers"]
    return reponse(rep["texte"], "hors_ligne", rep)
