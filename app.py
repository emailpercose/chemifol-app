import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import os
from streamlit_js_eval import get_geolocation
import time
from PIL import Image
import io

# ==============================================================================
# 1. CONFIGURAZIONE E STILE
# ==============================================================================
st.set_page_config(
    page_title="CHEMIFOL", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

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

# ==============================================================================
# 2. CONNESSIONE SUPABASE
# ==============================================================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        st.error("⚠️ Configura i Secrets su Streamlit!")
        return None

supabase = init_connection()

def get_df(table_name):
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def upload_photo(file):
    if not file or not supabase: return None
    try:
        file_name = f"{int(time.time())}_{file.name}"
        file_bytes = file.getvalue()
        supabase.storage.from_("foto_cantieri").upload(file_name, file_bytes, {"content-type": file.type})
        return supabase.storage.from_("foto_cantieri").get_public_url(file_name)
    except:
        return None

def get_all_cantieri():
    df = get_df("cantieri")
    if not df.empty and 'attivo' in df.columns:
        # Mostra solo quelli attivi per le nuove assegnazioni
        return sorted(df[df['attivo'] == 1]['nome_cantiere'].unique().tolist())
    elif not df.empty and 'nome_cantiere' in df.columns:
        return sorted(df['nome_cantiere'].unique().tolist())
    return []

def get_all_staff():
    df = get_df("users")
    if not df.empty:
        return df[df['role'] == 'user']['username'].unique().tolist()
    return []

# --- INIZIO PROGRAMMA ---
if 'user' not in st.session_state: st.session_state.user = None
if 'msg_feedback' not in st.session_state: st.session_state.msg_feedback = None

# Gestione Titolo/Logo
if os.path.exists("logo.png"):
    c_logo, _ = st.columns([1, 4])
    with c_logo: st.image("logo.png", width=250)
else:
    st.markdown("<h1 style='text-align: center; color: #2e7d32;'>CHEMIFOL</h1>", unsafe_allow_html=True)

# ==============================================================================
# 3. LOGICA LOGIN (MODIFICATA PER PERSISTENZA)
# ==============================================================================

# --- Auto-Login da Parametri URL ---
if st.session_state.user is None:
    qp = st.query_params
    if "u_persist" in qp:
        u_saved = qp["u_persist"]
        try:
            res = supabase.table("users").select("*").eq("username", u_saved).execute()
            if res.data:
                st.session_state.user = res.data[0]
                st.rerun()
        except:
            pass

if not st.session_state.user:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        st.subheader("🔐 Accesso CHEMIFOL")
        with st.form("login_frm"):
            u = st.text_input("Username").strip().lower()
            p = st.text_input("Password", type="password").strip()
            if st.form_submit_button("ENTRA"):
                try:
                    res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                    if res.data:
                        st.session_state.user = res.data[0]
                        # Salva sessione in URL
                        st.query_params["u_persist"] = u
                        st.rerun()
                    else:
                        st.error("Credenziali errate.")
                except Exception as e:
                    st.error(f"Errore connessione: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    user = st.session_state.user
    u_curr = user['username']
    name_display = "Mimmo Folda" if u_curr == 'mimmo' else user['nome_completo']
    role_curr = user['role']
    
    if role_curr == 'user' and user.get('pwd_changed') == 0:
        st.warning("Cambia la password al primo accesso.")
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        with st.form("first_pwd_change"):
            p1 = st.text_input("Nuova Password", type="password")
            p2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA E ACCEDI"):
                success = False
                if p1 and p1 == p2:
                    try:
                        supabase.table("users").update({"password": p1, "pwd_changed": 1}).eq("username", u_curr).execute()
                        success = True
                    except Exception as e: st.error(f"Errore: {e}")
                else: st.error("Le password non coincidono.")
                
                if success:
                    st.session_state.user = None
                    st.query_params.clear() # Pulisce per sicurezza
                    st.success("Fatto! Ricarica..."); time.sleep(1); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ------------------------------------------------------------------
    # MENU ADMIN
    # ------------------------------------------------------------------
    if role_curr == 'admin':
        with st.sidebar:
            st.markdown(f"## 👷 {name_display}")
            st.divider()
            
            # Conteggi
            df_logs = get_df("logs")
            n_log = len(df_logs[df_logs['visto'] == 0]) if not df_logs.empty and 'visto' in df_logs.columns else 0
            df_iss = get_df("issues")
            n_iss = len(df_iss[(df_iss['visto'] == 0) & (df_iss['status'] == 'APERTA')]) if not df_iss.empty and 'visto' in df_iss.columns else 0
            df_mat = get_df("material_requests")
            n_mat = len(df_mat[(df_mat['visto'] == 0) & (df_mat['status'] == 'PENDING')]) if not df_mat.empty and 'visto' in df_mat.columns else 0
            
            # Voci menu con badge
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
            if st.button("Esci"): 
                st.session_state.user = None
                st.query_params.clear() # Cancella persistenza
                st.rerun()

        if st.session_state.msg_feedback:
            st.success(st.session_state.msg_feedback); st.session_state.msg_feedback = None

        if choice == m_bach:
            st.title("📢 Bacheca Aziendale")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2 = st.columns([2, 1])
            titolo = c1.text_input("Titolo Annuncio")
            users = get_all_staff()
            destinatari_sel = c2.multiselect("Rivolto a:", ["TUTTI"] + users, default=["TUTTI"])
            msg = st.text_area("Messaggio")
            durata = st.slider("Giorni validità", 1, 60, 7)
            if st.button("PUBBLICA ANNUNCIO"):
                success = False
                if titolo and msg and destinatari_sel:
                    dest_str = "TUTTI" if "TUTTI" in destinatari_sel else ",".join(destinatari_sel)
                    scad = datetime.now() + timedelta(days=durata)
                    try:
                        supabase.table("bacheca").insert({
                            "titolo": titolo, "messaggio": msg, "destinatario": dest_str,
                            "data_pubblicazione": datetime.now().isoformat(),
                            "data_scadenza": scad.isoformat()
                        }).execute()
                        success = True
                    except: st.error("Errore pubblicazione.")
                else: st.error("Compila tutti i campi.")
                
                if success:
                    st.success("Pubblicato!"); time.sleep(1); st.rerun()

            st.divider()
            st.subheader("Annunci Attivi")
            df_b = get_df("bacheca")
            if not df_b.empty:
                df_b['data_scadenza'] = pd.to_datetime(df_b['data_scadenza'])
                df_b = df_b[df_b['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                for _, a in df_b.iterrows():
                    st.info(f"[{a['destinatario']}] **{a['titolo']}**: {a['messaggio']} (Scade: {a['data_scadenza'].strftime('%d/%m')})")
                    if st.button("🗑️", key=f"del_b_{a['id']}"): 
                        try:
                            supabase.table("bacheca").delete().eq("id", a['id']).execute()
                            st.rerun()
                        except: st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_mat:
            st.title("📦 Richieste Materiale")
            if n_mat > 0: supabase.table("material_requests").update({"visto": 1}).eq("visto", 0).execute()
            
            mode_mat = st.radio("Filtro:", ["DA FORNIRE (Pending)", "ARCHIVIO (Forniti)"], horizontal=True)
            if mode_mat == "DA FORNIRE (Pending)":
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                cantieri_list = ["TUTTI"] + get_all_cantieri()
                filter_loc = st.selectbox("📍 Filtra per Postazione/Cantiere:", cantieri_list)
                df_reqs = get_df("material_requests")
                if not df_reqs.empty:
                    df_reqs = df_reqs[df_reqs['status'] == 'PENDING']
                    if filter_loc != "TUTTI": df_reqs = df_reqs[df_reqs['location'] == filter_loc]
                    df_reqs = df_reqs.sort_values('request_date', ascending=False)
                    st.write(f"Trovate **{len(df_reqs)}** richieste.")
                    for _, r in df_reqs.iterrows():
                        loc_display = r['location'] if pd.notna(r['location']) else "Nessuna postazione"
                        with st.container():
                            st.markdown(f"""<div class='req-card'><b>👷 {r['username']}</b> presso <b>📍 {loc_display}</b><br>📅 {r['request_date'][:10]}<br><hr style='margin:5px 0'>🛒 <b>Lista:</b><br>{r['item_list']}</div>""", unsafe_allow_html=True)
                            if st.button("✅ SEGNA COME FORNITO", key=f"mat_ok_{r['id']}"):
                                success = False
                                try:
                                    supabase.table("material_requests").update({"status": "ARCHIVED"}).eq("id", r['id']).execute()
                                    success = True
                                except: pass
                                
                                if success:
                                    st.session_state.msg_feedback = "Archiviata!"; st.rerun()
                else: st.info("Nessuna richiesta.")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                df_arch = get_df("material_requests")
                if not df_arch.empty:
                    df_arch = df_arch[df_arch['status'] == 'ARCHIVED'].sort_values('request_date', ascending=False)
                    for _, r in df_arch.iterrows():
                        loc_display = r['location'] if pd.notna(r['location']) else "N/D"
                        with st.expander(f"✅ {r['request_date'][:10]} - {r['username']} @ {loc_display}"):
                            st.write(f"**Materiale:** {r['item_list']}")
                            if st.button("❌ ELIMINA", key=f"del_arch_mat_{r['id']}"):
                                try:
                                    supabase.table("material_requests").delete().eq("id", r['id']).execute()
                                    st.rerun()
                                except: st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_gest:
            st.title("👥 Gestione Risorse")
            tab_res, tab_loc, tab_ass = st.tabs(["➕ Dipendente", "🏗️ Cantiere", "🔗 Assegnazioni"])
            
            with tab_res:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                nu = c1.text_input("Nuovo Username").strip()
                nn = c2.text_input("Nome Completo")
                np = st.text_input("Password Iniziale", value="1234")
                if st.button("CREA DIPENDENTE"):
                    success = False
                    try:
                        supabase.table("users").insert({"username": nu.lower(), "password": np, "role": "user", "nome_completo": nn}).execute()
                        success = True
                    except Exception as e: st.error(f"Errore (username esiste già?): {e}")
                    
                    if success:
                        st.success("Creato!"); time.sleep(1); st.rerun()

                st.divider()
                st.dataframe(get_df("users"), use_container_width=True)
                st.divider()
                
                u_del = st.selectbox("Utente da eliminare", ["..."] + get_all_staff())
                if u_del != "..." and st.button("ELIMINA DIPENDENTE"):
                    success = False
                    try:
                        supabase.table("users").delete().eq("username", u_del).execute()
                        supabase.table("assignments").delete().eq("username", u_del).execute()
                        success = True
                    except: st.error("Errore eliminazione")
                    
                    if success:
                        st.success("Eliminato."); time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_loc:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                nl = st.text_input("Nuovo Cantiere")
                if st.button("AGGIUNGI CANTIERE"):
                    success = False
                    try:
                        supabase.table("cantieri").insert({"nome_cantiere": nl, "attivo": 1}).execute()
                        success = True
                    except: st.error("Errore inserimento.")
                    
                    if success:
                        st.success("Aggiunto!"); time.sleep(1); st.rerun()

                st.divider()
                st.dataframe(get_df("cantieri"), use_container_width=True)
                st.divider()
                
                c_del = st.selectbox("Cantiere da eliminare (Soft Delete)", ["..."] + get_all_cantieri())
                if c_del != "..." and st.button("ELIMINA CANTIERE"):
                    success = False
                    try:
                        # MODIFICA: Invece di DELETE, facciamo UPDATE attivo = 0
                        # Così rimane nello storico dei Logs
                        supabase.table("cantieri").update({"attivo": 0}).eq("nome_cantiere", c_del).execute()
                        # Rimuoviamo solo l'assegnazione futura
                        supabase.table("assignments").delete().eq("location", c_del).execute()
                        success = True
                    except: st.error("Errore eliminazione")
                    
                    if success:
                        st.success("Eliminato (Archiviato)."); time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_ass:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                su = st.selectbox("Dipendente", get_all_staff())
                
                # --- FIX ASSEGNAZIONI ---
                df_ass = get_df("assignments")
                all_cantieri = get_all_cantieri()
                curr_ass = []
                
                if not df_ass.empty and 'username' in df_ass.columns and 'location' in df_ass.columns:
                    raw_ass = df_ass[df_ass['username'] == su]['location'].tolist()
                    curr_ass = [c for c in raw_ass if c in all_cantieri]
                
                na = st.multiselect("Assegna", all_cantieri, default=curr_ass)
                
                if st.button("SALVA ASSEGNAZIONI"):
                    success = False
                    try:
                        supabase.table("assignments").delete().eq("username", su).execute()
                        if na:
                            data = [{"username": su, "location": l} for l in na]
                            supabase.table("assignments").insert(data).execute()
                        success = True
                    except Exception as e: st.error(f"Errore: {e}")
                    
                    if success:
                        st.success("Salvato."); time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_seg:
            st.title("⚠️ Segnalazioni")
            if n_iss > 0: supabase.table("issues").update({"visto": 1}).eq("visto", 0).execute()
            
            mode = st.radio("Vista:", ["APERTE", "RISOLTE"], horizontal=True)
            df_iss = get_df("issues")
            
            if mode == "APERTE":
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'APERTA'].sort_values('timestamp', ascending=False)
                    for _, r in df_iss.iterrows():
                        with st.container():
                            st.markdown(f"<div class='issue-card'><b>📍 {r['location']}</b> | 👷 {r['username']}<br>📅 {r['timestamp'][:16]}<br><br>📝 {r['description']}</div>", unsafe_allow_html=True)
                            if r.get('image_url'): st.image(r['image_url'], width=300, caption="📸 Foto Cantiere")
                            if st.button("✅ RISOLVI", key=f"s_{r['id']}"):
                                try:
                                    supabase.table("issues").update({"status": "RISOLTO"}).eq("id", r['id']).execute()
                                    st.rerun()
                                except: st.rerun()
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'RISOLTO'].sort_values('timestamp', ascending=False)
                    for _, r in df_iss.iterrows():
                        with st.expander(f"✅ {r['timestamp'][:10]} - {r['username']} @ {r['location']}"):
                            st.write(f"**Descrizione:** {r['description']}")
                            if r.get('image_url'): st.image(r['image_url'], width=200)
                            if st.button("ELIMINA", key=f"del_arch_{r['id']}"):
                                try:
                                    supabase.table("issues").delete().eq("id", r['id']).execute()
                                    st.rerun()
                                except: st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_map:
            st.title("🗺️ Tracciamento GPS")
            if n_log > 0: supabase.table("logs").update({"visto": 1}).eq("visto", 0).execute()
            
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
                            ci.success(f"🟢 IN: {o_in}")
                            ci.map(pd.DataFrame({'latitude': [float(r['gps_lat'])], 'longitude': [float(r['gps_lon'])]}), zoom=15)
                            if pd.notna(r['end_time']):
                                co.error(f"🔴 OUT: {o_out}")
                                co.map(pd.DataFrame({'latitude': [float(r['gps_lat_out'])], 'longitude': [float(r['gps_lon_out'])]}), zoom=15)
                            if st.button(f"Elimina Log", key=f"dm_{r['id']}"):
                                try:
                                    supabase.table("logs").delete().eq("id", r['id']).execute()
                                    st.rerun()
                                except: st.rerun()
                else: st.info("Nessun percorso.")
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
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 SCARICA CSV", data=csv, file_name="report.csv", mime='text/csv')

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
                        try:
                            supabase.table("logs").delete().eq("id", r['id']).execute(); st.rerun()
                        except: st.rerun()
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
            st.markdown("</div>", unsafe_allow_html=True)

        elif choice == m_sec:
            st.title("🔐 Sicurezza")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            st.subheader("Admin")
            nap = st.text_input("Nuova Password Admin", type="password")
            if st.button("CAMBIA"):
                success = False
                try:
                    supabase.table("users").update({"password": nap}).eq("username", "mimmo").execute()
                    success = True
                except: st.error("Errore")
                if success: st.success("OK")

            st.divider()
            st.subheader("Reset Staff")
            ur = st.selectbox("Dipendente", get_all_staff())
            if st.button("RESET A 1234"):
                success = False
                try:
                    supabase.table("users").update({"password": "1234", "pwd_changed": 0}).eq("username", ur).execute()
                    success = True
                except: st.error("Errore")
                if success: st.success("Fatto")
            st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # MENU DIPENDENTE
    # ------------------------------------------------------------------
    else:
        with st.sidebar:
            if os.path.exists("logo.png"): st.image("logo.png", width=150)
            st.markdown(f"### Ciao, {name_display}")
            menu_emp = st.radio("Vai a:", ["📢 Bacheca", "📦 Richiesta Materiale", "📍 Timbratore"])
            st.divider()
            if st.button("Logout"): 
                st.session_state.user = None
                st.query_params.clear()
                st.rerun()

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
                if not df_ass.empty and 'username' in df_ass.columns:
                    locs_avail = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs_avail:
                    sel_loc = st.selectbox("Per quale cantiere/postazione?", locs_avail)
                    txt_mat = st.text_area("Elenco materiale richiesto (Specifica quantità)", height=150)
                    if st.form_submit_button("INVIA RICHIESTA"):
                        if txt_mat and sel_loc:
                            success = False
                            try:
                                supabase.table("material_requests").insert({
                                    "username": u_curr, "location": sel_loc, "item_list": txt_mat,
                                    "request_date": datetime.now().isoformat(), "status": "PENDING", "visto": 0
                                }).execute()
                                success = True
                            except Exception as e: st.error(f"Errore: {e}")
                            
                            if success:
                                st.success("Inviata!"); time.sleep(1); st.rerun()
                        else: st.error("Compila tutto.")
                else:
                    st.warning("Non hai cantieri assegnati.")
                    st.form_submit_button("INVIA", disabled=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.subheader("Le tue ultime richieste")
            df_m = get_df("material_requests")
            if not df_m.empty:
                my_reqs = df_m[df_m['username'] == u_curr].sort_values('request_date', ascending=False).head(5)
                for _, r in my_reqs.iterrows():
                    status_icon = "⏳ IN ATTESA" if r['status'] == 'PENDING' else "✅ FORNITO/ARCHIVIATO"
                    st.caption(f"{r['request_date'][:10]} - 📍 {r['location']} - {status_icon}")
                    st.text(r['item_list']); st.divider()

        elif menu_emp == "📍 Timbratore":
            st.title("📍 Gestione Turno")
            df_logs = get_df("logs")
            active = None
            if not df_logs.empty:
                active_logs = df_logs[(df_logs['username'] == u_curr) & (df_logs['end_time'].isna())]
                if not active_logs.empty: active = active_logs.iloc[0]

            if active is not None:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.success(f"SEI A: **{active['location']}**")
                st.write(f"Dalle: {active['start_time']}")
                st.subheader("🔴 Termina Turno")
                loc_out = get_geolocation(component_key="out_geo")
                if st.button("TIMBRA USCITA"):
                    if loc_out:
                        success = False
                        try:
                            supabase.table("logs").update({
                                "end_time": datetime.now().isoformat(),
                                "gps_lat_out": loc_out['coords']['latitude'],
                                "gps_lon_out": loc_out['coords']['longitude'], "visto": 0
                            }).eq("id", active['id']).execute()
                            success = True
                        except Exception as e: st.error(f"Errore: {e}")
                        
                        if success:
                            st.balloons(); time.sleep(1); st.rerun()
                    else: st.error("Attendi GPS.")
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.divider()
                st.markdown("### ⚠️ Segnala Problema")
                # MODIFICA RICHIESTA: Checkbox per mostrare segnalazione
                segnala_flag = st.checkbox("Vuoi segnalare qualche problema?")
                
                if segnala_flag:
                    d = st.text_area("Descrizione Problema")
                    img_file = st.camera_input("Scatta una foto")
                    if st.button("INVIA SEGNALAZIONE"):
                        if d or img_file:
                            success = False
                            try:
                                url_foto = upload_photo(img_file)
                                supabase.table("issues").insert({
                                    "username": u_curr, "description": d, "location": active['location'],
                                    "timestamp": datetime.now().isoformat(), "status": "APERTA",
                                    "image_url": url_foto, "visto": 0
                                }).execute()
                                success = True
                            except Exception as e: st.error(f"Errore: {e}")
                            
                            if success:
                                st.success("Inviata!"); time.sleep(1); st.rerun()
                        else: st.error("Scrivi qualcosa o fai una foto.")
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("🟩 Inizia Turno")
                df_ass = get_df("assignments")
                locs = []
                if not df_ass.empty and 'username' in df_ass.columns:
                    locs = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs:
                    sl = st.selectbox("Cantiere", locs)
                    lin = get_geolocation(component_key="in_geo")
                    if st.button("TIMBRA INGRESSO"):
                        if lin:
                            success = False
                            try:
                                supabase.table("logs").insert({
                                    "username": u_curr, "location": sl,
                                    "start_time": datetime.now().isoformat(),
                                    "gps_lat": lin['coords']['latitude'],
                                    "gps_lon": lin['coords']['longitude'], "visto": 0
                                }).execute()
                                success = True
                            except Exception as e: st.error(f"Errore: {e}")
                            
                            if success:
                                st.rerun()
                        else: st.error("Attendi GPS.")
                else: st.warning("Non hai cantieri assegnati.")
                st.markdown("</div>", unsafe_allow_html=True)

# --- FINE PROGRAMMA ---
