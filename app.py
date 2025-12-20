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
    .admin-card { padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #003366;}
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
    else: st.session_state['cotizaciones'] = pd.DataFrame(columns=cols)

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
        st.markdown("### Acceso Seguro CRM TalentPRO")
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
    "PT": {"title": "Cotação", "quote": "COTAÇÃO", "invoice_to": "Faturar para:", "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Serviços", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total", "subtotal": "Subtotal", "fee": "Taxa Admin", "discount": "Desconto", "bank": "Taxa Bancária", "legal_intl": "Faturamento para {pais}. +Impostos retidos +Despesas OUR.", "noshow_title": "Política No-Show:", "noshow_text": "Multa de 50% por não comparecimento <24h.", "validity": "Validade 30 días"},
    "EN": {"title": "Quotation", "quote": "QUOTATION", "invoice_to": "Bill to:", "client": "Client", "sec_prod": "Assessments", "sec_serv": "Services", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total", "subtotal": "Subtotal", "fee": "Admin Fee", "discount": "Discount", "bank": "Bank Fee", "legal_intl": "Billing to {pais}. +Withholding taxes +OUR expenses.", "noshow_title": "No-Show Policy:", "noshow_text": "50% fine for non-attendance <24h.", "validity": "Validity 30 days"}
}

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939 , Andar 8, Tamboré", "Giro": "Atividades de consultoria em gestión empresarial"},
    "Peru": {"Nombre": "TALENTPRO SOCIEDAD ANÓNIMA CERRADA", "ID": "RUC 20606246847", "Dir": "AVENIDA EL DERBY 254, LIMA, PERÚ", "Giro": "SERVICIOS DE APOYO A LAS EMPRESAS"},
    "Chile_Pruebas": {"Nombre": "TALENTPRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630, Vitacura, Chile", "Giro": "Servicios de Reclutamiento"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630, Vitacura, Chile", "Giro": "Asesoría en Recursos Humanos"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2-2022 DV 27", "Dir": "CALLE 50, PH GLOBAL PLAZA, PANAMÁ", "Giro": "Talent Acquisition Services"}
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
    if isinstance(raw, str): return [raw] if raw and raw != "N/A" else []
    return raw

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102); self.cell(0, 15, getattr(self,'tit_doc','COTIZACIÓN'), 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128); self.cell(0, 10, 'TalentPro Digital System', 0, 0, 'C')

def generar_pdf_final(emp, cli, items, calc, idioma_code, extras):
    T = TEXTOS.get(idioma_code, TEXTOS["ES"]); pdf = PDF(); pdf.tit_doc=T['quote']; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0)
    pdf.set_text_color(100); pdf.cell(95,5,T['invoice_to'],0,1); pdf.set_font("Arial",'',9); pdf.set_text_color(50); y=pdf.get_y()
    pdf.cell(95,5,emp['ID'],0,1); pdf.multi_cell(90,5,emp['Dir']); pdf.cell(95,5,emp['Giro'],0,1)
    pdf.set_xy(105,y); pdf.set_font("Arial",'B',10); pdf.set_text_color(0); pdf.cell(95,5,cli['empresa'],0,1)
    pdf.set_xy(105,pdf.get_y()); pdf.set_font("Arial",'',9); pdf.set_text_color(50); pdf.cell(95,5,cli['contacto'],0,1); pdf.set_xy(105,pdf.get_y()); pdf.cell(95,5,cli['email'],0,1)
    pdf.ln(5); pdf.set_xy(105,pdf.get_y()); pdf.set_text_color(0,51,102); pdf.cell(95,5,f"Date: {datetime.now().strftime('%d/%m/%Y')} | ID: {extras['id']}",0,1); pdf.ln(10)
    pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.set_font("Arial",'B',9)
    pdf.cell(110,8,T['desc'],0,0,'L',1); pdf.cell(20,8,T['qty'],0,0,'C',1); pdf.cell(30,8,T['unit'],0,0,'R',1); pdf.cell(30,8,T['total'],0,1,'R',1)
    pdf.set_text_color(0); pdf.set_font("Arial",'',8); mon=items[0]['Moneda']
    for i in items:
        q=str(i['Det']).split('(')[0].replace('x','').strip(); pdf.cell(110,7,f"  {i['Desc'][:60]}",'B',0,'L'); pdf.cell(20,7,q,'B',0,'C'); pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(5); x=120
    def r(l,v,b=False):
        pdf.set_x(x); pdf.set_font("Arial",'B' if b else '',10); pdf.set_text_color(0 if not b else 255); if b: pdf.set_fill_color(0,51,102)
        pdf.cell(35,7,l,0,0,'R',b); pdf.cell(35,7,f"{mon} {v:,.2f} ",0,1,'R',b)
    r(T['subtotal'], calc['subtotal']); if calc['fee']>0: r(T['fee'], calc['fee'])
    if calc['tax_val']>0: r(calc['tax_name'], calc['tax_val'])
    if extras.get('bank',0)>0: r(T['bank'], extras['bank'])
    lbl_dsc = extras.get('desc_name') if extras.get('desc_name') else T['discount']
    if extras.get('desc',0)>0: r(lbl_dsc, -extras['desc'])
    pdf.ln(1); r(T['total'].upper(), calc['total'], True); pdf.ln(10); pdf.set_font("Arial",'I',8); pdf.set_text_color(80)
    if emp['Nombre']==EMPRESAS['Latam']['Nombre']: pdf.multi_cell(0,4,T['legal_intl'].format(pais=extras['pais']),0,'L'); pdf.ln(3)
    if any(any(tr in i['Desc'].lower() for tr in ['feedback','coaching','entrevista']) for i in items):
        pdf.set_font("Arial",'B',8); pdf.cell(0,4,T['noshow_title'],0,1); pdf.set_font("Arial",'',8); pdf.multi_cell(0,4,T['noshow_text'],0,'L'); pdf.ln(3)
    pdf.set_text_color(100); pdf.cell(0,5,T['validity'],0,1)
    return pdf.output(dest='S').encode('latin-1')

