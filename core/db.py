"""Base de donnees SQLite de Baobab Seve (module standard de Python : gratuit, sans serveur, sans cle).

Une base par visiteur (un fichier .db) contient :
  - les 6 tables de donnees, que les corrections validees modifient ;
  - le journal des actions (audit) ;
  - l'historique de la note de qualite (instantanes) ;
  - les validations (lots) et le detail de chaque changement, ce qui permet d'annuler la derniere validation ;
  - les decisions retenues (solution choisie dans SupplyMind).
Les colonnes de donnees n'ont pas de type declare : SQLite garde alors chaque valeur telle quelle (texte, entier,
decimal), ce qui evite toute conversion silencieuse.
"""
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "cache" / "db"
DEFAULT_PATH = ROOT / "cache" / "baobab.db"
TABLES = ["employes", "clients", "stocks", "fournisseurs", "production", "commandes"]
INDEX = "rid"  # identifiant de ligne : reprend l'index du DataFrame, pour retrouver une ligne corrigee

SCHEMA_SYSTEME = """
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, horodatage TEXT, role TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS instantanes (id INTEGER PRIMARY KEY, horodatage TEXT, evenement TEXT, note REAL,
    lignes_saines REAL, problemes INTEGER);
CREATE TABLE IF NOT EXISTS lots (id INTEGER PRIMARY KEY, horodatage TEXT, role TEXT, resume TEXT,
    nb_changements INTEGER, annule INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS changements (id INTEGER PRIMARY KEY, lot_id INTEGER, fichier TEXT, nature TEXT,
    ligne TEXT, colonne TEXT, ancienne TEXT, nouvelle TEXT);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, horodatage TEXT, role TEXT, fournisseur TEXT,
    retard_jours INTEGER, option_code TEXT, libelle TEXT);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def path_for(session_id):
    """Chemin de la base d'un visiteur."""
    return DB_DIR / f"{session_id}.db"


@contextmanager
def connect(path=None):
    path = Path(path or DEFAULT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------ valeurs <-> JSON
def _py(v):
    """Valeur Python simple (SQLite ne comprend pas les types numpy) ; les valeurs vides deviennent NULL."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def _enc(v):
    return json.dumps(_py(v), ensure_ascii=False)


def _dec(s):
    return json.loads(s) if s is not None else None


# ------------------------------------------------------------------ tables de donnees
def _ecrire_table(con, nom, df):
    colonnes = list(df.columns)
    con.execute(f'DROP TABLE IF EXISTS "{nom}"')
    defs = ", ".join([f'"{INDEX}" INTEGER PRIMARY KEY'] + [f'"{c}"' for c in colonnes])  # colonnes sans type
    con.execute(f'CREATE TABLE "{nom}" ({defs})')
    marques = ", ".join("?" * (len(colonnes) + 1))
    con.executemany(f'INSERT INTO "{nom}" VALUES ({marques})',
                    [[int(i)] + [_py(v) for v in ligne] for i, ligne in zip(df.index, df.itertuples(index=False, name=None))])


def has_data(path=None):
    path = Path(path or DEFAULT_PATH)
    if not path.exists():
        return False
    with closing(sqlite3.connect(path)) as con:
        noms = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return set(TABLES) <= noms


def init_db(data, path=None):
    """Cree la base (ou la recree) a partir des donnees d'origine."""
    path = Path(path or DEFAULT_PATH)
    if path.exists():
        path.unlink()
    with connect(path) as con:
        con.executescript(SCHEMA_SYSTEME)
        for nom in TABLES:
            _ecrire_table(con, nom, data[nom])


def save_tables(data, path=None):
    with connect(path) as con:
        for nom in TABLES:
            _ecrire_table(con, nom, data[nom])


def load_tables(path=None):
    """Retourne {nom: DataFrame} lu dans la base, dans l'ordre d'origine des lignes."""
    out = {}
    with closing(sqlite3.connect(Path(path or DEFAULT_PATH))) as con:
        for nom in TABLES:
            df = pd.read_sql_query(f'SELECT * FROM "{nom}" ORDER BY "{INDEX}"', con, index_col=INDEX)
            df.index.name = None
            out[nom] = df
    return out


def table_counts(path=None):
    with closing(sqlite3.connect(Path(path or DEFAULT_PATH))) as con:
        return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in TABLES}


# ------------------------------------------------------------------ journal des actions
def log_action(role, action, detail="", path=None):
    with connect(path) as con:
        con.executescript(SCHEMA_SYSTEME)
        con.execute("INSERT INTO audit (horodatage, role, action, detail) VALUES (?,?,?,?)", (_now(), role, action, detail))


def read_log(path=None):
    p = Path(path or DEFAULT_PATH)
    if not p.exists():
        return pd.DataFrame(columns=["horodatage", "role", "action", "detail"])
    with closing(sqlite3.connect(p)) as con:
        con.executescript(SCHEMA_SYSTEME)
        return pd.read_sql_query("SELECT horodatage, role, action, detail FROM audit ORDER BY id", con)


# ------------------------------------------------------------------ historique de la note
def add_snapshot(evenement, note, lignes_saines, problemes, path=None):
    with connect(path) as con:
        con.execute("INSERT INTO instantanes (horodatage, evenement, note, lignes_saines, problemes) VALUES (?,?,?,?,?)",
                    (_now(), evenement, float(note), float(lignes_saines), int(problemes)))


