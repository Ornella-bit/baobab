"""Habillage de l'application : feuille de style, en-tetes de page, pastilles, cartes (aux couleurs de la fiche)."""
import streamlit as st

CSS = """
<style>
.stApp { font-family: 'Segoe UI', 'Helvetica Neue', system-ui, -apple-system, sans-serif; }
.bb-h1, .bb-t, .stApp h2, .stApp h3 { font-family: 'Playfair Display', Georgia, 'Times New Roman', serif; }
.block-container { padding-top: 4.5rem; max-width: 1180px; }
h2, h3 { color: #24543B; letter-spacing: -0.01em; }
[data-testid="stMetric"] { background: #F9F5E9; border: 1px solid #DDD3BC; border-radius: 14px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(20,32,27,.04); }
[data-testid="stSidebar"] { border-right: 1px solid #DDD3BC; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
.stButton > button p, .stButton > button div { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
.stButton > button { height: auto; min-height: 2.6rem; padding: .5rem .8rem; line-height: 1.3; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; font-size: 1.9rem !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
.bb-tbl-wrap { max-height: 430px; overflow: auto; border: 1px solid #DDD3BC; border-radius: 12px; background: #FBF8F0; margin-bottom: .6rem; }
.bb-tbl { border-collapse: collapse; width: 100%; font-size: .86rem; color: #202923; }
.bb-tbl th { position: sticky; top: 0; background: #F0E9D6; color: #24543B; text-align: left; font-weight: 700; padding: 8px 12px; border-bottom: 2px solid #24543B; white-space: nowrap; }
.bb-tbl td { padding: 7px 12px; border-bottom: 1px solid #E7DFC9; vertical-align: top; }
.bb-tbl tr:nth-child(even) td { background: #F6F1E3; }
.bb-head { display: flex; align-items: center; gap: 14px; margin: 0 0 1.1rem 0; }
.bb-ico { width: 48px; height: 48px; border-radius: 14px; background: #F9F5E9; border: 1px solid #DDD3BC; font-size: 26px; display: flex; align-items: center; justify-content: center; flex: none; }
.bb-t { font-size: 1.7rem; font-weight: 800; color: #202923; line-height: 1.15; letter-spacing: -0.02em; }
.bb-s { font-size: .95rem; color: #5E655E; margin-top: 2px; }
.bb-kick { font-size: .78rem; font-weight: 700; letter-spacing: .14em; color: #24543B; text-transform: uppercase; }
.bb-h1 { font-size: 3.2rem; font-weight: 700; color: #202923; letter-spacing: -0.03em; line-height: 1.05; margin: 6px 0 8px; }
.bb-tag { font-size: 1.25rem; font-weight: 600; color: #C95635; margin: 0 0 12px; font-family: 'Playfair Display', Georgia, serif; font-style: italic; }
.bb-lead { font-size: 1.12rem; color: #202923; line-height: 1.45; margin-bottom: 14px; }
.bb-pts { display: flex; flex-wrap: wrap; gap: 8px; }
.bb-pt { background: #F9F5E9; border: 1px solid #DDD3BC; border-radius: 999px; padding: 6px 12px; font-size: .86rem; color: #202923; font-weight: 600; }
.bb-card { background: #F9F5E9; border: 1px solid #DDD3BC; border-radius: 16px; padding: 18px 20px 14px; height: 100%;
  box-shadow: 0 1px 2px rgba(20,32,27,.04); }
.bb-card .i { width: 42px; height: 42px; border-radius: 12px; background: #EADFC9; font-size: 22px; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.bb-card .k { font-size: .75rem; font-weight: 700; letter-spacing: .12em; color: #5E655E; }
.bb-card .t { font-size: 1.2rem; font-weight: 800; color: #202923; margin: 2px 0 6px; }
.bb-card .d { font-size: .93rem; color: #5E655E; line-height: 1.4; }
.bb-steps { display: flex; flex-wrap: wrap; gap: 10px; margin: .4rem 0 1.2rem; }
.bb-step { flex: 1 1 200px; background: #F9F5E9; border: 1px solid #DDD3BC; border-radius: 14px; padding: 12px 14px; display: flex; gap: 10px; align-items: flex-start; }
.bb-step .n { width: 26px; height: 26px; border-radius: 50%; background: #24543B; color: #F6F0E5; font-weight: 800; font-size: .85rem;
  display: flex; align-items: center; justify-content: center; flex: none; }
.bb-step b { display: block; color: #202923; font-size: .95rem; }
.bb-step span { color: #5E655E; font-size: .84rem; }
.bb-chip { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 14px; font-weight: 700; font-size: .92rem; border: 1px solid; }
.bb-chip.vert { background: #E8F5EA; color: #1F6A31; border-color: #B7DDBF; }
.bb-chip.orange { background: #FDEFE3; color: #B4470F; border-color: #F4C9A8; }
.bb-chip.rouge { background: #FBE3E7; color: #B2243B; border-color: #F1B3BE; }
.bb-chip i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; background: currentColor; }
.bb-note { color: #5E655E; font-size: .86rem; margin-left: 10px; }
.bb-alert { border-radius: 16px; padding: 16px 20px; border: 1px solid; display: flex; gap: 14px; align-items: center; }
.bb-alert.rouge { background: #FBE3E7; border-color: #F1B3BE; }
.bb-alert.vert { background: #E8F5EA; border-color: #B7DDBF; }
.bb-alert .big { font-size: 1.5rem; font-weight: 800; color: #202923; line-height: 1.2; }
.bb-alert .sm { color: #5E655E; font-size: .92rem; margin-top: 2px; }
.bb-gauge { background: #F9F5E9; border: 1px solid #DDD3BC; border-radius: 16px; padding: 14px 16px 12px; text-align: center; height: 100%; }
.bb-gauge .l { font-size: .78rem; font-weight: 700; letter-spacing: .1em; color: #5E655E; }
.bb-ring { width: 150px; height: 150px; border-radius: 50%; margin: 12px auto 8px; display: flex; align-items: center; justify-content: center; }
.bb-ring .in { width: 114px; height: 114px; border-radius: 50%; background: #F9F5E9; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.bb-ring b { font-size: 2rem; font-weight: 800; color: #202923; line-height: 1; }
.bb-ring span { font-size: .78rem; color: #5E655E; margin-top: 4px; }
.bb-lock { display: flex; align-items: center; gap: 10px; background: #F3E9D6; border: 1px solid #E2CFA6; color: #6B4E12; border-radius: 12px; padding: 10px 14px; font-weight: 600; font-size: .92rem; margin: .3rem 0; }
.bb-role { display: inline-block; background: #EADFC9; color: #24543B; border-radius: 999px; padding: 4px 12px; font-size: .84rem; font-weight: 700; }
.bb-card, .bb-step, .bb-gauge, [data-testid="stMetric"] { transition: transform .18s ease, box-shadow .18s ease; }
.bb-card:hover, .bb-step:hover, .bb-gauge:hover, [data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(36,84,59,.12); }
.stButton > button { transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(36,84,59,.15); border-color: #24543B; }
[data-testid="stChatMessage"] { border-radius: 16px; border: 1px solid #E7DFC9; background: #FBF8F0; padding: .9rem 1.1rem; margin-bottom: .6rem; }
[data-testid="stChatInput"] { border-radius: 14px; }
[data-testid="stExpander"] { border-radius: 12px; border-color: #DDD3BC; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
.bb-al { display: flex; gap: 12px; align-items: flex-start; border-radius: 14px; padding: 12px 16px; border: 1px solid; margin-bottom: 8px; }
.bb-al.rouge { background: #FBE3E7; border-color: #F1B3BE; } .bb-al.orange { background: #FDEFE3; border-color: #F4C9A8; } .bb-al.vert { background: #E8F5EA; border-color: #B7DDBF; }
.bb-al .pt { width: 12px; height: 12px; border-radius: 50%; margin-top: 5px; flex: none; }
.bb-al.rouge .pt { background: #D6334A; } .bb-al.orange .pt { background: #E08A3C; } .bb-al.vert .pt { background: #3E8E5E; }
.bb-al b { color: #202923; font-size: .95rem; } .bb-al span { display: block; color: #5E655E; font-size: .86rem; margin-top: 2px; }
.bb-al .pg { margin-left: auto; font-size: .75rem; font-weight: 700; color: #5E655E; letter-spacing: .06em; text-transform: uppercase; white-space: nowrap; }
.bb-bar { display: flex; align-items: center; gap: 10px; margin: 7px 0; font-size: .9rem; color: #202923; }
.bb-bar .n { flex: 0 0 150px; } .bb-bar .v { flex: 0 0 64px; text-align: right; font-weight: 700; }
.bb-bar .t { flex: 1; height: 12px; background: #EFE8D5; border-radius: 999px; overflow: hidden; }
.bb-bar .t i { display: block; height: 100%; border-radius: 999px; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(emoji, titre, sous_titre):
    st.html(f"<div class='bb-head'><div class='bb-ico'>{emoji}</div>"
            f"<div><div class='bb-t'>{titre}</div><div class='bb-s'>{sous_titre}</div></div></div>")


def acces_refuse(ce_quoi):
    """Message d'acces refuse : affiche a chaque fois, sans inviter a changer de role."""
    st.html(f"<div class='bb-lock'><span>🔒</span><span>Vous n'avez pas accès {ce_quoi}.</span></div>")


