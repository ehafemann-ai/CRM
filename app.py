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
usuario_es_super_admin = "acceso" in st.query_params and st.query_params["acceso"] == CLAVE_SECRETA

# --- 3. ESTILOS CSS (IDENTIDAD TALENTPRO Y DISEÑO DE TARJETAS) ---
st.markdown(f"""
    <style>
    .stMetric {{background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}}
    [data-testid="stSidebar"] {{ padding-top: 0rem; }}
    
    /* Botones Corporativos */
    div.stButton > button:first-child {{
        background-color: #004B8D; color: white; border-radius: 8px; font-weight: bold; border: none;
    }}
    div.stButton > button:first-child:hover {{ background-color: #6FBCE3; color: white; }}

    /* Caja de Login */
    .login-container {{
        background-color: #ffffff; padding: 40px; border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-top: 5px solid #004B8D; text-align: center;
    }}

    /* Tarjetas Finanzas por País */
    .finance-card-chile {{ border-left: 10px solid #004B8D; background-color: #f0f7ff; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; }}
    .finance-card-brasil {{ border-left: 10px solid #228B22; background-color: #f0fff0; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; }}
    .finance-card-panama {{ border-left: 10px solid #FFD700; background-color: #fffdf0; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; }}
    .finance-card-peru {{ border-left: 10px solid #FF0000; background-color: #fff5f5; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; }}
    .finance-card-default {{ border-left: 10px solid #6FBCE3; background-color: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; }}
    
    /* Animación Lluvia */
    @keyframes fall {{ 0% {{ transform: translateY(-10vh); opacity: 1; }} 100% {{ transform: translateY(110vh); opacity: 0; }} }}
    .money-rain {{ position: fixed; top: 0; font-size: 2.5rem; animation: fall linear forwards; z-index: 99999; pointer-events: none; }}
    </style>
""", unsafe_allow_html=True)

def animar_dinero(simbolo="💲"):
    h = "".join([f'<div class="money-rain" style="left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,2)}s; animation-duration:{random.uniform(2,4)}s;">{simbolo}</div>' for i in range(40)])
    st.markdown(h, unsafe_allow_html=True)

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
        return ({}, None) if "usuarios" in url_key else ([], None)
    except: return ([], None)

def github_push_json(url_key, data, sha):
    try:
        url = st.secrets['github'][url_key]
        payload = {"message": "Update DB", "content": base64.b64encode(json.dumps(data, indent=4, default=str).encode()).decode(), "sha": sha}
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
    st.session_state['users_db'], st.session_state['users_sha'] = github_get_json('url_usuarios')
    if not st.session_state['users_db']:
        hashed = bcrypt.hashpw(st.secrets['auth']['admin_pass'].encode(), bcrypt.gensalt()).decode()
        st.session_state['users_db'] = {st.secrets['auth']['admin_user']: {"name": "Super Admin", "role": "Super Admin", "password_hash": hashed}}
    if '_CONFIG_ORG' not in st.session_state['users_db']: st.session_state['users_db']['_CONFIG_ORG'] = {}

if 'leads_db' not in st.session_state:
    st.session_state['leads_db'], st.session_state['leads_sha'] = github_get_json('url_leads')

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
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
if 'menu_idx' not in st.session_state: st.session_state['menu_idx'] = 0
if 'cot_edit_data' not in st.session_state: st.session_state['cot_edit_data'] = None

# ==============================================================================
# 6. LÓGICA DE NEGOCIO (PRECIOS, TASAS, PDF)
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
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil", "Panamá", "Perú"]

@st.cache_data(ttl=3600)
def obtener_indicadores():
    try:
        r = requests.get('https://mindicador.cl/api', timeout=2).json()
        return {"UF": r['uf']['valor'], "USD_CLP": r['dolar']['valor'], "USD_BRL": 5.4}
    except: return {"UF": 39000, "USD_CLP": 950, "USD_BRL": 5.4}
TASAS = obtener_indicadores()

