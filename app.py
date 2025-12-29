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
st.set_page_config(
    page_title="TalentPRO CRM", 
    layout="wide", 
    page_icon="🔒", 
    initial_sidebar_state="expanded"
)

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
    /* Estilo General */
    .stApp {
        background-color: #f8fafd;
    }
    
    /* Contenedor de Login */
    .login-container {
        background-color: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        border: 1px solid #e1e8ed;
        text-align: center;
    }
    
    /* Botones con colores de la marca */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #5DADE2 0%, #003366 100%);
        color: white;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 10px;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        opacity: 0.9;
        transform: translateY(-1px);
        box-shadow: 0 5px 15px rgba(0,51,102,0.2);
    }
    
    /* Inputs */
    .stTextInput input {
        border-radius: 10px !important;
    }

    /* Sidebar y Métricas */
    .stMetric {background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 12px; box-shadow: 2px 2px 5px rgba(0,0,0,0.02);}
    
    /* ASEGURAR QUE EL SIDEBAR SEA VISIBLE */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e1e8ed;
        width: 300px !important;
    }

    /* Tarjetas de admin */
    .admin-card { padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #003366;}
    
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}
    
    /* Tutorial Styles */
    .tutorial-step {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #5DADE2;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
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
# 6. LOGIN & DATOS EXTERNOS
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
    st.markdown("""
        <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; 
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); z-index: -1;"></div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): 
                st.image(LOGO_PATH, use_container_width=True)
            
            st.markdown("<h4 style='color: #003366; margin-bottom: 2rem;'>CRM de Digitalización</h4>", unsafe_allow_html=True)
            
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("Usuario / Email", placeholder="ejemplo@talentpro.com")
                p = st.text_input("Contraseña", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("ACCEDER AL SISTEMA")
                
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
                                    st.success("¡Bienvenido!"); time.sleep(0.5); st.rerun()
                                else: st.error("⚠️ Credenciales incorrectas")
                            except Exception as e: st.error(f"Error de validación")
                        else: st.error("⚠️ Usuario no encontrado")
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 1rem;'>Expertos en Digitalización de RRHH</p>", unsafe_allow_html=True)

def logout(): st.session_state.clear(); st.rerun()

if not st.session_state['auth_status']: login_page(); st.stop()

# --- CONTINUACIÓN DEL CÓDIGO ---
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
        "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Servicios",
        "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total",
        "subtotal": "Subtotal", "fee": "Fee Admin", "discount": "Descuento", "bank": "Bank Fee",
        "legal_intl": "Facturación a {pais}. +Impostos retenidos +Gastos OUR.",
        "noshow_title": "Política No-Show:", "noshow_text": "Multa 50% inasistencia <24h.",
        "validity": "Validez 30 días"
    },
    "PT": {
        "title": "Cotação", "quote": "COTAÇÃO", "invoice_to": "Faturar para:",
        "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Serviços",
        "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total",
        "subtotal": "Subtotal", "fee": "Taxa Admin", "discount": "Desconto", "bank": "Taxa Bancária",
        "legal_intl": "Faturamento para {pais}. +Impostos retidos +Despesas OUR.",
        "noshow_title": "Política No-Show:", "noshow_text": "Multa de 50% por não comparecimento <24h.",
        "validity": "Validade 30 dias"
    },
    "EN": {
        "title": "Quotation", "quote": "QUOTATION", "invoice_to": "Bill to:",
        "client": "Client", "sec_prod": "Assessments", "sec_serv": "Services",
        "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total",
        "subtotal": "Subtotal", "fee": "Admin Fee", "discount": "Discount", "bank": "Bank Fee",
        "legal_intl": "Billing to {pais}. +Withholding taxes +OUR expenses.",
        "noshow_title": "No-Show Policy:", "noshow_text": "50% fine for non-attendance <24h.",
        "validity": "Validity 30 days"
    }
}

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939 , Andar 8, Tamboré", "Giro": "Atividades de consultoria em gestión empresarial, exceto consultoria técnica específica"},
    "Peru": {"Nombre": "TALENTPRO SOCIEDAD ANÓNIMA CERRADA", "ID": "RUC 20606246847", "Dir": "AVENIDA EL DERBY 254, SANTIAGO DE SURCO, LIMA, PERÚ", "Giro": "OTRAS ACTIVIDADES DE SERVICIOS DE APOYO A LAS EMPRESAS N.C.P"},
    "Chile_Pruebas": {"Nombre": "TALENTPRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile", "Giro": "Giro: Servicios de Reclutamiento y Selección de Personal"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile", "Giro": "Asesoría en Recursos Humanos"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2-2022 DV 27", "Dir": "CALLE 50, PH GLOBAL PLAZA, OFICINA 6D ,BELLA VISTA, PANAMÁ", "Giro": "Talent Acquisition Services"}
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

def get_user_teams_list(user_data):
    raw = user_data.get('equipo', [])
    if isinstance(raw, str):
        if raw == "N/A" or not raw: return []
        return [raw]
    return raw

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

# --- FUNCIÓN ANIMACIÓN LLUVIA DE DÓLARES ---
def lluvia_dolares():
    st.markdown("""
        <style>
        @keyframes fall {
            0% { transform: translateY(-10vh); opacity: 1; }
            100% { transform: translateY(110vh); opacity: 0; }
        }
        .money-rain {
            position: fixed;
            top: 0;
            font-size: 2.5rem;
            animation: fall linear forwards;
            z-index: 99999;
            pointer-events: none;
        }
        </style>
    """, unsafe_allow_html=True)
    html_content = ""
    for i in range(40):
        left = random.randint(0, 100)
        delay = random.uniform(0, 2)
        duration = random.uniform(2, 4)
        html_content += f'<div class="money-rain" style="left:{left}%; animation-delay:{delay}s; animation-duration:{duration}s;">💲</div>'
    st.markdown(html_content, unsafe_allow_html=True)

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================
# --- NUEVO MÓDULO TUTORIAL ---
def modulo_tutorial():
    st.title("📚 Centro de Ayuda y Tutoriales")
    st.markdown("Bienvenido a la guía rápida de **TalentPRO CRM**. Aquí encontrarás instrucciones paso a paso para utilizar cada módulo del sistema.")
    
    t1, t2, t3, t4, t5 = st.tabs(["1. Clientes (CRM)", "2. Cotizador", "3. Seguimiento", "4. Finanzas", "5. Dashboards"])
    
    with t1:
        st.markdown('<div class="tutorial-step">', unsafe_allow_html=True)
        st.markdown("### 📋 Gestión de Prospectos y Clientes")
        st.markdown("""
        Este módulo es el corazón de tu base de datos. Aquí puedes:
        1. **Crear Leads:** Ingresa nuevos prospectos en la pestaña "Gestión de Leads" > "Nuevo Lead".
        2. **Seguimiento:** Registra en qué etapa está el cliente (Prospección, Reunión, Propuesta).
        3. **Convertir a Cliente:** Cuando un lead compra, cambia su estado a "Cliente Activo".
        4. **Subir Propuestas:** Puedes adjuntar el PDF de la propuesta enviada al lead para tener el historial.
        5. **Clientes Históricos:** En la pestaña "Cartera Clientes", puedes registrar empresas que ya son clientes antiguos.
        """)
        st.info("💡 **Tip:** Mantén siempre actualizada la etapa del lead para que el embudo de ventas en el Dashboard sea real.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="tutorial-step">', unsafe_allow_html=True)
        st.markdown("### 💰 Generador de Cotizaciones")
        st.markdown("""
        Herramienta para crear propuestas formales en PDF de manera automática:
        1. **Configuración:** Selecciona el país (automáticamente ajusta moneda y entidad legal).
        2. **Cliente:** Elige un cliente existente o escribe uno nuevo (se guardará automáticamente como lead).
        3. **Agregar Ítems:**
           - **Assessments:** Selecciona el producto y cantidad. El sistema calcula el precio por volumen acumulado.
           - **Servicios:** Agrega servicios profesionales, horas de consultoría, etc.
        4. **Descuentos:** Puedes aplicar descuentos por monto fijo, porcentaje o simular un volumen mayor.
        5. **Generar:** Al hacer clic en GUARDAR, se genera un PDF descargable y se guarda el registro en el sistema.
        """)
        st.warning("⚠️ **Importante:** Si seleccionas Chile, el sistema generará dos PDFs separados si mezclas Productos (SpA) y Servicios (Ltda).")
        st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        st.markdown('<div class="tutorial-step">', unsafe_allow_html=True)
        st.markdown("### 🤝 Seguimiento Comercial")
        st.markdown("""
        Aquí gestionas las cotizaciones que ya enviaste:
        1. **Ver Estado:** Revisa si tus cotizaciones están "Enviadas", "Aprobadas" o "Rechazadas".
        2. **Cierre de Venta:** Cuando el cliente acepte, cambia el estado a **"Aprobada"**.
        3. **Requisitos:** Si el cliente requiere HES u Orden de Compra (OC), marca la casilla correspondiente.
        4. **Editar:** Si necesitas cambiar algo de una cotización enviada, usa el botón "✏️ Modificar/Clonar" para llevarla de vuelta al Cotizador.
        """)
        st.markdown('</div>', unsafe_allow_html=True)

    with t4:
        st.markdown('<div class="tutorial-step">', unsafe_allow_html=True)
        st.markdown("### 💵 Finanzas y Facturación")
        st.markdown("""
        Módulo para el equipo administrativo o para cerrar el ciclo de venta:
        1. **Por Facturar (Backlog):** Aquí aparecen todas las cotizaciones "Aprobadas".
        2. **Emitir Factura:**
           - Ingresa el número de OC y HES (si aplica).
           - Ingresa el número de Factura real.
           - **Sube el PDF de la factura** para respaldo.
           - Haz clic en "Emitir Factura".
        3. **Historial:** En la segunda pestaña verás todo lo facturado y podrás marcar si ya fue "Pagada".
        """)
        st.success("🎉 **Efecto:** Al emitir una factura, ¡verás una lluvia de dólares en la pantalla!")
        st.markdown('</div>', unsafe_allow_html=True)

    with t5:
        st.markdown('<div class="tutorial-step">', unsafe_allow_html=True)
        st.markdown("### 📊 Dashboards")
        st.markdown("""
        Visualiza el rendimiento del negocio:
        1. **Filtros:** Usa la barra lateral para filtrar por Año.
        2. **KPIs:** Revisa Ventas Totales, Pipeline, Tasa de Cierre.
        3. **Metas:** Cada vendedor puede ver su progreso vs la meta anual asignada.
        4. **Líderes:** Los líderes de célula pueden ver el rendimiento acumulado de su equipo.
        """)
        st.markdown('</div>', unsafe_allow_html=True)

def modulo_crm():
    st.title("📇 Prospectos y Clientes")
    tab1, tab2, tab_import = st.tabs(["📋 Gestión de Leads", "🏢 Cartera Clientes", "📥 Importar Masivo"])
    
    with tab1:
        # --- SECCIÓN CREAR LEAD ---
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
        
        # --- SECCIÓN GESTIONAR / EDITAR LEAD ---
        st.divider()
        st.subheader("🖊️ Gestionar / Editar Lead")
        
        # Filtro: Solo mostrar leads que NO sean clientes
        visible_leads = [l for l in st.session_state['leads_db'] if l.get('Etapa') not in ['Cliente Activo', 'Cerrado Ganado'] and l.get('Area') != 'Cartera']
        
        if not visible_leads:
            st.info("No hay leads activos (no clientes) registrados.")
        else:
            # Selector de Lead
            lead_names = [l.get('Cliente', 'Sin Nombre') for l in visible_leads]
            sel_lead_name = st.selectbox("Seleccionar Lead para gestionar", [""] + sorted(list(set(lead_names))))
            
            if sel_lead_name:
                # Buscar el lead en la base de datos COMPLETA para obtener su índice real
                lead_idx = next((i for i, d in enumerate(st.session_state['leads_db']) if d["Cliente"] == sel_lead_name), None)
                
                if lead_idx is not None:
                    lead_data = st.session_state['leads_db'][lead_idx]
                    
                    col_edit, col_info = st.columns([1, 1])
                    
                    with col_edit:
                        st.markdown("##### 📝 Editar Información")
                        with st.form(f"edit_lead_{lead_idx}"):
                            e_contacts = st.text_area("Contactos", value=lead_data.get('Contactos', ''))
                            # Opciones de Etapa Extendidas
                            e_etapa = st.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"], 
                                                   index=["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"].index(lead_data.get('Etapa', 'Prospección')) if lead_data.get('Etapa') in ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"] else 0)
                            e_expectativa = st.text_area("Expectativa / Dolor", value=lead_data.get('Expectativa', ''))
                            e_web = st.text_input("Web", value=lead_data.get('Web', ''))
                            
                            if st.form_submit_button("💾 Guardar Cambios"):
                                st.session_state['leads_db'][lead_idx]['Contactos'] = e_contacts
                                st.session_state['leads_db'][lead_idx]['Etapa'] = e_etapa
                                st.session_state['leads_db'][lead_idx]['Expectativa'] = e_expectativa
                                st.session_state['leads_db'][lead_idx]['Web'] = e_web
                                
                                if github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')):
                                    st.success("Lead actualizado correctamente."); time.sleep(1); st.rerun()
                                else:
                                    st.error("Error al actualizar en GitHub. Intente nuevamente (re-sincronizando).")

                    with col_info:
                        st.markdown(f"##### 📂 Historial de {sel_lead_name}")
                        
                        # 1. Mostrar Cotizaciones asociadas
                        df_cots = st.session_state['cotizaciones']
                        cots_lead = df_cots[df_cots['empresa'] == sel_lead_name]
                        
                        if not cots_lead.empty:
                            st.caption("Cotizaciones Realizadas:")
                            st.dataframe(cots_lead[['fecha', 'id', 'total', 'estado', 'vendedor']], use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay cotizaciones asociadas a este cliente.")
                            
                        st.divider()
                        
                        # 2. Subir Propuesta PDF
                        st.markdown("##### 📎 Propuesta Comercial")
                        
                        # Mostrar botón de descarga si ya existe archivo
                        if 'propuesta_file' in lead_data and lead_data['propuesta_file']:
                            try:
                                b64_file = lead_data['propuesta_file']
                                bin_file = base64.b64decode(b64_file)
                                st.download_button(label="📥 Descargar Propuesta Actual", data=bin_file, file_name=f"Propuesta_{sel_lead_name}.pdf", mime="application/pdf")
                            except:
                                st.error("Error al leer el archivo guardado.")

                        # Subir nuevo archivo
                        uploaded_propuesta = st.file_uploader("Subir/Actualizar PDF Propuesta", type=['pdf'], key=f"up_{lead_idx}")
                        if uploaded_propuesta is not None:
                            if st.button("Guardar Archivo"):
                                try:
                                    bytes_data = uploaded_propuesta.read()
                                    b64_str = base64.b64encode(bytes_data).decode()
                                    st.session_state['leads_db'][lead_idx]['propuesta_file'] = b64_str
                                    
                                    if github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')):
                                        st.success("Propuesta subida exitosamente."); time.sleep(1); st.rerun()
                                    else:
                                        st.error("Error al guardar archivo.")
                                except Exception as e:
                                    st.error(f"Error procesando archivo: {e}")

            st.divider()
            st.caption("Lista de leads visibles (No Clientes):")
            st.dataframe(pd.DataFrame(visible_leads), use_container_width=True)

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
        
        # --- FILTRO CLIENTES ---
        leads_db = st.session_state['leads_db']
        clients_from_db = [l['Cliente'] for l in leads_db if l.get('Etapa') in ['Cliente Activo', 'Cerrado Ganado'] or l.get('Area') == 'Cartera']
        df_cots = st.session_state['cotizaciones']
        clients_with_sales = df_cots[df_cots['estado'].isin(['Aprobada', 'Facturada'])]['empresa'].unique().tolist()
        real_clients_list = sorted(list(set(clients_from_db + clients_with_sales)))
        
        sel = st.selectbox("Ver Cliente 360 (Solo Clientes)", [""] + real_clients_list)
        
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
            
            # --- NUEVA SECCIÓN: EDICIÓN DATOS CLIENTE ---
            client_idx = next((i for i, l in enumerate(st.session_state['leads_db']) if l['Cliente'] == sel), None)
            if client_idx is not None:
                with st.expander("⚙️ Editar Datos del Cliente", expanded=False):
                    with st.form(f"form_edit_client_{client_idx}"):
                        c_data = st.session_state['leads_db'][client_idx]
                        col_e1, col_e2 = st.columns(2)
                        new_ind = col_e1.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"], index=["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"].index(c_data.get('Industria', 'Otros')) if c_data.get('Industria') in ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"] else 6)
                        new_web = col_e2.text_input("Web", value=c_data.get('Web', ''))
                        new_cont = st.text_area("Contactos", value=c_data.get('Contactos', ''))
                        
                        if st.form_submit_button("Actualizar Datos Cliente"):
                            st.session_state['leads_db'][client_idx]['Industria'] = new_ind
                            st.session_state['leads_db'][client_idx]['Web'] = new_web
                            st.session_state['leads_db'][client_idx]['Contactos'] = new_cont
                            
                            if github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')):
                                st.success("Cliente actualizado exitosamente")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Error al actualizar en GitHub")
            
            st.dataframe(dfc[['fecha','id','pais','total','estado','factura','pago']], use_container_width=True)

    with tab_import:
        st.subheader("Carga Masiva de Leads / Clientes (CSV)")
        st.markdown("##### 1. Descargar Plantilla")
        df_tem_lead = pd.DataFrame([{
            "Cliente":"Empresa ABC",
            "Area": "Cono Sur", 
            "Pais":"Chile",
            "Industria":"Tecnología",
            "Web": "www.empresa.com",
            "Contacto":"Juan Perez",
            "Email":"juan@abc.com",
            "Telefono": "+56912345678",
            "Origen":"Prospección del Usuario",
            "Etapa":"Prospección",
            "Expectativa": "Buscan evaluaciones psicométricas"
        }])
        csv_lead = df_tem_lead.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Plantilla Leads CSV", data=csv_lead, file_name="plantilla_leads_completa.csv", mime="text/csv")
        st.markdown("##### 2. Subir Archivo")
        uploaded_file = st.file_uploader("Subir CSV de Leads", type=["csv"])
        if uploaded_file is not None:
            try:
                try:
                    df_up = pd.read_csv(uploaded_file, sep=None, engine='python')
                except Exception:
                    uploaded_file.seek(0)
                    try:
                        df_up = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='latin-1')
                    except Exception:
                        uploaded_file.seek(0)
                        df_up = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                
                st.write("Vista Previa:", df_up.head())
                if st.button("Procesar Importación"):
                    new_entries = []
                    for _, row in df_up.iterrows():
                        contact_str = f"{row.get('Contacto','')} ({row.get('Email','')})"
                        if 'Telefono' in row and str(row['Telefono']) != 'nan':
                            contact_str += f" - Tel: {row['Telefono']}"

                        new_entries.append({
                            "id": int(time.time()) + random.randint(1, 1000),
                            "Cliente": row.get('Cliente', 'Sin Nombre'),
                            "Area": row.get('Area', 'Importado'),
                            "Pais": row.get('Pais', 'Desconocido'),
                            "Industria": row.get('Industria', 'Otros'),
                            "Web": str(row.get('Web', '')),
                            "Contactos": contact_str,
                            "Origen": row.get('Origen', 'Importación'),
                            "Etapa": row.get('Etapa', 'Prospección'),
                            "Expectativa": row.get('Expectativa', 'Importación Masiva'),
                            "Responsable": st.session_state['current_user'],
                            "Fecha": str(datetime.now().date())
                        })
                    final_db = st.session_state['leads_db'] + new_entries
                    if github_push_json('url_leads', final_db, st.session_state.get('leads_sha')):
                        st.session_state['leads_db'] = final_db
                        st.success(f"Se importaron {len(new_entries)} registros correctamente."); time.sleep(1); st.rerun()
                    else: st.error("Error al guardar en GitHub")
            except Exception as e: st.error(f"Error al leer el archivo: {e}")

def modulo_cotizador():
    # --- CHECK FOR EDIT MODE ---
    edit_data = st.session_state.get('cot_edit_data')
    if edit_data:
        st.info(f"✏️ MODO EDICIÓN: Estás modificando la cotización ID: {edit_data.get('id_orig')} - {edit_data.get('empresa')}")
        if st.button("❌ Cancelar Edición y Limpiar", type="secondary"):
            st.session_state['carrito'] = []
            st.session_state['cot_edit_data'] = None
            st.rerun()

    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES", "PT", "EN"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    c1,c2,c3,c4 = st.columns(4)
    v_uf = TASAS['UF']; v_usd = TASAS['USD_CLP']; v_brl = TASAS['USD_BRL']
    c1.metric("UF", f"${v_uf:,.0f}"); c2.metric("USD", f"${v_usd:,.0f}"); c3.metric("BRL", f"{v_brl:.2f}")
    if c4.button("Actualizar Tasas"): obtener_indicadores.clear(); st.rerun()
    if v_uf == 0 or v_usd == 0: st.error("⚠️ Error cargando indicadores. Intenta 'Actualizar Tasas'.")

    st.markdown("---"); c1, c2 = st.columns([1, 2])
    idx = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    
    # Pre-fill country if editing
    default_pais = edit_data.get('pais') if edit_data else None
    idx_p = TODOS_LOS_PAISES.index(default_pais) if default_pais in TODOS_LOS_PAISES else idx
    
    ps = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx_p); ctx = obtener_contexto(ps)
    c2.info(f"Moneda: **{ctx['mon']}** | Tarifas: **{ctx['tipo']}** {ctx.get('niv', '')}")
    st.markdown("---"); cc1,cc2,cc3,cc4=st.columns(4)
    
    # Lógica de asignación de equipo si el usuario tiene múltiples
    curr_user_data = st.session_state['users_db'].get(st.session_state['current_user'], {})
    user_teams = get_user_teams_list(curr_user_data)
    
    if len(user_teams) > 1:
        sel_team_cot = cc4.selectbox("Asignar a Célula", user_teams)
    elif len(user_teams) == 1:
        sel_team_cot = user_teams[0]
        cc4.text_input("Célula", value=sel_team_cot, disabled=True)
    else:
        sel_team_cot = "N/A"
        cc4.text_input("Célula", value="N/A", disabled=True)
        
    clientes_list = sorted(list(set([x['Cliente'] for x in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
    
    # --- MODIFICACIÓN: CLIENTE NUEVO DESDE COTIZADOR ---
    use_new_client = cc1.checkbox("¿Cliente Nuevo?", value=False)
    
    default_emp = edit_data.get('empresa') if edit_data else ""
    default_con = edit_data.get('contacto') if edit_data else ""
    default_ema = edit_data.get('email') if edit_data else ""
    
    if use_new_client:
        emp = cc1.text_input(txt['client'], placeholder="Nombre Empresa", value=default_emp)
    else:
        idx_cli = clientes_list.index(default_emp) if default_emp in clientes_list else 0
        emp = cc1.selectbox(txt['client'], [""] + clientes_list, index=idx_cli + 1 if default_emp in clientes_list else 0)

    con = cc2.text_input("Contacto", value=default_con); ema = cc3.text_input("Email", value=default_ema)
    ven = cc4.text_input("Ejecutivo", value=st.session_state['users_db'][st.session_state['current_user']].get('name',''), disabled=True)
    st.markdown("---"); tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4 = st.columns([3,1,1,1]); lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp,key="p1"); qp=c2.number_input("Cant",1,10000,10,key="q1")
            
            # --- MODIFICACIÓN: CÁLCULO DE PRECIO POR VOLUMEN ACUMULADO ---
            # 1. Calcular cuántas evaluaciones hay YA en el carrito
            cant_actual_carrito = 0
            for item in st.session_state['carrito']:
                if item['Ítem'] == 'Evaluación':
                    try:
                        # Parseamos la cantidad desde el string "x500" o similar
                        q_str = str(item['Det']).replace('x', '').strip().split('(')[0]
                        cant_actual_carrito += int(q_str)
                    except: pass
            
            # 2. El volumen total para calcular el precio es (lo del carrito + lo nuevo)
            volumen_total_calculo = cant_actual_carrito + qp
            
            # 3. Obtener precio unitario basado en ese volumen total
            up = calc_xls(ctx['dp'], sp, volumen_total_calculo, ctx['tipo']=='Loc')
            
            c3.metric("Unit", f"{up:,.2f}")
            if volumen_total_calculo != qp:
                c3.caption(f"Precio por volumen total ({volumen_total_calculo})")
            
            if c4.button("Add", key="b1"): 
                # Agregar el nuevo ítem
                st.session_state['carrito'].append({
                    "Ítem": "Evaluación", 
                    "Desc": sp, 
                    "Det": f"x{qp}", 
                    "Moneda": ctx['mon'], 
                    "Unit": up, 
                    "Total": up*qp
                })
                
                # --- MODIFICACIÓN: ACTUALIZAR PRECIOS DE ÍTEMS ANTERIORES ---
                # Recorrer el carrito y actualizar el precio unitario de TODAS las evaluaciones
                # basado en el nuevo volumen total alcanzado.
                new_total_qty = cant_actual_carrito + qp
                for i, item in enumerate(st.session_state['carrito']):
                    if item['Ítem'] == 'Evaluación':
                        try:
                            prod_name = item['Desc']
                            q_item_str = str(item['Det']).replace('x', '').strip().split('(')[0]
                            q_item = int(q_item_str)
                            
                            # Recalcular precio unitario con el gran total
                            new_up = calc_xls(ctx['dp'], prod_name, new_total_qty, ctx['tipo']=='Loc')
                            
                            # Actualizar en sesión
                            st.session_state['carrito'][i]['Unit'] = new_up
                            st.session_state['carrito'][i]['Total'] = new_up * q_item
                        except: pass
                
                st.rerun()

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
            # Recuperar valores si estamos editando
            def_fee = False
            def_bank = 0.0
            def_dsc_name = "Descuento"
            def_dsc_val = 0.0
            
            if edit_data:
                # Intentar mapear fee y bank
                if edit_data.get('fee', 0) > 0: def_fee = True
                def_bank = float(edit_data.get('bank', 0))
                def_dsc_name = edit_data.get('desc_name', "Descuento")
                def_dsc_val = float(edit_data.get('desc', 0))

            fee=st.checkbox("Fee 10%", value=def_fee); bnk=st.number_input("Bank", value=def_bank)
            
            # --- MODIFICACIÓN: Lógica de Descuento Avanzada ---
            st.markdown("##### Descuento")
            dsc_name = st.text_input("Glosa Descuento", value=def_dsc_name)
            
            # Si hay un descuento cargado, lo mostramos como Monto Fijo por defecto para simplificar la edición
            idx_desc_type = 0 if def_dsc_val == 0 else 0 # Default a monto fijo si editamos
            tipo_desc = st.selectbox("Tipo de Descuento", ["Monto Fijo ($)", "Porcentaje (%)", "Simular Volumen (Precio por Tramo)"], key="sel_tipo_desc", index=idx_desc_type)
            
            dsc = 0.0
            if tipo_desc == "Monto Fijo ($)":
                val_init = def_dsc_val if def_dsc_val > 0 else 0.0
                dsc = st.number_input("Monto Desc", value=val_init, step=100.0, key="in_monto_desc")
            elif tipo_desc == "Porcentaje (%)":
                pct_val = st.number_input("Porcentaje %", 0.0, 100.0, 0.0, step=1.0, key="in_pct_desc")
                dsc = sub * (pct_val / 100)
                st.caption(f"Desc: {ctx['mon']} {dsc:,.2f}")
            else: # Simular Volumen (Precio por Tramo)
                st.caption("Aplica el precio unitario correspondiente a un volumen mayor.")
                vol_sim = st.number_input("Volumen a Simular (Cant. Total)", min_value=1, value=1000, step=10, key="in_vol_sim")
                
                # Calcular el descuento comparando el precio real vs el precio simulado
                total_simulado = 0.0
                total_actual_evals = 0.0
                
                for item in st.session_state['carrito']:
                    if item['Ítem'] == 'Evaluación':
                        try:
                            # Obtener cantidad del ítem
                            q_str = str(item['Det']).replace('x', '').strip().split('(')[0]
                            qty = int(q_str)
                            
                            # Precio unitario al volumen simulado
                            unit_sim = calc_xls(ctx['dp'], item['Desc'], vol_sim, ctx['tipo']=='Loc')
                            
                            total_simulado += unit_sim * qty
                            total_actual_evals += item['Total']
                        except: pass
                
                # El descuento es la diferencia entre lo que vale ahora y lo que valdría con el precio simulado
                diff = total_actual_evals - total_simulado
                dsc = diff if diff > 0 else 0.0
                
                st.caption(f"Ahorro por volumen: {ctx['mon']} {dsc:,.2f}")
            # --------------------------------------------------

            vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-dsc
            st.metric("TOTAL",f"{ctx['mon']} {fin:,.2f}")
            
            # --- BOTONES DE ACCIÓN (GUARDAR / EDITAR) ---
            
            def guardar_cotizacion(es_update=False):
                if not emp: st.error("Falta Empresa"); return
                
                # --- AUTO CREAR LEAD SI NO EXISTE ---
                current_leads = st.session_state['leads_db']
                exists = any(l['Cliente'].lower() == emp.lower() for l in current_leads)
                
                if not exists and emp:
                    new_auto_lead = {
                        "id": int(time.time()),
                        "Cliente": emp,
                        "Area": "Auto-Creado",
                        "Pais": ps,
                        "Industria": "Otros",
                        "Web": "",
                        "Contactos": f"{con} ({ema})",
                        "Origen": "Cotizador",
                        "Etapa": "Propuesta",
                        "Expectativa": "Generado desde Cotizador",
                        "Responsable": st.session_state['current_user'],
                        "Fecha": str(datetime.now().date())
                    }
                    st.session_state['leads_db'].append(new_auto_lead)
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))

                # ID Logic
                if es_update and edit_data:
                    nid = edit_data['id_orig']
                else:
                    nid=f"TP-{random.randint(1000,9999)}"

                cli={'empresa':emp,'contacto':con,'email':ema}
                ext={'fee':vfee,'bank':bnk,'desc':dsc,'desc_name':dsc_name, 'pais':ps,'id':nid}
                
                # Generación PDF (Solo visualización/link, la lógica interna no cambia)
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
                else:
                    ent = get_empresa(ps, st.session_state['carrito'])
                    calc = {'subtotal':sub, 'fee':vfee, 'tax_name':tn, 'tax_val':tv, 'total':fin}
                    pdf = generar_pdf_final(ent, cli, st.session_state['carrito'], calc, idi, ext)
                    b64 = base64.b64encode(pdf).decode('latin-1')
                    links_html = f'<a href="data:application/pdf;base64,{b64}" download="Cot_{nid}.pdf">📄 Descargar PDF</a>'

                st.success("✅ Cotización generada/actualizada")
                st.markdown(links_html, unsafe_allow_html=True)
                
                # Guardar Dataframe
                row_data = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':ven, 'equipo_asignado': sel_team_cot, 'oc':'', 'factura':'', 'pago':'Pendiente', 'hes':False, 'hes_num':'', 'items': st.session_state['carrito'], 'pdf_data': ext, 'idioma': idi, 'factura_file': None}
                
                df_cots = st.session_state['cotizaciones']
                if es_update:
                    # Update row
                    idx = df_cots[df_cots['id'] == nid].index
                    if not idx.empty:
                        for k, v in row_data.items():
                            if k != 'factura_file': # No sobrescribir factura si existe
                                df_cots.at[idx[0], k] = v
                    else:
                        st.error("No se encontró el ID original para actualizar.")
                        return
                else:
                    # Append new
                    st.session_state['cotizaciones'] = pd.concat([df_cots, pd.DataFrame([row_data])], ignore_index=True)

                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    st.info("Guardado en Base de Datos")
                    st.session_state['carrito']=[]
                    st.session_state['cot_edit_data'] = None # Clear edit mode
                    time.sleep(2)
                    st.rerun()
                else: st.warning("Error al sincronizar con GitHub")

            if edit_data:
                col_upd, col_clon = st.columns(2)
                if col_upd.button("🔄 Actualizar Cotización Original"):
                    guardar_cotizacion(es_update=True)
                if col_clon.button("💾 Guardar como Nueva (Clon)"):
                    guardar_cotizacion(es_update=False)
            else:
                if st.button("GUARDAR", type="primary"):
                    guardar_cotizacion(es_update=False)

        with cL: 
            if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial (Ventas)")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("Sin datos."); return
    df = df.sort_values('fecha', ascending=False)
    curr_user = st.session_state['current_user']
    curr_role = st.session_state.get('current_role', 'Comercial')
    if curr_role == 'Comercial':
        my_team = st.session_state['users_db'][curr_user].get('equipo', 'N/A')
        team_names = [u['name'] for k, u in st.session_state['users_db'].items() if u.get('equipo') == my_team]
        df = df[df['vendedor'].isin(team_names)]
    c1, c2 = st.columns([3, 1])
    with c1: st.info("ℹ️ Gestión: Cambia estado a 'Aprobada' para que Finanzas facture.")
    with c2: ver_historial = st.checkbox("📂 Ver Historial Completo", value=False)
    if not ver_historial:
        df = df[df['estado'].isin(['Enviada', 'Aprobada'])]
        if df.empty: st.warning("No tienes cotizaciones abiertas.")
    for i, r in df.iterrows():
        lang_tag = f"[{r.get('idioma','ES')}]"
        team_tag = f"({r.get('equipo_asignado', 'N/A')})"
        label = f"{lang_tag} {team_tag} {r['fecha']} | {r['id']} | {r['empresa']} | {r['moneda']} {r['total']:,.0f}"
        if r['estado'] == 'Facturada': label += " ✅ (Facturada)"
        elif r['estado'] == 'Aprobada': label += " 🎉 (Cerrada)"
        elif r['estado'] == 'Enviada': label += " ⏳ (En Negociación)"
        with st.expander(label):
            col_status, col_req, col_act = st.columns([2, 2, 1])
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
            with col_act:
                st.caption("Acciones")
                if st.button("✏️ Modificar / Clonar", key=f"edit_btn_{r['id']}"):
                    # Extraer datos para edición
                    pdf_data = r.get('pdf_data', {}) if isinstance(r.get('pdf_data'), dict) else {}
                    st.session_state['carrito'] = r.get('items', [])
                    st.session_state['cot_edit_data'] = {
                        'id_orig': r['id'],
                        'empresa': r['empresa'],
                        'pais': r['pais'],
                        'contacto': pdf_data.get('contacto', ''),
                        'email': pdf_data.get('email', ''),
                        'fee': pdf_data.get('fee', 0),
                        'bank': pdf_data.get('bank', 0),
                        'desc': pdf_data.get('desc', 0),
                        'desc_name': pdf_data.get('desc_name', 'Descuento')
                    }
                    st.session_state['menu_idx'] = 3 # Índice del Cotizador
                    st.rerun()

            if not disabled_st and st.button("Actualizar Estado", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_status
                st.session_state['cotizaciones'].at[i, 'hes'] = hes_check
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    if new_status == 'Aprobada': st.balloons() # --- MODIFICACIÓN: GLOBOS AL APROBAR ---
                    st.success("Actualizado"); time.sleep(1); st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No hay datos."); return
    
    # Aseguramos que exista la columna para el archivo de la factura
    if 'factura_file' not in df.columns:
        df['factura_file'] = None
        st.session_state['cotizaciones'] = df

    tab_billing, tab_collection = st.tabs(["📝 Por Facturar (Backlog)", "💵 Historial Facturadas"])
    
    # --- PESTAÑA 1: POR FACTURAR ---
    with tab_billing:
        st.subheader("Pendientes de Facturación")
        to_bill = df[df['estado'] == 'Aprobada']
        if to_bill.empty: st.success("¡Excelente! No hay pendientes.")
        else:
            for i, r in to_bill.iterrows():
                with st.container(border=True): # Usamos un borde para separar cada ítem
                    lang_tag = f"[{r.get('idioma','ES')}]"
                    st.markdown(f"**{lang_tag} {r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']:,.0f}")
                    
                    if r.get('hes'): st.error("🚨 REQUISITO: Esta venta requiere N° HES o MIGO.")
                    
                    # Generación de Links PDF (Código original mantenido)
                    if r.get('items') and isinstance(r['items'], list):
                        cli = {'empresa':r['empresa'], 'contacto':'', 'email':''} 
                        ext = r.get('pdf_data', {'id':r['id'], 'pais':r['pais'], 'bank':0, 'desc':0})
                        prod_items = [x for x in r['items'] if x['Ítem']=='Evaluación']
                        serv_items = [x for x in r['items'] if x['Ítem']=='Servicio']
                        idi_saved = r.get('idioma', 'ES')
                        pdf_links = ""
                        if r['pais'] == "Chile" and prod_items and serv_items:
                             sub_p = sum(x['Total'] for x in prod_items); tax_p = sub_p*0.19; tot_p = sub_p*1.19
                             calc_p = {'subtotal':sub_p, 'fee':0, 'tax_name':"IVA", 'tax_val':tax_p, 'total':tot_p}
                             pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli, prod_items, calc_p, idi_saved, ext)
                             b64_p = base64.b64encode(pdf_p).decode('latin-1')
                             sub_s = sum(x['Total'] for x in serv_items); tot_s = sub_s
                             calc_s = {'subtotal':sub_s, 'fee':0, 'tax_name':"", 'tax_val':0, 'total':tot_s}
                             pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli, serv_items, calc_s, idi_saved, ext)
                             b64_s = base64.b64encode(pdf_s).decode('latin-1')
                             pdf_links = f'<a href="data:application/pdf;base64,{b64_p}" download="Cot_{r["id"]}_P.pdf">📄 Ver PDF SpA ({idi_saved})</a> | <a href="data:application/pdf;base64,{b64_s}" download="Cot_{r["id"]}_S.pdf">📄 Ver PDF Ltda ({idi_saved})</a>'
                        else:
                             ent = get_empresa(r['pais'], r['items']); sub = sum(x['Total'] for x in r['items']); tn, tv = get_impuestos(r['pais'], sub, sub); calc = {'subtotal':sub, 'fee':0, 'tax_name':tn, 'tax_val':tv, 'total':r['total']}
                             pdf = generar_pdf_final(ent, cli, r['items'], calc, idi_saved, ext)
                             b64 = base64.b64encode(pdf).decode('latin-1')
                             pdf_links = f'<a href="data:application/pdf;base64,{b64}" download="Cot_{r["id"]}.pdf">📄 Ver PDF Cotización ({idi_saved})</a>'
                        st.markdown(pdf_links, unsafe_allow_html=True)
                    else: st.warning("⚠️ PDF no disponible.")
                    
                    # --- NUEVA FUNCIONALIDAD: SUBIR FACTURA ---
                    col_file, col_dummy = st.columns([1, 1])
                    uploaded_invoice = col_file.file_uploader("📂 Subir PDF Factura Emitida", type=['pdf'], key=f"up_inv_{r['id']}")

                    # Campos de input existentes
                    c1, c2, c3, c4 = st.columns(4)
                    new_oc = c1.text_input("OC", value=r.get('oc',''), key=f"oc_{r['id']}")
                    new_hes_num = c2.text_input("N° HES", value=r.get('hes_num',''), key=f"hnum_{r['id']}")
                    new_inv = c3.text_input("N° Factura", key=f"inv_{r['id']}")
                    
                    if c4.button("Emitir Factura", key=f"bill_{r['id']}", type="primary"):
                        if not new_inv: 
                            st.error("Falta N° Factura")
                            continue
                        
                        # Guardar datos básicos
                        st.session_state['cotizaciones'].at[i, 'oc'] = new_oc
                        st.session_state['cotizaciones'].at[i, 'hes_num'] = new_hes_num
                        st.session_state['cotizaciones'].at[i, 'factura'] = new_inv
                        st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                        
                        # Guardar archivo PDF de factura si se subió
                        if uploaded_invoice:
                            try:
                                inv_b64 = base64.b64encode(uploaded_invoice.read()).decode()
                                st.session_state['cotizaciones'].at[i, 'factura_file'] = inv_b64
                            except Exception as e:
                                st.error(f"Error al procesar el archivo: {e}")

                        # Sync Github
                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            lluvia_dolares() # <--- EFECTO DE LLUVIA DE DÓLARES
                            st.success(f"Factura {new_inv} emitida correctamente!"); 
                            time.sleep(3); st.rerun()
    
    # --- PESTAÑA 2: HISTORIAL ---
    with tab_collection:
        st.subheader("Historial y Cobranza")
        billed = df[df['estado'] == 'Facturada'].copy()
        if billed.empty: st.info("No hay historial.")
        else:
            st.dataframe(billed[['fecha', 'id', 'empresa', 'total', 'moneda', 'oc', 'hes_num', 'factura', 'pago']], use_container_width=True)
            st.markdown("---"); st.subheader("🔧 Gestión de Factura")
            inv_list = billed['factura'].unique().tolist()
            sel_inv = st.selectbox("Seleccionar N° Factura", inv_list)
            
            if sel_inv:
                # Obtenemos la fila correspondiente
                row_idx = df[df['factura'] == sel_inv].index[0]
                r_sel = st.session_state['cotizaciones'].iloc[row_idx]
                
                # --- ZONA DE DESCARGA DE DOCUMENTOS ---
                st.markdown("##### 📂 Documentación Disponible")
                col_d_inv, col_d_quote = st.columns(2)
                
                # 1. Descargar Factura (si existe)
                with col_d_inv:
                    if 'factura_file' in r_sel and r_sel['factura_file']:
                        try:
                            b64_file = r_sel['factura_file']
                            if b64_file:
                                bin_file = base64.b64decode(b64_file)
                                st.download_button(
                                    label=f"📥 Descargar Factura {sel_inv} (PDF)",
                                    data=bin_file,
                                    file_name=f"Factura_{sel_inv}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                        except: st.error("Error al descargar factura.")
                    else:
                        st.warning("Sin archivo de factura adjunto.")

                # 2. Descargar Cotización Original
                with col_d_quote:
                    if r_sel.get('items') and isinstance(r_sel['items'], list):
                        try:
                            cli_q = {'empresa':r_sel['empresa'], 'contacto':'', 'email':''} 
                            ext_q = r_sel.get('pdf_data', {'id':r_sel['id'], 'pais':r_sel['pais'], 'bank':0, 'desc':0})
                            idi_q = r_sel.get('idioma', 'ES')
                            
                            # Lógica para Chile (Separado) o General
                            prod_items_q = [x for x in r_sel['items'] if x['Ítem']=='Evaluación']
                            serv_items_q = [x for x in r_sel['items'] if x['Ítem']=='Servicio']

                            if r_sel['pais'] == "Chile" and prod_items_q and serv_items_q:
                                sub_p = sum(x['Total'] for x in prod_items_q); tax_p = sub_p*0.19; tot_p = sub_p*1.19
                                calc_p = {'subtotal':sub_p, 'fee':0, 'tax_name':"IVA", 'tax_val':tax_p, 'total':tot_p}
                                pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli_q, prod_items_q, calc_p, idi_q, ext_q)
                                
                                sub_s = sum(x['Total'] for x in serv_items_q); tot_s = sub_s
                                calc_s = {'subtotal':sub_s, 'fee':0, 'tax_name':"", 'tax_val':0, 'total':tot_s}
                                pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli_q, serv_items_q, calc_s, idi_q, ext_q)
                                
                                col_q1, col_q2 = st.columns(2)
                                col_q1.download_button("📄 Cot. Productos (SpA)", pdf_p, file_name=f"Cot_{r_sel['id']}_Prod.pdf", mime="application/pdf")
                                col_q2.download_button("📄 Cot. Servicios (Ltda)", pdf_s, file_name=f"Cot_{r_sel['id']}_Serv.pdf", mime="application/pdf")
                            else:
                                ent_q = get_empresa(r_sel['pais'], r_sel['items']); sub_q = sum(x['Total'] for x in r_sel['items']); tn, tv = get_impuestos(r_sel['pais'], sub_q, sub_q); calc_q = {'subtotal':sub_q, 'fee':0, 'tax_name':tn, 'tax_val':tv, 'total':r_sel['total']}
                                pdf_q = generar_pdf_final(ent_q, cli_q, r_sel['items'], calc_q, idi_q, ext_q)
                                st.download_button("📄 Descargar Cotización Original", pdf_q, file_name=f"Cot_{r_sel['id']}.pdf", mime="application/pdf", use_container_width=True)
                        except Exception as e: st.error(f"Error generando cotización: {e}")

                st.markdown("---")

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
                    
                    # Permite reemplazar el archivo si se equivocaron
                    up_replace = st.file_uploader("Reemplazar PDF Factura (Opcional)", type=['pdf'], key="rep_pdf")

                    if st.button("Guardar Correcciones"):
                        st.session_state['cotizaciones'].at[row_idx, 'oc'] = e_oc
                        st.session_state['cotizaciones'].at[row_idx, 'hes_num'] = e_hes
                        st.session_state['cotizaciones'].at[row_idx, 'factura'] = e_inv
                        
                        if up_replace:
                             b64_rep = base64.b64encode(up_replace.read()).decode()
                             st.session_state['cotizaciones'].at[row_idx, 'factura_file'] = b64_rep

                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            st.success("Datos corregidos"); time.sleep(1); st.rerun()
                with t3:
                    st.error("⚠️ CUIDADO: Esto eliminará la factura y devolverá la cotización a la pestaña 'Por Facturar'.")
                    if st.button("🗑️ Eliminar Factura (Revertir a Backlog)"):
                        st.session_state['cotizaciones'].at[row_idx, 'estado'] = 'Aprobada'
                        st.session_state['cotizaciones'].at[row_idx, 'factura'] = ''
                        st.session_state['cotizaciones'].at[row_idx, 'pago'] = 'Pendiente'
                        # Limpiamos el archivo si se revierte
                        st.session_state['cotizaciones'].at[row_idx, 'factura_file'] = None 
                        
                        if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                            st.success("Factura eliminada."); time.sleep(1); st.rerun()

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

    # --- DEFINICIÓN DE PESTAÑAS (MODIFICADO PARA SUPER ADMIN) ---
    tabs_names = ["📊 General", "🎯 Metas y Desempeño", "📇 Leads (Funnel)", "📈 Cierre Ventas", "💵 Facturación"]
    
    # Si es Super Admin, agregamos la pestaña global al principio
    if curr_role == 'Super Admin':
        tabs_names.insert(0, "🌍 Visión Global (Admin)")
        
    all_tabs = st.tabs(tabs_names)
    
    # Lógica para asignar contenido a cada pestaña
    idx_offset = 1 if curr_role == 'Super Admin' else 0
    
    # --- PESTAÑA: VISIÓN GLOBAL (SOLO SUPER ADMIN) ---
    if curr_role == 'Super Admin':
        with all_tabs[0]:
            st.markdown("### 🌍 Visión Global de la Empresa")
            
            # Cálculo de Métricas Globales
            if not df_cots_filtered.empty:
                df_cots_filtered['Total_USD_Global'] = df_cots_filtered.apply(convert_to_usd, axis=1)
                
                # 1. Ventas Totales (Facturada)
                global_sales = df_cots_filtered[df_cots_filtered['estado'] == 'Facturada']['Total_USD_Global'].sum()
                
                # 2. Pipeline Total (Enviada + Aprobada)
                global_pipeline = df_cots_filtered[df_cots_filtered['estado'].isin(['Enviada', 'Aprobada'])]['Total_USD_Global'].sum()
                
                # 3. Forecast (Aprobada + Facturada)
                global_forecast = df_cots_filtered[df_cots_filtered['estado'].isin(['Aprobada', 'Facturada'])]['Total_USD_Global'].sum()
                
                c_g1, c_g2, c_g3 = st.columns(3)
                c_g1.metric("Ventas Totales (USD)", f"${global_sales:,.0f}")
                c_g2.metric("Pipeline Abierto (USD)", f"${global_pipeline:,.0f}")
                c_g3.metric("Forecast Total (Cerrado + Facturado)", f"${global_forecast:,.0f}")
                
                st.divider()
                
                # 4. Gráfico Comparativo por Equipos (Células)
                st.subheader("🏆 Comparativa por Equipos")
                
                # Agrupar por equipo_asignado
                if 'equipo_asignado' in df_cots_filtered.columns:
                    df_team_perf = df_cots_filtered[df_cots_filtered['estado'] == 'Facturada'].groupby('equipo_asignado')['Total_USD_Global'].sum().reset_index()
                    df_team_perf.columns = ['Equipo', 'Venta Total (USD)']
                    df_team_perf = df_team_perf.sort_values('Venta Total (USD)', ascending=False)
                    
                    if not df_team_perf.empty:
                        fig_teams = px.bar(df_team_perf, x='Equipo', y='Venta Total (USD)', color='Equipo', title="Ventas por Célula (USD)", text_auto='.2s')
                        st.plotly_chart(fig_teams, use_container_width=True)
                    else:
                        st.info("No hay ventas facturadas para mostrar comparativa.")
                
                st.divider()
                
                # 5. Visión Detallada por Equipo (Drill-down)
                st.subheader("🔍 Detalle por Célula")
                equipos_disponibles = df_cots_filtered['equipo_asignado'].unique().tolist() if 'equipo_asignado' in df_cots_filtered.columns else []
                sel_team_global = st.selectbox("Seleccionar Equipo para ver detalle:", ["Todos"] + sorted([str(x) for x in equipos_disponibles]))
                
                df_view = df_cots_filtered.copy()
                if sel_team_global != "Todos":
                    df_view = df_view[df_view['equipo_asignado'] == sel_team_global]
                
                # Mostrar KPIs del equipo seleccionado
                t_sales = df_view[df_view['estado'] == 'Facturada']['Total_USD_Global'].sum()
                t_pipe = df_view[df_view['estado'].isin(['Enviada', 'Aprobada'])]['Total_USD_Global'].sum()
                t_cnt = len(df_view[df_view['estado'] == 'Facturada'])
                
                k1, k2, k3 = st.columns(3)
                k1.metric(f"Ventas {sel_team_global}", f"${t_sales:,.0f}")
                k2.metric(f"Pipeline {sel_team_global}", f"${t_pipe:,.0f}")
                k3.metric("Cant. Cierres", t_cnt)
                
                st.caption("Desglose de Cotizaciones del Equipo:")
                st.dataframe(df_view[['fecha', 'empresa', 'total', 'moneda', 'estado', 'vendedor']], use_container_width=True, hide_index=True)

            else:
                st.info("No hay datos para generar la visión global.")

    # --- RESTO DE PESTAÑAS (IGUAL QUE ANTES) ---
    # Usamos all_tabs[idx_offset + i] para acceder a la pestaña correcta
    
    with all_tabs[idx_offset + 0]: # General
        df_open = df_cots_filtered[df_cots_filtered['estado'].isin(['Enviada', 'Aprobada'])].copy()
        cant_abiertas = len(df_open)
        monto_abierto_usd = 0
        if not df_open.empty:
             df_open['Total_USD'] = df_open.apply(convert_to_usd, axis=1)
             monto_abierto_usd = df_open['Total_USD'].sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Leads", len(df_leads_filtered))
        c2.metric("Cotizaciones Abiertas", cant_abiertas) 
        c3.metric("Pipeline (USD)", f"${monto_abierto_usd:,.0f}")
        total_ops = len(df_cots_filtered); won_ops = len(df_cots_filtered[df_cots_filtered['estado'].isin(['Aprobada','Facturada'])])
        win_rate = (won_ops/total_ops*100) if total_ops > 0 else 0
        c4.metric("Tasa de Cierre", f"{win_rate:.1f}%")
        facturado = df_cots_filtered[df_cots_filtered['estado']=='Facturada']['total'].sum() if not df_cots_filtered.empty else 0
        c5.metric("Total Facturado", f"${facturado:,.0f}")
        st.divider()
        if not df_cots_filtered.empty:
            fig = px.pie(df_cots_filtered, names='estado', title="Distribución Estado Cotizaciones")
            st.plotly_chart(fig, use_container_width=True)
            
    with all_tabs[idx_offset + 1]: # Metas
        st.subheader("Desempeño Individual vs Metas")
        user_data = users.get(curr_email, {})
        my_team = user_data.get('equipo', 'Sin Equipo')
        df_my_sales = df_cots_filtered[(df_cots_filtered['vendedor'] == user_data.get('name','')) & (df_cots_filtered['estado'] == 'Facturada')]
        def get_cat(m): return clasificar_cliente(m)
        if not df_my_sales.empty:
            df_my_sales['Categoria'] = df_my_sales['total'].apply(get_cat)
            my_rev = df_my_sales['total'].sum(); cnt_big = len(df_my_sales[df_my_sales['Categoria']=='Grande'])
            cnt_mid = len(df_my_sales[df_my_sales['Categoria']=='Mediano']); cnt_sml = len(df_my_sales[df_my_sales['Categoria']=='Chico'])
        else: my_rev = 0; cnt_big=0; cnt_mid=0; cnt_sml=0

        u_metas = user_data.get('metas_anuales', {})
        goal_rev = sum(float(u_metas.get(str(y), {}).get('rev', 0)) for y in selected_years)
        goal_big = sum(int(u_metas.get(str(y), {}).get('big', 0)) for y in selected_years)
        goal_mid = sum(int(u_metas.get(str(y), {}).get('mid', 0)) for y in selected_years)
        goal_sml = sum(int(u_metas.get(str(y), {}).get('sml', 0)) for y in selected_years)
        if goal_rev == 0: goal_rev = float(user_data.get('meta_rev', 0))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"#### 👤 Mis Resultados ({user_data.get('name','')})")
            if goal_rev > 0: st.progress(min(my_rev/goal_rev, 1.0), text=f"Facturación: ${my_rev:,.0f} / ${goal_rev:,.0f} USD ({my_rev/goal_rev*100:.1f}%)")
            else: st.info("Sin meta asignada.")
            c_a, c_b, c_c = st.columns(3)
            c_a.metric("Grandes", f"{cnt_big}/{goal_big}"); c_b.metric("Medianos", f"{cnt_mid}/{goal_mid}"); c_c.metric("Chicos", f"{cnt_sml}/{goal_sml}")

        with c2:
            my_teams = get_user_teams_list(user_data)
            if my_teams:
                for team_name in my_teams:
                    st.markdown(f"#### 🏆 Célula: {team_name}")
                    team_config_db = users.get('_CONFIG_ORG', {})
                    team_goal_rev = 0
                    if isinstance(team_config_db.get(team_name), dict):
                        t_metas = team_config_db[team_name].get('metas_anuales', {})
                        team_goal_rev = sum(float(t_metas.get(str(y), 0)) for y in selected_years)
                        if team_goal_rev == 0: team_goal_rev = float(team_config_db[team_name].get('meta', 0))
                    
                    team_members = [d['name'] for e,d in users.items() if team_name in get_user_teams_list(d)]
                    df_team_sales = df_cots_filtered[(df_cots_filtered['vendedor'].isin(team_members)) & (df_cots_filtered['estado'] == 'Facturada')].copy()
                    
                    if not df_team_sales.empty:
                        df_team_sales['Total_USD'] = df_team_sales.apply(convert_to_usd, axis=1)
                        team_rev = df_team_sales['Total_USD'].sum()
                    else: team_rev = 0
                    
                    if team_goal_rev > 0:
                        st.progress(min(team_rev/team_goal_rev, 1.0), text=f"Meta: ${team_rev:,.0f} / ${team_goal_rev:,.0f} USD")
                    else: st.info(f"Sin meta global definida.")
            else:
                st.info("Usuario sin célula asignada.")
    
    with all_tabs[idx_offset + 2]: # Leads
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
        
    with all_tabs[idx_offset + 3]: # Cierre Ventas
        if not df_cots_filtered.empty:
            df_sales = df_cots_filtered[df_cots_filtered['estado'].isin(['Aprobada','Facturada'])]
            if not df_sales.empty:
                st.subheader("Evolución de Ventas")
                fig_line = px.line(df_sales.groupby(['Año','Mes'])['total'].sum().reset_index(), x='Mes', y='total', color='Año', markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
            else: st.info("Aún no hay ventas cerradas.")
        else: st.info("Sin datos.")
        
    with all_tabs[idx_offset + 4]: # Facturación
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
    tab_list, tab_create, tab_teams, tab_reset, tab_import = st.tabs(["⚙️ Gestionar Usuarios", "➕ Crear Nuevo Usuario", "🏢 Estructura Organizacional", "🔥 RESET SISTEMA", "📥 Importar Usuarios"])
    
    with tab_teams:
        st.subheader("Configuración de Células y Sub Células")
        config_org = users.get('_CONFIG_ORG', {})
        current_year = datetime.now().year
        sel_year_team = st.number_input("Configurar Metas para el Año:", min_value=2020, max_value=2050, value=current_year, step=1)
        with st.expander("Crear Nueva Célula Principal"):
            new_team_name = st.text_input("Nombre de la Célula (ej: Europa)")
            if st.button("Crear Célula"):
                if new_team_name and new_team_name not in config_org:
                    config_org[new_team_name] = {'metas_anuales': {}, 'subs': {}}
                    users['_CONFIG_ORG'] = config_org
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success("Célula creada"); st.rerun()
        st.markdown("---")
        for team, data in config_org.items():
            if not isinstance(data, dict): continue
            with st.container(border=True): 
                c1, c2, c3 = st.columns([2, 2, 3])
                c1.markdown(f"### 🌍 {team}")
                curr_meta = float(data.get('metas_anuales', {}).get(str(sel_year_team), 0))
                new_meta_team = c2.number_input(f"Meta {team} ({sel_year_team}) USD", value=curr_meta, key=f"m_{team}_{sel_year_team}")
                
                # Gestión de Miembros en la Célula
                all_users_emails = [k for k in users.keys() if not k.startswith("_")]
                current_members = [u for u in all_users_emails if team in get_user_teams_list(users[u])]
                
                with c3.expander("Gestionar Miembros y Sub Células"):
                    st.markdown("###### Miembros de la Célula")
                    new_members = st.multiselect(f"Usuarios en {team}", all_users_emails, default=current_members, key=f"mem_{team}")
                    if st.button(f"Actualizar Miembros {team}", key=f"upd_mem_{team}"):
                        for u_email in all_users_emails:
                            u_teams = get_user_teams_list(users[u_email])
                            if u_email in new_members:
                                if team not in u_teams: u_teams.append(team)
                            else:
                                if team in u_teams: u_teams.remove(team)
                            users[u_email]['equipo'] = u_teams
                        
                        if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                            sync_users_after_update(); st.success("Miembros actualizados"); time.sleep(1); st.rerun()

                    st.markdown("###### Sub Células")
                    new_sub = st.text_input(f"Nueva Sub Célula en {team}", key=f"ns_{team}")
                    if st.button(f"Agregar Sub Célula", key=f"b_{team}"):
                        if new_sub:
                            data['subs'][new_sub] = 0
                            users['_CONFIG_ORG'] = config_org
                            github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                            sync_users_after_update(); st.rerun()
                    
                    if data['subs']:
                        for sub_name in list(data['subs'].keys()):
                            sc1, sc2 = st.columns([3,1])
                            sc1.text(f"🔹 {sub_name}")
                            if sc2.button("🗑️", key=f"del_sub_{team}_{sub_name}"):
                                del data['subs'][sub_name]
                                users['_CONFIG_ORG'] = config_org
                                github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                                sync_users_after_update(); st.rerun()

                with c1.expander("Opciones Avanzadas"):
                    if st.button("Eliminar Célula Completa", key=f"del_team_{team}", type="primary"):
                        del config_org[team]
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.rerun()
                if new_meta_team != curr_meta:
                    if st.button(f"Guardar Meta {team}", key=f"gm_{team}"):
                        if 'metas_anuales' not in data: data['metas_anuales'] = {}
                        data['metas_anuales'][str(sel_year_team)] = new_meta_team
                        users['_CONFIG_ORG'] = config_org
                        github_push_json('url_usuarios', users, st.session_state.get('users_sha'))
                        sync_users_after_update(); st.success("Guardado"); time.sleep(1); st.rerun()

    with tab_create:
        st.subheader("Alta de Nuevo Usuario")
        config_org = users.get('_CONFIG_ORG', {})
        team_options = list(config_org.keys())
        with st.form("new_user_form"):
            new_email = st.text_input("Correo Electrónico (Usuario)")
            new_name = st.text_input("Nombre Completo")
            new_role = st.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"])
            sel_teams = st.multiselect("Células Principales", team_options)
            sub_options = []
            for t in sel_teams:
                if t in config_org: sub_options += list(config_org[t]['subs'].keys())
            sel_sub_team = st.selectbox("Sub Célula", ["N/A"] + sub_options)
            new_pass = st.text_input("Contraseña Inicial", type="password")
            if st.form_submit_button("Crear Usuario"):
                if not new_email or not new_pass: st.error("Faltan datos")
                elif new_email in users: st.error("Usuario existe")
                else:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    users[new_email] = {"name": new_name, "role": new_role, "password_hash": hashed, "equipo": sel_teams, "sub_equipo": sel_sub_team, "meta_rev": 0, "metas_anuales": {}}
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success(f"Usuario {new_email} creado"); time.sleep(1); st.rerun()

    with tab_list:
        c_sel, c_info = st.columns([1, 2])
        user_keys = [k for k in users.keys() if not k.startswith("_")]
        with c_sel:
            st.subheader("Directorio")
            df_users = pd.DataFrame([{"Email": k, "Nombre": v.get('name'), "Rol": v.get('role')} for k, v in users.items() if not k.startswith("_")])
            st.dataframe(df_users, use_container_width=True, hide_index=True)
            st.markdown("---")
            edit_user = st.selectbox("Seleccionar Usuario a Editar:", user_keys)
        with c_info:
            if edit_user:
                u = users[edit_user]
                st.subheader(f"Editando: {u.get('name')}")
                curr_year_admin = datetime.now().year
                sel_year_meta = st.number_input("Año de Metas:", min_value=2020, max_value=2050, value=curr_year_admin, step=1, key="sy_meta")
                with st.container(border=True):
                    st.markdown("##### 👤 Perfil y Células")
                    c1, c2, c3 = st.columns(3)
                    new_role_e = c1.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"], index=["Comercial", "Finanzas", "Super Admin"].index(u.get('role', 'Comercial')))
                    config_org = users.get('_CONFIG_ORG', {})
                    team_opts = list(config_org.keys())
                    curr_teams = get_user_teams_list(u)
                    valid_defaults = [t for t in curr_teams if t in team_opts]
                    new_teams_e = c2.multiselect("Células", team_opts, default=valid_defaults)
                    sub_opts = ["N/A"]
                    for t in new_teams_e:
                        if t in config_org: sub_opts += list(config_org[t]['subs'].keys())
                    curr_sub = u.get('sub_equipo', 'N/A')
                    idx_sub = sub_opts.index(curr_sub) if curr_sub in sub_opts else 0
                    new_sub_e = c3.selectbox("Sub Célula", sub_opts, index=idx_sub, key="edit_sub")
                with st.container(border=True):
                    st.markdown(f"##### 🎯 Metas Anuales ({sel_year_meta})")
                    u_metas = u.get('metas_anuales', {})
                    u_metas_year = u_metas.get(str(sel_year_meta), {})
                    col_m1, col_m2 = st.columns(2)
                    m_rev = col_m1.number_input("Facturación ($)", value=float(u_metas_year.get('rev', 0)))
                    col_c1, col_c2, col_c3 = st.columns(3)
                    m_big = col_c1.number_input("Grandes (>20k)", value=int(u_metas_year.get('big', 0)))
                    m_mid = col_c2.number_input("Medianos", value=int(u_metas_year.get('mid', 0)))
                    m_sml = col_c3.number_input("Chicos", value=int(u_metas_year.get('sml', 0)))
                if st.button("💾 Guardar Cambios del Usuario", type="primary"):
                    users[edit_user].update({'role': new_role_e, 'equipo': new_teams_e, 'sub_equipo': new_sub_e})
                    if 'metas_anuales' not in users[edit_user]: users[edit_user]['metas_anuales'] = {}
                    users[edit_user]['metas_anuales'][str(sel_year_meta)] = {'rev': m_rev, 'big': m_big, 'mid': m_mid, 'sml': m_sml}
                    if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                        sync_users_after_update(); st.success("Guardado correctamente"); time.sleep(1); st.rerun()
                with st.expander("🚨 Zona de Seguridad (Contraseña / Eliminar)"):
                    p1, p2 = st.columns(2)
                    pass_rst = p1.text_input("Nueva Contraseña", type="password")
                    if p1.button("Reestablecer Clave"):
                        if pass_rst:
                            users[edit_user]['password_hash'] = bcrypt.hashpw(pass_rst.encode(), bcrypt.gensalt()).decode()
                            if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                                sync_users_after_update(); st.success("Clave cambiada")
                    if edit_user != st.session_state['current_user']:
                        if p2.button(f"🗑️ Eliminar a {edit_user}", type="primary"):
                            del users[edit_user]
                            if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                                sync_users_after_update(); st.success("Eliminado"); time.sleep(1); st.rerun()
                    else: p2.warning("No puedes eliminarte a ti mismo.")

    with tab_reset:
        st.error("⚠️ ZONA DE PELIGRO EXTREMO: Aquí puedes borrar datos masivamente.")
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
                    st.session_state['leads_db'] = []; st.success("Leads eliminados.")
                else: success = False
            if del_cots:
                if github_push_json('url_cotizaciones', [], st.session_state.get('cotizaciones_sha')):
                    st.session_state['cotizaciones'] = pd.DataFrame(columns=st.session_state['cotizaciones'].columns)
                    st.success("Cotizaciones eliminadas.")
                else: success = False
            if del_teams or del_metas:
                new_users = st.session_state['users_db'].copy()
                if del_teams:
                    new_users['_CONFIG_ORG'] = {}
                    for k, v in new_users.items():
                        if k.startswith("_"): continue
                        v['equipo'] = []
                        v['sub_equipo'] = 'N/A'
                if del_metas:
                    for k, v in new_users.items():
                        if k.startswith("_"): continue
                        v['meta_rev'] = 0; v['metas_anuales'] = {}
                if github_push_json('url_usuarios', new_users, st.session_state.get('users_sha')):
                    sync_users_after_update(); st.success("Configuraciones reseteadas.")
                else: success = False
            if success: st.balloons(); time.sleep(2); st.rerun()
            else: st.error("Hubo un error al intentar borrar algunos datos.")
    
    with tab_import:
        st.subheader("Importar Usuarios y Estructura (CSV)")
        st.markdown("##### 1. Descargar Plantilla")
        df_tem_user = pd.DataFrame([{"email":"usuario@talentpro.com","nombre":"Nombre Apellido","rol":"Comercial","equipo":"Cono Sur","password_inicial":"Talent2025"}])
        csv_user = df_tem_user.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Plantilla Usuarios CSV", data=csv_user, file_name="plantilla_usuarios.csv", mime="text/csv")
        st.markdown("##### 2. Subir Archivo")
        up_users = st.file_uploader("Cargar CSV de Usuarios", type=["csv"])
        if up_users:
            try:
                try:
                    df_u = pd.read_csv(up_users, sep=None, engine='python')
                except Exception:
                    up_users.seek(0)
                    try:
                        df_u = pd.read_csv(up_users, sep=None, engine='python', encoding='latin-1')
                    except Exception:
                        up_users.seek(0)
                        df_u = pd.read_csv(up_users, sep=';', encoding='latin-1')

                st.write("Vista Previa:", df_u.head())
                if st.button("Procesar Usuarios"):
                    cnt = 0
                    for _, row in df_u.iterrows():
                        em = row['email']
                        if em not in users:
                            hashed = bcrypt.hashpw(str(row['password_inicial']).encode(), bcrypt.gensalt()).decode()
                            users[em] = {"name": row['nombre'], "role": row['rol'], "equipo": [row.get('equipo', 'N/A')], "password_hash": hashed, "meta_rev": 0, "metas_anuales": {}}
                            cnt += 1
                    if cnt > 0:
                        if github_push_json('url_usuarios', users, st.session_state.get('users_sha')):
                            sync_users_after_update(); st.success(f"{cnt} usuarios importados exitosamente.")
                    else: st.warning("No se encontraron usuarios nuevos para importar.")
            except Exception as e: st.error(f"Error procesando CSV: {e}")

# --- MENU LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    role = st.session_state.get('current_role', 'Comercial')
    
    # OPCIONES DEL MENÚ
    opts = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Tutorial"]
    icos = ['bar-chart', 'check', 'person', 'file', 'currency-dollar', 'book']
    
    if role == "Super Admin": opts.append("Usuarios"); icos.append("people")
    
    # Manejo de la selección automática (Navegación entre pestañas)
    if st.session_state['menu_idx'] < len(opts):
        default_idx = st.session_state['menu_idx']
    else:
        default_idx = 0
    
    # Menú estilizado con colores corporativos para verse "a un costado"
    menu = option_menu(
        "Menú Principal",
        opts, 
        icons=icos, 
        menu_icon="cast",
        default_index=default_idx, 
        key='main_menu',
        styles={
            "container": {"padding": "0!important", "background-color": "#ffffff"},
            "icon": {"color": "#003366", "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin":"0px", "--hover-color": "#f0f2f6"},
            "nav-link-selected": {"background-color": "#003366"},
        }
    )
    
    # Actualizar el índice en sesión si el usuario hace clic manualmente
    if menu in opts:
        st.session_state['menu_idx'] = opts.index(menu)

    st.divider()
    if st.button("Cerrar Sesión"): logout()

if menu == "Seguimiento": modulo_seguimiento()
elif menu == "Prospectos y Clientes": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Dashboards": modulo_dashboard()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Tutorial": modulo_tutorial()
elif menu == "Usuarios": modulo_admin()
