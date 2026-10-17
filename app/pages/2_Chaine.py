import streamlit as st
from common import PARAMS, get_data, setup

setup("Chaîne")
st.title("2 · Chaîne de production (SupplyMind)")
st.caption("Étape 2 : emplacement du graphe et de la simulation (étape 4B).")
data = get_data()
st.markdown("**Fournisseurs**")
st.dataframe(data["fournisseurs"], width="stretch")
st.markdown("**Production par ligne**")
st.dataframe(data["production"], width="stretch")
sc = PARAMS["scenario"]
st.slider(f"Retard du fournisseur {sc['fournisseur_en_retard']} (jours)", 0, 10, sc["retard_jours"], disabled=True)
st.info("La simulation sera branchée ici.")
