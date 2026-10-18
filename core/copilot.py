"""Copilote : un modele de langage qui APPELLE des fonctions (il ne calcule jamais), avec un moteur de
secours hors ligne qui reutilise exactement les memes fonctions.

ask(question, role, data, scores) retourne :
  {"texte", "sources" (fichiers utilises), "confiance" ({score, couleur, a_confirmer, plus_faible} ou None),
   "options" (liste A/B/C ou None), "outils" (fonctions appelees), "mode" ("llm" ou "hors_ligne")}
Si la cle d'API manque, si Internet est coupe ou si le service est en panne, on bascule seul sur le mode hors ligne.
"""
import json
import os
import re
import unicodedata

from core import rbac
from core.loader import PARAMS, ROOT
from core.simulate import list_options, simulate_supplier_delay, stock_coverage
from core.trust import trust_score

try:  # la cle se lit dans le fichier .env (jamais publie sur GitHub)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

MODELE = os.getenv("BAOBAB_MODELE", "claude-sonnet-5-5")
OUTILS = ["get_stock_coverage", "simulate_supplier_delay", "list_options", "get_trust", "get_passport"]
FICHIERS_PAR_OUTIL = {
    "get_stock_coverage": {"stocks", "production"},
    "simulate_supplier_delay": {"stocks", "production", "fournisseurs", "commandes"},
    "list_options": {"stocks", "production", "fournisseurs", "commandes"},
    "get_passport": {"stocks", "production", "fournisseurs", "commandes"},
    "get_trust": set(),
}

SYSTEME = """Tu es le copilote de Baobab Sève, une plateforme qui aide une usine de jus de fruits (Délice SA) à fiabiliser \
ses données et à anticiper les ruptures de sa chaîne de production.
Règles :
- Réponds en français simple, pour quelqu'un qui n'est pas spécialiste. Au plus 6 phrases.
- Tu ne calcules JAMAIS toi-même : pour tout chiffre, appelle un outil et n'utilise que ce qu'il renvoie.
- Si aucun outil ne permet de répondre, dis « Je ne sais pas : ce n'est pas dans mes données » et n'invente rien.
- Quand un arrêt de production est prévu, présente les trois solutions A, B et C avec leur surcoût et leur risque.
- La décision finale revient toujours à un humain : tu proposes, tu ne décides pas.
- Ne donne jamais de salaires ni d'informations personnelles : tu n'y as pas accès.
- Ne parle pas du score de confiance : l'application l'affiche elle-même."""

SCHEMAS = [
    {"name": "get_stock_coverage",
     "description": "Jours de stock restants pour une matière sur une ligne de production.",
     "input_schema": {"type": "object", "properties": {
         "ligne": {"type": "string", "description": "Ligne 1 ou Ligne 2"},
         "matiere": {"type": "string", "description": "concentre_mangue, concentre_orange, sucre ou bouteilles"}},
         "required": ["ligne", "matiere"]}},
    {"name": "simulate_supplier_delay",
     "description": "Simule le retard d'un fournisseur : jour d'arrêt, manque, commandes et clients touchés.",
     "input_schema": {"type": "object", "properties": {
         "fournisseur": {"type": "string", "description": "Alpha, Delta ou Sigma"},
         "retard_jours": {"type": "integer", "description": "retard annoncé en jours"}},
         "required": ["fournisseur", "retard_jours"]}},
    {"name": "list_options",
     "description": "Les trois solutions chiffrées (A, B, C) si le retard d'un fournisseur provoque un arrêt.",
     "input_schema": {"type": "object", "properties": {
         "fournisseur": {"type": "string"}, "retard_jours": {"type": "integer"}},
         "required": ["fournisseur", "retard_jours"]}},
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
    return {"erreur": f"outil inconnu : {nom}"}


def _json(o):
    return json.dumps(o, ensure_ascii=False, default=lambda x: x.item() if hasattr(x, "item") else str(x))


# ------------------------------------------------------------------ utilitaires de texte
def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _n(x):
    return f"{x:,}".replace(",", " ")


def _matiere(m):
    return m.replace("concentre", "concentré").replace("_", " ")


def _texte_options(options):
    risque = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}
    return " ".join(f"{o['code']}) {o['libelle']} (surcoût {o['surcout_pct']:g} %, risque {risque[o['risque']]}"
                    f"{'' if o['faisable'] else ', impossible'})." for o in options)