def calc_xls(df, p, c, l):
    if df.empty: return 0.0
    r = df[df['Producto'].str.strip().str.lower() == str(p).strip().lower()]
    if r.empty: return 0.0
    if c > 1000:
        inf_cols = ['Infinito', 'infinito', '1001', '1001+', '1000+', '>1000']
        for col in inf_cols:
            if col in r.columns: return float(r.iloc[0][col])
        return float(r.iloc[0, -1])
    ts = [50, 100, 200, 300, 500, 1000] if l else [100, 200, 300, 500, 1000]
    for t in ts:
        if c <= t:
            if str(t) in r.columns: return float(r.iloc[0][str(t)])
            elif t in r.columns: return float(r.iloc[0][t])
    return float(r.iloc[0, -1])

def safe_extract_qty(det):
    try: return int(str(det).lower().replace('x','').strip().split(' ')[0].split('(')[0])
    except: return 0

def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "ds": df_s_cl, "tipo": "Loc"}
    if pais in ["Brasil", "Brazil"]: return {"mon": "R$", "dp": df_p_br, "ds": df_s_br, "tipo": "Loc"}
    return {"mon": "US$", "dp": df_p_usd, "ds": df_s_usd, "tipo": "Int"}

def get_impuestos(pais, sub, eva):
    if pais == "Chile": return "IVA (19%)", eva * 0.19
    if pais in ["Panamá", "Panama"]: return "ITBMS (7%)", sub * 0.07
    return "", 0

def clasificar_cliente(monto):
    if monto >= 20000: return "Grande"
    if 10000 <= monto < 20000: return "Mediano"
    return "Chico"

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Tamboré"},
    "Peru": {"Nombre": "TALENTPRO PERU S.A.C.", "ID": "RUC 20606246847", "Dir": "Lima"},
    "Chile_Pruebas": {"Nombre": "TALENTPRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Vitacura"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Vitacura"},
    "Latam": {"Nombre": "TALENTPRO LATAM S.A.", "ID": "RUC: 155723672", "Dir": "Panamá"}
}

# --- PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        try: self.image("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg", 10, 10, 35)
        except: pass
        self.set_font('Arial', 'B', 15); self.cell(0, 10, 'COTIZACIÓN', 0, 1, 'R'); self.ln(10)

