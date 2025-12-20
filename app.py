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
    else: st.session_state['cotizaciones'] = pd.DataFrame(columns=cols)

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

def calc_paa(c, m):
    b = 1500 if c<=2 else 1200 if c<=5 else 1100
    if m == "US$": return b
    if m == "UF": return (b*TASAS['USD_CLP'])/TASAS['UF'] if TASAS['UF'] > 0 else 0
    return b*TASAS['USD_BRL']

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

def get_user_teams_list(user_data):
    raw = user_data.get('equipo', [])
    if isinstance(raw, str): return [raw] if raw and raw != "N/A" else []
    return raw

# --- PDF ENGINE ---
LOGO_PATH = "logo_talentpro.jpg"
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102); self.cell(0, 15, getattr(self,'tit_doc','COTIZACIÓN'), 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128); self.cell(0, 10, 'TalentPro Digital System', 0, 0, 'C')

def generar_pdf_final(emp, cli, items, calc, idioma_code, extras):
    T = TEXTOS.get(idioma_code, {"desc":"Descripción", "qty":"Cant", "unit":"Unit", "total":"Total"}); pdf = PDF(); pdf.tit_doc="COTIZACIÓN"; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0); pdf.set_text_color(100); pdf.cell(95,5,"Facturar a:",0,1)
    pdf.set_font("Arial",'',9); pdf.set_text_color(50); y=pdf.get_y(); pdf.cell(95,5,emp['ID'],0,1); pdf.multi_cell(90,5,emp['Dir'])
    pdf.set_xy(105,y); pdf.set_font("Arial",'B',10); pdf.set_text_color(0); pdf.cell(95,5,cli['empresa'],0,1); pdf.set_xy(105,pdf.get_y()); pdf.set_font("Arial",'',9); pdf.set_text_color(50); pdf.cell(95,5,cli.get('contacto',''),0,1)
    pdf.ln(10); pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.set_font("Arial",'B',9); pdf.cell(110,8,T['desc'],0,0,'L',1); pdf.cell(20,8,T['qty'],0,0,'C',1); pdf.cell(30,8,T['unit'],0,0,'R',1); pdf.cell(30,8,T['total'],0,1,'R',1)
    pdf.set_text_color(0); pdf.set_font("Arial",'',8); mon=items[0]['Moneda']
    for i in items:
        pdf.cell(110,7,f"  {i['Desc'][:60]}",'B',0,'L'); pdf.cell(20,7,str(i['Det']),'B',0,'C'); pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(5); pdf.set_font("Arial",'B',10); pdf.cell(160,7,"SUBTOTAL",0,0,'R'); pdf.cell(30,7,f"{mon} {calc['subtotal']:,.2f}",0,1,'R')
    if calc.get('tax_val',0)>0: pdf.cell(160,7,calc.get('tax_name','TAX'),0,0,'R'); pdf.cell(30,7,f"{mon} {calc['tax_val']:,.2f}",0,1,'R')
    pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.cell(160,8,"TOTAL",0,0,'R',1); pdf.cell(30,8,f"{mon} {calc['total']:,.2f}",0,1,'R',1)
    return pdf.output(dest='S').encode('latin-1')

def lluvia_dolares():
    st.markdown("""<style>@keyframes fall {0% { transform: translateY(-10vh); opacity: 1; } 100% { transform: translateY(110vh); opacity: 0; }} .money-rain {position: fixed; top: 0; font-size: 2.5rem; animation: fall linear forwards; z-index: 99999; pointer-events: none;}</style>""", unsafe_allow_html=True)
    h = ""
    for i in range(40): h += f'<div class="money-rain" style="left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,2)}s; animation-duration:{random.uniform(2,4)}s;">💲</div>'
    st.markdown(h, unsafe_allow_html=True)

# ==============================================================================
# 7. MÓDULOS APP
# ==============================================================================

