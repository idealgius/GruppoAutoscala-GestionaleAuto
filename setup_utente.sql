-- Creazione tabella utenti
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

-- Aggiunta colonna utente_id nella tabella clienti
ALTER TABLE clienti ADD COLUMN IF NOT EXISTS utente_id INTEGER;

-- Aggiunta colonna utente_id nella tabella vetture
ALTER TABLE vetture ADD COLUMN IF NOT EXISTS utente_id INTEGER;
