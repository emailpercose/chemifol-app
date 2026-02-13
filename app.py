import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
from streamlit_js_eval import get_geolocation
import time

# --- CONFIGURAZIONE SISTEMA ---
st.set_page_config(page_title="Chemifol Enterprise 37.0", page_icon="🏗️", layout="wide", initial_sidebar_state="expanded")

# --- CSS STILE ---
st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
    
    div.stBlock {
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border: 1px solid #e0e0e0; border-top: 5px solid #2e7d32; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    
    .stButton>button {
        background-color: #2e7d32; color: white; border: none; padding: 12px; 
        border-radius: 8px; font-weight: 600; width: 100%; transition: all 0.3s ease;
    }
    .stButton>button:hover { background-color: #1b5e20; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    
    [data-testid="stMap"] { height: 350px !important; border-radius: 10px; border: 1px solid #ccc; }
    
    .bacheca-card {
        background-color: #fffde7; border-left: 8px solid #fbc02d; padding: 15px;
        border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .bacheca-title { font-weight: 900; font-size: 18px; color: #f57f17; display: block; }
    .bacheca-meta { font-size: 12px; color: #777; margin-top: 5px; font-style: italic; }
    
    .issue-card {
        border-left: 5px solid #d32f2f; background-color: #fff; padding: 15px;
        margin-bottom: 10px; border-radius: 8px; border: 1px solid #eee;
    }
    
    .req-card {
        border-left: 5px solid #1976d2; background-color: #e3f2fd; padding: 15px;
        margin-bottom: 10px; border-radius: 8px; border: 1px solid #bbdefb;
    }

    .report-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .report-table th { background-color: #e8f5e9; padding: 10px; text-align: left; border-bottom: 2px solid #2e7d32; }
    .report-table td { padding: 10px; border-bottom: 1px solid #eee; }
    
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('chemifol_db_permanente.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, nome_completo TEXT, pwd_changed INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS assignments (username TEXT, location TEXT, PRIMARY KEY (username, location))''')
    c.execute('''CREATE TABLE IF NOT EXISTS cantieri (nome_cantiere TEXT PRIMARY KEY, attivo INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, location TEXT, 
        start_time TIMESTAMP, end_time TIMESTAMP, gps_lat REAL, gps_lon REAL, 
        gps_lat_out REAL, gps_lon_out REAL, method TEXT, visto INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, description TEXT, 
        location TEXT, timestamp TIMESTAMP, status TEXT, image BLOB, visto INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bacheca (
        id INTEGER PRIMARY KEY AUTOINCREMENT, titolo TEXT, messaggio TEXT, destinatario TEXT,
        data_pubblicazione TIMESTAMP, data_scadenza TIMESTAMP)''')
    
    # TABELLA RICHIESTA MATERIALE
    c.execute('''CREATE TABLE IF NOT EXISTS material_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, location TEXT, item_list TEXT,
        request_date TIMESTAMP, status TEXT DEFAULT 'PENDING', visto INTEGER DEFAULT 0)''')
    
    # Migrazioni per database esistenti (Evita errori se colonne mancano)
    try: c.execute("ALTER TABLE logs ADD COLUMN visto INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE issues ADD COLUMN visto INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE bacheca ADD COLUMN titolo TEXT")
    except: pass
    try: c.execute("ALTER TABLE bacheca ADD COLUMN destinatario TEXT DEFAULT 'TUTTI'")
    except: pass
    try: c.execute("ALTER TABLE material_requests ADD COLUMN visto INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE material_requests ADD COLUMN location TEXT")
    except: pass
    try: c.execute("ALTER TABLE material_requests ADD COLUMN status TEXT DEFAULT 'PENDING'")
    except: pass

    # Staff Default
    staff_default = [
        ('mimmo', '1234', 'admin', 'Mimmo Folda', 1),
        ('Concetta', '1234', 'user', 'Concetta Spina', 0),
        ('Francesca', '1234', 'user', 'Francesca Folda', 0),
        ('Catella', '1234', 'user', 'Catella Chioppa', 0),
        ('Giulia', '1234', 'user', 'Giulia Mele', 0),
        ('Marialaura', '1234', 'user', 'Marialaura Carnevale', 0),
        ('Lara', '1234', 'user', 'Lara Della Corte', 0),
        ('Salvatore', '1234', 'user', 'Salvatore Folda', 0)
    ]
    for s in staff_default:
        c.execute("INSERT INTO users (username, password, role, nome_completo, pwd_changed) VALUES (?,?,?,?,?) ON CONFLICT(username) DO NOTHING", s)
    
    check = c.execute("SELECT count(*) FROM cantieri").fetchone()[0]
    if check == 0:
        OLD_LOCS = ["Don Camillo", "Don Camillo pomeriggio", "Bellocchi", "Gitecna", "Foramil", "Pro Ingenio", "Windor San Giorgio", "CM-TS", "Impregico", "Geo Ga", "Windor Crispiano", "Studio 3A", "Professione casa", "Bonucci", "RD", "IM.A.F. srl", "Bianalisi - Centro Analisi", "Minerva", "Centro Radiologico", "Bellocchi straordinario", "Cappella Giampetruzzi"]
        for loc in OLD_LOCS:
            c.execute("INSERT INTO cantieri (nome_cantiere) VALUES (?) ON CONFLICT(nome_cantiere) DO NOTHING", (loc,))
    
    conn.commit()
    return conn

conn = init_db()

# --- UTILITY ---
def get_all_cantieri():
    return sorted([r[0] for r in conn.execute("SELECT nome_cantiere FROM cantieri WHERE attivo=1").fetchall()])

def get_all_staff():
    return [r[0] for r in conn.execute("SELECT username FROM users WHERE role='user'").fetchall()]

if os.path.exists("logo.png"):
    c_logo, _ = st.columns([1, 4])
    with c_logo: st.image("logo.png", width=250)
else:
    st.markdown("<h1 style='text-align: center; color: #2e7d32;'>CHEMIFOL GESTIONALE</h1>", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user = None
if 'msg_feedback' not in st.session_state: st.session_state.msg_feedback = None

# ==============================================================================
#                               LOGICA PRINCIPALE
# ==============================================================================

if not st.session_state.user:
    # --- LOGIN ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        st.subheader("🔐 Accesso Sicuro")
        with st.form("login_frm"):
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRA"):
                usr = conn.execute("SELECT * FROM users WHERE lower(username)=? AND password=?", (u.lower(), p)).fetchone()
                if usr:
                    st.session_state.user = usr
                    st.rerun()
                else: st.error("Dati errati.")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    # --- UTENTE LOGGATO ---
    u_curr, p_curr, role_curr, name_curr, pwd_chg = st.session_state.user
    
    # 1. Obbligo cambio password
    if role_curr == 'user' and pwd_chg == 0:
        st.warning(f"👋 Benvenuto, {name_curr}. Al primo accesso è obbligatorio cambiare la password.")
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        with st.form("first_pwd_change"):
            p1 = st.text_input("Nuova Password", type="password")
            p2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                if p1 and p1 == p2:
                    conn.execute("UPDATE users SET password=?, pwd_changed=1 WHERE username=?", (p1, u_curr))
                    conn.commit()
                    st.session_state.user = (u_curr, p1, role_curr, name_curr, 1)
                    st.success("Password aggiornata! Accesso in corso..."); time.sleep(1); st.rerun()
                else: st.error("Le password non coincidono o sono vuote.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ------------------------------------------------------------------
    #                           SEZIONE ADMIN
    # ------------------------------------------------------------------
    if role_curr == 'admin':
        with st.sidebar:
            st.markdown(f"## 👷 {name_curr}")
            st.divider()
            
            # Conta notifiche
            n_log = conn.execute("SELECT COUNT(*) FROM logs WHERE visto=0").fetchone()[0]
            n_iss = conn.execute("SELECT COUNT(*) FROM issues WHERE visto=0 AND status='APERTA'").fetchone()[0]
            n_mat = conn.execute("SELECT COUNT(*) FROM material_requests WHERE visto=0 AND status='PENDING'").fetchone()[0]
            
            # Voci Menu
            m_bach = "📢 Bacheca & News"
            m_mat = f"📦 Richiesta Materiale ({n_mat})" if n_mat > 0 else "📦 Richiesta Materiale"
            m_gest = "👥 Staff & Cantieri"
            m_seg = f"⚠️ Segnalazioni ({n_iss})" if n_iss > 0 else "⚠️ Segnalazioni"
            m_map = f"🗺️ Mappe GPS ({n_log})" if n_log > 0 else "🗺️ Mappe GPS"
            m_rep = f"📊 Report Ore ({n_log})" if n_log > 0 else "📊 Report Ore"
            m_cal = "🗓️ Calendario"
            m_sec = "🔐 Sicurezza"
            
            choice = st.radio("Navigazione:", [m_bach, m_mat, m_gest, m_seg, m_map, m_rep, m_cal, m_sec])
            st.divider()
            if st.button("Esci"): st.session_state.user = None; st.rerun()

        # Feedback messaggio persistente
        if st.session_state.msg_feedback:
            st.success(st.session_state.msg_feedback)
            st.session_state.msg_feedback = None

        # --- ADMIN: BACHECA ---
        if choice == m_bach:
            st.title("📢 Bacheca Aziendale")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2 = st.columns([2, 1])
            titolo = c1.text_input("Titolo Annuncio (Grassetto)")
            users = get_all_staff()
            destinatari_sel = c2.multiselect("Rivolto a:", ["TUTTI"] + users, default=["TUTTI"])
            msg = st.text_area("Messaggio")
            durata = st.slider("Giorni validità", 1, 60, 7)
            if st.button("PUBBLICA ANNUNCIO"):
                if titolo and msg and destinatari_sel:
                    dest_str = "TUTTI" if "TUTTI" in destinatari_sel else ",".join(destinatari_sel)
                    scad = datetime.now() + timedelta(days=durata)
                    conn.execute("INSERT INTO bacheca (titolo, messaggio, destinatario, data_pubblicazione, data_scadenza) VALUES (?, ?, ?, ?, ?)", (titolo, msg, dest_str, datetime.now(), scad))
                    conn.commit(); st.success("Pubblicato!"); st.rerun()
                else: st.error("Compila tutti i campi.")
            st.divider()
            st.subheader("Annunci Attivi")
            anns = pd.read_sql("SELECT * FROM bacheca WHERE data_scadenza > ? ORDER BY data_pubblicazione DESC", conn, params=(datetime.now(),))
            for _, a in anns.iterrows():
                st.info(f"[{a['destinatario']}] **{a['titolo']}**: {a['messaggio']} (Scade: {a['data_scadenza']})")
                if st.button(f"Elimina {a['id']}", key=f"del_{a['id']}"): conn.execute("DELETE FROM bacheca WHERE id=?", (a['id'],)); conn.commit(); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: RICHIESTA MATERIALE ---
        elif choice == m_mat:
            st.title("📦 Richieste Materiale")
            # Segna come letti
            if n_mat > 0: conn.execute("UPDATE material_requests SET visto=1 WHERE visto=0"); conn.commit()
            
            mode_mat = st.radio("Filtro:", ["DA FORNIRE (Pending)", "ARCHIVIO (Forniti)"], horizontal=True)
            
            if mode_mat == "DA FORNIRE (Pending)":
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                
                # FILTRO PER POSTAZIONE
                cantieri_list = ["TUTTI"] + get_all_cantieri()
                filter_loc = st.selectbox("📍 Filtra per Postazione/Cantiere:", cantieri_list)
                
                query = "SELECT * FROM material_requests WHERE status='PENDING'"
                params = []
                
                if filter_loc != "TUTTI":
                    query += " AND location = ?"
                    params.append(filter_loc)
                
                query += " ORDER BY request_date DESC"
                
                reqs = pd.read_sql(query, conn, params=params)
                
                if not reqs.empty:
                    st.write(f"Trovate **{len(reqs)}** richieste.")
                    for _, r in reqs.iterrows():
                        loc_display = r['location'] if r['location'] else "Nessuna postazione specificata"
                        with st.container():
                            st.markdown(f"""
                            <div class='req-card'>
                                <b>👷 {r['username']}</b> presso <b>📍 {loc_display}</b><br>
                                📅 {r['request_date']}<br>
                                <hr style='margin:5px 0'>
                                🛒 <b>Lista:</b><br>{r['item_list']}
                            </div>""", unsafe_allow_html=True)
                            if st.button("✅ SEGNA COME FORNITO (ARCHIVIA)", key=f"mat_ok_{r['id']}"):
                                conn.execute("UPDATE material_requests SET status='ARCHIVED' WHERE id=?", (r['id'],))
                                conn.commit()
                                # Messaggio di feedback e reload
                                st.session_state.msg_feedback = f"Richiesta di {r['username']} archiviata con successo! Controlla la scheda 'ARCHIVIO'."
                                st.rerun()
                else: 
                    st.info("Nessuna richiesta in sospeso per questa selezione.")
                st.markdown("</div>", unsafe_allow_html=True)
            
            else:
                # SEZIONE ARCHIVIO
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("Archivio Storico (Forniti)")
                
                arch_mat = pd.read_sql("SELECT * FROM material_requests WHERE status='ARCHIVED' ORDER BY request_date DESC", conn)
                
                if not arch_mat.empty:
                    for _, r in arch_mat.iterrows():
                        loc_display = r['location'] if r['location'] else "N/D"
                        with st.expander(f"✅ {r['request_date']} - {r['username']} @ {loc_display}"):
                            st.write(f"**Materiale:** {r['item_list']}")
                            # Tasto Elimina per rimuovere dal DB
                            if st.button("❌ ELIMINA DEFINITIVAMENTE", key=f"del_arch_mat_{r['id']}"):
                                conn.execute("DELETE FROM material_requests WHERE id=?", (r['id'],))
                                conn.commit()
                                st.session_state.msg_feedback = "Richiesta eliminata definitivamente dal database."
                                st.rerun()
                else:
                    st.info("L'archivio è vuoto.")
                st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: STAFF & CANTIERI ---
        elif choice == m_gest:
            st.title("👥 Gestione Risorse")
            tab_res, tab_loc, tab_ass = st.tabs(["➕ Dipendente", "🏗️ Cantiere", "🔗 Assegnazioni"])
            with tab_res:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("Gestione Dipendenti")
                c1, c2 = st.columns(2)
                nu = c1.text_input("Nuovo Username").strip(); nn = c2.text_input("Nome Completo"); np = st.text_input("Password Iniziale", value="1234")
                if st.button("CREA DIPENDENTE"):
                    try: conn.execute("INSERT INTO users (username, password, role, nome_completo, pwd_changed) VALUES (?, ?, 'user', ?, 0)", (nu, np, nn)); conn.commit(); st.success("Creato!"); st.rerun()
                    except: st.error("Username esistente.")
                st.divider()
                u_del = st.selectbox("Seleziona utente da eliminare", ["Seleziona..."] + get_all_staff())
                if u_del != "Seleziona..." and st.button("ELIMINA DIPENDENTE ❌"): conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.execute("DELETE FROM assignments WHERE username=?", (u_del,)); conn.commit(); st.success("Dipendente eliminato."); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with tab_loc:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("Gestione Postazioni")
                nl = st.text_input("Nuovo Cantiere")
                if st.button("AGGIUNGI CANTIERE"):
                    try: conn.execute("INSERT INTO cantieri (nome_cantiere) VALUES (?)", (nl,)); conn.commit(); st.success("Aggiunto!"); st.rerun()
                    except: st.error("Esistente.")
                st.divider()
                c_del = st.selectbox("Seleziona cantiere da eliminare", ["Seleziona..."] + get_all_cantieri())
                if c_del != "Seleziona..." and st.button("ELIMINA CANTIERE ❌"): conn.execute("DELETE FROM cantieri WHERE nome_cantiere=?", (c_del,)); conn.execute("DELETE FROM assignments WHERE location=?", (c_del,)); conn.commit(); st.success("Cantiere eliminato."); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with tab_ass:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                su = st.selectbox("Dipendente", get_all_staff())
                cl = [r[0] for r in conn.execute("SELECT location FROM assignments WHERE username=?", (su,)).fetchall()]
                na = st.multiselect("Assegna", get_all_cantieri(), default=cl)
                if st.button("SALVA ASSEGNAZIONI"): conn.execute("DELETE FROM assignments WHERE username=?", (su,)); conn.executemany("INSERT INTO assignments VALUES (?,?)", [(su, l) for l in na]); conn.commit(); st.success("Salvato.")
                st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: SEGNALAZIONI ---
        elif choice == m_seg:
            st.title("⚠️ Segnalazioni")
            if n_iss > 0: conn.execute("UPDATE issues SET visto=1 WHERE visto=0"); conn.commit()
            mode = st.radio("Vista:", ["APERTE (Da Lavorare)", "RISOLTE (Archivio)"], horizontal=True)
            if mode == "APERTE (Da Lavorare)":
                issues = pd.read_sql("SELECT * FROM issues WHERE status='APERTA' ORDER BY timestamp DESC", conn)
                for _, r in issues.iterrows():
                    with st.container():
                        st.markdown(f"<div class='issue-card'><b>📍 {r['location']}</b> | 👷 {r['username']}<br>📅 {r['timestamp']}<br><br>📝 {r['description']}</div>", unsafe_allow_html=True)
                        if r['image']: st.image(r['image'], width=250)
                        if st.button("✅ RISOLVI", key=f"s_{r['id']}"): conn.execute("UPDATE issues SET status='RISOLTO' WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                f_d = c1.selectbox("Chi", ["TUTTI"] + get_all_staff()); f_c = c2.selectbox("Dove", ["TUTTI"] + get_all_cantieri()); f_t = c3.date_input("Quando", value=None)
                q = "SELECT * FROM issues WHERE status='RISOLTO'"; p = []
                if f_d != "TUTTI": q += " AND username=?"; p.append(f_d)
                if f_c != "TUTTI": q += " AND location=?"; p.append(f_c)
                if f_t: q += " AND date(timestamp) = ?"; p.append(f_t)
                arch = pd.read_sql(q + " ORDER BY timestamp DESC", conn, params=p)
                if not arch.empty:
                    for _, r in arch.iterrows():
                        with st.expander(f"✅ {r['timestamp']} - {r['username']} @ {r['location']}"):
                            st.write(f"**Descrizione:** {r['description']}")
                            if r['image']: st.image(r['image'], caption="Foto allegata", width=300)
                            if st.button("ELIMINA DEFINITIVAMENTE ❌", key=f"del_arch_{r['id']}"): conn.execute("DELETE FROM issues WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                else: st.info("Nessuna segnalazione.")
                st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: MAPPE ---
        elif choice == m_map:
            st.title("🗺️ Tracciamento GPS")
            if n_log > 0: conn.execute("UPDATE logs SET visto=1 WHERE visto=0"); conn.commit()
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Utente", ["TUTTI"] + get_all_staff()); fl = c2.selectbox("Luogo", ["TUTTE"] + get_all_cantieri()); fd = c3.date_input("Data Specifica", value=datetime.now())
            q = "SELECT * FROM logs WHERE gps_lat != 0"; p = []
            if fu != "TUTTI": q += " AND username=?"; p.append(fu)
            if fl != "TUTTE": q += " AND location=?"; p.append(fl)
            if fd: q += " AND date(start_time) = ?"; p.append(fd)
            df = pd.read_sql(q + " ORDER BY start_time DESC", conn, params=p)
            if not df.empty:
                df['start_time'] = pd.to_datetime(df['start_time'])
                for _, r in df.iterrows():
                    o_in = r['start_time'].strftime('%H:%M'); o_out = "IN CORSO"
                    if r['end_time']: o_out = pd.to_datetime(r['end_time']).strftime('%H:%M')
                    with st.expander(f"📍 {r['username']} @ {r['location']} ({r['start_time'].strftime('%d/%m')} | {o_in} - {o_out})"):
                        ci, co = st.columns(2)
                        try:
                            if r['gps_lat']!=0: ci.success(f"🟢 IN: {o_in}"); ci.map(pd.DataFrame({'latitude': [r['gps_lat']], 'longitude': [r['gps_lon']]}), zoom=15)
                        except: ci.error("Err GPS")
                        if r['end_time']:
                            try:
                                if r['gps_lat_out']!=0: co.error(f"🔴 OUT: {o_out}"); co.map(pd.DataFrame({'latitude': [r['gps_lat_out']], 'longitude': [r['gps_lon_out']]}), zoom=15)
                            except: co.error("Err GPS Out")
                        if st.button(f"Elimina {r['id']} ❌", key=f"dm_{r['id']}"): conn.execute("DELETE FROM logs WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
            else: st.info("Nessun percorso.")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: REPORT ---
        elif choice == m_rep:
            st.title("📊 Report Ore")
            if n_log > 0: conn.execute("UPDATE logs SET visto=1 WHERE visto=0"); conn.commit()
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            col_mode, col_fil = st.columns([1, 3])
            filter_mode = col_mode.radio("Filtra per:", ["Mese", "Giorno"], horizontal=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Dipendente", ["TUTTI"] + get_all_staff(), key="ru"); fl = c2.selectbox("Postazione", ["TUTTE"] + get_all_cantieri(), key="rl")
            df = pd.read_sql("SELECT * FROM logs WHERE end_time IS NOT NULL ORDER BY start_time DESC", conn)
            if not df.empty:
                df['start_time'] = pd.to_datetime(df['start_time']); df['end_time'] = pd.to_datetime(df['end_time'])
                df['Ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                if filter_mode == "Mese":
                    fm = c3.selectbox("Seleziona Mese", df['start_time'].dt.strftime('%m-%Y').unique(), key="rm")
                    df = df[df['start_time'].dt.strftime('%m-%Y') == fm]
                else:
                    fd = c3.date_input("Seleziona Giorno", value=datetime.now())
                    df = df[df['start_time'].dt.date == fd]
                if fu != "TUTTI": df = df[df['username'] == fu]
                if fl != "TUTTE": df = df[df['location'] == fl]
                st.markdown("""<table class='report-table'><tr><th>CHI</th><th>DOVE</th><th>DATA</th><th>ORARI</th><th>ORE</th><th>DEL</th></tr>""", unsafe_allow_html=True)
                for _, r in df.iterrows():
                    c_1, c_2, c_3, c_4, c_5, c_6 = st.columns([2,2,1,2,1,1])
                    c_1.write(f"👷 {r['username']}"); c_2.write(f"📍 {r['location']}")
                    c_3.write(r['start_time'].strftime('%d/%m')); c_4.write(f"{r['start_time'].strftime('%H:%M')} - {r['end_time'].strftime('%H:%M')}")
                    c_5.write(f"**{r['Ore']}**")
                    if c_6.button("❌", key=f"dh_{r['id']}"): conn.execute("DELETE FROM logs WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                st.markdown("</table>", unsafe_allow_html=True)
                st.success(f"TOTALE: {df['Ore'].sum():.2f} ore")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: CALENDARIO ---
        elif choice == m_cal:
            st.title("🗓️ Matrice")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            su = st.selectbox("Dipendente", get_all_staff(), key="mu")
            df = pd.read_sql("SELECT * FROM logs WHERE username=? AND end_time IS NOT NULL", conn, params=(su,))
            if not df.empty:
                df['start_time'] = pd.to_datetime(df['start_time'])
                df['Giorno'] = df['start_time'].dt.day; df['Mese'] = df['start_time'].dt.strftime('%m-%Y')
                df['Ore'] = ((pd.to_datetime(df['end_time']) - df['start_time']).dt.total_seconds() / 3600).round(2)
                sm = st.selectbox("Mese", df['Mese'].unique())
                piv = df[df['Mese'] == sm].pivot_table(index='location', columns='Giorno', values='Ore', aggfunc='sum', fill_value=0)
                piv['TOTALE'] = piv.sum(axis=1)
                st.dataframe(piv, use_container_width=True)
            else: st.info("Nessun dato.")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: SICUREZZA ---
        elif choice == m_sec:
            st.title("🔐 Sicurezza")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            st.subheader("Admin")
            nap = st.text_input("Nuova Password Admin", type="password")
            if st.button("CAMBIA"): conn.execute("UPDATE users SET password=? WHERE username='mimmo'", (nap,)); conn.commit(); st.success("OK")
            st.divider()
            st.subheader("Reset Staff")
            ur = st.selectbox("Dipendente", get_all_staff())
            if st.button("RESET A 1234"): conn.execute("UPDATE users SET password='1234', pwd_changed=0 WHERE username=?", (ur,)); conn.commit(); st.success("Fatto")
            st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    #                           SEZIONE DIPENDENTE
    # ------------------------------------------------------------------
    else:
        with st.sidebar:
            if os.path.exists("logo.png"): st.image("logo.png", width=150)
            st.markdown(f"### Ciao, {name_curr}"); st.divider()
            
            menu_emp = st.radio("Vai a:", ["📢 Bacheca", "📦 Richiesta Materiale", "📍 Timbratore"])
            
            st.divider(); 
            if st.button("Logout"): st.session_state.user = None; st.rerun()

        # --- DIPENDENTE: BACHECA ---
        if menu_emp == "📢 Bacheca":
            st.title("📢 Bacheca Comunicazioni")
            msgs = pd.read_sql("SELECT * FROM bacheca WHERE data_scadenza > ? ORDER BY data_pubblicazione DESC", conn, params=(datetime.now(),))
            found = False
            for _, m in msgs.iterrows():
                dests = m['destinatario'].split(',')
                if "TUTTI" in dests or u_curr in dests:
                    found = True
                    st.markdown(f"<div class='bacheca-card'><span class='bacheca-title'>{m['titolo']}</span>{m['messaggio']}<div class='bacheca-meta'>Del: {m['data_pubblicazione'][:10]}</div></div>", unsafe_allow_html=True)
            if not found: st.info("Nessun avviso.")

        # --- DIPENDENTE: RICHIESTA MATERIALE ---
        elif menu_emp == "📦 Richiesta Materiale":
            st.title("📦 Richiesta Prodotti/Materiale")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            st.info("Usa questo modulo per richiedere prodotti, DPI o attrezzatura all'amministrazione.")
            
            with st.form("req_form"):
                # SELETTORE POSTAZIONE LIMITATO AGLI ASSEGNATI
                locs_avail = [r[0] for r in conn.execute("SELECT location FROM assignments WHERE username=?", (u_curr,)).fetchall()]
                
                if locs_avail:
                    sel_loc = st.selectbox("Per quale cantiere/postazione?", locs_avail)
                    txt_mat = st.text_area("Elenco materiale richiesto (Specifica quantità)", height=150)
                    
                    if st.form_submit_button("INVIA RICHIESTA"):
                        if txt_mat and sel_loc:
                            conn.execute("INSERT INTO material_requests (username, location, item_list, request_date, status, visto) VALUES (?, ?, ?, ?, 'PENDING', 0)", 
                                         (u_curr, sel_loc, txt_mat, datetime.now()))
                            conn.commit()
                            st.success(f"Richiesta per {sel_loc} inviata con successo!")
                        else: st.error("Compila tutti i campi.")
                else:
                    st.warning("Non hai cantieri assegnati per cui richiedere materiale.")
                    st.form_submit_button("INVIA RICHIESTA", disabled=True)

            st.markdown("</div>", unsafe_allow_html=True)
            
            # Storico Ultime Richieste
            st.subheader("Le tue ultime richieste")
            my_reqs = pd.read_sql("SELECT * FROM material_requests WHERE username=? ORDER BY request_date DESC LIMIT 5", conn, params=(u_curr,))
            if not my_reqs.empty:
                for _, r in my_reqs.iterrows():
                    status_icon = "⏳ IN ATTESA" if r['status'] == 'PENDING' else "✅ FORNITO/ARCHIVIATO"
                    loc_display = r['location'] if r['location'] else "N/D"
                    st.caption(f"{r['request_date']} - 📍 {loc_display} - {status_icon}")
                    st.text(r['item_list'])
                    st.divider()

        # --- DIPENDENTE: TIMBRATORE ---
        elif menu_emp == "📍 Timbratore":
            st.title("📍 Gestione Turno")
            active = conn.execute("SELECT * FROM logs WHERE username=? AND end_time IS NULL", (u_curr,)).fetchone()
            if active:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.success(f"SEI A: **{active[2]}**"); st.write(f"Dalle: {active[3]}")
                st.subheader("🔴 Termina Turno")
                loc_out = get_geolocation()
                if st.button("TIMBRA USCITA"):
                    if loc_out and 'coords' in loc_out:
                        conn.execute("UPDATE logs SET end_time=?, gps_lat_out=?, gps_lon_out=?, visto=0 WHERE id=?", (datetime.now(), loc_out['coords']['latitude'], loc_out['coords']['longitude'], active[0])); conn.commit(); st.balloons(); st.rerun()
                    else: st.error("Attiva GPS.")
                st.markdown("</div>", unsafe_allow_html=True)
                st.divider()
                st.markdown("### ⚠️ Segnala Problema")
                with st.expander("Apri modulo segnalazione"):
                    d = st.text_area("Descrizione"); f = st.camera_input("Foto")
                    if st.button("INVIA SEGNALAZIONE"):
                        b = f.getvalue() if f else None
                        conn.execute("INSERT INTO issues (username, description, location, timestamp, status, image, visto) VALUES (?,?,?,?,'APERTA',?,0)", (u_curr, d, active[2], datetime.now(), b)); conn.commit(); st.success("Inviata.")
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("🟩 Inizia Turno")
                locs = [r[0] for r in conn.execute("SELECT location FROM assignments WHERE username=?", (u_curr,)).fetchall()]
                if locs:
                    sl = st.selectbox("Cantiere", locs)
                    lin = get_geolocation()
                    if st.button("TIMBRA INGRESSO"):
                        if lin and 'coords' in lin:
                            conn.execute("INSERT INTO logs (username, location, start_time, gps_lat, gps_lon, method, visto) VALUES (?, ?, ?, ?, ?, 'app', 0)", (u_curr, sl, datetime.now(), lin['coords']['latitude'], lin['coords']['longitude'])); conn.commit(); st.rerun()
                        else: st.error("Attiva GPS.")
                else: st.warning("Nessun cantiere.")
                st.markdown("</div>", unsafe_allow_html=True)

# --- FINE PROGRAMMA ---