import sqlite3
import hashlib

# Lista utenti da inserire: (username, password, nome_reale)
utenti = [
    ("G.AS_Gianluca.Scala", "000GruppoAutoScala2025", "Gianluca Scala"),
    ("G.AS_Clemente.Palladino", "001GruppoAutoScala2025", "Clemente Palladino"),
    ("G.AS_Carlo.Postiglione", "002GruppoAutoScala2025", "Carlo Postiglione"),
    ("G.AS_Giuseppe.Palladino", "003GruppoAutoScala2025", "Giuseppe Palladino")
]

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# Creazione tabella utenti se non esiste
cursor.execute("""
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    nome_reale TEXT NOT NULL
)
""")

for username, password, nome_reale in utenti:
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    try:
        cursor.execute("INSERT INTO utenti (username, password, nome_reale) VALUES (?, ?, ?)",
                       (username, hashed_pw, nome_reale))
        print(f"✅ Utente '{username}' inserito correttamente")
    except sqlite3.IntegrityError:
        print(f"⚠️ Utente '{username}' già presente nel database")

conn.commit()
conn.close()
