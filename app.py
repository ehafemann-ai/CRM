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
    except: return ([], None)

def github_push_json(url_key, data_dict, sha):
    try:
        url = st.secrets['github'][url_key]
        json_str = json.dumps(data_dict, indent=4, default=str)
        content_b64 = base64.b64encode(json_str.encode()).decode()
        payload = {"message": "Update DB", "content": content_b64}
        if sha: payload["sha"] = sha
        headers = {"Authorization": f"token {st.secrets['github']['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201]
    except: return False

# ==============================================================================
# 5. INICIALIZACIÓN Y LÓGICA DE NEGOCIO
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
    df = pd.DataFrame(cots) if cots else pd.DataFrame(columns=['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor', 'hes', 'items', 'pdf_data', 'idioma', 'factura_file'])
    st.session_state['cotizaciones'] = df

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'menu_idx' not in st.session_state: st.session_state['menu_idx'] = 0

# --- FUNCIONES DE CÁLCULO ---
def calc_xls(df, p, c, l):
    if df.empty: return 0.0
    p_clean = str(p).strip()
    r = df[df['Producto'].str.strip().str.lower() == p_clean.lower()]
    if r.empty: return 0.0
    ts = [50, 100, 200, 300, 500, 1000] if l else [100, 200, 300, 500, 1000]
    if c > 1000:
        for col in ['Infinito', '1001+', '1000+', '>1000']:
            if col in r.columns: return float(r.iloc[0][col])
        return float(r.iloc[0, -1])
    for t in ts:
        if c <= t and str(t) in r.columns: return float(r.iloc[0][str(t)])
    return float(r.iloc[0, -1])

def safe_extract_qty(det_str):
    try: return int(str(det_str).lower().replace('x', '').strip().split(' ')[0])
    except: return 0

# --- CARGA DE PRECIOS ---
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
TASAS = {"UF": 38000, "USD_CLP": 950, "USD_BRL": 5.0} # Fallback simple

# --- PDF & OTROS ---
LOGO_PATH = "logo_talentpro.jpg"
TEXTOS = {"ES": {"title": "Cotizador TalentPRO", "client": "Cliente", "sec_prod": "Assessments", "sec_serv": "Servicios", "qty": "Cant", "total": "Total"}, "PT": {}, "EN": {}} # Simplificado para brevedad
EMPRESAS = {"Chile_Pruebas": {"Nombre": "TALENTPRO SPA", "ID": "76.743.976-8", "Dir": "Vitacura"}, "Chile_Servicios": {"Nombre": "TALENTPRO LTDA", "ID": "77.704.757-4", "Dir": "Vitacura"}, "Latam": {"Nombre": "TALENTPRO LATAM S.A.", "ID": "PANAMA", "Dir": "Calle 50"}}

class PDF(FPDF):
    def header(self): 
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 30)
        self.set_font('Arial', 'B', 15); self.cell(0, 10, 'COTIZACIÓN', 0, 1, 'R')
