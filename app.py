from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tuo_secret_key'

# =====================================
# Database connection
# =====================================
def get_db_connection():
    conn = psycopg2.connect(
        host='aws-1-eu-central-1.pooler.supabase.com',
        port=6543,
        database='postgres',
        user='postgres.cwuzhmfktymgmjolykgs',
        password='CRonaldo7.!'
    )
    return conn

# =====================================
# Utility functions
# =====================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Devi essere loggato per accedere a questa pagina.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_nome_reale(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM utenti WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

# =====================================
# LOGIN / LOGOUT
# =====================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM utenti WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            flash("Username o password non validi.")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Hai effettuato il logout.")
    return redirect('/login')

# =====================================
# HOME
# =====================================
@app.route('/')
@login_required
def home():
    nome_reale = get_nome_reale(session['user_id'])
    return render_template('home.html', nome_reale=nome_reale)

# =====================================
# CLIENTI
# =====================================
@app.route('/clienti')
@login_required
def lista_clienti():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM clienti WHERE utente_id=%s ORDER BY id", (session['user_id'],))
    clienti = cur.fetchall()
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
        request.form['nome'],
        request.form['cognome'],
        request.form['data_nascita'] or None,
        request.form['provincia'],
        request.form['comune'],
        request.form['codice_fiscale'],
        request.form.get('telefono'),
        request.form.get('email'),
        session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clienti
        (nome, cognome, data_nascita, provincia, comune, codice_fiscale, telefono, email, utente_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, data)
    conn.commit()
    conn.close()
    return redirect('/clienti')

