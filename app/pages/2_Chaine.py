import pandas as pd
import streamlit as st
from common import analyse, db_path, log_action, setup, working_data
from theme import acces_refuse, page_header, show_svg, show_table, trust_html
from visuals import chain_svg

from core import db, rbac
from core.graph import build_graph
from core.loader import PARAMS
from core.simulate import list_options, simulate_supplier_delay
from core.trust import trust_score

setup("Chaîne")
page_header("🔗", "2 · Chaîne de production", "SupplyMind : relier la chaîne de bout en bout et simuler un retard")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, _, _ = analyse()
sc = PARAMS["scenario"]
EMOJI_RISQUE = {"faible": "🟢", "moyen": "🟠", "eleve": "🔴"}


def nombre(n):
    return f"{n:,}".replace(",", " ")


# --- parametres de la simulation --------------------------------------------------------------
fournisseurs = sorted(data["fournisseurs"]["fournisseur"].unique())
col1, col2 = st.columns([1, 2])
fournisseur = col1.selectbox("Fournisseur en retard", fournisseurs,
                             index=fournisseurs.index(sc["fournisseur_en_retard"]))
retard = col2.slider("Retard annoncé (jours)", 0, 10, sc["retard_jours"])
sim = simulate_supplier_delay(data, fournisseur, retard)

# --- resultat --------------------------------------------------------------------------------
if sim["ligne"] is None:
    st.info(f"{fournisseur} ne fournit aucune matière utilisée par une ligne de production.")
elif sim["arret_jour"] is None:
    st.success(f"✅ Aucun arrêt prévu : la {sim['ligne']} a {sim['couverture_jours']:.0f} jours de stock de "
               f"{sim['matiere'].replace('_', ' ')}, plus que le retard de {retard} jours.")
else:
    st.error(f"⚠️ La {sim['ligne']} s'arrêterait à **J+{sim['arret_jour']}** faute de "
             f"{sim['matiere'].replace('_', ' ')}.")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Couverture de stock", f"{sim['couverture_jours']:.0f} jours" if sim["couverture_jours"] is not None else "—")
m2.metric("Arrêt de production", f"J+{sim['arret_jour']}" if sim["arret_jour"] is not None else "Aucun")
m3.metric("Manque", f"{nombre(sim['manque'])} unités")
m4.metric("Commandes menacées", len(sim["commandes"]))
m5.metric("Clients touchés", len(sim["clients"]))

# --- confiance -------------------------------------------------------------------------------
t = trust_score(["stocks", "production", "fournisseurs", "commandes"], scores)
st.html("<b>Confiance de cette analyse</b> &nbsp; " + trust_html(t, scores))
if t["a_confirmer"]:
    st.warning("Confiance basse : à confirmer avant de décider. Corrige d'abord les données (page 1).")

# --- graphe ----------------------------------------------------------------------------------
st.subheader("La chaîne de bout en bout")
graphe = build_graph(data)
show_svg(chain_svg(graphe, sim["noeuds_impactes"], source=fournisseur if sim["arret_jour"] is not None else None))

# --- commandes menacees et options -------------------------------------------------------------
if sim["commandes_detail"]:
    st.subheader("Commandes menacées")
    tableau = pd.DataFrame(sim["commandes_detail"]).rename(columns={
        "commande_id": "Commande", "client": "Client", "produit": "Produit", "quantite": "Quantité",
        "date_livraison": "Livraison", "jour": "Jour"})
    show_table(tableau, hide_index=True)

options = list_options(data, sim)
if options:
    st.subheader("Trois solutions")
    for colonne, o in zip(st.columns(3), options):
        with colonne.container(border=True):
            st.markdown(f"**Option {o['code']}** {'✅ faisable' if o['faisable'] else '❌ impossible'}")
            st.write(o["libelle"])
            st.write(f"Surcoût : **+{o['surcout_pct']:g} %** · Risque : {EMOJI_RISQUE[o['risque']]} {o['risque'].replace('eleve', 'élevé')}")
            if o["faisable"]:
                if rbac.can_validate(role):
                    if st.button(f"Retenir l'option {o['code']}", key=f"option_{o['code']}"):
                        st.session_state["option_retenue"] = o["code"]
                        log_action(role, "option_retenue", f"{fournisseur} {retard} j : option {o['code']}")
                        db.add_decision(role, fournisseur, retard, o["code"], o["libelle"], db_path())
                else:
                    acces_refuse("à cette décision")
    if st.session_state.get("option_retenue"):
        st.success(f"Option {st.session_state['option_retenue']} retenue et inscrite au journal des actions.")

# --- decisions prises (base de donnees) -------------------------------------------------------
st.subheader("Décisions prises")
if rbac.can_validate(role):
    decisions = db.read_decisions(db_path())
    if decisions.empty:
        st.caption("Aucune décision retenue pour le moment : chaque décision sera conservée dans la base de données.")
    else:
        show_table(decisions.rename(columns={"horodatage": "Date", "role": "Rôle", "fournisseur": "Fournisseur",
                                               "retard_jours": "Retard (jours)", "option_code": "Option", "libelle": "Solution"}),
                     hide_index=True)
else:
    acces_refuse("aux décisions prises")
