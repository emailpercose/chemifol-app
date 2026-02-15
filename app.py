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
# 1. CONFIGURAZIONE E STILE (OTTIMIZZATO MOBILE E STYLE SPLENDOR)
# ==============================================================================
st.set_page_config(
    page_title="CHEMIFOL", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# CSS AVANZATO: Mobile Friendly + Stile Corporate Blu
st.markdown("""
    <style>
    /* Font generale */
    .stApp { background-color: #f4f6f9; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    
    /* Stile Card / Blocchi */
    div.stBlock {
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 8px; 
        border: 1px solid #e0e0e0; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
        margin-bottom: 15px;
    }

    /* Bottoni Grandi e Blu (Facili da premere su mobile) */
    .stButton>button {
        background-color: #004085; 
        color: white; 
        border: none; 
        padding: 12px; 
        border-radius: 6px; 
        font-weight: 600; 
        width: 100%; 
        min-height: 45px; 
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stButton>button:hover { background-color: #002752; }

    /* Centratura Tabelle */
    .stDataFrame, .stTable {
        width: 100% !important;
        display: flex;
        justify-content: center;
    }
    
    /* Adattamenti Mobile */
    @media only screen and (max-width: 600px) {
        .stDataFrame { font-size: 11px; }
        h1 { font-size: 22px !important; text-align: center; color: #004085 !important; }
        h2 { font-size: 18px !important; text-align: center; color: #004085 !important; }
        h3 { font-size: 16px !important; text-align: center; }
        div.stBlock { padding: 12px; }
    }

    /* Link Mappe */
    .map-link {
        display: block;
        text-align: center;
        background-color: #e9ecef;
        padding: 10px;
        border-radius: 6px;
        color: #004085;
        text-decoration: none;
        font-weight: bold;
        margin-top: 8px;
        border: 1px solid #ced4da;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CONNESSIONE SUPABASE E FUNZIONI HELPER
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

# Funzione per esportare in Excel
def to_excel(df):
    output = io.BytesIO()
    # Usa xlsxwriter come motore
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

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

# Sidebar Logo / Titolo
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)
    else:
        st.markdown("<h2 style='color:#004085; text-align:center;'>CHEMIFOL</h2>", unsafe_allow_html=True)

# ==============================================================================
# 3. LOGICA LOGIN (PERSISTENTE)
# ==============================================================================

# Auto-Login da URL
if st.session_state.user is None:
    qp = st.query_params
    if "u_persist" in qp:
        u_saved = qp["u_persist"]
        try:
            res = supabase.table("users").select("*").eq("username", u_saved).execute()
            if res.data:
                st.session_state.user = res.data[0]
                st.rerun()
        except: pass

if not st.session_state.user:
    # Schermata Login
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div class='stBlock' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='color: #004085;'>Portale Accesso</h3>", unsafe_allow_html=True)
        
        with st.form("login_frm"):
            u = st.text_input("Utente").strip().lower()
            p = st.text_input("Password", type="password").strip()
            resta_collegato = st.checkbox("Resta collegato")
            
            if st.form_submit_button("ACCEDI"):
                try:
                    res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                    if res.data:
                        st.session_state.user = res.data[0]
                        if resta_collegato: 
                            st.query_params["u_persist"] = u
                        else: 
                            st.query_params.clear()
                        st.rerun()
                    else:
                        st.error("Credenziali errate.")
                except Exception as e:
                    st.error(f"Errore connessione: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    # --- UTENTE LOGGATO ---
    user = st.session_state.user
    u_curr = user['username']
    name_display = "Mimmo Folda" if u_curr == 'mimmo' else user['nome_completo']
    role_curr = user['role']
    
    # Cambio Password Obbligatorio
    if role_curr == 'user' and user.get('pwd_changed') == 0:
        st.warning("⚠️ Imposta la tua password personale.")
        st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
        with st.form("first_pwd_change"):
            p1 = st.text_input("Nuova Password", type="password")
            p2 = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("SALVA"):
                success = False
                if p1 and p1 == p2:
                    try:
                        supabase.table("users").update({"password": p1, "pwd_changed": 1}).eq("username", u_curr).execute()
                        success = True
                    except Exception as e: st.error(f"Errore: {e}")
                else: st.error("Le password non coincidono.")
                
                if success:
                    st.session_state.user = None
                    st.query_params.clear()
                    st.success("Password salvata. Rientra."); time.sleep(1.5); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ------------------------------------------------------------------
    # MENU ADMIN
    # ------------------------------------------------------------------
    if role_curr == 'admin':
        with st.sidebar:
            st.markdown(f"**Benvenuto, {name_display}**")
            st.divider()
            
            choice = st.radio("MENU", [
                "📢 Comunicazioni", 
                "📦 Materiali", 
                "👥 Risorse Umane", 
                "⚠️ Segnalazioni", 
                "🗺️ GPS Tracker", 
                "📊 Analisi Ore", 
                "🗓️ Presenze Mensili", 
                "🔐 Sicurezza"
            ])
            st.divider()
            if st.button("DISCONNETTI"): 
                st.session_state.user = None
                st.query_params.clear()
                st.rerun()

        if st.session_state.msg_feedback:
            st.success(st.session_state.msg_feedback); st.session_state.msg_feedback = None

        # --- ADMIN: BACHECA ---
        if choice == "📢 Comunicazioni":
            st.title("📢 Bacheca Aziendale")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1])
            titolo = c1.text_input("Titolo")
            users = get_all_staff()
            destinatari_sel = c2.multiselect("Per chi?", ["TUTTI"] + users, default=["TUTTI"])
            msg = st.text_area("Messaggio")
            durata = st.slider("Durata giorni:", 1, 60, 7)
            
            if st.button("PUBBLICA"):
                if titolo and msg:
                    dest_str = "TUTTI" if "TUTTI" in destinatari_sel else ",".join(destinatari_sel)
                    scad = datetime.now() + timedelta(days=durata)
                    supabase.table("bacheca").insert({
                        "titolo": titolo, "messaggio": msg, "destinatario": dest_str,
                        "data_pubblicazione": datetime.now().isoformat(),
                        "data_scadenza": scad.isoformat()
                    }).execute()
                    st.success("Fatto!"); time.sleep(0.5); st.rerun()
                else: st.error("Manca testo.")
            
            st.divider()
            df_b = get_df("bacheca")
            if not df_b.empty:
                df_b['data_scadenza'] = pd.to_datetime(df_b['data_scadenza'])
                df_b = df_b[df_b['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                for _, a in df_b.iterrows():
                    c_txt, c_btn = st.columns([4, 1])
                    c_txt.info(f"**{a['titolo']}** ({a['destinatario']}): {a['messaggio']}")
                    if c_btn.button("🗑️", key=f"del_b_{a['id']}"): 
                        supabase.table("bacheca").delete().eq("id", a['id']).execute()
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: MATERIALI ---
        elif choice == "📦 Materiali":
            st.title("📦 Gestione Materiali")
            supabase.table("material_requests").update({"visto": 1}).eq("visto", 0).execute()
            
            t1, t2 = st.tabs(["DA EVADERE", "STORICO"])
            with t1:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                df_reqs = get_df("material_requests")
                if not df_reqs.empty:
                    df_pending = df_reqs[df_reqs['status'] == 'PENDING'].sort_values('request_date', ascending=False)
                    if df_pending.empty: st.info("Tutto pulito! Nessuna richiesta.")
                    
                    for _, r in df_pending.iterrows():
                        with st.container():
                            st.write(f"👷 **{r['username'].upper()}** @ 📍 {r['location']}")
                            st.caption(f"Richiesto il: {r['request_date'][:10]}")
                            st.text_area("Lista:", r['item_list'], disabled=True, key=f"txt_{r['id']}")
                            
                            if st.button("✅ CONFERMA FORNITURA", key=f"mat_ok_{r['id']}"):
                                # Aggiunge data fornitura
                                data_fornitura = datetime.now().strftime("%d/%m/%Y %H:%M")
                                new_text = f"{r['item_list']}\n\n[✅ FORNITO IL: {data_fornitura}]"
                                supabase.table("material_requests").update({
                                    "status": "ARCHIVED",
                                    "item_list": new_text
                                }).eq("id", r['id']).execute()
                                st.rerun()
                            st.divider()
                else: st.info("Database vuoto.")
                st.markdown("</div>", unsafe_allow_html=True)
            with t2:
                df_reqs = get_df("material_requests")
                if not df_reqs.empty:
                    df_arch = df_reqs[df_reqs['status'] == 'ARCHIVED'].sort_values('request_date', ascending=False)
                    st.dataframe(df_arch[['request_date', 'username', 'location', 'item_list']], use_container_width=True)

        # --- ADMIN: RISORSE UMANE ---
        elif choice == "👥 Risorse Umane":
            st.title("👥 Risorse Umane & Cantieri")
            tab_res, tab_loc, tab_ass = st.tabs(["➕ Dipendenti", "🏗️ Cantieri", "🔗 Assegnazioni"])
            
            with tab_res:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                nu = c1.text_input("Username")
                nn = c2.text_input("Nome Completo")
                if st.button("REGISTRA UTENTE"):
                    try:
                        supabase.table("users").insert({"username": nu.lower(), "password": "1234", "role": "user", "nome_completo": nn}).execute()
                        st.success("Fatto!"); time.sleep(0.5); st.rerun()
                    except: st.error("Errore o utente esistente.")
                
                st.divider()
                users_list = get_all_staff()
                u_del = st.selectbox("Elimina Utente", ["..."] + users_list)
                if u_del != "..." and st.button("ELIMINA UTENTE SELEZIONATO"):
                    supabase.table("users").delete().eq("username", u_del).execute()
                    supabase.table("assignments").delete().eq("username", u_del).execute()
                    st.success("Cancellato."); time.sleep(0.5); st.rerun()
                
                st.dataframe(get_df("users"), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_loc:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                nl = st.text_input("Nuovo Cantiere")
                if st.button("AGGIUNGI CANTIERE"):
                    supabase.table("cantieri").insert({"nome_cantiere": nl, "attivo": 1}).execute()
                    st.success("Ok!"); time.sleep(0.5); st.rerun()
                
                st.divider()
                cantieri_list = get_all_cantieri()
                c_del = st.selectbox("Archivia Cantiere", ["..."] + cantieri_list)
                if c_del != "..." and st.button("ARCHIVIA (Nascondi)"):
                    # Soft Delete: attivo=0
                    supabase.table("cantieri").update({"attivo": 0}).eq("nome_cantiere", c_del).execute()
                    # Rimuove solo assegnazione futura
                    supabase.table("assignments").delete().eq("location", c_del).execute()
                    st.success("Archiviato."); time.sleep(0.5); st.rerun()
                
                st.dataframe(get_df("cantieri"), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_ass:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                su = st.selectbox("Utente", get_all_staff())
                df_ass = get_df("assignments")
                all_cantieri = get_all_cantieri()
                curr_ass = []
                if not df_ass.empty and 'username' in df_ass.columns:
                    curr_ass = df_ass[df_ass['username'] == su]['location'].tolist()
                    curr_ass = [c for c in curr_ass if c in all_cantieri]
                
                na = st.multiselect("Cantieri Autorizzati", all_cantieri, default=curr_ass)
                if st.button("SALVA ASSEGNAZIONI"):
                    supabase.table("assignments").delete().eq("username", su).execute()
                    if na: supabase.table("assignments").insert([{"username": su, "location": l} for l in na]).execute()
                    st.success("Salvato!"); time.sleep(0.5); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: SEGNALAZIONI ---
        elif choice == "⚠️ Segnalazioni":
            st.title("⚠️ Segnalazioni")
            supabase.table("issues").update({"visto": 1}).eq("visto", 0).execute()
            
            opt = st.radio("Filtro:", ["DA GESTIRE", "RISOLTE"], horizontal=True)
            df_iss = get_df("issues")
            
            if opt == "DA GESTIRE":
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'APERTA'].sort_values('timestamp', ascending=False)
                    for _, r in df_iss.iterrows():
                        st.markdown(f"<div class='stBlock'>📍 <strong>{r['location']}</strong> - 👷 {r['username']}<br><small>{r['timestamp'][:16]}</small><br><br>📝 {r['description']}</div>", unsafe_allow_html=True)
                        if r.get('image_url'): st.image(r['image_url'], width=300)
                        if st.button("✅ RISOLTO", key=f"s_{r['id']}"):
                            supabase.table("issues").update({"status": "RISOLTO"}).eq("id", r['id']).execute()
                            st.rerun()
            else:
                if not df_iss.empty:
                    df_iss = df_iss[df_iss['status'] == 'RISOLTO'].sort_values('timestamp', ascending=False)
                    st.dataframe(df_iss[['timestamp', 'location', 'username', 'description']], use_container_width=True)

        # --- ADMIN: GPS ---
        elif choice == "🗺️ GPS Tracker":
            st.title("🗺️ Mappa Attività")
            supabase.table("logs").update({"visto": 1}).eq("visto", 0).execute()
            
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Utente", ["TUTTI"] + get_all_staff())
            fl = c2.selectbox("Cantiere", ["TUTTE"] + get_all_cantieri())
            fd = c3.date_input("Data", value=datetime.now())
            
            df = get_df("logs")
            if not df.empty:
                df = df[df['gps_lat'] != 0]
                if fu != "TUTTI": df = df[df['username'] == fu]
                if fl != "TUTTE": df = df[df['location'] == fl]
                df['start_time'] = pd.to_datetime(df['start_time'])
                df = df[df['start_time'].dt.date == fd].sort_values('start_time', ascending=False)
                
                for _, r in df.iterrows():
                    ora_in = r['start_time'].strftime('%H:%M')
                    ora_out = pd.to_datetime(r['end_time']).strftime('%H:%M') if pd.notna(r['end_time']) else "IN CORSO"
                    
                    with st.expander(f"{r['username']} @ {r['location']} | {ora_in} - {ora_out}"):
                        c_a, c_b = st.columns(2)
                        
                        # INGRESSO
                        c_a.write("🟢 **INGRESSO**")
                        c_a.map(pd.DataFrame({'lat': [float(r['gps_lat'])], 'lon': [float(r['gps_lon'])]}), zoom=15)
                        # Link Google Maps
                        link_in = f"http://maps.google.com/?q={r['gps_lat']},{r['gps_lon']}"
                        c_a.markdown(f"<a href='{link_in}' target='_blank' class='map-link'>📍 APRI IN GOOGLE MAPS</a>", unsafe_allow_html=True)

                        # USCITA
                        if pd.notna(r['end_time']):
                            c_b.write("🔴 **USCITA**")
                            c_b.map(pd.DataFrame({'lat': [float(r['gps_lat_out'])], 'lon': [float(r['gps_lon_out'])]}), zoom=15)
                            link_out = f"http://maps.google.com/?q={r['gps_lat_out']},{r['gps_lon_out']}"
                            c_b.markdown(f"<a href='{link_out}' target='_blank' class='map-link'>📍 APRI IN GOOGLE MAPS</a>", unsafe_allow_html=True)
                        
                        if st.button("Elimina Record", key=f"del_log_{r['id']}"):
                            supabase.table("logs").delete().eq("id", r['id']).execute()
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: REPORT ORE ---
        elif choice == "📊 Analisi Ore":
            st.title("📊 Report Ore")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            mode = st.radio("Filtra per:", ["Mese", "Giorno"], horizontal=True)
            c1, c2, c3 = st.columns(3)
            fu = c1.selectbox("Dipendente", ["TUTTI"] + get_all_staff(), key="rep_u")
            fl = c2.selectbox("Cantiere", ["TUTTE"] + get_all_cantieri(), key="rep_l")
            
            df = get_df("logs")
            if not df.empty:
                df = df[pd.notna(df['end_time'])].copy()
                df['start_time'] = pd.to_datetime(df['start_time'])
                df['end_time'] = pd.to_datetime(df['end_time'])
                df['Ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                
                if mode == "Mese":
                    fm = c3.selectbox("Mese", df['start_time'].dt.strftime('%m-%Y').unique())
                    df = df[df['start_time'].dt.strftime('%m-%Y') == fm]
                else:
                    fd = c3.date_input("Giorno", value=datetime.now())
                    df = df[df['start_time'].dt.date == fd]
                
                if fu != "TUTTI": df = df[df['username'] == fu]
                if fl != "TUTTE": df = df[df['location'] == fl]
                
                st.dataframe(df[['username', 'location', 'start_time', 'end_time', 'Ore']], use_container_width=True)
                st.success(f"TOTALE ORE: {df['Ore'].sum():.2f}")
                
                # --- DOWNLOAD EXCEL ---
                c_xls, c_csv = st.columns(2)
                try:
                    df_xlsx = to_excel(df[['username', 'location', 'start_time', 'end_time', 'Ore']])
                    c_xls.download_button("📥 SCARICA EXCEL (.xlsx)", data=df_xlsx, file_name="report_ore.xlsx")
                except:
                    c_xls.warning("Excel non disp.")
                
                csv = df.to_csv(index=False).encode('utf-8')
                c_csv.download_button("📥 SCARICA CSV", data=csv, file_name="report.csv", mime='text/csv')

            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: MATRICE ---
        elif choice == "🗓️ Presenze Mensili":
            st.title("🗓️ Matrice Presenze")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            su = st.selectbox("Dipendente", get_all_staff(), key="mtr_u")
            df = get_df("logs")
            if not df.empty:
                df = df[(df['username'] == su) & (pd.notna(df['end_time']))].copy()
                if not df.empty:
                    df['start_time'] = pd.to_datetime(df['start_time'])
                    df['end_time'] = pd.to_datetime(df['end_time'])
                    df['Giorno'] = df['start_time'].dt.day
                    df['Mese'] = df['start_time'].dt.strftime('%m-%Y')
                    df['Ore'] = ((df['end_time'] - df['start_time']).dt.total_seconds() / 3600).round(2)
                    sm = st.selectbox("Seleziona Mese", df['Mese'].unique())
                    piv = df[df['Mese'] == sm].pivot_table(index='location', columns='Giorno', values='Ore', aggfunc='sum', fill_value=0)
                    piv['TOTALE'] = piv.sum(axis=1)
                    st.dataframe(piv, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # --- ADMIN: SICUREZZA ---
        elif choice == "🔐 Sicurezza":
            st.title("🔐 Sicurezza")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            nap = st.text_input("Cambia Password Admin", type="password")
            if st.button("AGGIORNA PASSWORD ADMIN"):
                supabase.table("users").update({"password": nap}).eq("username", "mimmo").execute()
                st.success("Fatto"); time.sleep(1); st.rerun()
            st.divider()
            ur = st.selectbox("Reset Password Dipendente", get_all_staff())
            if st.button("RESETTA A '1234'"):
                supabase.table("users").update({"password": "1234", "pwd_changed": 0}).eq("username", ur).execute()
                st.success("Resettata"); time.sleep(1); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # MENU DIPENDENTE
    # ------------------------------------------------------------------
    else:
        with st.sidebar:
            st.markdown(f"**Ciao, {name_display}**")
            st.divider()
            menu_emp = st.radio("NAVIGAZIONE", ["📢 Bacheca", "📦 Richieste", "📍 Timbratore"])
            st.divider()
            if st.button("DISCONNETTI"): 
                st.session_state.user = None
                st.query_params.clear()
                st.rerun()

        if menu_emp == "📢 Bacheca":
            st.title("📢 Comunicazioni")
            anns = get_df("bacheca")
            if not anns.empty:
                anns['data_scadenza'] = pd.to_datetime(anns['data_scadenza'])
                anns = anns[anns['data_scadenza'] > datetime.now()].sort_values('data_pubblicazione', ascending=False)
                found = False
                for _, m in anns.iterrows():
                    if "TUTTI" in str(m['destinatario']) or u_curr in str(m['destinatario']):
                        found = True
                        st.info(f"**{m['titolo']}**: {m['messaggio']}")
                if not found: st.info("Nessuna comunicazione.")
            else: st.info("Nessuna comunicazione.")

        elif menu_emp == "📦 Richieste":
            st.title("📦 Richiesta Materiali")
            st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
            with st.form("req_form"):
                df_ass = get_df("assignments")
                locs_avail = []
                if not df_ass.empty and 'username' in df_ass.columns:
                    locs_avail = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs_avail:
                    sel_loc = st.selectbox("Dove ti serve?", locs_avail)
                    txt_mat = st.text_area("Elenco materiale (es. 2 scope, 1 detergente...)", height=100)
                    if st.form_submit_button("INVIA RICHIESTA"):
                        if txt_mat:
                            supabase.table("material_requests").insert({
                                "username": u_curr, "location": sel_loc, "item_list": txt_mat,
                                "request_date": datetime.now().isoformat(), "status": "PENDING", "visto": 0
                            }).execute()
                            st.success("Inviata!"); time.sleep(1); st.rerun()
                        else: st.error("Inserisci il materiale.")
                else: st.warning("Non hai cantieri assegnati.")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.subheader("Storico richieste")
            df_m = get_df("material_requests")
            if not df_m.empty:
                my_reqs = df_m[df_m['username'] == u_curr].sort_values('request_date', ascending=False).head(5)
                for _, r in my_reqs.iterrows():
                    icon = "⏳" if r['status'] == 'PENDING' else "✅"
                    st.caption(f"{icon} {r['request_date'][:10]} - {r['location']}")
                    st.text(r['item_list'])
                    st.divider()

        elif menu_emp == "📍 Timbratore":
            st.title("📍 Gestione Turno")
            df_logs = get_df("logs")
            active = None
            if not df_logs.empty:
                active_logs = df_logs[(df_logs['username'] == u_curr) & (df_logs['end_time'].isna())]
                if not active_logs.empty: active = active_logs.iloc[0]

            if active is not None:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.success(f"TURNI ATTIVO: **{active['location']}**")
                st.write(f"Inizio: {pd.to_datetime(active['start_time']).strftime('%H:%M')}")
                st.write("---")
                loc_out = get_geolocation(component_key="out_geo")
                if st.button("🔴 TERMINA TURNO"):
                    if loc_out:
                        supabase.table("logs").update({
                            "end_time": datetime.now().isoformat(),
                            "gps_lat_out": loc_out['coords']['latitude'],
                            "gps_lon_out": loc_out['coords']['longitude'], "visto": 0
                        }).eq("id", active['id']).execute()
                        st.balloons(); time.sleep(1); st.rerun()
                    else: st.warning("Recupero GPS... Riprova.")
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.divider()
                # Checkbox Segnalazione (Richiesto)
                check_seg = st.checkbox("Vuoi segnalare un problema?")
                if check_seg:
                    st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                    d = st.text_area("Descrizione problema")
                    img_file = st.camera_input("Foto")
                    if st.button("INVIA SEGNALAZIONE"):
                        if d or img_file:
                            url = upload_photo(img_file)
                            supabase.table("issues").insert({
                                "username": u_curr, "description": d, "location": active['location'],
                                "timestamp": datetime.now().isoformat(), "status": "APERTA",
                                "image_url": url, "visto": 0
                            }).execute()
                            st.success("Inviata!"); time.sleep(1); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='stBlock'>", unsafe_allow_html=True)
                st.subheader("Inizia Turno")
                df_ass = get_df("assignments")
                locs = []
                if not df_ass.empty and 'username' in df_ass.columns:
                    locs = df_ass[df_ass['username'] == u_curr]['location'].tolist()
                
                if locs:
                    sl = st.selectbox("Seleziona Cantiere", locs)
                    lin = get_geolocation(component_key="in_geo")
                    if st.button("🟢 INIZIA LAVORO"):
                        if lin:
                            supabase.table("logs").insert({
                                "username": u_curr, "location": sl,
                                "start_time": datetime.now().isoformat(),
                                "gps_lat": lin['coords']['latitude'],
                                "gps_lon": lin['coords']['longitude'], "visto": 0
                            }).execute()
                            st.rerun()
                        else: st.warning("Attendi GPS...")
                else: st.warning("Nessun cantiere assegnato.")
                st.markdown("</div>", unsafe_allow_html=True)

# --- FINE PROGRAMMA ---
