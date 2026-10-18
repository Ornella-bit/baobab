import streamlit as st
from common import analyse, setup, working_data
from theme import page_header, trust_html

from core import copilot, rbac

setup("Copilote")
page_header("💬", "3 · Copilote", "Posez une question en français : la réponse cite ses sources et affiche sa confiance")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, _, _ = analyse()

with st.sidebar:
    hors_ligne = st.toggle("Mode hors ligne (sans Internet)", value=False,
                           help="Le copilote répond avec les mêmes fonctions de calcul, sans modèle de langage.")
    st.caption("Cette démo utilise l'IA si une clé d'API est configurée dans .env, sinon le mode hors ligne.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def afficher(m):
    with st.chat_message(m["role"]):
        st.write(m["content"])
        meta = m.get("meta")
        if not meta:
            return
        if meta["confiance"]:
            c = meta["confiance"]
            st.html(trust_html(c, scores))
            if c["a_confirmer"]:
                st.warning("À confirmer : les données utilisées sont peu fiables.")
        if meta["sources"]:
            st.caption("Sources : " + ", ".join(meta["sources"]) + f" · mode : {meta['mode'].replace('_', ' ')}")


for m in st.session_state.messages:
    afficher(m)

suggestions = ["Que se passe-t-il si Delta a 5 jours de retard ?", "Combien de jours de stock reste-t-il à la Ligne 2 ?",
               "D'où vient le nectar de mangue ?", "Quel est le salaire du directeur ?"]
choix = None
for rang in (suggestions[:2], suggestions[2:]):
    for col, s in zip(st.columns(2), rang):
        if col.button(s, key=f"sugg_{s}", width="stretch"):
            choix = s
question = st.chat_input("Pose une question sur la chaîne de production…") or choix

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    afficher(st.session_state.messages[-1])
    with st.spinner("Analyse en cours…"):
        r = copilot.ask(question, role, data, scores, mode="hors_ligne" if hors_ligne else "auto")
    st.session_state.messages.append({"role": "assistant", "content": r["texte"], "meta": r})
    afficher(st.session_state.messages[-1])

if st.session_state.messages and st.button("Effacer la conversation"):
    st.session_state.messages = []
    st.rerun()
