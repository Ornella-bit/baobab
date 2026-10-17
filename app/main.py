import streamlit as st
from common import PARAMS, contracts, get_data, setup

setup("Accueil")
st.title("🌳 BAOBAB")
st.subheader("Des données fiables, une chaîne de production sous contrôle")
st.write(
    f"Démonstration sur les données **fictives** de {PARAMS['societe']}, une usine de jus de fruits. "
    "Utilise le menu de gauche : **Données**, **Chaîne**, **Copilote**."
)
data = get_data()
cols = st.columns(len(data) + 1)
for col, (nom, df) in zip(cols, data.items()):
    col.metric(nom.capitalize(), f"{len(df):,}".replace(",", " "), help="nombre de lignes")
cols[-1].metric("Contrats PDF", len(contracts()))
st.info(f"Rôle actuel : **{st.session_state.get('role', '—')}**")
