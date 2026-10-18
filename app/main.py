"""Point d'entree : menu de gauche (Accueil, Données, Chaîne, Copilote), thème et choix du rôle."""
import streamlit as st
from common import ROLES
from theme import inject_css

st.set_page_config(page_title="BAOBAB", page_icon="🌳", layout="wide")
inject_css()
with st.sidebar:
    st.markdown("### 🌳 BAOBAB")
    st.selectbox("Rôle de l'utilisateur", ROLES, key="role")

st.navigation([
    st.Page("accueil.py", title="Accueil", icon="🏠", default=True),
    st.Page("pages/1_Donnees.py", title="Données", icon="🗂️"),
    st.Page("pages/2_Chaine.py", title="Chaîne", icon="🔗"),
    st.Page("pages/3_Copilote.py", title="Copilote", icon="💬"),
]).run()