def lluvia_dolares():
    st.markdown("""<style>@keyframes fall {0% { transform: translateY(-10vh); opacity: 1; } 100% { transform: translateY(110vh); opacity: 0; }} .money-rain {position: fixed; top: 0; font-size: 2.5rem; animation: fall linear forwards; z-index: 99999; pointer-events: none;}</style>""", unsafe_allow_html=True)
    h = ""
    for i in range(40): h += f'<div class="money-rain" style="left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,2)}s; animation-duration:{random.uniform(2,4)}s;">💲</div>'
    st.markdown(h, unsafe_allow_html=True)

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================
def modulo_crm():
    st.title("📇 Prospectos y Clientes")
    tab1, tab2, tab_import = st.tabs(["📋 Gestión de Leads", "🏢 Cartera Clientes", "📥 Importar Masivo"])
    with tab1:
        with st.expander("➕ Nuevo Lead", expanded=False):
            with st.form("form_lead"):
                c1, c2, c3 = st.columns(3); nom_cliente = c1.text_input("Cliente / Empresa"); area = c2.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"]); pais = c3.selectbox("País", TODOS_LOS_PAISES)
                c1, c2, c3 = st.columns(3); ind = c1.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"]); web = c2.text_input("Web"); idioma = c3.selectbox("Idioma", ["ES", "EN", "PT"])
                contacts_data = []
                for i in range(1, 4):
                    cx1, cx2, cx3 = st.columns(3); n = cx1.text_input(f"Nombre {i}", key=f"n{i}"); m = cx2.text_input(f"Mail {i}", key=f"m{i}"); t = cx3.text_input(f"Tel {i}", key=f"t{i}")
                    if n: contacts_data.append(f"{n} ({m})")
                c1, c2 = st.columns(2); origen = c1.selectbox("Origen", ["SHL", "KAM TalentPRO", "Prospección"]); etapa = c2.selectbox("Etapa Inicial", ["Prospección", "Contacto", "Reunión", "Propuesta"]); exp = st.text_area("Expectativa")
                if st.form_submit_button("Guardar Lead"):
                    new_l = {"id": int(time.time()), "Cliente": nom_cliente, "Area": area, "Pais": pais, "Industria": ind, "Web": web, "Contactos": ", ".join(contacts_data), "Origen": origen, "Etapa": etapa, "Expectativa": exp, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())}
                    st.session_state['leads_db'].append(new_l)
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Guardado"); time.sleep(1); st.rerun()
        st.divider(); st.subheader("🖊️ Gestionar / Editar Lead")
        v_leads = [l for l in st.session_state['leads_db'] if l.get('Etapa') not in ['Cliente Activo', 'Cerrado Ganado'] and l.get('Area') != 'Cartera']
        if v_leads:
            sel_l_name = st.selectbox("Seleccionar Lead", [""] + sorted(list(set([l['Cliente'] for l in v_leads]))))
            if sel_l_name:
                idx_l = next((i for i, d in enumerate(st.session_state['leads_db']) if d["Cliente"] == sel_l_name), None)
                if idx_l is not None:
                    ld = st.session_state['leads_db'][idx_l]; col_ed, col_inf = st.columns(2)
                    with col_ed:
                        with st.form(f"ed_l_{idx_l}"):
                            ec = st.text_area("Contactos", value=ld.get('Contactos','')); ee = st.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"], index=0); ew = st.text_input("Web", value=ld.get('Web',''))
                            if st.form_submit_button("💾 Guardar"):
                                st.session_state['leads_db'][idx_l].update({"Contactos": ec, "Etapa": ee, "Web": ew}); github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("OK"); st.rerun()
                    with col_inf:
                        df_c = st.session_state['cotizaciones']; c_l = df_c[df_c['empresa'] == sel_l_name]
                        if not c_l.empty: st.dataframe(c_l[['fecha', 'total', 'estado']], use_container_width=True)
                        up_p = st.file_uploader("Subir Propuesta PDF", type=['pdf'], key=f"up_p_{idx_l}")
                        if up_p and st.button("Guardar Propuesta"):
                            st.session_state['leads_db'][idx_l]['propuesta_file'] = base64.b64encode(up_p.read()).decode(); github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Subido"); st.rerun()
        st.dataframe(pd.DataFrame(v_leads), use_container_width=True)

    with tab2:
        cl_list = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db'] if l.get('Etapa') in ['Cliente Activo', 'Cerrado Ganado'] or l.get('Area') == 'Cartera'])))
        sel_c = st.selectbox("Cliente 360", [""] + cl_list)
        if sel_c:
            dfc = st.session_state['cotizaciones'][st.session_state['cotizaciones']['empresa']==sel_c]
            st.metric("Total Cotizado", f"${dfc['total'].sum():,.0f}"); st.dataframe(dfc, use_container_width=True)

    with tab_import:
        up_csv = st.file_uploader("Subir CSV Leads", type=["csv"])
        if up_csv and st.button("Importar"):
            try:
                df_u = pd.read_csv(up_csv, sep=None, engine='python')
                for _, r in df_u.iterrows():
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": r.get('Cliente','S/N'), "Etapa": "Prospección", "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())})
                github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Importado"); st.rerun()
            except: st.error("Error CSV")