def generar_pdf_final(emp, cli, items, calc, idi, ext):
    pdf = PDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 10)
    pdf.cell(100, 5, emp['Nombre'], 0, 0); pdf.cell(0, 5, "FACTURAR A:", 0, 1)
    pdf.set_font("Arial", '', 9); pdf.cell(100, 5, emp['ID'], 0, 0); pdf.cell(0, 5, cli['empresa'], 0, 1); pdf.ln(10)
    pdf.set_fill_color(0, 75, 141); pdf.set_text_color(255); pdf.cell(110, 8, "Descripción", 1, 0, 'L', 1); pdf.cell(20, 8, "Cant", 1, 0, 'C', 1); pdf.cell(30, 8, "Unit", 1, 0, 'R', 1); pdf.cell(30, 8, "Total", 1, 1, 'R', 1)
    pdf.set_text_color(0); mon = items[0]['Moneda']
    for i in items:
        pdf.cell(110, 7, str(i['Desc'])[:55], 1); pdf.cell(20, 7, str(i['Det']), 1, 0, 'C'); pdf.cell(30, 7, f"{i['Unit']:,.2f}", 1, 0, 'R'); pdf.cell(30, 7, f"{i['Total']:,.2f}", 1, 1, 'R')
    pdf.ln(5); pdf.cell(160, 7, "TOTAL", 0, 0, 'R'); pdf.cell(30, 7, f"{mon} {calc['total']:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Resumen Ejecutivo TalentPRO")
    df = st.session_state['cotizaciones']
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div style="background-color:#004B8D; padding:20px; border-radius:10px; text-align:center;"><h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3><h1 style="color:white; font-size:45px; margin:0;">{abiertas}</h1></div>""", unsafe_allow_html=True)
    c2.metric("Pipeline USD Est.", f"${df[df['estado']!='Facturada']['total'].astype(float).sum():,.0f}")
    c3.metric("Prospectos Activos", len(st.session_state['leads_db']))
    
    st.divider()
    tab_gen, tab_lead = st.tabs(["📈 Ventas", "📇 Funnel Leads"])
    with tab_gen:
        if not df.empty:
            fig = px.bar(df, x='vendedor', y='total', color='estado', title="Desempeño por Ejecutivo", color_discrete_map={'Facturada':'#004B8D', 'Enviada':'#6FBCE3'})
            st.plotly_chart(fig, use_container_width=True)
    with tab_lead:
        df_l = pd.DataFrame(st.session_state['leads_db'])
        if not df_l.empty:
            st.plotly_chart(px.funnel(df_l['Etapa'].value_counts().reset_index(), x='count', y='Etapa'), use_container_width=True)

def modulo_crm():
    st.title("📇 Gestión de Leads y Clientes")
    tab1, tab2, tab3 = st.tabs(["📋 Gestión Leads", "🏢 Cartera Clientes", "📥 Importar Masivo"])
    with tab1:
        with st.expander("➕ Nuevo Prospecto", expanded=False):
            with st.form("new_lead_f"):
                cx1, cx2, cx3 = st.columns(3); cli = cx1.text_input("Empresa"); ps = cx2.selectbox("País", TODOS_LOS_PAISES); ar = cx3.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"])
                ori = st.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Referido", "Prospección Propia"]); exp = st.text_area("Expectativa / Dolor")
                if st.form_submit_button("Guardar"):
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": cli, "Pais": ps, "Area": ar, "Origen": ori, "Etapa": "Prospección", "Expectativa": exp, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Guardado"); st.rerun()
        df_l = pd.DataFrame(st.session_state['leads_db'])
        if not df_l.empty:
            sel_l = st.selectbox("Gestionar Lead", [""] + df_l['Cliente'].tolist())
            if sel_l:
                idx = df_l[df_l['Cliente']==sel_l].index[0]
                with st.form(f"edit_l_{idx}"):
                    ne = st.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"], index=0)
                    if st.form_submit_button("Actualizar"):
                        st.session_state['leads_db'][idx]['Etapa'] = ne; github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.rerun()
            st.dataframe(df_l, use_container_width=True)

def modulo_cotizador():
    st.title("📝 Cotizador TalentPRO")
    edit_data = st.session_state.get('cot_edit_data')
    if edit_data:
        st.info(f"✏️ Modo Edición: {edit_data['id_orig']}")
        if st.button("Cancelar Edición"): st.session_state['carrito']=[]; st.session_state['cot_edit_data']=None; st.rerun()

    # --- ALINEACIÓN: CLIENTE, CONTACTO, EMAIL ---
    r1, r2, r3 = st.columns(3)
    es_nuevo = r1.checkbox("¿Cliente Nuevo?", value=False, key="new_c_cot")
    if es_nuevo:
        emp = r1.text_input("Empresa Nueva", placeholder="Empresa"); con = r2.text_input("Contacto", placeholder="Nombre"); ema = r3.text_input("Email", placeholder="email")
        ori = st.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Prospección", "Referido"])
    else:
        clis = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = r1.selectbox("Cliente", [""] + clis, index=clis.index(edit_data['empresa'])+1 if edit_data and edit_data['empresa'] in clis else 0)
        con = r2.text_input("Contacto", value=edit_data['contacto'] if edit_data else ""); ema = r3.text_input("Email", value=edit_data['email'] if edit_data else ""); ori = "Existente"

    ps = st.selectbox("País de Facturación", TODOS_LOS_PAISES, index=TODOS_LOS_PAISES.index(edit_data['pais']) if edit_data and edit_data['pais'] in TODOS_LOS_PAISES else 0)
    ctx = obtener_contexto(ps)
    
    tp, ts = st.tabs(["Assessments", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Item", lp); qp = c2.number_input("Cant", 1, 10000, 10)
        
        # --- CÁLCULO VOLUMEN RETROACTIVO ---
        total_evals_futuro = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación') + qp
        up = calc_xls(ctx['dp'], sp, total_evals_futuro, ctx['tipo'] == 'Loc')
        c3.metric("Unit.", f"{up:,.2f}")
        
        if c4.button("Add"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # Forzar actualización de todo el carrito
            cur_tot = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for idx, item in enumerate(st.session_state['carrito']):
                if item['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], item['Desc'], cur_tot, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][idx].update({"Unit": nu, "Total": nu * safe_extract_qty(item['Det'])})
            st.rerun()

    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        if ls:
            ss=c1.selectbox("Servicio", ["Certificación PAA"]+ls)
            if "PAA" in ss: qs=c2.number_input("Personas",1,100,1); us=calc_paa(qs,ctx['mon']); dt=f"x{qs}"
            else: r=c2.selectbox("Rol",['Senior','BM','BP']); qs=1; rw=ctx['ds'][ctx['ds']['Servicio']==ss]; us=float(rw.iloc[0][r]) if not rw.empty else 0; dt=f"x{qs} ({r})"
            c3.metric("Unit",f"{us:,.2f}"); if c4.button("Add ", key="add_s"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        df_cart = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_cart, use_container_width=True, key="cart_ed_f")
        st.session_state['carrito'] = edited.to_dict('records')
        
        # Sync si editan tabla
        qty_manual = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
        for i, it in enumerate(st.session_state['carrito']):
            if it['Ítem'] == 'Evaluación':
                nu = calc_xls(ctx['dp'], it['Desc'], qty_manual, ctx['tipo'] == 'Loc')
                if abs(it['Unit'] - nu) > 0.01:
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])}); st.rerun()

        sub = sum(i['Total'] for i in st.session_state['carrito']); eva = sum(i['Total'] for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
        cL, cR = st.columns([3,1])
        with cL: 
            if st.button("🗑️ LIMPIAR COTIZACIÓN"): st.session_state['carrito'] = []; st.rerun()
        with cR:
            fee = st.checkbox("Fee 10%", value=edit_data['fee']>0 if edit_data else False); vfee = eva*0.1 if fee else 0
            tipo_d = st.selectbox("Descuento", ["Monto", "Simular Vol"])
            dsc = 0.0
            if tipo_d == "Simular Vol":
                v_sim = st.number_input("Simular Qty", 1, 10000, 1000); tot_sim = sum(calc_xls(ctx['dp'], i['Desc'], v_sim, ctx['tipo'] == 'Loc') * safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
                dsc = max(0, eva - tot_sim); st.caption(f"Ahorro: {dsc:,.2f}")
            else: dsc = st.number_input("Descuento $", value=float(edit_data['desc']) if edit_data else 0.0)
            
            tn, tv = get_impuestos(ps, sub, eva); fin = sub + vfee + tv - dsc
            st.metric("TOTAL", f"{ctx['mon']} {fin:,.2f}")
            
            if st.button("GUARDAR / ACTUALIZAR", type="primary"):
                if es_nuevo and emp:
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": emp, "Pais": ps, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date())})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                nid = edit_data['id_orig'] if edit_data else f"TP-{random.randint(1000,9999)}"
                row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':st.session_state['current_user'], 'items': st.session_state['carrito'], 'pdf_data':{'contacto':con, 'email':ema, 'fee':vfee, 'desc':dsc}, 'pago':'Pendiente'}
                if edit_data:
                    idx = st.session_state['cotizaciones'][st.session_state['cotizaciones']['id']==nid].index
                    st.session_state['cotizaciones'].iloc[idx[0]] = row
                else:
                    st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.session_state['carrito']=[]; st.session_state['cot_edit_data']=None; st.success("OK"); time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento de Ventas")
    df = st.session_state['cotizaciones'].sort_values('fecha', ascending=False)
    for i, r in df.iterrows():
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_st = c1.selectbox("Cambiar Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"], index=0, key=f"st_s_{r['id']}")
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_s_{r['id']}")
            if c3.button("Actualizar ", key=f"btn_s_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st; st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                if new_st == "Aprobada": st.balloons()
                st.success("OK"); st.rerun()
            if st.button("✏️ Modificar / Clonar", key=f"ed_s_{r['id']}"):
                st.session_state['carrito'] = r['items']; st.session_state['cot_edit_data'] = {'id_orig': r['id'], 'empresa': r['empresa'], 'pais': r['pais'], 'contacto': r['pdf_data'].get('contacto',''), 'email': r['pdf_data'].get('email',''), 'fee': r['pdf_data'].get('fee',0), 'desc': r['pdf_data'].get('desc',0)}
                st.session_state['menu_idx'] = 3; st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera TalentPRO")
    df = st.session_state['cotizaciones']
    tab_p, tab_c = st.tabs(["📝 Pendientes por País", "💵 Cobranza"])
    with tab_p:
        pend = df[df['estado'] == 'Aprobada']
        for ps in pend['pais'].unique():
            cls = "finance-card-chile" if ps=="Chile" else "finance-card-brasil" if ps=="Brasil" else "finance-card-panama" if ps=="Panama" else "finance-card-default"
            st.markdown(f"### 📍 {ps}")
            for i, r in pend[pend['pais']==ps].iterrows():
                with st.container():
                    st.markdown(f'<div class="{cls}"><b>{r["empresa"]}</b> | {r["id"]} | {r["moneda"]} {r["total"]:,.2f}</div>', unsafe_allow_html=True)
                    if r['pais']=="Chile" and r.get('items'):
                        pi=[x for x in r['items'] if x['Ítem']=='Evaluación']; si=[x for x in r['items'] if x['Ítem']=='Servicio']
                        if pi and si: st.warning("💡 Nota: Emitir SpA para Assessments y Ltda para Servicios.")
                    c1, c2, c3 = st.columns([2,2,1]); n_inv = c1.text_input("N° Factura", key=f"inv_n_{r['id']}"); up_f = c2.file_uploader("PDF", type=['pdf'], key=f"up_f_{r['id']}")
                    if c3.button("Facturar ", key=f"btn_f_{r['id']}"):
                        if n_inv:
                            st.session_state['cotizaciones'].at[i, 'estado']='Facturada'; st.session_state['cotizaciones'].at[i, 'factura']=n_inv
                            if up_f: st.session_state['cotizaciones'].at[i, 'factura_file']=base64.b64encode(up_f.read()).decode()
                            github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                            st.balloons(); animar_dinero(); st.rerun()
    with tab_c:
        fact = df[df['estado'] == 'Facturada']
        for i, r in fact.iterrows():
            with st.expander(f"Fac: {r['factura']} | {r['empresa']} | {r['pago']}"):
                c1, c2 = st.columns(2); p_st = c1.selectbox("Pago", ["Pendiente", "Pagada", "Vencida"], key=f"pay_{r['id']}")
                if c2.button("Confirmar Pago ", key=f"btn_p_{r['id']}"):
                    st.session_state['cotizaciones'].at[i, 'pago'] = p_st; github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                    if p_st == "Pagada": animar_dinero("💵"); st.rerun()

def modulo_admin():
    st.title("👥 Administración y Metas")
    users = st.session_state['users_db']
    tab_u, tab_e, tab_reset = st.tabs(["Gestionar Usuarios", "Estructura Org.", "RESET"])
    with tab_u:
        edit_u = st.selectbox("Editar Usuario", [k for k in users.keys() if not k.startswith("_")])
        if edit_u:
            u = users[edit_u]; st.markdown(f"##### Perfil: {u['name']}")
            col_m1, col_m2 = st.columns(2); m_rev = col_m1.number_input("Meta Facturación ($)", value=float(u.get('meta_rev',0)))
            if st.button("Guardar Cambios del Usuario"):
                users[edit_u]['meta_rev'] = m_rev; github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.success("Guardado"); st.rerun()

# --- LOGIN & NAV ---
def login_page():
    logo_url = "https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg"
    e1, col, e2 = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""<div class="login-container"><img src="{logo_url}" width="280"><h2 style="color:#004B8D">Portal TalentPRO</h2></div>""", unsafe_allow_html=True)
        with st.form("login_f"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR", use_container_width=True):
                user = st.session_state['users_db'].get(u)
                if user and bcrypt.checkpw(p.encode(), user['password_hash'].encode()):
                    st.session_state['auth_status'] = True; st.session_state['current_user'] = u; st.rerun()
                else: st.error("Acceso denegado")

if not st.session_state['auth_status']:
    login_page()
else:
    with st.sidebar:
        st.image("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg", width=150)
        menu = option_menu("Menú", ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"], 
                           icons=['bar-chart', 'check2', 'people', 'file-earmark', 'currency-dollar', 'shield-lock'], 
                           default_index=st.session_state['menu_idx'])
        st.session_state['menu_idx'] = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"].index(menu)
        if st.button("SALIR"): st.session_state.clear(); st.rerun()

    if menu == "Dashboards": modulo_dashboard()
    elif menu == "Seguimiento": modulo_seguimiento()
    elif menu == "Prospectos y Clientes": modulo_crm()
    elif menu == "Cotizador": modulo_cotizador()
    elif menu == "Finanzas": modulo_finanzas()
    elif menu == "Usuarios": modulo_admin()