@app.route('/modifica_cliente/<int:id>', methods=['GET'])
@login_required
def modifica_cliente(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM clienti WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    cliente = cur.fetchone()
    conn.close()
    if cliente:
        return render_template('modifica_cliente.html', cliente=cliente)
    flash("Cliente non trovato.")
    return redirect('/clienti')

@app.route('/aggiorna_cliente/<int:id>', methods=['POST'])
@login_required
def aggiorna_cliente(id):
    data = (
        request.form['nome'],
        request.form['cognome'],
        request.form['data_nascita'] or None,
        request.form['provincia'],
        request.form['comune'],
        request.form['codice_fiscale'],
        request.form.get('telefono'),
        request.form.get('email'),
        session['user_id'],
        id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE clienti
        SET nome=%s, cognome=%s, data_nascita=%s, provincia=%s, comune=%s,
            codice_fiscale=%s, telefono=%s, email=%s, utente_id=%s
        WHERE id=%s
    """, data)
    conn.commit()
    conn.close()
    return redirect('/clienti')

@app.route('/elimina_cliente/<int:id>')
@login_required
def elimina_cliente(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clienti WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/clienti')

# =====================================
# VETTURE
# =====================================
@app.route('/vetture')
@login_required
def lista_vetture():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM vetture WHERE utente_id=%s ORDER BY id", (session['user_id'],))
    vetture = cur.fetchall()
    conn.close()
    return render_template('vetture.html', vetture=vetture)

@app.route('/inserisci_vettura', methods=['GET'])
@login_required
def inserisci_vettura():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, nome, cognome FROM clienti WHERE utente_id=%s ORDER BY id", (session['user_id'],))
    clienti = cur.fetchall()
    conn.close()
    return render_template('inserisci_vettura.html', clienti=clienti)

@app.route('/salva_vettura', methods=['POST'])
@login_required
def salva_vettura():
    data = (
        request.form['cliente_id'],
        request.form['targa'],
        request.form['marca'],
        request.form['modello'],
        request.form['cilindrata'],
        request.form['kw'],
        request.form['carburante'],
        request.form.get('codice_motore'),
        request.form.get('telaio'),
        request.form.get('immatricolazione') or None,
        request.form.get('km'),
        request.form.get('cambio'),
        session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vetture
        (cliente_id,targa,marca,modello,cilindrata,kw,carburante,codice_motore,telaio,immatricolazione,km,cambio,utente_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, data)
    conn.commit()
    conn.close()
    return redirect('/vetture')

@app.route('/modifica_vettura/<int:id>', methods=['GET'])
@login_required
def modifica_vettura(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM vetture WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    vettura = cur.fetchone()
    cur.execute("SELECT id, nome, cognome FROM clienti WHERE utente_id=%s ORDER BY id", (session['user_id'],))
    clienti = cur.fetchall()
    conn.close()
    if vettura:
        return render_template('modifica_vettura.html', vettura=vettura, clienti=clienti)
    flash("Vettura non trovata.")
    return redirect('/vetture')

@app.route('/aggiorna_vettura/<int:id>', methods=['POST'])
@login_required
def aggiorna_vettura(id):
    data = (
        request.form['targa'],
        request.form['marca'],
        request.form['modello'],
        request.form['cilindrata'],
        request.form['kw'],
        request.form['carburante'],
        request.form.get('codice_motore'),
        request.form['cliente_id'],
        session['user_id'],
        id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE vetture
        SET targa=%s, marca=%s, modello=%s, cilindrata=%s, kw=%s, carburante=%s,
            codice_motore=%s, cliente_id=%s, utente_id=%s
        WHERE id=%s
    """, data)
    conn.commit()
    conn.close()
    return redirect('/vetture')

@app.route('/elimina_vettura/<int:id>')
@login_required
def elimina_vettura(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM vetture WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/vetture')

# =====================================
# MODELLI
# =====================================
@app.route('/modelli')
@login_required
def lista_modelli():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM modelli WHERE utente_id=%s ORDER BY id", (session['user_id'],))
    modelli = cur.fetchall()
    conn.close()
    return render_template('modelli.html', modelli=modelli)

@app.route('/inserisci_modello', methods=['GET'])
@login_required
def inserisci_modello():
    return render_template('inserisci_modello.html')

@app.route('/salva_modello', methods=['POST'])
@login_required
def salva_modello():
    data = (
        request.form['marca'],
        request.form['modello'],
        request.form.get('cilindrata'),
        request.form.get('kw'),
        request.form.get('carburante'),
        request.form.get('codice_motore'),
        session['user_id']
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO modelli
        (marca, modello, cilindrata, kw, carburante, codice_motore, utente_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, data)
    conn.commit()
    conn.close()
    return redirect('/modelli')

@app.route('/modifica_modello/<int:id>', methods=['GET'])
@login_required
def modifica_modello(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM modelli WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    modello = cur.fetchone()
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
        request.form.get('cilindrata'),
        request.form.get('kw'),
        request.form.get('carburante'),
        request.form.get('codice_motore'),
        session['user_id'],
        id
    )
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE modelli
        SET marca=%s, modello=%s, cilindrata=%s, kw=%s, carburante=%s, codice_motore=%s, utente_id=%s
        WHERE id=%s
    """, data)
    conn.commit()
    conn.close()
    return redirect('/modelli')

@app.route('/elimina_modello/<int:id>')
@login_required
def elimina_modello(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM modelli WHERE id=%s AND utente_id=%s", (id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/modelli')

# =====================================
# RICAMBI (GLOBALI)
# =====================================
@app.route('/ricambi')
@login_required
def lista_ricambi():
    filtro_prefisso = request.args.get('prefisso') or ''
    ricerca = request.args.get('q') or ''
    query = "SELECT * FROM ricambi WHERE utente_id IS NULL"
    params = []
    if filtro_prefisso:
        query += " AND codice LIKE %s"
        params.append(f"{filtro_prefisso}%")
    if ricerca:
        query += " AND codice LIKE %s"
        params.append(f"%{ricerca}%")
    query += " ORDER BY id"
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params)
    ricambi = cur.fetchall()
    conn.close()
    return render_template('ricambi.html', ricambi=ricambi, filtro_prefisso=filtro_prefisso, ricerca=ricerca)

@app.route('/inserisci_ricambio', methods=['GET'])
@login_required
def inserisci_ricambio():
    return render_template('inserisci_ricambio.html')

@app.route('/salva_ricambio', methods=['POST'])
@login_required
def salva_ricambio():
    nome = request.form['nome']
    codice = request.form['codice']
    quantita = int(request.form.get('quantita', 0))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ricambi (nome, codice, quantita, utente_id)
        VALUES (%s,%s,%s,NULL)
        ON CONFLICT (codice) DO UPDATE
        SET nome=EXCLUDED.nome,
            quantita=EXCLUDED.quantita,
            utente_id=NULL
    """, (nome, codice, quantita))
    conn.commit()
    conn.close()
    return redirect('/ricambi')

@app.route('/modifica_ricambio/<int:id>', methods=['GET'])
@login_required
def modifica_ricambio(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM ricambi WHERE id=%s AND utente_id IS NULL", (id,))
    ricambio = cur.fetchone()
    conn.close()
    if ricambio:
        return render_template('modifica_ricambio.html', ricambio=ricambio)
    flash("Ricambio non trovato.")
    return redirect('/ricambi')

@app.route('/aggiorna_ricambio/<int:id>', methods=['POST'])
@login_required
def aggiorna_ricambio(id):
    nome = request.form['nome']
    codice = request.form['codice']
    quantita = int(request.form.get('quantita', 0))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ricambi
        SET nome=%s, codice=%s, quantita=%s
        WHERE id=%s AND utente_id IS NULL
    """, (nome, codice, quantita, id))
    conn.commit()
    conn.close()
    return redirect('/ricambi')

@app.route('/elimina_ricambio/<int:id>')
@login_required
def elimina_ricambio(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ricambi WHERE id=%s AND utente_id IS NULL", (id,))
    conn.commit()
    conn.close()
    return redirect('/ricambi')

# =====================================
# Aggiorna quantità ricambi collegati
# =====================================
def aggiorna_quantita_collegati(ricambio_id, nuova_quantita):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT codice FROM ricambi WHERE id=%s AND utente_id IS NULL", (ricambio_id,))
    row = cur.fetchone()
    if row:
        codice = row[0]
        cur.execute("""
            UPDATE ricambi r
            SET quantita = %s
            FROM ricambi_collegati rc
            WHERE ((rc.codice_principale = %s AND rc.codice_secondario = r.codice)
                OR (rc.codice_secondario = %s AND rc.codice_principale = r.codice))
              AND r.id <> %s
              AND r.utente_id IS NULL
        """, (nuova_quantita, codice, codice, ricambio_id))
        conn.commit()
    conn.close()

@app.route('/aggiorna_quantita_ricambio/<int:id>', methods=['POST'])
@login_required
def aggiorna_quantita_ricambio(id):
    nuova_quantita = int(request.form['quantita'])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE ricambi SET quantita=%s WHERE id=%s AND utente_id IS NULL", (nuova_quantita, id))
    conn.commit()
    conn.close()
    aggiorna_quantita_collegati(id, nuova_quantita)
    return redirect('/ricambi')

# =====================================
# STORICO AZIONI
# =====================================
@app.route('/storico')
@login_required
def storico():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM storico_azioni ORDER BY data_ora DESC")
    logs = cur.fetchall()
    conn.close()
    return render_template('storico.html', logs=logs)

# =====================================
# AVVIO SERVER
# =====================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
