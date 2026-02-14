import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import os
from streamlit_js_eval import get_geolocation
import time

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
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        df = df.dropna(how='all')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame() 

def update_df(sheet_name, df):
    try:
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Errore salvataggio {sheet_name}: {e}")

def get_next_id(df):
    if df.empty or 'id' not in df.columns:
        return 1
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0)
    return int(df['id'].max()) + 1

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
                    st.error("Errore: Il foglio 'users' è vuoto.")
                else:
                    # --- CORREZIONE PASSWORD (Toglie il .0) ---
                    users['username'] = users['username'].astype(str).str.strip().str.lower()
                    
                    # Funzione per pulire la password dal .0
                    def clean_password(val):
                        s = str(val).strip()
                        if s.endswith('.0'):
                            return s[:-2]
                        return s

                    users['password'] = users['password'].apply(clean_password)
                    
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
                    users['username'] = users['username'].astype(str).str.strip().str.lower()
                    users.loc[users['username'] == u_curr, 'password'] = p1
                    users.loc[users['username'] == u_curr, 'pwd_changed'] = 1
                    update_df("users", users)
                    st.session_state.user = (u_curr, p1, role_curr, name_curr, 1)
                    st.success("Password aggiornata! Accesso in corso..."); time.sleep(1); st.rerun()
                else: st.error("Le password non coincidono.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # --- MENU ADMIN ---
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
            titolo = c1.text_input("Titolo Annuncio")
            users_list = get_all_staff()
            destinatari_sel = c2.multiselect("Rivolto a:", ["TUTTI"] + users_list, default=["TUTTI"])
            msg = st.text_area("Messaggio")
            durata = st.slider("Giorni validità", 1, 60, 7)
            if st.button("PUBBLICA ANNUNCIO"):
                if titolo and msg:
                    dest_str = "TUTTI" if "TUTTI" in destinatari_sel else ",".join(destinatari_sel)
                    scad = datetime.now() + timedelta(days=durata)
                    df_b = get_df("bacheca")
                    new_id = get_next_id(df_b)
                    new_row = pd.DataFrame([{"id": new_id, "titolo": titolo, "messaggio": msg, "destinatario": dest_str, "data_pubblicazione": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data_scadenza": scad.strftime("%Y-%m-%d %H:%M:%S")}])
                    update_df("bacheca", pd.concat([df_b, new_row], ignore_index=True))
                    st.success("Pubblicato!"); st.rerun()
            st.divider()
            anns = get_df("bacheca")
            if not anns.empty:
                anns['data_scadenza'] = pd.to_datetime(anns['data_scadenza'])
                anns = anns[anns['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                for _, a in anns.iterrows():
                    st.info(f"[{a['destinatario']}] **{a['titolo']}**: {a['messaggio']}")
                    if st.button(f"Elimina {a['id']}", key=f"del_{a['id']}"): 
                        df_all = get_df("bacheca")
                        update_df("bacheca", df_all[df_all['id'] != a['id']])
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_mat:
            st.title("📦 Richieste Materiale")
            df_m = get_df("material_requests")
            if not df_m.empty:
                df_m.loc[df_m['visto'] == 0, 'visto'] = 1
                update_df("material_requests", df_m)
            mode_mat = st.radio("Filtro:", ["DA FORNIRE", "ARCHIVIO"], horizontal=True)
            if mode_mat == "DA FORNIRE":
                df_reqs = get_df("material_requests")
                if not df_reqs.empty:
                    df_reqs = df_reqs[df_reqs['status'] == 'PENDING']
                    for _, r in df_reqs.iterrows():
                        with st.container():
                            st.markdown(f"<div class='req-card'>👷 {r['username']} @ {r['location']}<br>{r['item_list']}</div>", unsafe_allow_html=True)
                            if st.button("✅ FORNITO", key=f"mat_ok_{r['id']}"):
                                df_all = get_df("material_requests")
                                df_all.loc[df_all['id'] == r['id'], 'status'] = 'ARCHIVED'
                                update_df("material_requests", df_all)
                                st.rerun()
            else:
                st.write("Archivio richieste completate.")

        elif choice == m_gest:
            st.title("👥 Gestione Staff e Cantieri")
            t1, t2, t3 = st.tabs(["Staff", "Cantieri", "Assegnazioni"])
            with t1:
                nu = st.text_input("Nuovo Username")
                nn = st.text_input("Nome Completo")
                if st.button("CREA UTENTE"):
                    df_u = get_df("users")
                    new_r = pd.DataFrame([{"username": nu.lower(), "password": "1234", "role": "user", "nome_completo": nn, "pwd_changed": 0}])
                    update_df("users", pd.concat([df_u, new_r], ignore_index=True))
                    st.success("Creato!")
            with t2:
                nl = st.text_input("Nome Cantiere")
                if st.button("AGGIUNGI CANTIERE"):
                    df_c = get_df("cantieri")
                    new_r = pd.DataFrame([{"nome_cantiere": nl, "attivo": 1}])
                    update_df("cantieri", pd.concat([df_c, new_r], ignore_index=True))
                    st.success("Aggiunto!")
            with t3:
                su = st.selectbox("Seleziona Staff", get_all_staff())
                df_ass = get_df("assignments")
                curr = df_ass[df_ass['username'] == su]['location'].tolist() if not df_ass.empty else []
                na = st.multiselect("Assegna Cantieri", get_all_cantieri(), default=curr)
                if st.button("SALVA ASSEGNAZIONI"):
                    df_ass = df_ass[df_ass['username'] != su] if not df_ass.empty else pd.DataFrame(columns=['username','location'])
                    new_rows = pd.DataFrame([{"username": su, "location": l} for l in na])
                    update_df("assignments", pd.concat([df_ass, new_rows], ignore_index=True))
                    st.success("Salvate!")

        elif choice == m_seg:
            st.title("⚠️ Segnalazioni")
            df_iss = get_df("issues")
            if not df_iss.empty:
                for _, r in df_iss[df_iss['status']=='APERTA'].iterrows():
                    st.error(f"📍 {r['location']} - 👷 {r['username']}: {r['description']}")
                    if st.button("✅ RISOLVI", key=f"iss_{r['id']}"):
                        df_iss.loc[df_iss['id'] == r['id'], 'status'] = 'RISOLTO'
                        update_df("issues", df_iss)
                        st.rerun()

        elif choice == m_map:
            st.title("🗺️ Posizioni GPS")
            df = get_df("logs")
            if not df.empty:
                st.dataframe(df[df['gps_lat']!=0])

        elif choice == m_rep:
            st.title("📊 Report Ore")
            df = get_df("logs")
            if not df.empty:
                df['start_time'] = pd.to_datetime(df['start_time'])
                df['end_time'] = pd.to_datetime(df['end_time'])
                df['ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                st.write(df[['username', 'location', 'start_time', 'end_time', 'ore']])

        elif choice == m_sec:
            st.title("🔐 Sicurezza")
            nap = st.text_input("Nuova Password Admin", type="password")
            if st.button("Aggiorna Password Admin"):
                df_u = get_df("users")
                df_u.loc[df_u['username'] == 'mimmo', 'password'] = nap
                update_df("users", df_u)
                st.success("Fatto!")

    # --- SEZIONE DIPENDENTE ---
    else:
        with st.sidebar:
            st.markdown(f"### Ciao, {name_curr}")
            menu_emp = st.radio("Vai a:", ["📢 Bacheca", "📦 Materiale", "📍 Timbratore"])
            if st.button("Logout"): st.session_state.user = None; st.rerun()

        if menu_emp == "📢 Bacheca":
            anns = get_df("bacheca")
            if not anns.empty:
                for _, m in anns.iterrows():
                    if "TUTTI" in str(m['destinatario']) or u_curr in str(m['destinatario']):
                        st.markdown(f"<div class='bacheca-card'><b>{m['titolo']}</b><br>{m['messaggio']}</div>", unsafe_allow_html=True)

        elif menu_emp == "📦 Materiale":
            with st.form("mat_req"):
                df_ass = get_df("assignments")
                locs = df_ass[df_ass['username'] == u_curr]['location'].tolist() if not df_ass.empty else []
                sel_l = st.selectbox("Cantiere", locs)
                txt = st.text_area("Cosa ti serve?")
                if st.form_submit_button("INVIA RICHIESTA"):
                    df_m = get_df("material_requests")
                    new_r = pd.DataFrame([{"id": get_next_id(df_m), "username": u_curr, "location": sel_l, "item_list": txt, "request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "PENDING", "visto": 0}])
                    update_df("material_requests", pd.concat([df_m, new_r], ignore_index=True))
                    st.success("Inviata!")

        elif menu_emp == "📍 Timbratore":
            df_logs = get_df("logs")
            active = df_logs[(df_logs['username'] == u_curr) & (df_logs['end_time'].isna() | (df_logs['end_time'] == ""))] if not df_logs.empty else pd.DataFrame()
            if not active.empty:
                st.success(f"Sei in turno a: {active.iloc[0]['location']}")
                loc_out = get_geolocation(component_key="out_geo")
                if st.button("TIMBRA USCITA"):
                    if loc_out:
                        df_logs.loc[df_logs['id'] == active.iloc[0]['id'], 'end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df_logs.loc[df_logs['id'] == active.iloc[0]['id'], 'gps_lat_out'] = loc_out['coords']['latitude']
                        df_logs.loc[df_logs['id'] == active.iloc[0]['id'], 'gps_lon_out'] = loc_out['coords']['longitude']
                        update_df("logs", df_logs)
                        st.rerun()
                st.divider()
                with st.expander("⚠️ Segnala Problema"):
                    d = st.text_area("Descrizione")
                    if st.button("INVIA"):
                        df_i = get_df("issues")
                        new_r = pd.DataFrame([{"id": get_next_id(df_i), "username": u_curr, "description": d, "location": active.iloc[0]['location'], "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "APERTA", "visto": 0}])
                        update_df("issues", pd.concat([df_i, new_r], ignore_index=True))
                        st.success("Inviata!")
            else:
                df_ass = get_df("assignments")
                locs = df_ass[df_ass['username'] == u_curr]['location'].tolist() if not df_ass.empty else []
                sl = st.selectbox("Dove sei?", locs)
                lin = get_geolocation(component_key="in_geo")
                if st.button("TIMBRA INGRESSO"):
                    if lin:
                        df_logs = get_df("logs")
                        new_r = pd.DataFrame([{"id": get_next_id(df_logs), "username": u_curr, "location": sl, "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "gps_lat": lin['coords']['latitude'], "gps_lon": lin['coords']['longitude'], "visto": 0}])
                        update_df("logs", pd.concat([df_logs, new_r], ignore_index=True))
                        st.rerun()
