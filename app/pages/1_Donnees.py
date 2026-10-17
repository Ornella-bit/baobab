import streamlit as st
from common import get_data, setup

setup("Données")
st.title("1 · Données (DataCompass)")
st.caption("Étape 2 : l'application s'ouvre et lit les fichiers. Les notes de qualité arrivent à l'étape 4.")
data = get_data()
choix = st.selectbox("Fichier à afficher", list(data))
st.dataframe(data[choix].head(200), use_container_width=True)
st.write(f"{len(data[choix])} lignes · {len(data[choix].columns)} colonnes")
