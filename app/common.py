"""Elements partages par les pages : chemin Python, choix du role, donnees de travail et analyse."""
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import db, quality  # noqa: E402
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
    if not db.has_data(db_path()):  # premiere visite : la base du visiteur est creee a partir des fichiers
        db.init_db(get_data(), db_path())
        for k in ("data", "version", "avant"):
            st.session_state.pop(k, None)
    if "nettoyage" not in st.session_state:
        st.session_state.nettoyage = True
        _nettoyer_vieilles_bases()


def session_id():
    """Identifiant du visiteur : une base SQLite par visiteur, retrouvee apres un rechargement grace a l'adresse (?s=...)."""
    if "sid" not in st.session_state:
        depuis_url = str(st.query_params.get("s", ""))
        st.session_state.sid = depuis_url if re.fullmatch(r"[0-9a-f]{12}", depuis_url) else uuid.uuid4().hex[:12]
    st.query_params["s"] = st.session_state.sid
    return st.session_state.sid


def db_path():
    return db.path_for(session_id())


def _nettoyer_vieilles_bases(jours=2):
    """Supprime les bases des visiteurs partis depuis plus de deux jours."""
    limite = time.time() - jours * 86400
    for f in db.DB_DIR.glob("*.db"):
        try:
            if f.stat().st_mtime < limite:
                f.unlink()
        except OSError:
            pass


def log_action(role, action, detail=""):
    """Inscrit une action dans le journal de la base du visiteur."""
    db.log_action(role, action, detail, path=db_path())


@st.cache_data
def get_data():
    """Donnees d'origine (jamais modifiees)."""
    return load_all()


def contracts():
    return list_contracts()


def reset_demo():
    """Remet la demo a zero (donnees d'origine, notes « avant » recalculees)."""
    db.init_db(get_data(), db_path())
    for k in ("data", "version", "avant", "option_retenue"):
        st.session_state.pop(k, None)


def working_data():
    """Donnees courantes : copie des donnees d'origine, modifiee par les corrections validees."""
    if "data" not in st.session_state:
        st.session_state.data = db.load_tables(db_path())
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
        instantanes = db.read_snapshots(db_path())
        if len(instantanes):  # l'etat « avant » est celui du depart, meme apres un rechargement de la page
            d = instantanes.iloc[0]
            st.session_state.avant = {"note": float(d["note"]), "sains": float(d["lignes_saines"]), "problemes": int(d["problemes"])}
        else:
            st.session_state.avant = {"note": quality.global_score(scores), "sains": global_sains(data, sains),
                                      "problemes": sum(len(v) for v in issues.values())}
            a = st.session_state.avant
            db.add_snapshot("départ", a["note"], a["sains"], a["problemes"], db_path())
    return scores, issues, sains


def snapshot(evenement):
    """Memorise la note de qualite actuelle dans l'historique de la base."""
    data = working_data()
    scores, issues, sains = _analyse(st.session_state.version, data)
    db.add_snapshot(evenement, quality.global_score(scores), global_sains(data, sains),
                    sum(len(v) for v in issues.values()), db_path())


def record_validation(role, avant, resume):
    """Enregistre dans la base les corrections que l'utilisateur vient de valider (donnees courantes = apres)."""
    lot, n = db.record_validation(role, avant, st.session_state.data, resume, db_path())
    st.session_state.version += 1
    log_action(role, "valider_corrections", resume)
    snapshot("validation")
    return lot, n


def undo_last_validation(role):
    """Annule la derniere validation : la base est remise dans l'etat precedent et rechargee."""
    res = db.undo_last(db_path())
    if res is not None:
        st.session_state.data = db.load_tables(db_path())
        st.session_state.version += 1
        log_action(role, "annuler_validation", f"lot {res[0]} annulé ({res[1]} changements)")
        snapshot("annulation")
    return res
