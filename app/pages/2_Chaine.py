import pandas as pd
import streamlit as st
from common import analyse, db_path, log_action, setup, working_data
from theme import acces_refuse, bars_html, heatmap_html, page_header, show_svg, show_table, trust_html
from visuals import chain_svg

from core import db, explorer, rbac, whatif
from core.graph import ORDRE, build_graph
from core.loader import PARAMS
from core.simulate import list_options, scenario_par_defaut, simulate_supplier_delay
from core.trust import trust_score

setup("Chaîne")
page_header("🔗", "2 · Chaîne de production", "SupplyMind : relier la chaîne de bout en bout et simuler un retard")
role = st.session_state.get("role", rbac.ROLES[0])
data = working_data()
scores, _, _ = analyse()
sc = PARAMS["scenario"]
EMOJI_RISQUE = {"faible": "🟢", "moyen": "🟠", "eleve": "🔴"}


def nombre(n):
    return f"{n:,}".replace(",", " ")


@st.cache_data(show_spinner=False)
def _graphe(version, _data):
    return build_graph(_data)


@st.cache_data(show_spinner=False)
def _svg(version, fournisseur, retard, _graphe, noeuds, source_active):
    return chain_svg(_graphe, noeuds, source=fournisseur if source_active else None)


@st.cache_data(show_spinner=False)
def _svg_focus(version, noeud, _graphe):
    return chain_svg(_graphe, focus=noeud)


@st.cache_data(show_spinner=False)
def _carte(version, _data):
    return whatif.carte_des_risques(_data, 10)


def choisir(label, options, cle, defaut=None):
    """Boutons cliquables (st.pills) ; liste deroulante si la version de Streamlit est ancienne."""
    try:
        choix = st.pills(label, options, selection_mode="single", default=defaut if defaut in options else options[0], key=cle,
                         format_func=lambda o: explorer.TITRES.get(o, o).replace("concentre", "concentré").replace("_", " "))
    except AttributeError:
        choix = st.selectbox(label, options, index=options.index(defaut) if defaut in options else 0, key=cle)
    return choix or (defaut if defaut in options else options[0])