# ------------------------------------------------------------------ moteur hors ligne
def _hors_ligne(question, ctx):
    data, q = ctx["data"], _norm(question)
    produits = list(data["production"]["produit"].unique())
    fournisseurs = list(data["fournisseurs"]["fournisseur"].unique())
    sc = PARAMS["scenario"]

    produit = next((p for p in produits if any(mot in q for mot in _norm(p).split() if len(mot) > 4 and mot not in ("nectar",))), None)
    if any(mot in q for mot in ("passeport", "tracabilite", "provenance", "d'ou vient", "d ou vient", "origine", "composition")) and produit:
        r = _executer("get_passport", {"produit": produit}, ctx)
        ctx["outils"].append("get_passport")
        parts = []
        for m in r["matieres"]:
            fs = ", ".join(f"{f['nom']} (fiabilité {f['fiabilite_pct']} %, délai {f['delai_jours']} jours)" for f in m["fournisseurs"])
            parts.append(f"{_matiere(m['matiere'])} : {fs} ; {m['nb_lots']} lots en stock sur la ligne")
        return (f"Le {r['produit']} est fabriqué sur la {r['ligne']}. " + " | ".join(parts) +
                f". Il est commandé par {', '.join(r['clients'])} ({len(r['commandes'])} commandes).")

    four = next((f for f in fournisseurs if _norm(f) in q), None)
    jours = re.search(r"(\d+)\s*(?:jours?|j\b)", q) or re.search(r"retard\D{0,12}(\d+)", q)
    if any(mot in q for mot in ("retard", "arret", "rupture", "que faire", "solution", "option", "livraison")) or four:
        four = four or sc["fournisseur_en_retard"]
        n = int(jours.group(1)) if jours else sc["retard_jours"]
        sim = _executer("simulate_supplier_delay", {"fournisseur": four, "retard_jours": n}, ctx)
        ctx["outils"].append("simulate_supplier_delay")
        if sim["ligne"] is None:
            return f"{four} ne fournit aucune matière utilisée par une ligne de production."
        if sim["arret_jour"] is None:
            return (f"Avec {n} jours de retard chez {four}, aucun arrêt n'est prévu : la {sim['ligne']} a "
                    f"{sim['couverture_jours']:g} jours de stock de {_matiere(sim['matiere'])}, ce qui couvre le retard.")
        r = _executer("list_options", {"fournisseur": four, "retard_jours": n}, ctx)
        ctx["outils"].append("list_options")
        ids = ", ".join(sim["commandes"]) or "aucune"
        return (f"Avec {n} jours de retard chez {four}, la {sim['ligne']} s'arrêterait à J+{sim['arret_jour']} faute de "
                f"{_matiere(sim['matiere'])}. Il manquerait {_n(sim['manque'])} unités. {len(sim['commandes'])} commandes sont "
                f"menacées ({ids}), pour {', '.join(sim['clients'])}. Trois solutions : {_texte_options(r['options'])} "
                "La décision revient au directeur général.")

    if any(mot in q for mot in ("stock", "couverture", "combien de jours", "autonomie")):
        ligne = "Ligne 1" if "ligne 1" in q else "Ligne 2" if "ligne 2" in q else None
        matiere = next((m for m in ("concentre_orange", "concentre_mangue", "sucre", "bouteilles")
                        if _norm(m.split("_")[-1]) in q or (m == "bouteilles" and "bouteille" in q)), None)
        prod = data["production"]
        if ligne is None and matiere:
            ligne = prod[prod["matiere"] == matiere]["ligne"].iloc[0]
        if ligne is None:
            ligne = sc["ligne"]
        if matiere is None:
            cands = prod[prod["ligne"] == ligne]["matiere"]
            matiere = min(cands, key=lambda m: stock_coverage(data, ligne, m)["jours"]) if ligne != sc["ligne"] else sc["matiere"]
        r = _executer("get_stock_coverage", {"ligne": ligne, "matiere": matiere}, ctx)
        ctx["outils"].append("get_stock_coverage")
        return (f"La {ligne} a {_n(r['stock'])} unités de {_matiere(matiere)} en stock et en consomme {_n(r['conso_par_jour'])} par jour : "
                f"cela représente {r['jours']:g} jours de couverture.")
    return None


# ------------------------------------------------------------------ boucle avec le modele de langage
def _llm(question, role, ctx, client):
    msgs = [{"role": "user", "content": f"[Rôle de l'utilisateur : {role}] {question}"}]
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


# ------------------------------------------------------------------ point d'entree
def ask(question, role, data, scores, mode="auto", client=None, journaliser=True):
    """mode : « auto » (IA si possible, sinon hors ligne), « llm » (IA seulement), « hors_ligne »."""
    ctx = {"data": data, "scores": scores, "outils": [], "options": None}
    q = _norm(question)
    if journaliser:
        rbac.log_action(role, "question", question[:120])

    def reponse(texte, mode_):
        sources = sorted(set().union(*(FICHIERS_PAR_OUTIL.get(o, set()) for o in ctx["outils"]))) if ctx["outils"] else []
        sources = [s for s in sources if s in scores]
        return {"texte": texte, "sources": sources, "confiance": trust_score(sources, scores) if sources else None,
                "options": ctx["options"], "outils": list(ctx["outils"]), "mode": mode_}

    if any(mot in q for mot in ("salaire", "remuneration", "paie ", "naissance")):  # droits : jamais de donnees RH
        if role != "Directeur général":
            rbac.log_action(role, "acces_refuse", question[:120]) if journaliser else None
            return reponse("Vous n'avez pas accès à cette information.", "garde-fou")
        return reponse("Je ne sais pas : les données des salariés ne sont pas accessibles au copilote dans ce prototype.", "garde-fou")

    if mode != "hors_ligne":
        client = client or _client()
        if client is not None:
            try:
                return reponse(_llm(question, role, ctx, client), "llm")
            except Exception:  # service indisponible, pas d'Internet, delai depasse...
                ctx["outils"].clear()
                ctx["options"] = None
        if mode == "llm":
            return reponse("Le modèle de langage n'est pas disponible pour le moment.", "indisponible")
    texte = _hors_ligne(question, ctx)
    if texte is None:
        return reponse("Je ne sais pas : ce n'est pas dans mes données. Essaie par exemple : « Que se passe-t-il si Delta a 5 jours "
                       "de retard ? », « Combien de jours de stock reste-t-il à la Ligne 2 ? » ou « D'où vient le nectar de mangue ? ».", "hors_ligne")
    return reponse(texte, "hors_ligne")