def chip(couleur, texte):
    """Pastille de confiance : couleur = vert / orange / rouge."""
    return f"<span class='bb-chip {couleur}'><i></i>{texte}</span>"


def trust_html(t, scores):
    """Bloc de confiance d'une reponse : pastille + source la plus faible."""
    note = f"<span class='bb-note'>source la plus faible : {t['plus_faible']} ({scores[t['plus_faible']]})</span>"
    return chip(t["couleur"], f"Confiance {t['score']} / 100" + (" · à confirmer" if t["a_confirmer"] else "")) + note


def hero_texte(societe):
    return ("<div class='bb-kick'>Démo · données fictives de " + societe + "</div>"
            "<div class='bb-h1'>Baobab <span style='color:#24543B'>Sève</span></div>"
            "<div class='bb-tag'>De la donnée à la décision.</div>"
            "<div class='bb-lead'>Des racines propres, un tronc qui relie tout, une cime qui éclaire les décisions : "
            "vos données deviennent fiables, et votre chaîne de production reste sous contrôle.</div>"
            "<div class='bb-pts'><span class='bb-pt'>Données nettoyées</span><span class='bb-pt'>Chaîne reliée</span>"
            "<span class='bb-pt'>Copilote qui cite ses sources</span><span class='bb-pt'>Confiance affichée</span></div>")


