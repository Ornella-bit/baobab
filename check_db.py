"""Verification de la base SQLite : python check_db.py (aucune cle, aucun reseau)."""
import tempfile
from pathlib import Path

import pandas as pd

from core import db, quality
from core.loader import load_all

ok = True


def verifier(condition, message):
    global ok
    print(("OK   " if condition else "ECHEC"), message)
    ok = ok and bool(condition)


def meme_donnees(a, b):
    for nom in db.TABLES:
        x, y = a[nom], b[nom]
        if list(x.columns) != list(y.columns) or len(x) != len(y) or list(x.index) != list(y.index):
            return False
        for c in x.columns:
            for u, v in zip(x[c], y[c]):
                if not db._egal(u, v):
                    return False
    return True


def corriger(data):
    """Applique toutes les corrections automatiques, comme le fait le bouton « Valider »."""
    out = {k: v.copy() for k, v in data.items()}
    for f in db.TABLES:
        lst = [i for i in quality.list_issues(out[f], f) if i["correction"] is not None]
        for i in lst:
            i["statut"] = "valide"
        out[f] = quality.apply_corrections(out[f], lst)
    return out


with tempfile.TemporaryDirectory() as tmp:
    chemin = Path(tmp) / "test.db"
    origine = load_all()

    # 1. creation et relecture
    db.init_db(origine, chemin)
    verifier(db.has_data(chemin), "la base est creee avec les 6 tables")
    relu = db.load_tables(chemin)
    verifier(meme_donnees(origine, relu), "les donnees relues sont identiques aux fichiers d'origine (valeurs, ordre, index)")
    s0, s1 = quality.all_scores(origine), quality.all_scores(relu)
    verifier(s0 == s1, f"les notes de qualite sont identiques apres un aller-retour par la base : {quality.global_score(s1)}")
    verifier(db.table_counts(chemin)["clients"] == len(origine["clients"]), "le nombre de lignes est conserve")

    # 2. validation, enregistrement et relecture
    corrige = corriger(origine)
    note_avant, note_apres = quality.global_score(s0), quality.global_score(quality.all_scores(corrige))
    verifier(note_apres > note_avant, f"les corrections font monter la note : {note_avant} -> {note_apres}")
    lot, n = db.record_validation("Directeur général", origine, corrige, "test", chemin)
    verifier(n > 0, f"{n} changements enregistres dans le lot {lot}")
    relu2 = db.load_tables(chemin)
    verifier(meme_donnees(corrige, relu2), "apres validation, la base contient les donnees corrigees")
    verifier(quality.all_scores(relu2) == quality.all_scores(corrige), "les notes relues dans la base = notes des donnees corrigees")
    verifier(len(db.read_lots(chemin)) == 1 and db.can_undo(chemin), "le lot apparait dans l'historique et peut etre annule")

    # 3. annulation
    res = db.undo_last(chemin)
    verifier(res is not None and res[1] == n, "l'annulation traite tous les changements du lot")
    relu3 = db.load_tables(chemin)
    verifier(meme_donnees(origine, relu3), "apres annulation, les donnees sont revenues exactement a l'origine")
    verifier(not db.can_undo(chemin) and db.undo_last(chemin) is None, "plus rien a annuler ensuite")

    # 4. journal, instantanes, decisions
    db.log_action("Directeur général", "valider_corrections", "essai", chemin)
    verifier(len(db.read_log(chemin)) == 1, "le journal des actions est dans la base")
    db.add_snapshot("départ", note_avant, 70.0, 100, chemin)
    db.add_snapshot("validation", note_apres, 88.0, 10, chemin)
    snaps = db.read_snapshots(chemin)
    verifier(list(snaps["evenement"]) == ["départ", "validation"], "l'historique de la note est conserve")
    db.add_decision("Directeur général", "Delta", 5, "B", "Commander en express", chemin)
    verifier(len(db.read_decisions(chemin)) == 1, "les decisions retenues sont conservees")

    # 5. requetes libres : lecture seule
    df = db.run_select("SELECT COUNT(*) AS n FROM clients", chemin)
    verifier(int(df.iloc[0, 0]) == len(origine["clients"]), "une requete SELECT fonctionne")
    for mauvaise in ("DROP TABLE clients", "DELETE FROM clients", "SELECT 1; DROP TABLE clients",
                     "UPDATE clients SET ville='x'", "WITH t AS (SELECT 1) DELETE FROM clients", ""):
        try:
            db.run_select(mauvaise, chemin)
            verifier(False, f"requete dangereuse refusee : {mauvaise!r}")
        except Exception:
            verifier(True, f"requete dangereuse refusee : {mauvaise!r}")
    verifier(db.table_counts(chemin)["clients"] == len(origine["clients"]), "la table clients est intacte apres les tentatives")

    # 6. remise a zero
    db.init_db(origine, chemin)
    verifier(len(db.read_log(chemin)) == 0 and meme_donnees(origine, db.load_tables(chemin)), "la remise a zero recree une base propre")

print("\nTOUT EST BON" if ok else "\nIL Y A DES ECHECS")
raise SystemExit(0 if ok else 1)
