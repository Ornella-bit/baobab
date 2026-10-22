import time

import streamlit as st
from common import analyse, log_action, setup, working_data
from theme import page_header, show_table, trust_html

from core import askdata, copilot, rbac

setup("Copilote")
page_header("💬", "3 · Copilote", "Posez n'importe quelle question sur vos données : la réponse cite ses sources et affiche sa confiance")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, problemes, _ = analyse()

st.session_state.setdefault("messages", [])
st.session_state.setdefault("memoire", None)
st.session_state.setdefault("en_attente", None)

EXEMPLES = {
    "🔮 Simuler": ["Que se passe-t-il si Delta a 5 jours de retard ?", "Quel fournisseur est le plus risqué ?",
                   "Quelle solution recommandes-tu ?"],
    "📦 Interroger les données": ["Quel client a passé la plus grosse commande ?", "Combien de lots de sucre avons-nous ?",
                                  "Compare Sigma et Delta"],
    "🧪 Qualité et confiance": ["Quels sont les problèmes dans les stocks ?", "Pourquoi cette confiance ?",
                                "Combien de clients n'ont pas d'e-mail ?"],
}

with st.sidebar:
    hors_ligne = st.toggle("Mode hors ligne (sans Internet)", value=False,
                           help="Le copilote répond avec le même moteur de calcul, sans modèle de langage.")
    st.caption("Sans clé d'API, le copilote travaille toujours hors ligne : il comprend la question, interroge une copie "
               "des données en lecture seule, puis rédige la réponse à partir du résultat.")
    with st.expander("Ce que je peux interroger"):
        st.write(askdata.decrire_schema(data))
    if st.session_state.memoire and st.session_state.memoire.get("plan"):
        st.caption("🧠 Sujet en mémoire : " + askdata._comprehension(st.session_state.memoire["plan"]))
    if st.session_state.messages and st.button("🗑️ Effacer la conversation", width="stretch"):
        st.session_state.messages = []
        st.session_state.memoire = None
        st.rerun()


def flux(texte, pause=0.012):
    """Affiche la réponse mot après mot (effet « le copilote écrit »)."""
    for mot in texte.split(" "):
        yield mot + " "
        time.sleep(pause)


def ecrire(texte, progressif):
    if progressif:
        try:
            st.write_stream(flux(texte))
            return
        except AttributeError:  # version de Streamlit sans write_stream
            pass
    st.write(texte)


def details(m, rang, dernier):
    """Tout ce qui accompagne la réponse : tableau, confiance, sources, explication, questions de suite."""
    meta = m.get("meta")
    if not meta:
        return
    tab = meta.get("tableau")
    if tab is not None and len(tab):
        with st.expander(f"📊 Voir les données ({len(tab)} ligne{'s' if len(tab) > 1 else ''})", expanded=len(tab) <= 6):
            show_table(tab, hide_index=True)
    if meta["confiance"]:
        c = meta["confiance"]
        st.html(trust_html(c, scores))
        if c["a_confirmer"]:
            st.warning("À confirmer : les données utilisées sont peu fiables.")
    if meta["sources"]:
        st.caption("Sources : " + ", ".join(meta["sources"]) + f" · mode : {meta['mode'].replace('_', ' ')}")
    if meta.get("explication"):
        with st.expander("🔎 Comment j'ai trouvé cette réponse"):
            for i, etape in enumerate(meta["explication"], 1):
                st.markdown(f"**{i}.** {etape}")
            if meta.get("requete"):
                st.code(meta["requete"], language="sql")
    if dernier and meta.get("suggestions"):
        st.caption("Pour continuer :")
        for col, s in zip(st.columns(len(meta["suggestions"])), meta["suggestions"]):
            if col.button(s, key=f"suite_{rang}_{s}", width="stretch"):
                st.session_state.en_attente = s
                st.rerun()


# --- une question arrive : saisie libre ou bouton ---------------------------------------------
question = st.chat_input("Pose une question sur tes données… (ex. « Combien de lots de sucre ? », « Et pour la mangue ? »)")
if st.session_state.en_attente:
    question, st.session_state.en_attente = st.session_state.en_attente, None

# --- historique ----------------------------------------------------------------------------
msgs = st.session_state.messages
if not msgs and not question:
    st.html("<div class='bb-lock' style='background:#E8F5EA;border-color:#B7DDBF;color:#1F6A31'><span>💡</span>"
            "<span>Demande ce que tu veux sur les stocks, commandes, fournisseurs, production et clients. "
            "Le copilote se souvient de la conversation : « Et pour Sigma ? » fonctionne.</span></div>")
    for titre, qs in EXEMPLES.items():
        st.markdown(f"**{titre}**")
        for col, s in zip(st.columns(len(qs)), qs):
            if col.button(s, key=f"ex_{s}", width="stretch"):
                st.session_state.en_attente = s
                st.rerun()

for i, m in enumerate(msgs):
    with st.chat_message(m["role"]):
        st.write(m["content"])
        details(m, i, dernier=(i == len(msgs) - 1 and not question))

if question:
    msgs.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    historique = [{"role": m["role"], "content": m["content"]} for m in msgs[:-1][-8:]]
    with st.chat_message("assistant"):
        with st.spinner("Je réfléchis…"):
            r = copilot.ask(question, role, data, scores, mode="hors_ligne" if hors_ligne else "auto", log_fn=log_action,
                            memoire=st.session_state.memoire, problemes=problemes, historique=historique)
        st.session_state.memoire = r["memoire"]
        ecrire(r["texte"], progressif=True)
        reponse = {"role": "assistant", "content": r["texte"], "meta": r}
        details(reponse, len(msgs), dernier=True)
    msgs.append(reponse)