def show_svg(svg):
    """Affiche un SVG dessine par le programme (st.html retire les SVG, st.image les accepte)."""
    try:
        st.image(svg, width="stretch")
    except TypeError:  # anciennes versions de Streamlit
        st.image(svg, use_container_width=True)


def cards(textes):
    """textes : liste de (icone, kicker, titre, description)."""
    html = "".join(f"<div style='flex:1 1 240px'><div class='bb-card'><div class='i'>{i}</div>"
                   f"<div class='k'>{k}</div><div class='t'>{t}</div><div class='d'>{d}</div></div></div>" for i, k, t, d in textes)
    return f"<div style='display:flex;flex-wrap:wrap;gap:14px;margin-bottom:10px'>{html}</div>"


def steps(liste):
    html = "".join(f"<div class='bb-step'><div class='n'>{n}</div><div><b>{t}</b><span>{d}</span></div></div>"
                   for n, (t, d) in enumerate(liste, 1))
    return f"<div class='bb-steps'>{html}</div>"


def gauge_card(titre, score, prev=None):
    """Jauge en CSS pur (conic-gradient) : elle ne depend d'aucune image."""
    deg = max(0, min(100, score)) * 3.6
    depart = f"<div class='bb-note' style='margin:0'>au départ : {prev}</div>" if prev is not None and prev != score else ""
    return (f"<div class='bb-gauge'><div class='l'>{titre}</div>"
            f"<div class='bb-ring' style='background:conic-gradient(#3E8E5E 0deg {deg:.1f}deg, #DDD3BC {deg:.1f}deg 360deg)'>"
            f"<div class='in'><b>{score}</b><span>sur 100</span></div></div>{depart}</div>")


def alert_rows(alertes):
    """Liste d'alertes (core.alerts.compute_alerts) en cartes colorees."""
    return "".join(f"<div class='bb-al {a['niveau']}'><div class='pt'></div><div><b>{a['titre']}</b><span>{a['detail']}</span></div>"
                   f"<div class='pg'>{a['page']}</div></div>" for a in alertes)


def bars_html(items, maximum=100):
    """Barres horizontales en HTML pur. items : liste de (libelle, valeur, texte_valeur, couleur_css)."""
    html = "".join(f"<div class='bb-bar'><div class='n'>{n}</div><div class='t'><i style='width:{max(2, min(100, 100 * v / maximum)):.1f}%;background:{c}'></i></div>"
                   f"<div class='v'>{t}</div></div>" for n, v, t, c in items)
    return f"<div>{html}</div>"