def read_snapshots(path=None):
    with closing(sqlite3.connect(Path(path or DEFAULT_PATH))) as con:
        return pd.read_sql_query("SELECT * FROM instantanes ORDER BY id", con)


# ------------------------------------------------------------------ validations et annulation
def _egal(a, b):
    a, b = _py(a), _py(b)
    return a == b


def diff_tables(avant, apres):
    """Liste des changements entre deux jeux de donnees : cellules modifiees et lignes supprimees."""
    changements = []
    for nom in TABLES:
        a, b = avant[nom], apres[nom]
        for idx in a.index.difference(b.index):
            changements.append({"fichier": nom, "nature": "ligne_supprimee", "ligne": int(idx), "colonne": None,
                                "ancienne": _enc({c: _py(a.at[idx, c]) for c in a.columns}), "nouvelle": None})
        for idx in a.index.intersection(b.index):
            for c in a.columns:
                if not _egal(a.at[idx, c], b.at[idx, c]):
                    changements.append({"fichier": nom, "nature": "cellule", "ligne": int(idx), "colonne": c,
                                        "ancienne": _enc(a.at[idx, c]), "nouvelle": _enc(b.at[idx, c])})
    return changements


def record_validation(role, avant, apres, resume, path=None):
    """Enregistre une validation : ecrit les nouvelles donnees et garde le detail de chaque changement."""
    changements = diff_tables(avant, apres)
    with connect(path) as con:
        con.executescript(SCHEMA_SYSTEME)
        cur = con.execute("INSERT INTO lots (horodatage, role, resume, nb_changements) VALUES (?,?,?,?)",
                          (_now(), role, resume, len(changements)))
        lot = cur.lastrowid
        con.executemany("INSERT INTO changements (lot_id, fichier, nature, ligne, colonne, ancienne, nouvelle) "
                        "VALUES (?,?,?,?,?,?,?)",
                        [(lot, c["fichier"], c["nature"], c["ligne"], c["colonne"], c["ancienne"], c["nouvelle"])
                         for c in changements])
        for nom in TABLES:
            _ecrire_table(con, nom, apres[nom])
    return lot, len(changements)


def read_lots(path=None):
    with closing(sqlite3.connect(Path(path or DEFAULT_PATH))) as con:
        con.executescript(SCHEMA_SYSTEME)
        return pd.read_sql_query("SELECT id, horodatage, role, resume, nb_changements, annule FROM lots ORDER BY id DESC", con)


def can_undo(path=None):
    lots = read_lots(path)
    return bool(len(lots) and (lots["annule"] == 0).any())


def undo_last(path=None):
    """Annule la derniere validation non annulee. Retourne (numero du lot, nombre de changements) ou None."""
    with connect(path) as con:
        con.executescript(SCHEMA_SYSTEME)
        r = con.execute("SELECT id FROM lots WHERE annule=0 ORDER BY id DESC LIMIT 1").fetchone()
        if r is None:
            return None
        lot = r[0]
        rows = con.execute("SELECT fichier, nature, ligne, colonne, ancienne FROM changements WHERE lot_id=?", (lot,)).fetchall()
        for fichier, nature, ligne, colonne, ancienne in rows:
            if nature == "cellule":
                con.execute(f'UPDATE "{fichier}" SET "{colonne}"=? WHERE "{INDEX}"=?', (_dec(ancienne), int(ligne)))
            else:  # ligne supprimee : on la remet a sa place
                valeurs = _dec(ancienne)
                cols = list(valeurs)
                con.execute(f'INSERT INTO "{fichier}" ("{INDEX}", ' + ", ".join(f'"{c}"' for c in cols) + ") VALUES (?, "
                            + ", ".join("?" * len(cols)) + ")", [int(ligne)] + [valeurs[c] for c in cols])
        con.execute("UPDATE lots SET annule=1 WHERE id=?", (lot,))
        return lot, len(rows)


# ------------------------------------------------------------------ decisions
def add_decision(role, fournisseur, retard_jours, option_code, libelle, path=None):
    with connect(path) as con:
        con.executescript(SCHEMA_SYSTEME)
        con.execute("INSERT INTO decisions (horodatage, role, fournisseur, retard_jours, option_code, libelle) VALUES (?,?,?,?,?,?)",
                    (_now(), role, fournisseur, int(retard_jours), option_code, libelle))


def read_decisions(path=None):
    with closing(sqlite3.connect(Path(path or DEFAULT_PATH))) as con:
        con.executescript(SCHEMA_SYSTEME)
        return pd.read_sql_query("SELECT horodatage, role, fournisseur, retard_jours, option_code, libelle "
                                 "FROM decisions ORDER BY id DESC", con)


# ------------------------------------------------------------------ requetes libres (lecture seule)
def run_select(sql, path=None, limite=500):
    """Execute UNE requete de lecture (SELECT ou WITH). Tout le reste est refuse. Retourne un DataFrame."""
    texte = sql.strip().rstrip(";").strip()
    if not texte:
        raise ValueError("Requête vide.")
    if ";" in texte:
        raise ValueError("Une seule requête à la fois.")
    if texte.split(None, 1)[0].lower() not in ("select", "with"):
        raise ValueError("Seules les requêtes de lecture (SELECT) sont autorisées.")
    uri = f"file:{Path(path or DEFAULT_PATH).as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        con.execute("PRAGMA query_only = ON")
        cur = con.execute(texte)
        colonnes = [d[0] for d in cur.description]
        lignes = cur.fetchmany(limite)
    return pd.DataFrame(lignes, columns=colonnes)
