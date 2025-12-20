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
st.markdown(f"""
    <style>
    .stMetric {{background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}}
    [data-testid="stSidebar"] {{ padding-top: 0rem; }}
    
    /* Botones TalentPRO */
    div.stButton > button:first-child {{
        background-color: #004B8D;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: None;
    }}
    div.stButton > button:first-child:hover {{
        background-color: #6FBCE3;
    }}

    /* Caja de Login */
    .login-container {{
        background-color: #ffffff;
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-top: 5px solid #004B8D;
        text-align: center;
    }}
    
    /* Estilos Categorías Finanzas */
    .finance-card-chile {{ border-left: 10px solid #004B8D; background-color: #f0f7ff; padding: 15px; border-radius: 8px; margin-bottom: 10px; }}
    .finance-card-brasil {{ border-left: 10px solid #228B22; background-color: #f0fff0; padding: 15px; border-radius: 8px; margin-bottom: 10px; }}
    .finance-card-panama {{ border-left: 10px solid #FFD700; background-color: #fffdf0; padding: 15px; border-radius: 8px; margin-bottom: 10px; }}
    .finance-card-default {{ border-left: 10px solid #6FBCE3; background-color: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 10px; }}
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
    df = pd.DataFrame(cots) if cots else pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns: df[c] = ""
    st.session_state['cotizaciones'] = df

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'menu_idx' not in st.session_state: st.session_state['menu_idx'] = 0

# ==============================================================================
# 6. LOGICA DE NEGOCIO (PRECIOS, TASAS, PDF)
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
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil", "Panama", "Peru"]

@st.cache_data(ttl=3600)
def obtener_indicadores():
    t = {"UF": 38000, "USD_CLP": 950, "USD_BRL": 5.2}
    try: 
        resp = requests.get('https://mindicador.cl/api',timeout=2).json()
        t['UF'] = resp['uf']['valor']; t['USD_CLP'] = resp['dolar']['valor']
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
        for col in ['Infinito', '1001+', '1000+', '>1000']:
            if col in r.columns: return float(r.iloc[0][col])
        return float(r.iloc[0, -1])
    for t in ts:
        if c <= t and str(t) in r.columns: return float(r.iloc[0][str(t)])
    return float(r.iloc[0, -1])

def safe_extract_qty(det_str):
    try: return int(str(det_str).lower().replace('x', '').strip().split(' ')[0].split('(')[0])
    except: return 0

def lluvia_dolares():
    st.markdown("""<style>@keyframes fall {0% { transform: translateY(-10vh); opacity: 1; } 100% { transform: translateY(110vh); opacity: 0; }} .money-rain {position: fixed; top: 0; font-size: 2.5rem; animation: fall linear forwards; z-index: 99999; pointer-events: none;}</style>""", unsafe_allow_html=True)
    h = ""
    for i in range(40): h += f'<div class="money-rain" style="left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,2)}s; animation-duration:{random.uniform(2,4)}s;">💲</div>'
    st.markdown(h, unsafe_allow_html=True)

# (Motor PDF simplificado para el ejemplo pero funcional)
class PDF(FPDF):
    def header(self): self.set_font('Arial', 'B', 15); self.cell(0, 10, 'COTIZACIÓN TALENTPRO', 0, 1, 'C')

def generar_pdf_final(emp, cli, items, calc, idi, ext):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Cliente: {cli['empresa']}", 0, 1)
    pdf.cell(0, 10, f"Total: {calc['total']}", 0, 1)
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Dashboards")
    df = st.session_state['cotizaciones']
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div style="background-color:#004B8D; padding:20px; border-radius:10px; text-align:center;"><h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3><h1 style="color:white; font-size:45px; margin:0;">{abiertas}</h1></div>""", unsafe_allow_html=True)
    c2.metric("Pipeline USD", f"${df[df['estado']!='Facturada']['total'].astype(float).sum():,.0f}")
    c3.metric("Prospectos Activos", len(st.session_state['leads_db']))
    
    st.divider()
    if not df.empty:
        fig = px.pie(df, names='estado', title="Estado Global", color_discrete_map={'Facturada':'#004B8D', 'Enviada':'#6FBCE3', 'Aprobada':'#228B22'})
        st.plotly_chart(fig, use_container_width=True)

