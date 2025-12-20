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

# --- 3. ESTILOS CSS GENERALES Y LOGIN ---
# Colores: Azul PRO (#004B8D), Azul Talent (#6FBCE3)
st.markdown(f"""
    <style>
    /* Estilos Generales */
    .stMetric {{background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}}
    [data-testid="stSidebar"] {{ padding-top: 0rem; }}
    
    /* Personalización de Botones Principales */
    div.stButton > button:first-child {{
        background-color: #004B8D;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: None;
    }}
    div.stButton > button:first-child:hover {{
        background-color: #6FBCE3;
        color: white;
    }}

    /* Estilo para la caja de Login */
    .login-container {{
        background-color: #ffffff;
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-top: 5px solid #004B8D;
        text-align: center;
    }}
    .login-header {{
        color: #004B8D;
        font-family: 'Arial';
        font-weight: bold;
        margin-bottom: 20px;
    }}
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
        return ({}, None) if "users" in url_key else ([], None)
    except: return ([], None) if "users" not in url_key else ({}, None)

def github_push_json(url_key, data_dict, sha):
    try:
        url = st.secrets['github'][url_key]
        json_str = json.dumps(data_dict, indent=4, default=str)
        content_b64 = base64.b64encode(json_str.encode()).decode()
        payload = {"message": "Update DB from CRM", "content": content_b64}
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

# ==============================================================================
# 5. INICIALIZACIÓN DE ESTADO
# ==============================================================================
if 'users_db' not in st.session_state:
    users, sha = github_get_json('url_usuarios')
    st.session_state['users_db'] = users; st.session_state['users_sha'] = sha

if 'leads_db' not in st.session_state:
    leads, sha_l = github_get_json('url_leads')
    st.session_state['leads_db'] = leads if isinstance(leads, list) else []; st.session_state['leads_sha'] = sha_l

if 'cotizaciones' not in st.session_state:
    cots, sha_c = github_get_json('url_cotizaciones')
    st.session_state['cotizaciones_sha'] = sha_c
    cols = ['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor', 'oc', 'factura', 'pago', 'hes', 'hes_num', 'items', 'pdf_data', 'idioma', 'equipo_asignado', 'factura_file']
    if cots and isinstance(cots, list):
        df = pd.DataFrame(cots)
        for c in cols:
            if c not in df.columns: df[c] = ""
        st.session_state['cotizaciones'] = df
    else: st.session_state['cotizaciones'] = pd.DataFrame(columns=cols)

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
if 'menu_idx' not in st.session_state: st.session_state['menu_idx'] = 0

# ==============================================================================
# 6. LOGICA DE NEGOCIO Y DATOS
# ==============================================================================
@st.cache_data(ttl=60)
def cargar_precios():
    try:
        url = st.secrets["github"]["url_precios"]
        r = requests.get(url, headers={"Authorization": f"token {st.secrets['github']['token']}"})
        xls = pd.ExcelFile(io.BytesIO(r.content))
        def lh(n): return pd.read_excel(xls, n) if n in xls.sheet_names else pd.DataFrame()
        return (lh('Pruebas Int'), lh('Servicios Int'), lh('Config'), lh('Pruebas_CL'), lh('Servicios_CL'), lh('Pruebas_BR'), lh('Servicios_BR'))
    except: return (pd.DataFrame(),)*7

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

def calc_xls(df, p, c, l):
    if df.empty: return 0.0
    p_clean = str(p).strip()
    r = df[df['Producto'].str.strip().str.lower() == p_clean.lower()]
    if r.empty: return 0.0
    ts = [50, 100, 200, 300, 500, 1000] if l else [100, 200, 300, 500, 1000]
    if c > 1000:
        for col in ['Infinito', 'infinito', '1001', '1001+', '1000+', '>1000']:
            if col in r.columns: return float(r.iloc[0][col])
        return float(r.iloc[0, -1])
    for t in ts:
        if c <= t:
            col_name = str(t)
            if col_name in r.columns: return float(r.iloc[0][col_name])
    return float(r.iloc[0, -1])

def safe_extract_qty(det_str):
    try: return int(str(det_str).lower().replace('x', '').strip().split(' ')[0].split('(')[0])
    except: return 0

# --- PAGINA DE LOGIN PERSONALIZADA ---
def login_page():
    # Logo URL desde tu S3 (misma que el resto de la app usa)
    logo_url = "https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg"
    
    empty1, col_login, empty2 = st.columns([1, 1.5, 1])
    
    with col_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="login-container">
                <img src="{logo_url}" width="280">
                <h2 class="login-header">Acceso al Sistema CRM</h2>
                <p style="color: #666;">Expertos en Digitalización de RRHH</p>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            user_input = st.text_input("Usuario / Email", placeholder="ejemplo@talentpro.com")
            pass_input = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button("INGRESAR AL PORTAL", use_container_width=True)
            
            if submit:
                user_data = st.session_state['users_db'].get(user_input)
                if user_data and 'password_hash' in user_data:
                    if bcrypt.checkpw(pass_input.encode(), user_data['password_hash'].encode()):
                        st.session_state['auth_status'] = True
                        st.session_state['current_user'] = user_input
                        st.session_state['current_role'] = user_data.get('role', 'Comercial')
                        st.success("Acceso concedido"); time.sleep(0.5); st.rerun()
                    else: st.error("Contraseña incorrecta")
                else: st.error("Usuario no encontrado")

# ==============================================================================
# 7. MÓDULOS APP (Dashboard, Seguimiento, CRM, Cotizador, Finanzas, Admin)
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Resumen de Operaciones")
    df = st.session_state['cotizaciones']
    # KPI Cotizaciones Abiertas
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div style="background-color:#004B8D; padding:20px; border-radius:10px; text-align:center;"><h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3><h1 style="color:white; font-size:45px; margin:0;">{abiertas}</h1></div>""", unsafe_allow_html=True)
    c2.metric("Pipeline USD", f"${df[df['estado']!='Facturada']['total'].astype(float).sum():,.0f}")
    c3.metric("Facturación Mes", f"${df[df['estado']=='Facturada']['total'].astype(float).sum():,.0f}")
    
    st.divider()
    if not df.empty:
        fig = px.bar(df, x='vendedor', y='total', color='estado', title="Desempeño por Ejecutivo", color_discrete_map={'Facturada':'#004B8D', 'Enviada':'#6FBCE3'})
        st.plotly_chart(fig, use_container_width=True)

