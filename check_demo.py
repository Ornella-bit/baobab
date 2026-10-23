"""Verifie le pack demo (etape 14) : import de fichiers, simulation « et si », fiches du graphe. Usage : python check_demo.py -> « OK »."""
import io

import pandas as pd

from core import explorer, importer, whatif
from core.graph import ORDRE, build_graph
from core.loader import load_all

data = load_all()

# 1) import : chaque modele se lit et se relie entierement, et le jeu de donnees reste exploitable
for table in importer.TABLES:
    df = importer.lire_fichier(importer.modele_csv(table), f"{table}.csv")
    lien = importer.relier_colonnes(df, table)
    assert all(lien.values()), (table, lien)
    assert importer.detecter_table(df)[0][0] == table, (table, importer.detecter_table(df)[:2])
    nouveau, rapport = importer.preparer(df, table, lien)
    assert nouveau is not None and list(nouveau.columns) == list(importer.TABLES[table]["colonnes"]), table

# 2) fichier mal presente : en-tetes libres, separateur « ; », virgules decimales, unites variees
contenu, nom = importer.fichier_exemple_stocks()
df = importer.lire_fichier(contenu, nom)
assert importer.detecter_table(df)[0] == ("stocks", 1.0)
nouveau, rapport = importer.preparer(df, "stocks", importer.relier_colonnes(df, "stocks"))
assert set(nouveau["matiere"]) <= {"sucre", "concentre_orange", "concentre_mangue", "bouteilles"}, set(nouveau["matiere"])
assert set(nouveau["unite"]) <= {"kg", "tonnes", "unites", "cartons"}, set(nouveau["unite"])
candidat, erreur = importer.appliquer(data, "stocks", nouveau, "remplacer")
assert erreur is None and len(candidat["stocks"]) == len(nouveau) and len(data["stocks"]) == 191  # l'original n'est pas touche
candidat, erreur = importer.appliquer(data, "stocks", nouveau, "ajouter")
assert erreur is None and len(candidat["stocks"]) == 191 + len(nouveau)

# 3) fichiers refuses, avec un message clair
for contenu_mauvais, nom_mauvais in [(b"", "a.csv"), (b"a,b\n1,2", "virus.exe"), (b"\x00\x01\x02", "faux.xlsx"), (b"a\n1\n", "une_colonne.csv")]:
    try:
        importer.lire_fichier(contenu_mauvais, nom_mauvais)
        raise AssertionError(f"{nom_mauvais} aurait du etre refuse")
    except importer.ErreurImport as e:
        assert str(e)
assert importer.refus_confidentialite(importer.lire_fichier("nom;salaire\nA;1\n".encode(), "rh.csv"))
assert importer.lire_fichier("a;b\n1;2\n".encode("latin-1"), "latin.csv").shape == (1, 2)

# 4) un fichier incoherent avec les autres est refuse sans rien casser
inconnue = pd.DataFrame({"fournisseur": ["Zeta"], "matiere": ["lait"], "delai_moyen_jours": [3], "fiabilite_pct": [90], "prix_relatif": [1.0]})
_, rapport = importer.preparer(inconnue, "fournisseurs", {c: c for c in importer.TABLES["fournisseurs"]["colonnes"]})
assert rapport["inconnues"]["matiere"] == ["lait"] and rapport["avertissements"]  # signale, sans bloquer
production_incoherente = pd.DataFrame({"ligne": ["Ligne 9"], "produit": ["Jus de lait"], "matiere": ["lait"], "conso_par_jour": [100]})
_, erreur = importer.appliquer(data, "production", production_incoherente, "ajouter")
assert erreur, "une ligne de production qui consomme une matiere sans stock ni unite doit etre refusee"
assert len(data["production"]) == 6

# 5) simulation « et si » : les chiffres du scenario de depart, puis l'effet d'un stock ou d'une consommation differente
s = whatif.sensibilite(data, "Delta", 8)
assert s[3]["manque"] == 0 and s[5]["manque"] == 1200 and s[5]["arret_jour"] == 4 and s[6]["manque"] == 2400
assert whatif.retard_supportable(data, "Delta") == 4.0
assert whatif.carte_des_risques(data, 6)["Alpha"] == [0] * 7
c = whatif.comparer(data, "Delta", 5, stock_supplementaire=1200)
assert c["avant"]["manque"] == 1200 and c["apres"]["manque"] == 0 and c["gain_manque"] == 1200 and c["commandes_sauvees"] == 3
c = whatif.comparer(data, "Delta", 5, conso_pct=30)
assert c["apres"]["arret_jour"] == 3 and c["apres"]["manque"] > 1200
assert len(data["stocks"]) == 191  # les donnees d'origine ne bougent pas

# 6) fiches du graphe
g = build_graph(data)
f = explorer.fiche(data, g, "Delta")
assert "J+4" in f["alerte"] and len(f["aval"]) > 0 and f["amont"] == []
assert "CMD004" in explorer.fiche(data, g, "Client B")["faits"][0][1]
for t, noeuds in explorer.noeuds_par_type(g).items():
    for n in noeuds:
        assert explorer.fiche(data, g, n)["titre"], n
assert [t for t in ORDRE if explorer.noeuds_par_type(g)[t]] == ORDRE
print("OK : import (6 types, fichier mal présenté, refus clairs), simulation « et si » et fiches du graphe.")
