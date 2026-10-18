"""Verifie le copilote (etape 4D) sans Internet ni cle d'API. Usage : python check_copilot.py -> « OK ».
Le chemin « modele de langage » est teste avec un faux client qui imite les reponses de l'API."""
from types import SimpleNamespace as NS

from core import copilot, quality
from core.loader import load_all
from core.trust import trust_score

data = load_all()
scores = quality.all_scores(data)
DG, STAG = "Directeur général", "Stagiaire logistique"


def ask(q, role=DG, **kw):
    return copilot.ask(q, role, data, scores, journaliser=False, **kw)


# 1) retard Delta (hors ligne)
r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", mode="hors_ligne")
for attendu in ("J+4", "1 200", "CMD004", "CMD007", "Client B", "A)", "B)", "C)", "directeur général"):
    assert attendu in r["texte"], (attendu, r["texte"])
assert r["mode"] == "hors_ligne" and len(r["options"]) == 3
assert r["sources"] == ["commandes", "fournisseurs", "production", "stocks"], r["sources"]
assert r["confiance"] == trust_score(r["sources"], scores)
print("Réponse :", r["texte"][:230], "...\nConfiance :", r["confiance"])

# 2) retard court : pas d'arret, pas d'options
r = ask("Et si Delta a 3 jours de retard ?", mode="hors_ligne")
assert "aucun arrêt" in r["texte"] and r["options"] is None

# 3) couverture de stock et passeport produit
r = ask("Combien de jours de stock reste-t-il à la Ligne 2 ?", mode="hors_ligne")
assert "4 jours" in r["texte"] and "4 800" in r["texte"], r["texte"]
r = ask("D'où vient le nectar de mangue ?", mode="hors_ligne")
assert "Delta" in r["texte"] and "Sigma" in r["texte"] and "Alpha" in r["texte"] and "Ligne 2" in r["texte"], r["texte"]

# 4) droits : jamais de salaires, surtout pour le stagiaire
r = ask("Quel est le salaire du directeur ?", role=STAG)
assert "n'avez pas accès" in r["texte"] and r["sources"] == [] and r["confiance"] is None
r = ask("Quel est le salaire du directeur ?", role=DG)
assert r["texte"].startswith("Je ne sais pas") and r["confiance"] is None

# 5) question hors perimetre : on dit qu'on ne sait pas
r = ask("Quelle est la capitale de la France ?", mode="hors_ligne")
assert r["texte"].startswith("Je ne sais pas") and r["sources"] == []


# 6) boucle avec le modele de langage (faux client)
class FauxClient:
    def __init__(self, scenario):
        self.scenario, self.appels = list(scenario), []
        self.messages = self

    def create(self, **kw):
        self.appels.append(kw)
        return self.scenario.pop(0)


outil = NS(type="tool_use", id="t1", name="simulate_supplier_delay", input={"fournisseur": "Delta", "retard_jours": 5})
final = NS(type="text", text="La Ligne 2 s'arrêterait à J+4 : il manquerait 1 200 unités.")
faux = FauxClient([NS(stop_reason="tool_use", content=[outil]), NS(stop_reason="end_turn", content=[final])])
r = ask("Si Delta a 5 jours de retard, que se passe-t-il ?", mode="llm", client=faux)
assert r["mode"] == "llm" and r["texte"] == final.text and r["outils"] == ["simulate_supplier_delay"]
assert r["confiance"] and r["sources"] == ["commandes", "fournisseurs", "production", "stocks"]
envoye = faux.appels[1]["messages"][-1]["content"][0]            # le resultat de l'outil est renvoye au modele
assert envoye["tool_use_id"] == "t1" and '"arret_jour": 4' in envoye["content"] and '"manque": 1200' in envoye["content"]
assert faux.appels[0]["system"] == copilot.SYSTEME and len(faux.appels[0]["tools"]) == 5
print("Boucle IA (faux client) : outils", r["outils"], "-> réponse reformulée, confiance", r["confiance"]["score"])


# 7) panne du service : retour automatique au mode hors ligne
class Panne:
    messages = NS(create=lambda **kw: (_ for _ in ()).throw(ConnectionError("pas d'Internet")))


r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", client=Panne())
assert r["mode"] == "hors_ligne" and "J+4" in r["texte"]
r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", mode="llm", client=Panne())
assert r["mode"] == "indisponible"

# 8) le schema des outils correspond aux outils executables
assert [s["name"] for s in copilot.SCHEMAS] == copilot.OUTILS
print("\nOK : le copilote répond avec sources et confiance, respecte les droits et fonctionne hors ligne.")
