<p align="center"><img src="app/assets/logo.png" alt="Baobab Sève : de la donnée à la décision" width="340"></p>

# Baobab Sève

> De la donnée à la décision. Des racines propres, un tronc qui relie tout, une cime qui éclaire les décisions.

**[🌐 Essayer la démo en ligne](https://baobao-seve.streamlit.app/)** · **[▶️ Voir la vidéo de démonstration](https://youtu.be/tuzpyNcVVX0)**

Prototype réalisé pour le **CREATE WITH AI Hackathon** (JNC Africa, 2026). Il fiabilise les données d'une entreprise, relie sa chaîne de production, et répond aux questions en français avec ses sources et un score de confiance. Toutes les données sont **fictives** (usine de jus de fruits « Délice SA »).

## Ce que fait Baobab Sève

| Page | Rôle | Ce qu'on y voit |
| --- | --- | --- |
| **Données** (racines) | DataCompass | Scanne 6 fichiers (6 517 lignes), détecte 2 228 problèmes (doublons, e-mails manquants, unités mélangées…), propose 1 419 corrections que le directeur valide. Lignes sans défaut : 68,8 % → 87,8 %. |
| **Chaîne** (tronc) | SupplyMind | Relie fournisseurs, matières, lignes, produits, commandes et clients. Simule le retard d'un fournisseur : arrêt de production, manque, commandes et clients touchés, trois solutions chiffrées. |
| **Copilote** (cime) | Copilote | Répond en français, cite ses fichiers sources, affiche un score de confiance (vert, orange, rouge « à confirmer »). Répond à des questions libres sur les données (ex. « Quel client a la plus grosse commande ? », « Compare Sigma et Delta »), se souvient de la conversation, explique son calcul. Fonctionne aussi sans Internet. |
| **Tableau de bord** | Pilotage | Alertes classées (urgent, à surveiller), note de qualité par fichier, jours de stock par ligne, évolution de la note, et **rapport PDF** de 3 à 4 pages à télécharger (sans aucune donnée personnelle). |

**Scénario de démonstration :** le fournisseur Delta annonce 5 jours de retard. La Ligne 2 s'arrêterait à J+4, il manquerait 1 200 unités, 3 commandes et 2 clients seraient touchés. Option A : transférer le stock de l'entrepôt Nord (0 % de surcoût, risque moyen). Option B : commande express chez Sigma (+6 %, risque faible). Option C : reporter la production (+2 %, risque élevé).

## Comment ça marche

- **L'IA ne calcule jamais.** Le copilote choisit parmi des fonctions de calcul vérifiables (`get_stock_coverage`, `simulate_supplier_delay`, `list_options`, `get_trust`, `get_passport`, `explain_trust`, `get_quality_report`, `rank_suppliers`, `get_briefing`, `get_order`, `query_data`) et reformule leur résultat. Chaque chiffre vient d'une de ces fonctions. Pour les questions libres, `query_data` transforme la question en requête SQL en lecture seule sur une copie des données qui ne contient aucun nom, téléphone, e-mail ni salarié ; la requête et la compréhension de la question sont visibles sous chaque réponse (« Comment j'ai trouvé cette réponse »).
- **Score de confiance :** moyenne pondérée des notes de qualité des fichiers utilisés, plafonnée à la note du fichier le plus faible plus 15 points. Vert à partir de 80, orange de 60 à 79, rouge en dessous de 60.
- **Mode hors ligne :** sans clé d'API ni Internet, un moteur de secours appelle les mêmes fonctions. Les chiffres, sources et scores sont identiques ; seule la formulation change.
- **Base de données SQLite :** chaque visiteur a sa propre base (module standard de Python : gratuit, sans serveur, sans clé). Elle contient les données, le journal des actions, l'historique de la note de qualité, les validations (annulables d'un clic) et les décisions retenues. Le directeur peut l'interroger en lecture seule avec du SQL et la télécharger.
- **Droits par rôle :** le *Directeur général* voit tout et valide les corrections ; le *Stagiaire logistique* voit des colonnes masquées (noms, téléphones, e-mails, salaires) et ne peut pas valider. Un message « Vous n'avez pas accès… » s'affiche à chaque accès refusé, et les actions sont inscrites dans un journal.

## Lancer en local

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows (Mac/Linux : source .venv/bin/activate)
pip install -r requirements.txt
python generate_data.py          # crée les données fictives dans data/
streamlit run app/main.py        # ouvre l'application
```

Pour activer le modèle de langage, copie `.env.example` en `.env` et renseigne `ANTHROPIC_API_KEY`. Cette clé n'est jamais publiée (le fichier `.env` est ignoré par Git). Sans clé, le mode hors ligne s'active seul.

## Vérifier

```bash
python check_scenario.py   # le scénario Delta (arrêt J+4, manque 1 200)
python check_quality.py    # détection et correction des défauts
python check_supply.py     # graphe, simulation et options A, B, C
python check_copilot.py    # copilote, droits, mode hors ligne, questions libres
python check_askdata.py    # moteur de questions libres (28 questions, lecture seule)
python check_report.py     # alertes et rapport PDF (sans donnée personnelle)
python check_db.py         # base SQLite : relecture, validation, annulation, requêtes en lecture seule
```

Chaque commande doit se terminer par « OK ».

## Structure

- `app/` : application Streamlit (accueil, Données, Chaîne, Copilote, Tableau de bord, thème et visuels)
- `core/` : logique métier (`quality`, `graph`, `simulate`, `trust`, `rbac`, `pii`, `copilot`, `askdata`, `nlu`, `alerts`, `report`, `loader`, `db`)
- `config/params.json` : paramètres du scénario (retard, stocks, surcoûts, seuils de confiance)
- `generate_data.py` : génère les données fictives avec des défauts placés volontairement
- `SPECS.md` : contrat entre les modules

## Limites assumées

- Les données sont fictives : Baobab Sève n'a pas encore été testé sur les fichiers d'une vraie entreprise.
- Les rôles sont simulés (pas de connexion avec mot de passe) : c'est un prototype de démonstration.
- Testé sur 6 517 lignes ; pour des volumes bien plus grands, SQLite serait remplacé par une base de données serveur (PostgreSQL). Sur l'hébergement gratuit, les bases des visiteurs sont supprimées quand le site se réinitialise.
