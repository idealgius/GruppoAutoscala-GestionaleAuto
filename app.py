from flask import Flask, render_template, request, redirect, session, url_for, flash
from functools import wraps
import hashlib
import os
import re
import psycopg2
import psycopg2.extras

# ----- Row adapter per compatibilità (accesso sia per indice che per nome) -----
class RowAdapter:
    def __init__(self, row_dict, columns):
        """
        row_dict: dict-like mapping column->value (es. from RealDictCursor)
        columns: ordered list of column names (so row[0] works)
        """
        self._data = row_dict or {}
        self._cols = columns or []

    def __getitem__(self, key):
        # support integer index
        if isinstance(key, int):
            if 0 <= key < len(self._cols):
                return self._data.get(self._cols[key])
            raise IndexError("RowAdapter index out of range")
        # support string key
        return self._data.get(key)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __repr__(self):
        return f"<RowAdapter {self._data}>"

# ----- DB wrapper per PostgreSQL (mantiene compatibilità con l'uso attuale di '?' e ':name') -----
class CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        # Save column order from description (may be None if no result)
        desc = getattr(cursor, "description", None)
        if desc:
            self._columns = [d[0] for d in desc]
        else:
            self._columns = []

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        # If it's a dict-like (RealDictCursor), convert to RowAdapter preserving order
        if isinstance(row, dict):
            return RowAdapter(row, self._columns)
        # If it's a sequence (tuple), convert to dict using columns
        if isinstance(row, (list, tuple)):
            d = {self._columns[i]: row[i] for i in range(len(self._columns))}
            return RowAdapter(d, self._columns)
        # Fallback: try to cast to dict
        try:
            d = dict(row)
            return RowAdapter(d, self._columns)
        except Exception:
            return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows is None:
            return []
        adapted = []
        for row in rows:
            if isinstance(row, dict):
                adapted.append(RowAdapter(row, self._columns))
            elif isinstance(row, (list, tuple)):
                d = {self._columns[i]: row[i] for i in range(len(self._columns))}
                adapted.append(RowAdapter(d, self._columns))
            else:
                try:
                    d = dict(row)
                    adapted.append(RowAdapter(d, self._columns))
                except Exception:
                    adapted.append(row)
        return adapted

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class DBConn:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, query, params=()):
        """
        Support two parameter styles:
         - Named params with :name  (converted to %(name)s)
         - Positional with ?        (converted to %s)
        Works with dict or sequence params.
        """
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Named parameters :name -> %(name)s
        if isinstance(params, dict):
            q = re.sub(r':([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', query)
            cur.execute(q, params)
        else:
            # positional params: replace '?' with '%s' (only for convenience)
            if '?' in query:
                q = query.replace('?', '%s')
            else:
                q = query
            if isinstance(params, (list, tuple)):
                cur.execute(q, params)
            else:
                # single scalar param
                cur.execute(q, (params,))
        return CursorWrapper(cur)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()


# ----- Avvio app con percorso templates corretto -----
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
app.secret_key = "supersecretkey123"  # 🔒 Cambia in produzione

# ---------- Mappa username -> nome reale ----------
NOMI_REAL = {
    "G.AS_Gianluca.Scala": "Gianluca Scala",
    "G.AS_Clemente.Palladino": "Clemente Palladino",
    "G.AS_Carlo.Postiglione": "Carlo Postiglione",
    "G.AS_Giuseppe.Palladino": "Giuseppe Palladino"
}

