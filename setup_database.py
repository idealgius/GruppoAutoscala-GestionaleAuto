import sqlite3

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cognome TEXT NOT NULL,
    telefono TEXT,
    email TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vetture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    marca TEXT NOT NULL,
    modello TEXT NOT NULL,
    targa TEXT UNIQUE NOT NULL,
    anno INTEGER,
    FOREIGN KEY (cliente_id) REFERENCES clienti(id)
)
""")

conn.commit()
conn.close()

print("✅ Database e tabelle creati con successo!")