@st.fragment
def simulation():
    """Fragment : bouger le curseur ou changer de fournisseur ne recharge que cette zone (la page reste fluide)."""
    # --- parametres de la simulation --------------------------------------------------------------
    fournisseurs = sorted(data["fournisseurs"]["fournisseur"].unique())
    defaut = scenario_par_defaut(data)
    col1, col2 = st.columns([1, 2])
    fournisseur = col1.selectbox("Fournisseur en retard", fournisseurs,
                                 index=fournisseurs.index(defaut[0]))
    retard = col2.slider("Retard annoncé (jours)", 0, 10, defaut[1])
    sim = simulate_supplier_delay(data, fournisseur, retard)

    # --- resultat --------------------------------------------------------------------------------
    if sim["ligne"] is None:
        st.info(f"{fournisseur} ne fournit aucune matière utilisée par une ligne de production.")
    elif sim["arret_jour"] is None:
        st.success(f"✅ Aucun arrêt prévu : la {sim['ligne']} a {sim['couverture_jours']:.0f} jours de stock de "
                   f"{sim['matiere'].replace('_', ' ')}, plus que le retard de {retard} jours.")
    else:
        st.error(f"⚠️ La {sim['ligne']} s'arrêterait à **J+{sim['arret_jour']}** faute de "
                 f"{sim['matiere'].replace('_', ' ')}.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Couverture de stock", f"{sim['couverture_jours']:.0f} jours" if sim["couverture_jours"] is not None else "—")
    m2.metric("Arrêt de production", f"J+{sim['arret_jour']}" if sim["arret_jour"] is not None else "Aucun")
    m3.metric("Manque", f"{nombre(sim['manque'])} unités")
    m4.metric("Commandes menacées", len(sim["commandes"]))
    m5.metric("Clients touchés", len(sim["clients"]))

    # --- confiance -------------------------------------------------------------------------------
    t = trust_score(["stocks", "production", "fournisseurs", "commandes"], scores)
    st.html("<b>Confiance de cette analyse</b> &nbsp; " + trust_html(t, scores))
    if t["a_confirmer"]:
        st.warning("Confiance basse : à confirmer avant de décider. Corrige d'abord les données (page 1).")

    # --- graphe ----------------------------------------------------------------------------------
    st.subheader("La chaîne de bout en bout")
    graphe = _graphe(st.session_state.version, data)
    show_svg(_svg(st.session_state.version, fournisseur, retard, graphe, sim["noeuds_impactes"], sim["arret_jour"] is not None))

    # --- commandes menacees et options -------------------------------------------------------------
    if sim["commandes_detail"]:
        st.subheader("Commandes menacées")
        tableau = pd.DataFrame(sim["commandes_detail"]).rename(columns={
            "commande_id": "Commande", "client": "Client", "produit": "Produit", "quantite": "Quantité",
            "date_livraison": "Livraison", "jour": "Jour"})
        show_table(tableau, hide_index=True)

    options = list_options(data, sim)
    if options:
        st.subheader("Trois solutions")
        for colonne, o in zip(st.columns(3), options):
            with colonne.container(border=True):
                st.markdown(f"**Option {o['code']}** {'✅ faisable' if o['faisable'] else '❌ impossible'}")
                st.write(o["libelle"])
                st.write(f"Surcoût : **+{o['surcout_pct']:g} %** · Risque : {EMOJI_RISQUE[o['risque']]} {o['risque'].replace('eleve', 'élevé')}")
                if o["faisable"]:
                    if rbac.can_validate(role):
                        if st.button(f"Retenir l'option {o['code']}", key=f"option_{o['code']}"):
                            st.session_state["option_retenue"] = o["code"]
                            log_action(role, "option_retenue", f"{fournisseur} {retard} j : option {o['code']}")
                            db.add_decision(role, fournisseur, retard, o["code"], o["libelle"], db_path())
                            st.toast(f"Option {o['code']} retenue et inscrite au journal", icon="✅")
                    else:
                        acces_refuse("à cette décision")
        if st.session_state.get("option_retenue"):
            st.success(f"Option {st.session_state['option_retenue']} retenue et inscrite au journal des actions.")

    # --- decisions prises (base de donnees) -------------------------------------------------------
    st.subheader("Décisions prises")
    if rbac.can_validate(role):
        decisions = db.read_decisions(db_path())
        if decisions.empty:
            st.caption("Aucune décision retenue pour le moment : chaque décision sera conservée dans la base de données.")
        else:
            show_table(decisions.rename(columns={"horodatage": "Date", "role": "Rôle", "fournisseur": "Fournisseur",
                                                   "retard_jours": "Retard (jours)", "option_code": "Option", "libelle": "Solution"}),
                         hide_index=True)
    else:
        acces_refuse("aux décisions prises")

    # --- aller plus loin : et si ?, explorer, carte des risques ------------------------------------
    st.subheader("Aller plus loin")
    t_si, t_exp, t_carte = st.tabs(["🎛️ Et si… ?", "🧭 Explorer la chaîne", "🔥 Carte des risques"])

    with t_si:
        if sim["ligne"] is None:
            st.info("Choisissez un fournisseur qui alimente une ligne de production pour tester des scénarios.")
        else:
            st.caption(f"Scénario testé : {fournisseur} avec {retard} jours de retard, sur la {sim['ligne']} "
                       f"({sim['matiere'].replace('concentre', 'concentré').replace('_', ' ')}). Les données d'origine ne sont pas modifiées.")
            s1, s2 = st.columns(2)
            conso_pct = s1.slider("Variation de la consommation (%)", -30, 50, 0, 5, key="si_conso",
                                  help="Une commande exceptionnelle (+) ou un ralentissement de la ligne (-).")
            stock_plus = s2.slider("Stock supplémentaire disponible (unités)", 0, 10000, 0, 100, key="si_stock",
                                   help="Par exemple un transfert depuis un autre entrepôt.")
            cmp = whatif.comparer(data, fournisseur, retard, conso_pct, stock_plus, sim["ligne"], sim["matiere"])
            av, ap = cmp["avant"], cmp["apres"]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Manque", f"{nombre(ap['manque'])} unités", f"{ap['manque'] - av['manque']:+,}".replace(",", " ") if ap["manque"] != av["manque"] else None,
                      delta_color="inverse")
            k2.metric("Arrêt de production", f"J+{ap['arret_jour']}" if ap["arret_jour"] is not None else "Aucun",
                      "évité" if (av["arret_jour"] is not None and ap["arret_jour"] is None) else None)
            k3.metric("Commandes menacées", len(ap["commandes"]), f"{len(ap['commandes']) - len(av['commandes']):+d}" if len(ap["commandes"]) != len(av["commandes"]) else None,
                      delta_color="inverse")
            avant_supp, apres_supp = whatif.retard_supportable(data, fournisseur), whatif.retard_supportable(whatif.modifier(data, conso_pct, stock_plus, sim["ligne"], sim["matiere"]), fournisseur)
            k4.metric("Retard supportable", f"{apres_supp:g} jours".replace(".", ","), f"{apres_supp - avant_supp:+.1f}".replace(".", ",") if apres_supp != avant_supp else None)
            if av["manque"] > 0 and ap["manque"] > 0:
                st.warning(f"Pour absorber {retard} jours de retard sans arrêt, il faudrait au moins **{nombre(ap['manque'])} unités** de stock en plus.")
            elif av["manque"] > 0:
                st.success("Avec ce scénario, la production ne s'arrête pas.")
            mod = whatif.modifier(data, conso_pct, stock_plus, sim["ligne"], sim["matiere"])
            courbe_av, courbe_ap = whatif.sensibilite(data, fournisseur, 12), whatif.sensibilite(mod, fournisseur, 12)
            haut = max([c["manque"] for c in courbe_av + courbe_ap] + [1])
            ga, gb = st.columns(2)
            ga.markdown("**Manque selon le retard : situation actuelle**")
            ga.html(bars_html([(f"{c['jours']} jours", c["manque"], nombre(c["manque"]), "#D6334A" if c["manque"] else "#3E8E5E") for c in courbe_av], maximum=haut))
            gb.markdown("**Manque selon le retard : avec votre scénario**")
            gb.html(bars_html([(f"{c['jours']} jours", c["manque"], nombre(c["manque"]), "#D6334A" if c["manque"] else "#3E8E5E") for c in courbe_ap], maximum=haut))

    with t_exp:
        st.caption("Cliquez sur un type, puis sur un élément : tout ce qui lui est relié s'allume, le reste s'estompe.")
        groupes = explorer.noeuds_par_type(graphe)
        type_choisi = choisir("Type d'élément", [t for t in ORDRE if groupes[t]], "ex_type", "fournisseur")
        noeud = choisir("Élément", groupes[type_choisi], f"ex_noeud_{type_choisi}")
        show_svg(_svg_focus(st.session_state.version, noeud, graphe))
        f = explorer.fiche(data, graphe, noeud)
        with st.container(border=True):
            st.markdown(f"**{f['titre']}**")
            for libelle, valeur in f["faits"]:
                st.markdown(f"- {libelle} : **{valeur}**")
            if f["alerte"]:
                st.warning(f["alerte"])
        ca, cb = st.columns(2)
        ca.markdown("**En amont** (ce dont il dépend)")
        ca.write(", ".join(n.replace("concentre", "concentré").replace("_", " ") for n in f["amont"]) or "Rien : c'est un point de départ.")
        cb.markdown("**En aval** (ce qu'il touche)")
        cb.write(", ".join(n.replace("concentre", "concentré").replace("_", " ") for n in f["aval"]) or "Rien : c'est un point d'arrivée.")

    with t_carte:
        st.caption("Unités manquantes pour chaque fournisseur selon le retard annoncé (jours). Vert : aucun manque.")
        carte = _carte(st.session_state.version, data)
        st.html(heatmap_html(list(carte), [f"{j} j" for j in range(11)], list(carte.values()), "Fournisseur"))
        supportables = {f: whatif.retard_supportable(data, f) for f in carte}
        st.caption("Retard supportable sans arrêt : " + " · ".join(f"{f} {v:g} jours".replace(".", ",") for f, v in supportables.items() if v is not None) + ".")


simulation()
