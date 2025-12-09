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

# --- 3. ESTILOS CSS ---
st.markdown("""
    <style>
    .stMetric {background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}
    div.stButton > button:first-child { background-color: #003366; color: white; border-radius: 8px; font-weight: bold;}
    [data-testid="stSidebar"] { padding-top: 0rem; }
    </style>
""", unsafe_allow_html=True)

if not usuario_es_super_admin:
    hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """
    st.markdown(hide_menu_style, unsafe_allow_html=True)

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
        return r.status_code in [200, 201]
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
    
    if '_CONFIG_ORG' not in users:
        users['_CONFIG_ORG'] = {} 
        
    st.session_state['users_db'] = users
    st.session_state['users_sha'] = sha

if 'leads_db' not in st.session_state:
    leads, sha_l = github_get_json('url_leads')
    st.session_state['leads_db'] = leads if isinstance(leads, list) else []
    st.session_state['leads_sha'] = sha_l

if 'cotizaciones' not in st.session_state:
    cots, sha_c = github_get_json('url_cotizaciones')
    st.session_state['cotizaciones_sha'] = sha_c
    cols = ['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor', 'oc', 'factura', 'pago', 'hes', 'hes_num', 'items', 'pdf_data', 'idioma', 'equipo_asignado']
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

# ==============================================================================
# 6. LOGIN & DATOS EXTERNOS
# ==============================================================================
LOGO_PATH = "logo_talentpro.jpg"
@st.cache_resource
def descargar_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            r = requests.get("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg")
            if r.status_code == 200:
                with open(LOGO_PATH, 'wb') as f: f.write(r.content)
        except: pass
descargar_logo()

def login_page():
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=300)
        st.markdown("### Acceso Seguro ERP")
        with st.form("login_form"):
            u = st.text_input("Usuario", key="login_user")
            p = st.text_input("Contraseña", type="password", key="login_pass")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            if submit:
                if u.startswith("_"): st.error("Usuario no válido")
                else:
                    user = st.session_state['users_db'].get(u)
                    if user and 'password_hash' in user:
                        try:
                            stored_hash = user.get('password_hash', '')
                            if bcrypt.checkpw(p.encode(), stored_hash.encode()):
                                st.session_state['auth_status'] = True
                                st.session_state['current_user'] = u
                                st.session_state['current_role'] = user.get('role', 'Comercial')
                                st.success("Acceso Correcto"); time.sleep(0.2); st.rerun()
                            else: st.error("⚠️ Contraseña incorrecta")
                        except Exception as e: st.error(f"Error de validación")
                    else: st.error("⚠️ Usuario no encontrado")

def logout(): st.session_state.clear(); st.rerun()

if not st.session_state['auth_status']: login_page(); st.stop()

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
if not data_precios or data_precios[0] is None: st.error("Error Precios"); st.stop()
df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data_precios
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil"]

@st.cache_data(ttl=3600)
def obtener_indicadores():
    t = {"UF": 0, "USD_CLP": 0, "USD_BRL": 0}
    try: 
        resp = requests.get('https://mindicador.cl/api',timeout=2).json()
        t['UF'] = resp['uf']['valor']
        t['USD_CLP'] = resp['dolar']['valor']
    except: pass
    try:
        resp_b = requests.get('https://open.er-api.com/v6/latest/USD', timeout=2).json()
        t['USD_BRL'] = resp_b['rates']['BRL']
    except: pass
    return t
TASAS = obtener_indicadores()

TEXTOS = {
    "ES": {
        "title": "Cotizador", "quote": "COTIZACIÓN", "invoice_to": "Facturar a:",
        "client": "Cliente", "sec_prod": "Licencias", "sec_serv": "Servicios",
        "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total",
        "subtotal": "Subtotal", "fee": "Fee Admin", "discount": "Descuento", "bank": "Bank Fee",
        "legal_intl": "Facturación a {pais}. +Impuestos retenidos +Gastos OUR.",
        "noshow_title": "Política No-Show:", "noshow_text": "Multa 50% inasistencia <24h.",
        "validity": "Validez 30 días"
    },
    "PT": {
        "title": "Cotação", "quote": "COTAÇÃO", "invoice_to": "Faturar para:",
        "client": "Cliente", "sec_prod": "Licenças", "sec_serv": "Serviços",
        "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total",
        "subtotal": "Subtotal", "fee": "Taxa Admin", "discount": "Desconto", "bank": "Taxa Bancária",
        "legal_intl": "Faturamento para {pais}. +Impostos retidos +Despesas OUR.",
        "noshow_title": "Política No-Show:", "noshow_text": "Multa de 50% por não comparecimento <24h.",
        "validity": "Validade 30 dias"
    },
    "EN": {
        "title": "Quotation", "quote": "QUOTATION", "invoice_to": "Bill to:",
        "client": "Client", "sec_prod": "Licenses", "sec_serv": "Services",
        "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total",
        "subtotal": "Subtotal", "fee": "Admin Fee", "discount": "Discount", "bank": "Bank Fee",
        "legal_intl": "Billing to {pais}. +Withholding taxes +OUR expenses.",
        "noshow_title": "No-Show Policy:", "noshow_text": "50% fine for non-attendance <24h.",
        "validity": "Validity 30 days"
    }
}

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado 939", "Giro": "Consultoria"},
    "Peru": {"Nombre": "TALENTPRO S.A.C.", "ID": "DNI 25489763", "Dir": "AV. EL DERBY 254", "Giro": "Servicios"},
    "Chile_Pruebas": {"Nombre": "TALENT PRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630", "Giro": "Selección"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630", "Giro": "RRHH"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2", "Dir": "CALLE 50, PANAMÁ", "Giro": "Talent Services"}
}

# --- LÓGICA DE NEGOCIO ---
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
            except: 
                try: return float(r.iloc[0][str(t)])
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

# --- HELPER PARA EQUIPOS ---
def get_user_teams_list(user_data):
    """Normaliza el campo 'equipo' que puede ser string antiguo o lista nueva."""
    raw = user_data.get('equipo', [])
    if isinstance(raw, str):
        if raw == "N/A" or not raw: return []
        return [raw]
    return raw # Es lista

# --- PDF ENGINE ---
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
    pdf.ln(5)
    x=120
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

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================
def modulo_crm():
    st.title("📇 Prospectos y Clientes")
    tab1, tab2 = st.tabs(["📋 Gestión de Leads", "🏢 Cartera Clientes"])
    with tab1:
        with st.expander("➕ Nuevo Lead", expanded=False):
            with st.form("form_lead"):
                st.subheader("1. Datos Generales")
                c1, c2, c3 = st.columns(3)
                nom_cliente = c1.text_input("Cliente / Empresa")
                area = c2.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"])
                pais = c3.selectbox("País", TODOS_LOS_PAISES)
                c1, c2, c3 = st.columns(3)
                ind = c1.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"])
                web = c2.text_input("Web"); idioma = c3.selectbox("Idioma", ["ES", "EN", "PT"])
                st.subheader("2. Contactos Clave")
                contacts_data = []
                for i in range(1, 4):
                    c1, c2, c3 = st.columns(3)
                    n = c1.text_input(f"Nombre {i}", key=f"n{i}"); m = c2.text_input(f"Mail {i}", key=f"m{i}"); t = c3.text_input(f"Tel {i}", key=f"t{i}")
                    if n: contacts_data.append(f"{n} ({m})")
                st.subheader("3. Seguimiento")
                c1, c2 = st.columns(2)
                origen = c1.selectbox("Origen", ["SHL", "KAM TalentPRO", "Prospección del Usuario"])
                etapa = c2.selectbox("Etapa Inicial", ["Prospección", "Contacto", "Reunión", "Propuesta"])
                expectativa = st.text_area("Expectativa / Dolor Principal")
                if st.form_submit_button("Guardar Lead"):
                    str_contactos = ", ".join(contacts_data)
                    new_lead = {"id": int(time.time()), "Cliente": nom_cliente, "Area": area, "Pais": pais, "Industria": ind, "Web": web, "Contactos": str_contactos, "Origen": origen, "Etapa": etapa, "Expectativa": expectativa, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())}
                    new_db = st.session_state['leads_db'] + [new_lead]
                    if github_push_json('url_leads', new_db, st.session_state.get('leads_sha')):
                        st.session_state['leads_db'] = new_db; st.success("Lead guardado correctamente."); time.sleep(1); st.rerun()
                    else: st.error("Error al guardar en GitHub")
        if st.session_state['leads_db']: st.dataframe(pd.DataFrame(st.session_state['leads_db']), use_container_width=True)
        else: st.info("No hay leads registrados.")
    with tab2:
        with st.expander("➕ Registrar Cliente Existente / Histórico", expanded=False):
             with st.form("form_existing_client"):
                 st.info("Utiliza esto para agregar clientes que ya existen y no son prospectos nuevos.")
                 ec1, ec2 = st.columns(2)
                 e_name = ec1.text_input("Nombre Empresa")
                 e_pais = ec2.selectbox("País Origen", TODOS_LOS_PAISES, key="epais")
                 ec3, ec4 = st.columns(2)
                 e_ind = ec3.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"], key="eind")
                 e_cont = ec4.text_input("Contacto Principal")
                 if st.form_submit_button("Guardar Cliente en Cartera"):
                     if e_name:
                         exist_client = {"id": int(time.time()), "Cliente": e_name, "Area": "Cartera", "Pais": e_pais, "Industria": e_ind, "Web": "", "Contactos": e_cont, "Origen": "Base Histórica", "Etapa": "Cliente Activo", "Expectativa": "Cliente Recurrente", "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())}
                         new_db_ex = st.session_state['leads_db'] + [exist_client]
                         if github_push_json('url_leads', new_db_ex, st.session_state.get('leads_sha')):
                             st.session_state['leads_db'] = new_db_ex; st.success(f"Cliente {e_name} agregado a la cartera."); time.sleep(1); st.rerun()
                     else: st.error("Falta el nombre de la empresa")
        l_leads = [l['Cliente'] for l in st.session_state['leads_db']]
        l_cots = st.session_state['cotizaciones']['empresa'].unique().tolist()
        todos = sorted(list(set(l_leads + l_cots)))
        sel = st.selectbox("Ver Cliente 360", [""] + todos)
        if sel:
            df = st.session_state['cotizaciones']; dfc = df[df['empresa']==sel]
            tot = dfc['total'].sum() if not dfc.empty else 0
            fac_cli = dfc[dfc['estado']=='Facturada']['total'].sum() if not dfc.empty else 0
            pag_cli = dfc[(dfc['estado']=='Facturada') & (dfc['pago']=='Pagada')]['total'].sum() if not dfc.empty else 0
            lead_info = next((l for l in st.session_state['leads_db'] if l['Cliente'] == sel), None)
            st.markdown(f"### 🏢 {sel}")
            if lead_info:
                c1,c2,c3 = st.columns(3)
                c1.info(f"**Industria:** {lead_info.get('Industria','')}"); c2.info(f"**Web:** {lead_info.get('Web','')}"); c3.info(f"**Origen:** {lead_info.get('Origen','')}")
                st.write(f"**Contactos:** {lead_info.get('Contactos','')}"); st.write(f"**Dolor:** {lead_info.get('Expectativa','')}"); st.divider()
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Cotizado", f"${tot:,.0f}"); c2.metric("Total Facturado", f"${fac_cli:,.0f}"); c3.metric("Total Pagado", f"${pag_cli:,.0f}"); c4.metric("# Cotizaciones", len(dfc))
            st.dataframe(dfc[['fecha','id','pais','total','estado','factura','pago']], use_container_width=True)

def modulo_cotizador():
    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES", "PT", "EN"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    c1,c2,c3,c4 = st.columns(4)
    v_uf = TASAS['UF']; v_usd = TASAS['USD_CLP']; v_brl = TASAS['USD_BRL']
    c1.metric("UF", f"${v_uf:,.0f}"); c2.metric("USD", f"${v_usd:,.0f}"); c3.metric("BRL", f"{v_brl:.2f}")
    if c4.button("Actualizar Tasas"): obtener_indicadores.clear(); st.rerun()
    if v_uf == 0 or v_usd == 0: st.error("⚠️ Error cargando indicadores. Intenta 'Actualizar Tasas'.")

    st.markdown("---"); c1, c2 = st.columns([1, 2])
    idx = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    ps = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx); ctx = obtener_contexto(ps)
    c2.info(f"Moneda: **{ctx['mon']}** | Tarifas: **{ctx['tipo']}** {ctx.get('niv', '')}")
    st.markdown("---"); cc1,cc2,cc3,cc4=st.columns(4)
    
    # Lógica de asignación de equipo si el usuario tiene múltiples
    curr_user_data = st.session_state['users_db'].get(st.session_state['current_user'], {})
    user_teams = get_user_teams_list(curr_user_data)
    
    if len(user_teams) > 1:
        sel_team_cot = cc4.selectbox("Asignar a Equipo", user_teams)
    elif len(user_teams) == 1:
        sel_team_cot = user_teams[0]
        cc4.text_input("Equipo", value=sel_team_cot, disabled=True)
    else:
        sel_team_cot = "N/A"
        cc4.text_input("Equipo", value="N/A", disabled=True)
        
    clientes_list = sorted(list(set([x['Cliente'] for x in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
    emp = cc1.selectbox(txt['client'], [""]+clientes_list)
    con = cc2.text_input("Contacto"); ema = cc3.text_input("Email")
    ven = cc4.text_input("Ejecutivo", value=st.session_state['users_db'][st.session_state['current_user']].get('name',''), disabled=True)
    st.markdown("---"); tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4 = st.columns([3,1,1,1]); lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp,key="p1"); qp=c2.number_input("Cant",1,10000,10,key="q1")
            up=calc_xls(ctx['dp'],sp,qp,ctx['tipo']=='Loc'); c3.metric("Unit",f"{up:,.2f}")
            if c4.button("Add",key="b1"): st.session_state['carrito'].append({"Ítem":"Evaluación","Desc":sp,"Det":f"x{qp}","Moneda":ctx['mon'],"Unit":up,"Total":up*qp}); st.rerun()
    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        if ls:
            ss=c1.selectbox("Serv",["Certificación PAA"]+ls,key="s1")
            if "PAA" in ss:
                c2.write(""); qs=c2.number_input("Pers",1,100,1,key="q2"); us=calc_paa(qs,ctx['mon']); dt=f"{qs} pers"
            else:
                r,q=c2.columns(2); cs=ctx['ds'].columns.tolist(); rol=r.selectbox("Rol",[x for x in ['Senior','BM','BP'] if x in cs]); qs=q.number_input("Cant",1,100,1); rw=ctx['ds'][(ctx['ds']['Servicio']==ss)]; us=float(rw.iloc[0][rol]) if not rw.empty else 0; dt=f"{rol} ({qs})"
            c3.metric("Unit",f"{us:,.2f}")
            if c4.button("Add",key="b2"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        st.markdown("---")
        df_cart = pd.DataFrame(st.session_state['carrito'])
        st.caption("📝 Puedes editar la descripción, cantidad o precio directamente en la tabla.")
        edited_cart = st.data_editor(df_cart, num_rows="dynamic", use_container_width=True, column_config={"Total": st.column_config.NumberColumn(format="$%.2f"), "Unit": st.column_config.NumberColumn(format="$%.2f")}, key="cart_editor")
        st.session_state['carrito'] = edited_cart.to_dict('records')
        sub = sum(item['Total'] for item in st.session_state['carrito'])
        eva = sum(item['Total'] for item in st.session_state['carrito'] if item['Ítem']=='Evaluación')
        cL, cR = st.columns([3,1])
        with cR:
            fee=st.checkbox("Fee 10%",False); bnk=st.number_input("Bank",0.0)
            dsc_name = st.text_input("Glosa Descuento", value="Descuento")
            dsc = st.number_input("Monto Desc", 0.0)
            vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-dsc
            st.metric("TOTAL",f"{ctx['mon']} {fin:,.2f}")
            if st.button("GUARDAR", type="primary"):
                if not emp: st.error("Falta Empresa"); return
                nid=f"TP-{random.randint(1000,9999)}"; cli={'empresa':emp,'contacto':con,'email':ema}
                ext={'fee':vfee,'bank':bnk,'desc':dsc,'desc_name':dsc_name, 'pais':ps,'id':nid}
                prod_items = [x for x in st.session_state['carrito'] if x['Ítem']=='Evaluación']
                serv_items = [x for x in st.session_state['carrito'] if x['Ítem']=='Servicio']
                links_html = ""
                if ps == "Chile" and prod_items and serv_items:
                    sub_p = sum(x['Total'] for x in prod_items); fee_p = sub_p*0.10 if fee else 0; tax_p = sub_p*0.19; tot_p = sub_p + fee_p + tax_p
                    calc_p = {'subtotal':sub_p, 'fee':fee_p, 'tax_name':"IVA (19%)", 'tax_val':tax_p, 'total':tot_p}
                    pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli, prod_items, calc_p, idi, ext)
                    b64_p = base64.b64encode(pdf_p).decode('latin-1')
                    links_html += f'<a href="data:application/pdf;base64,{b64_p}" download="Cot_{nid}_Productos.pdf">📄 Descargar Cotización (Productos - SpA)</a><br><br>'
                    sub_s = sum(x['Total'] for x in serv_items); tot_s = sub_s + bnk - dsc
                    calc_s = {'subtotal':sub_s, 'fee':0, 'tax_name':"", 'tax_val':0, 'total':tot_s}
                    pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli, serv_items, calc_s, idi, ext)
                    b64_s = base64.b64encode(pdf_s).decode('latin-1')
                    links_html += f'<a href="data:application/pdf;base64,{b64_s}" download="Cot_{nid}_Servicios.pdf">📄 Descargar Cotización (Servicios - Ltda)</a>'
                    st.success("✅ Generadas 2 cotizaciones separadas (SpA y Servicios)")
                else:
                    ent = get_empresa(ps, st.session_state['carrito'])
                    calc = {'subtotal':sub, 'fee':vfee, 'tax_name':tn, 'tax_val':tv, 'total':fin}
                    pdf = generar_pdf_final(ent, cli, st.session_state['carrito'], calc, idi, ext)
                    b64 = base64.b64encode(pdf).decode('latin-1')
                    links_html = f'<a href="data:application/pdf;base64,{b64}" download="Cot_{nid}.pdf">📄 Descargar PDF</a>'
                    st.success("✅ Cotización generada")
                st.markdown(links_html, unsafe_allow_html=True)
                row = {
                    'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 
                    'estado':'Enviada', 'vendedor':ven, 'equipo_asignado': sel_team_cot,
                    'oc':'', 'factura':'', 'pago':'Pendiente', 'hes':False, 'hes_num':'', 
                    'items': st.session_state['carrito'], 'pdf_data': ext, 'idioma': idi
                }
                st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    st.info("Guardado en Base de Datos"); st.session_state['carrito']=[]; time.sleep(2)
                else: st.warning("Error al sincronizar con GitHub")
        with cL: 
            if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial (Ventas)")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("Sin datos."); return
    df = df.sort_values('fecha', ascending=False)
    
    curr_user = st.session_state['current_user']
    curr_role = st.session_state.get('current_role', 'Comercial')
    
    # Filtro por equipo
    if curr_role == 'Comercial':
        my_teams = get_user_teams_list(st.session_state['users_db'][curr_user])
        allowed_sellers = []
        for u, d in st.session_state['users_db'].items():
             u_teams = get_user_teams_list(d)
             if set(u_teams) & set(my_teams):
                 allowed_sellers.append(d['name'])
        
        # Filtro: O soy yo el vendedor, O el vendedor es de mi equipo
        df = df[df['vendedor'].isin(allowed_sellers)]
    
    c1, c2 = st.columns([3, 1])
    with c1: st.info("ℹ️ Gestión: Cambia estado a 'Aprobada' para que Finanzas facture.")
    with c2: ver_historial = st.checkbox("📂 Ver Historial Completo", value=False)
    
    if not ver_historial:
        df = df[df['estado'].isin(['Enviada', 'Aprobada'])]
        if df.empty: st.warning("No tienes cotizaciones abiertas. Marca 'Ver Historial' para ver cerradas.")

    for i, r in df.iterrows():
        lang_tag = f"[{r.get('idioma','ES')}]"
        team_tag = f"({r.get('equipo_asignado', 'N/A')})"
        label = f"{lang_tag} {team_tag} {r['fecha']} | {r['id']} | {r['empresa']} | {r['moneda']} {r['total']:,.0f}"
        if r['estado'] == 'Facturada': label += " ✅ (Facturada)"
        elif r['estado'] == 'Aprobada': label += " 🎉 (Cerrada)"
        elif r['estado'] == 'Enviada': label += " ⏳ (En Negociación)"
        
        with st.expander(label):
            col_status, col_req = st.columns(2)
            with col_status:
                st.caption("Estado")
                est_options = ["Enviada", "Aprobada", "Rechazada", "Perdida"]
                disabled_st = r['estado'] == 'Facturada'
                current_st = r['estado'] if r['estado'] in est_options else est_options[0]
                if r['estado'] == 'Facturada': current_st = "Aprobada"
                
                new_status = st.selectbox("Estado", est_options, key=f"st_{r['id']}", index=est_options.index(current_st), disabled=disabled_st)
            
            with col_req:
                st.caption("Requisitos")
                hes_check = st.checkbox("Requiere HES", value=r.get('hes', False), key=f"hs_{r['id']}", disabled=disabled_st)
                if hes_check: st.warning("⚠️ Requiere HES para facturar.")

            if not disabled_st and st.button("Actualizar Venta", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_status
                st.session_state['cotizaciones'].at[i, 'hes'] = hes_check
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    st.success("Estado actualizado"); time.sleep(1); st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No hay datos."); return
    
    tab_billing, tab_collection = st.tabs(["📝 Por Facturar (Backlog)", "💵 Historial Facturadas"])
    
    with tab_billing:
        st.subheader("Pendientes de Facturación")
        to_bill = df[df['estado'] == 'Aprobada']
        
        if to_bill.empty: 
            st.success("¡Excelente! No hay cotizaciones pendientes de facturar.")
        else:
            for i, r in to_bill.iterrows():
                with st.container():
                    lang_tag = f"[{r.get('idioma','ES')}]"
                    st.markdown(f"**{lang_tag} {r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']:,.0f}")
                    if r.get('hes'): st.error("🚨 REQUISITO: Esta venta requiere N° HES o MIGO para facturar.")
                    
                    if r.get('items') and isinstance(r['items'], list):
                        cli = {'empresa':r['empresa'], 'contacto':'', 'email':''} 
                        ext = r.get('pdf_data', {'id':r['id'], 'pais':r['pais'], 'bank':0, 'desc':0})
                        prod_items = [x for x in r['items'] if x['Ítem']=='Evaluación']
                        serv_items = [x for x in r['items'] if x['Ítem']=='Servicio']
                        
                        pdf_links = ""
                        if r['pais'] == "Chile" and prod_items and serv_items:
                             sub_p = sum(x['Total'] for x in prod_items); tax_p = sub_p*0.19; tot_p = sub_p*1.19
                             calc_p = {'subtotal':sub_p, 'fee':0, 'tax_name':"IVA", 'tax_val':tax_p, 'total':tot_p}
                             pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli, prod_items, calc_p, "COTIZACIÓN", ext)
                             b64_p = base64.b64encode(pdf_p).decode('latin-1')
                             
                             sub_s = sum(x['Total'] for x in serv_items); tot_s = sub_s
                             calc_s = {'subtotal':sub_s, 'fee':0, 'tax_name':"", 'tax_val':0, 'total':tot_s}
                             pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli, serv_items, calc_s, "COTIZACIÓN", ext)
                             b64_s = base64.b64encode(pdf_s).decode('latin-1')
                             pdf_links = f'<a href="data:application/pdf;base64,{b64_p}" download="Cot_{r["id"]}_P.pdf">📄 Ver PDF SpA</a> | <a href="data:application/pdf;base64,{b64_s}" download="Cot_{r["id"]}_S.pdf">📄 Ver PDF Ltda</a>'
                        else:
                             ent = get_empresa(r['pais'], r['items'])
                             sub = sum(x['Total'] for x in r['items'])
                             tn, tv = get_impuestos(r['pais'], sub, sub)
                             calc = {'subtotal':sub, 'fee':0, 'tax_name':tn, 'tax_val':tv, 'total':r['total']}
                             pdf = generar_pdf_final(ent, cli, r['items'], calc, "COTIZACIÓN", ext)
                             b64 = base64.b64encode(pdf).decode('latin-1')
                             pdf_links = f'<a href="data:application/pdf;base64,{b64}" download="Cot_{r["id"]}.pdf">📄 Ver PDF Cotización</a>'
                        st.markdown(pdf_links, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Vista de PDF no disponible (cotización antigua sin detalle).")

                    c1, c2, c3, c4 = st.columns(4)
                    new_oc = c1.text_input("Orden de Compra (OC)", value=r.get('oc',''), key=f"oc_{r['id']}")
                    new_hes_num = c2.text_input("N° HES / MIGO", value=r.get('hes_num',''), key=f"hnum_{r['id']}")
                    new_inv = c3.text_input("N° Factura", key=f"inv_{r['id']}")
                    
                    if c4.button("Emitir Factura", key=f"bill_{r['id']}"):
                        if not new_inv: st.error("Falta N° Factura"); continue
                        st.session_state['cotizaciones'].at[i, 'oc'] = new_oc
                        st.session_state['cotizaciones'].at[i, 'hes_num'] = new_hes_num
                        st.session_state['cotizaciones'].at[i, 'factura'] = new_inv
                        st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            st.success(f"Factura {new_inv} guardada! Movida al historial."); time.sleep(1); st.rerun()
                    st.divider()

    with tab_collection:
        st.subheader("Historial y Cobranza")
        billed = df[df['estado'] == 'Facturada'].copy()
        if billed.empty:
            st.info("No hay historial de facturación.")
        else:
            st.dataframe(billed[['fecha', 'id', 'empresa', 'total', 'moneda', 'oc', 'hes_num', 'factura', 'pago']], use_container_width=True)
            st.markdown("---")
            st.subheader("🔧 Gestión de Factura (Edición/Anulación)")
            
            inv_list = billed['factura'].unique().tolist()
            sel_inv = st.selectbox("Seleccionar N° Factura", inv_list)
            
            if sel_inv:
                row_idx = df[df['factura'] == sel_inv].index[0]
                r_sel = st.session_state['cotizaciones'].iloc[row_idx]
                
                t1, t2, t3 = st.tabs(["💰 Actualizar Pago", "✏️ Corregir Datos", "🚫 Anular Factura"])
                
                with t1:
                    curr_pay = r_sel['pago']
                    c1, c2 = st.columns([2,1])
                    new_p = c1.selectbox("Estado Pago", ["Pendiente", "Pagada", "Vencida"], index=["Pendiente", "Pagada", "Vencida"].index(curr_pay))
                    if c2.button("Actualizar Pago"):
                        st.session_state['cotizaciones'].at[row_idx, 'pago'] = new_p
                        github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                        st.success("Pago actualizado"); time.sleep(0.5); st.rerun()

                with t2:
                    st.info("Edita datos si hubo un error de tipeo.")
                    e_oc = st.text_input("Corregir OC", value=r_sel['oc'])
                    e_hes = st.text_input("Corregir HES", value=r_sel['hes_num'])
                    e_inv = st.text_input("Corregir N° Factura", value=r_sel['factura'])
                    
                    if st.button("Guardar Correcciones"):
                        st.session_state['cotizaciones'].at[row_idx, 'oc'] = e_oc
                        st.session_state['cotizaciones'].at[row_idx, 'hes_num'] = e_hes
                        st.session_state['cotizaciones'].at[row_idx, 'factura'] = e_inv
                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            st.success("Datos corregidos"); time.sleep(1); st.rerun()

                with t3:
                    st.error("⚠️ CUIDADO: Esto eliminará la factura y devolverá la cotización a la pestaña 'Por Facturar'.")
                    if st.button("🗑️ Eliminar Factura (Revertir a Backlog)"):
                        st.session_state['cotizaciones'].at[row_idx, 'estado'] = 'Aprobada'
                        st.session_state['cotizaciones'].at[row_idx, 'factura'] = ''
                        st.session_state['cotizaciones'].at[row_idx, 'pago'] = 'Pendiente'
                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            st.success("Factura eliminada. Cotización devuelta al Backlog."); time.sleep(1); st.rerun()

def convert_to_usd(row):
    m = row['moneda']; v = row['total']
    if m == 'US$': return v
    if m == 'UF': return (v * TASAS['UF']) / TASAS['USD_CLP'] if TASAS['USD_CLP'] > 0 else 0
    if m == 'R$': return v / TASAS['USD_BRL'] if TASAS['USD_BRL'] > 0 else 0
    return 0

def modulo_dashboard():
    st.title("📊 Dashboards & Analytics")
    st.sidebar.markdown("### 📅 Filtro de Tiempo")
    
    # 1. Asegurar DataFrame de Cotizaciones y su columna Año
    df_cots = st.session_state['cotizaciones'].copy()
    if not df_cots.empty:
        df_cots['fecha_dt'] = pd.to_datetime(df_cots['fecha'], errors='coerce')
        df_cots = df_cots.dropna(subset=['fecha_dt'])
        if not df_cots.empty:
            df_cots['Año'] = df_cots['fecha_dt'].dt.year
            df_cots['Mes'] = df_cots['fecha_dt'].dt.month_name()
    
    # 2. Asegurar DataFrame de Leads y su columna Año
    if st.session_state['leads_db']:
        df_leads = pd.DataFrame(st.session_state['leads_db'])
        if 'Fecha' in df_leads.columns:
            df_leads['fecha_dt'] = pd.to_datetime(df_leads['Fecha'], errors='coerce')
            df_leads = df_leads.dropna(subset=['fecha_dt'])
            if not df_leads.empty:
                df_leads['Año'] = df_leads['fecha_dt'].dt.year
                df_leads['Mes'] = df_leads['fecha_dt'].dt.month_name()
        
        for col in ['Origen', 'Etapa', 'Industria']:
            if col not in df_leads.columns: df_leads[col] = "Sin Dato"
        df_leads = df_leads.fillna("Sin Dato")
    else: 
        df_leads = pd.DataFrame()

    # 3. Construcción segura de la lista de Años para el filtro
    years_cots = df_cots['Año'].unique().tolist() if not df_cots.empty and 'Año' in df_cots.columns else []
    years_leads = df_leads['Año'].unique().tolist() if not df_leads.empty and 'Año' in df_leads.columns else []
    
    all_years = sorted(list(set(years_cots + years_leads)))
    if not all_years:
        all_years = [datetime.now().year]

    selected_years = st.sidebar.multiselect("Seleccionar Años", all_years, default=[max(all_years)])
    
    # 4. Aplicar Filtro Temporal de forma segura
    if not df_cots.empty and 'Año' in df_cots.columns:
        df_cots_filtered = df_cots[df_cots['Año'].isin(selected_years)]
    else: 
        df_cots_filtered = df_cots

    if not df_leads.empty and 'Año' in df_leads.columns:
        df_leads_filtered = df_leads[df_leads['Año'].isin(selected_years)]
    else: 
        df_leads_filtered = df_leads

    users = st.session_state['users_db']
    curr_email = st.session_state['current_user']
    curr_role = st.session_state.get('current_role', 'Comercial')

    tab_gen, tab_kpi, tab_lead, tab_sale, tab_bill = st.tabs(["📊 General", "🎯 Metas y Desempeño", "📇 Leads (Funnel)", "📈 Cierre Ventas", "💵 Facturación"])
    
    with tab_gen:
        df_open = df_cots_filtered[df_cots_filtered['estado'].isin(['Enviada', 'Aprobada'])].copy()
        cant_abiertas = len(df_open)
        monto_abierto_usd = 0
        if not df_open.empty:
             df_open['Total_USD'] = df_open.apply(convert_to_usd, axis=1)
             monto_abierto_usd = df_open['Total_USD'].sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Leads", len(df_leads_filtered))
        c2.metric("Cant. Abiertas", cant_abiertas) 
        c3.metric("Monto en Juego (Open)", f"${monto_abierto_usd:,.0f}")
        
        total_ops = len(df_cots_filtered); won_ops = len(df_cots_filtered[df_cots_filtered['estado'].isin(['Aprobada','Facturada'])])
        win_rate = (won_ops/total_ops*100) if total_ops > 0 else 0
        c4.metric("Tasa de Cierre", f"{win_rate:.1f}%")
        
        df_fact = df_cots_filtered[df_cots_filtered['estado']=='Facturada'].copy()
        if not df_fact.empty:
             df_fact['Total_USD'] = df_fact.apply(convert_to_usd, axis=1)
             facturado_usd = df_fact['Total_USD'].sum()
        else: facturado_usd = 0
        
        c5.metric("Facturado (USD)", f"${facturado_usd:,.0f}")
        
        st.divider()
        if not df_cots_filtered.empty:
            fig = px.pie(df_cots_filtered, names='estado', title="Distribución Estado Cotizaciones")
            st.plotly_chart(fig, use_container_width=True)

    with tab_kpi:
        st.subheader("Desempeño Individual vs Metas")
        
        # SI ES FINANZAS/ADMIN: VE A TODOS
        if curr_role in ['Super Admin', 'Finanzas']:
            st.info("Vista de Supervisor: Selecciona un comercial o ve la tabla resumen.")
            
            # Tabla Resumen Todos
            summary_data = []
            for u_email, u_data in users.items():
                if u_data.get('role') == 'Comercial' or u_email == curr_email:
                    # FETCH GOAL BY SELECTED YEARS
                    user_metas = u_data.get('metas_anuales', {})
                    goal_rev = sum(float(user_metas.get(str(y), {}).get('rev', 0)) for y in selected_years)
                    # Fallback to legacy field if no annual meta
                    if goal_rev == 0: goal_rev = float(u_data.get('meta_rev', 0))

                    df_u_sales = df_cots_filtered[(df_cots_filtered['vendedor'] == u_data.get('name')) & (df_cots_filtered['estado'] == 'Facturada')].copy()
                    
                    real_rev_usd = 0
                    if not df_u_sales.empty:
                        df_u_sales['Total_USD'] = df_u_sales.apply(convert_to_usd, axis=1)
                        real_rev_usd = df_u_sales['Total_USD'].sum()
                    
                    pct = (real_rev_usd / goal_rev * 100) if goal_rev > 0 else 0
                    
                    # Equipos string para display
                    eq_list = get_user_teams_list(u_data)
                    eq_str = ", ".join(eq_list)
                    
                    summary_data.append({
                        "Nombre": u_data.get('name'),
                        "Equipo": eq_str,
                        "Meta (USD)": f"${goal_rev:,.0f}",
                        "Venta (USD)": f"${real_rev_usd:,.0f}",
                        "Cumplimiento": f"{pct:.1f}%"
                    })
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
            
            # Drill Down
            st.divider()
            sel_rep = st.selectbox("Ver detalle de vendedor:", [d['name'] for e,d in users.items() if d.get('role') in ['Comercial', 'Super Admin', 'Finanzas']])
            if sel_rep:
                user_data = next((d for e,d in users.items() if d['name'] == sel_rep), {})
                df_my_sales = df_cots_filtered[(df_cots_filtered['vendedor'] == sel_rep) & (df_cots_filtered['estado'] == 'Facturada')]
        
        # SI ES COMERCIAL O ADMIN CON META PERSONAL
        else:
            user_data = users.get(curr_email, {})
            df_my_sales = df_cots_filtered[(df_cots_filtered['vendedor'] == user_data.get('name','')) & (df_cots_filtered['estado'] == 'Facturada')]

        if user_data:
            def get_cat(m): return clasificar_cliente(m)
            if not df_my_sales.empty:
                df_my_sales['Categoria'] = df_my_sales['total'].apply(get_cat)
                df_my_sales['Total_USD'] = df_my_sales.apply(convert_to_usd, axis=1)
                my_rev = df_my_sales['Total_USD'].sum()
                cnt_big = len(df_my_sales[df_my_sales['Categoria']=='Grande'])
                cnt_mid = len(df_my_sales[df_my_sales['Categoria']=='Mediano'])
                cnt_sml = len(df_my_sales[df_my_sales['Categoria']=='Chico'])
            else:
                my_rev = 0; cnt_big=0; cnt_mid=0; cnt_sml=0

            # Calculate Aggregate Goals based on selected years
            u_metas = user_data.get('metas_anuales', {})
            goal_rev = sum(float(u_metas.get(str(y), {}).get('rev', 0)) for y in selected_years)
            goal_big = sum(int(u_metas.get(str(y), {}).get('big', 0)) for y in selected_years)
            goal_mid = sum(int(u_metas.get(str(y), {}).get('mid', 0)) for y in selected_years)
            goal_sml = sum(int(u_metas.get(str(y), {}).get('sml', 0)) for y in selected_years)
            
            # Fallback legacy
            if goal_rev == 0:
                goal_rev = float(user_data.get('meta_rev', 0))
                goal_big = int(user_data.get('meta_cli_big', 0))
                goal_mid = int(user_data.get('meta_cli_mid', 0))
                goal_sml = int(user_data.get('meta_cli_small', 0))

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"#### Resultados: {user_data.get('name','')}")
                if goal_rev > 0: 
                    st.progress(min(my_rev/goal_rev, 1.0), text=f"Facturación: ${my_rev:,.0f} / ${goal_rev:,.0f} USD ({my_rev/goal_rev*100:.1f}%)")
                else: st.info("Sin meta asignada.")
                c_a, c_b, c_c = st.columns(3)
                c_a.metric("Grandes", f"{cnt_big}/{goal_big}"); c_b.metric("Medianos", f"{cnt_mid}/{goal_mid}"); c_c.metric("Chicos", f"{cnt_sml}/{goal_sml}")

            with c2:
                my_teams = get_user_teams_list(user_data)
                
                if my_teams:
                    for team_name in my_teams:
                        st.markdown(f"#### 🏆 Equipo: {team_name}")
                        team_config_db = users.get('_CONFIG_ORG', {})
                        team_goal_rev = 0
                        if isinstance(team_config_db.get(team_name), dict):
                            t_metas = team_config_db[team_name].get('metas_anuales', {})
                            team_goal_rev = sum(float(t_metas.get(str(y), 0)) for y in selected_years)
                            if team_goal_rev == 0: team_goal_rev = float(team_config_db[team_name].get('meta', 0))
                        
                        # Filtrar cotizaciones asignadas específicamente a este equipo
                        df_team_sales = df_cots_filtered[(df_cots_filtered['equipo_asignado'] == team_name) & (df_cots_filtered['estado'] == 'Facturada')].copy()
                        
                        if not df_team_sales.empty:
                            df_team_sales['Total_USD'] = df_team_sales.apply(convert_to_usd, axis=1)
                            team_rev = df_team_sales['Total_USD'].sum()
                        else: team_rev = 0
                        
                        if team_goal_rev > 0:
                            st.progress(min(team_rev/team_goal_rev, 1.0), text=f"Meta: ${team_rev:,.0f} / ${team_goal_rev:,.0f} USD")
                        else: st.info(f"Sin meta global definida.")
                else:
                    st.info("Usuario sin equipo asignado.")

    with tab_lead:
        if not df_leads_filtered.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Funnel por Etapa")
                fig_funnel = px.funnel(df_leads_filtered['Etapa'].value_counts().reset_index(), x='count', y='Etapa', title="Embudo")
                st.plotly_chart(fig_funnel, use_container_width=True)
            with c2:
                st.subheader("Leads por Origen")
                fig_source = px.bar(df_leads_filtered, x='Origen', title="Fuentes", color='Origen')
                st.plotly_chart(fig_source, use_container_width=True)
        else: st.info("No hay datos de leads.")

    with tab_sale:
        if not df_cots_filtered.empty:
            df_sales = df_cots_filtered[df_cots_filtered['estado'].isin(['Aprobada','Facturada'])]
            if not df_sales.empty:
                st.subheader("Evolución de Ventas")
                fig_line = px.line(df_sales.groupby(['Año','Mes'])['total'].sum().reset_index(), x='Mes', y='total', color='Año', markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
            else: st.info("Aún no hay ventas cerradas.")
        else: st.info("Sin datos.")

    with tab_bill:
        df_inv = df_cots_filtered[df_cots_filtered['estado']=='Facturada']
        if not df_inv.empty:
            c1, c2, c3 = st.columns(3)
            tot_inv = df_inv['total'].sum()
            tot_paid = df_inv[df_inv['pago']=='Pagada']['total'].sum()
            tot_pend = tot_inv - tot_paid
            c1.metric("Total Facturado", f"${tot_inv:,.0f}")
            c2.metric("Cobrado", f"${tot_paid:,.0f}")
            fig_pay = px.pie(df_inv, names='pago', title="Status de Cobranza", hole=0.4, color_discrete_map={'Pagada':'green', 'Pendiente':'orange', 'Vencida':'red'})
            st.plotly_chart(fig_pay, use_container_width=True)
        else: st.info("No hay facturas emitidas.")

def modulo_admin():
    st.title("👥 Administración de Usuarios y Metas")
    users = st.session_state['users_db']
    
    tab_list, tab_create, tab_teams, tab_reset = st.tabs(["⚙️ Gestionar Usuarios", "➕ Crear Nuevo Usuario", "🏢 Estructura Organizacional", "🔥 RESET SISTEMA"])
    
    # ------------------ SECCIÓN EQUIPOS POR AÑO ------------------
    with tab_teams:
        st.subheader("Configuración de Metas Globales (Por Año)")
        config_org = users.get('_CONFIG_ORG', {})
        
        # Selector de Año para configurar
        current_year = datetime.now().year
        sel_year_team = st.selectbox("Configurar Metas para el Año:", [current_year, current_year+1, current_year-1])
        
        # Crear Nuevo Equipo
        with st.expander("Crear Nuevo Equipo Principal"):
            new_team_name = st.text_input("Nombre del Equipo (ej: Europa)")
            if st.button("Crear Equipo"):
                if new_team_name and new_team_name not in config_org:
                    config_org[new_team_name] = {'metas_anuales': {}, 'subs': {}}
                    users['_CONFIG_ORG'] = config_org
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success("Equipo creado"); st.rerun()

        # Editar Equipos Existentes
        st.markdown("---")
        for team, data in config_org.items():
            if not isinstance(data, dict): continue
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 3])
                c1.markdown(f"### 🌍 {team}")
                
                # Obtener meta del año seleccionado
                curr_meta = float(data.get('metas_anuales', {}).get(str(sel_year_team), 0))
                new_meta_team = c2.number_input(f"Meta {team} ({sel_year_team}) USD", value=curr_meta, key=f"m_{team}_{sel_year_team}")
                
                # Sub-equipos
                new_sub = c3.text_input(f"Nuevo Sub-equipo en {team}", key=f"ns_{team}")
                if c3.button(f"Agregar Sub-equipo a {team}", key=f"b_{team}"):
                    if new_sub:
                        data['subs'][new_sub] = 0
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.rerun()

                # Gestión Sub-equipos (Ver/Borrar)
                if data['subs']:
                    with c3.expander("Ver/Borrar Sub-equipos"):
                        for sub_name in list(data['subs'].keys()):
                            sc1, sc2 = st.columns([3,1])
                            sc1.text(f"🔹 {sub_name}")
                            if sc2.button("🗑️", key=f"del_sub_{team}_{sub_name}"):
                                del data['subs'][sub_name]
                                users['_CONFIG_ORG'] = config_org
                                github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                                sync_users_after_update(); st.rerun()
                
                # Gestión Equipo Principal (Renombrar/Borrar)
                with c1.expander("Opciones Avanzadas"):
                    new_name = st.text_input("Renombrar Equipo", value=team, key=f"ren_{team}")
                    if st.button("Renombrar", key=f"b_ren_{team}"):
                        config_org[new_name] = config_org.pop(team)
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.rerun()
                    
                    if st.button("Eliminar Equipo Completo", key=f"del_team_{team}", type="primary"):
                        del config_org[team]
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.rerun()

                # Guardar meta
                if new_meta_team != curr_meta:
                    if st.button(f"Guardar Meta {team}", key=f"gm_{team}"):
                        if 'metas_anuales' not in data: data['metas_anuales'] = {}
                        data['metas_anuales'][str(sel_year_team)] = new_meta_team
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.success("Guardado"); time.sleep(1); st.rerun()
                st.divider()

    # ------------------ SECCIÓN CREAR USUARIO ------------------
    with tab_create:
        st.subheader("Alta de Nuevo Usuario")
        config_org = users.get('_CONFIG_ORG', {})
        team_options = list(config_org.keys())
        
        with st.form("new_user_form"):
            new_email = st.text_input("Correo Electrónico (Usuario)")
            new_name = st.text_input("Nombre Completo")
            new_role = st.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"])
            
            c_t1, c_t2 = st.columns(2)
            sel_team = c_t1.selectbox("Equipo Principal", ["N/A"] + team_options)
            
            sub_options = []
            if sel_team != "N/A" and sel_team in config_org:
                sub_options = list(config_org[sel_team]['subs'].keys())
            sel_sub_team = c_t2.selectbox("Sub-Equipo", ["N/A"] + sub_options)

            new_pass = st.text_input("Contraseña Inicial", type="password")
            
            if st.form_submit_button("Crear Usuario"):
                if not new_email or not new_pass: st.error("Faltan datos")
                elif new_email in users: st.error("Usuario existe")
                else:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    users[new_email] = {
                        "name": new_name, "role": new_role, "password_hash": hashed, 
                        "equipo": sel_team, "sub_equipo": sel_sub_team,
                        "meta_rev": 0, "metas_anuales": {} 
                    }
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success(f"Usuario {new_email} creado"); time.sleep(1); st.rerun()

    # ------------------ SECCIÓN LISTAR/EDITAR USUARIOS ------------------
    with tab_list:
        st.subheader("Usuarios Registrados")
        clean_users = []
        for u_email, u_data in users.items():
            if u_email.startswith("_"): continue
            
            # Helper display
            eq_show = u_data.get('equipo', [])
            if isinstance(eq_show, list): eq_show = ", ".join(eq_show)
            
            clean_users.append({
                "Email": u_email, "Nombre": u_data.get('name'), "Rol": u_data.get('role'), 
                "Equipo": eq_show, "Sub-Equipo": u_data.get('sub_equipo', '-'),
                "Meta $": f"${u_data.get('meta_rev', 0):,.0f}"
            })
        st.dataframe(pd.DataFrame(clean_users), use_container_width=True)
        
        st.markdown("---"); st.subheader("✏️ Editar Perfil y Metas")
        user_keys = [k for k in users.keys() if not k.startswith("_")]
        edit_user = st.selectbox("Seleccionar Usuario", user_keys)
        
        # Selector de AÑO para editar metas
        curr_year_admin = datetime.now().year
        sel_year_meta = st.selectbox("Editar Metas para el Año:", [curr_year_admin, curr_year_admin+1, curr_year_admin-1], key="sy_meta")

        if edit_user:
            u = users[edit_user]
            with st.expander(f"Configuración: {u.get('name')}", expanded=True):
                c1, c2, c3 = st.columns(3)
                new_role_e = c1.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"], index=["Comercial", "Finanzas", "Super Admin"].index(u.get('role', 'Comercial')))
                
                # Lógica dinámica para equipos en edición
                config_org = users.get('_CONFIG_ORG', {})
                team_opts = ["N/A"] + list(config_org.keys())
                curr_teams = get_user_teams_list(u)
                valid_defaults = [t for t in curr_teams if t in team_opts]
                
                # MULTI-EQUIPO SUPPORT
                new_teams_e = c2.multiselect("Equipos", team_opts, default=valid_defaults)
                
                # Sub-equipo (simplificado a uno por ahora, o podría ser multi también)
                sub_opts = ["N/A"]
                for t in new_teams_e:
                    if t in config_org: sub_opts += list(config_org[t]['subs'].keys())
                
                curr_sub = u.get('sub_equipo', 'N/A')
                idx_sub = sub_opts.index(curr_sub) if curr_sub in sub_opts else 0
                new_sub_e = c3.selectbox("Sub-Equipo", sub_opts, index=idx_sub, key="edit_sub")

                st.markdown(f"#### 🎯 Metas Anuales ({sel_year_meta})")
                
                # Cargar metas del año seleccionado (o 0 si no existen)
                u_metas = u.get('metas_anuales', {})
                u_metas_year = u_metas.get(str(sel_year_meta), {})
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                m_rev = col_m1.number_input("Meta Facturación ($)", value=float(u_metas_year.get('rev', 0)))
                m_big = col_m2.number_input("Meta Clientes Grandes", value=int(u_metas_year.get('big', 0)))
                m_mid = col_m3.number_input("Meta Clientes Medianos", value=int(u_metas_year.get('mid', 0)))
                m_sml = col_m4.number_input("Meta Clientes Chicos", value=int(u_metas_year.get('sml', 0)))

                if st.button("💾 Guardar Cambios"):
                    # Actualizar datos básicos
                    users[edit_user].update({'role': new_role_e, 'equipo': new_teams_e, 'sub_equipo': new_sub_e})
                    
                    # Actualizar metas del año específico
                    if 'metas_anuales' not in users[edit_user]: users[edit_user]['metas_anuales'] = {}
                    users[edit_user]['metas_anuales'][str(sel_year_meta)] = {
                        'rev': m_rev, 'big': m_big, 'mid': m_mid, 'sml': m_sml
                    }
                    
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success("Perfil actualizado"); time.sleep(1); st.rerun()
                
                st.divider()
                st.warning("⚠️ Zona Seguridad")
                pass_rst = st.text_input("Nueva Contraseña (Admin)", type="password")
                if st.button("Reestablecer Clave"):
                    if pass_rst:
                        users[edit_user]['password_hash'] = bcrypt.hashpw(pass_rst.encode(), bcrypt.gensalt()).decode()
                        if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                            sync_users_after_update(); st.success("Clave cambiada")
                
                st.markdown("### 🚨 Zona de Peligro")
                if edit_user == st.session_state['current_user']: st.error("No puedes eliminar tu propio usuario.")
                else:
                    if st.button(f"🗑️ Eliminar a {edit_user}", type="primary"):
                        del users[edit_user]
                        if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                            sync_users_after_update(); st.success(f"Usuario {edit_user} eliminado."); time.sleep(1); st.rerun()

    # ------------------ SECCIÓN RESET SISTEMA ------------------
    with tab_reset:
        st.error("⚠️ ZONA DE PELIGRO EXTREMO: Aquí puedes borrar datos masivamente.")
        st.markdown("Útil para limpiar datos de prueba antes de salir a producción.")
        
        c1, c2, c3, c4 = st.columns(4)
        del_leads = c1.checkbox("Borrar TODOS los Leads y Clientes")
        del_cots = c2.checkbox("Borrar TODAS las Cotizaciones y Ventas")
        del_teams = c3.checkbox("Borrar Estructura de Equipos")
        del_metas = c4.checkbox("Resetear Metas de Usuarios")
        
        confirm_text = st.text_input("Escribe 'CONFIRMAR' para habilitar el borrado:")
        
        if st.button("Ejecutar Limpieza", type="primary", disabled=(confirm_text != "CONFIRMAR")):
            success = True
            
            if del_leads:
                if github_push_json('url_leads', [], st.session_state.get('leads_sha')):
                    st.session_state['leads_db'] = []
                    st.success("Leads eliminados.")
                else: success = False
            
            if del_cots:
                if github_push_json('url_cotizaciones', [], st.session_state.get('cotizaciones_sha')):
                    st.session_state['cotizaciones'] = pd.DataFrame(columns=st.session_state['cotizaciones'].columns)
                    st.success("Cotizaciones eliminadas.")
                else: success = False
            
            if del_teams or del_metas:
                # Modificamos el diccionario local de usuarios
                new_users = st.session_state['users_db'].copy()
                
                if del_teams:
                    new_users['_CONFIG_ORG'] = {} # Borrar equipos
                    # Limpiar asignaciones en usuarios
                    for k, v in new_users.items():
                        if k.startswith("_"): continue
                        v['equipo'] = []
                        v['sub_equipo'] = 'N/A'
                
                if del_metas:
                    for k, v in new_users.items():
                        if k.startswith("_"): continue
                        v['meta_rev'] = 0
                        v['metas_anuales'] = {}
                
                if github_push_json('url_usuarios', new_users, st.session_state.get('users_sha')):
                    sync_users_after_update()
                    st.success("Configuraciones de usuarios/equipos reseteadas.")
                else: success = False

            if success:
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                st.error("Hubo un error al intentar borrar algunos datos.")

# --- MENU LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    role = st.session_state.get('current_role', 'Comercial')
    # REORDERED MENU: Dashboard is now first
    opts = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas"]; icos = ['bar-chart', 'check', 'person', 'file', 'currency-dollar']
    if role == "Super Admin": opts.append("Usuarios"); icos.append("people")
    menu = option_menu("Menú", opts, icons=icos, default_index=0)
    if st.button("Salir"): logout()

if menu == "Seguimiento": modulo_seguimiento()
elif menu == "Prospectos y Clientes": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Dashboards": modulo_dashboard()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Usuarios": modulo_admin()