# ---------- Connessione DB (solo PostgreSQL) ----------
def get_db():
    """
    Costruisce la stringa di connessione PostgreSQL in questo ordine di priorità:
    1) DATABASE_URL (es. postgres://user:pass@host:port/dbname)
    2) POSTGRES_USER + POSTGRES_PASSWORD (opzionali) + POSTGRES_DB (default gestionaleauto_gruppoautoscala)
       + POSTGRES_HOST (default localhost) + POSTGRES_PORT (default 5432)
    Se non trova credenziali sufficienti, solleva un errore chiaro.
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # preferiamo la variabile pronta
        conn = psycopg2.connect(db_url, sslmode="require")
        return DBConn(conn)

    # altrimenti compone dalla singole variabili (più comodo per sviluppo)
    pg_user = os.environ.get("POSTGRES_USER")
    pg_password = os.environ.get("POSTGRES_PASSWORD")
    pg_db = os.environ.get("POSTGRES_DB", "gestionaleauto_gruppoautoscala")
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")

    if pg_user and pg_password:
        conn_str = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        conn = psycopg2.connect(conn_str, sslmode="require")
        return DBConn(conn)

    # altrimenti errore esplicito (così non proseguiamo in errore silenzioso)
    raise RuntimeError(
        "Variabile DATABASE_URL non impostata e POSTGRES_USER/POSTGRES_PASSWORD non fornite.\n"
        "Imposta DATABASE_URL (es. 'postgresql://user:pass@host:port/dbname') oppure\n"
        "imposta POSTGRES_USER e POSTGRES_PASSWORD e (opz.) POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT."
    )


# ---------- Assicura colonna "quantita" in ricambi ----------
# Questo codice tenta di aggiungere la colonna (se non esiste) ma non interrompe l'app in caso di errore.
try:
    tmp_conn = get_db()
    tmp_conn.execute("ALTER TABLE ricambi ADD COLUMN quantita INTEGER DEFAULT 0")
    tmp_conn.commit()
except Exception:
    pass
finally:
    try:
        tmp_conn.close()
    except Exception:
        pass


# ---------- Decoratore protezione ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Funzione helper per scalare giacenza ----------
def scalo_ricambio(ricambio_id):
    conn = get_db()
    conn.execute(
        "UPDATE ricambi SET quantita = quantita - 1 WHERE id=? AND utente_id=?",
        (ricambio_id, session["user_id"])
    )
    conn.commit()
    q = conn.execute(
        "SELECT quantita, nome FROM ricambi WHERE id=? AND utente_id=?",
        (ricambio_id, session["user_id"])
    ).fetchone()
    conn.close()
    if q:
        nome = q["nome"]
        quantita = q["quantita"]
        if quantita == 2:
            flash(f"⚠️ Giacenza bassa per {nome} (2 rimasti)")
        elif quantita == 1:
            flash(f"⚠️ Solo 1 {nome} rimasto")
        elif quantita == 0:
            flash(f"❌ {nome} esaurito!")

# ---------- LOGIN/LOGOUT ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        user = conn.execute(
            "SELECT id FROM utenti WHERE username=? AND password=?",
            (username, hashed_pw)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = username
            flash(f"✅ Benvenuto, {NOMI_REAL.get(username, username)}!")
            return redirect(url_for("home"))
        flash("❌ Username o password errati")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logout effettuato correttamente")
    return redirect(url_for("login"))

# ---------- HOME ----------
@app.route("/")
def home():
    if "user_id" not in session:
        # Se l'utente non è loggato, vai al login
        return redirect(url_for("login"))

    username = session.get("username")
    nome_reale = NOMI_REAL.get(username, username)
    mostra_menu = True
    return render_template("home.html", nome_reale=nome_reale, mostra_menu=mostra_menu)

# =========================
#          CLIENTI
# =========================
@app.route("/inserisci_cliente")
@login_required
def inserisci_cliente():
    return render_template("inserisci_cliente.html")

@app.route("/salva_cliente", methods=["POST"])
@login_required
def salva_cliente():
    dati = {k: request.form.get(k, "").strip() for k in
            ["nome", "cognome", "data_nascita", "provincia", "comune",
             "codice_fiscale", "telefono", "email"]}
    dati["utente_id"] = session["user_id"]

    conn = get_db()
    conn.execute("""
        INSERT INTO clienti (nome, cognome, data_nascita, provincia, comune, codice_fiscale, telefono, email, utente_id)
        VALUES (:nome, :cognome, :data_nascita, :provincia, :comune, :codice_fiscale, :telefono, :email, :utente_id)
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Cliente salvato correttamente")
    return redirect(url_for("lista_clienti"))

