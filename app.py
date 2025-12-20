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
# 6. LOGICA DE NEGOCIO Y DATOS
# ==============================================================================
@st.cache_data(ttl=60)
def cargar_precios():
    try:
        url = st.secrets["github"]["url_precios"]
        r = requests.get(url, headers={"Authorization": f"token {st.secrets['github']['token']}"})
        if r.status_code == 200:
            xls = pd.ExcelFile(io.BytesIO(r.content))
            def lh(n): return pd.read_excel(xls, n) if n in xls.sheet_names else pd.DataFrame()
            return (lh('Pruebas Int'), lh('Servicios Int'), lh('Config'), lh('Pruebas_CL'), lh('Servicios_CL'), lh('Pruebas_BR'), lh('Servicios_BR'))
        return (pd.DataFrame(),)*7
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

def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "ds": df_s_cl, "tipo": "Loc"}
    if pais in ["Brasil", "Brazil"]: return {"mon": "R$", "dp": df_p_br, "ds": df_s_br, "tipo": "Loc"}
    fil = df_config[df_config['Pais'] == pais]
    return {"mon": "US$", "dp": df_p_usd, "ds": df_s_usd, "tipo": "Int", "niv": fil.iloc[0]['Nivel'] if not fil.empty else "Medio"}

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
        if c <= t:
            col_name = str(t)
            if col_name in r.columns: return float(r.iloc[0][col_name])
    return float(r.iloc[0, -1])

def safe_extract_qty(det_str):
    try: return int(str(det_str).lower().replace('x', '').strip().split(' ')[0].split('(')[0])
    except: return 0

# --- PDF ENGINE ---
LOGO_PATH = "logo_talentpro.jpg"
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102); self.cell(0, 15, getattr(self,'tit_doc','COTIZACIÓN'), 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)

