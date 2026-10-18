"""Visuels de l'application (SVG), aux couleurs de la fiche BAOBAB."""
import math
import random

from core.graph import ORDRE

INK, MUT, GREEN, RED, ORG, DEEP = "#14201B", "#55655F", "#2B7A3E", "#D6334A", "#E4571F", "#0F3D2E"
LIGNE, NEUTRE = "#C9D3CD", "#F4F7F5"
TITRES = {"fournisseur": "Fournisseurs", "matiere": "Matières", "ligne": "Lignes", "produit": "Produits",
          "commande": "Commandes", "client": "Clients"}


def _libelle(nom, type_):
    if type_ == "matiere":
        nom = nom.replace("concentre", "concentré").replace("_", " ").capitalize()
    return nom if len(nom) <= 22 else nom[:21] + "…"


def chain_svg(graph, impactes=(), source=None, width=980):
    """Dessine la chaine de gauche a droite. Rouge : touche par le retard ; orange : source du retard."""
    impactes, nw, nh, marge = set(impactes), 134, 28, 24
    colonnes = {t: sorted(n for n, d in graph.nodes(data=True) if d["type"] == t) for t in ORDRE}
    hauteur = max(len(v) for v in colonnes.values()) * 40 + 70
    pas = (width - 2 * marge - nw) / (len(ORDRE) - 1)
    pos = {}
    for i, t in enumerate(ORDRE):
        noms = colonnes[t]
        espace = (hauteur - 70) / max(len(noms), 1)
        for j, n in enumerate(noms):
            pos[n] = (marge + i * pas, 44 + espace * (j + 0.5) - nh / 2)

    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {hauteur + 26}' width='100%' "
           f"font-family='Inter, Segoe UI, system-ui, sans-serif'>"]
    for i, t in enumerate(ORDRE):
        out.append(f"<text x='{marge + i * pas + nw / 2}' y='20' text-anchor='middle' font-size='11' "
                   f"font-weight='600' fill='{MUT}' letter-spacing='0.6'>{TITRES[t].upper()}</text>")
    chaud = impactes | ({source} if source else set())
    for a, b in graph.edges:
        (xa, ya), (xb, yb) = pos[a], pos[b]
        x1, y1, x2, y2 = xa + nw, ya + nh / 2, xb, yb + nh / 2
        xm = (x1 + x2) / 2
        rouge = a in chaud and b in chaud
        out.append(f"<path d='M{x1:.1f} {y1:.1f} C{xm:.1f} {y1:.1f} {xm:.1f} {y2:.1f} {x2:.1f} {y2:.1f}' fill='none' "
                   f"stroke='{RED if rouge else LIGNE}' stroke-width='{2.2 if rouge else 1.1}' "
                   f"opacity='{1 if rouge else 0.8}'/>")
    for n, (x, y) in pos.items():
        type_ = graph.nodes[n]["type"]
        if n == source:
            fond, trait, texte, epais = "#FCE7DC", ORG, INK, 2
        elif n in impactes:
            fond, trait, texte, epais = "#FBE3E7", RED, INK, 2
        else:
            fond, trait, texte, epais = "#FFFFFF", LIGNE, MUT, 1.2
        out.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{nw}' height='{nh}' rx='8' fill='{fond}' stroke='{trait}' "
                   f"stroke-width='{epais}'/><text x='{x + nw / 2:.1f}' y='{y + nh / 2 + 4:.1f}' text-anchor='middle' "
                   f"font-size='12' font-weight='{600 if n in chaud else 400}' fill='{texte}'>{_libelle(n, type_)}</text>")
    ly = hauteur + 10
    for k, (couleur, fond, texte) in enumerate([(ORG, "#FCE7DC", "Source du retard"),
                                                (RED, "#FBE3E7", "Touché par le retard"), (LIGNE, "#FFFFFF", "Non touché")]):
        x = marge + k * 190
        out.append(f"<rect x='{x}' y='{ly}' width='14' height='14' rx='4' fill='{fond}' stroke='{couleur}' stroke-width='1.6'/>"
                   f"<text x='{x + 22}' y='{ly + 11}' font-size='12' fill='{MUT}'>{texte}</text>")
    out.append("</svg>")
    return "".join(out)