def generar_pdf_final(emp, cli, items, calc, idi, ext):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", '', 10); pdf.cell(0, 10, f"Empresa: {emp['Nombre']}", 0, 1)
    pdf.cell(0, 10, f"Cliente: {cli['empresa']}", 0, 1)
    for i in items: pdf.cell(0, 8, f"{i['Desc']} - {i['Det']} - {i['Unit']} - {i['Total']}", 0, 1)
    pdf.cell(0, 10, f"TOTAL: {calc['total']}", 0, 1)
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 6. MÓDULOS DE LA APP
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Resumen Ejecutivo")
    df = st.session_state['cotizaciones']
    
    # --- MÉTRICA SOLICITADA: COTIZACIONES ABIERTAS ---
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background-color:#003366; padding:20px; border-radius:10px; text-align:center;">
            <h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3>
            <h1 style="color:white; font-size:50px; margin:0;">{abiertas}</h1>
            <p style="color:#d1d1d1;">En negociación o aprobadas</p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2: st.metric("Pipeline Total (USD Estimado)", f"${df['total'].astype(float).sum():,.0f}")
    with c3: st.metric("Ventas Cerradas", len(df[df['estado'] == 'Facturada']))
    
    st.divider()
    if not df.empty:
        fig = px.pie(df, names='estado', title="Distribución por Estado", color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

def modulo_cotizador():
    st.title("📝 Cotizador TalentPRO")
    ctx = obtener_contexto(st.selectbox("País", TODOS_LOS_PAISES))
    
    cc1, cc2, cc3, cc4 = st.columns(4)
    # --- FUNCIONALIDAD RESTAURADA: CLIENTE NUEVO + ORIGEN ---
    es_nuevo = cc1.checkbox("¿Cliente Nuevo?", key="chk_nuevo")
    
    if es_nuevo:
        emp = cc1.text_input("Nombre Empresa Nueva")
        con = cc2.text_input("Contacto")
        ema = cc3.text_input("Email")
        ori = cc4.selectbox("Origen del Cliente", ["SHL", "TalentPRO", "Prospección Propia", "Referido"])
    else:
        lista_cli = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = cc1.selectbox("Seleccionar Cliente", [""] + lista_cli)
        con = cc2.text_input("Contacto")
        ema = cc3.text_input("Email")
        ori = "Existente"

    tp, ts = st.tabs(["Evaluaciones", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        prods = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Producto", prods)
        qp = c2.number_input("Cantidad", 1, 10000, 10)
        
        # Lógica de Volumen Acumulado
        qty_actual = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
        up = calc_xls(ctx['dp'], sp, qty_actual + qp, ctx['tipo'] == 'Loc')
        c3.metric("Unitario", f"{up:,.2f}")
        
        if c4.button("Añadir"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # RECALCULAR TODOS POR VOLUMEN
            t_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], t_qty, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])})
            st.rerun()

    if st.session_state['carrito']:
        df_c = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_c, use_container_width=True, key="tabla_cot")
        st.session_state['carrito'] = edited.to_dict('records')
        
        sub = sum(i['Total'] for i in st.session_state['carrito'])
        st.metric("Subtotal", f"{ctx['mon']} {sub:,.2f}")
        
        if st.button("GUARDAR COTIZACIÓN"):
            nid = f"TP-{random.randint(1000,9999)}"
            # Auto-crear lead si es nuevo
            if es_nuevo and emp:
                new_lead = {"Cliente": emp, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date())}
                st.session_state['leads_db'].append(new_lead)
                github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
            
            nueva_cot = {"id": nid, "fecha": str(datetime.now().date()), "empresa": emp, "total": sub, "moneda": ctx['mon'], "estado": "Enviada", "vendedor": st.session_state.get('current_user',''), "items": st.session_state['carrito']}
            st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([nueva_cot])], ignore_index=True)
            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
            st.session_state['carrito'] = []; st.success(f"Cotización {nid} Guardada"); time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No hay cotizaciones"); return
    
    for i, r in df.sort_values('fecha', ascending=False).iterrows():
        # --- SOLUCIÓN ERROR: KEY ÚNICA PARA CADA WIDGET ---
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            # Agregamos key=f"..._{r['id']}" para evitar el DuplicateElementId
            new_st = c1.selectbox("Cambiar Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"], 
                                  index=["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"].index(r['estado']) if r['estado'] in ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"] else 0,
                                  key=f"sel_{r['id']}")
            
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_{r['id']}")
            
            if c3.button("Actualizar", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st
                st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.success("Actualizado"); time.sleep(0.5); st.rerun()

def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "tipo": "Loc"}
    if pais == "Brasil": return {"mon": "R$", "dp": df_p_br, "tipo": "Loc"}
    return {"mon": "US$", "dp": df_p_usd, "tipo": "Int"}

def modulo_finanzas():
    st.title("💰 Facturación")
    df = st.session_state['cotizaciones']
    pendientes = df[df['estado'] == 'Aprobada']
    if pendientes.empty: st.success("No hay facturas pendientes"); return
    
    for i, r in pendientes.iterrows():
        with st.container(border=True):
            st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']}")
            # Key única para widgets de finanzas
            inv_num = st.text_input("N° Factura", key=f"inv_n_{r['id']}")
            if st.button("Marcar como Facturada", key=f"fact_b_{r['id']}"):
                if inv_num:
                    st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                    st.session_state['cotizaciones'].at[i, 'factura'] = inv_num
                    github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                    st.balloons(); st.rerun()

def login_page():
    st.title("🔒 Acceso CRM TalentPRO")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in st.session_state['users_db']:
            # Simplificado para test, usar bcrypt en prod
            st.session_state['auth_status'] = True
            st.session_state['current_user'] = u
            st.rerun()
        else: st.error("Usuario no válido")

# --- NAVEGACIÓN PRINCIPAL ---
if not st.session_state['auth_status']:
    login_page()
else:
    with st.sidebar:
        menu = option_menu("TalentPRO", ["Dashboards", "Seguimiento", "Cotizador", "Finanzas"], 
                           icons=['bar-chart', 'check2-circle', 'file-earmark-plus', 'currency-dollar'], 
                           menu_icon="cast", default_index=st.session_state['menu_idx'])
        if st.button("Cerrar Sesión"): 
            st.session_state['auth_status'] = False; st.rerun()

    if menu == "Dashboards": modulo_dashboard()
    elif menu == "Seguimiento": modulo_seguimiento()
    elif menu == "Cotizador": modulo_cotizador()
    elif menu == "Finanzas": modulo_finanzas()