def alert(couleur, grand, petit):
    return f"<div class='bb-alert {couleur}'><div><div class='big'>{grand}</div><div class='sm'>{petit}</div></div></div>"


# --- affichage robuste des tableaux et courbes ---------------------------------------------------
# st.dataframe et st.line_chart reposent sur la bibliotheque pyarrow. Sur certains ordinateurs Windows, une
# strategie de securite (« Application Control ») bloque ses fichiers : l'application bascule alors, sans erreur,
# sur un affichage HTML/SVG qui n'en a pas besoin.
_ARROW_OK = {"ok": True}


def _echappe(v):
    import html
    import pandas as pd
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        return html.escape(str(int(v)))
    return html.escape(str(v))


def _tableau_html(df, hide_index):
    import pandas as pd
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df = df.head(300)
    cols = list(df.columns)
    entete = ("" if hide_index else "<th></th>") + "".join(f"<th>{_echappe(c)}</th>" for c in cols)
    lignes = []
    for idx, ligne in zip(df.index, df.itertuples(index=False, name=None)):
        cellules = ("" if hide_index else f"<td><b>{_echappe(idx)}</b></td>") + "".join(f"<td>{_echappe(v)}</td>" for v in ligne)
        lignes.append(f"<tr>{cellules}</tr>")
    return f"<div class='bb-tbl-wrap'><table class='bb-tbl'><thead><tr>{entete}</tr></thead><tbody>{''.join(lignes)}</tbody></table></div>"


def show_table(df, hide_index=False):
    """Affiche un tableau (st.dataframe) ; si pyarrow est bloque par Windows, repli automatique sur un tableau HTML."""
    if _ARROW_OK["ok"]:
        try:
            st.dataframe(df, hide_index=hide_index, width="stretch")
            return
        except (ImportError, OSError):
            _ARROW_OK["ok"] = False
    st.html(_tableau_html(df, hide_index))


def _courbe_svg(etiquettes, valeurs, hauteur=230):
    larg, g, d, h, b = 760, 46, 20, 22, 44
    lo, hi = min(valeurs), max(valeurs)
    marge = max((hi - lo) * 0.25, 1.0)
    lo, hi = lo - marge, hi + marge
    n = len(valeurs)
    x = lambda i: g + 50 + (larg - g - d - 100) * (i / (n - 1) if n > 1 else 0.5)
    y = lambda v: h + (hauteur - h - b) * (1 - (v - lo) / (hi - lo))
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(valeurs))
    grille = "".join(
        f'<line x1="{g}" x2="{larg - d}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#E4DCC6" stroke-width="1"/>'
        f'<text x="{g - 8}" y="{y(t) + 4:.1f}" text-anchor="end" font-size="12" fill="#5E6A62">{t:.0f}</text>'
        for t in [lo + (hi - lo) * k / 3 for k in range(4)])
    points = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="5" fill="#24543B"/>'
        f'<text x="{x(i):.1f}" y="{y(v) - 11:.1f}" text-anchor="middle" font-size="13" font-weight="700" fill="#202923">{v:g}</text>'
        f'<text x="{x(i):.1f}" y="{hauteur - 16}" text-anchor="middle" font-size="12" fill="#5E6A62">{e}</text>'
        for i, (e, v) in enumerate(zip(etiquettes, valeurs)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larg} {hauteur}" width="{larg}" height="{hauteur}">'
            f'<rect width="{larg}" height="{hauteur}" fill="#FBF8F0"/>{grille}'
            f'<polyline points="{pts}" fill="none" stroke="#24543B" stroke-width="3" stroke-linejoin="round"/>{points}</svg>')


def show_line(etiquettes, valeurs, hauteur=230):
    """Courbe d'une valeur au fil des etapes ; repli sur un SVG si pyarrow est bloque."""
    if _ARROW_OK["ok"]:
        try:
            import pandas as pd
            st.line_chart(pd.DataFrame({"Note de qualité": valeurs}, index=etiquettes), height=hauteur)
            return
        except (ImportError, OSError):
            _ARROW_OK["ok"] = False
    show_svg(_courbe_svg(etiquettes, valeurs, hauteur))
