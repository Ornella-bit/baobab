# Baobab Sève · Spécifications du prototype

Version 1, figée à l'étape 3. Ce fichier est le contrat entre les modules : si on change un nom ou un format, on le change ici d'abord.

## 1. But et scénario de démonstration

Montrer en moins de 3 minutes que Baobab Sève (1) fiabilise des données, (2) anticipe un arrêt de production et (3) dit à quel point chaque réponse est fiable. Données **fictives** de « Délice SA », usine de jus de fruits.

| Fait du scénario | Valeur |
| --- | --- |
| Stock de concentré de mangue à la Ligne 2 | 4 800 unités |
| Consommation de la Ligne 2 | 1 200 unités par jour |
| Couverture | 4 jours |
| Retard annoncé par Delta | 5 jours |
| Arrêt de la Ligne 2 | à J+4 |
| Manque | 1 200 unités |
| Commandes menacées | CMD004, CMD005, CMD007 (clients B et C) |
| Option A | Transfert depuis l'entrepôt Nord (3 000 unités disponibles), coût +0 %, risque moyen |
| Option B | Commande express chez Sigma, +6 %, risque faible |
| Option C | Report de la production de la Ligne 2, +2 %, risque élevé |

`python check_scenario.py` vérifie ces chiffres. Les valeurs sont dans `config/params.json`.

## 2. Les modules

| Module | Rôle | Fichier | Priorité |
| --- | --- | --- | --- |
| A. DataCompass | Classer les colonnes, noter la qualité, trouver doublons et problèmes, proposer des corrections | `core/quality.py`, `core/pii.py` | Indispensable |
| B. SupplyMind | Graphe de la chaîne, couverture de stock, simulation de retard, 3 options | `core/graph.py`, `core/simulate.py` | Indispensable |
| C. Confiance et droits | Score de confiance, rôles, masquage, journal | `core/trust.py`, `core/rbac.py` | Indispensable (déjà écrit) |
| D. Copilote | Question en français, appel de fonctions, réponse avec sources et confiance | `core/copilot.py` | Indispensable |
| E. Interface | 3 pages Streamlit et choix du rôle | `app/` | Indispensable |
| Bonus | Alertes automatiques, passeport produit, lecture des contrats PDF, graphe animé | | Seulement si le temps le permet |

Règle d'or : le modèle de langage ne calcule jamais. Il appelle des fonctions du code et reformule leur résultat.

## 3. Données (dans `data/`)