LIMEF = '#C9F25B'
ICONS = {
 'db': '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
 'file': '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
 'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
 'sensor': '<circle cx="12" cy="12" r="2"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2"/>',
 'sheet': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16"/>',
 'scan': '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M4 12h16"/>',
 'shield': '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
 'wrench': '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-2.4-.5-.5-2.4z"/>',
 'bars': '<path d="M5 20V11M11 20V4M17 20v-6"/>',
 'chat': '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z"/>',
 'bell': '<path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7"/><path d="M10 20a2 2 0 0 0 4 0"/>',
 'flask': '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/>',
 'passport': '<rect x="5" y="3" width="14" height="18" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M9 17h6"/>',
 'lock': '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
 'users': '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 5a3 3 0 0 1 0 6M18 14c2 .7 3 2.8 3 6"/>',
 'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>',
 'eye': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 'graph': '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7h8M7.5 8l3.5 8M16.5 9l-3.5 7"/>',
 'up': '<path d="M6 15l6-6 6 6"/>',
 'check': '<path d="m5 12 5 5 9-10"/>',
 'target': '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
 'book': '<path d="M4 4h12a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M4 17a3 3 0 0 1 3-3h12"/>',
 'factory': '<path d="M3 21V10l6 4V10l6 4V6h3v15z"/><path d="M3 21h18"/>',
 'bank': '<path d="M3 10 12 4l9 6"/><path d="M5 10v8M9 10v8M15 10v8M19 10v8M3 21h18"/>',
 'truck': '<path d="M2 6h11v10H2zM13 9h5l3 3v4h-8"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
 'wheat': '<path d="M12 22V8M12 8c-2.5 0-4-1.5-4-4 2.5 0 4 1.5 4 4zM12 8c2.5 0 4-1.5 4-4-2.5 0-4 1.5-4 4zM12 14c-2.5 0-4-1.5-4-4 2.5 0 4 1.5 4 4zM12 14c2.5 0 4-1.5 4-4-2.5 0-4 1.5-4 4z"/>',
 'phone': '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
 'building': '<path d="M5 21V4h9v17M14 9h5v12M3 21h18M8 8h3M8 12h3M8 16h3"/>',
 'coin': '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.2c-.6-.8-1.5-1.2-2.6-1.2-1.5 0-2.6.8-2.6 2s1 1.7 2.7 2.1c1.7.4 2.7 1 2.7 2.2s-1.1 2-2.7 2c-1.2 0-2.2-.5-2.8-1.3M12 6.5V8M12 16v1.5"/>',
}


def icon(name, size=20, color='currentColor', sw=1.7):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" style="flex:none">{ICONS[name]}</svg>')