def modulo_cotizador():
    edit_data = st.session_state.get('cot_edit_data')
    if edit_data:
        st.info(f"✏️ MODO EDICIÓN: ID {edit_data.get('id_orig')}")
        if st.button("❌ Cancelar"): st.session_state['carrito'] = []; st.session_state['cot_edit_data'] = None; st.rerun()

    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES", "PT", "EN"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    c1,c2,c3,c4 = st.columns(4); c1.metric("UF", f"${TASAS['UF']:,.0f}"); c2.metric("USD", f"${TASAS['USD_CLP']:,.0f}"); c3.metric("BRL", f"{TASAS['USD_BRL']:.2f}")
    if c4.button("Actualizar Tasas"): obtener_indicadores.clear(); st.rerun()
    
    ps = st.selectbox("🌎 País", TODOS_LOS_PAISES, index=TODOS_LOS_PAISES.index(edit_data.get('pais')) if edit_data and edit_data.get('pais') in TODOS_LOS_PAISES else 0); ctx = obtener_contexto(ps)
    cc1,cc2,cc3,cc4=st.columns(4)
    u_teams = get_user_teams_list(st.session_state['users_db'].get(st.session_state['current_user'], {}))
    sel_t = cc4.selectbox("Célula", u_teams) if len(u_teams)>1 else (u_teams[0] if u_teams else "N/A")
    clientes = sorted(list(set([x['Cliente'] for x in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
    emp = cc1.selectbox(txt['client'], [""] + clientes, index=clientes.index(edit_data.get('empresa'))+1 if edit_data and edit_data.get('empresa') in clientes else 0)
    con = cc2.text_input("Contacto", value=edit_data.get('contacto','') if edit_data else ""); ema = cc3.text_input("Email", value=edit_data.get('email','') if edit_data else "")
    ven = st.session_state['users_db'][st.session_state['current_user']].get('name','')

    tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4 = st.columns([3,1,1,1]); lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp); qp=c2.number_input("Cant",1,10000,10)
            # --- PRECIO DINÁMICO ---
            c_qty = sum(int(str(i['Det']).replace('x','').strip()) for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
            up = calc_xls(ctx['dp'], sp, c_qty + qp, ctx['tipo']=='Loc'); c3.metric("Unit", f"{up:,.2f}")
            if c4.button("Add", key="add_p"):
                st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
                # RECALCULAR TODOS LOS ITEMS DEL CARRITO POR EL NUEVO VOLUMEN
                t_qty = sum(int(str(i['Det']).replace('x','').strip()) for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
                for i, it in enumerate(st.session_state['carrito']):
                    if it['Ítem'] == 'Evaluación':
                        nu = calc_xls(ctx['dp'], it['Desc'], t_qty, ctx['tipo']=='Loc'); nq = int(str(it['Det']).replace('x','').strip())
                        st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * nq})
                st.rerun()

    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        if ls:
            ss=c1.selectbox("Serv",["Certificación PAA"]+ls)
            if "PAA" in ss: qs=c2.number_input("Pers",1,100,1); us=calc_paa(qs,ctx['mon']); dt=f"x{qs}"
            else: r=c2.selectbox("Rol",['Senior','BM','BP']); qs=1; rw=ctx['ds'][ctx['ds']['Servicio']==ss]; us=float(rw.iloc[0][r]) if not rw.empty else 0; dt=f"x{qs} ({r})"
            c3.metric("Unit",f"{us:,.2f}")
            if c4.button("Add", key="add_s"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        st.divider()
        df_cart = pd.DataFrame(st.session_state['carrito'])
        edited_cart = st.data_editor(df_cart, num_rows="dynamic", use_container_width=True, key="ceditor")
        st.session_state['carrito'] = edited_cart.to_dict('records')
        
        # --- RECALCULO AUTOMATICO SI CAMBIA CANTIDAD EN TABLA ---
        try:
            cur_qty = sum(int(str(i['Det']).replace('x','').strip().split(' ')[0]) for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], cur_qty, ctx['tipo']=='Loc')
                    nq = int(str(it['Det']).replace('x','').strip().split(' ')[0])
                    if it['Unit'] != nu:
                        st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * nq}); st.rerun()
        except: pass

        sub = sum(i['Total'] for i in st.session_state['carrito']); eva = sum(i['Total'] for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
        col_L, col_R = st.columns([3,1])
        with col_R:
            fee = st.checkbox("Fee 10%", value=edit_data.get('fee',0)>0 if edit_data else False); vfee = eva*0.1 if fee else 0
            bnk = st.number_input("Bank", value=float(edit_data.get('bank',0)) if edit_data else 0.0)
            dsc_n = st.text_input("Glosa Desc", value=edit_data.get('desc_name','Descuento') if edit_data else "Descuento")
            # Logica de descuento (Simulacion volumen incorporada)
            tipo_d = st.selectbox("Tipo Descuento", ["Fijo", "Porcentaje", "Simular Vol"])
            dsc = 0.0
            if tipo_d == "Fijo": dsc = st.number_input("Monto", value=float(edit_data.get('desc',0)) if edit_data else 0.0)
            elif tipo_d == "Porcentaje": dsc = sub * (st.number_input("%", 0, 100, 0)/100)
            else:
                v_sim = st.number_input("Simular Qty", 1, 10000, 1000)
                tot_sim = sum(calc_xls(ctx['dp'], i['Desc'], v_sim, ctx['tipo']=='Loc') * int(str(i['Det']).replace('x','').strip().split(' ')[0]) for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
                dsc = max(0, eva - tot_sim)
                st.caption(f"Ahorro: {dsc:,.2f}")
            
            tn, tv = get_impuestos(ps, sub, eva); fin = sub + vfee + tv + bnk - dsc
            st.metric("TOTAL", f"{ctx['mon']} {fin:,.2f}")
            
            if st.button("GUARDAR / ACTUALIZAR", type="primary"):
                nid = edit_data['id_orig'] if edit_data else f"TP-{random.randint(1000,9999)}"
                row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':ven, 'equipo_asignado': sel_t, 'oc':'', 'factura':'', 'pago':'Pendiente', 'hes':False, 'hes_num':'', 'items': st.session_state['carrito'], 'pdf_data': {'contacto':con, 'email':ema, 'fee':vfee, 'bank':bnk, 'desc':dsc, 'desc_name':dsc_n, 'pais':ps, 'id':nid}, 'idioma': idi, 'factura_file': None}
                if edit_data:
                    idx = st.session_state['cotizaciones'][st.session_state['cotizaciones']['id']==nid].index
                    if not idx.empty: st.session_state['cotizaciones'].iloc[idx[0]] = row
                else: st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.session_state['carrito'] = []; st.session_state['cot_edit_data'] = None; st.success("Guardado"); time.sleep(1); st.rerun()
        if col_L.button("Limpiar"): st.session_state['carrito'] = []; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial")
    df = st.session_state['cotizaciones'].sort_values('fecha', ascending=False)
    if df.empty: st.info("Sin datos"); return
    
    # Filtro por Rol / Equipo
    if st.session_state.get('current_role') == 'Comercial':
        me = st.session_state['users_db'][st.session_state['current_user']].get('name','')
        df = df[df['vendedor'] == me]

    for i, r in df.iterrows():
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['moneda']} {r['total']:,.0f} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_s = c1.selectbox("Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"], index=["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"].index(r['estado']) if r['estado'] in ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"] else 0)
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False))
            if c3.button("Actualizar", key=f"upd_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_s; st.session_state['cotizaciones'].at[i, 'hes'] = hes
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    if new_s == 'Aprobada': st.balloons()
                    st.success("OK"); st.rerun()
            if st.button("✏️ Editar / Clonar", key=f"ed_{r['id']}"):
                pd_ = r.get('pdf_data', {})
                st.session_state['carrito'] = r['items']
                st.session_state['cot_edit_data'] = {'id_orig': r['id'], 'empresa': r['empresa'], 'pais': r['pais'], 'contacto': pd_.get('contacto',''), 'email': pd_.get('email',''), 'fee': pd_.get('fee',0), 'bank': pd_.get('bank',0), 'desc': pd_.get('desc',0), 'desc_name': pd_.get('desc_name','Desc')}
                st.session_state['menu_idx'] = 3; st.rerun()

def modulo_finanzas():
    st.title("💰 Finanzas")
    df = st.session_state['cotizaciones']
    t1, t2 = st.tabs(["Por Facturar", "Historial"])
    with t1:
        pend = df[df['estado'] == 'Aprobada']
        for i, r in pend.iterrows():
            with st.container(border=True):
                st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']:,.2f}")
                if r.get('hes'): st.warning("⚠️ Requiere HES")
                c1, c2, c3, c4 = st.columns(4)
                f_inv = c1.text_input("N° Factura", key=f"f_{r['id']}")
                f_oc = c2.text_input("OC", value=r.get('oc',''), key=f"o_{r['id']}")
                up_f = c3.file_uploader("Subir PDF Factura", type=['pdf'], key=f"upf_{r['id']}")
                if c4.button("Marcar Facturada", key=f"bf_{r['id']}"):
                    if f_inv:
                        st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                        st.session_state['cotizaciones'].at[i, 'factura'] = f_inv
                        st.session_state['cotizaciones'].at[i, 'oc'] = f_oc
                        if up_f: st.session_state['cotizaciones'].at[i, 'factura_file'] = base64.b64encode(up_f.read()).decode()
                        github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                        lluvia_dolares(); st.success("Facturado"); time.sleep(2); st.rerun()
    with t2:
        hist = df[df['estado'] == 'Facturada']
        st.dataframe(hist[['fecha', 'empresa', 'total', 'factura', 'pago']], use_container_width=True)

def modulo_dashboard():
    st.title("📊 Dashboard")
    dfc = st.session_state['cotizaciones'].copy()
    if dfc.empty: st.info("Sin datos"); return
    
    # Conversión simple a USD para gráficos
    def to_usd(r):
        if r['moneda'] == 'US$': return r['total']
        if r['moneda'] == 'UF': return (r['total'] * TASAS['UF']) / TASAS['USD_CLP'] if TASAS['USD_CLP']>0 else 0
        return r['total'] / TASAS['USD_BRL'] if TASAS['USD_BRL']>0 else 0
    
    dfc['total_usd'] = dfc.apply(to_usd, axis=1)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Leads", len(st.session_state['leads_db']))
    c2.metric("Pipeline USD", f"${dfc[dfc['estado'].isin(['Enviada','Aprobada'])]['total_usd'].sum():,.0f}")
    c3.metric("Facturado USD", f"${dfc[dfc['estado']=='Facturada']['total_usd'].sum():,.0f}")
    
    st.plotly_chart(px.pie(dfc, names='estado', title="Estado Global"), use_container_width=True)
    st.plotly_chart(px.bar(dfc, x='vendedor', y='total_usd', color='estado', title="Ventas por Ejecutivo (USD)"), use_container_width=True)

def modulo_admin():
    st.title("👥 Admin")
    users = st.session_state['users_db']
    t1, t2, t3 = st.tabs(["Usuarios", "Estructura", "Reset"])
    with t1:
        with st.form("new_u"):
            ne = st.text_input("Email"); nn = st.text_input("Nombre"); np = st.text_input("Pass", type="password"); nr = st.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"])
            if st.form_submit_button("Crear"):
                users[ne] = {"name": nn, "role": nr, "password_hash": bcrypt.hashpw(np.encode(), bcrypt.gensalt()).decode(), "equipo": []}
                github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.success("Creado"); st.rerun()
        st.write("Usuarios Actuales:")
        st.dataframe(pd.DataFrame([{"Email": k, "Nombre": v.get('name'), "Rol": v.get('role')} for k, v in users.items() if not k.startswith("_")]), use_container_width=True)
    with t2:
        st.subheader("Células")
        conf = users.get('_CONFIG_ORG', {})
        nt = st.text_input("Nueva Célula")
        if st.button("Añadir") and nt:
            conf[nt] = {'metas_anuales': {}, 'subs': {}}; users['_CONFIG_ORG'] = conf
            github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.rerun()
        st.write(list(conf.keys()))
    with t3:
        st.warning("Zona de peligro")
        if st.text_input("Escribe CONFIRMAR") == "CONFIRMAR":
            if st.button("RESET COTIZACIONES"):
                github_push_json('url_cotizaciones', [], st.session_state.get('cotizaciones_sha')); st.rerun()

# --- NAVEGACIÓN ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    role = st.session_state.get('current_role', 'Comercial')
    opts = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas"]
    icons = ['bar-chart', 'check', 'person', 'file', 'currency-dollar']
    if role == "Super Admin": opts.append("Usuarios"); icons.append("people")
    
    menu = option_menu("Menú", opts, icons=icons, default_index=st.session_state['menu_idx'], key='main_menu')
    st.session_state['menu_idx'] = opts.index(menu)
    if st.button("Salir"): logout()

if menu == "Seguimiento": modulo_seguimiento()
elif menu == "Prospectos y Clientes": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Dashboards": modulo_dashboard()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Usuarios": modulo_admin()
