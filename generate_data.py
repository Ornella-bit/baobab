"""Genere les 7 jeux de donnees FICTIFS de « Delice SA » (usine de jus de fruits).

Usage :  python generate_data.py
Les fichiers sont ecrits dans data/. Les valeurs du scenario de demo
(Ligne 2 : 4 800 unites, 1 200 par jour, retard Delta de 5 jours) viennent de
config/params.json. Des defauts realistes sont places volontairement pour que
DataCompass ait quelque chose a reperer. La « verite terrain » (nombre exact de
defauts) est ecrite dans data/_verite_terrain.json pour pouvoir tester le code.
"""
import json
import random
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent
DATA = ROOT / "data"
P = json.loads((ROOT / "config" / "params.json").read_text(encoding="utf-8"))
SC = P["scenario"]
random.seed(P["seed"])
J0 = date.fromisoformat(P["date_reference"])

PRENOMS = ["Jean", "Marie", "Koffi", "Aminata", "Yao", "Fatou", "Kouadio", "Awa", "Ibrahim",
           "Mariam", "Serge", "Aïcha", "Moussa", "Adjoua", "Franck", "Nadia", "Cédric", "Sali",
           "Patrice", "Rokia", "Arnaud", "Khadija", "Landry", "Esther", "Boubacar", "Grâce"]
NOMS = ["Kouassi", "Traoré", "Koné", "Diallo", "N'Guessan", "Ouattara", "Bamba", "Coulibaly",
        "Yao", "Konan", "Touré", "Sylla", "Camara", "Fofana", "Aka", "Soro", "Dosso", "Gnagne",
        "Tano", "Zadi", "Bakayoko", "Diomandé", "Kouamé", "Ballo", "Cissé", "Sanogo"]
VILLES = ["Abidjan", "Bouaké", "Yamoussoukro", "San-Pédro", "Korhogo", "Daloa", "Man", "Dakar", "Douala", "Accra"]
POSTES = ["Opérateur de ligne", "Technicien maintenance", "Magasinier", "Comptable", "Acheteur",
          "Responsable qualité", "Logisticien", "Chauffeur", "Commercial", "Assistant RH"]
DOMAINES = ["gmail.com", "yahoo.fr", "outlook.com", "delice-sa.ci"]


def sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def telephone(propre=True):
    base = "".join(random.choice("0123456789") for _ in range(8))
    n = random.choice(["01", "05", "07"]) + base
    if propre:
        return f"+225 {n[:2]} {n[2:4]} {n[4:6]} {n[6:8]} {n[8:10]}"
    return random.choice([n, n[:5] + " " + n[5:], "225" + n, n[:-2], "(+225) " + n, n + "x"])


def email(prenom, nom):
    return sans_accent(f"{prenom}.{nom}".lower().replace("'", "").replace(" ", "")) + "@" + random.choice(DOMAINES)


def bruit_nom(prenom, nom):
    """Variante realiste d'un meme nom (pour fabriquer des doublons)."""
    choix = random.choice(["maj", "init", "accent", "espace", "inverse"])
    if choix == "maj":
        return f"{prenom.upper()} {nom.upper()}"
    if choix == "init":
        return f"{prenom[0]}. {nom}"
    if choix == "accent":
        return f"{sans_accent(prenom)} {sans_accent(nom)}"
    if choix == "espace":
        return f"{prenom}  {nom} "
    return f"{nom} {prenom}"


verite = {}

# 1) employes.xlsx : 300 salaries, donnees personnelles et salaires ------------------------
emp = []
for i in range(300):
    pr, no = random.choice(PRENOMS), random.choice(NOMS)
    emp.append({"id": f"E{i+1:04d}", "nom": f"{pr} {no}", "poste": random.choice(POSTES),
                "salaire_fcfa": random.randrange(150_000, 1_800_000, 5_000),
                "telephone": telephone(random.random() > 0.15),
                "email": email(pr, no) if random.random() > 0.05 else "",
                "date_naissance": (date(1965, 1, 1) + timedelta(days=random.randint(0, 12_000))).strftime(
                    random.choice(["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y"]))})
dup_emp = random.sample(emp, 6)
for e in dup_emp:
    pr, no = e["nom"].split(" ", 1)
    emp.append({**e, "id": f"E{len(emp)+1:04d}", "nom": bruit_nom(pr, no)})
random.shuffle(emp)
pd.DataFrame(emp).to_excel(DATA / "employes.xlsx", index=False)
verite["employes"] = {"lignes": len(emp), "doublons": 6}

