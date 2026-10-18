"""Visuels de l'application (SVG), aux couleurs de la fiche BAOBAB."""
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