def modulo_dashboard():
    st.title("📊 Resumen Ejecutivo")
    df = st.session_state['cotizaciones']
    
    # --- MÉTRICA SOLICITADA: COTIZACIONES ABIERTAS ---
    abiertas = len(df[df['estado'].isin(['Enviada', 'Aprobada'])])
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div style="background-color:#003366; padding:20px; border-radius:10px; text-align:center;"><h3 style="color:white; margin:0;">Cotizaciones Abiertas</h3><h1 style="color:white; font-size:45px; margin:0;">{abiertas}</h1></div>""", unsafe_allow_html=True)
    c2.metric("Total Prospectos", len(st.session_state['leads_db']))
    c3.metric("Facturación Mes", f"${df[df['estado']=='Facturada']['total'].sum():,.0f}")
    
    st.divider()
    tab_gen, tab_kpi, tab_lead = st.tabs(["📊 General", "🎯 Metas", "📇 Leads"])
    with tab_gen:
        if not df.empty:
            fig = px.bar(df, x='vendedor', y='total', color='estado', title="Ventas por Ejecutivo")
            st.plotly_chart(fig, use_container_width=True)
    with tab_kpi:
        st.info("Configura las metas en el panel de Usuarios para ver el progreso aquí.")
    with tab_lead:
        df_l = pd.DataFrame(st.session_state['leads_db'])
        if not df_l.empty:
            st.plotly_chart(px.pie(df_l, names='Etapa', title="Funnel de Leads"), use_container_width=True)

def modulo_crm():
    st.title("📇 Gestión de Leads y Cartera")
    tab1, tab2, tab3 = st.tabs(["📋 Gestión de Leads", "🏢 Cartera Clientes", "📥 Importar Masivo"])
    
    with tab1:
        with st.expander("➕ Nuevo Prospecto", expanded=False):
            with st.form("form_lead"):
                c1, c2, c3 = st.columns(3); nom = c1.text_input("Empresa"); pais = c2.selectbox("País", TODOS_LOS_PAISES); area = c3.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"])
                ori = st.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Prospección Propia", "Referido"]); exp = st.text_area("Expectativa / Dolor")
                if st.form_submit_button("Guardar Lead"):
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": nom, "Pais": pais, "Area": area, "Origen": ori, "Etapa": "Prospección", "Expectativa": exp, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Lead guardado"); st.rerun()
        
        df_l = pd.DataFrame(st.session_state['leads_db'])
        if not df_l.empty:
            sel_l = st.selectbox("Gestionar Lead", [""] + df_l['Cliente'].tolist())
            if sel_l:
                idx = df_l[df_l['Cliente']==sel_l].index[0]
                ld = st.session_state['leads_db'][idx]
                with st.form(f"edit_l_{idx}"):
                    new_etapa = st.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Cerrado Ganado", "Cerrado Perdido", "Cliente Activo"], index=0)
                    new_exp = st.text_area("Expectativa", value=ld.get('Expectativa',''))
                    if st.form_submit_button("Actualizar Lead"):
                        st.session_state['leads_db'][idx]['Etapa'] = new_etapa
                        st.session_state['leads_db'][idx]['Expectativa'] = new_exp
                        github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha')); st.success("Actualizado"); st.rerun()
            st.dataframe(df_l, use_container_width=True)

def modulo_cotizador():
    st.title("📝 Cotizador TalentPRO")
    edit_data = st.session_state.get('cot_edit_data')
    
    # --- CLIENTE NUEVO / EXISTENTE + ORIGEN ---
    cc1, cc2, cc3, cc4 = st.columns(4)
    es_nuevo = cc1.checkbox("¿Cliente Nuevo?", value=False)
    
    if es_nuevo:
        emp = cc1.text_input("Empresa Nueva")
        ori = cc2.selectbox("Origen", ["SHL", "TalentPRO", "LinkedIn", "Referido", "Prospección Propia"])
        con = cc3.text_input("Contacto")
        ema = cc4.text_input("Email")
    else:
        lista_cli = sorted(list(set([l['Cliente'] for l in st.session_state['leads_db']] + st.session_state['cotizaciones']['empresa'].unique().tolist())))
        emp = cc1.selectbox("Cliente", [""] + lista_cli)
        con = cc2.text_input("Contacto")
        ema = cc3.text_input("Email")
        ori = "Existente"

    ps = st.selectbox("País Facturación", TODOS_LOS_PAISES); ctx = obtener_contexto(ps)
    
    tp, ts = st.tabs(["Assessments", "Servicios"])
    with tp:
        c1, c2, c3, c4 = st.columns([3,1,1,1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        sp = c1.selectbox("Producto", lp); qp = c2.number_input("Cant", 1, 10000, 10)
        
        # Volumen Acumulado
        qty_acc = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
        up = calc_xls(ctx['dp'], sp, qty_acc + qp, ctx['tipo'] == 'Loc')
        c3.metric("Unit", f"{up:,.2f}")
        
        if c4.button("Añadir"):
            st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
            # RECALCULO RETROACTIVO
            t_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], t_qty, ctx['tipo'] == 'Loc')
                    st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * safe_extract_qty(it['Det'])})
            st.rerun()

    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        if ls:
            ss=c1.selectbox("Servicio", ["Certificación PAA"]+ls)
            if "PAA" in ss: qs=c2.number_input("Personas",1,100,1); us=calc_paa(qs,ctx['mon']); dt=f"x{qs}"
            else: r=c2.selectbox("Rol",['Senior','BM','BP']); qs=1; rw=ctx['ds'][ctx['ds']['Servicio']==ss]; us=float(rw.iloc[0][r]) if not rw.empty else 0; dt=f"x{qs} ({r})"
            c3.metric("Unit",f"{us:,.2f}")
            if c4.button("Add ", key="adds"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        st.divider()
        df_c = pd.DataFrame(st.session_state['carrito'])
        edited = st.data_editor(df_c, use_container_width=True, key="cart_editor")
        st.session_state['carrito'] = edited.to_dict('records')
        
        # Sincronización proactiva de precios al editar cantidades en la tabla
        try:
            cur_tot_qty = sum(safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
            for i, it in enumerate(st.session_state['carrito']):
                if it['Ítem'] == 'Evaluación':
                    nu = calc_xls(ctx['dp'], it['Desc'], cur_tot_qty, ctx['tipo'] == 'Loc')
                    nq = safe_extract_qty(it['Det'])
                    if abs(it['Unit'] - nu) > 0.001:
                        st.session_state['carrito'][i].update({"Unit": nu, "Total": nu * nq}); st.rerun()
        except: pass

        sub = sum(i['Total'] for i in st.session_state['carrito']); eva = sum(i['Total'] for i in st.session_state['carrito'] if i['Ítem']=='Evaluación')
        col_L, col_R = st.columns([3,1])
        with col_R:
            fee = st.checkbox("Fee Admin 10%", value=False); vfee = eva*0.1 if fee else 0
            bnk = st.number_input("Bank Fee", value=0.0)
            tipo_d = st.selectbox("Descuento", ["Monto Fijo", "Simular Volumen"])
            dsc = 0.0
            if tipo_d == "Simular Volumen":
                v_sim = st.number_input("Simular Qty", 1, 10000, 1000)
                tot_sim = sum(calc_xls(ctx['dp'], i['Desc'], v_sim, ctx['tipo'] == 'Loc') * safe_extract_qty(i['Det']) for i in st.session_state['carrito'] if i['Ítem'] == 'Evaluación')
                dsc = max(0, eva - tot_sim); st.caption(f"Ahorro: {dsc:,.2f}")
            else: dsc = st.number_input("Monto Descuento")
            
            tn, tv = get_impuestos(ps, sub, eva); fin = sub + vfee + tv + bnk - dsc
            st.metric("TOTAL COTIZACIÓN", f"{ctx['mon']} {fin:,.2f}")
            
            if st.button("GUARDAR COTIZACIÓN FINAL", type="primary"):
                if es_nuevo and emp:
                    st.session_state['leads_db'].append({"id": int(time.time()), "Cliente": emp, "Pais": ps, "Origen": ori, "Etapa": "Propuesta", "Fecha": str(datetime.now().date()), "Responsable": st.session_state['current_user']})
                    github_push_json('url_leads', st.session_state['leads_db'], st.session_state.get('leads_sha'))
                
                nid = f"TP-{random.randint(1000,9999)}"
                row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':st.session_state['current_user'], 'items': st.session_state['carrito'], 'pdf_data': {'contacto':con, 'email':ema, 'tax_name':tn, 'tax_val':tv}}
                st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                st.session_state['carrito'] = []; st.success("Guardado"); time.sleep(1); st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento de Ventas")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No hay cotizaciones registradas."); return
    
    for i, r in df.sort_values('fecha', ascending=False).iterrows():
        # --- KEY UNICA PARA CADA WIDGET ---
        with st.expander(f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['estado']}"):
            c1, c2, c3 = st.columns(3)
            new_st = c1.selectbox("Estado", ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"], 
                                  index=["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"].index(r['estado']) if r['estado'] in ["Enviada", "Aprobada", "Rechazada", "Perdida", "Facturada"] else 0,
                                  key=f"st_seg_{r['id']}")
            hes = c2.checkbox("Requiere HES", value=r.get('hes', False), key=f"hes_seg_{r['id']}")
            if c3.button("Actualizar ", key=f"btn_seg_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_st
                st.session_state['cotizaciones'].at[i, 'hes'] = hes
                github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                if new_st == "Aprobada": st.balloons()
                st.success("OK"); st.rerun()

def modulo_finanzas():
    st.title("💰 Gestión Financiera")
    df = st.session_state['cotizaciones']
    t1, t2 = st.tabs(["📝 Pendientes", "💵 Historial"])
    with t1:
        pend = df[df['estado'] == 'Aprobada']
        for i, r in pend.iterrows():
            with st.container(border=True):
                st.write(f"**{r['empresa']}** | ID: {r['id']} | Total: {r['moneda']} {r['total']}")
                if r.get('hes'): st.error("🚨 Requiere HES para facturar.")
                # Lógica PDFs Chile (SpA/Ltda) restaurada
                if r.get('items') and r['pais'] == "Chile":
                    prod_i = [x for x in r['items'] if x['Ítem']=='Evaluación']
                    serv_i = [x for x in r['items'] if x['Ítem']=='Servicio']
                    if prod_i and serv_i:
                        st.info("Esta cotización requiere facturas separadas (SpA y Ltda).")
                
                c1, c2, c3 = st.columns(3)
                n_inv = c1.text_input("N° Factura", key=f"fin_n_{r['id']}")
                up_f = c2.file_uploader("PDF Factura", type=['pdf'], key=f"fin_up_{r['id']}")
                if c3.button("Facturar ", key=f"fin_btn_{r['id']}"):
                    if n_inv:
                        st.session_state['cotizaciones'].at[i, 'estado'] = 'Facturada'
                        st.session_state['cotizaciones'].at[i, 'factura'] = n_inv
                        if up_f: st.session_state['cotizaciones'].at[i, 'factura_file'] = base64.b64encode(up_f.read()).decode()
                        github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha'))
                        lluvia_dolares(); st.success("Facturado"); st.rerun()

def modulo_admin():
    st.title("👥 Administración y Metas")
    users = st.session_state['users_db']
    tab_u, tab_e = st.tabs(["Gestionar Usuarios", "Estructura Organizacional"])
    with tab_u:
        with st.form("new_u"):
            ne = st.text_input("Email"); nn = st.text_input("Nombre"); np = st.text_input("Pass", type="password")
            nr = st.selectbox("Rol", ["Comercial", "Finanzas", "Super Admin"])
            if st.form_submit_button("Crear Usuario"):
                users[ne] = {"name": nn, "role": nr, "password_hash": bcrypt.hashpw(np.encode(), bcrypt.gensalt()).decode(), "equipo": []}
                github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.success("Creado"); st.rerun()
    with tab_e:
        st.subheader("Configuración de Células")
        conf = users.get('_CONFIG_ORG', {})
        nc = st.text_input("Nueva Célula Principal")
        if st.button("Añadir Célula"):
            conf[nc] = {'meta': 0, 'subs': {}}; users['_CONFIG_ORG'] = conf
            github_push_json('url_usuarios', users, st.session_state.get('users_sha')); st.success("Añadida"); st.rerun()

# --- LOGIN Y NAVEGACIÓN ---
if not st.session_state['auth_status']:
    st.title("🔒 TalentPRO CRM Login")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        user_data = st.session_state['users_db'].get(u)
        if user_data:
            if bcrypt.checkpw(p.encode(), user_data['password_hash'].encode()):
                st.session_state['auth_status'] = True; st.session_state['current_user'] = u; st.rerun()
            else: st.error("Clave incorrecta")
        else: st.error("Usuario no existe")
else:
    with st.sidebar:
        menu = option_menu("Menú", ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"], 
                           icons=['bar-chart', 'check2', 'people', 'file-earmark', 'currency-dollar', 'shield-lock'], 
                           default_index=st.session_state['menu_idx'])
        st.session_state['menu_idx'] = ["Dashboards", "Seguimiento", "Prospectos y Clientes", "Cotizador", "Finanzas", "Usuarios"].index(menu)
        if st.button("Cerrar Sesión"): st.session_state.clear(); st.rerun()

    if menu == "Dashboards": modulo_dashboard()
    elif menu == "Seguimiento": modulo_seguimiento()
    elif menu == "Prospectos y Clientes": modulo_crm()
    elif menu == "Cotizador": modulo_cotizador()
    elif menu == "Finanzas": modulo_finanzas()
    elif menu == "Usuarios": modulo_admin()
