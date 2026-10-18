# BAOBAB

<p align="center"><img src="app/assets/baobab.png" alt="L'arbre BAOBAB : racines, tronc, cime" width="300"></p>

> Des racines propres, un tronc qui relie tout, une cime qui éclaire les décisions.

**[🌐 Essayer la démo en ligne](LIEN_SITE)** · **[▶️ Voir la vidéo de démonstration](LIEN_YOUTUBE)**

Prototype réalisé pour le **CREATE WITH AI Hackathon** (JNC Africa, 2026). Il fiabilise les données d'une entreprise, relie sa chaîne de production, et répond aux questions en français avec ses sources et un score de confiance. Toutes les données sont **fictives** (usine de jus de fruits « Délice SA »).

## Ce que fait BAOBAB

| Page | Rôle | Ce qu'on y voit |
| --- | --- | --- |
| **Données** (racines) | DataCompass | Scanne 6 fichiers (6 517 lignes), détecte 2 228 problèmes (doublons, e-mails manquants, unités mélangées…), propose 1 419 corrections que le directeur valide. Lignes sans défaut : 68,8 % → 87,8 %. |
| **Chaîne** (tronc) | SupplyMind | Relie fournisseurs, matières, lignes, produits, commandes et clients. Simule le retard d'un fournisseur : arrêt de production, manque, commandes et clients touchés, trois solutions chiffrées. |
| **Copilote** (cime) | Copilote | Répond en français, cite ses fichiers sources, affiche un score de confiance (vert, orange, rouge « à confirmer »). Fonctionne aussi sans Internet. |

**Scénario de démonstration :** le fournisseur Delta annonce 5 jours de retard. La Ligne 2 s'arrêterait à J+4, il manquerait 1 200 unités, 3 commandes et 2 clients seraient touchés. Option A : transférer le stock de l'entrepôt Nord (0 % de surcoût, risque moyen). Option B : commande express chez Sigma (+6 %, risque faible). Option C : reporter la production (+2 %, risque élevé).

## Comment ça marche

- **L'IA ne calcule jamais.** Le copilote choisit parmi des fonctions de calcul vérifiables (`get_stock_coverage`, `simulate_supplier_delay`, `list_options`, `get_trust`, `get_passport`) et reformule leur résultat. Chaque chiffre vient d'une de ces fonctions.
- **Score de confiance :** moyenne pondérée des notes de qualité des fichiers utilisés, plafonnée à la note du fichier le plus faible plus 15 points. Vert à partir de 80, orange de 60 à 79, rouge en dessous de 60.
- **Mode hors ligne :** sans clé d'API ni Internet, un moteur de secours appelle les mêmes fonctions. Les chiffres, sources et scores sont identiques ; seule la formulation change.
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
python check_copilot.py    # copilote, droits, mode hors ligne
```

Chaque commande doit se terminer par « OK ».

## Structure

- `app/` : application Streamlit (accueil, Données, Chaîne, Copilote, thème et visuels)
- `core/` : logique métier (`quality`, `graph`, `simulate`, `trust`, `rbac`, `pii`, `copilot`, `loader`)
- `config/params.json` : paramètres du scénario (retard, stocks, surcoûts, seuils de confiance)
- `generate_data.py` : génère les données fictives avec des défauts placés volontairement
- `SPECS.md` : contrat entre les modules

## Limites assumées

- Les données sont fictives : BAOBAB n'a pas encore été testé sur les fichiers d'une vraie entreprise.
- Les rôles sont simulés (pas de connexion avec mot de passe) : c'est un prototype de démonstration.
- Testé sur 6 517 lignes ; pour des volumes bien plus grands, les fichiers seraient remplacés par une base de données.
