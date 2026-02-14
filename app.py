import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import os
from streamlit_js_eval import get_geolocation
import time
import base64
from io import BytesIO
from PIL import Image

# --- CONFIGURAZIONE SISTEMA ---
st.set_page_config(
    page_title="Chemifol Enterprise 37.0", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

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

# --- MOTORE GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_df(sheet_name):
    """Legge una scheda e pulisce le righe vuote"""
    try:
        # ttl=5 evita l'errore 429 (troppe richieste)
        df = conn.read(worksheet=sheet_name, ttl=5)
        df = df.dropna(how='all')
        # Pulisce i nomi delle colonne da spazi accidentali
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame() 

def update_df(sheet_name, df):
    """Salva il dataframe sulla scheda"""
    try:
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore salvataggio {sheet_name}: {e}")

def get_next_id(df):
    """Calcola il prossimo ID"""
    if df.empty or 'id' not in df.columns:
        return 1
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0)
    return int(df['id'].max()) + 1

# --- UTILITY FOTO (Base64) ---
def process_image(img_file):
    """Converte foto in testo compresso per Google Sheets"""
    if img_file is None: return ""
    try:
        img = Image.open(img_file)
        # Ridimensiona a 600px per risparmiare spazio nel foglio
        img.thumbnail((600, 600)) 
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=50) # Qualità media per velocità
        return base64.b64encode(buffered.getvalue()).decode()
    except: return ""

def decode_image(img_str):
    """Legge il testo e lo fa tornare foto"""
    try: return base64.b64decode(img_str)
    except: return None

# --- UTILITY DI LETTURA ---
def get_all_cantieri():
    df = get_df("cantieri")
    if not df.empty and 'attivo' in df.columns:
        return sorted(df[df['attivo'] == 1]['nome_cantiere'].astype(str).unique().tolist())
    elif not df.empty and 'nome_cantiere' in df.columns:
        return sorted(df['nome_cantiere'].astype(str).unique().tolist())
    return []

def get_all_staff():
    df = get_df("users")
    if not df.empty:
        return df[df['role'] == 'user']['username'].astype(str).unique().tolist()
    return []

