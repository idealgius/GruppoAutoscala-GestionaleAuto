import sqlite3

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# Elimina le tabelle esistenti
cursor.execute("DROP TABLE IF EXISTS clienti")
cursor.execute("DROP TABLE IF EXISTS vetture")
cursor.execute("DROP TABLE IF EXISTS prodotti")

# Tabella clienti
cursor.execute("""
CREATE TABLE clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cognome TEXT,
    data_nascita TEXT,
    provincia TEXT,
    comune TEXT,
    codice_fiscale TEXT,
    telefono TEXT,
    email TEXT
)
""")

# Tabella vetture
cursor.execute("""
CREATE TABLE vetture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    marca TEXT,
    modello TEXT,
    cilindrata TEXT,
    kw TEXT,
    carburante TEXT,
    targa TEXT,
    telaio TEXT,
    immatricolazione TEXT,
    km TEXT,
    cambio TEXT,
    codice_motore TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clienti(id)
)
""")

# Tabella prodotti (filtri, olio ecc.)
cursor.execute("""
CREATE TABLE prodotti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT,
    modello TEXT,
    cilindrata TEXT,
    kw TEXT,
    carburante TEXT,
    filtro_olio TEXT,
    filtro_aria TEXT,
    filtro_abitacolo TEXT,
    filtro_carburante TEXT,
    olio_motore TEXT
)
""")

conn.commit()
conn.close()

print("✅ Database aggiornato correttamente.")
