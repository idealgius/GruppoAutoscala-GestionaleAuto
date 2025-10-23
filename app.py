from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask import request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import hashlib
from functools import wraps
import json

# =====================================
# CONFIG
# =====================================
import os
from flask import Flask

app = Flask(__name__)

# Imposta SECRET_KEY: usa la variabile d'ambiente se disponibile, altrimenti usa una chiave di default per locale
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'questa_e_una_chiave_di_default')

# =====================================
# CONNESSIONE SUPABASE (HOST ORIGINALE)
# =====================================
import os
import psycopg2

import os
import psycopg2

import os
import psycopg2
from urllib.parse import urlparse

def get_db_connection():
    try:
        url = os.getenv("DATABASE_URL")
        if url:
            result = urlparse(url)
            return psycopg2.connect(
                dbname=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                sslmode="require"
            )
        # fallback se DATABASE_URL non c'è
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", 6543),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            sslmode="require"
        )
    except Exception as e:
        raise RuntimeError(f"Impossibile connettersi al database: {e}")


def lavorazioni_officina_query(user_id):
    """Restituisce tutte le lavorazioni relative all'officina indicata."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT *
            FROM lavorazioni
            WHERE id_officina = %s AND eliminata = FALSE
            ORDER BY data_creazione DESC
        """, (user_id,))
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows

# =====================================
# UTILITY
# =====================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def status_to_color(stato: str) -> str:
    if not stato:
        return '#f8f9fa'
    stato = stato.lower()
    if stato in ['ordine inviato', 'giallo']:
        return '#fff3cd'
    if stato in ['in lavorazione', 'azzurro']:
        return '#ffe5b4'
    if stato in ['completato', 'verde']:
        return '#d4edda'
    return '#f8f9fa'

# =====================================
# DECORATORE LOGIN
# =====================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Devi essere loggato per accedere a questa pagina.")
            return redirect(url_for('scelta_login'))
        return f(*args, **kwargs)
    return decorated_function