# --- GESTIONE LOGO ---
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
    # --- LOGIN MODIFICATO E BLINDATO ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        st.subheader("🔐 Accesso Sicuro")
        with st.form("login_frm"):
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password")
            submitted = st.form_submit_button("ENTRA")
            
            if submitted:
                users = get_df("users")
                if users.empty:
                    st.error("Errore: Il foglio 'users' è vuoto o non raggiungibile.")
                else:
                    # PULIZIA DATI (Rimuove spazi vuoti invisibili e .0)
                    users['username'] = users['username'].astype(str).str.strip().str.lower()
                    
                    # Funzione pulizia password
                    def clean_pass(val):
                        s = str(val).strip()
                        if s.endswith('.0'): return s[:-2]
                        return s
                    
                    users['password'] = users['password'].apply(clean_pass)
                    
                    # Cerca utente
                    u_clean = u.strip().lower()
                    p_clean = p.strip()
                    
                    usr = users[(users['username'] == u_clean) & (users['password'] == p_clean)]
                    
                    if not usr.empty:
                        user_data = usr.iloc[0]
                        st.session_state.user = (
                            user_data['username'], 
                            user_data['password'], 
                            user_data['role'], 
                            user_data['nome_completo'], 
                            int(user_data['pwd_changed']) if 'pwd_changed' in user_data else 0
                        )
                        st.rerun()
                    else: 
                        st.error("Dati errati.")
                        
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
                    users = get_df("users")
                    # Pulizia per sicurezza
                    users['username'] = users['username'].astype(str).str.strip().str.lower()
                    
                    users.loc[users['username'] == u_curr, 'password'] = p1
                    users.loc[users['username'] == u_curr, 'pwd_changed'] = 1
                    update_df("users", users)
                    
                    st.session_state.user = (u_curr, p1, role_curr, name_curr, 1)
                    st.success("Password aggiornata! Accesso in corso..."); time.sleep(1); st.rerun()
                else: st.error("Le password non coincidono o sono vuote.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ------------------------------------------------------------------
    #                               SEZIONE ADMIN
    # ------------------------------------------------------------------
    if role_curr == 'admin':
        with st.sidebar:
            st.markdown(f"## 👷 {name_curr}")
            st.divider()
            
            df_logs = get_df("logs")
            n_log = len(df_logs[df_logs['visto'] == 0]) if not df_logs.empty and 'visto' in df_logs.columns else 0
            
            df_iss = get_df("issues")
            n_iss = len(df_iss[(df_iss['visto'] == 0) & (df_iss['status'] == 'APERTA')]) if not df_iss.empty and 'visto' in df_iss.columns else 0
            
            df_mat = get_df("material_requests")
            n_mat = len(df_mat[(df_mat['visto'] == 0) & (df_mat['status'] == 'PENDING')]) if not df_mat.empty and 'visto' in df_mat.columns else 0
            
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

        if st.session_state.msg_feedback:
            st.success(st.session_state.msg_feedback)
            st.session_state.msg_feedback = None

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
                    df_b = get_df("bacheca")
                    new_id = get_next_id(df_b)
                    new_row = pd.DataFrame([{
                        "id": new_id, "titolo": titolo, "messaggio": msg, 
                        "destinatario": dest_str, 
                        "data_pubblicazione": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        "data_scadenza": scad.strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df_b = pd.concat([df_b, new_row], ignore_index=True)
                    update_df("bacheca", df_b)
                    st.success("Pubblicato!"); st.rerun()
                else: st.error("Compila tutti i campi.")
            st.divider()
            st.subheader("Annunci Attivi")
            anns = get_df("bacheca")
            if not anns.empty:
                anns['data_scadenza'] = pd.to_datetime(anns['data_scadenza'])
                anns = anns[anns['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                for _, a in anns.iterrows():
                    st.info(f"[{a['destinatario']}] **{a['titolo']}**: {a['messaggio']} (Scade: {a['data_scadenza']})")
                    if st.button(f"Elimina {a['id']}", key=f"del_{a['id']}"): 
                        df_all = get_df("bacheca")
                        df_all = df_all[df_all['id'] != a['id']]
                        update_df("bacheca", df_all)
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_mat:
            st.title("📦 Richieste Materiale")
            if n_mat > 0:
                df_m = get_df("material_requests")
                df_m.loc[df_m['visto'] == 0, 'visto'] = 1
                update_df("material_requests", df_m)
            
            mode_mat = st.radio("Filtro:", ["DA FORNIRE (Pending)", "ARCHIVIO (Forniti)"], horizontal=True)
            
            if mode_mat == "DA FORNIRE (Pending)":
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                cantieri_list = ["TUTTI"] + get_all_cantieri()
                filter_loc = st.selectbox("📍 Filtra per Postazione/Cantiere:", cantieri_list)
                df_reqs = get_df("material_requests")
                if not df_reqs.empty:
                    df_reqs = df_reqs[df_reqs['status'] == 'PENDING']
                    if filter_loc != "TUTTI":
                        df_reqs = df_reqs[df_reqs['location'] == filter_loc]
                    df_reqs = df_reqs.sort_values('request_date', ascending=False)
                    st.write(f"Trovate **{len(df_reqs)}** richieste.")
                    for _, r in df_reqs.iterrows():
                        loc_display = r['location'] if pd.notna(r['location']) else "Nessuna postazione"
                        with st.container():
                            st.markdown(f"""<div class='req-card'><b>👷 {r['username']}</b> presso <b>📍 {loc_display}</b><br>📅 {r['request_date']}<br><hr style='margin:5px 0'>🛒 <b>Lista:</b><br>{r['item_list']}</div>""", unsafe_allow_html=True)
                            if st.button("✅ SEGNA COME FORNITO", key=f"mat_ok_{r['id']}"):
                                df_all = get_df("material_requests")
                                df_all.loc[df_all['id'] == r['id'], 'status'] = 'ARCHIVED'
                                update_df("material_requests", df_all)
                                st.session_state.msg_feedback = "Richiesta archiviata!"
                                st.rerun()
                else: st.info("Nessuna richiesta.")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                df_arch = get_df("material_requests")
                if not df_arch.empty:
                    df_arch = df_arch[df_arch['status'] == 'ARCHIVED'].sort_values('request_date', ascending=False)
                    for _, r in df_arch.iterrows():
                        loc_display = r['location'] if pd.notna(r['location']) else "N/D"
                        with st.expander(f"✅ {r['request_date']} - {r['username']} @ {loc_display}"):
                            st.write(f"**Materiale:** {r['item_list']}")
                            if st.button("❌ ELIMINA", key=f"del_arch_mat_{r['id']}"):
                                df_all = get_df("material_requests")
                                df_all = df_all[df_all['id'] != r['id']]
                                update_df("material_requests", df_all)
                                st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_gest:
            st.title("👥 Gestione Risorse")
            tab_res, tab_loc, tab_ass = st.tabs(["➕ Dipendente", "🏗️ Cantiere", "🔗 Assegnazioni"])
            
            with tab_res:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("Gestione Dipendenti")
                c1, c2 = st.columns(2)
                nu = c1.text_input("Nuovo Username").strip()
                nn = c2.text_input("Nome Completo")
                np = st.text_input("Password Iniziale", value="1234")
                if st.button("CREA DIPENDENTE"):
                    df_u = get_df("users")
                    if nu in df_u['username'].values:
                        st.error("Username esistente.")
                    else:
                        new_row = pd.DataFrame([{"username": nu, "password": np, "role": "user", "nome_completo": nn, "pwd_changed": 0}])
                        df_u = pd.concat([df_u, new_row], ignore_index=True)
                        update_df("users", df_u)
                        st.success("Creato!"); st.rerun()
                st.divider()
                u_del = st.selectbox("Utente da eliminare", ["Seleziona..."] + get_all_staff())
                if u_del != "Seleziona..." and st.button("ELIMINA DIPENDENTE ❌"):
                    df_u = get_df("users")
                    df_u = df_u[df_u['username'] != u_del]
                    update_df("users", df_u)
                    df_ass = get_df("assignments")
                    df_ass = df_ass[df_ass['username'] != u_del]
                    update_df("assignments", df_ass)
                    st.success("Eliminato."); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_loc:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                nl = st.text_input("Nuovo Cantiere")
                if st.button("AGGIUNGI CANTIERE"):
                    df_c = get_df("cantieri")
                    if not df_c.empty and nl in df_c['nome_cantiere'].values:
                        st.error("Esistente.")
                    else:
                        new_row = pd.DataFrame([{"nome_cantiere": nl, "attivo": 1}])
                        df_c = pd.concat([df_c, new_row], ignore_index=True)
                        update_df("cantieri", df_c)
                        st.success("Aggiunto!"); st.rerun()
                st.divider()
                c_del = st.selectbox("Cantiere da eliminare", ["Seleziona..."] + get_all_cantieri())
                if c_del != "Seleziona..." and st.button("ELIMINA CANTIERE ❌"):
                    df_c = get_df("cantieri")
                    df_c = df_c[df_c['nome_cantiere'] != c_del]
                    update_df("cantieri", df_c)
                    df_ass = get_df("assignments")
                    df_ass = df_ass[df_ass['location'] != c_del]
                    update_df("assignments", df_ass)
                    st.success("Eliminato."); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_ass:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                su = st.selectbox("Dipendente", get_all_staff())
                df_ass = get_df("assignments")
                curr_ass = []
                if not df_ass.empty and not df_ass[df_ass['username'] == su].empty:
                    curr_ass = df_ass[df_ass['username'] == su]['location'].tolist()
                na = st.multiselect("Assegna", get_all_cantieri(), default=curr_ass)
                if st.button("SALVA ASSEGNAZIONI"):
                    if not df_ass.empty:
                        df_ass = df_ass[df_ass['username'] != su]
                    new_rows = []
                    for l in na:
                        new_rows.append({"username": su, "location": l})
                    if new_rows:
                        df_ass = pd.concat([df_ass, pd.DataFrame(new_rows)], ignore_index=True)
                    update_df("assignments", df_ass)
                    st.success("Salvato.")
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_seg:
            st.title("⚠️ Segnalazioni")
            if n_iss > 0:
                df_i = get_df("issues")
                df_i.loc[df_i['visto'] == 0, 'visto'] = 1
                update_df("issues", df_i)
            mode = st.radio("Vista:", ["APERTE (Da Lavorare)", "RISOLTE (Archivio)"], horizontal=True)
            df_iss = get_df("issues")
            if mode == "APERTE (Da Lavorare)":
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'APERTA'].sort_values('timestamp', ascending=False)
                    for _, r in df_iss.iterrows():
                        with st.container():
                            st.markdown(f"<div class='issue-card'><b>📍 {r['location']}</b> | 👷 {r['username']}<br>📅 {r['timestamp']}<br><br>📝 {r['description']}</div>", unsafe_allow_html=True)
                            
                            # --- VISUALIZZATORE FOTO ADMIN ---
                            if 'image' in r and pd.notna(r['image']) and len(str(r['image'])) > 100:
                                try:
                                    img_data = decode_image(r['image'])
                                    if img_data:
                                        st.image(img_data, width=300, caption="📸 Foto dal cantiere")
                                except: st.error("Errore caricamento foto")
                            # ---------------------------------

                            if st.button("✅ RISOLVI", key=f"s_{r['id']}"):
                                df_all = get_df("issues")
                                df_all.loc[df_all['id'] == r['id'], 'status'] = 'RISOLTO'
                                update_df("issues", df_all)
                                st.rerun()
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'RISOLTO'].sort_values('timestamp', ascending=False)
                    for _, r in df_iss.iterrows():
                        with st.expander(f"✅ {r['timestamp']} - {r['username']} @ {r['location']}"):
                            st.write(f"**Descrizione:** {r['description']}")
                            
                            # --- VISUALIZZATORE FOTO ARCHIVIO ---
                            if 'image' in r and pd.notna(r['image']) and len(str(r['image'])) > 100:
                                try:
                                    img_data = decode_image(r['image'])
                                    if img_data: st.image(img_data, width=200)
                                except: pass
                            # ------------------------------------

                            if st.button("ELIMINA DEFINITIVAMENTE ❌", key=f"del_arch_{r['id']}"):
                                df_all = get_df("issues")
                                df_all = df_all[df_all['id'] != r['id']]
                                update_df("issues", df_all)
                                st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_map:
            st.title("🗺️ Tracciamento GPS")
            if n_log > 0:
                df_l = get_df("logs")
                df_l.loc[df_l['visto'] == 0, 'visto'] = 1
                update_df("logs", df_l)
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Utente", ["TUTTI"] + get_all_staff())
            fl = c2.selectbox("Luogo", ["TUTTE"] + get_all_cantieri())
            fd = c3.date_input("Data Specifica", value=datetime.now())
            df = get_df("logs")
            if not df.empty:
                df = df[df['gps_lat'] != 0]
                if fu != "TUTTI": df = df[df['username'] == fu]
                if fl != "TUTTE": df = df[df['location'] == fl]
                df['start_time'] = pd.to_datetime(df['start_time'])
                df = df[df['start_time'].dt.date == fd].sort_values('start_time', ascending=False)
                if not df.empty:
                    for _, r in df.iterrows():
                        o_in = r['start_time'].strftime('%H:%M')
                        o_out = "IN CORSO"
                        if pd.notna(r['end_time']):
                            o_out = pd.to_datetime(r['end_time']).strftime('%H:%M')
                        with st.expander(f"📍 {r['username']} @ {r['location']} ({o_in} - {o_out})"):
                            ci, co = st.columns(2)
                            try:
                                ci.success(f"🟢 IN: {o_in}")
                                ci.map(pd.DataFrame({'latitude': [float(r['gps_lat'])], 'longitude': [float(r['gps_lon'])]}), zoom=15)
                            except: ci.error("Err GPS")
                            if pd.notna(r['end_time']):
                                try:
                                    co.error(f"🔴 OUT: {o_out}")
                                    co.map(pd.DataFrame({'latitude': [float(r['gps_lat_out'])], 'longitude': [float(r['gps_lon_out'])]}), zoom=15)
                                except: pass
                            if st.button(f"Elimina {r['id']} ❌", key=f"dm_{r['id']}"):
                                df_all = get_df("logs")
                                df_all = df_all[df_all['id'] != r['id']]
                                update_df("logs", df_all)
                                st.rerun()
                else: st.info("Nessun percorso trovato.")
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_rep:
            st.title("📊 Report Ore")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            col_mode, col_fil = st.columns([1, 3])
            filter_mode = col_mode.radio("Filtra per:", ["Mese", "Giorno"], horizontal=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Dipendente", ["TUTTI"] + get_all_staff(), key="ru")
            fl = c2.selectbox("Postazione", ["TUTTE"] + get_all_cantieri(), key="rl")
            df = get_df("logs")
            if not df.empty:
                df = df[pd.notna(df['end_time'])].copy()
                df['start_time'] = pd.to_datetime(df['start_time'])
                df['end_time'] = pd.to_datetime(df['end_time'])
                df['Ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                
                # --- DOWNLOAD BUTTON AGGIUNTO ---
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 SCARICA EXCEL (CSV)", data=csv, file_name="report_ore.csv", mime='text/csv')
                # --------------------------------

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
                    if c_6.button("❌", key=f"dh_{r['id']}"):
                         df_all = get_df("logs")
                         df_all = df_all[df_all['id'] != r['id']]
                         update_df("logs", df_all)
                         st.rerun()
                st.markdown("</table>", unsafe_allow_html=True)
                st.success(f"TOTALE: {df['Ore'].sum():.2f} ore")
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_cal:
            st.title("🗓️ Matrice")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            su = st.selectbox("Dipendente", get_all_staff(), key="mu")
            df = get_df("logs")
            if not df.empty:
                df = df[(df['username'] == su) & (pd.notna(df['end_time']))].copy()
                if not df.empty:
                    df['start_time'] = pd.to_datetime(df['start_time'])
                    df['end_time'] = pd.to_datetime(df['end_time'])
                    df['Giorno'] = df['start_time'].dt.day; df['Mese'] = df['start_time'].dt.strftime('%m-%Y')
                    df['Ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                    sm = st.selectbox("Mese", df['Mese'].unique())
                    piv = df[df['Mese'] == sm].pivot_table(index='location', columns='Giorno', values='Ore', aggfunc='sum', fill_value=0)
                    piv['TOTALE'] = piv.sum(axis=1)
                    st.dataframe(piv, use_container_width=True)
                else: st.info("Nessun dato.")
            else: st.info("Nessun dato.")
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_sec:
            st.title("🔐 Sicurezza")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            st.subheader("Admin")
            nap = st.text_input("Nuova Password Admin", type="password")
            if st.button("CAMBIA"):
                df_u = get_df("users")
                df_u.loc[df_u['username'] == 'mimmo', 'password'] = nap
                update_df("users", df_u)
                st.success("OK")
            st.divider()
            st.subheader("Reset Staff")
            ur = st.selectbox("Dipendente", get_all_staff())
            if st.button("RESET A 1234"):
                df_u = get_df("users")
                df_u.loc[df_u['username'] == ur, 'password'] = '1234'
                df_u.loc[df_u['username'] == ur, 'pwd_changed'] = 0
                update_df("users", df_u)
                st.success("Fatto")
            st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    #                               SEZIONE DIPENDENTE
    # ------------------------------------------------------------------
    else:
        with st.sidebar:
            if os.path.exists("logo.png"): st.image("logo.png", width=150)
            st.markdown(f"### Ciao, {name_curr}"); st.divider()
            menu_emp = st.radio("Vai a:", ["📢 Bacheca", "📦 Richiesta Materiale", "📍 Timbratore"])
            st.divider(); 
            if st.button("Logout"): st.session_state.user = None; st.rerun()

        if menu_emp == "📢 Bacheca":
            st.title("📢 Bacheca Comunicazioni")
            anns = get_df("bacheca")
            if not anns.empty:
                anns['data_scadenza'] = pd.to_datetime(anns['data_scadenza'])
                anns = anns[anns['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                found = False
                for _, m in anns.iterrows():
                    dests = str(m['destinatario']).split(',')
                    if "TUTTI" in dests or u_curr in dests:
                        found = True
                        st.markdown(f"<div class='bacheca-card'><span class='bacheca-title'>{m['titolo']}</span>{m['messaggio']}<div class='bacheca-meta'>Del: {str(m['data_pubblicazione'])[:10]}</div></div>", unsafe_allow_html=True)
                if not found: st.info("Nessun avviso.")
            else: st.info("Nessun avviso.")

        elif menu_emp == "📦 Richiesta Materiale":
            st.title("📦 Richiesta Prodotti/Materiale")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            st.info("Usa questo modulo per richiedere prodotti, DPI o attrezzatura all'amministrazione.")
            
            with st.form("req_form"):
                df_ass = get_df("assignments")
                locs_avail = []
                if not df_ass.empty:
                    locs_avail = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs_avail:
                    sel_loc = st.selectbox("Per quale cantiere/postazione?", locs_avail)
                    txt_mat = st.text_area("Elenco materiale richiesto (Specifica quantità)", height=150)
                    
                    if st.form_submit_button("INVIA RICHIESTA"):
                        if txt_mat and sel_loc:
                            df_m = get_df("material_requests")
                            new_id = get_next_id(df_m)
                            new_row = pd.DataFrame([{
                                "id": new_id, "username": u_curr, "location": sel_loc, 
                                "item_list": txt_mat, 
                                "request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                "status": "PENDING", "visto": 0
                            }])
                            df_m = pd.concat([df_m, new_row], ignore_index=True)
                            update_df("material_requests", df_m)
                            st.success(f"Richiesta per {sel_loc} inviata con successo!")
                        else: st.error("Compila tutti i campi.")
                else:
                    st.warning("Non hai cantieri assegnati per cui richiedere materiale.")
                    st.form_submit_button("INVIA RICHIESTA", disabled=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.subheader("Le tue ultime richieste")
            df_m = get_df("material_requests")
            if not df_m.empty:
                my_reqs = df_m[df_m['username'] == u_curr].sort_values('request_date', ascending=False).head(5)
                for _, r in my_reqs.iterrows():
                    status_icon = "⏳ IN ATTESA" if r['status'] == 'PENDING' else "✅ FORNITO/ARCHIVIATO"
                    loc_display = r['location'] if pd.notna(r['location']) else "N/D"
                    st.caption(f"{r['request_date']} - 📍 {loc_display} - {status_icon}")
                    st.text(r['item_list'])
                    st.divider()

        elif menu_emp == "📍 Timbratore":
            st.title("📍 Gestione Turno")
            df_logs = get_df("logs")
            active = None
            if not df_logs.empty:
                active_logs = df_logs[
                    (df_logs['username'] == u_curr) & 
                    (df_logs['end_time'].isna() | (df_logs['end_time'] == ""))
                ]
                if not active_logs.empty:
                    active = active_logs.iloc[0]

            if active is not None:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.success(f"SEI A: **{active['location']}**")
                st.write(f"Dalle: {active['start_time']}")
                st.subheader("🔴 Termina Turno")
                loc_out = get_geolocation(component_key="out_geo")
                if st.button("TIMBRA USCITA"):
                    if loc_out and 'coords' in loc_out:
                        df_logs.loc[df_logs['id'] == active['id'], 'end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df_logs.loc[df_logs['id'] == active['id'], 'gps_lat_out'] = loc_out['coords']['latitude']
                        df_logs.loc[df_logs['id'] == active['id'], 'gps_lon_out'] = loc_out['coords']['longitude']
                        df_logs.loc[df_logs['id'] == active['id'], 'visto'] = 0
                        update_df("logs", df_logs)
                        st.balloons(); st.rerun()
                    else: st.error("Attendi il segnale GPS o abilita la posizione.")
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.divider()
                st.markdown("### ⚠️ Segnala Problema")
                with st.expander("Apri modulo segnalazione"):
                    d = st.text_area("Descrizione")
                    # --- SCATTA FOTO ---
                    img_file = st.camera_input("Scatta una foto")
                    
                    if st.button("INVIA SEGNALAZIONE"):
                        if d or img_file:
                            # Processa immagine se presente
                            img_str = process_image(img_file)
                            
                            df_i = get_df("issues")
                            new_id = get_next_id(df_i)
                            new_row = pd.DataFrame([{
                                "id": new_id, "username": u_curr, "description": d, 
                                "location": active['location'], 
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                "status": "APERTA", 
                                "image": img_str, # Salva la foto codificata
                                "visto": 0
                            }])
                            df_i = pd.concat([df_i, new_row], ignore_index=True)
                            update_df("issues", df_i)
                            st.success("Inviata!")
                        else: st.error("Scrivi qualcosa o fai una foto.")
                    # -------------------
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("🟩 Inizia Turno")
                df_ass = get_df("assignments")
                locs = []
                if not df_ass.empty:
                    locs = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs:
                    sl = st.selectbox("Cantiere", locs)
                    lin = get_geolocation(component_key="in_geo")
                    if st.button("TIMBRA INGRESSO"):
                        if lin and 'coords' in lin:
                            new_id = get_next_id(df_logs)
                            new_row = pd.DataFrame([{
                                "id": new_id, "username": u_curr, "location": sl, 
                                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                "end_time": None, 
                                "gps_lat": lin['coords']['latitude'], "gps_lon": lin['coords']['longitude'], 
                                "gps_lat_out": 0, "gps_lon_out": 0, "method": "app", "visto": 0
                            }])
                            df_logs = pd.concat([df_logs, new_row], ignore_index=True)
                            update_df("logs", df_logs)
                            st.rerun() 
                        else: st.error("Attendi il segnale GPS o abilita la posizione.")
                else: st.warning("Non hai cantieri assegnati.")
                st.markdown("</div>", unsafe_allow_html=True)

# --- FINE PROGRAMMA ---
