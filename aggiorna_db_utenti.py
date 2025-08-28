import sqlite3

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# 1️⃣ Creazione tabella utenti
cursor.execute("""
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")
print("✅ Tabella 'utenti' creata o già presente.")

# 2️⃣ Aggiunta colonna utente_id in clienti se non esiste
cursor.execute("PRAGMA table_info(clienti)")
columns_clienti = [col[1] for col in cursor.fetchall()]
if "utente_id" not in columns_clienti:
    cursor.execute("ALTER TABLE clienti ADD COLUMN utente_id INTEGER")
    print("✅ Colonna 'utente_id' aggiunta in 'clienti'.")
else:
    print("ℹ️ Colonna 'utente_id' già presente in 'clienti'.")

# 3️⃣ Aggiunta colonna utente_id in vetture se non esiste
cursor.execute("PRAGMA table_info(vetture)")
columns_vetture = [col[1] for col in cursor.fetchall()]
if "utente_id" not in columns_vetture:
    cursor.execute("ALTER TABLE vetture ADD COLUMN utente_id INTEGER")
    print("✅ Colonna 'utente_id' aggiunta in 'vetture'.")
else:
    print("ℹ️ Colonna 'utente_id' già presente in 'vetture'.")

conn.commit()
conn.close()

print("🎯 Aggiornamento database completato!")