| Fichier | Colonnes |
| --- | --- |
| employes.xlsx | id, nom, poste, salaire_fcfa, telephone, email, date_naissance |
| clients.csv | client_id, nom_complet, ville, telephone, email |
| stocks.csv | lot_id, lieu, matiere, quantite, unite, date_reception |
| fournisseurs.csv | fournisseur, matiere, delai_moyen_jours, fiabilite_pct, prix_relatif |
| production.csv | ligne, produit, matiere, conso_par_jour |
| commandes.csv | commande_id, client, produit, quantite, date_livraison |
| contrats/*.pdf | 12 contrats (prix, durée, pénalité, échéance), lecture en bonus |

Lieux de stock : « Ligne 1 », « Ligne 2 », « Entrepot Nord », « Entrepot Sud ». Pour la couverture, seule l'unité « unites » est comptée.

## 4. Contrat de fonctions

Toutes les fonctions reçoivent des DataFrames pandas ou le dictionnaire `data` renvoyé par `core.loader.load_all()`.

| Fonction | Retourne |
| --- | --- |
| `quality.classify_columns(df)` | `{colonne: identite, contact, argent, date, produit, quantite ou autre}` |
| `quality.measures(df, fichier)` | `{completude, unicite, validite, coherence}` entre 0 et 1 |
| `quality.quality_score(df, fichier)` | note de 0 à 100 |
| `quality.find_duplicates(df, colonne, seuil=90)` | DataFrame `ligne_a, ligne_b, similarite` |
| `quality.list_issues(df, fichier)` | liste de problèmes (format ci-dessous) |
| `quality.apply_corrections(df, issues)` | nouveau DataFrame, seuls les problèmes « valide » sont appliqués |
| `pii.detect_pii(df)` | `{colonne: nom, telephone, email, salaire ou date_naissance}` |
| `pii.count_pii(data)` | nombre de colonnes sensibles dans tous les fichiers |
| `graph.build_graph(data)` | `networkx.DiGraph` (fournisseur, matière, ligne, produit, commande, client) |
| `graph.downstream(graph, noeud)` | liste de `(nom, type)` touchés en aval |
| `simulate.stock_coverage(data, ligne, matiere)` | `{stock, conso_par_jour, jours}` |
| `simulate.simulate_supplier_delay(data, fournisseur, retard_jours)` | `{arret_jour, manque, commandes, clients, couverture_jours, ligne, matiere, details, commandes_detail, noeuds_impactes}` ; `details` = une entrée par ligne et matière du fournisseur, `ligne` = la ligne la plus touchée |
| `simulate.list_options(data, simulation)` | 3 options `{code, libelle, surcout_pct, risque, faisable}` si un arrêt est prévu, liste vide sinon |
| `trust.score_from_parts(c, u, v, h)` | note de 0 à 100 (écrit) |
| `trust.trust_score(sources, scores, poids=None)` | `{score, couleur, a_confirmer, plus_faible}` (écrit) |
| `rbac.can_validate(role)`, `rbac.apply_role(df, fichier, role)` | booléen, DataFrame masqué (écrit) |
| `rbac.log_action(role, action, detail)`, `rbac.read_log()` | écrit / lit `cache/audit.csv` (écrit) |
| `copilot.ask(question, role, data, scores, mode="auto")` | `{texte, sources, confiance, options, outils, mode}` ; IA si une clé d'API est configurée, sinon moteur hors ligne qui appelle les mêmes fonctions |
| `copilot.get_stock_coverage(data, ligne, matiere)`, `copilot.get_passport(data, produit)` | `{ligne, matiere, stock, conso_par_jour, jours}` ; passeport du produit |

Un **problème** est un dictionnaire : `id`, `fichier`, `type` (doublon, format, valeur_aberrante, manquant, unite), `ligne`, `colonne`, `valeur`, `correction`, `statut` (a_valider, valide, refuse).

Outils exposés au modèle de langage : `get_stock_coverage`, `simulate_supplier_delay`, `list_options`, `get_trust`, `get_passport`.

## 5. Formules et règles

- Note de qualité d'un fichier : `100 × (0,30 × complétude + 0,30 × unicité + 0,20 × validité + 0,20 × cohérence)`.
- Note globale affichée en page 1 : moyenne des notes des 6 fichiers tabulaires.
- Confiance d'une réponse : `min(moyenne pondérée des notes des sources, note la plus faible + 15)`. Vert à partir de 80, orange de 60 à 79, rouge sous 60 avec la mention « à confirmer ».
- Doublons : `rapidfuzz.fuzz.token_sort_ratio ≥ 90`, avec ville ou téléphone concordant pour les clients.
- Couverture : `jours = stock / conso_par_jour`. Si `retard > jours`, arrêt au jour `jours` et manque = `(retard − jours) × conso_par_jour`.
- Commandes menacées : commandes d'un produit de la ligne arrêtée dont la livraison tombe à partir du jour d'arrêt.
- Objectif de calibrage de la démo : note globale d'environ 40 à 45 avant corrections et 75 à 80 après. Ce sont des cibles de réglage ; les chiffres affichés dans le pitch sont ceux que le code calcule.

## 6. Rôles

| Rôle | Salaires et identités | Stocks, fournisseurs, production, commandes | Valider une correction |
| --- | --- | --- | --- |
| Directeur général | Visibles | Visibles | Oui |
| Stagiaire logistique | Masquées (●●●●) | Visibles | Non |

Chaque question posée au copilote et chaque validation de correction est inscrite dans `cache/audit.csv`.

## 7. Les trois écrans montrés au jury

1. **Données** : tableau des fichiers avec leur note colorée ; en dessous, les problèmes du fichier choisi ; bouton « Valider les corrections » (désactivé pour le stagiaire) ; note globale avant et après.
2. **Chaîne** : choix du fournisseur et curseur du retard ; carte du résultat (arrêt, manque, commandes, clients) ; graphe de la chaîne ; trois cartes pour les options A, B et C.
3. **Copilote** : zone de discussion ; sous chaque réponse, les fichiers sources et un badge de confiance coloré ; « à confirmer » en rouge si la confiance est basse.

## 8. Critères d'acceptation

- [ ] `python check_scenario.py` et `python check_specs.py` finissent par « OK ».
- [ ] Page 1 : la note globale monte après validation des corrections ; le stagiaire ne peut pas valider.
- [ ] Page 2 : avec Delta et 5 jours de retard, l'arrêt à J+4, le manque de 1 200 et les 3 options s'affichent.
- [ ] Page 3 : une question sur le retard Delta donne une réponse avec sources, score et couleur de confiance.
- [ ] Hors ligne, le copilote répond depuis `cache/answers.json`.
- [ ] Le scénario complet se joue en moins de 3 minutes sans erreur.

## 9. Hors périmètre du prototype

Connecteurs vers de vrais systèmes, vraie authentification, hébergement sécurisé, données réelles. Ils sont dans la feuille de route (étape 6).
