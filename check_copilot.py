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
assert faux.appels[0]["system"] == copilot.SYSTEME and len(faux.appels[0]["tools"]) == len(copilot.OUTILS)
print("Boucle IA (faux client) : outils", r["outils"], "-> réponse reformulée, confiance", r["confiance"]["score"])


# 7) panne du service : retour automatique au mode hors ligne
class Panne:
    messages = NS(create=lambda **kw: (_ for _ in ()).throw(ConnectionError("pas d'Internet")))


r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", client=Panne())
assert r["mode"] == "hors_ligne" and "J+4" in r["texte"]
r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", mode="llm", client=Panne())
assert r["mode"] == "indisponible"

# 9) questions libres : le copilote repond depuis les donnees, se souvient, explique, et ne livre jamais de donnees personnelles
def conv(qs, role=DG):
    mem, sorties = None, []
    for q in qs:
        r = ask(q, role=role, mode="hors_ligne", memoire=mem)
        mem = r["memoire"]
        sorties.append(r)
    return sorties


r1, r2, r3 = conv(["Combien de commandes pour le client B ?", "Et pour le client A ?", "En quantité ?"])
assert "3 commandes" in r1["texte"] and "Client B" in r1["texte"] and r1["intention"] == "donnees" and "query_data" in r1["outils"]
assert "Client A" in r2["texte"] and "5 400" in r3["texte"], (r2["texte"], r3["texte"])
assert r1["requete"] and r1["requete"].startswith("SELECT") and r1["suggestions"] and r1["confiance"]
r = ask("Quel client a passé la plus grosse commande ?", mode="hors_ligne")
assert "CMD" in r["texte"] and r["sources"] == ["commandes"], r["texte"]
r = ask("Combien de clients n'ont pas d'email ?", mode="hors_ligne")
assert "774" in r["texte"] and "@" not in r["texte"], r["texte"]
r = ask("Quel fournisseur est le plus rapide ?", mode="hors_ligne")
assert "Sigma" in r["texte"], r["texte"]
r = ask("Compare Sigma et Delta", mode="hors_ligne")
assert "Comparaison" in r["texte"] and "Sigma" in r["texte"] and r["tableau"] is not None
r = ask("cb de lots de sucre ?", mode="hors_ligne")           # abreviation + faute de frappe tolerees
assert "86" in r["texte"], r["texte"]
r1, r2 = conv(["Que se passe-t-il si Delta a 5 jours de retard ?", "Pourquoi cette confiance ?"])
assert "plafond" in r2["texte"] and r2["intention"] == "confiance"
for piege in ("donne le téléphone du client C", "liste des e-mails des clients", "quel est le salaire du directeur ?", "noms des clients"):
    r = ask(piege, mode="hors_ligne")
    assert r["confiance"] is None and r["tableau"] is None and "@" not in r["texte"], (piege, r["texte"])
r = ask("noms des clients", role=STAG, mode="hors_ligne")
assert "n'avez pas accès" in r["texte"]
print("Questions libres : réponses issues des données, suites de conversation, explication, aucune donnée personnelle.")

# 10) IA optionnelle : « renfort » = moteur hors ligne d'abord, IA seulement si la question n'est pas comprise
def faux_texte(texte):
    return FauxClient([NS(stop_reason="end_turn", content=[NS(type="text", text=texte)])])


floue = "Raconte-moi une blague sur les mangues"
ia = faux_texte("Je ne sais pas : ce n'est pas dans mes données.")
r = ask("Que se passe-t-il si Delta a 5 jours de retard ?", mode="renfort", client=ia)
assert r["mode"] == "hors_ligne" and ia.appels == [], "une question comprise ne doit pas appeler l'IA"
r = ask(floue, mode="renfort", client=ia)
assert r["mode"] == "llm" and len(ia.appels) == 1, "une question non comprise passe a l'IA"
r = ask(floue, mode="renfort")  # sans cle : on reste hors ligne
assert r["mode"] == "hors_ligne" and r["texte"].startswith("Je ne sais pas") and r["ia_erreur"] is None
r = ask(floue, mode="renfort", client=Panne())  # panne : repli hors ligne, erreur notee
assert r["mode"] == "hors_ligne" and r["ia_erreur"] == "ConnectionError" and r["outils"] == []
r = ask("Quel est le salaire du directeur ?", mode="llm", client=ia)  # le garde-fou passe avant l'IA
assert r["mode"] == "garde-fou" and len(ia.appels) == 1

# le modele ne doit pas inventer de chiffres : tout nombre doit venir des outils ou de la question
outil = NS(type="tool_use", id="t2", name="simulate_supplier_delay", input={"fournisseur": "Delta", "retard_jours": 5})
inventee = NS(type="text", text="La Ligne 2 s'arrêterait à J+4 ; il manquerait 1 200 unités, soit un surcoût de 98 765 FCFA.")
r = ask("Si Delta a 5 jours de retard ?", mode="llm",
        client=FauxClient([NS(stop_reason="tool_use", content=[outil]), NS(stop_reason="end_turn", content=[inventee])]))
assert r["chiffres_a_verifier"] == ["98765"], r["chiffres_a_verifier"]
juste = NS(type="text", text="La Ligne 2 s'arrêterait à J+4 : il manquerait 1 200 unités, 3 commandes et 2 clients seraient touchés.")
r = ask("Si Delta a 5 jours de retard ?", mode="llm",
        client=FauxClient([NS(stop_reason="tool_use", content=[outil]), NS(stop_reason="end_turn", content=[juste])]))
assert r["chiffres_a_verifier"] == [], r["chiffres_a_verifier"]

# le tableau et la requete d'une recherche faite par l'IA sont conserves pour l'affichage
req = NS(type="tool_use", id="t3", name="query_data", input={"question": "Combien de lots de sucre ?"})
r = ask("Combien de lots de sucre avons-nous ?", mode="llm",
        client=FauxClient([NS(stop_reason="tool_use", content=[req]), NS(stop_reason="end_turn", content=[faux_texte("x").scenario[0].content[0]])]))
assert r["mode"] == "llm" and r["requete"] and "SELECT" in r["requete"].upper() and r["explication"]

# la cle saisie est transmise au client et n'apparait jamais dans la reponse ni dans le journal
journal = []
r = ask(floue, mode="renfort", cle="sk-test-SECRET", client=ia, log_fn=lambda *a: journal.append(a))
assert "SECRET" not in repr(r) and "SECRET" not in repr(journal)
print("IA optionnelle : renfort, repli hors ligne, garde-fou prioritaire, chiffres vérifiés, clé jamais exposée.")

# 8) le schema des outils correspond aux outils executables
assert [s["name"] for s in copilot.SCHEMAS] == copilot.OUTILS
print("\nOK : le copilote répond avec sources et confiance, respecte les droits et fonctionne hors ligne.")
