# BAOBAB

Prototype pour le CREATE WITH AI Hackathon : fiabiliser les données d'une entreprise (DataCompass),
relier sa chaîne de production (SupplyMind) et répondre avec un score de confiance. Données **fictives**.

## Démarrage (10 minutes)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python generate_data.py          # crée les 7 jeux de données dans data/
python check_scenario.py         # doit afficher OK (arrêt J+4, manque 1 200)
streamlit run app/main.py        # ouvre l'application (3 pages)
```

Copie `.env.example` en `.env` et mets-y ta clé d'API quand le copilote sera branché.

## Structure

- `generate_data.py` données fictives de « Délice SA » avec défauts volontaires
- `config/params.json` paramètres du scénario de démo (retard Delta, stocks, surcoûts)
- `core/` logique métier (chargement ; qualité, simulation, confiance arrivent ensuite)
- `app/` application Streamlit (accueil + 3 pages, choix du rôle dans la barre latérale)
- `cache/` réponses de secours du copilote
