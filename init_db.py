import sqlite3
import hashlib

# Connessione al database (verrà creato se non esiste)
conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# ---------- Creazione tabelle ----------

# Tabella utenti
cursor.execute("""
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

# Tabella clienti
cursor.execute("""
CREATE TABLE IF NOT EXISTS clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cognome TEXT,
    data_nascita TEXT,
    provincia TEXT,
    comune TEXT,
    codice_fiscale TEXT,
    telefono TEXT,
    email TEXT,
    utente_id INTEGER
)
""")

# Tabella vetture
cursor.execute("""
CREATE TABLE IF NOT EXISTS vetture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    targa TEXT,
    marca TEXT,
    modello TEXT,
    cilindrata TEXT,
    kw TEXT,
    carburante TEXT,
    codice_motore TEXT,
    telaio TEXT,
    immatricolazione TEXT,
    km TEXT,
    cambio TEXT,
    utente_id INTEGER
)
""")

# ---------- NUOVE TABELLE ----------

# Tabella modelli
cursor.execute("""
CREATE TABLE IF NOT EXISTS modelli (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL,
    modello TEXT NOT NULL,
    cilindrata TEXT,
    kw TEXT,
    codice_motore TEXT,
    utente_id INTEGER NOT NULL,
    UNIQUE(marca, modello, cilindrata, kw, codice_motore)
)
""")

# Tabella ricambi
cursor.execute("""
CREATE TABLE IF NOT EXISTS ricambi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    codice TEXT NOT NULL UNIQUE,
    utente_id INTEGER NOT NULL
)
""")

# Tabella relazione modelli-ricambi
cursor.execute("""
CREATE TABLE IF NOT EXISTS modello_ricambi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    modello_id INTEGER NOT NULL,
    ricambio_id INTEGER NOT NULL,
    utente_id INTEGER NOT NULL,
    UNIQUE(modello_id, ricambio_id)
)
""")

# ---------- Inserimento utenti iniziali ----------
utenti_iniziali = [
    ("G.AS_Gianluca.Scala", hashlib.sha256("password1".encode()).hexdigest()),
    ("G.AS_Clemente.Palladino", hashlib.sha256("password2".encode()).hexdigest()),
    ("G.AS_Carlo.Postiglione", hashlib.sha256("password3".encode()).hexdigest()),
    ("G.AS_Giuseppe.Palladino", hashlib.sha256("password4".encode()).hexdigest())
]

for username, pw_hash in utenti_iniziali:
    cursor.execute("SELECT id FROM utenti WHERE username=?", (username,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO utenti (username, password) VALUES (?, ?)", (username, pw_hash))

conn.commit()
conn.close()

print("Database, tabelle e utenti iniziali creati correttamente!")
