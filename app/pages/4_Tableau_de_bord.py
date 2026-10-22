from pathlib import Path

import streamlit as st
from common import analyse, db_path, log_action, setup, working_data
from theme import alert_rows, bars_html, page_header, show_line, trust_html

from core import alerts, db, quality, rbac, report
from core.loader import PARAMS
from core.trust import couleur, trust_score

setup("Tableau de bord")
page_header("📊", "4 · Tableau de bord", "L'essentiel pour décider : alertes, qualité des données, stocks et rapport PDF")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, issues, sains = analyse()
avant = st.session_state.avant
sc = PARAMS["scenario"]
COULEURS = {"vert": "#3E8E5E", "orange": "#E08A3C", "rouge": "#D6334A"}
ASSETS = Path(__file__).resolve().parent.parent / "assets"


@st.cache_data(show_spinner="Préparation du rapport PDF…")
def rapport_pdf(version, fournisseur, retard, peut_voir_decisions, _data, _scores, _issues, _sains, _avant, _chemin_base):
    decisions = db.read_decisions(_chemin_base) if peut_voir_decisions else None
    return report.build_report(_data, _scores, _issues, _sains, _avant, decisions, fournisseur, retard,
                               logo_path=str(ASSETS / "logo.png"))


@st.fragment
def tableau():
    """Fragment : changer de scénario met à jour les alertes et le rapport sans recharger la page."""
    fournisseurs = sorted(data["fournisseurs"]["fournisseur"].unique())
    c1, c2 = st.columns([1, 2])
    fournisseur = c1.selectbox("Scénario : fournisseur en retard", fournisseurs, index=fournisseurs.index(sc["fournisseur_en_retard"]),
                               key="tb_fournisseur")
    retard = c2.slider("Retard annoncé (jours)", 0, 10, sc["retard_jours"], key="tb_retard")
    liste = alerts.compute_alerts(data, scores, issues, fournisseur, retard)
    resume = alerts.resume_alertes(liste)
    note = quality.global_score(scores)
    conf = trust_score(sorted(scores), scores)
    n_pb = sum(len(v) for v in issues.values())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Note de qualité", f"{note:g} / 100".replace(".", ","), f"{note - avant['note']:+.1f}".replace(".", ",") if abs(note - avant["note"]) >= 0.05 else None)
    m2.metric("Confiance globale", f"{conf['score']} / 100")
    m3.metric("Alertes urgentes", resume["rouge"], f"{resume['orange']} à surveiller", delta_color="off")
    m4.metric("Problèmes détectés", f"{n_pb:,}".replace(",", " "), f"{n_pb - avant['problemes']:+,}".replace(",", " ") if n_pb != avant["problemes"] else None,
              delta_color="inverse")

    st.subheader("Alertes")
    st.html(alert_rows(liste))

    g, d = st.columns(2, gap="large")
    with g:
        st.subheader("Qualité par fichier")
        st.html(bars_html([(f.capitalize(), v, f"{v:g}".replace(".", ","), COULEURS[couleur(v)]) for f, v in sorted(scores.items(), key=lambda t: t[1])]))
        st.caption(f"Vert à partir de {PARAMS['seuils_confiance']['vert']}, orange à partir de {PARAMS['seuils_confiance']['orange']}.")
    with d:
        st.subheader("Jours de stock")
        cou = alerts.couvertures(data)
        st.html(bars_html([(f"{c['ligne']} · {c['matiere'].replace('concentre', 'concentré').replace('_', ' ')}", c["jours"], f"{c['jours']:g} j".replace(".", ","),
                            COULEURS["rouge" if c["jours"] < alerts.COUVERTURE_ROUGE else "orange" if c["jours"] < alerts.COUVERTURE_ORANGE else "vert"])
                           for c in cou], maximum=40))
        st.caption("Barre pleine à 40 jours. Rouge sous 3 jours, orange sous 7 jours.")

    snaps = db.read_snapshots(db_path())
    if len(snaps) >= 2:
        st.subheader("Évolution de la note de qualité")
        show_line([f"{i}" for i in range(1, len(snaps) + 1)], [float(v) for v in snaps["note"]])
        st.caption("Une étape par validation ou annulation de corrections (page Données).")

    st.subheader("Rapport PDF")
    st.write("Un document de 3 à 4 pages à imprimer ou envoyer : alertes, qualité, chaîne, solutions chiffrées, fournisseurs et décisions. "
             "Il ne contient aucune donnée personnelle.")
    pdf = rapport_pdf(st.session_state.version, fournisseur, retard, rbac.can_validate(role), data, scores, issues, sains, avant, db_path())
    if st.download_button("📄 Télécharger le rapport PDF", pdf, file_name="rapport_baobab_seve.pdf", mime="application/pdf",
                          key="dl_rapport", on_click=log_action, args=(role, "rapport_pdf", f"{fournisseur} {retard} j")):
        st.toast("Rapport téléchargé", icon="📄")


tableau()
