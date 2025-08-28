import sqlite3

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# Crea tabella vetture solo se non esiste già
cursor.execute("""
CREATE TABLE IF NOT EXISTS vetture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    marca TEXT,
    modello TEXT,
    targa TEXT,
    anno_immatricolazione TEXT,
    cilindrata TEXT,
    kw TEXT,
    carburante TEXT,
    cambio TEXT,
    codice_motore TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clienti(id)
)
""")

conn.commit()
conn.close()

print("✅ Tabella vetture creata correttamente.")
