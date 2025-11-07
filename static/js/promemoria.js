document.addEventListener('DOMContentLoaded', () => {
    const quadProm = document.getElementById('quadrato-promemoria');
    const popupProm = document.getElementById('popup-promemoria');
    const listaProm = document.getElementById('lista-promemoria');
    const btnAddProm = document.getElementById('aggiungi-promemoria');
    const formProm = document.getElementById('form-promemoria');
    const inputTitolo = document.getElementById('titolo-promemoria');
    const inputDesc = document.getElementById('descrizione-promemoria');
    const btnSalvaProm = document.getElementById('salva-promemoria');

    if (!quadProm) return;

    // --- Mostra / nascondi popup laterale ---
    quadProm.addEventListener('click', async () => {
        const visibile = popupProm.style.display === 'block';
        popupProm.style.display = visibile ? 'none' : 'block';
        if (!visibile) await caricaPromemoria();
    });

    // --- Mostra form per nuovo promemoria ---
    btnAddProm.addEventListener('click', () => {
        formProm.style.display = formProm.style.display === 'none' ? 'block' : 'none';
        inputTitolo.focus();
    });

    // --- Salva nuovo promemoria ---
    btnSalvaProm.addEventListener('click', async () => {
        const titolo = inputTitolo.value.trim();
        const info = inputDesc.value.trim();
        if (!titolo) return alert('Inserisci un titolo.');

        try {
            const res = await fetch('/aggiungi_promemoria', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ testo: titolo || '', descrizione: info || '' })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                inputTitolo.value = '';
                inputDesc.value = '';
                formProm.style.display = 'none';
                await caricaPromemoria();
            } else {
                alert(data.error || 'Errore nel salvataggio.');
            }
        } catch {
            alert('Errore di connessione al server.');
        }
    });

    // --- Carica lista promemoria ---
    async function caricaPromemoria() {
        try {
            const res = await fetch('/lista_promemoria');
            const data = await res.json();
            listaProm.innerHTML = '';
            if (data.length === 0) {
                listaProm.innerHTML = '<li>Nessun promemoria</li>';
                return;
            }

            data.forEach(item => {
                const li = document.createElement('li');
                li.classList.add('promemoria-item');
                li.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong style="color:#004080;">${item.titolo || '(Senza titolo)'}</strong><br>
                            <span style="font-size:0.9em; color:#333;">${item.info || ''}</span>
                        </div>
                        <button class="elimina-promemoria" data-id="${item.id}" title="Elimina">🗑️</button>
                    </div>
                `;

                // Clic sul promemoria → mostra dettagli in finestra centrale
                li.querySelector('div').addEventListener('click', () => mostraDettagli(item));

                // Elimina promemoria
                li.querySelector('.elimina-promemoria').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (!confirm('Eliminare questo promemoria?')) return;
                    await eliminaPromemoria(item.id);
                });

                listaProm.appendChild(li);
            });
        } catch {
            listaProm.innerHTML = '<li>Errore nel caricamento</li>';
        }
    }

    // --- Elimina promemoria ---
    async function eliminaPromemoria(id) {
        try {
            const res = await fetch(`/elimina_promemoria/${id}`, { method: 'POST' });
            const data = await res.json();
            if (res.ok && data.success) {
                await caricaPromemoria();
            } else {
                alert(data.error || 'Errore durante l\'eliminazione.');
            }
        } catch {
            alert('Errore di connessione al server.');
        }
    }

    // --- Mostra finestra centrale con dettagli ---
    function mostraDettagli(item) {
        // Se esiste già, la rimuoviamo per ricrearla pulita
        const esistente = document.getElementById('dettagli-promemoria');
        if (esistente) esistente.remove();

        const overlay = document.createElement('div');
        overlay.id = 'dettagli-promemoria';
        overlay.style = `
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 3000;
        `;

        const box = document.createElement('div');
        box.style = `
            background: #f9fcff;
            border-radius: 12px;
            padding: 20px;
            width: 350px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.3);
            animation: fadeIn 0.25s ease-out;
            font-family: "Segoe UI", sans-serif;
            position: relative;
        `;
        box.innerHTML = `
            <h3 style="color:#007BFF; margin-top:0;">${item.titolo || '(Senza titolo)'}</h3>
            <p style="color:#333; white-space:pre-line;">${item.info || 'Nessuna descrizione.'}</p>
            <small style="color:#666;">Creato il: ${item.data_creazione || '-'}</small>
            <div style="text-align:right; margin-top:15px;">
                <button class="chiudi-dettagli" style="background:#add8e6; border:none; color:white; padding:6px 12px; border-radius:6px; cursor:pointer;">Chiudi</button>
            </div>
        `;

        overlay.appendChild(box);
        document.body.appendChild(overlay);

        // Chiudi cliccando il pulsante
        box.querySelector('.chiudi-dettagli').addEventListener('click', () => overlay.remove());

        // Chiudi cliccando fuori dal box
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
    }
});
