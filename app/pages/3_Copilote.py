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

def cle_secrete():
    """Clé d'API : saisie par le visiteur (gardée en mémoire de sa session seulement) ou fournie par l'hébergeur."""
    saisie = st.session_state.get("cle_ia")
    if saisie:
        return saisie
    try:
        return st.secrets.get("ANTHROPIC_API_KEY") or None
    except Exception:  # pas de fichier de secrets
        return None


MOTEURS = {"⚙️ Hors ligne : gratuit, sans Internet": "hors_ligne",
           "🤝 IA en renfort : l'IA aide si le moteur ne comprend pas": "renfort",
           "🤖 IA d'abord : l'IA comprend, les outils calculent": "auto"}
ETIQUETTES = {"llm": "🤖 IA + calculs vérifiés", "hors_ligne": "⚙️ moteur hors ligne", "garde-fou": "🛡️ garde-fou",
              "indisponible": "⚠️ IA indisponible"}

with st.sidebar:
    st.markdown("**Moteur du copilote**")
    cle = cle_secrete()
    with st.expander("🔑 Activer l'IA (facultatif)", expanded=False):
        st.caption("L'application marche sans clé. Avec une clé d'API Anthropic, l'IA comprend les formulations très libres ; "
                   "elle ne calcule jamais : elle appelle les mêmes fonctions vérifiées, et tout chiffre absent de leurs "
                   "résultats est signalé. La clé reste dans ta session : elle n'est ni enregistrée ni journalisée.")
        st.caption("⚠️ Avec l'IA, la question et les résultats des fonctions (sans contacts ni salariés) sont envoyés au "
                   "fournisseur du modèle. Hors ligne, rien ne sort de l'application.")
        saisie = st.text_input("Clé d'API", type="password", value=st.session_state.get("cle_ia", ""), placeholder="sk-ant-…")
        if saisie != st.session_state.get("cle_ia", ""):
            st.session_state.cle_ia = saisie.strip()
            st.rerun()
    if cle:
        choix = st.radio("Moteur", list(MOTEURS), index=1, label_visibility="collapsed")
        moteur = MOTEURS[choix]
    else:
        moteur = "hors_ligne"
        st.caption("⚙️ Moteur hors ligne actif : il comprend la question, interroge une copie des données en lecture seule, "
                   "puis rédige la réponse à partir du résultat.")
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
    if meta.get("chiffres_a_verifier"):
        st.warning("À vérifier : " + ", ".join(meta["chiffres_a_verifier"]) + " ne figure pas dans les résultats des fonctions de "
                   "calcul. L'IA a pu se tromper : ne pas utiliser ce chiffre sans le contrôler.")
    if meta.get("ia_erreur"):
        st.caption(f"L'IA n'a pas répondu ({meta['ia_erreur']}) : réponse du moteur hors ligne.")
    etiquette = ETIQUETTES.get(meta["mode"], meta["mode"].replace("_", " "))
    if meta["sources"]:
        st.caption("Sources : " + ", ".join(meta["sources"]) + f" · {etiquette}")
    else:
        st.caption(etiquette)
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
            r = copilot.ask(question, role, data, scores, mode=moteur, cle=cle, log_fn=log_action,
                            memoire=st.session_state.memoire, problemes=problemes, historique=historique)
        st.session_state.memoire = r["memoire"]
        ecrire(r["texte"], progressif=True)
        reponse = {"role": "assistant", "content": r["texte"], "meta": r}
        details(reponse, len(msgs), dernier=True)
    msgs.append(reponse)
