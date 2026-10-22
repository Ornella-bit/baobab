"""Verifie les alertes et le rapport PDF (etape 13) sans Internet ni Streamlit. Usage : python check_report.py -> « OK »."""
import pandas as pd
from reportlab import rl_config

from core import alerts, quality, report
from core.loader import load_all

rl_config.pageCompression = 0  # texte lisible dans le PDF pour le verifier
data = load_all()
scores = quality.all_scores(data)
issues = {f: quality.list_issues(df, f) for f, df in data.items()}

# 1) alertes : le scenario Delta est l'alerte la plus urgente, les stocks courts et les donnees sont signales
liste = alerts.compute_alerts(data, scores, issues)
assert liste[0]["niveau"] == "rouge" and "Ligne 2" in liste[0]["titre"] and "J+4" in liste[0]["titre"], liste[0]
assert [a["niveau"] for a in liste] == sorted((a["niveau"] for a in liste), key=alerts.ORDRE_NIVEAU.get), "alertes mal triees"
titres = " | ".join(a["titre"] for a in liste)
assert "concentré mangue sur la Ligne 2 (4 jours)" in titres and "Delta : fiabilité" in titres and "corrections prêtes" in titres, titres
assert alerts.resume_alertes(liste) == {"rouge": 1, "orange": 5, "vert": 0}, alerts.resume_alertes(liste)
cou = alerts.couvertures(data)
assert cou[0]["jours"] == 4.0 and cou[0]["ligne"] == "Ligne 2" and cou == sorted(cou, key=lambda c: c["jours"])

# 2) pas d'arret : l'alerte du scenario passe au vert
calme = alerts.compute_alerts(data, scores, issues, "Delta", 2)
assert calme[-1]["niveau"] == "vert" or all(a["niveau"] != "rouge" for a in calme)
assert not any("s'arrêterait" in a["titre"] for a in calme)

# 3) rapport PDF
decisions = pd.DataFrame([{"horodatage": "2026-11-02T09:00:00", "role": "Directeur général", "fournisseur": "Delta", "retard_jours": 5,
                           "option_code": "B", "libelle": "Commander 1 200 unités en express chez Sigma"}])
pdf = report.build_report(data, scores, issues, avant={"note": 90.0, "sains": 80.0, "problemes": 3000}, decisions=decisions)
assert pdf[:5] == b"%PDF-" and len(pdf) > 20_000 and pdf.count(b"/Type /Page\n") >= 3, (len(pdf), pdf.count(b"/Type /Page\n"))
for attendu in (b"Rapport de situation", b"J+4", b"Trois solutions", b"cisions prises", b"Alertes"):  # accents ecrits en octal dans le PDF
    assert attendu in pdf, attendu
assert b"@" not in pdf, "le rapport ne doit contenir aucun e-mail"
sans_decision = report.build_report(data, scores, issues)
assert b"cision enregistr" in sans_decision
print(f"OK : {len(liste)} alertes triées, rapport PDF de {len(pdf) // 1024} Ko sans donnée personnelle.")