# 2) clients.csv : 6 000 lignes dont environ 1 100 doublons ---------------------------------
N_DOUBLONS = 1_100
base = []
for i in range(6_000 - N_DOUBLONS):
    pr, no = random.choice(PRENOMS), random.choice(NOMS)
    ville = random.choice(VILLES)
    base.append({"client_id": f"C{i+1:05d}", "nom_complet": f"{pr} {no}", "ville": ville,
                 "telephone": telephone(True), "email": email(pr, no) if random.random() > 0.12 else ""})
# on rend les identites uniques en ajoutant un numero de telephone distinct
seen, clients = set(), []
for c in base:
    cle = (c["nom_complet"], c["telephone"])
    if cle in seen:
        continue
    seen.add(cle)
    clients.append(c)
while len(clients) < 6_000 - N_DOUBLONS:
    pr, no = random.choice(PRENOMS), random.choice(NOMS)
    clients.append({"client_id": f"C{len(clients)+1:05d}", "nom_complet": f"{pr} {no}",
                    "ville": random.choice(VILLES), "telephone": telephone(True),
                    "email": email(pr, no)})
doublons = []
for src in random.sample(clients, N_DOUBLONS):
    pr, no = src["nom_complet"].split(" ", 1)
    doublons.append({**src, "client_id": f"C{len(clients)+len(doublons)+1:05d}",
                     "nom_complet": bruit_nom(pr, no)})
tous = clients + doublons
random.shuffle(tous)
pd.DataFrame(tous).to_csv(DATA / "clients.csv", index=False)
verite["clients"] = {"lignes": len(tous), "doublons": N_DOUBLONS,
                     "emails_manquants": sum(1 for c in tous if not c["email"])}

# 3) fournisseurs.csv ---------------------------------------------------------------------------
fournisseurs = pd.DataFrame([
    {"fournisseur": "Alpha", "matiere": "sucre", "delai_moyen_jours": 6, "fiabilite_pct": 94, "prix_relatif": 1.00},
    {"fournisseur": "Alpha", "matiere": "bouteilles", "delai_moyen_jours": 8, "fiabilite_pct": 92, "prix_relatif": 1.00},
    {"fournisseur": "Delta", "matiere": "concentre_mangue", "delai_moyen_jours": 7, "fiabilite_pct": 81, "prix_relatif": 1.00},
    {"fournisseur": "Delta", "matiere": "concentre_orange", "delai_moyen_jours": 7, "fiabilite_pct": 83, "prix_relatif": 1.00},
    {"fournisseur": "Sigma", "matiere": "concentre_mangue", "delai_moyen_jours": 2, "fiabilite_pct": 90,
     "prix_relatif": round(1 + SC["surcout_commande_express_sigma_pct"] / 100, 2)},
    {"fournisseur": "Sigma", "matiere": "concentre_orange", "delai_moyen_jours": 3, "fiabilite_pct": 88, "prix_relatif": 1.05},
])
fournisseurs.to_csv(DATA / "fournisseurs.csv", index=False)

# 4) production.csv : consommation par jour de chaque ligne ----------------------------------
production = pd.DataFrame([
    {"ligne": "Ligne 1", "produit": "Jus d'orange 1 L", "matiere": "concentre_orange", "conso_par_jour": 900},
    {"ligne": "Ligne 1", "produit": "Jus d'orange 1 L", "matiere": "sucre", "conso_par_jour": 300},
    {"ligne": "Ligne 1", "produit": "Jus d'orange 1 L", "matiere": "bouteilles", "conso_par_jour": 900},
    {"ligne": "Ligne 2", "produit": "Nectar de mangue 1 L", "matiere": SC["matiere"], "conso_par_jour": SC["consommation_par_jour"]},
    {"ligne": "Ligne 2", "produit": "Nectar de mangue 1 L", "matiere": "sucre", "conso_par_jour": 400},
    {"ligne": "Ligne 2", "produit": "Nectar de mangue 1 L", "matiere": "bouteilles", "conso_par_jour": 1200},
])
production.to_csv(DATA / "production.csv", index=False)

# 5) stocks.csv : stock par lot, unites melangees, valeurs mal saisies ---------------------------
stocks, n = [], 0


def lot(lieu, matiere, qte, unite="unites"):
    global n
    n += 1
    stocks.append({"lot_id": f"L{n:04d}", "lieu": lieu, "matiere": matiere, "quantite": qte, "unite": unite,
                   "date_reception": (J0 - timedelta(days=random.randint(1, 40))).isoformat()})


# lignes du scenario, volontairement propres (unites, valeurs exactes)
for q in (1_200, 1_200, 1_200, 1_200):
    lot("Ligne 2", SC["matiere"], q)
