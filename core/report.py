"""Rapport PDF de situation : une page de synthese pour le directeur, avec alertes, qualite, chaine et decisions.

Tous les chiffres viennent des fonctions de calcul de l'application (qualite, simulation, alertes, confiance).
Le rapport ne contient jamais de donnees personnelles (noms, telephones, e-mails, salaires).
Police : Helvetica (accents francais ; evite les symboles absents de cette police).
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.graphics.shapes import Drawing, Line, Rect, String

from core import alerts as al
from core import quality
from core.loader import PARAMS
from core.simulate import list_options, simulate_supplier_delay
from core.trust import couleur, trust_score

VERT, VERT_CLAIR, SABLE, ENCRE, GRIS = colors.HexColor("#24543B"), colors.HexColor("#E8F5EA"), colors.HexColor("#F9F5E9"), colors.HexColor("#202923"), colors.HexColor("#5E655E")
NIVEAU = {"rouge": (colors.HexColor("#B2243B"), colors.HexColor("#FBE3E7"), "URGENT"),
          "orange": (colors.HexColor("#B4470F"), colors.HexColor("#FDEFE3"), "A SURVEILLER"),
          "vert": (colors.HexColor("#1F6A31"), colors.HexColor("#E8F5EA"), "OK")}
COULEUR_NOTE = {"vert": colors.HexColor("#3E8E5E"), "orange": colors.HexColor("#E08A3C"), "rouge": colors.HexColor("#D6334A")}
LARGEUR = A4[0] - 3.6 * cm


def _styles():
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle("titre", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=ENCRE, alignment=0, spaceAfter=2),
        "sous": ParagraphStyle("sous", parent=base["Normal"], fontSize=10.5, textColor=GRIS, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, textColor=VERT, spaceBefore=14, spaceAfter=6),
        "p": ParagraphStyle("p", parent=base["Normal"], fontSize=9.5, leading=13, textColor=ENCRE),
        "petit": ParagraphStyle("petit", parent=base["Normal"], fontSize=8, leading=10.5, textColor=GRIS),
        "cellule": ParagraphStyle("cellule", parent=base["Normal"], fontSize=8.6, leading=11, textColor=ENCRE),
        "cellule_b": ParagraphStyle("cellule_b", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=ENCRE),
    }


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _n(x):
    return f"{int(round(x)):,}".replace(",", " ")


def _d(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def _matiere(m):
    return str(m).replace("concentre", "concentré").replace("_", " ")


def _tableau(lignes, largeurs, entete=True, zebre=True):
    t = Table(lignes, colWidths=largeurs, repeatRows=1 if entete else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8.6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7DFC9"))]
    if entete:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0E9D6")), ("LINEBELOW", (0, 0), (-1, 0), 1.2, VERT)]
    if zebre:
        style += [("ROWBACKGROUNDS", (0, 1 if entete else 0), (-1, -1), [colors.white, colors.HexColor("#FBF8F0")])]
    t.setStyle(TableStyle(style))
    return t


def _kpi(valeur, libelle, sous="", couleur_val=ENCRE):
    s = _styles()
    s["p"] = ParagraphStyle("kpi", parent=s["p"], leading=25)
    v = Paragraph(f"<font size=20 color='{couleur_val.hexval().replace('0x', '#')}'><b>{_esc(valeur)}</b></font>", s["p"])
    return [v, Paragraph(f"<font size=8 color='#5E655E'>{_esc(libelle)}</font>", s["petit"]), Paragraph(f"<font size=7.5 color='#5E655E'>{_esc(sous)}</font>", s["petit"])]


def _barres_qualite(scores, largeur=LARGEUR, hauteur_ligne=24):
    """Barres horizontales : une par fichier, couleur selon le seuil vert/orange/rouge."""
    fichiers = sorted(scores, key=lambda f: scores[f])
    h = hauteur_ligne * len(fichiers) + 14
    d = Drawing(largeur, h)
    x0, wmax = 95, largeur - 95 - 50
    for i, f in enumerate(fichiers):
        y = h - (i + 1) * hauteur_ligne
        d.add(String(0, y + 6, f.capitalize(), fontName="Helvetica", fontSize=9.5, fillColor=ENCRE))
        d.add(Rect(x0, y + 3, wmax, 12, fillColor=colors.HexColor("#EFE8D5"), strokeColor=None))
        d.add(Rect(x0, y + 3, wmax * scores[f] / 100, 12, fillColor=COULEUR_NOTE[couleur(scores[f])], strokeColor=None))
        d.add(String(x0 + wmax + 8, y + 5, f"{_d(scores[f])}", fontName="Helvetica-Bold", fontSize=9.5, fillColor=ENCRE))
    for seuil in (PARAMS["seuils_confiance"]["orange"], PARAMS["seuils_confiance"]["vert"]):
        x = x0 + wmax * seuil / 100
        d.add(Line(x, 4, x, h - 2, strokeColor=GRIS, strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(String(x - 6, -8, str(seuil), fontName="Helvetica", fontSize=7, fillColor=GRIS))
    return d


def _barres_couverture(cou, largeur=LARGEUR, hauteur_ligne=24, maximum=40):
    h = hauteur_ligne * len(cou) + 14
    d = Drawing(largeur, h)
    x0, wmax = 170, largeur - 170 - 55
    for i, c in enumerate(cou):
        y = h - (i + 1) * hauteur_ligne
        niveau = "rouge" if c["jours"] < al.COUVERTURE_ROUGE else "orange" if c["jours"] < al.COUVERTURE_ORANGE else "vert"
        d.add(String(0, y + 6, f"{c['ligne']} - {_matiere(c['matiere'])}", fontName="Helvetica", fontSize=9, fillColor=ENCRE))
        d.add(Rect(x0, y + 3, wmax, 12, fillColor=colors.HexColor("#EFE8D5"), strokeColor=None))
        d.add(Rect(x0, y + 3, wmax * min(c["jours"], maximum) / maximum, 12, fillColor=COULEUR_NOTE[niveau], strokeColor=None))
        d.add(String(x0 + wmax + 8, y + 5, f"{_d(c['jours'])} j", fontName="Helvetica-Bold", fontSize=9, fillColor=ENCRE))
    return d


def _pied(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(1.8 * cm, 1.1 * cm, f"Baobab Sève  |  {PARAMS['societe']}  |  Données fictives de démonstration")
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#DDD3BC"))
    canvas.line(1.8 * cm, 1.5 * cm, A4[0] - 1.8 * cm, 1.5 * cm)
    canvas.restoreState()


def build_report(data, scores, issues=None, sains=None, avant=None, decisions=None, fournisseur=None, retard_jours=None,
                 logo_path=None, maintenant=None):
    """Construit le rapport et retourne les octets du PDF.

    issues  : problemes par fichier (quality.list_issues) ; sains : % de lignes saines par fichier ;
    avant   : {"note", "sains", "problemes"} au depart (pour montrer la progression) ;
    decisions : DataFrame des decisions prises (core.db.read_decisions) ; fournisseur / retard_jours : scenario."""
    s = _styles()
    sc = PARAMS["scenario"]
    fournisseur = fournisseur or sc["fournisseur_en_retard"]
    retard_jours = sc["retard_jours"] if retard_jours is None else retard_jours
    maintenant = maintenant or datetime.now()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=2.0 * cm,
                            title="Baobab Sève - Rapport de situation", author="Baobab Sève", subject=PARAMS["societe"])
    el = []

    # --- en-tete
    titre = [Paragraph("Rapport de situation", s["titre"]),
             Paragraph(f"{_esc(PARAMS['societe'])} · situation au {PARAMS['date_reference'][8:]}/{PARAMS['date_reference'][5:7]}/{PARAMS['date_reference'][:4]} · "
                       f"généré le {maintenant.strftime('%d/%m/%Y à %H:%M')}", s["sous"])]
    if logo_path:
        try:
            logo = Image(logo_path, width=3.2 * cm, height=3.2 * cm * 0.42, kind="proportional")
            logo.hAlign = "RIGHT"
            entete = Table([[titre, logo]], colWidths=[LARGEUR - 3.6 * cm, 3.6 * cm])
            entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            el.append(entete)
        except Exception:
            el += titre
    else:
        el += titre

    # --- synthese
    liste_alertes = al.compute_alerts(data, scores, issues, fournisseur, retard_jours)
    resume = al.resume_alertes(liste_alertes)
    note = quality.global_score(scores)
    conf = trust_score(sorted(scores), scores)
    prog = ""
    if avant is not None and avant.get("note") is not None and abs(avant["note"] - note) >= 0.05:
        prog = f"au départ : {_d(avant['note'])}"
    n_pb = sum(len(v) for v in issues.values()) if issues else None
    kpis = [_kpi(_d(note), "Note de qualité des données (sur 100)", prog, COULEUR_NOTE[couleur(note)]),
            _kpi(str(resume["rouge"]), "Alertes urgentes", f"{resume['orange']} à surveiller", NIVEAU["rouge"][0] if resume["rouge"] else NIVEAU["vert"][0]),
            _kpi(f"{conf['score']} / 100", "Confiance globale", "à confirmer" if conf["a_confirmer"] else "exploitable", COULEUR_NOTE[conf["couleur"]]),
            _kpi(_n(n_pb) if n_pb is not None else "-", "Problèmes détectés", f"{_d(avant['problemes'], 0)} au départ" if avant and avant.get("problemes") not in (None, n_pb) else "", ENCRE)]
    t = Table([[k for k in kpis]], colWidths=[LARGEUR / 4] * 4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SABLE), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DDD3BC")),
                           ("LINEAFTER", (0, 0), (-2, -1), 0.4, colors.HexColor("#DDD3BC")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el.append(t)

    if resume["rouge"]:
        premiere = next(a for a in liste_alertes if a["niveau"] == "rouge")
        el += [Spacer(1, 8), Paragraph(f"<b>À retenir :</b> {_esc(premiere['titre'])}. {_esc(premiere['detail'])}", s["p"])]

    # --- alertes
    el.append(Paragraph("1. Alertes", s["h2"]))
    lignes = [[Paragraph("<b>Niveau</b>", s["cellule"]), Paragraph("<b>Alerte</b>", s["cellule"]), Paragraph("<b>Page</b>", s["cellule"])]]
    styles_cases = []
    for i, a in enumerate(liste_alertes, 1):
        fg, bg, lib = NIVEAU[a["niveau"]]
        lignes.append([Paragraph(f"<font color='{fg.hexval().replace('0x', '#')}'><b>{lib}</b></font>", s["cellule"]),
                       Paragraph(f"<b>{_esc(a['titre'])}</b><br/><font color='#5E655E'>{_esc(a['detail'])}</font>", s["cellule"]),
                       Paragraph(_esc(a["page"]), s["cellule"])])
        styles_cases.append(("BACKGROUND", (0, i), (0, i), bg))
    t = _tableau(lignes, [2.6 * cm, LARGEUR - 2.6 * cm - 1.9 * cm, 1.9 * cm], zebre=False)
    t.setStyle(TableStyle(styles_cases))
    el.append(t)

    # --- qualite
    intro_q = [Paragraph("2. Qualité des données", s["h2"]), Paragraph("Chaque fichier reçoit une note sur 100 : 30 % complétude, 30 % unicité, 20 % validité, 20 % cohérence. "
                        f"Vert à partir de {PARAMS['seuils_confiance']['vert']}, orange à partir de {PARAMS['seuils_confiance']['orange']}, rouge en dessous.", s["petit"])]
    graphique_q = [Spacer(1, 6), _barres_qualite(scores), Spacer(1, 12)]
    ent = ["Fichier", "Lignes", "Complétude", "Unicité", "Validité", "Cohérence", "Problèmes"]
    lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ent]]
    for f, df in data.items():
        m = quality.measures(df, f)
        lignes.append([Paragraph(f.capitalize(), s["cellule_b"]), _n(len(df))] + [f"{_d(100 * m[k])} %" for k in ("completude", "unicite", "validite", "coherence")]
                      + [_n(len(issues[f])) if issues and f in issues else "-"])
    el.append(KeepTogether(intro_q + graphique_q + [_tableau(lignes, [3.4 * cm, 2 * cm] + [(LARGEUR - 5.4 * cm - 2.2 * cm) / 4] * 4 + [2.2 * cm])]))

    # --- chaine
    cou = al.couvertures(data)
    intro_c = [Paragraph("3. Chaîne de production", s["h2"]), Paragraph("Jours de stock par ligne et par matière (stock nettoyé : valeurs invalides ignorées, unités converties).", s["petit"])]
    lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ("Ligne", "Matière", "Stock", "Consommation / jour", "Couverture")]]
    for c in cou:
        lignes.append([c["ligne"], _matiere(c["matiere"]), _n(c["stock"]), _n(c["conso_par_jour"]), f"{_d(c['jours'])} jours"])
    el.append(KeepTogether(intro_c + [Spacer(1, 6), _barres_couverture(cou), Spacer(1, 12), _tableau(lignes, [2.6 * cm, 4.2 * cm, 3 * cm, 4 * cm, LARGEUR - 13.8 * cm])]))

    sim = simulate_supplier_delay(data, fournisseur, retard_jours)
    el.append(Paragraph(f"Scénario simulé : {_esc(fournisseur)} avec {retard_jours} jours de retard", s["h2"]))
    if sim["arret_jour"] is None:
        el.append(Paragraph("Aucun arrêt de production prévu : les stocks couvrent le retard annoncé.", s["p"]))
    else:
        el.append(Paragraph(f"La <b>{_esc(sim['ligne'])}</b> s'arrêterait à <b>J+{sim['arret_jour']}</b> faute de {_esc(_matiere(sim['matiere']))}. "
                            f"Il manquerait <b>{_n(sim['manque'])} unités</b>. {len(sim['commandes'])} commandes et {len(sim['clients'])} clients seraient touchés.", s["p"]))
        if sim["commandes_detail"]:
            lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ("Commande", "Client", "Produit", "Quantité", "Livraison", "Jour")]]
            for o in sim["commandes_detail"]:
                lignes.append([o["commande_id"], o["client"], _esc(o["produit"]), _n(o["quantite"]), o["date_livraison"], f"J+{o['jour']}"])
            el += [Spacer(1, 6), _tableau(lignes, [2.2 * cm, 2.4 * cm, 4.6 * cm, 2.2 * cm, 2.8 * cm, LARGEUR - 14.2 * cm])]
        options = list_options(data, sim)
        if options:
            el.append(Paragraph("Trois solutions", s["h2"]))
            risque = {"faible": "faible", "moyen": "moyen", "eleve": "élevé"}
            lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ("Option", "Solution", "Faisable", "Surcoût", "Risque")]]
            for o in options:
                lignes.append([Paragraph(f"<b>{o['code']}</b>", s["cellule"]), Paragraph(_esc(o["libelle"]), s["cellule"]),
                               "oui" if o["faisable"] else "non", f"+{_d(o['surcout_pct'])} %", risque[o["risque"]]])
            el.append(_tableau(lignes, [1.6 * cm, LARGEUR - 8.4 * cm, 2.2 * cm, 2.4 * cm, 2.2 * cm]))
            el.append(Paragraph("La décision revient au directeur général : le rapport propose, il ne décide pas.", s["petit"]))

    # --- fournisseurs
    four = data["fournisseurs"].sort_values(["fournisseur", "matiere"])
    lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ("Fournisseur", "Matière", "Délai (jours)", "Fiabilité", "Prix relatif")]]
    for _, r in four.iterrows():
        lignes.append([Paragraph(_esc(r["fournisseur"]), s["cellule_b"]), _matiere(r["matiere"]), _n(r["delai_moyen_jours"]),
                       f"{_n(r['fiabilite_pct'])} %", _d(float(r["prix_relatif"]), 2)])
    el.append(KeepTogether([Paragraph("4. Fournisseurs", s["h2"]), _tableau(lignes, [3.4 * cm, 4.6 * cm, 3 * cm, 3 * cm, LARGEUR - 14 * cm])]))

    # --- decisions
    el.append(Paragraph("5. Décisions prises", s["h2"]))
    if decisions is None or len(decisions) == 0:
        el.append(Paragraph("Aucune décision enregistrée pour le moment.", s["p"]))
    else:
        lignes = [[Paragraph(f"<b>{h}</b>", s["cellule"]) for h in ("Date", "Fournisseur", "Retard", "Option", "Solution")]]
        for _, r in decisions.head(15).iterrows():
            lignes.append([str(r["horodatage"])[:16], _esc(r["fournisseur"]), f"{int(r['retard_jours'])} j", r["option_code"], Paragraph(_esc(r["libelle"]), s["cellule"])])
        el.append(_tableau(lignes, [3.2 * cm, 2.6 * cm, 1.8 * cm, 1.6 * cm, LARGEUR - 9.2 * cm]))

    # --- confiance
    bloc = [Paragraph("6. Comment lire ce rapport", s["h2"]),
            Paragraph(f"Confiance globale : <b>{conf['score']} / 100</b> ({conf['couleur']}). Elle vaut le plus petit de la moyenne des notes de qualité "
                      f"et de la note du fichier le plus faible ({_esc(conf['plus_faible'])}, {_d(scores[conf['plus_faible']])}) plus 15 points. "
                      "Corriger les données dans la page Données fait monter cette confiance.", s["p"]),
            Spacer(1, 4),
            Paragraph("Les chiffres viennent de fonctions de calcul vérifiables (qualité, simulation, couverture de stock). Aucune donnée personnelle "
                      "(noms, téléphones, e-mails, salaires) n'apparaît dans ce rapport. Données fictives de démonstration.", s["petit"])]
    el.append(KeepTogether(bloc))

    doc.build(el, onFirstPage=_pied, onLaterPages=_pied)
    return buf.getvalue()
