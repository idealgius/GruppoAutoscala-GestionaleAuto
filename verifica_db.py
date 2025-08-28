import sqlite3

conn = sqlite3.connect("concessionaria.db")
cursor = conn.cursor()

# Controlla se la tabella 'utenti' esiste
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='utenti';")
tabella_utenti = cursor.fetchone()
if tabella_utenti:
    print("✅ La tabella 'utenti' esiste.")
else:
    print("❌ La tabella 'utenti' NON esiste.")

# Controlla colonne nella tabella 'clienti'
cursor.execute("PRAGMA table_info(clienti);")
colonne_clienti = [col[1] for col in cursor.fetchall()]
print(f"Colonne in 'clienti': {colonne_clienti}")
if "utente_id" in colonne_clienti:
    print("✅ 'utente_id' presente in 'clienti'.")
else:
    print("❌ 'utente_id' MANCANTE in 'clienti'.")

# Controlla colonne nella tabella 'vetture'
cursor.execute("PRAGMA table_info(vetture);")
colonne_vetture = [col[1] for col in cursor.fetchall()]
print(f"Colonne in 'vetture': {colonne_vetture}")
if "utente_id" in colonne_vetture:
    print("✅ 'utente_id' presente in 'vetture'.")
else:
    print("❌ 'utente_id' MANCANTE in 'vetture'.")

conn.close()