# =====================================
# HELPERS UTENTE / LAVORAZIONI / STORICO
# =====================================
def get_nome_reale(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT username FROM utenti WHERE id = %s", (user_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else None

def fetch_user_by_credentials(username: str, ruolo: str | None = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    username = username.strip()
    try:
        if ruolo:
            cur.execute(
                "SELECT * FROM utenti WHERE LOWER(username)=LOWER(%s) AND LOWER(ruolo)=LOWER(%s)",
                (username, ruolo)
            )
        else:
            cur.execute("SELECT * FROM utenti WHERE LOWER(username)=LOWER(%s)", (username,))
        user = cur.fetchone()
    finally:
        conn.close()
    return user

def fetch_lavorazioni(id_officina: int | None = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if id_officina:
            cur.execute("SELECT * FROM lavorazioni WHERE id_officina=%s ORDER BY data_creazione DESC", (id_officina,))
        else:
            cur.execute("SELECT * FROM lavorazioni ORDER BY data_creazione DESC")
        raw = cur.fetchall()
    finally:
        conn.close()
    out = []
    for lav in raw:
        stato_val = lav.get('stato') or lav.get('status') or ''
        lav['stato'] = stato_val
        lav['colore'] = status_to_color(stato_val)
        out.append(lav)
    return out

def lavorazioni_officina(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Rimosso il riferimento a 'eliminata' per evitare l'errore
        cur.execute("""
            SELECT * FROM lavorazioni
            WHERE id_officina=%s
            ORDER BY data_creazione DESC
        """, (user_id,))
        raw = cur.fetchall()
    finally:
        conn.close()

    out = []
    for lav in raw:
        stato_val = lav.get('stato') or lav.get('status') or ''
        lav['stato'] = stato_val
        lav['colore'] = status_to_color(stato_val)
        out.append(lav)
    return out

def log_storico(user_id, azione: str, tabella: str | None = None, record_id: int | None = None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO storico_azioni (id_utente, azione, tabella, record_id, data_ora) VALUES (%s, %s, %s, %s, %s)",
            (user_id, azione, tabella, record_id, datetime.utcnow())
        )
        conn.commit()
    except Exception:
        app.logger.exception("Impossibile registrare lo storico.")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def registra_azione_username(username, azione, dettagli):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO storico_azioni (utente, azione, dettagli, data_ora)
            VALUES (%s, %s, %s, %s)
        """, (username, azione, dettagli, datetime.utcnow()))
        conn.commit()
    except Exception:
        app.logger.exception("Impossibile registrare azione con username.")
    finally:
        try:
            conn.close()
        except Exception:
            pass

# =====================================
# ROUTE: scelta login e login/logout
# =====================================
@app.route('/scelta_login')
def scelta_login():
    return render_template('login_selezione.html')

@app.route('/login', defaults={'ruolo': None}, methods=['GET', 'POST'])
@app.route('/login/<ruolo>', methods=['GET', 'POST'])
def login(ruolo):
    ruolo_input = (ruolo or request.form.get('ruolo') or request.args.get('ruolo') or '').strip().lower()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Inserisci username e password.")
            return render_template('login.html', ruolo=ruolo_input)

        user = fetch_user_by_credentials(username, ruolo_input)

        if not user:
            flash("Username o password non validi.")
            return render_template('login.html', ruolo=ruolo_input)

        db_pw = user.get('password', '')

        try:
            if isinstance(db_pw, str) and db_pw == password:
                pass
            elif isinstance(db_pw, str) and len(db_pw) == 64:
                if hash_password(password) == db_pw:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE utenti SET password=%s WHERE id=%s", (password, user['id']))
                    conn.commit()
                    conn.close()
                else:
                    flash("Username o password non validi.")
                    return render_template('login.html', ruolo=ruolo_input)
            else:
                flash("Username o password non validi.")
                return render_template('login.html', ruolo=ruolo_input)
        except Exception:
            app.logger.exception("Errore durante verifica password:")
            flash("Si è verificato un errore durante il login.")
            return render_template('login.html', ruolo=ruolo_input)

        user_role = user.get('ruolo', '').strip().lower()
        if not user_role:
            flash("Utente senza ruolo assegnato, contatta l'amministratore.")
            return redirect(url_for('scelta_login'))

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['ruolo'] = user_role

        flash(f"Login effettuato con successo come {user_role}.")
        try:
            log_storico(session['user_id'], "Login", "utenti", session['user_id'])
        except Exception:
            pass

        if user_role == 'officina':
            return redirect(url_for('home_officina'))
        elif user_role == 'accettazione':
            return redirect(url_for('home'))
        else:
            flash("Ruolo non riconosciuto.")
            return redirect(url_for('scelta_login'))

    if not ruolo_input:
        return redirect(url_for('scelta_login'))
    return render_template('login.html', ruolo=ruolo_input)

@app.route('/logout')
@login_required
def logout():
    try:
        log_storico(session.get('user_id'), "Logout", "utenti", session.get('user_id'))
    except Exception:
        pass
    session.clear()
    flash("Hai effettuato il logout.")
    return redirect(url_for('scelta_login'))

# =====================================
# HOME (accettazione) e HOME OFFICINA
# =====================================
@app.route('/')
@login_required
def home():
    if session.get('ruolo') != 'accettazione':
        flash("Accesso negato: non sei Accettazione")
        return redirect(url_for('scelta_login'))
    nome_reale = get_nome_reale(session['user_id'])
    lavorazioni = fetch_lavorazioni(None)
    return render_template('home.html', nome_reale=nome_reale, ruolo='accettazione', lavorazioni=lavorazioni)

@app.route('/officina')
@login_required
def home_officina():
    # Controllo ruolo
    if session.get('ruolo') != 'officina':
        flash("Accesso negato: non sei Officina", "danger")
        return redirect(url_for('scelta_login'))

    nome_reale = get_nome_reale(session['user_id'])
    
    # Recupera lavorazioni: se None, usa lista vuota
    lavorazioni = lavorazioni_officina_query(session['user_id']) or []
    
    # Assegna i colori in base allo stato della lavorazione
    stato_colore = {
        'ordine inviato': '#fff3cd',       # giallo chiaro
        'in lavorazione': '#cce5ff',       # azzurro chiaro
        'completata': '#c8f7c5'            # verde chiaro
    }

    for lav in lavorazioni:
        lav.setdefault('tipo', 'Lavorazione')
        lav.setdefault('stato', '-')
        lav.setdefault('marca', '-')
        lav.setdefault('modello', '-')
        lav.setdefault('cilindrata', '-')
        lav.setdefault('kw', '-')
        lav.setdefault('anno', '-')
        lav.setdefault('note', '')
        lav.setdefault('cliente_nome', '')

        # Imposta colore in base allo stato
        lav['colore'] = stato_colore.get(lav['stato'].lower(), '#ffffff')

    mostra_sidebar = True

    return render_template(
        'home_officina.html',
        nome_reale=nome_reale,
        ruolo='officina',
        lavorazioni=lavorazioni,
        mostra_sidebar=mostra_sidebar
    )


# =====================================
# CLIENTI
# =====================================
@app.route('/clienti')
@login_required
def lista_clienti():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM clienti WHERE utente_id=%s ORDER BY id", (session['user_id'],))
        clienti = cur.fetchall()
    finally:
        conn.close()
    return render_template('clienti.html', clienti=clienti)

@app.route('/inserisci_cliente', methods=['GET'])
@login_required
def inserisci_cliente():
    return render_template('inserisci_cliente.html')

@app.route('/salva_cliente', methods=['POST'])
@login_required
def salva_cliente():
    data = (
        request.form['nome'], request.form['cognome'], request.form['via'],
        request.form['provincia'], request.form['comune'], request.form.get('data_nascita') or None,
        request.form.get('codice_fiscale') or None, request.form.get('telefono'),
        request.form.get('email') or None, session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO clienti
            (nome, cognome, via, provincia, comune, data_nascita, codice_fiscale, telefono, email, utente_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, data)
        new_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Inserito cliente {new_id}: {data[0]} {data[1]}", "clienti", new_id)
    except Exception:
        pass
    return redirect('/clienti')

# =====================================
# VETTURE
# =====================================
@app.route('/vetture')
@login_required
def lista_vetture():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM vetture WHERE utente_id=%s ORDER BY id", (session['user_id'],))
        vetture = cur.fetchall()
    finally:
        conn.close()
    return render_template('vetture.html', vetture=vetture)

@app.route('/inserisci_vettura', methods=['GET'])
@login_required
def inserisci_vettura():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, nome, cognome FROM clienti WHERE utente_id=%s ORDER BY id", (session['user_id'],))
        clienti = cur.fetchall()
        cur.execute("SELECT DISTINCT marca FROM modelli WHERE utente_id=%s ORDER BY marca", (session['user_id'],))
        marche = [row['marca'] for row in cur.fetchall()]
        cur.execute("SELECT * FROM modelli WHERE utente_id=%s ORDER BY marca, modello, versione", (session['user_id'],))
        modelli_raw = cur.fetchall()
    finally:
        conn.close()
    modelli_json = json.dumps(modelli_raw)
    return render_template('inserisci_vettura.html', clienti=clienti, marche=marche, modelli_json=modelli_json)

@app.route('/salva_vettura', methods=['POST'])
@login_required
def salva_vettura():
    data = (
        request.form['cliente_id'], request.form['targa'], request.form['marca'], request.form['modello'],
        request.form.get('cilindrata'), request.form.get('kw'), request.form.get('carburante'),
        request.form.get('codice_motore'), request.form.get('telaio'), request.form.get('immatricolazione') or None,
        request.form.get('km'), request.form.get('cambio'), session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO vetture
            (cliente_id,targa,marca,modello,cilindrata,kw,carburante,codice_motore,telaio,immatricolazione,km,cambio,utente_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, data)
        new_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Inserita vettura {new_id}: {data[2]} {data[3]}", "vetture", new_id)
    except Exception:
        pass
    return redirect('/vetture')
# =====================================
# MODELLI
# =====================================
@app.route('/modelli')
@login_required
def lista_modelli():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT DISTINCT marca FROM modelli WHERE utente_id=%s ORDER BY marca", (session['user_id'],))
        marche = [row['marca'] for row in cur.fetchall()]
        cur.execute("SELECT * FROM modelli WHERE utente_id=%s ORDER BY marca, modello, versione", (session['user_id'],))
        modelli_raw = cur.fetchall()
    finally:
        conn.close()
    seen = set()
    modelli = []
    for m in modelli_raw:
        key = (m['marca'], m['modello'], m.get('versione'))
        if key not in seen:
            seen.add(key)
            modelli.append(m)
    return render_template('modelli.html', marche=marche, modelli=modelli)

@app.route('/inserisci_modello', methods=['GET'])
@login_required
def inserisci_modello():
    marche = [
        "ALFA ROMEO","AUDI","BMW","CHEVROLET","CHRYSLER","CITROEN","CUPRA","DACIA",
        "DAEWOO","DAIHATSU","DODGE","DR","EVO","FIAT","FORD","HONDA","HYUNDAI",
        "INFINITI","ISUZU","IVECO","JAGUAR","JEEP","KIA","LADA","LANCIA","LAND ROVER",
        "LEXUS","LYNK&CO","MAN","MASERATI","MAXUS","MAZDA","MERCEDES","MG","MINI",
        "MITSUBISHI","NISSAN","OPEL","PEUGEOT","PIAGGIO","POLESTAR","PORSCHE","RENAULT",
        "ROVER","SAAB","SEAT","SKODA","SMART","SSANGYONG","SUBARU","SUZUKI","TATA",
        "TESLA","TOYOTA","VOLKSWAGEN","VOLVO"
    ]
    return render_template('inserisci_modello.html', marche=marche)

@app.route('/salva_modello', methods=['POST'])
@login_required
def salva_modello():
    data = (
        request.form['marca'],
        request.form['modello'],
        request.form.get('versione'),
        request.form.get('codice_versione'),
        request.form.get('cilindrata'),
        request.form.get('kw'),
        request.form.get('carburante'),
        request.form.get('codice_motore'),
        session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO modelli
            (marca, modello, versione, codice_versione, cilindrata, kw, carburante, codice_motore, utente_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, data)
        new_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Inserito modello {new_id}: {data[0]} {data[1]}", "modelli", new_id)
    except Exception:
        pass
    return redirect('/modelli')

@app.route('/modifica_modello/<int:id>', methods=['GET'])
@login_required
def modifica_modello(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM modelli WHERE id=%s AND utente_id=%s", (id, session['user_id']))
        modello = cur.fetchone()
    finally:
        conn.close()
    if modello:
        return render_template('modifica_modello.html', modello=modello)
    flash("Modello non trovato.")
    return redirect('/modelli')

@app.route('/aggiorna_modello/<int:id>', methods=['POST'])
@login_required
def aggiorna_modello(id):
    data = (
        request.form['marca'],
        request.form['modello'],
        request.form.get('versione'),
        request.form.get('codice_versione'),
        request.form.get('cilindrata'),
        request.form.get('kw'),
        request.form.get('carburante'),
        request.form.get('codice_motore'),
        session['user_id'],
        id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE modelli
            SET marca=%s, modello=%s, versione=%s, codice_versione=%s,
                cilindrata=%s, kw=%s, carburante=%s, codice_motore=%s, utente_id=%s
            WHERE id=%s
        """, data)
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Aggiornato modello {id}: {data[0]} {data[1]}", "modelli", id)
    except Exception:
        pass
    return redirect('/modelli')

@app.route('/elimina_modello/<int:id>')
@login_required
def elimina_modello(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT marca, modello FROM modelli WHERE id=%s AND utente_id=%s", (id, session['user_id']))
        modello = cur.fetchone()
        cur.execute("DELETE FROM modelli WHERE id=%s AND utente_id=%s", (id, session['user_id']))
        conn.commit()
    finally:
        conn.close()
    try:
        nome_mod = f"{modello[0]} {modello[1]}" if modello else str(id)
        log_storico(session['user_id'], f"Eliminato modello {id}: {nome_mod}", "modelli", id)
    except Exception:
        pass
    return redirect('/modelli')

# =====================================
# RICAMBI
# =====================================
@app.route('/ricambi')
@login_required
def lista_ricambi():
    marca = request.args.get('marca')
    modello = request.args.get('modello')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if marca and modello:
            cur.execute("""
                SELECT r.* FROM ricambi r
                JOIN modelli m ON r.modello_id = m.id
                WHERE LOWER(m.marca)=LOWER(%s) AND LOWER(m.modello)=LOWER(%s)
                ORDER BY r.id
            """, (marca, modello))
        else:
            cur.execute("SELECT * FROM ricambi ORDER BY id")
        ricambi = cur.fetchall()
    finally:
        conn.close()
    return render_template('ricambi.html', ricambi=ricambi)

@app.route('/aggiungi_ricambio', methods=['POST'])
@login_required
def aggiungi_ricambio():
    nome = request.form['nome']
    codice = request.form['codice']
    prezzo = request.form['prezzo']
    prefisso = (codice or '')[:3].upper()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ricambi (nome, codice, prezzo, prefisso, utente_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (nome, codice, prezzo, prefisso, session['user_id']))
        new_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Aggiunto ricambio {new_id}: {nome}", "ricambi", new_id)
    except Exception:
        pass
    flash('Ricambio aggiunto con successo!', 'success')
    return redirect(url_for('lista_ricambi'))

@app.route('/elimina_ricambio/<int:id>', methods=['POST'])
@login_required
def elimina_ricambio(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM ricambi WHERE id = %s AND utente_id=%s", (id, session['user_id']))
        conn.commit()
    finally:
        conn.close()
    try:
        log_storico(session['user_id'], f"Eliminato ricambio {id}", "ricambi", id)
    except Exception:
        pass
    flash('Ricambio eliminato con successo.', 'info')
    return redirect(url_for('lista_ricambi'))

@app.route('/modifica_ricambio/<int:id>', methods=['GET', 'POST'])
@login_required
def modifica_ricambio(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        nome = request.form['nome']
        codice = request.form['codice']
        prezzo = request.form['prezzo']
        prefisso = (codice or '')[:3].upper()
        try:
            cur.execute("""
                UPDATE ricambi
                SET nome=%s, codice=%s, prezzo=%s, prefisso=%s
                WHERE id=%s AND utente_id=%s
            """, (nome, codice, prezzo, prefisso, id, session['user_id']))
            conn.commit()
            try:
                log_storico(session['user_id'], f"Aggiornato ricambio {id}: {nome}", "ricambi", id)
            except Exception:
                pass
            flash('Ricambio modificato correttamente.', 'success')
        finally:
            conn.close()
        return redirect(url_for('lista_ricambi'))

    # GET → mostra form
    cur.execute("SELECT * FROM ricambi WHERE id=%s", (id,))
    ricambio = cur.fetchone()
    cur.close()
    if not ricambio:
        flash("Ricambio non trovato", 'danger')
        return redirect(url_for('lista_ricambi'))
    return render_template('modifica_ricambio.html', ricambio=ricambio)

@app.route('/modello_ricambi/<int:modello_id>')
@login_required
def modello_ricambi(modello_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM modelli WHERE id=%s", (modello_id,))
        modello = cur.fetchone()
        if not modello:
            flash("Modello non trovato.")
            return redirect(url_for('lista_modelli'))

        cur.execute("""
            SELECT r.* FROM ricambi r
            JOIN modelli_ricambi mr ON r.id = mr.ricambio_id
            WHERE mr.modello_id = %s
            ORDER BY r.codice ASC
        """, (modello_id,))
        associati = cur.fetchall()

        cur.execute("""
            SELECT r.* FROM ricambi r
            WHERE r.id NOT IN (SELECT ricambio_id FROM modelli_ricambi WHERE modello_id = %s)
            ORDER BY r.codice ASC
        """, (modello_id,))
        non_associati = cur.fetchall()
    finally:
        conn.close()
    return render_template('modello_ricambi.html', modello=modello, associati=associati, non_associati=non_associati)

@app.route('/aggiungi_ricambio_a_modello/<int:modello_id>', methods=['POST'])
@login_required
def aggiungi_ricambio_a_modello(modello_id):
    if session.get('username') != 'Giuseppe Palladino':
        flash("Non hai i permessi per associare ricambi ai modelli.")
        return redirect(url_for('modello_ricambi', modello_id=modello_id))

    ricambio_id = request.form.get('ricambio_id')
    if not ricambio_id:
        flash("Seleziona un ricambio da associare.")
        return redirect(url_for('modello_ricambi', modello_id=modello_id))

    try:
        ricambio_id_int = int(ricambio_id)
    except ValueError:
        flash("ID ricambio non valido.")
        return redirect(url_for('modello_ricambi', modello_id=modello_id))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM modelli WHERE id=%s", (modello_id,))
        if not cur.fetchone():
            flash("Modello non trovato.")
            return redirect(url_for('lista_modelli'))

        cur.execute("SELECT id FROM ricambi WHERE id=%s", (ricambio_id_int,))
        if not cur.fetchone():
            flash("Ricambio non trovato.")
            return redirect(url_for('modello_ricambi', modello_id=modello_id))

        cur.execute("SELECT 1 FROM modelli_ricambi WHERE modello_id=%s AND ricambio_id=%s", (modello_id, ricambio_id_int))
        exists = cur.fetchone()
        if exists:
            flash("Questo ricambio è già associato a questo modello.")
            return redirect(url_for('modello_ricambi', modello_id=modello_id))

        cur.execute("INSERT INTO modelli_ricambi (modello_id, ricambio_id) VALUES (%s, %s)", (modello_id, ricambio_id_int))
        conn.commit()
        log_storico(session['user_id'], f"Associato ricambio {ricambio_id_int} a modello {modello_id}", "modelli_ricambi", modello_id)
        flash("Ricambio associato correttamente.")
    except Exception:
        conn.rollback()
        app.logger.exception("Errore durante l'associazione ricambio-modello.")
        flash("Si è verificato un errore durante l'associazione.")
    finally:
        conn.close()

    return redirect(url_for('modello_ricambi', modello_id=modello_id))

@app.route('/rimuovi_ricambio_da_modello/<int:modello_id>/<int:ricambio_id>', methods=['POST'])
@login_required
def rimuovi_ricambio_da_modello(modello_id, ricambio_id):
    if session.get('username') != 'Giuseppe Palladino':
        flash("Non hai i permessi per rimuovere ricambi dai modelli.")
        return redirect(url_for('modello_ricambi', modello_id=modello_id))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM modelli_ricambi WHERE modello_id=%s AND ricambio_id=%s", (modello_id, ricambio_id))
        if not cur.fetchone():
            flash("Associazione non trovata.")
            return redirect(url_for('modello_ricambi', modello_id=modello_id))

        cur.execute("DELETE FROM modelli_ricambi WHERE modello_id=%s AND ricambio_id=%s", (modello_id, ricambio_id))
        conn.commit()
        log_storico(session['user_id'], f"Rimosso ricambio {ricambio_id} da modello {modello_id}", "modelli_ricambi", modello_id)
        flash("Ricambio rimosso correttamente.")
    except Exception:
        conn.rollback()
        app.logger.exception("Errore durante la rimozione dell'associazione.")
        flash("Si è verificato un errore durante la rimozione.")
    finally:
        conn.close()

    return redirect(url_for('modello_ricambi', modello_id=modello_id))

@app.route('/ricambi/aggiorna_giacenza/<int:ricambio_id>', methods=['POST'])
@login_required
def aggiorna_giacenza(ricambio_id):
    if session.get('username') != 'G.AS_Giuseppe.Palladino':
        flash("Accesso negato.", "danger")
        return redirect(url_for('lista_ricambi'))

    azione = request.form.get('azione')
    nuova_quantita = request.form.get('nuova_quantita')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # prendi la quantità attuale
        cur.execute("SELECT quantita FROM ricambi WHERE id=%s", (ricambio_id,))
        result = cur.fetchone()
        if not result:
            flash("Ricambio non trovato.", "danger")
            return redirect(url_for('lista_ricambi'))

        quantita = result[0]

        if azione == 'incrementa':
            quantita += 1
        elif azione == 'decrementa':
            quantita = max(0, quantita - 1)
        elif nuova_quantita is not None:
            try:
                quantita = max(0, int(nuova_quantita))
            except ValueError:
                flash("Valore non valido.", "danger")
                return redirect(url_for('lista_ricambi'))

        cur.execute("UPDATE ricambi SET quantita=%s WHERE id=%s", (quantita, ricambio_id))
        conn.commit()
    finally:
        conn.close()

    flash("Giacenza aggiornata.", "success")
    return redirect(url_for('lista_ricambi'))

# =====================================
# LAVORAZIONI (OFFICINA)
# =====================================
@app.route('/lavorazioni')
@login_required
def lavorazioni_generale():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT l.*, u.username
            FROM lavorazioni l
            LEFT JOIN utenti u ON l.tecnico_id = u.id
            WHERE l.eliminata = FALSE
            ORDER BY l.id DESC
        """)
        lavori_raw = cur.fetchall()
    finally:
        conn.close()

    # Rimuove duplicati in Python usando (cliente_nome, targa, data_creazione)
    seen = set()
    lavori = []
    for l in lavori_raw:
        key = (l.get('cliente_nome'), l.get('targa'), l.get('data_creazione'))
        if key not in seen:
            seen.add(key)
            lavori.append(l)

    return render_template('lavorazioni.html', lavorazioni=lavori)

@app.route('/nuova_lavorazione', methods=['GET', 'POST'])
@login_required
def nuova_lavorazione():
    # Recupero tecnici dal DB
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, username FROM utenti WHERE ruolo = 'tecnico'")
        tecnici = cur.fetchall()
    finally:
        conn.close()

    if request.method == 'POST':
        tecnico_id = request.form['tecnico_id']
        veicolo = request.form['veicolo']
        cilindrata = request.form['cilindrata']
        kw = request.form['kw']
        note = request.form['note']

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO lavorazioni (tecnico_id, veicolo, cilindrata, kw, note, data_creazione)
                VALUES (%s, %s, %s, %s, %s, NOW())
                RETURNING id
            """, (tecnico_id, veicolo, cilindrata, kw, note))
            new_id = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        try:
            log_storico(session['user_id'], "Nuova lavorazione", "lavorazioni", new_id)
        except Exception:
            pass

        flash('Lavorazione aggiunta con successo.', 'success')
        return redirect(url_for('lavorazioni'))

    return render_template('nuova_lavorazione.html', tecnici=tecnici)

@app.route('/ajax_lavorazioni')
@login_required
def ajax_lavorazioni():
    ruolo = session.get('ruolo')
    user_id = session.get('user_id')
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if ruolo == 'officina':
            cur.execute("""
                SELECT id, data_creazione, tipo, COALESCE(tagliando, FALSE) AS tagliando, 
                       COALESCE(dischi_pattini, FALSE) AS dischi_pattini,
                       COALESCE(marca, '') AS marca, COALESCE(modello, '') AS modello, COALESCE(stato, '') AS stato
                FROM lavorazioni
                WHERE id_officina = %s AND COALESCE(eliminata, false) = false
                ORDER BY data_creazione DESC
            """, (user_id,))
        elif ruolo == 'accettazione':
            cur.execute("""
                SELECT id, data_creazione, tipo, COALESCE(tagliando, FALSE) AS tagliando, 
                       COALESCE(dischi_pattini, FALSE) AS dischi_pattini,
                       COALESCE(marca, '') AS marca, COALESCE(modello, '') AS modello, COALESCE(stato, '') AS stato
                FROM lavorazioni
                WHERE COALESCE(eliminata, false) = false
                  AND TRIM(stato) IN ('ordine inviato', 'in lavorazione', 'completata')
                ORDER BY data_creazione DESC
            """)
        else:
            return jsonify({"error": "Ruolo non autorizzato"}), 403

        rows = cur.fetchall()

        lavori_list = []
        for r in rows:
            # Determina il tipo leggibile
            if r[3]:  # tagliando
                tipo_display = "Tagliando"
            elif r[4]:  # dischi_pattini
                tipo_display = "Dischi e Pattini freno"
            else:
                tipo_display = r[2] or ""  # tipo originale

            lavori_list.append({
                "id": r[0],
                "data_creazione": r[1].strftime("%d/%m/%Y %H:%M") if r[1] else "",
                "tipo": tipo_display,
                "marca": r[5] or "",
                "modello": r[6] or "",
                "stato": r[7] or ""
            })

        return jsonify(lavori_list)

    except Exception:
        app.logger.exception("Errore nel recupero delle lavorazioni AJAX.")
        return jsonify({"error": "Impossibile recuperare le lavorazioni"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =====================================
# OFFICINA: inserisci / aggiorna stato
# =====================================
@app.route('/officina/inserisci', methods=['GET', 'POST'])
@login_required
def inserisci_lavorazione():
    if session.get('ruolo') != 'officina':
        flash("Accesso non autorizzato.")
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if request.method == 'POST':
            tagliando = request.form.get('tagliando') == 'on'
            dischi_pattini = request.form.get('dischi_pattini') == 'on'
            tipo_lavorazione = request.form.get('tipo_lavorazione') if not (tagliando or dischi_pattini) else None
            marca = request.form.get('marca') or ''
            modello = request.form.get('modello') or ''
            cilindrata = request.form.get('cilindrata')
            kw = request.form.get('kw')
            anno = request.form.get('anno')
            cliente_nome = request.form.get('cliente_nome')
            targa = request.form.get('targa')
            stato = 'ordine inviato'

            if not cliente_nome and not targa:
                flash("Devi inserire almeno il nome del cliente o la targa del veicolo.")
                return redirect(url_for('inserisci_lavorazione'))

            def to_int(val):
                try:
                    return int(val) if val and val.strip() else None
                except ValueError:
                    return None

            cilindrata_val = to_int(cilindrata)
            kw_val = to_int(kw)
            anno_val = to_int(anno)

            # Inserimento definitivo senza controllo duplicati
            cur.execute("""
                INSERT INTO lavorazioni 
                (id_officina, tipo, marca, modello, cilindrata, kw, anno, stato, cliente_nome, targa)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id;
            """, (
                session['user_id'],
                tipo_lavorazione if tipo_lavorazione else ('Tagliando' if tagliando else 'Dischi e Pattini freno' if dischi_pattini else None),
                marca, modello, cilindrata_val, kw_val, anno_val, stato, cliente_nome, targa
            ))

            new_record = cur.fetchone()
            new_id = new_record['id'] if new_record else None
            conn.commit()

            try:
                log_storico(session['user_id'], f"Inserita lavorazione {new_id}: {marca} {modello}", "lavorazioni", new_id)
            except Exception:
                pass

            flash("Lavorazione inserita correttamente.")
            return redirect(url_for('home_officina'))

        # GET: recupero marche e modelli
        cur.execute("SELECT DISTINCT marca FROM modelli ORDER BY marca")
        marche = [row['marca'] for row in cur.fetchall()]
        cur.execute("SELECT marca, modello FROM modelli ORDER BY marca, modello")
        modelli = cur.fetchall()
    finally:
        conn.close()

    return render_template('inserisci_lavorazione.html', marche=marche, modelli=modelli)

@app.route('/accettazione/aggiorna_stato/<int:id>', methods=['POST'])
@login_required
def accettazione_aggiorna_stato(id):
    # ✅ Solo utenti con ruolo 'accettazione' possono aggiornare lo stato
    if session.get('ruolo') != 'accettazione':
        return jsonify({"success": False, "message": "Accesso non autorizzato."}), 403

    # ✅ Ricevi i dati dal frontend (fetch JSON)
    data = request.get_json(silent=True) or {}
    nuovo_stato = (data.get('stato') or '').replace('_', ' ').lower().strip()

    # ✅ Stati ammessi
    stati_validi = ['ordine inviato', 'in lavorazione', 'completata']
    if nuovo_stato not in stati_validi:
        app.logger.warning(f"Stato non valido ricevuto: '{nuovo_stato}'")
        return jsonify({"success": False, "message": "Stato non valido."}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # ✅ Aggiorna lo stato nel DB
        cur.execute("""
            UPDATE lavorazioni 
            SET stato = %s, data_aggiornamento = NOW()
            WHERE id = %s
        """, (nuovo_stato, id))
        conn.commit()

        # ✅ Log nello storico (senza causare crash se fallisce)
        try:
            log_storico(session['user_id'], f"Aggiornato stato lavorazione {id} → {nuovo_stato}", "lavorazioni", id)
        except Exception as log_err:
            app.logger.warning(f"Errore durante log storico lavorazione {id}: {log_err}")

    except Exception as e:
        conn.rollback()
        app.logger.exception(f"Errore aggiornando stato lavorazione {id}: {e}")
        return jsonify({"success": False, "message": "Errore aggiornando stato."}), 500

    finally:
        conn.close()

    # ✅ Tutto ok → rispondi al frontend
    return jsonify({"success": True, "nuovo_stato": nuovo_stato})


@app.route('/dettagli_lavorazione/<int:id>', methods=['GET'])
@login_required
def dettagli_lavorazione(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT l.*, 
                   COALESCE(c.nome, l.cliente_nome) AS nome_cliente, 
                   COALESCE(c.cognome, '') AS cognome_cliente,
                   COALESCE(v.marca, l.marca) AS marca,
                   COALESCE(v.modello, l.modello) AS modello,
                   COALESCE(v.targa, l.targa) AS targa
            FROM lavorazioni l
            LEFT JOIN clienti c ON l.cliente_id = c.id
            LEFT JOIN vetture v ON l.vettura_id = v.id
            WHERE l.id = %s
        """, (id,))
        lavorazione = cur.fetchone()
    finally:
        conn.close()

    if not lavorazione:
        return jsonify({'error': 'Lavorazione non trovata'}), 404

    # --- Costruisci una descrizione leggibile del tipo di lavorazione ---
    tipo_descrizione = ""
    if lavorazione.get('tagliando'):
        tipo_descrizione = "Tagliando"
    if lavorazione.get('dischi_pattini'):
        if tipo_descrizione:
            tipo_descrizione += " + Dischi e Pattini freno"
        else:
            tipo_descrizione = "Dischi e Pattini freno"
    if not tipo_descrizione:
        tipo_descrizione = lavorazione.get('tipo', 'Altro')

    return jsonify({
        'id': lavorazione['id'],
        'tipo': tipo_descrizione,
        'tagliando': lavorazione.get('tagliando', False),
        'dischi_pattini': lavorazione.get('dischi_pattini', False),
        'marca': lavorazione.get('marca', ''),
        'modello': lavorazione.get('modello', ''),
        'cilindrata': lavorazione.get('cilindrata', ''),
        'kw': lavorazione.get('kw', ''),
        'cavalli': lavorazione.get('cavalli', ''),
        'anno': lavorazione.get('anno', ''),
        'nome_cliente': lavorazione.get('nome_cliente', ''),
        'cognome_cliente': lavorazione.get('cognome_cliente', ''),
        'targa': lavorazione.get('targa', ''),
        'descrizione': lavorazione.get('descrizione', ''),
        'note': lavorazione.get('note', ''),
        'stato': lavorazione.get('stato', ''),
        'data_creazione': lavorazione.get('data_creazione', '')
    })
@app.route('/officina/lavorazioni', methods=['GET'])
@login_required
def lavorazioni_officina():
    if session.get('ruolo') == 'officina':
        # Se l'utente è dell'officina, mostriamo solo le lavorazioni in corso (che non sono eliminate)
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM lavorazioni 
                WHERE id_officina = %s AND eliminata = FALSE 
                ORDER BY data_creazione DESC
            """, (session['user_id'],))
            lavorazioni_list = cur.fetchall()
        finally:
            conn.close()

        return render_template('lavorazioni.html', lavorazioni=lavorazioni_list, ruolo='officina')

# =====================================
# ELIMINA LAVORAZIONE (LOGICA)
# =====================================
@app.route('/accettazione/elimina_lavorazione/<int:id>', methods=['POST'])
@login_required
def elimina_lavorazione(id):
    # Controllo ruolo: solo accettazione può eliminare
    if session.get('ruolo') != 'accettazione':
        return jsonify({"success": False, "error": "Accesso non autorizzato."}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Controllo che la lavorazione esista
        cur.execute("SELECT id FROM lavorazioni WHERE id = %s AND eliminata = FALSE", (id,))
        lavorazione = cur.fetchone()
        if not lavorazione:
            return jsonify({"success": False, "error": "Lavorazione non trovata."}), 404

        # Soft delete della lavorazione
        cur.execute("""
            UPDATE lavorazioni 
            SET eliminata = TRUE
            WHERE id = %s
        """, (id,))
        conn.commit()

        # Log nello storico
        try:
            cur.execute("""
                INSERT INTO storico_azioni (id_utente, azione, tabella, record_id, data_ora)
                VALUES (%s, %s, %s, %s, NOW())
            """, (session.get('user_id'), 'Eliminazione', 'lavorazioni', id))
            conn.commit()
        except Exception as log_err:
            app.logger.error(f"Impossibile registrare storico: {log_err}")
            conn.rollback()

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# =====================================
# PROMEMORIA (route corretta per url_for("promemoria"))
# =====================================
@app.route('/promemoria', methods=['GET', 'POST'])
@login_required
def promemoria():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if request.method == 'POST':
            testo = request.form.get('testo')
            if testo:
                cur.execute("INSERT INTO promemoria (utente_id, testo, data_creazione) VALUES (%s,%s,%s)",
                            (session['user_id'], testo, datetime.utcnow()))
                conn.commit()
                try:
                    log_storico(session['user_id'], "Aggiunto promemoria", "promemoria", None)
                except Exception:
                    pass
        if session.get('ruolo') == 'accettazione':
            cur.execute("SELECT * FROM promemoria ORDER BY data_creazione DESC")
        else:
            cur.execute("SELECT * FROM promemoria WHERE utente_id=%s ORDER BY data_creazione DESC", (session['user_id'],))
        promemoria_rows = cur.fetchall()
    finally:
        conn.close()

    if request.args.get('ajax') in ['1', 'true']:
        return jsonify(promemoria_rows)
    return render_template('promemoria.html', promemoria=promemoria_rows)

@app.route('/aggiungi_promemoria', methods=['POST'])
@login_required
def aggiungi_promemoria():
    try:
        dati = request.get_json()
        titolo = dati.get('titolo')
        info = dati.get('info')

        if not titolo or not info:
            return jsonify({"success": False, "message": "Titolo e informazioni obbligatori"}), 400

        supabase.table('promemoria').insert({
            "utente_id": session['user_id'],
            "titolo": titolo,
            "info": info,
            "data_creazione": datetime.utcnow()
        }).execute()

        try:
            log_storico(session['user_id'], f"Aggiunto promemoria: {titolo}", "promemoria", None)
        except Exception:
            pass

        return jsonify({"success": True, "message": "Promemoria aggiunto correttamente"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/lista_promemoria', methods=['GET'])
@login_required
def lista_promemoria():
    try:
        if session.get('ruolo') == 'accettazione':
            risultati = supabase.table('promemoria').select('*').order('data_creazione', desc=True).execute().data
        else:
            risultati = supabase.table('promemoria').select('*').eq('utente_id', session['user_id']).order('data_creazione', desc=True).execute().data

        return jsonify({"success": True, "promemoria": risultati})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# =====================================
# STORICO (route già definita con log_storico)
# =====================================
@app.route('/storico')
@login_required
def storico():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT s.*, u.username FROM storico_azioni s LEFT JOIN utenti u ON s.utente_id = u.id ORDER BY s.data_ora DESC LIMIT 200")
        storico_rows = cur.fetchall()
    except Exception:
        app.logger.exception("Errore nel recupero dello storico.")
        storico_rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if request.args.get('ajax') in ['1', 'true']:
        return jsonify(storico_rows)
    return render_template('storico.html', storico=storico_rows)

# =====================================
# AVVIO SERVER
# =====================================
if __name__ == '__main__':
    app.run(debug=True)