@app.route("/clienti")
@login_required
def lista_clienti():
    conn = get_db()
    clienti = conn.execute(
        "SELECT * FROM clienti WHERE utente_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("clienti.html", clienti=clienti)

@app.route("/modifica_cliente/<int:id>")
@login_required
def modifica_cliente(id):
    conn = get_db()
    cliente = conn.execute(
        "SELECT * FROM clienti WHERE id=? AND utente_id=?", (id, session["user_id"])
    ).fetchone()
    conn.close()
    if cliente:
        return render_template("modifica_cliente.html", cliente=cliente)
    flash(f"❌ Cliente ID {id} non trovato o non accessibile")
    return redirect(url_for("lista_clienti"))

@app.route("/aggiorna_cliente/<int:id>", methods=["POST"])
@login_required
def aggiorna_cliente(id):
    dati = {k: request.form.get(k, "").strip() for k in
            ["nome", "cognome", "data_nascita", "provincia", "comune",
             "codice_fiscale", "telefono", "email"]}
    dati["utente_id"] = session["user_id"]
    dati["id"] = id

    conn = get_db()
    conn.execute("""
        UPDATE clienti
        SET nome=:nome, cognome=:cognome, data_nascita=:data_nascita, provincia=:provincia, comune=:comune,
            codice_fiscale=:codice_fiscale, telefono=:telefono, email=:email
        WHERE id=:id AND utente_id=:utente_id
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Cliente aggiornato correttamente")
    return redirect(url_for("lista_clienti"))

@app.route("/elimina_cliente/<int:id>")
@login_required
def elimina_cliente(id):
    conn = get_db()
    vetture_collegate = conn.execute(
        "SELECT COUNT(*) as c FROM vetture WHERE cliente_id=? AND utente_id=?",
        (id, session["user_id"])
    ).fetchone()["c"]
    if vetture_collegate > 0:
        conn.close()
        flash(f"❌ Non puoi eliminare: il cliente ha {vetture_collegate} vettura/e associate.")
        return redirect(url_for("lista_clienti"))
    conn.execute("DELETE FROM clienti WHERE id=? AND utente_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("✅ Cliente eliminato")
    return redirect(url_for("lista_clienti"))

# =========================
#          VETTURE
# =========================
@app.route("/inserisci_vettura")
@login_required
def inserisci_vettura():
    conn = get_db()
    clienti = conn.execute(
        "SELECT id, nome, cognome FROM clienti WHERE utente_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("inserisci_vettura.html", clienti=clienti)

@app.route("/salva_vettura", methods=["POST"])
@login_required
def salva_vettura():
    dati = {k: request.form.get(k, "").strip() for k in
            ["targa", "marca", "modello", "cilindrata", "kw", "carburante",
             "codice_motore", "telaio", "immatricolazione", "km", "cambio"]}
    dati["cliente_id"] = request.form.get("cliente_id", "").strip()
    dati["utente_id"] = session["user_id"]

    conn = get_db()
    conn.execute("""
        INSERT INTO vetture (cliente_id, targa, marca, modello, cilindrata, kw, carburante,
                             codice_motore, telaio, immatricolazione, km, cambio, utente_id)
        VALUES (:cliente_id, :targa, :marca, :modello, :cilindrata, :kw, :carburante,
                :codice_motore, :telaio, :immatricolazione, :km, :cambio, :utente_id)
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Vettura salvata correttamente")
    return redirect(url_for("lista_vetture"))

@app.route("/vetture")
@login_required
def lista_vetture():
    conn = get_db()
    vetture = conn.execute("""
        SELECT v.id, v.targa, v.marca, v.modello, v.cilindrata, v.kw, v.carburante, v.codice_motore,
               COALESCE(c.nome || ' ' || c.cognome, '—') AS cliente_nome
        FROM vetture v
        LEFT JOIN clienti c ON v.cliente_id=c.id
        WHERE v.utente_id=?
        ORDER BY v.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("vetture.html", vetture=vetture)

@app.route("/modifica_vettura/<int:id>")
@login_required
def modifica_vettura(id):
    conn = get_db()
    vettura = conn.execute(
        "SELECT * FROM vetture WHERE id=? AND utente_id=?", (id, session["user_id"])
    ).fetchone()
    clienti = conn.execute(
        "SELECT id, nome, cognome FROM clienti WHERE utente_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    if vettura:
        return render_template("modifica_vettura.html", vettura=vettura, clienti=clienti)
    flash(f"❌ Vettura ID {id} non trovata o non accessibile")
    return redirect(url_for("lista_vetture"))

@app.route("/aggiorna_vettura/<int:id>", methods=["POST"])
@login_required
def aggiorna_vettura(id):
    dati = {k: request.form.get(k, "").strip() for k in
            ["targa", "marca", "modello", "cilindrata", "kw", "carburante",
             "codice_motore", "telaio", "immatricolazione", "km", "cambio"]}
    dati["cliente_id"] = request.form.get("cliente_id", "").strip()
    dati["utente_id"] = session["user_id"]
    dati["id"] = id

    conn = get_db()
    conn.execute("""
        UPDATE vetture
        SET cliente_id=:cliente_id, targa=:targa, marca=:marca, modello=:modello,
            cilindrata=:cilindrata, kw=:kw, carburante=:carburante,
            codice_motore=:codice_motore, telaio=:telaio,
            immatricolazione=:immatricolazione, km=:km, cambio=:cambio
        WHERE id=:id AND utente_id=:utente_id
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Vettura aggiornata correttamente")
    return redirect(url_for("lista_vetture"))

@app.route("/elimina_vettura/<int:id>")
@login_required
def elimina_vettura(id):
    conn = get_db()
    conn.execute("DELETE FROM vetture WHERE id=? AND utente_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("✅ Vettura eliminata correttamente")
    return redirect(url_for("lista_vetture"))

# =========================
#          MODELLI
# =========================
@app.route("/modelli")
@login_required
def lista_modelli():
    conn = get_db()
    modelli = conn.execute("""
        SELECT id, marca, modello, cilindrata, kw, carburante, codice_motore
        FROM modelli
        WHERE utente_id=?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("modelli.html", modelli=modelli)

@app.route("/inserisci_modello")
@login_required
def inserisci_modello():
    return render_template("inserisci_modello.html")

@app.route("/salva_modello", methods=["POST"])
@login_required
def salva_modello():
    dati = {k: request.form.get(k, "").strip() for k in
            ["marca", "modello", "cilindrata", "kw", "carburante", "codice_motore"]}
    dati["utente_id"] = session["user_id"]

    conn = get_db()
    conn.execute("""
        INSERT INTO modelli (marca, modello, cilindrata, kw, carburante, codice_motore, utente_id)
        VALUES (:marca, :modello, :cilindrata, :kw, :carburante, :codice_motore, :utente_id)
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Modello salvato correttamente")
    return redirect(url_for("lista_modelli"))

@app.route("/modifica_modello/<int:id>")
@login_required
def modifica_modello(id):
    conn = get_db()
    modello = conn.execute("SELECT * FROM modelli WHERE id=? AND utente_id=?", (id, session["user_id"])).fetchone()
    conn.close()
    if modello:
        return render_template("modifica_modello.html", modello=modello)
    flash(f"❌ Modello ID {id} non trovato o non accessibile")
    return redirect(url_for("lista_modelli"))

@app.route("/aggiorna_modello/<int:id>", methods=["POST"])
@login_required
def aggiorna_modello(id):
    dati = {k: request.form.get(k, "").strip() for k in
            ["marca", "modello", "cilindrata", "kw", "carburante", "codice_motore"]}
    dati["utente_id"] = session["user_id"]
    dati["id"] = id

    conn = get_db()
    conn.execute("""
        UPDATE modelli
        SET marca=:marca, modello=:modello, cilindrata=:cilindrata, kw=:kw,
            carburante=:carburante, codice_motore=:codice_motore
        WHERE id=:id AND utente_id=:utente_id
    """, dati)
    conn.commit()
    conn.close()
    flash("✅ Modello aggiornato correttamente")
    return redirect(url_for("lista_modelli"))

@app.route("/elimina_modello/<int:id>")
@login_required
def elimina_modello(id):
    conn = get_db()
    assoc = conn.execute(
        "SELECT COUNT(*) as c FROM modello_ricambi mr JOIN modelli m ON m.id=mr.modello_id "
        "WHERE mr.modello_id=? AND m.utente_id=?",
        (id, session["user_id"])
    ).fetchone()["c"]
    if assoc > 0:
        conn.close()
        flash("❌ Rimuovi prima le associazioni ricambi a questo modello.")
        return redirect(url_for("lista_modelli"))

    conn.execute("DELETE FROM modelli WHERE id=? AND utente_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("✅ Modello eliminato correttamente")
    return redirect(url_for("lista_modelli"))

# =========================
#          RICAMBI
# =========================
@app.route("/ricambi")
@login_required
def lista_ricambi():
    conn = get_db()
    ricambi = conn.execute("""
        SELECT id, nome, codice, quantita
        FROM ricambi
        WHERE utente_id=?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("ricambi.html", ricambi=ricambi)

@app.route("/inserisci_ricambio")
@login_required
def inserisci_ricambio():
    return render_template("inserisci_ricambio.html")

@app.route("/salva_ricambio", methods=["POST"])
@login_required
def salva_ricambio():
    dati = {
        "nome": request.form.get("nome", "").strip(),
        "codice": request.form.get("codice", "").strip(),
        "quantita": int(request.form.get("quantita", 0)),
        "utente_id": session["user_id"]
    }

    if not dati["nome"] or not dati["codice"]:
        flash("❌ Nome e codice sono obbligatori")
        return redirect(url_for("inserisci_ricambio"))

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO ricambi (nome, codice, quantita, utente_id)
            VALUES (:nome, :codice, :quantita, :utente_id)
        """, dati)
        conn.commit()
        flash("✅ Ricambio salvato correttamente")
    except Exception:
        flash("❌ Codice ricambio già esistente")
    finally:
        conn.close()
    return redirect(url_for("lista_ricambi"))

@app.route("/modifica_ricambio/<int:id>")
@login_required
def modifica_ricambio(id):
    conn = get_db()
    ricambio = conn.execute(
        "SELECT * FROM ricambi WHERE id=? AND utente_id=?", (id, session["user_id"])
    ).fetchone()
    conn.close()
    if ricambio:
        return render_template("modifica_ricambio.html", ricambio=ricambio)
    flash("❌ Ricambio non trovato o non accessibile")
    return redirect(url_for("lista_ricambi"))

@app.route("/aggiorna_ricambio/<int:id>", methods=["POST"])
@login_required
def aggiorna_ricambio(id):
    dati = {
        "nome": request.form.get("nome", "").strip(),
        "codice": request.form.get("codice", "").strip(),
        "quantita": int(request.form.get("quantita", 0)),
        "id": id,
        "utente_id": session["user_id"]
    }

    conn = get_db()
    try:
        conn.execute("""
            UPDATE ricambi
            SET nome=:nome, codice=:codice, quantita=:quantita
            WHERE id=:id AND utente_id=:utente_id
        """, dati)
        conn.commit()
        flash("✅ Ricambio aggiornato correttamente")
    except Exception:
        flash("❌ Codice ricambio già in uso")
    finally:
        conn.close()
    return redirect(url_for("lista_ricambi"))

@app.route("/elimina_ricambio/<int:id>")
@login_required
def elimina_ricambio(id):
    conn = get_db()
    assoc = conn.execute("""
        SELECT COUNT(*) as c
        FROM modello_ricambi mr
        JOIN ricambi r ON r.id = mr.ricambio_id
        WHERE mr.ricambio_id=? AND r.utente_id=?
    """, (id, session["user_id"])).fetchone()["c"]
    if assoc > 0:
        conn.close()
        flash("❌ Rimuovi prima le associazioni di questo ricambio ai modelli.")
        return redirect(url_for("lista_ricambi"))

    conn.execute("DELETE FROM ricambi WHERE id=? AND utente_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("✅ Ricambio eliminato")
    return redirect(url_for("lista_ricambi"))

# =========================
#   ASSOCIAZIONI MODELLO↔RICAMBI
# =========================
@app.route("/modello/<int:modello_id>/ricambi")
@login_required
def ricambi_del_modello(modello_id):
    conn = get_db()
    modello = conn.execute(
        "SELECT * FROM modelli WHERE id=? AND utente_id=?", (modello_id, session["user_id"])
    ).fetchone()
    if not modello:
        conn.close()
        flash("❌ Modello non trovato o non accessibile")
        return redirect(url_for("lista_modelli"))

    associati = conn.execute("""
        SELECT r.id, r.nome, r.codice, r.quantita
        FROM modello_ricambi mr
        JOIN ricambi r ON r.id = mr.ricambio_id
        WHERE mr.modello_id=? AND mr.utente_id=? AND r.utente_id=?
        ORDER BY r.nome
    """, (modello_id, session["user_id"], session["user_id"])).fetchall()

    non_associati = conn.execute("""
        SELECT r.id, r.nome, r.codice, r.quantita
        FROM ricambi r
        WHERE r.utente_id=?
          AND r.id NOT IN (
              SELECT ricambio_id FROM modello_ricambi
              WHERE modello_id=? AND utente_id=?
          )
        ORDER BY r.nome
    """, (session["user_id"], modello_id, session["user_id"])).fetchall()

    conn.close()
    return render_template(
        "modello_ricambi.html",
        modello=modello,
        associati=associati,
        non_associati=non_associati
    )

@app.route("/modello/<int:modello_id>/aggiungi_ricambio", methods=["POST"])
@login_required
def aggiungi_ricambio_a_modello(modello_id):
    ricambio_id = request.form.get("ricambio_id", "").strip()
    conn = get_db()
    m = conn.execute("SELECT id FROM modelli WHERE id=? AND utente_id=?", (modello_id, session["user_id"])).fetchone()
    r = conn.execute("SELECT id FROM ricambi WHERE id=? AND utente_id=?", (ricambio_id, session["user_id"])).fetchone()
    if not (m and r):
        conn.close()
        flash("❌ Modello o ricambio non valido")
        return redirect(url_for("ricambi_del_modello", modello_id=modello_id))

    try:
        conn.execute("""
            INSERT INTO modello_ricambi (modello_id, ricambio_id, utente_id)
            VALUES (?, ?, ?)
        """, (modello_id, ricambio_id, session["user_id"]))
        conn.commit()
        flash("✅ Ricambio associato al modello")
    except Exception:
        flash("ℹ️ Ricambio già associato a questo modello")
    finally:
        conn.close()
    return redirect(url_for("ricambi_del_modello", modello_id=modello_id))

@app.route("/modello/<int:modello_id>/rimuovi_ricambio/<int:ricambio_id>")
@login_required
def rimuovi_ricambio_da_modello(modello_id, ricambio_id):
    conn = get_db()
    m = conn.execute("SELECT id FROM modelli WHERE id=? AND utente_id=?", (modello_id, session["user_id"])).fetchone()
    r = conn.execute("SELECT id FROM ricambi WHERE id=? AND utente_id=?", (ricambio_id, session["user_id"])).fetchone()
    if not (m and r):
        conn.close()
        flash("❌ Modello o ricambio non valido")
        return redirect(url_for("ricambi_del_modello", modello_id=modello_id))

    conn.execute("""
        DELETE FROM modello_ricambi
        WHERE modello_id=? AND ricambio_id=? AND utente_id=?
    """, (modello_id, ricambio_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("✅ Associazione rimossa")
    return redirect(url_for("ricambi_del_modello", modello_id=modello_id))

# ---------- Avvio server ----------
if __name__ == "__main__":
    app.run(debug=True)
