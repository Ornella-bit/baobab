import streamlit as st
from common import setup

setup("Copilote")
st.title("3 · Copilote")
st.caption("Étape 2 : zone de discussion vide. Le modèle de langage et le score de confiance arrivent plus tard.")
if "messages" not in st.session_state:
    st.session_state.messages = []
for m in st.session_state.messages:
    st.chat_message(m["role"]).write(m["content"])
if question := st.chat_input("Pose une question sur la chaîne de production…"):
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append({"role": "assistant", "content": "Le copilote n'est pas encore branché."})
    st.rerun()
