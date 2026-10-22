"""Verifie le moteur de questions libres (core/askdata.py + core/nlu.py), sans Internet ni Streamlit. Usage : python check_askdata.py -> « OK »."""
from core import askdata, nlu
from core.loader import load_all

data = load_all()
con = askdata.construire_base(data)

# 1) confidentialite par construction : pas de salaries, pas de noms/telephones/e-mails dans la copie de travail
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert tables == {"commandes", "stocks", "fournisseurs", "production", "clients"}, tables
cols_clients = {r[1] for r in con.execute("PRAGMA table_info(clients)")}
assert cols_clients == {"client_id", "ville", "email_manquant", "telephone_manquant"}, cols_clients

# 2) questions -> morceaux attendus dans la reponse
CAS = [
    ("Combien de clients ?", ["6 000 clients"]),
    ("combien de clients n'ont pas d'email ?", ["774"]),
    ("Combien de lots de sucre ?", ["86 lots de sucre"]),
    ("cb de lots de sucre", ["86"]),
    ("combien de commandes pour le client B ?", ["3 commandes", "Client B"]),
    ("quantité par client", ["Client B : 5 700", "Client A : 5 400", "Client C : 5 100"]),
    ("top 2 des clients par quantité commandée", ["Client B", "Client A"]),
    ("quelle est la plus grosse commande ?", ["CMD"]),
    ("dernière commande", ["14 novembre 2026", "CMD008"]),
    ("première commande à livrer", ["4 novembre 2026", "CMD003"]),
    ("commandes livrées entre le 5 et le 8 novembre", ["3 commandes", "CMD001", "CMD004", "CMD006"]),
    ("lots reçus avant le 1er octobre", ["35 lots", "avant le 1er octobre 2026"]),
    ("lots sans quantité", ["30 lots", "invalide"]),
    ("quantité de bouteilles en stock", ["138 809", "ignorés"]),
    ("stock total de mangue", ["8 200"]),
    ("combien de lots à Entrepôt Nord ?", ["45 lots"]),
    ("liste des matières", ["4 matières", "sucre", "bouteilles"]),
    ("liste des fournisseurs", ["3 fournisseurs", "Alpha", "Delta", "Sigma"]),
    ("quelle ville est la plus représentée ?", ["Accra", "630"]),
    ("quel est le délai moyen des fournisseurs ?", ["5,5 jours"]),
    ("fournisseur le plus fiable", ["94 %", "Alpha"]),
    ("quelle est la fiabilité la plus faible ?", ["81 %", "Delta"]),
    ("quel fournisseur est le plus rapide ?", ["2 jours", "Sigma"]),
    ("quelle matière est fournie par Alpha ?", ["sucre", "bouteilles"]),
    ("quels produits sont fabriqués sur la ligne 2 ?", ["Nectar de mangue"]),
    ("quelle ligne consomme le plus de sucre ?", ["400", "Ligne 2"]),
    ("compare Sigma et Delta", ["Comparaison", "plus rapide : Sigma"]),
    ("Client A vs Client B", ["Comparaison", "5 400", "5 700"]),
]
for question, attendus in CAS:
    r = askdata.repondre(question, data, con=con)
    assert r is not None, f"question non comprise : {question}"
    for a in attendus:
        assert a in r["texte"], (question, a, r["texte"])
    assert r["requete"].lstrip().upper().startswith("SELECT"), r["requete"]
    assert all(w not in r["requete"].upper() for w in ("INSERT", "UPDATE", "DELETE", "DROP", "ATTACH")), r["requete"]

# 3) hors sujet : le moteur ne repond pas au hasard
for hors in ("Quelle est la capitale de la France ?", "Raconte-moi une blague", "bonjour"):
    assert askdata.repondre(hors, data, con=con) is None, hors

# 4) suites de conversation (« Et pour… ? », « En quantité ? »)
r = askdata.repondre("Combien de commandes pour le client B ?", data, con=con)
r2 = askdata.repondre("Et pour le client A ?", data, r["plan"], con=con)
assert "Client A" in r2["texte"] and "3 commandes" in r2["texte"], r2["texte"]
r3 = askdata.repondre("En quantité ?", data, r2["plan"], con=con)
assert "5 400" in r3["texte"], r3["texte"]

# 5) tolerance aux fautes et aux nombres en lettres
assert nlu.normaliser("Cb de STOK ?") == "combien de stok"
assert nlu.mot_proche("dleta", "delta") and nlu.mot_proche("confience", "confiance")
assert nlu.extraire_jours("retard de cinq jours") == 5 and nlu.extraire_jours("deux semaines") == 14

print(f"OK : {len(CAS)} questions libres répondues depuis les données (lecture seule, sans données personnelles).")