def generar_pdf_final(emp, cli, items, calc, idioma_code, extras):
    # (Motor PDF completo restaurado)
    T = TEXTOS.get(idioma_code, TEXTOS["ES"]); pdf = PDF(); pdf.tit_doc="COTIZACIÓN"; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.cell(95,5,emp['Nombre'],0,0); pdf.cell(95,5,"Facturar a:",0,1)
    pdf.set_font("Arial",'',9); pdf.cell(95,5,emp['ID'],0,1); pdf.cell(95,5,cli['empresa'],0,1)
    pdf.ln(10); pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.cell(110,8,"Descripción",0,0,'L',1); pdf.cell(20,8,"Cant",0,0,'C',1); pdf.cell(30,8,"Unit",0,0,'R',1); pdf.cell(30,8,"Total",0,1,'R',1)
    pdf.set_text_color(0); mon=items[0]['Moneda']
    for i in items:
        pdf.cell(110,7,i['Desc'][:60],'B',0,'L'); pdf.cell(20,7,str(i['Det']),'B',0,'C'); pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(10); pdf.cell(140,7,"SUBTOTAL",0,0,'R'); pdf.cell(40,7,f"{mon} {calc['subtotal']:,.2f}",0,1,'R')
    pdf.cell(140,7,"TOTAL",0,0,'R'); pdf.cell(40,7,f"{mon} {calc['total']:,.2f}",0,1,'R')
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Resumen de Operaciones")
    df = st.session_state['cotizaciones']
    
    # KPI SOLICITADO
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div style="background-color:#003366; padding:20px; border-radius:10px; text-align:center;"><h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3><h1 style="color:white; font-size:45px; margin:0;">{abiertas}</h1></div>""", unsafe_allow_html=True)
    c2.metric("Total Prospectos", len(st.session_state['leads_db']))
    c3.metric("Facturación Mes", f"${df[df['estado']=='Facturada']['total'].sum():,.0f}")
    
    st.divider()
    if not df.empty:
        fig = px.bar(df, x='vendedor', y='total', color='estado', title="Ventas por Ejecutivo")
        st.plotly_chart(fig, use_container_width=True)

def modulo_crm():
    st.title("📇 Gestión de Leads y Cartera")
    tab1, tab2, tab3 = st.tabs(["📋 Leads Activos", "🏢 Cartera Clientes", "📥 Importar CSV"])
    
    with tab1:
        with st.expander("➕ Crear Nuevo Lead"):
            with st.form("new_lead"):
                c1, c2, c3 = st.columns(3); cli = c1.text_input("Empresa"); pais = c2.selectbox("País", TODOS_LOS_PAISES); area = c3.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"])
                ori = st.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Referido"]); exp = st.text_area("Expectativa")
                if st.form_submit_button("Guardar"):
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": cli, "Pais": pais, "Origen": ori, "Etapa": "Prospección", "Expectativa": exp, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Lead Creado"); st.rerun()
        
        # Gestión de Leads (Editar)
        df_l = pd.DataFrame(st.session_state['leads_db'])
        if not df_l.empty:
            sel_l = st.selectbox("Editar Lead", [""] + df_l['Cliente'].tolist())
            if sel_l:
                idx = df_l[df_l['Cliente']==sel_l].index[0]
                with st.form("edit_l"):
                    st.write(f"Editando {sel_l}")
                    new_etapa = st.selectbox("Etapa", ["Prospección", "Contacto", "Propuesta", "Cerrado Ganado", "Cerrado Perdido"], index=0)
                    if st.form_submit_button("Actualizar"):
                        st.session_state['leads_db'][idx]['Etapa'] = new_etapa; github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.rerun()

def modulo_cotizador():
    st.title("📝 Cotizador Inteligente")
    edit_data = st.session_state.get('cot_edit_data')
    
    # --- CLIENTE NUEVO / EXISTENTE ---
    cc1, cc2, cc3 = st.columns([1,1,2])
    es_nuevo = cc1.checkbox("¿Cliente Nuevo?", value=False)
    
    if es_nuevo:
        emp = cc1.text_input("Nombre Empresa Nueva")
        ori = cc2.selectbox("Origen del Cliente", ["SHL", "TalentPRO", "LinkedIn", "Referido"])
        con = cc3.text_input("Contacto / Email")
    else:
        lista_cli = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = cc1.selectbox("Cliente", [""] + lista_cli)
        con = cc2.text_input("Contacto / Email")
        ori = "Existente"

    ps = st.selectbox("País", TODOS_LOS_PAISES); ctx = obtener_contexto(ps)
    
    # --- SECCIÓN PRODUCTOS ---
    tp, ts = st.tabs(["Assessments", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Item", lp); qp = c2.number_input("Cant", 1, 10000, 10)
        
        # Volumen Acumulado
        qty_acc = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
        up = calc_xls(ctx['dp'], sp, qty_acc + qp, ctx['tipo'] == 'Loc')
        c3.metric("Unit", f"{up:,.2f}")
        
        if c4.button("Add"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # RECALCULO RETROACTIVO
            t_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], t_qty, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])})
            st.rerun()

    # --- TABLA Y TOTALES ---
    if st.session_state['carrito']:
        df_c = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_c, use_container_width=True, key="cart_ed")
        st.session_state['carrito'] = edited.to_dict('records')
        
        sub = sum(i['Total'] for i in st.session_state['carrito']); eva = sum(i['Total'] for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
        
        col_L, col_R = st.columns([3,1])
        with col_R:
            fee = st.checkbox("Fee 10%"); vfee = eva*0.1 if fee else 0
            # Descuento por simulación
            tipo_d = st.selectbox("Tipo Descuento", ["Fijo", "Simular Vol"])
            dsc = 0.0
            if tipo_d == "Simular Vol":
                v_sim = st.number_input("Simular Qty", 1, 10000, 1000)
                tot_sim = sum(calc_xls(ctx['dp'], i['Desc'], v_sim, ctx['tipo'] == 'Loc') * safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
                dsc = max(0, eva - tot_sim); st.caption(f"Ahorro: {dsc:,.2f}")
            else: dsc = st.number_input("Monto Desc")
            
            fin = sub + vfee - dsc; st.metric("TOTAL", f"{ctx['mon']} {fin:,.2f}")
            
            if st.button("GUARDAR"):
                if es_nuevo and emp:
                    st.session_state['leads_db'].append({"Cliente": emp, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date())})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                
                nid = f"TP-{random.randint(1000,9999)}"
                row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':st.session_state['current_user'], 'items': st.session_state['carrito']}
                st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.session_state['carrito'] = []; st.success("Guardado"); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento de Ventas")
    df = st.session_state['cotizaciones']
    for i, r in df.sort_values('fecha', ascending=False).iterrows():
        # KEY UNICA PARA CADA WIDGET PARA EVITAR EL ERROR DE DUPLICADOS
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_st = c1.selectbox("Cambiar Estado", ["Enviada", "Aprobada", "Rechazada", "Facturada"], index=0, key=f"st_{r['id']}")
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_{r['id']}")
            if c3.button("Actualizar", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st
                st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.rerun()

def modulo_finanzas():
    st.title("💰 Facturación y Cobranza")
    df = st.session_state['cotizaciones']
    pendientes = df[df['estado'] == 'Aprobada']
    for i, r in pendientes.iterrows():
        with st.container(border=True):
            st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']}")
            # KEY UNICA PARA FINANZAS
            n_inv = st.text_input("N° Factura", key=f"inv_{r['id']}")
            if st.button("Emitir Factura", key=f"fbtn_{r['id']}"):
                if n_inv:
                    st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                    st.session_state['cotizaciones'].at[i, 'factura'] = n_inv
                    github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                    lluvia_dolares(); st.rerun()

def modulo_admin():
    st.title("👥 Administración y Metas")
    users = st.session_state['users_db']
    # Restaurado el control de células y metas
    with st.expander("Configurar Células"):
        conf = users.get('_CONFIG_ORG', {})
        nc = st.text_input("Nueva Célula")
        if st.button("Crear Célula"):
            conf[nc] = {'meta': 0, 'subs': {}}; users['_CONFIG_ORG'] = conf
            github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.rerun()
    st.write("Usuarios:", pd.DataFrame(users).T)

# ==============================================================================
# 8. LOGIN Y NAVEGACIÓN
# ==============================================================================
def login_page():
    st.title("🔒 TalentPRO CRM Login")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in st.session_state['users_db']:
            st.session_state['auth_status'] = True; st.session_state['current_user'] = u; st.rerun()
        else: st.error("Acceso Denegado")

if not st.session_state['auth_status']:
    login_page()
else:
    with st.sidebar:
        menu = option_menu("Menú", ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"], 
                           icons=['bar-chart', 'check2', 'people', 'file-earmark', 'currency-dollar', 'shield-lock'], 
                           default_index=st.session_state['menu_idx'])
        st.session_state['menu_idx'] = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"].index(menu)
        if st.button("Salir"): st.session_state.clear(); st.rerun()

    if menu == "Dashboards": modulo_dashboard()
    elif menu == "Seguimiento": modulo_seguimiento()
    elif menu == "Prospectos y Clientes": modulo_crm()
    elif menu == "Cotizador": modulo_cotizador()
    elif menu == "Finanzas": modulo_finanzas()
    elif menu == "Usuarios": modulo_admin()