def modulo_cotizador():
    st.title("📝 Cotizador")
    cc1, cc2, cc3, cc4 = st.columns(4)
    es_nuevo = cc1.checkbox("¿Cliente Nuevo?", key="chk_nuevo")
    
    if es_nuevo:
        emp = cc1.text_input("Empresa Nueva")
        ori = cc2.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Referido"])
        con = cc3.text_input("Contacto"); ema = cc4.text_input("Email")
    else:
        lista_cli = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = cc1.selectbox("Cliente", [""] + lista_cli)
        con = cc2.text_input("Contacto"); ema = cc3.text_input("Email"); ori = "Existente"

    ps = st.selectbox("País", TODOS_LOS_PAISES)
    ctx = {"mon": "UF", "dp": df_p_cl, "tipo": "Loc"} if ps == "Chile" else {"mon": "US$", "dp": df_p_usd, "tipo": "Int"}
    
    tp, ts = st.tabs(["Assessments", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Producto", lp); qp = c2.number_input("Cantidad", 1, 10000, 10)
        
        t_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación') + qp
        up = calc_xls(ctx['dp'], sp, t_qty, ctx['tipo'] == 'Loc')
        c3.metric("Unitario", f"{up:,.2f}")
        
        if c4.button("Agregar"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # Actualizar precios retroactivos
            cur_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], cur_qty, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])})
            st.rerun()

    if st.session_state['carrito']:
        df_c = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_c, use_container_width=True, key="tabla_cot")
        st.session_state['carrito'] = edited.to_dict('records')
        sub = sum(i['Total'] for i in st.session_state['carrito'])
        st.metric("Total", f"{ctx['mon']} {sub:,.2f}")
        
        if st.button("GUARDAR COTIZACIÓN"):
            if es_nuevo and emp:
                st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": emp, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date())})
                github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
            
            nid = f"TP-{random.randint(1000,9999)}"
            nueva = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':sub, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':st.session_state['current_user'], 'items':st.session_state['carrito']}
            st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([nueva])], ignore_index=True)
            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
            st.session_state['carrito'] = []; st.success("Guardada"); time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento")
    df = st.session_state['cotizaciones']
    for i, r in df.sort_values('fecha', ascending=False).iterrows():
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_st = c1.selectbox("Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"], index=0, key=f"st_{r['id']}")
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_{r['id']}")
            if c3.button("Actualizar", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st
                st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                if new_st == "Aprobada": st.balloons() # ANIMACION APROBADO
                st.success("OK"); st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera")
    df = st.session_state['cotizaciones']
    
    t1, t2, t3 = st.tabs(["📝 Pendientes por País", "💵 Gestión de Pagos", "📂 Historial"])
    
    with t1:
        pendientes = df[df['estado'] == 'Aprobada']
        if pendientes.empty: st.success("Todo facturado."); return
        
        # Agrupar por País
        paises_pendientes = pendientes['pais'].unique()
        for pais in paises_pendientes:
            # Color por Pais
            estilo = "finance-card-default"
            if pais == "Chile": estilo = "finance-card-chile"
            elif pais == "Brasil": estilo = "finance-card-brasil"
            elif pais in ["Panamá", "Panama"]: estilo = "finance-card-panama"
            
            st.markdown(f"### 📍 {pais}")
            subset = pendientes[pendientes['pais'] == pais]
            
            for i, r in subset.iterrows():
                with st.container():
                    st.markdown(f"""<div class="{estilo}"><b>{r['empresa']}</b> | ID: {r['id']} | Total: {r['moneda']} {r['total']:,.2f}</div>""", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns([2,2,1])
                    n_inv = c1.text_input("N° Factura", key=f"inv_{r['id']}")
                    up_f = c2.file_uploader("PDF Factura", type=['pdf'], key=f"upf_{r['id']}")
                    if c3.button("Facturar", key=f"fbtn_{r['id']}"):
                        if n_inv:
                            st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                            st.session_state['cotizaciones'].at[i, 'factura'] = n_inv
                            if up_f: st.session_state['cotizaciones'].at[i, 'factura_file'] = base64.b64encode(up_f.read()).decode()
                            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                            st.balloons(); lluvia_dolares() # ANIMACION FACTURADO
                            st.rerun()

    with t2:
        st.subheader("Control de Cobranza")
        facturadas = df[df['estado'] == 'Facturada']
        for i, r in facturadas.iterrows():
            with st.expander(f"Fac: {r['factura']} | {r['empresa']} | Status: {r['pago']}"):
                c1, c2 = st.columns(2)
                p_status = c1.selectbox("Estado Pago", ["Pendiente", "Pagada", "Vencida"], key=f"pay_{r['id']}")
                if c2.button("Actualizar Pago", key=f"pbtn_{r['id']}"):
                    st.session_state['cotizaciones'].at[i, 'pago'] = p_status
                    github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                    if p_status == "Pagada": lluvia_dolares() # ANIMACION PAGO
                    st.success("Cobranza actualizada"); st.rerun()

    with t3:
        st.dataframe(df[df['estado'] == 'Facturada'][['fecha', 'pais', 'empresa', 'total', 'factura', 'pago']], use_container_width=True)

def modulo_crm():
    st.title("📇 CRM")
    st.dataframe(pd.DataFrame(st.session_state['leads_db']), use_container_width=True)

def modulo_admin():
    st.title("👥 Admin")
    st.write("Usuarios registrados:", st.session_state['users_db'])

# ==============================================================================
# 8. LOGIN Y NAVEGACIÓN
# ==============================================================================
def login_page():
    logo_url = "https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg"
    e1, col_log, e2 = st.columns([1, 1.5, 1])
    with col_log:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""<div class="login-container"><img src="{logo_url}" width="280"><h2 class="login-header">Acceso al Sistema</h2><p style="color: #666;">Expertos en Digitalización de RRHH</p></div>""", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR AL PORTAL", use_container_width=True):
                user = st.session_state['users_db'].get(u)
                if user and bcrypt.checkpw(p.encode(), user['password_hash'].encode()):
                    st.session_state['auth_status'] = True; st.session_state['current_user'] = u; st.rerun()
                else: st.error("Acceso incorrecto")

if not st.session_state['auth_status']:
    login_page()
else:
    with st.sidebar:
        st.image("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg", width=150)
        menu = option_menu("Menú", ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"], 
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
