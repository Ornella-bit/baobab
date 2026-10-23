import streamlit as st
from common import analyse, db_path, log_action, setup, snapshot, working_data
from theme import acces_refuse, page_header, show_table, steps

from core import db, importer, quality, rbac

setup("Importer")
page_header("📥", "5 · Importer vos fichiers", "Déposez un fichier CSV ou Excel : Baobab Sève reconnaît le type, relie les colonnes et réanalyse tout")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, issues, sains = analyse()
st.session_state.setdefault("import_sauvegarde", None)

st.html(steps([("Déposer", "Un fichier .csv ou .xlsx, même mal présenté."), ("Vérifier", "Le type et les colonnes sont devinés, vous corrigez si besoin."),
               ("Importer", "Tout est testé avant d'être appliqué."), ("Découvrir", "Notes, alertes et copilote se mettent à jour.")]))
st.info("🔒 Vos fichiers restent dans votre session de démonstration (base propre à votre visite). Évitez d'y déposer de vraies données personnelles. "
        "Les fichiers de salaires sont refusés.")

if not rbac.can_validate(role):
    acces_refuse("à l'import de fichiers")
    st.stop()

# --- 1) choisir le fichier ---------------------------------------------------------------------
c1, c2 = st.columns([2, 1], gap="large")
with c1:
    fichier = st.file_uploader("Votre fichier", type=["csv", "xlsx", "xls", "txt"], key="import_fichier")
    st.caption("Pas de fichier sous la main ?")
    if st.button("✨ Essayer avec un fichier d'exemple (export de stocks mal présenté)"):
        contenu, nom = importer.fichier_exemple_stocks()
        st.session_state.import_exemple = (contenu, nom)
        st.rerun()
with c2:
    st.markdown("**Modèles prêts à remplir**")
    for t, meta in importer.TABLES.items():
        st.download_button(f"⬇️ {t}.csv", importer.modele_csv(t), file_name=f"modele_{t}.csv", key=f"modele_{t}", width="stretch")

source = None
if fichier is not None:
    source = (fichier.getvalue(), fichier.name)
    st.session_state.pop("import_exemple", None)
elif st.session_state.get("import_exemple"):
    source = st.session_state.import_exemple
    st.caption(f"Fichier d'exemple chargé : {source[1]}")

# --- 2) analyse du fichier -----------------------------------------------------------------------
if source:
    try:
        df = importer.lire_fichier(*source)
    except importer.ErreurImport as e:
        st.error(str(e))
        st.stop()
    refus = importer.refus_confidentialite(df)
    if refus:
        st.error("🔒 " + refus)
        st.stop()

    classement = importer.detecter_table(df)
    meilleur, part = classement[0]
    st.subheader("Ce que j'ai compris")
    if part < 0.5:
        st.warning("Je ne reconnais pas clairement ce fichier. Choisissez le type ci-dessous et reliez les colonnes à la main.")
    table = st.selectbox("Type de fichier", list(importer.TABLES), index=list(importer.TABLES).index(meilleur),
                         format_func=lambda t: importer.TABLES[t]["label"], key=f"table_{source[1]}")
    if table == meilleur and part >= 0.5:
        st.success(f"Fichier reconnu : **{importer.TABLES[table]['label']}** ({int(part * 100)} % des colonnes retrouvées, {len(df)} lignes).")

    lien_auto = importer.relier_colonnes(df, table)
    st.markdown("**Correspondance des colonnes** (modifiable)")
    options = ["(aucune)"] + list(df.columns)
    lien = {}
    cols = st.columns(3)
    for i, cible in enumerate(importer.TABLES[table]["colonnes"]):
        defaut = options.index(lien_auto[cible]) if lien_auto[cible] else 0
        choix = cols[i % 3].selectbox(f"« {cible} »", options, index=defaut, key=f"lien_{source[1]}_{table}_{cible}")
        lien[cible] = None if choix == "(aucune)" else choix
    with st.expander("👀 Aperçu du fichier (10 premières lignes)", expanded=True):
        show_table(df.head(10), hide_index=True)

    nouveau, rapport = importer.preparer(df, table, lien)
    if rapport["manquantes"]:
        st.error("Colonnes obligatoires non reliées : " + ", ".join(rapport["manquantes"]) + ".")
        st.stop()
    for a in rapport["avertissements"]:
        st.warning(a)
    if rapport["ignorees"]:
        st.caption("Colonnes du fichier non utilisées : " + ", ".join(rapport["ignorees"]) + ".")

    # --- 3) essai avant d'appliquer ------------------------------------------------------------------
    mode = st.radio("Que faire des lignes du fichier ?", ["remplacer", "ajouter"], horizontal=True,
                    format_func=lambda m: {"remplacer": f"Remplacer toute la table « {table} »", "ajouter": f"Ajouter à la table « {table} »"}[m])
    candidat, erreur = importer.appliquer(data, table, nouveau, mode)
    if erreur:
        st.error("⛔ Import impossible pour l'instant. " + erreur)
        st.stop()
    apres = quality.all_scores(candidat)
    st.subheader("Effet de l'import (essai à blanc, rien n'est encore modifié)")
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Lignes de « {table} »", len(candidat[table]), f"{len(candidat[table]) - len(data[table]):+d}")
    m2.metric(f"Note de « {table} »", f"{apres[table]:g}".replace(".", ","), f"{apres[table] - scores[table]:+.1f}".replace(".", ","))
    m3.metric("Note globale", f"{quality.global_score(apres):g}".replace(".", ","), f"{quality.global_score(apres) - quality.global_score(scores):+.1f}".replace(".", ","))

    if st.button("✅ Importer et réanalyser", type="primary"):
        st.session_state.import_sauvegarde = {"table": table, "df": data[table].copy()}
        st.session_state.data = candidat
        db.save_tables(candidat, db_path())
        st.session_state.version += 1
        log_action(role, "import_fichier", f"{table} : {len(nouveau)} lignes ({mode}) depuis {source[1]}")
        snapshot(f"import {table}")
        st.session_state.pop("import_exemple", None)
        st.toast(f"{len(nouveau)} lignes importées dans « {table} »", icon="📥")
        st.success("Import réussi. Les notes, les alertes, le graphe et le copilote utilisent maintenant vos données.")
        st.rerun()

# --- 4) annuler -----------------------------------------------------------------------------------
sauv = st.session_state.import_sauvegarde
if sauv:
    st.divider()
    st.caption(f"Dernier import : table « {sauv['table']} ». Vous pouvez revenir en arrière.")
    if st.button("↩️ Annuler le dernier import"):
        st.session_state.data[sauv["table"]] = sauv["df"]
        db.save_tables(st.session_state.data, db_path())
        st.session_state.version += 1
        log_action(role, "annuler_import", sauv["table"])
        snapshot(f"annulation import {sauv['table']}")
        st.session_state.import_sauvegarde = None
        st.rerun()