assert sum(s["quantite"] for s in stocks) == SC["stock_ligne"]
for q in (1_000, 1_000, 1_000):
    lot("Entrepot Nord", SC["matiere"], q)
lot("Entrepot Sud", SC["matiere"], 400)
for _ in range(3):
    lot("Ligne 1", "concentre_orange", random.choice([1_500, 1_800, 2_000]))
n_scenario = len(stocks)
# lots courants avec unites melangees (kg / tonnes / cartons) pour le sucre et les bouteilles
for _ in range(180):
    lieu = random.choice(["Ligne 1", "Ligne 2", "Entrepot Nord", "Entrepot Sud"])
    if random.random() < 0.5:
        unite = random.choice(["kg", "kg", "tonnes"])
        qte = random.randint(200, 2_000) if unite == "kg" else round(random.uniform(0.3, 2.5), 1)
        lot(lieu, "sucre", qte, unite)
    else:
        unite = random.choice(["unites", "cartons"])
        lot(lieu, "bouteilles", random.randint(500, 3_000) if unite == "unites" else random.randint(20, 120), unite)
# 30 valeurs mal saisies parmi les lots non scenario
idx = random.sample(range(n_scenario, len(stocks)), 30)
for k, i in enumerate(idx):
    stocks[i]["quantite"] = [-50, 99999, "N/A", "", "12O0"][k % 5]
pd.DataFrame(stocks).to_csv(DATA / "stocks.csv", index=False)
verite["stocks"] = {"lignes": len(stocks), "valeurs_mal_saisies": 30,
                    "unites_melangees": sorted({s["unite"] for s in stocks})}

# 6) commandes.csv : clients A, B, C ---------------------------------------------------------------
cmd = [
    ("CMD001", "Client A", "Jus d'orange 1 L", 1_800, 3),
    ("CMD002", "Client A", "Jus d'orange 1 L", 2_400, 9),
    ("CMD003", "Client A", "Nectar de mangue 1 L", 1_200, 2),   # livre avant l'arret : sans risque
    ("CMD004", "Client B", "Nectar de mangue 1 L", 2_400, 5),   # menacee
    ("CMD005", "Client B", "Nectar de mangue 1 L", 1_800, 7),   # menacee
    ("CMD006", "Client B", "Jus d'orange 1 L", 1_500, 6),
    ("CMD007", "Client C", "Nectar de mangue 1 L", 3_000, 8),   # menacee
    ("CMD008", "Client C", "Jus d'orange 1 L", 2_100, 12),
]
commandes = pd.DataFrame([{"commande_id": a, "client": b, "produit": c, "quantite": d,
                           "date_livraison": (J0 + timedelta(days=e)).isoformat()} for a, b, c, d, e in cmd])
commandes.to_csv(DATA / "commandes.csv", index=False)

# 7) contrats/*.pdf : 12 contrats fournisseurs, dates dans des formats differents -------------
(DATA / "contrats").mkdir(exist_ok=True)
FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%m-%d-%Y"]
MOIS = {"January": "janvier", "February": "février", "March": "mars", "April": "avril", "May": "mai",
        "June": "juin", "July": "juillet", "August": "août", "September": "septembre",
        "October": "octobre", "November": "novembre", "December": "décembre"}
k = 0
for four in ("Alpha", "Delta", "Sigma"):
    for j in range(4):
        k += 1
        fin = J0 + timedelta(days=random.randint(40, 700))
        txt_date = fin.strftime(FORMATS[(k + j) % len(FORMATS)])
        for en, fr in MOIS.items():
            txt_date = txt_date.replace(en, fr)
        c = canvas.Canvas(str(DATA / "contrats" / f"contrat_{four.lower()}_{j+1}.pdf"), pagesize=A4)
        lignes = [f"CONTRAT D'APPROVISIONNEMENT N° {k:03d}", "",
                  f"Entre Délice SA et le fournisseur {four}.",
                  f"Prix unitaire : {random.randint(900, 2_500)} FCFA",
                  f"Durée : {random.choice([12, 18, 24, 36])} mois",
                  f"Pénalité de retard : {random.choice([1, 2, 3])} % du montant par jour de retard",
                  f"Date d'échéance : {txt_date}", "",
                  "Document fictif généré pour la démonstration Baobab Sève."]
        y = 780
        for ligne in lignes:
            c.drawString(60, y, ligne)
            y -= 24
        c.save()
verite["contrats"] = {"fichiers": 12, "formats_de_date": len(FORMATS)}

(DATA / "_verite_terrain.json").write_text(json.dumps(verite, ensure_ascii=False, indent=2), encoding="utf-8")
print("Donnees generees dans", DATA)
print(json.dumps(verite, ensure_ascii=False, indent=2))