def tree_svg():
    random.seed(11)
    W, H = 560, 640
    cx, ground = 280, 372
    TREE_G = '#4C9A2A'
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">']
    out.append('<defs><radialGradient id="gl" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#FF8A55" stop-opacity=".30"/><stop offset="1" stop-color="#FF8A55" stop-opacity="0"/></radialGradient>'
               '<radialGradient id="gl2" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#C9F25B" stop-opacity=".75"/><stop offset="1" stop-color="#C9F25B" stop-opacity="0"/></radialGradient>'
               '<linearGradient id="tr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EFE7D3"/><stop offset="1" stop-color="#DDD2B6"/></linearGradient></defs>')
    out.append(f'<ellipse cx="{cx}" cy="150" rx="235" ry="150" fill="url(#gl)"/>')
    out.append(f'<ellipse cx="{cx}" cy="505" rx="235" ry="135" fill="url(#gl2)"/>')

    lines, nodes_up, nodes_dn = [], [], []

    def grow(x, y, ang, ln, depth, sign, nodes, color):
        x2 = x + ln * math.sin(ang)
        y2 = y - sign * ln * math.cos(ang)
        w = 0.9 + depth * 0.8
        lines.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-opacity="{0.55 + 0.1*depth:.2f}" stroke-width="{w:.1f}" stroke-linecap="round"/>')
        if depth == 0:
            nodes.append((x2, y2))
            return
        n = 2 if random.random() < 0.72 else 3
        base = [-1, 1] if n == 2 else [-1, 0, 1]
        for b in base:
            a = ang + b * random.uniform(0.38, 0.62) + random.uniform(-0.08, 0.08)
            grow(x2, y2, a, ln * random.uniform(0.66, 0.76), depth - 1, sign, nodes, color)

    trunk_top = 238
    for dx, a0 in [(-18, -0.35), (0, 0.0), (18, 0.35)]:
        grow(cx + dx, trunk_top, a0, 66, 4, 1, nodes_up, ORG)
    for dx, a0 in [(-62, -0.55), (-30, -0.2), (6, 0.05), (36, 0.25), (64, 0.6)]:
        grow(cx + dx, ground, a0, 48, 3, -1, nodes_dn, TREE_G)

    def links(nodes, color, thr):
        res = []
        for i, (x1, y1) in enumerate(nodes):
            for (x2, y2) in nodes[i + 1:]:
                if math.hypot(x1 - x2, y1 - y2) < thr:
                    res.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-opacity=".3" stroke-width=".8"/>')
        return res

    out.append(f'<path d="M{cx-34},{trunk_top-6} C{cx-40},282 {cx-64},330 {cx-78},{ground} L{cx+78},{ground} C{cx+64},330 {cx+40},282 {cx+34},{trunk_top-6} C{cx+30},{trunk_top-24} {cx-30},{trunk_top-24} {cx-34},{trunk_top-6} Z" fill="url(#tr)" stroke="{INK}" stroke-opacity=".30" stroke-width="1.3"/>')
    for off in [-22, -8, 8, 22]:
        out.append(f'<path d="M{cx+off*0.6},{trunk_top+6} C{cx+off*0.8},300 {cx+off*1.5},340 {cx+off*2.0},{ground-4}" fill="none" stroke="{INK}" stroke-opacity=".10" stroke-width="1"/>')
    out.append(f'<line x1="10" y1="{ground}" x2="{W-10}" y2="{ground}" stroke="{INK}" stroke-opacity=".35" stroke-dasharray="3 5"/>')

    out += links(nodes_up, ORG, 52) + links(nodes_dn, TREE_G, 52)
    out += lines
    for (x, y) in nodes_up:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{ORG}" fill-opacity=".16"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="{ORG}"/>')
    for (x, y) in nodes_dn:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{TREE_G}" fill-opacity=".16"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{TREE_G}"/>')
    out.append(f'<circle cx="{cx}" cy="{trunk_top+40}" r="6" fill="{DEEP}"/><circle cx="{cx}" cy="{trunk_top+40}" r="13" fill="none" stroke="{DEEP}" stroke-opacity=".4"/>')

    def label(y, txt, sub, col):
        return (f'<text x="{W-6}" y="{y}" text-anchor="end" font-size="14" font-weight="800" letter-spacing="2.2" fill="{col}">{txt}</text>'
                f'<text x="{W-6}" y="{y+19}" text-anchor="end" font-size="13.5" font-weight="500" fill="{MUT}">{sub}</text>')
    out.append(label(52, 'CIME', 'des décisions éclairées', '#C44A14'))
    out.append(label(300, 'TRONC', 'tout est relié', INK))
    out.append(label(ground + 215, 'RACINES', 'des données propres', GREEN))
    out.append(f'<text x="10" y="{ground-8}" font-size="11" letter-spacing="1.6" font-weight="600" fill="{MUT}">NIVEAU DU SOL</text>')
    out.append(f'<text x="10" y="{ground+16}" font-size="11.5" fill="{MUT}">informations brutes, en désordre ↓</text>')
    out.append('</svg>')
    return ''.join(out)


def gauge(score, prev=None, size=190):
    r = 70
    L = math.pi * r
    prog = L * score / 100
    s = f'<svg width="{size}" height="{size*0.62:.0f}" style="max-width:100%" viewBox="0 0 180 112" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">'
    s += f'<path d="M20,90 A70,70 0 0 1 160,90" fill="none" stroke="{INK}" stroke-opacity=".10" stroke-width="12" stroke-linecap="round"/>'
    if prev is not None:
        s += f'<path d="M20,90 A70,70 0 0 1 160,90" fill="none" stroke="{RED}" stroke-opacity=".6" stroke-width="12" stroke-linecap="round" stroke-dasharray="{L*prev/100:.1f} 400"/>'
    s += f'<path d="M20,90 A70,70 0 0 1 160,90" fill="none" stroke="#5DB233" stroke-width="12" stroke-linecap="round" stroke-dasharray="{prog:.1f} 400"/>'
    s += f'<text x="90" y="82" text-anchor="middle" font-size="38" font-weight="800" fill="{INK}">{score}</text>'
    s += f'<text x="90" y="103" text-anchor="middle" font-size="12.5" fill="{MUT}">sur 100</text>'
    s += '</svg>'
    return s
