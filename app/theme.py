"""Habillage de l'application : feuille de style, en-tetes de page, pastilles, cartes (aux couleurs de la fiche)."""
import streamlit as st

CSS = """
<style>
.stApp { font-family: 'Segoe UI', Inter, system-ui, -apple-system, sans-serif; }
.block-container { padding-top: 4.5rem; max-width: 1180px; }
h2, h3 { color: #0F3D2E; letter-spacing: -0.01em; }
[data-testid="stMetric"] { background: #F5F8F3; border: 1px solid #C9D6CB; border-radius: 14px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(20,32,27,.04); }
[data-testid="stSidebar"] { border-right: 1px solid #C2D0C4; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
.bb-head { display: flex; align-items: center; gap: 14px; margin: 0 0 1.1rem 0; }
.bb-ico { width: 48px; height: 48px; border-radius: 14px; background: #F5F8F3; border: 1px solid #C2D0C4; font-size: 26px; display: flex; align-items: center; justify-content: center; flex: none; }
.bb-t { font-size: 1.7rem; font-weight: 800; color: #14201B; line-height: 1.15; letter-spacing: -0.02em; }
.bb-s { font-size: .95rem; color: #55655F; margin-top: 2px; }
.bb-kick { font-size: .78rem; font-weight: 700; letter-spacing: .14em; color: #2B7A3E; text-transform: uppercase; }
.bb-h1 { font-size: 3rem; font-weight: 800; color: #0F3D2E; letter-spacing: -0.03em; line-height: 1.05; margin: 6px 0 8px; }
.bb-lead { font-size: 1.12rem; color: #14201B; line-height: 1.45; margin-bottom: 14px; }
.bb-pts { display: flex; flex-wrap: wrap; gap: 8px; }
.bb-pt { background: #F5F8F3; border: 1px solid #C2D0C4; border-radius: 999px; padding: 6px 12px; font-size: .86rem; color: #14201B; font-weight: 600; }
.bb-card { background: #F5F8F3; border: 1px solid #C9D6CB; border-radius: 16px; padding: 18px 20px 14px; height: 100%;
  box-shadow: 0 1px 2px rgba(20,32,27,.04); }
.bb-card .i { width: 42px; height: 42px; border-radius: 12px; background: #DDE7DB; font-size: 22px; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.bb-card .k { font-size: .75rem; font-weight: 700; letter-spacing: .12em; color: #55655F; }
.bb-card .t { font-size: 1.2rem; font-weight: 800; color: #14201B; margin: 2px 0 6px; }
.bb-card .d { font-size: .93rem; color: #55655F; line-height: 1.4; }
.bb-steps { display: flex; flex-wrap: wrap; gap: 10px; margin: .4rem 0 1.2rem; }
.bb-step { flex: 1 1 200px; background: #F5F8F3; border: 1px solid #C9D6CB; border-radius: 14px; padding: 12px 14px; display: flex; gap: 10px; align-items: flex-start; }
.bb-step .n { width: 26px; height: 26px; border-radius: 50%; background: #0F3D2E; color: #C9F25B; font-weight: 800; font-size: .85rem;
  display: flex; align-items: center; justify-content: center; flex: none; }
.bb-step b { display: block; color: #14201B; font-size: .95rem; }
.bb-step span { color: #55655F; font-size: .84rem; }
.bb-chip { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 14px; font-weight: 700; font-size: .92rem; border: 1px solid; }
.bb-chip.vert { background: #E8F5EA; color: #1F6A31; border-color: #B7DDBF; }
.bb-chip.orange { background: #FDEFE3; color: #B4470F; border-color: #F4C9A8; }
.bb-chip.rouge { background: #FBE3E7; color: #B2243B; border-color: #F1B3BE; }
.bb-chip i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; background: currentColor; }
.bb-note { color: #55655F; font-size: .86rem; margin-left: 10px; }
.bb-alert { border-radius: 16px; padding: 16px 20px; border: 1px solid; display: flex; gap: 14px; align-items: center; }
.bb-alert.rouge { background: #FBE3E7; border-color: #F1B3BE; }
.bb-alert.vert { background: #E8F5EA; border-color: #B7DDBF; }
.bb-alert .big { font-size: 1.5rem; font-weight: 800; color: #14201B; line-height: 1.2; }
.bb-alert .sm { color: #55655F; font-size: .92rem; margin-top: 2px; }
.bb-gauge { background: #F5F8F3; border: 1px solid #C9D6CB; border-radius: 16px; padding: 14px 16px 12px; text-align: center; height: 100%; }
.bb-gauge .l { font-size: .78rem; font-weight: 700; letter-spacing: .1em; color: #55655F; }
.bb-ring { width: 150px; height: 150px; border-radius: 50%; margin: 12px auto 8px; display: flex; align-items: center; justify-content: center; }
.bb-ring .in { width: 114px; height: 114px; border-radius: 50%; background: #F5F8F3; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.bb-ring b { font-size: 2rem; font-weight: 800; color: #14201B; line-height: 1; }
.bb-ring span { font-size: .78rem; color: #55655F; margin-top: 4px; }
.bb-lock { display: flex; align-items: center; gap: 10px; background: #F3E9D6; border: 1px solid #E2CFA6; color: #6B4E12; border-radius: 12px; padding: 10px 14px; font-weight: 600; font-size: .92rem; margin: .3rem 0; }
.bb-role { display: inline-block; background: #EAF1EC; color: #0F3D2E; border-radius: 999px; padding: 4px 12px; font-size: .84rem; font-weight: 700; }
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
            "<div class='bb-h1'>BAOBAB</div>"
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
            f"<div class='bb-ring' style='background:conic-gradient(#5DB233 0deg {deg:.1f}deg, #C2D0C4 {deg:.1f}deg 360deg)'>"
            f"<div class='in'><b>{score}</b><span>sur 100</span></div></div>{depart}</div>")


def alert(couleur, grand, petit):
    return f"<div class='bb-alert {couleur}'><div><div class='big'>{grand}</div><div class='sm'>{petit}</div></div></div>"
