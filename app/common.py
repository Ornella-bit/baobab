"""Elements partages par les 3 pages : chemin Python, choix du role, chargement des donnees."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core.loader import PARAMS, data_ready, list_contracts, load_all  # noqa: E402

ROLES = ["Directeur général", "Stagiaire logistique"]


def setup(page_title):
    st.set_page_config(page_title=f"BAOBAB · {page_title}", page_icon="🌳", layout="wide")
    with st.sidebar:
        st.markdown("### 🌳 BAOBAB")
        st.caption(f"Démo sur données fictives · {PARAMS['societe']}")
        st.selectbox("Rôle de l'utilisateur", ROLES, key="role")
    if not data_ready():
        st.error("Les données n'existent pas encore. Lance d'abord : `python generate_data.py`")
        st.stop()


@st.cache_data
def get_data():
    return load_all()


def contracts():
    return list_contracts()
