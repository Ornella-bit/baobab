"""Point d'entree : menu de gauche (Accueil, Données, Chaîne, Copilote, Tableau de bord, Importer), thème et choix du rôle."""
from pathlib import Path

import streamlit as st
from PIL import Image
from common import ROLES
from theme import inject_css

ASSETS = Path(__file__).parent / "assets"
st.set_page_config(page_title="Baobab Sève", page_icon=Image.open(ASSETS / "favicon.png"), layout="wide")
inject_css()
with st.sidebar:
    st.image(str(ASSETS / "logo.png"), width="stretch")
    st.selectbox("Rôle de l'utilisateur", ROLES, key="role")

st.navigation([
    st.Page("accueil.py", title="Accueil", icon="🏠", default=True),
    st.Page("pages/1_Donnees.py", title="Données", icon="🗂️"),
    st.Page("pages/2_Chaine.py", title="Chaîne", icon="🔗"),
    st.Page("pages/3_Copilote.py", title="Copilote", icon="💬"),
    st.Page("pages/4_Tableau_de_bord.py", title="Tableau de bord", icon="📊"),
    st.Page("pages/5_Importer.py", title="Importer", icon="📥"),
]).run()
