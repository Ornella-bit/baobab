import pandas as pd
import streamlit as st
from common import analyse, global_sains, reset_demo, setup, working_data

from core import pii, quality, rbac
from core.trust import couleur

setup("Données")
st.title("1 · Données (DataCompass)")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, issues, sains = analyse()
avant = st.session_state.avant
note_globale = quality.global_score(scores)
sains_globale = global_sains(data, sains)
n_problemes = sum(len(v) for v in issues.values())
EMOJI = {"vert": "🟢", "orange": "🟠", "rouge": "🔴"}

# --- chiffres cles -------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Note globale de qualité", f"{note_globale}", f"{note_globale - avant['note']:+.1f} depuis le départ")
c2.metric("Lignes sans défaut", f"{sains_globale} %", f"{sains_globale - avant['sains']:+.1f} points")
c3.metric("Problèmes détectés", f"{n_problemes}", f"{n_problemes - avant['problemes']:+d}", delta_color="inverse")
c4.metric("Colonnes personnelles", pii.count_pii(data), help="noms, téléphones, e-mails, salaires, dates de naissance")

# --- tableau des fichiers ----------------------------------------------------------------
tableau = pd.DataFrame([{
    "Fichier": f, "Lignes": len(df), "Note": scores[f], "Niveau": EMOJI[couleur(scores[f])],
    "Lignes saines (%)": round(100 * sains[f], 1), "Problèmes": len(issues[f]),
} for f, df in data.items()])
st.dataframe(tableau, hide_index=True, width="stretch")

# --- corrections ---------------------------------------------------------------------------
a_valider = {f: [i for i in lst if i["correction"] is not None] for f, lst in issues.items()}
n_corr = sum(len(v) for v in a_valider.values())
st.subheader("Corrections proposées")
st.write(f"**{n_corr}** corrections automatiques sont proposées. Les autres problèmes (e-mail manquant, valeur "
         "invraisemblable) demandent une décision humaine. Rien n'est modifié sans validation.")
col_a, col_b = st.columns([3, 1])
with col_a:
    if rbac.can_validate(role):
        if st.button(f"✅ Valider les {n_corr} corrections", type="primary", disabled=n_corr == 0):
            for f, lst in a_valider.items():
                for i in lst:
                    i["statut"] = "valide"
                st.session_state.data[f] = quality.apply_corrections(st.session_state.data[f], lst)
            st.session_state.version += 1
            rbac.log_action(role, "valider_corrections", f"{n_corr} corrections validées")
            st.rerun()
    else:
        st.warning("Seul le directeur général peut valider les corrections. Change de rôle dans la barre latérale.")
with col_b:
    if st.button("↩️ Remettre la démo à zéro"):
        reset_demo()
        st.rerun()

# --- detail d'un fichier ----------------------------------------------------------------------
st.subheader("Détail d'un fichier")
fichier = st.selectbox("Fichier", list(data))
masquees = rbac.COLONNES_MASQUEES.get(role, {}).get(fichier, [])
tab_apercu, tab_pb, tab_pii = st.tabs(["Aperçu", "Problèmes", "Données personnelles"])

with tab_apercu:
    st.dataframe(rbac.apply_role(data[fichier], fichier, role).head(200), width="stretch")
    st.caption(f"{len(data[fichier])} lignes · {len(data[fichier].columns)} colonnes")

with tab_pb:
    lst = issues[fichier]
    if not lst:
        st.success("Aucun problème détecté.")
    else:
        par_type = pd.Series([i["type"] for i in lst]).value_counts().rename("nombre")
        st.dataframe(par_type, width="stretch")
        lignes = pd.DataFrame([{
            "type": i["type"], "ligne": i["ligne"], "colonne": i["colonne"],
            "valeur": rbac.MASQUE if i["colonne"] in masquees else i["valeur"],
            "correction proposée": rbac.MASQUE if i["colonne"] in masquees else
            (str(i["correction"]) if i["correction"] is not None else "à traiter par un humain"),
            "explication": rbac.MASQUE if i["colonne"] in masquees else i["note"],
        } for i in lst[:300]])
        st.dataframe(lignes, hide_index=True, width="stretch")
        if len(lst) > 300:
            st.caption(f"Les 300 premiers problèmes sur {len(lst)} sont affichés.")

with tab_pii:
    sensibles = pii.detect_pii(data[fichier])
    if sensibles:
        st.dataframe(pd.DataFrame({"colonne": list(sensibles), "type": list(sensibles.values()),
                                   "protégée pour ce rôle": ["oui" if c in masquees else "non" for c in sensibles]}),
                     hide_index=True, width="stretch")
    else:
        st.info("Aucune donnée personnelle détectée dans ce fichier.")

if rbac.can_validate(role):
    with st.expander("Journal des actions"):
        st.dataframe(rbac.read_log(), hide_index=True, width="stretch")