def modulo_cotizador():
    st.title("📝 Generador de Cotizaciones")
    
    cc1, cc2, cc3, cc4 = st.columns(4)
    es_nuevo = cc1.checkbox("¿Cliente Nuevo?", value=False)
    
    if es_nuevo:
        emp = cc1.text_input("Nombre Empresa Nueva")
        ori = cc2.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Referido", "Prospección"])
        con = cc3.text_input("Contacto")
        ema = cc4.text_input("Email")
    else:
        lista_cli = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = cc1.selectbox("Cliente Existente", [""] + lista_cli)
        con = cc2.text_input("Contacto")
        ema = cc3.text_input("Email")
        ori = "Existente"

    ps = st.selectbox("País de Facturación", TODOS_LOS_PAISES)
    ctx = {"mon": "UF", "dp": df_p_cl, "tipo": "Loc"} if ps == "Chile" else {"mon": "US$", "dp": df_p_usd, "tipo": "Int"}
    
    tp, ts = st.tabs(["Assessments", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Seleccionar Item", lp); qp = c2.number_input("Cantidad", 1, 10000, 10)
        
        # Lógica de Volumen Acumulado Reactiva
        qty_acc = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
        up = calc_xls(ctx['dp'], sp, qty_acc + qp, ctx['tipo'] == 'Loc')
        c3.metric("Precio Unit.", f"{up:,.2f}")
        
        if c4.button("AGREGAR"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # Recalculo automático de ítems previos
            t_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], t_qty, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])})
            st.rerun()

    if st.session_state['carrito']:
        st.divider()
        df_cart = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_cart, use_container_width=True, key="cart_table")
        st.session_state['carrito'] = edited.to_dict('records')
        
        sub = sum(i['Total'] for i in st.session_state['carrito'])
        st.metric("Total Cotización", f"{ctx['mon']} {sub:,.2f}")
        
        if st.button("FINALIZAR Y GUARDAR"):
            if es_nuevo and emp:
                st.session_state['leads_db'].append({"Cliente": emp, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date())})
                github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
            
            nid = f"TP-{random.randint(1000,9999)}"
            row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':sub, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':st.session_state['current_user'], 'items': st.session_state['carrito']}
            st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
            st.session_state['carrito'] = []; st.success(f"Cotización {nid} generada"); time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial")
    df = st.session_state['cotizaciones']
    for i, r in df.sort_values('fecha', ascending=False).iterrows():
        # Key única con ID de cotización para evitar errores de duplicados
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_st = c1.selectbox("Cambiar Estado", ["Enviada", "Aprobada", "Rechazada", "Facturada"], index=0, key=f"st_{r['id']}")
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_{r['id']}")
            if c3.button("ACTUALIZAR", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st
                st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.rerun()

def modulo_finanzas():
    st.title("💰 Facturación")
    df = st.session_state['cotizaciones']
    pendientes = df[df['estado'] == 'Aprobada']
    for i, r in pendientes.iterrows():
        with st.container(border=True):
            st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']}")
            # Restaurada Lógica PDFs Chile (SpA/Ltda)
            if r['pais'] == "Chile":
                st.info("Nota: Generar facturas separadas si incluye Servicios y Assessments.")
            
            c1, c2 = st.columns(2)
            n_inv = c1.text_input("N° Factura", key=f"inv_{r['id']}")
            if c2.button("MARCAR FACTURADA", key=f"fbtn_{r['id']}"):
                if n_inv:
                    st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                    st.session_state['cotizaciones'].at[i, 'factura'] = n_inv
                    github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                    lluvia_dolares(); st.rerun()

def modulo_crm():
    st.title("📇 CRM de Prospectos")
    df_l = pd.DataFrame(st.session_state['leads_db'])
    if not df_l.empty:
        st.dataframe(df_l, use_container_width=True)

def modulo_admin():
    st.title("👥 Panel Administrativo")
    st.write("Usuarios:", st.session_state['users_db'])

# --- NAVEGACIÓN Y CONTROL DE ACCESO ---
if not st.session_state['auth_status']:
    login_page()
else:
    with st.sidebar:
        # Logo en sidebar
        st.image("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg", width=150)
        menu = option_menu("Menú TalentPRO", ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"], 
                           icons=['bar-chart', 'check2', 'people', 'file-earmark', 'currency-dollar', 'shield-lock'], 
                           default_index=st.session_state['menu_idx'])
        st.session_state['menu_idx'] = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"].index(menu)
        if st.button("CERRAR SESIÓN"): st.session_state.clear(); st.rerun()

    if menu == "Dashboards": modulo_dashboard()
    elif menu == "Seguimiento": modulo_seguimiento()
    elif menu == "Prospectos y Clientes": modulo_crm()
    elif menu == "Cotizador": modulo_cotizador()
    elif menu == "Finanzas": modulo_finanzas()
    elif menu == "Usuarios": modulo_admin()
