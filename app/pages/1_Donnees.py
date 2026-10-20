from pathlib import Path

import pandas as pd
import streamlit as st
from common import (analyse, db_path, global_sains, record_validation, reset_demo, setup, undo_last_validation,
                    working_data)
from theme import acces_refuse, gauge_card, page_header, show_line, show_table

from core import db, pii, quality, rbac
from core.trust import couleur

setup("Données")
page_header("🗂️", "1 · Données", "DataCompass : scanner, corriger et protéger les données de l'entreprise")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, issues, sains = analyse()
avant = st.session_state.avant
note_globale = quality.global_score(scores)
sains_globale = global_sains(data, sains)
n_problemes = sum(len(v) for v in issues.values())
EMOJI = {"vert": "🟢", "orange": "🟠", "rouge": "🔴"}

# --- chiffres cles -------------------------------------------------------------------------
cg, ck = st.columns([1, 2], gap="medium")
cg.html(gauge_card("NOTE DE QUALITÉ", note_globale, avant["note"] if avant["note"] != note_globale else None))
with ck:
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    c1.metric("Note globale de qualité", f"{note_globale}", f"{note_globale - avant['note']:+.1f} depuis le départ")
    c2.metric("Lignes sans défaut", f"{sains_globale} %", f"{sains_globale - avant['sains']:+.1f} points")
    c3.metric("Problèmes détectés", f"{n_problemes}", f"{n_problemes - avant['problemes']:+d}", delta_color="inverse")
    c4.metric("Colonnes personnelles", pii.count_pii(data), help="noms, téléphones, e-mails, salaires, dates de naissance")

# --- tableau des fichiers ----------------------------------------------------------------
tableau = pd.DataFrame([{
    "Fichier": f, "Lignes": len(df), "Note": scores[f], "Niveau": EMOJI[couleur(scores[f])],
    "Lignes saines (%)": round(100 * sains[f], 1), "Problèmes": len(issues[f]),
} for f, df in data.items()])
show_table(tableau, hide_index=True)

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
            avant_donnees = {f: df.copy() for f, df in st.session_state.data.items()}
            for f, lst in a_valider.items():
                for i in lst:
                    i["statut"] = "valide"
                st.session_state.data[f] = quality.apply_corrections(st.session_state.data[f], lst)
            record_validation(role, avant_donnees, f"{n_corr} corrections validées")
            st.rerun()
    else:
        acces_refuse("à la validation des corrections")
with col_b:
    if st.button("↩️ Remettre la démo à zéro"):
        reset_demo()
        st.rerun()

# --- evolution et historique (base de donnees) ---------------------------------------------
st.subheader("Évolution de la note de qualité")
instantanes = db.read_snapshots(db_path())
if len(instantanes) >= 2:
    courbe = instantanes.assign(Étape=[f"{i + 1}. {e}" for i, e in enumerate(instantanes["evenement"])]).set_index("Étape")
    show_line(list(courbe.index), [float(v) for v in courbe["note"]])
else:
    st.caption("La courbe apparaît après la première validation : chaque étape est conservée dans la base de données.")

st.subheader("Historique des validations")
if rbac.can_validate(role):
    lots = db.read_lots(db_path())
    if lots.empty:
        st.caption("Aucune validation pour le moment.")
    else:
        show_table(lots.assign(annule=lots["annule"].map({0: "", 1: "annulée"})).rename(columns={
            "id": "N°", "horodatage": "Date", "role": "Rôle", "resume": "Résumé", "nb_changements": "Changements",
            "annule": "État"}), hide_index=True)
        if db.can_undo(db_path()):
            if st.button("↩️ Annuler la dernière validation"):
                undo_last_validation(role)
                st.rerun()
else:
    acces_refuse("à l'historique des validations")

with st.expander("🗄️ Base de données (SQLite)"):
    if rbac.can_validate(role):
        st.caption("Les données, les validations, le journal et les décisions sont stockés dans une base SQLite "
                   "propre à chaque visiteur. Requêtes en lecture seule uniquement.")
        show_table(pd.DataFrame({"table": list(db.table_counts(db_path())), "lignes": list(db.table_counts(db_path()).values())}),
                     hide_index=True)
        sql = st.text_area("Requête SQL (SELECT)", value="SELECT ville, COUNT(*) AS clients FROM clients GROUP BY ville ORDER BY clients DESC",
                           height=90)
        if st.button("▶️ Exécuter la requête"):
            try:
                show_table(db.run_select(sql, db_path()), hide_index=True)
            except Exception as e:
                st.error(f"Requête refusée ou invalide : {e}")
        st.download_button("⬇️ Télécharger la base (.db)", data=Path(db_path()).read_bytes(), file_name="baobab_seve.db")
    else:
        acces_refuse("à la base de données")

# --- detail d'un fichier ----------------------------------------------------------------------
st.subheader("Détail d'un fichier")
fichier = st.selectbox("Fichier", list(data))
masquees = rbac.COLONNES_MASQUEES.get(role, {}).get(fichier, [])
tab_apercu, tab_pb, tab_pii = st.tabs(["Aperçu", "Problèmes", "Données personnelles"])

with tab_apercu:
    if masquees:
        acces_refuse("aux colonnes " + ", ".join(masquees) + " de ce fichier")
    show_table(rbac.apply_role(data[fichier], fichier, role).head(200))
    st.caption(f"{len(data[fichier])} lignes · {len(data[fichier].columns)} colonnes")

with tab_pb:
    lst = issues[fichier]
    if masquees:
        acces_refuse("aux valeurs des colonnes " + ", ".join(masquees))
    if not lst:
        st.success("Aucun problème détecté.")
    else:
        par_type = pd.Series([i["type"] for i in lst]).value_counts().rename("nombre")
        show_table(par_type)
        lignes = pd.DataFrame([{
            "type": i["type"], "ligne": i["ligne"], "colonne": i["colonne"],
            "valeur": rbac.MASQUE if i["colonne"] in masquees else i["valeur"],
            "correction proposée": rbac.MASQUE if i["colonne"] in masquees else
            (str(i["correction"]) if i["correction"] is not None else "à traiter par un humain"),
            "explication": rbac.MASQUE if i["colonne"] in masquees else i["note"],
        } for i in lst[:300]])
        show_table(lignes, hide_index=True)
        if len(lst) > 300:
            st.caption(f"Les 300 premiers problèmes sur {len(lst)} sont affichés.")

with tab_pii:
    sensibles = pii.detect_pii(data[fichier])
    if sensibles:
        show_table(pd.DataFrame({"colonne": list(sensibles), "type": list(sensibles.values()),
                                   "protégée pour ce rôle": ["oui" if c in masquees else "non" for c in sensibles]}),
                     hide_index=True)
    else:
        st.info("Aucune donnée personnelle détectée dans ce fichier.")

st.subheader("Journal des actions")
if rbac.can_validate(role):
    with st.expander("Voir le journal"):
        show_table(db.read_log(db_path()), hide_index=True)
else:
    acces_refuse("au journal des actions")
