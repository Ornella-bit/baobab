import streamlit as st
from common import PARAMS, get_data, setup

setup("Chaîne")
st.title("2 · Chaîne de production (SupplyMind)")
st.caption("Étape 2 : emplacement du graphe et de la simulation (étape 5).")
data = get_data()
st.markdown("**Fournisseurs**")
st.dataframe(data["fournisseurs"], use_container_width=True)
st.markdown("**Production par ligne**")
st.dataframe(data["production"], use_container_width=True)
sc = PARAMS["scenario"]
st.slider(f"Retard du fournisseur {sc['fournisseur_en_retard']} (jours)", 0, 10, sc["retard_jours"], disabled=True)
st.info("La simulation sera branchée ici.")
