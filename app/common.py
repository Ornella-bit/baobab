"""Elements partages par les pages : chemin Python, choix du role, donnees de travail et analyse."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import quality  # noqa: E402
from core.loader import PARAMS, data_ready, list_contracts, load_all  # noqa: E402

ROLES = ["Directeur général", "Stagiaire logistique"]


def setup(page_title):
    """Verifie que les donnees existent ; sur un serveur neuf (deploiement), les cree toutes seules."""
    st.session_state.setdefault("role", ROLES[0])
    if not data_ready():
        with st.spinner("Première ouverture : création des données fictives (environ 20 secondes)…"):
            subprocess.run([sys.executable, str(ROOT / "generate_data.py")], cwd=ROOT, capture_output=True, check=False)
        st.cache_data.clear()
    if not data_ready():
        st.error("Les données n'existent pas encore. Lance d'abord : `python generate_data.py`")
        st.stop()


@st.cache_data
def get_data():
    """Donnees d'origine (jamais modifiees)."""
    return load_all()


def contracts():
    return list_contracts()


def reset_demo():
    """Remet la demo a zero (donnees d'origine, notes « avant » recalculees)."""
    for k in ("data", "version", "avant"):
        st.session_state.pop(k, None)


def working_data():
    """Donnees courantes : copie des donnees d'origine, modifiee par les corrections validees."""
    if "data" not in st.session_state:
        st.session_state.data = {k: v.copy() for k, v in get_data().items()}
        st.session_state.version = 0
        st.session_state.avant = None
    return st.session_state.data


@st.cache_data(show_spinner="Analyse des données…")
def _analyse(version, _data):
    scores = quality.all_scores(_data)
    issues = {f: quality.list_issues(df, f) for f, df in _data.items()}
    sains = {f: quality.healthy_rate(df, issues[f]) for f, df in _data.items()}
    return scores, issues, sains


def global_sains(data, sains):
    """Part de lignes saines sur l'ensemble des fichiers, en %."""
    total = sum(len(df) for df in data.values())
    return round(100 * sum(sains[f] * len(df) for f, df in data.items()) / total, 1)


def analyse():
    """Retourne (notes, problemes, lignes_saines) des donnees courantes, et memorise l'etat « avant »."""
    data = working_data()
    scores, issues, sains = _analyse(st.session_state.version, data)
    if st.session_state.avant is None:
        st.session_state.avant = {"note": quality.global_score(scores), "sains": global_sains(data, sains),
                                  "problemes": sum(len(v) for v in issues.values())}
    return scores, issues, sains
