import streamlit as st
import pandas as pd
import random
import requests
import os
import io
import json
import base64
import bcrypt
from datetime import datetime, timedelta
from fpdf import FPDF
from streamlit_option_menu import option_menu
import time
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="TalentPRO CRM", layout="wide", page_icon="🔒")

# --- 2. PUERTA TRASERA (BACKDOOR) ---
CLAVE_SECRETA = "TalentPro_2025"
query_params = st.query_params
usuario_es_super_admin = False

if "acceso" in query_params:
    if query_params["acceso"] == CLAVE_SECRETA:
        usuario_es_super_admin = True
        st.toast("🔓 Modo Super Admin: Menús Visibles")

# --- 3. ESTILOS CSS (DISEÑO TALENTPRO) ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafd; }
    .stMetric {background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 12px; box-shadow: 2px 2px 5px rgba(0,0,0,0.02);}
    div.stButton > button:first-child { background: linear-gradient(90deg, #5DADE2 0%, #003366 100%); color: white; border-radius: 10px; font-weight: bold;}
    [data-testid="stSidebar"] { padding-top: 0rem; }
    .admin-card { padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #003366;}
    
    /* Login Container */
    .login-container { background-color: white; padding: 3rem; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #e1e8ed; text-align: center; }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. FUNCIONES GITHUB (API)
# ==============================================================================
def github_get_json(url_key):
    try:
        url = st.secrets['github'][url_key]
        headers = {"Authorization": f"token {st.secrets['github']['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content), r.json()['sha']
        if "users" in url_key: return ({}, None)
        return ([], None) 
    except: return ([], None) if "users" not in url_key else ({}, None)

def github_push_json(url_key, data_dict, sha):
    try:
        url = st.secrets['github'][url_key]
        json_str = json.dumps(data_dict, indent=4, default=str)
        content_b64 = base64.b64encode(json_str.encode()).decode()
        payload = {"message": "Update DB from ERP", "content": content_b64}
        if sha: payload["sha"] = sha
        headers = {"Authorization": f"token {st.secrets['github']['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.put(url, headers=headers, json=payload)
        
        if r.status_code in [200, 201]:
            new_sha = r.json()['content']['sha']
            if 'leads' in url_key: st.session_state['leads_sha'] = new_sha
            elif 'cotizaciones' in url_key: st.session_state['cotizaciones_sha'] = new_sha
            elif 'usuarios' in url_key: st.session_state['users_sha'] = new_sha
            return True
        return False
    except: return False

def sync_users_after_update():
    users, sha = github_get_json('url_usuarios')
    st.session_state['users_db'] = users
    st.session_state['users_sha'] = sha

# ==============================================================================
# 5. INICIALIZACIÓN DE ESTADO
# ==============================================================================
if 'users_db' not in st.session_state:
    users, sha = github_get_json('url_usuarios')
    admin_email = st.secrets['auth']['admin_user']
    if not users or admin_email not in users:
        hashed = bcrypt.hashpw(st.secrets['auth']['admin_pass'].encode(), bcrypt.gensalt()).decode()
        users = {admin_email: {"name": "Super Admin", "role": "Super Admin", "password_hash": hashed}}
    if '_CONFIG_ORG' not in users: users['_CONFIG_ORG'] = {} 
    st.session_state['users_db'] = users
    st.session_state['users_sha'] = sha

if 'leads_db' not in st.session_state:
    leads, sha_l = github_get_json('url_leads')
    st.session_state['leads_db'] = leads if isinstance(leads, list) else []
    st.session_state['leads_sha'] = sha_l

if 'cotizaciones' not in st.session_state:
    cots, sha_c = github_get_json('url_cotizaciones')
    st.session_state['cotizaciones_sha'] = sha_c
    cols = ['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor', 'oc', 'factura', 'pago', 'hes', 'hes_num', 'items', 'pdf_data', 'idioma', 'equipo_asignado', 'factura_file']
    if cots and isinstance(cots, list):
        df = pd.DataFrame(cots)
        for c in cols:
            if c not in df.columns: 
                if c in ['items', 'pdf_data']: df[c] = None
                else: df[c] = ""
        st.session_state['cotizaciones'] = df
    else:
        st.session_state['cotizaciones'] = pd.DataFrame(columns=cols)

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
if 'cot_edit_data' not in st.session_state: st.session_state['cot_edit_data'] = None
if 'menu_idx' not in st.session_state: st.session_state['menu_idx'] = 0

# ==============================================================================
# 6. LOGIN & ASSETS
# ==============================================================================
LOGO_PATH = "logo_talentpro.jpg"
@st.cache_resource
def descargar_logo():
    url_logo = "https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg"
    if not os.path.exists(LOGO_PATH):
        try:
            r = requests.get(url_logo)
            if r.status_code == 200:
                with open(LOGO_PATH, 'wb') as f: f.write(r.content)
        except: pass
descargar_logo()

def login_page():
    st.markdown("""<div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); z-index: -1;"></div>""", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1.2,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
            st.markdown("<h4 style='color: #003366;'>CRM de Digitalización</h4>", unsafe_allow_html=True)
            with st.form("login_form"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("ACCEDER", use_container_width=True):
                    user = st.session_state['users_db'].get(u)
                    if user and bcrypt.checkpw(p.encode(), user.get('password_hash','').encode()):
                        st.session_state['auth_status'] = True
                        st.session_state['current_user'] = u
                        st.session_state['current_role'] = user.get('role', 'Comercial')
                        st.rerun()
                    else: st.error("⚠️ Usuario o clave incorrecta")
            st.markdown('</div>', unsafe_allow_html=True)

def logout(): st.session_state.clear(); st.rerun()

if not st.session_state['auth_status']: login_page(); st.stop()

# --- CARGA DE PRECIOS Y TASAS ---
@st.cache_data(ttl=60)
def cargar_precios():
    try:
        url = st.secrets["github"]["url_precios"]
        r = requests.get(url, headers={"Authorization": f"token {st.secrets['github']['token']}"})
        if r.status_code == 200:
            xls = pd.ExcelFile(io.BytesIO(r.content))
            def lh(n): return pd.read_excel(xls, n) if n in xls.sheet_names else pd.DataFrame()
            return (lh('Pruebas Int'), lh('Servicios Int'), lh('Config'), lh('Pruebas_CL'), lh('Servicios_CL'), lh('Pruebas_BR'), lh('Servicios_BR'))
        return None,None,None,None,None,None,None
    except: return None,None,None,None,None,None,None

data_precios = cargar_precios()
df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data_precios
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil"]

@st.cache_data(ttl=3600)
def obtener_indicadores():
    t = {"UF": 0, "USD_CLP": 0, "USD_BRL": 0}
    try: 
        resp = requests.get('https://mindicador.cl/api',timeout=2).json()
        t['UF'] = resp['uf']['valor']; t['USD_CLP'] = resp['dolar']['valor']
    except: pass
    try:
        resp_b = requests.get('https://open.er-api.com/v6/latest/USD', timeout=2).json()
        t['USD_BRL'] = resp_b['rates']['BRL']
    except: pass
    return t
TASAS = obtener_indicadores()

TEXTOS = {
    "ES": {"title": "Cotizador", "quote": "COTIZACIÓN", "invoice_to": "Facturar a:", "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Servicios", "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total", "subtotal": "Subtotal", "fee": "Fee Admin", "discount": "Descuento", "bank": "Bank Fee", "legal_intl": "Facturación a {pais}. +Impostos retenidos +Gastos OUR.", "noshow_title": "Política No-Show:", "noshow_text": "Multa 50% inasistencia <24h.", "validity": "Validez 30 días"},
    "PT": {"title": "Cotação", "quote": "COTAÇÃO", "invoice_to": "Faturar para:", "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Serviços", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total", "subtotal": "Subtotal", "fee": "Taxa Admin", "discount": "Desconto", "bank": "Taxa Bancária", "legal_intl": "Faturamento para {pais}. +Impostos retidos +Despesas OUR.", "noshow_title": "Política No-Show:", "noshow_text": "Multa de 50% por não comparecimento <24h.", "validity": "Validade 30 dias"},
    "EN": {"title": "Quotation", "quote": "QUOTATION", "invoice_to": "Bill to:", "client": "Client", "sec_prod": "Assessments", "sec_serv": "Services", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total", "subtotal": "Subtotal", "fee": "Admin Fee", "discount": "Discount", "bank": "Bank Fee", "legal_intl": "Billing to {pais}. +Withholding taxes +OUR expenses.", "noshow_title": "No-Show Policy:", "noshow_text": "50% fine for non-attendance <24h.", "validity": "Validity 30 days"}
}

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939 , Andar 8, Tamboré", "Giro": "Atividades de consultoria em gestión empresarial"},
    "Peru": {"Nombre": "TALENTPRO SOCIEDAD ANÓNIMA CERRADA", "ID": "RUC 20606246847", "Dir": "AVENIDA EL DERBY 254, LIMA", "Giro": "Servicios de apoyo a empresas"},
    "Chile_Pruebas": {"Nombre": "TALENTPRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630, Vitacura", "Giro": "Reclutamiento y Selección"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630, Vitacura", "Giro": "Asesoría en Recursos Humanos"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2-2022", "Dir": "CALLE 50, PANAMÁ", "Giro": "Talent Acquisition Services"}
}

# --- LÓGICA DE NEGOCIO Y PDF ---
def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "ds": df_s_cl, "tipo": "Loc"}
    if pais in ["Brasil", "Brazil"]: return {"mon": "R$", "dp": df_p_br, "ds": df_s_br, "tipo": "Loc"}
    fil = df_config[df_config['Pais'] == pais]
    return {"mon": "US$", "dp": df_p_usd, "ds": df_s_usd, "tipo": "Int", "niv": fil.iloc[0]['Nivel'] if not fil.empty else "Medio"}

def calc_paa(c, m):
    b = 1500 if c<=2 else 1200 if c<=5 else 1100
    if m == "US$": return b
    if m == "UF": return (b*TASAS['USD_CLP'])/TASAS['UF'] if TASAS['UF'] > 0 else 0
    return b*TASAS['USD_BRL']

def calc_xls(df, p, c, l):
    if df.empty: return 0.0
    r = df[df['Producto']==p]
    if r.empty: return 0.0
    ts = [50,100,200,300,500,1000,'Infinito'] if l else [100,200,300,500,1000,'Infinito']
    for t in ts:
        if c <= (float('inf') if t=='Infinito' else t):
            try: return float(r.iloc[0][t])
            except: return 0.0
    return 0.0

def get_impuestos(pais, sub, eva):
    if pais=="Chile": return "IVA (19%)", eva*0.19
    if pais in ["Panamá","Panama"]: return "ITBMS (7%)", sub*0.07
    if pais=="Honduras": return "Retención", sub*0.1111
    return "", 0

def get_empresa(pais, items):
    if pais=="Brasil": return EMPRESAS["Brasil"]
    if pais in ["Perú","Peru"]: return EMPRESAS["Peru"]
    if pais=="Chile": return EMPRESAS["Chile_Pruebas"] if any(i['Ítem']=='Evaluación' for i in items) else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

def clasificar_cliente(monto):
    if monto >= 20000: return "Grande"
    if 10000 <= monto < 20000: return "Mediano"
    if 5000 <= monto < 10000: return "Chico"
    return "Micro"

def get_user_teams_list(user_data):
    raw = user_data.get('equipo', [])
    if isinstance(raw, str): return [raw] if (raw and raw != "N/A") else []
    return raw

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102)
        self.cell(0, 15, getattr(self,'tit_doc','COTIZACIÓN'), 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, 'TalentPro Digital System', 0, 0, 'C')

def generar_pdf_final(emp, cli, items, calc, idioma_code, extras):
    T = TEXTOS.get(idioma_code, TEXTOS["ES"])
    pdf = PDF(); pdf.tit_doc=T['quote']; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0)
    pdf.set_text_color(100); pdf.cell(95,5,T['invoice_to'],0,1)
    pdf.set_font("Arial",'',9); pdf.set_text_color(50); y=pdf.get_y()
    pdf.cell(95,5,emp['ID'],0,1); pdf.multi_cell(90,5,emp['Dir']); pdf.cell(95,5,emp['Giro'],0,1)
    pdf.set_xy(105,y); pdf.set_font("Arial",'B',10); pdf.set_text_color(0); pdf.cell(95,5,cli['empresa'],0,1)
    pdf.set_xy(105,pdf.get_y()); pdf.set_font("Arial",'',9); pdf.set_text_color(50)
    pdf.cell(95,5,cli['contacto'],0,1); pdf.set_xy(105,pdf.get_y()); pdf.cell(95,5,cli['email'],0,1)
    pdf.ln(5); pdf.set_xy(105,pdf.get_y()); pdf.set_text_color(0,51,102)
    pdf.cell(95,5,f"Date: {datetime.now().strftime('%d/%m/%Y')} | ID: {extras['id']}",0,1); pdf.ln(10)
    pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.set_font("Arial",'B',9)
    pdf.cell(110,8,T['desc'],0,0,'L',1); pdf.cell(20,8,T['qty'],0,0,'C',1); pdf.cell(30,8,T['unit'],0,0,'R',1); pdf.cell(30,8,T['total'],0,1,'R',1)
    pdf.set_text_color(0); pdf.set_font("Arial",'',8); mon=items[0]['Moneda']
    for i in items:
        q=str(i['Det']).split('(')[0].replace('x','').strip()
        pdf.cell(110,7,f"  {i['Desc'][:60]}",'B',0,'L'); pdf.cell(20,7,q,'B',0,'C'); pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(5); x=120
    def r(l,v,b=False):
        pdf.set_x(x); pdf.set_font("Arial",'B' if b else '',10); pdf.set_text_color(0 if not b else 255)
        if b: pdf.set_fill_color(0,51,102)
        pdf.cell(35,7,l,0,0,'R',b); pdf.cell(35,7,f"{mon} {v:,.2f} ",0,1,'R',b)
    r(T['subtotal'], calc['subtotal'])
    if calc['fee']>0: r(T['fee'], calc['fee'])
    if calc['tax_val']>0: r(calc['tax_name'], calc['tax_val'])
    if extras.get('bank',0)>0: r(T['bank'], extras['bank'])
    lbl_dsc = extras.get('desc_name') if extras.get('desc_name') else T['discount']
    if extras.get('desc',0)>0: r(lbl_dsc, -extras['desc'])
    pdf.ln(1); r(T['total'].upper(), calc['total'], True); pdf.ln(10)
    pdf.set_font("Arial",'I',8); pdf.set_text_color(80)
    if emp['Nombre']==EMPRESAS['Latam']['Nombre']: pdf.multi_cell(0,4,T['legal_intl'].format(pais=extras['pais']),0,'L'); pdf.ln(3)
    if any(any(tr in i['Desc'].lower() for tr in ['feedback','coaching','entrevista']) for i in items):
        pdf.set_font("Arial",'B',8); pdf.cell(0,4,T['noshow_title'],0,1); pdf.set_font("Arial",'',8); pdf.multi_cell(0,4,T['noshow_text'],0,'L'); pdf.ln(3)
    pdf.set_text_color(100); pdf.cell(0,5,T['validity'],0,1)
    return pdf.output(dest='S').encode('latin-1')

def lluvia_dolares():
    st.markdown("""<style>@keyframes fall {0% { transform: translateY(-10vh); opacity: 1; }100% { transform: translateY(110vh); opacity: 0; }}.money-rain {position: fixed; top: 0; font-size: 2.5rem; animation: fall linear forwards; z-index: 99999; pointer-events: none;}</style>""", unsafe_allow_html=True)
    html = "".join([f'<div class="money-rain" style="left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,2)}s; animation-duration:{random.uniform(2,4)}s;">💲</div>' for _ in range(40)])
    st.markdown(html, unsafe_allow_html=True)

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================
def modulo_crm():
    st.title("📇 Prospectos y Clientes")
    tab1, tab2, tab_import = st.tabs(["📋 Gestión de Leads", "🏢 Cartera Clientes", "📥 Importar Masivo"])
    with tab1:
        with st.expander("➕ Nuevo Lead", expanded=False):
            with st.form("form_lead"):
                st.subheader("1. Datos Generales")
                c1, c2, c3 = st.columns(3)
                nom_cliente = c1.text_input("Cliente / Empresa"); area = c2.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"]); pais = c3.selectbox("País", TODOS_LOS_PAISES)
                c1, c2, c3 = st.columns(3)
                ind = c1.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"]); web = c2.text_input("Web"); idioma = c3.selectbox("Idioma", ["ES", "EN", "PT"])
                st.subheader("2. Contactos Clave")
                contacts_data = []
                for i in range(1, 4):
                    c1, c2, c3 = st.columns(3); n = c1.text_input(f"Nombre {i}", key=f"n{i}"); m = c2.text_input(f"Mail {i}", key=f"m{i}"); t = c3.text_input(f"Tel {i}", key=f"t{i}")
                    if n: contacts_data.append(f"{n} ({m})")
                st.subheader("3. Seguimiento")
                c1, c2 = st.columns(2); origen = c1.selectbox("Origen", ["SHL", "KAM TalentPRO", "Prospección del Usuario"]); etapa = c2.selectbox("Etapa Inicial", ["Prospección", "Contacto", "Reunión", "Propuesta"])
                expectativa = st.text_area("Expectativa / Dolor Principal")
                if st.form_submit_button("Guardar Lead"):
                    str_contactos = ", ".join(contacts_data)
                    new_lead = {"id": int(time.time()), "Cliente": nom_cliente, "Area": area, "Pais": pais, "Industria": ind, "Web": web, "Contactos": str_contactos, "Origen": origen, "Etapa": etapa, "Expectativa": expectativa, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())}
                    new_db = st.session_state['leads_db'] + [new_lead]
                    if github_push_json('url_leads', new_db, st.session_state.get('leads_sha')):
                        st.session_state['leads_db'] = new_db; st.success("Lead guardado correctamente."); time.sleep(1); st.rerun()
        st.divider(); st.subheader("🖊️ Gestionar / Editar Lead")
        visible_leads = [l for l in st.session_state['leads_db'] if l.get('Etapa') not in ['Cliente Activo', 'Cerrado Ganado'] and l.get('Area') != 'Cartera']
        if visible_leads:
            lead_names = [l.get('Cliente', 'Sin Nombre') for l in visible_leads]
            sel_lead_name = st.selectbox("Seleccionar Lead para gestionar", [""] + sorted(list(set(lead_names))))
            if sel_lead_name:
                lead_idx = next((i for i, d in enumerate(st.session_state['leads_db']) if d["Cliente"] == sel_lead_name), None)
                if lead_idx is not None:
                    lead_data = st.session_state['leads_db'][lead_idx]
                    col_edit, col_info = st.columns([1, 1])
                    with col_edit:
                        st.markdown("##### 📝 Editar Información")
                        with st.form(f"edit_lead_{lead_idx}"):
                            e_contacts = st.text_area("Contactos", value=lead_data.get('Contactos', ''))
                            e_etapa = st.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"], index=0)
                            e_expectativa = st.text_area("Expectativa / Dolor", value=lead_data.get('Expectativa', ''))
                            e_web = st.text_input("Web", value=lead_data.get('Web', ''))
                            if st.form_submit_button("💾 Guardar Cambios"):
                                st.session_state['leads_db'][lead_idx].update({'Contactos': e_contacts, 'Etapa': e_etapa, 'Expectativa': e_expectativa, 'Web': e_web})
                                github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                                st.success("Lead actualizado."); time.sleep(1); st.rerun()
                    with col_info:
                        st.markdown(f"##### 📂 Historial de {sel_lead_name}")
                        df_cots = st.session_state['cotizaciones']
                        cots_lead = df_cots[df_cots['empresa'] == sel_lead_name]
                        if not cots_lead.empty: st.dataframe(cots_lead[['fecha', 'id', 'total', 'estado', 'vendedor']], use_container_width=True, hide_index=True)
                        st.divider(); st.markdown("##### 📎 Propuesta Comercial")
                        if 'propuesta_file' in lead_data and lead_data['propuesta_file']:
                            st.download_button(label="📥 Descargar Propuesta", data=base64.b64decode(lead_data['propuesta_file']), file_name=f"Propuesta_{sel_lead_name}.pdf", mime="application/pdf")
                        uploaded_propuesta = st.file_uploader("Subir/Actualizar PDF Propuesta", type=['pdf'], key=f"up_{lead_idx}")
                        if uploaded_propuesta is not None and st.button("Guardar Archivo"):
                            st.session_state['leads_db'][lead_idx]['propuesta_file'] = base64.b64encode(uploaded_propuesta.read()).decode()
                            github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                            st.success("Propuesta subida."); time.sleep(1); st.rerun()
            st.dataframe(pd.DataFrame(visible_leads), use_container_width=True)

    with tab2:
        with st.expander("➕ Registrar Cliente Existente", expanded=False):
             with st.form("form_existing_client"):
                 ec1, ec2 = st.columns(2); e_name = ec1.text_input("Nombre Empresa"); e_pais = ec2.selectbox("País Origen", TODOS_LOS_PAISES, key="epais")
                 ec3, ec4 = st.columns(2); e_ind = ec3.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Otros"], key="eind"); e_cont = ec4.text_input("Contacto Principal")
                 if st.form_submit_button("Guardar Cliente en Cartera"):
                     exist_client = {"id": int(time.time()), "Cliente": e_name, "Area": "Cartera", "Pais": e_pais, "Industria": e_ind, "Web": "", "Contactos": e_cont, "Origen": "Base Histórica", "Etapa": "Cliente Activo", "Expectativa": "Cliente Recurrente", "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())}
                     st.session_state['leads_db'].append(exist_client)
                     github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                     st.success(f"Cliente {e_name} agregado."); time.sleep(1); st.rerun()
        
        leads_db = st.session_state['leads_db']
        clients_list = sorted(list(set([l['Cliente'] for l in leads_db if l.get('Etapa') in ['Cliente Activo', 'Cerrado Ganado'] or l.get('Area') == 'Cartera'] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        sel = st.selectbox("Ver Cliente 360", [""] + clients_list)
        if sel:
            df = st.session_state['cotizaciones']; dfc = df[df['empresa']==sel]
            tot = dfc['total'].sum(); fac_cli = dfc[dfc['estado']=='Facturada']['total'].sum(); pag_cli = dfc[(dfc['estado']=='Facturada') & (dfc['pago']=='Pagada')]['total'].sum()
            st.markdown(f"### 🏢 {sel}")
            c1,c2,c3,c4 = st.columns(4); c1.metric("Total Cotizado", f"${tot:,.0f}"); c2.metric("Total Facturado", f"${fac_cli:,.0f}"); c3.metric("Total Pagado", f"${pag_cli:,.0f}"); c4.metric("# Cotizaciones", len(dfc))
            client_idx = next((i for i, l in enumerate(st.session_state['leads_db']) if l['Cliente'] == sel), None)
            if client_idx is not None:
                with st.expander("⚙️ Editar Datos del Cliente"):
                    with st.form(f"f_edit_cli_{client_idx}"):
                        c_data = st.session_state['leads_db'][client_idx]
                        new_ind = st.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Otros"], index=0); new_web = st.text_input("Web", value=c_data.get('Web', '')); new_cont = st.text_area("Contactos", value=c_data.get('Contactos', ''))
                        if st.form_submit_button("Actualizar"):
                            st.session_state['leads_db'][client_idx].update({'Industria': new_ind, 'Web': new_web, 'Contactos': new_cont})
                            github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                            st.success("Actualizado"); time.sleep(1); st.rerun()
            st.dataframe(dfc[['fecha','id','pais','total','estado','factura','pago']], use_container_width=True)

    with tab_import:
        st.subheader("Carga Masiva de Leads (CSV)")
        uploaded_file = st.file_uploader("Subir CSV", type=["csv"])
        if uploaded_file is not None and st.button("Procesar Importación"):
            df_up = pd.read_csv(uploaded_file, sep=None, engine='python')
            for _, row in df_up.iterrows():
                st.session_state['leads_db'].append({"id": int(time.time())+random.randint(1,999), "Cliente": row.get('Cliente', 'S/N'), "Area": row.get('Area', 'Importado'), "Pais": row.get('Pais', 'Chile'), "Etapa": row.get('Etapa', 'Prospección'), "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())})
            github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
            st.success("Importados correctamente."); time.sleep(1); st.rerun()

def modulo_cotizador():
    edit_data = st.session_state.get('cot_edit_data')
    if edit_data: st.info(f"✏️ MODO EDICIÓN: ID: {edit_data.get('id_orig')} - {edit_data.get('empresa')}")
    if st.button("❌ Limpiar y Salir", type="secondary"): st.session_state['carrito'] = []; st.session_state['cot_edit_data'] = None; st.rerun()

    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES", "PT", "EN"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    c1,c2,c3,c4 = st.columns(4); c1.metric("UF", f"${TASAS['UF']:,.0f}"); c2.metric("USD", f"${TASAS['USD_CLP']:,.0f}"); c3.metric("BRL", f"{TASAS['USD_BRL']:.2f}")
    
    ps = st.selectbox("🌎 País", TODOS_LOS_PAISES, index=0); ctx = obtener_contexto(ps)
    cc1,cc2,cc3,cc4 = st.columns(4)
    curr_user_data = st.session_state['users_db'].get(st.session_state['current_user'], {})
    user_teams = get_user_teams_list(curr_user_data)
    sel_team_cot = cc4.selectbox("Célula", user_teams) if len(user_teams) > 1 else user_teams[0] if user_teams else "N/A"
    
    clientes_list = sorted(list(set([x['Cliente'] for x in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
    use_new_client = cc1.checkbox("¿Cliente Nuevo?", value=False)
    emp = cc1.text_input(txt['client'], value=edit_data.get('empresa','') if edit_data else "") if use_new_client else cc1.selectbox(txt['client'], [""] + clientes_list)
    con = cc2.text_input("Contacto", value=edit_data.get('contacto','') if edit_data else ""); ema = cc3.text_input("Email", value=edit_data.get('email','') if edit_data else "")
    ven = st.session_state['users_db'][st.session_state['current_user']].get('name','')

    tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4 = st.columns([3,1,1,1]); lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp,key="p1"); qp=c2.number_input("Cant",1,10000,10,key="q1")
            cant_ya = sum(int(str(item['Det']).replace('x', '').strip()) for item in st.session_state['carrito'] if item['Ítem'] == 'Evaluación')
            vol_tot = cant_ya + qp; up = calc_xls(ctx['dp'], sp, vol_tot, ctx['tipo']=='Loc')
            c3.metric("Unit", f"{up:,.2f}")
            if c4.button("Add", key="b1"): 
                st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
                for i, item in enumerate(st.session_state['carrito']):
                    if item['Ítem'] == 'Evaluación':
                        n_up = calc_xls(ctx['dp'], item['Desc'], vol_tot, ctx['tipo']=='Loc')
                        st.session_state['carrito'][i].update({"Unit": n_up, "Total": n_up * int(str(item['Det']).replace('x',''))})
                st.rerun()
    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        if ls:
            ss=c1.selectbox("Serv",["Certificación PAA"]+ls,key="s1")
            if "PAA" in ss: qs=c2.number_input("Pers",1,100,1); us=calc_paa(qs,ctx['mon']); dt=f"{qs} pers"
            else: r,q=c2.columns(2); cs=ctx['ds'].columns.tolist(); rol=r.selectbox("Rol",[x for x in ['Senior','BM','BP'] if x in cs]); qs=q.number_input("Cant",1,100,1); rw=ctx['ds'][(ctx['ds']['Servicio']==ss)]; us=float(rw.iloc[0][rol]) if not rw.empty else 0; dt=f"{rol} ({qs})"
            c3.metric("Unit",f"{us:,.2f}")
            if c4.button("Add",key="b2"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        df_cart = pd.DataFrame(st.session_state['carrito']); edited = st.data_editor(df_cart, use_container_width=True, num_rows="dynamic"); st.session_state['carrito'] = edited.to_dict('records')
        sub = sum(item['Total'] for item in st.session_state['carrito']); eva = sum(item['Total'] for item in st.session_state['carrito'] if item['Ítem']=='Evaluación')
        cR = st.columns([3,1])[1]; fee=cR.checkbox("Fee 10%", value=False); bnk=cR.number_input("Bank Fee", 0.0)
        dsc_name = cR.text_input("Glosa Descuento", "Descuento"); td = cR.selectbox("Tipo Descuento", ["Monto Fijo", "Porcentaje", "Simular Volumen"]); dsc = 0.0
        if td == "Monto Fijo": dsc = cR.number_input("Monto", 0.0)
        elif td == "Porcentaje": pct = cR.number_input("%", 0.0, 100.0, 0.0); dsc = sub * (pct/100)
        else: vs = cR.number_input("Volumen", 1000); sim_tot = sum(int(str(i['Det']).replace('x',''))*calc_xls(ctx['dp'], i['Desc'], vs, ctx['tipo']=='Loc') for i in st.session_state['carrito'] if i['Ítem']=='Evaluación'); dsc = eva - sim_tot
        vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-max(dsc,0); st.metric("TOTAL",f"{ctx['mon']} {fin:,.2f}")
        if st.button("GUARDAR", type="primary"):
            nid = edit_data['id_orig'] if edit_data else f"TP-{random.randint(1000,9999)}"
            row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':ven, 'equipo_asignado': sel_team_cot, 'items': st.session_state['carrito'], 'pdf_data': {'fee':vfee,'bank':bnk,'desc':dsc,'desc_name':dsc_name, 'pais':ps,'id':nid}, 'idioma': idi}
            df = st.session_state['cotizaciones']
            if edit_data: df.loc[df['id']==nid, row.keys()] = row.values()
            else: st.session_state['cotizaciones'] = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
            st.success("Ok"); st.session_state['carrito']=[]; st.session_state['cot_edit_data'] = None; time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("Sin datos."); return
    df = df.sort_values('fecha', ascending=False)
    for i, r in df.iterrows():
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['moneda']} {r['total']:,.0f}"):
            c1,c2,c3 = st.columns([2,2,1]); ns = c1.selectbox("Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida"], key=f"s_{r['id']}"); hes = c2.checkbox("HES", value=r.get('hes', False), key=f"h_{r['id']}")
            if c3.button("Actualizar", key=f"b_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = ns; st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                if ns == 'Aprobada': st.balloons()
                st.success("Ok"); st.rerun()
            if c3.button("✏️ Editar", key=f"e_{r['id']}"):
                st.session_state['carrito'] = r['items']; st.session_state['cot_edit_data'] = {'id_orig': r['id'], 'empresa': r['empresa'], 'pais': r['pais']}
                st.session_state['menu_idx'] = 3; st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera")
    df = st.session_state['cotizaciones']
    t1, t2 = st.tabs(["📝 Backlog", "💵 Historial"])
    with t1:
        pend = df[df['estado'] == 'Aprobada']
        for i, r in pend.iterrows():
            with st.container(border=True):
                st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']:,.0f}")
                if r.get('hes'): st.error("🚨 Requiere HES")
                up = st.file_uploader("Factura PDF", type=['pdf'], key=f"i_{r['id']}")
                c1,c2,c3 = st.columns(3); oc = c1.text_input("OC", key=f"oc_{r['id']}"); hes_n = c2.text_input("N° HES", key=f"hn_{r['id']}"); inv = c3.text_input("N° Factura", key=f"f_{r['id']}")
                if st.button("Emitir Factura", key=f"eb_{r['id']}"):
                    if inv:
                        st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'; st.session_state['cotizaciones'].at[i, 'factura'] = inv; st.session_state['cotizaciones'].at[i, 'oc'] = oc; st.session_state['cotizaciones'].at[i, 'hes_num'] = hes_n
                        if up: st.session_state['cotizaciones'].at[i, 'factura_file'] = base64.b64encode(up.read()).decode()
                        github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                        lluvia_dolares(); st.success("Facturado"); time.sleep(2); st.rerun()
    with t2:
        billed = df[df['estado'] == 'Facturada']
        st.dataframe(billed[['fecha','id','empresa','total','factura','pago']], use_container_width=True)

def convert_to_usd(row):
    m = row['moneda']; v = row['total']
    if m == 'US$': return v
    if m == 'UF': return (v * TASAS['UF']) / TASAS['USD_CLP'] if TASAS['USD_CLP'] > 0 else 0
    if m == 'R$': return v / TASAS['USD_BRL'] if TASAS['USD_BRL'] > 0 else 0
    return 0

def modulo_dashboard():
    st.title("📊 Dashboards & Analytics")
    df_cots = st.session_state['cotizaciones'].copy()
    if not df_cots.empty:
        df_cots['fecha_dt'] = pd.to_datetime(df_cots['fecha'], errors='coerce')
        df_cots = df_cots.dropna(subset=['fecha_dt'])
        df_cots['Año'] = df_cots['fecha_dt'].dt.year
    
    st.sidebar.subheader("Filtros Dashboard")
    all_years = sorted(df_cots['Año'].unique().tolist()) if not df_cots.empty else [datetime.now().year]
    selected_years = st.sidebar.multiselect("Años", all_years, default=[max(all_years)])
    
    tab1, tab2, tab3 = st.tabs(["📊 General", "🎯 Metas y Desempeño", "📇 Leads"])
    with tab1:
        df_f = df_cots[df_cots['Año'].isin(selected_years)] if not df_cots.empty else pd.DataFrame()
        c1,c2,c3 = st.columns(3); c1.metric("Leads Totales", len(st.session_state['leads_db']))
        if not df_f.empty:
            df_f['Total_USD'] = df_f.apply(convert_to_usd, axis=1)
            c2.metric("Facturado USD", f"${df_f[df_f['estado']=='Facturada']['Total_USD'].sum():,.0f}"); c3.metric("Cotizado USD", f"${df_f['Total_USD'].sum():,.0f}")
            fig = px.pie(df_f, names='estado', title="Pipeline"); st.plotly_chart(fig, use_container_width=True)

    with tab2:
        user_data = st.session_state['users_db'].get(st.session_state['current_user'], {})
        st.subheader(f"Desempeño: {user_data.get('name','')}")
        u_metas = user_data.get('metas_anuales', {})
        total_meta = sum(float(u_metas.get(str(y), {}).get('rev', 0)) for y in selected_years)
        df_user = df_f[df_f['vendedor'] == user_data.get('name','')] if not df_f.empty else pd.DataFrame()
        user_rev = df_user[df_user['estado']=='Facturada']['Total_USD'].sum() if not df_user.empty else 0
        if total_meta > 0: st.progress(min(user_rev/total_meta, 1.0), text=f"Progreso Meta: {user_rev/total_meta*100:.1f}%")
        else: st.info("Sin meta anual cargada.")

def modulo_admin():
    st.title("👥 Administración TalentPRO")
    users = st.session_state['users_db']
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚙️ Usuarios", "➕ Nuevo", "🏢 Estructura", "🔥 RESET", "📥 Importar"])
    with tab1:
        df_u = pd.DataFrame([{"Email": k, "Nombre": v.get('name'), "Rol": v.get('role'), "Equipos": v.get('equipo')} for k, v in users.items() if not k.startswith("_")])
        st.dataframe(df_u, use_container_width=True)
        sel_u = st.selectbox("Usuario a Editar", df_u['Email'].tolist() if not df_u.empty else [])
        if sel_u:
            with st.form("edit_user"):
                u = users[sel_u]; year = st.number_input("Año Meta", 2024, 2030, 2025)
                m_rev = st.number_input("Meta Facturación USD", value=float(u.get('metas_anuales',{}).get(str(year),{}).get('rev',0)))
                if st.form_submit_button("Guardar"):
                    if 'metas_anuales' not in users[sel_u]: users[sel_u]['metas_anuales'] = {}
                    users[sel_u]['metas_anuales'][str(year)] = {'rev': m_rev}
                    github_push_json('url_usuarios', users, st.session_state['users_sha']); st.success("Ok")
    with tab2:
        with st.form("new_u"):
            ne = st.text_input("Email"); nn = st.text_input("Nombre"); nr = st.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"]); np = st.text_input("Password", type="password")
            if st.form_submit_button("Crear"):
                users[ne] = {"name": nn, "role": nr, "password_hash": bcrypt.hashpw(np.encode(), bcrypt.gensalt()).decode(), "equipo": []}
                github_push_json('url_usuarios', users, st.session_state['users_sha']); st.success("Creado"); st.rerun()
    with tab3:
        st.subheader("Configuración de Células")
        config = users.get('_CONFIG_ORG', {})
        with st.form("new_team"):
            nt = st.text_input("Nombre Célula")
            if st.form_submit_button("Añadir"):
                config[nt] = {'metas_anuales': {}, 'subs': {}}
                users['_CONFIG_ORG'] = config
                github_push_json('url_usuarios', users, st.session_state['users_sha']); st.rerun()
        for t, d in config.items():
            with st.expander(f"Célula: {t}"):
                y_meta = st.number_input(f"Meta USD {t}", key=f"m_{t}")
                if st.button(f"Guardar Meta {t}"):
                    d['metas_anuales']['2025'] = y_meta
                    users['_CONFIG_ORG'] = config; github_push_json('url_usuarios', users, st.session_state['users_sha']); st.rerun()
    with tab4:
        st.error("⚠️ Zona de Reset de Datos")
        if st.text_input("Escriba CONFIRMAR") == "CONFIRMAR":
            if st.button("RESET COTIZACIONES"):
                github_push_json('url_cotizaciones', [], st.session_state['cotizaciones_sha']); st.rerun()
    with tab5:
        st.info("Importar usuarios vía CSV (email, nombre, rol, password)")

# ==============================================================================
# 10. NAVEGACIÓN DUAL (RESPONSIVE)
# ==============================================================================
role = st.session_state.get('current_role', 'Comercial')
opts = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas"]
icos = ['bar-chart', 'check', 'person', 'file', 'currency-dollar']
if role == "Super Admin": opts.append("Usuarios"); icos.append("people")

# A) MENÚ DESPLEGABLE SUPERIOR (Visible en cualquier ancho)
st.markdown("### 🧭 Navegación Principal")
selected_nav = st.selectbox("Ir a módulo:", opts, index=st.session_state['menu_idx'], label_visibility="collapsed")

# B) SIDEBAR (Standard Desktop)
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    st.markdown("---")
    selected_side = option_menu("Menú Lateral", opts, icons=icos, default_index=st.session_state['menu_idx'], key='side_nav')
    if st.button("Log Out"): logout()

# Sincronización
if selected_nav != opts[st.session_state['menu_idx']]:
    st.session_state['menu_idx'] = opts.index(selected_nav); st.rerun()
elif selected_side != opts[st.session_state['menu_idx']]:
    st.session_state['menu_idx'] = opts.index(selected_side); st.rerun()

# RENDERIZADO
menu = opts[st.session_state['menu_idx']]
if menu == "Dashboards": modulo_dashboard()
elif menu == "Seguimiento": modulo_seguimiento()
elif menu == "Prospectos y Clientes": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Usuarios": modulo_admin()
