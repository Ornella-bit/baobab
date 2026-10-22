from pathlib import Path

import streamlit as st
from common import analyse, contracts, setup, working_data
from theme import alert, cards, gauge_card, hero_texte, steps

from core import quality
from core.loader import PARAMS
from core.simulate import simulate_supplier_delay

setup("Accueil")
data = working_data()
scores, issues, sains = analyse()
avant = st.session_state.avant
note = quality.global_score(scores)
sc = PARAMS["scenario"]
sim = simulate_supplier_delay(data, sc["fournisseur_en_retard"], sc["retard_jours"])

with st.container(border=True):
    colonne_texte, colonne_arbre = st.columns([3, 2], gap="medium", vertical_alignment="center")
    colonne_texte.html(hero_texte(PARAMS["societe"]))
    colonne_arbre.image(str(Path(__file__).parent / "assets" / "baobab.png"), width="stretch")

st.html(cards([
    ("🗂️", "ÉTAPE 1 · RACINES", "Données", "Scanner les fichiers, repérer les erreurs et les doublons, corriger avec validation humaine."),
    ("🔗", "ÉTAPE 2 · TRONC", "Chaîne", "Relier fournisseurs, matières, lignes, commandes et clients, et simuler un retard."),
    ("💬", "ÉTAPE 3 · CIME", "Copilote", "Poser une question en français : réponse avec sources et score de confiance."),
]))
c1, c2, c3, c4 = st.columns(4)
c1.page_link("pages/1_Donnees.py", label="Ouvrir les données", icon="🗂️")
c2.page_link("pages/2_Chaine.py", label="Ouvrir la chaîne", icon="🔗")
c3.page_link("pages/3_Copilote.py", label="Ouvrir le copilote", icon="💬")
c4.page_link("pages/4_Tableau_de_bord.py", label="Tableau de bord et rapport PDF", icon="📊")

st.subheader("Essayez le copilote en un clic")
EXEMPLES = ["Que se passe-t-il si Delta a 5 jours de retard ?", "Quel client a passé la plus grosse commande ?",
            "Compare Sigma et Delta", "Combien de lots de sucre avons-nous ?"]
for colonne, exemple in zip(st.columns(len(EXEMPLES)), EXEMPLES):
    if colonne.button(exemple, key=f"ex_{exemple}", width="stretch"):
        st.session_state.en_attente = exemple  # la page Copilote répond dès son ouverture
        st.switch_page("pages/3_Copilote.py")

st.subheader("L'essentiel en un coup d'œil")
g, a = st.columns([1, 2], gap="medium")
with g:
    st.html(gauge_card("NOTE DE QUALITÉ DES DONNÉES", note, avant["note"]))
with a:
    if sim["arret_jour"] is not None:
        st.html(alert("rouge", f"Alerte : la {sim['ligne']} s'arrêterait à J+{sim['arret_jour']}",
                      f"{sc['fournisseur_en_retard']} annonce {sc['retard_jours']} jours de retard · {len(sim['commandes'])} commandes "
                      f"et {len(sim['clients'])} clients touchés. Voir la page Chaîne pour les trois solutions."))
    else:
        st.html(alert("vert", "Aucun arrêt de production prévu", "Les stocks couvrent le retard annoncé."))

st.subheader("Le fil de la démonstration")
st.html(steps([("Scanner", "Les fichiers sont analysés et notés."), ("Corriger", "Le directeur valide les corrections."),
               ("Simuler", "Un retard fournisseur est chiffré."), ("Demander", "Le copilote répond, sources à l'appui.")]))
st.caption(f"Rôle actuel : **{st.session_state.get('role', '—')}** · {len(contracts())} contrats PDF · "
           f"{sum(len(df) for df in data.values()):,} lignes analysées".replace(",", " "))
