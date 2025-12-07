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

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="TalentPro ERP", layout="wide", page_icon="🔒")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}
    div.stButton > button:first-child { background-color: #003366; color: white; border-radius: 8px; font-weight: bold;}
    [data-testid="stSidebar"] { padding-top: 0rem; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. FUNCIONES GITHUB (API)
# ==============================================================================
def github_get_json(url_key):
    try:
        url = st.secrets['github'][url_key]
        headers = {"Authorization": f"token {st.secrets['github']['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content), r.json()['sha']
        # Retornos seguros si no existe archivo
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

# ==============================================================================
# 2. INICIALIZACIÓN DE ESTADO
# ==============================================================================
if 'users_db' not in st.session_state:
    users, sha = github_get_json('url_usuarios')
    admin_email = st.secrets['auth']['admin_user']
    if not users or admin_email not in users:
        hashed = bcrypt.hashpw(st.secrets['auth']['admin_pass'].encode(), bcrypt.gensalt()).decode()
        users = {admin_email: {"name": "Super Admin", "role": "Super Admin", "password_hash": hashed}}
    st.session_state['users_db'] = users
    st.session_state['users_sha'] = sha

if 'leads_db' not in st.session_state:
    leads, sha_l = github_get_json('url_leads')
    st.session_state['leads_db'] = leads if isinstance(leads, list) else []
    st.session_state['leads_sha'] = sha_l

if 'cotizaciones' not in st.session_state:
    cots, sha_c = github_get_json('url_cotizaciones')
    st.session_state['cotizaciones_sha'] = sha_c
    cols = ['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor', 'oc', 'factura', 'pago']
    if cots and isinstance(cots, list):
        df = pd.DataFrame(cots)
        # Asegurar columnas nuevas en datos viejos
        for c in cols:
            if c not in df.columns: df[c] = ""
        st.session_state['cotizaciones'] = df
    else:
        st.session_state['cotizaciones'] = pd.DataFrame(columns=cols)

if 'carrito' not in st.session_state: st.session_state['carrito'] = []
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'current_user' not in st.session_state: st.session_state['current_user'] = None

# ==============================================================================
# 3. LOGIN & DATOS EXTERNOS
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
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                user = st.session_state['users_db'].get(u)
                if user and bcrypt.checkpw(p.encode(), user.get('password_hash','').encode()):
                    st.session_state['auth_status'] = True
                    st.session_state['current_user'] = u
                    st.session_state['current_role'] = user['role']
                    st.rerun()
                else: st.error("Acceso denegado")

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
    t = {"UF": 38000, "USD_CLP": 980, "USD_BRL": 5.8}
    try: t['UF'], t['USD_CLP'] = requests.get('https://mindicador.cl/api',timeout=2).json()['uf']['valor'], requests.get('https://mindicador.cl/api',timeout=2).json()['dolar']['valor']
    except: pass
    return t
TASAS = obtener_indicadores()

TEXTOS = {"ES": {"title": "Cotizador", "quote": "COTIZACIÓN", "legal_intl": "Facturación a {pais}. +Impuestos retenidos +Gastos OUR.", "noshow_text": "Multa 50% inasistencia <24h.", "sec_prod": "Licencias", "sec_serv": "Servicios", "client": "Cliente"}}
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
    if m == "UF": return (b*TASAS['USD_CLP'])/TASAS['UF']
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
    if pais=="Chile": 
        # Default para lógica simple, la lógica split va en el módulo
        return EMPRESAS["Chile_Pruebas"] if any(i['Ítem']=='Evaluación' for i in items) else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

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

def generar_pdf_final(emp, cli, items, calc, titulo, extras):
    pdf = PDF(); pdf.tit_doc=titulo; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0)
    pdf.set_text_color(100); pdf.cell(95,5,"Facturar a:",0,1)
    pdf.set_font("Arial",'',9); pdf.set_text_color(50); y=pdf.get_y()
    pdf.cell(95,5,emp['ID'],0,1); pdf.multi_cell(90,5,emp['Dir']); pdf.cell(95,5,emp['Giro'],0,1)
    pdf.set_xy(105,y); pdf.set_font("Arial",'B',10); pdf.set_text_color(0); pdf.cell(95,5,cli['empresa'],0,1)
    pdf.set_xy(105,pdf.get_y()); pdf.set_font("Arial",'',9); pdf.set_text_color(50)
    pdf.cell(95,5,cli['contacto'],0,1); pdf.set_xy(105,pdf.get_y()); pdf.cell(95,5,cli['email'],0,1)
    pdf.ln(5); pdf.set_xy(105,pdf.get_y()); pdf.set_text_color(0,51,102)
    pdf.cell(95,5,f"Fecha: {datetime.now().strftime('%d/%m/%Y')} | ID: {extras['id']}",0,1); pdf.ln(10)
    
    pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.set_font("Arial",'B',9)
    pdf.cell(110,8,"Descripción",0,0,'L',1); pdf.cell(20,8,"Cant",0,0,'C',1); pdf.cell(30,8,"Unit",0,0,'R',1); pdf.cell(30,8,"Total",0,1,'R',1)
    pdf.set_text_color(0); pdf.set_font("Arial",'',8); mon=items[0]['Moneda']
    for i in items:
        q=str(i['Det']).split('(')[0].replace('x','').strip()
        pdf.cell(110,7,f"  {i['Desc'][:60]}",'B',0,'L'); pdf.cell(20,7,q,'B',0,'C')
        pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(5)
    
    x=120
    def r(l,v,b=False):
        pdf.set_x(x); pdf.set_font("Arial",'B' if b else '',10); pdf.set_text_color(0 if not b else 255)
        if b: pdf.set_fill_color(0,51,102)
        pdf.cell(35,7,l,0,0,'R',b); pdf.cell(35,7,f"{mon} {v:,.2f} ",0,1,'R',b)
    
    r("Subtotal", calc['subtotal'])
    if calc['fee']>0: r("Fee Admin", calc['fee'])
    if calc['tax_val']>0: r(calc['tax_name'], calc['tax_val'])
    if extras.get('bank',0)>0: r("Bank Fee", extras['bank'])
    if extras.get('desc',0)>0: r("Descuento", -extras['desc'])
    pdf.ln(1); r("TOTAL", calc['total'], True); pdf.ln(10)
    pdf.set_font("Arial",'I',8); pdf.set_text_color(80)
    if emp['Nombre']==EMPRESAS['Latam']['Nombre']: pdf.multi_cell(0,4,TEXTOS['ES']['legal_intl'].format(pais=extras['pais']),0,'L'); pdf.ln(3)
    if any(any(tr in i['Desc'].lower() for tr in ['feedback','coaching','entrevista']) for i in items):
        pdf.set_font("Arial",'B',8); pdf.cell(0,4,"Política No-Show:",0,1); pdf.set_font("Arial",'',8); pdf.multi_cell(0,4,TEXTOS['ES']['noshow_text'],0,'L'); pdf.ln(3)
    pdf.set_text_color(100); pdf.cell(0,5,"Validez 30 días",0,1)
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 5. MÓDULOS APP
# ==============================================================================
def modulo_crm():
    st.title("📇 CRM & Gestión Comercial")
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
                web = c2.text_input("Web")
                idioma = c3.selectbox("Idioma", ["ES", "EN", "PT"])
                
                st.subheader("2. Contactos Clave")
                contacts_data = []
                for i in range(1, 4):
                    c1, c2, c3 = st.columns(3)
                    n = c1.text_input(f"Nombre {i}", key=f"n{i}")
                    m = c2.text_input(f"Mail {i}", key=f"m{i}")
                    t = c3.text_input(f"Tel {i}", key=f"t{i}")
                    if n: contacts_data.append(f"{n} ({m})")

                st.subheader("3. Seguimiento")
                c1, c2 = st.columns(2)
                origen = c1.selectbox("Origen", ["Inbound", "Outbound", "Referido", "Evento"])
                etapa = c2.selectbox("Etapa Inicial", ["Prospección", "Contacto", "Reunión", "Propuesta"])
                expectativa = st.text_area("Expectativa / Dolor Principal")
                
                if st.form_submit_button("Guardar Lead"):
                    str_contactos = ", ".join(contacts_data)
                    new_lead = {
                        "id": int(time.time()), "Cliente": nom_cliente, "Area": area, "Pais": pais, "Industria": ind,
                        "Web": web, "Contactos": str_contactos, "Origen": origen, "Etapa": etapa,
                        "Expectativa": expectativa, "Responsable": st.session_state['current_user'], 
                        "Fecha": str(datetime.now().date())
                    }
                    new_db = st.session_state['leads_db'] + [new_lead]
                    if github_push_json('url_leads', new_db, st.session_state.get('leads_sha')):
                        st.session_state['leads_db'] = new_db
                        st.success("Lead guardado correctamente.")
                        time.sleep(1); st.rerun()
                    else: st.error("Error al guardar en GitHub")

        if st.session_state['leads_db']:
            st.dataframe(pd.DataFrame(st.session_state['leads_db']), use_container_width=True)
        else: st.info("No hay leads registrados.")

    with tab2:
        l_leads = [l['Cliente'] for l in st.session_state['leads_db']]
        l_cots = st.session_state['cotizaciones']['empresa'].unique().tolist()
        todos = sorted(list(set(l_leads + l_cots)))
        sel = st.selectbox("Ver Cliente 360", [""] + todos)
        
        if sel:
            df = st.session_state['cotizaciones']; dfc = df[df['empresa']==sel]
            tot = dfc['total'].sum() if not dfc.empty else 0
            # Recuperamos KPI de facturación para este cliente específico
            fac_cli = dfc[dfc['estado']=='Facturada']['total'].sum() if not dfc.empty else 0
            
            lead_info = next((l for l in st.session_state['leads_db'] if l['Cliente'] == sel), None)
            
            st.markdown(f"### 🏢 {sel}")
            if lead_info:
                c1,c2,c3 = st.columns(3)
                c1.info(f"**Industria:** {lead_info.get('Industria','')}")
                c2.info(f"**Web:** {lead_info.get('Web','')}")
                c3.info(f"**Origen:** {lead_info.get('Origen','')}")
                st.write(f"**Contactos:** {lead_info.get('Contactos','')}")
                st.write(f"**Dolor:** {lead_info.get('Expectativa','')}")
                st.divider()

            c1,c2,c3 = st.columns(3)
            c1.metric("Total Cotizado", f"${tot:,.0f}")
            c2.metric("Total Facturado", f"${fac_cli:,.0f}")
            c3.metric("# Cotizaciones", len(dfc))
            
            st.dataframe(dfc[['fecha','id','pais','total','estado','factura','pago']], use_container_width=True)

def modulo_cotizador():
    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("UF", f"${TASAS['UF']:,.0f}"); c2.metric("USD", f"${TASAS['USD_CLP']:,.0f}"); c3.metric("BRL", f"{TASAS['USD_BRL']:.2f}")
    if c4.button("Actualizar Tasas"): obtener_indicadores.clear(); st.rerun()
    
    st.markdown("---"); c1, c2 = st.columns([1, 2])
    idx = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    ps = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx); ctx = obtener_contexto(ps)
    c2.info(f"Moneda: **{ctx['mon']}** | Tarifas: **{ctx['tipo']}** {ctx.get('niv', '')}")
    
    st.markdown("---"); cc1,cc2,cc3,cc4=st.columns(4)
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
        st.markdown("---"); dfc=pd.DataFrame(st.session_state['carrito']); st.dataframe(dfc, use_container_width=True)
        sub=dfc['Total'].sum(); eva=dfc[dfc['Ítem']=='Evaluación']['Total'].sum()
        cL, cR = st.columns([3,1])
        with cR:
            fee=st.checkbox("Fee 10%",False); bnk=st.number_input("Bank",0.0); dsc=st.number_input("Desc",0.0)
            vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-dsc
            st.metric("TOTAL",f"{ctx['mon']} {fin:,.2f}")
            
            if st.button("GUARDAR", type="primary"):
                if not emp: st.error("Falta Empresa"); return
                nid=f"TP-{random.randint(1000,9999)}"; cli={'empresa':emp,'contacto':con,'email':ema}
                ext={'fee':vfee,'bank':bnk,'desc':dsc,'pais':ps,'id':nid}
                
                # --- LOGICA SPLIT CHILE ---
                prod_items = [x for x in st.session_state['carrito'] if x['Ítem']=='Evaluación']
                serv_items = [x for x in st.session_state['carrito'] if x['Ítem']=='Servicio']
                links_html = ""
                
                # Caso: Chile con mezcla -> Dos cotizaciones
                if ps == "Chile" and prod_items and serv_items:
                    # 1. Productos (SpA)
                    sub_p = sum(x['Total'] for x in prod_items)
                    fee_p = sub_p*0.10 if fee else 0
                    tax_p = sub_p*0.19
                    tot_p = sub_p + fee_p + tax_p
                    calc_p = {'subtotal':sub_p, 'fee':fee_p, 'tax_name':"IVA (19%)", 'tax_val':tax_p, 'total':tot_p}
                    pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli, prod_items, calc_p, txt['quote'], ext)
                    b64_p = base64.b64encode(pdf_p).decode('latin-1')
                    links_html += f'<a href="data:application/pdf;base64,{b64_p}" download="Cot_{nid}_Productos.pdf">📄 Descargar Cotización (Productos - SpA)</a><br><br>'

                    # 2. Servicios (Ltda)
                    sub_s = sum(x['Total'] for x in serv_items)
                    tot_s = sub_s + bnk - dsc
                    calc_s = {'subtotal':sub_s, 'fee':0, 'tax_name':"", 'tax_val':0, 'total':tot_s}
                    pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli, serv_items, calc_s, txt['quote'], ext)
                    b64_s = base64.b64encode(pdf_s).decode('latin-1')
                    links_html += f'<a href="data:application/pdf;base64,{b64_s}" download="Cot_{nid}_Servicios.pdf">📄 Descargar Cotización (Servicios - Ltda)</a>'
                    st.success("✅ Generadas 2 cotizaciones separadas (SpA y Servicios)")
                
                # Caso Normal
                else:
                    ent = get_empresa(ps, st.session_state['carrito'])
                    calc = {'subtotal':sub, 'fee':vfee, 'tax_name':tn, 'tax_val':tv, 'total':fin}
                    pdf = generar_pdf_final(ent, cli, st.session_state['carrito'], calc, txt['quote'], ext)
                    b64 = base64.b64encode(pdf).decode('latin-1')
                    links_html = f'<a href="data:application/pdf;base64,{b64}" download="Cot_{nid}.pdf">📄 Descargar PDF</a>'
                    st.success("✅ Cotización generada")

                st.markdown(links_html, unsafe_allow_html=True)
                
                # Guardar en DB
                row = {'id':nid, 'fecha':str(datetime.now().date()), 'empresa':emp, 'pais':ps, 'total':fin, 'moneda':ctx['mon'], 'estado':'Enviada', 'vendedor':ven, 'oc':'', 'factura':'', 'pago':'Pendiente'}
                st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([row])], ignore_index=True)
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    st.info("Guardado en Base de Datos"); st.session_state['carrito']=[]; time.sleep(2)
                else: st.warning("Error al sincronizar con GitHub")
        with cL: 
            if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento de Cotizaciones")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("Sin datos."); return
    df = df.sort_values('fecha', ascending=False)
    st.markdown("### 🔍 Gestión Comercial & Facturación")
    for i, r in df.iterrows():
        label = f"{r['fecha']} | {r['id']} | {r['empresa']} | {r['moneda']} {r['total']:,.0f}"
        if r['estado'] == 'Facturada': label += " ✅"
        elif r['estado'] == 'Enviada': label += " ⏳"
        
        with st.expander(label):
            col_status, col_data, col_pay = st.columns([1, 1, 1])
            with col_status:
                st.caption("Flujo de Venta")
                est_options = ["Enviada", "Aprobada", "Facturada", "Rechazada", "Perdida"]
                idx = est_options.index(r['estado']) if r['estado'] in est_options else 0
                new_status = st.selectbox("Estado", est_options, key=f"st_{r['id']}")

            with col_data:
                st.caption("Datos Administrativos")
                new_oc = st.text_input("Orden de Compra (OC)", value=r.get('oc', ''), key=f"oc_{r['id']}")
                new_fact = st.text_input("N° Factura", value=r.get('factura', ''), key=f"ft_{r['id']}", disabled=(new_status in ["Enviada","Rechazada","Perdida"]))
            
            with col_pay:
                st.caption("Cobranza")
                pay_options = ["Pendiente", "Pagada", "Vencida"]
                curr_pay = r.get('pago', 'Pendiente')
                new_pay = st.selectbox("Estado Pago", pay_options, key=f"py_{r['id']}", disabled=(not new_fact))

            if st.button("💾 Actualizar", key=f"btn_{r['id']}"):
                st.session_state['cotizaciones'].at[i, 'estado'] = new_status
                st.session_state['cotizaciones'].at[i, 'oc'] = new_oc
                st.session_state['cotizaciones'].at[i, 'factura'] = new_fact
                st.session_state['cotizaciones'].at[i, 'pago'] = new_pay
                if github_push_json('url_cotizaciones', st.session_state['cotizaciones'].to_dict(orient='records'), st.session_state.get('cotizaciones_sha')):
                    st.success("Actualizado"); time.sleep(1); st.rerun()

# ==============================================================================
# MÓDULO DASHBOARD (CON SANITIZACIÓN DE DATOS)
# ==============================================================================
def modulo_dashboard():
    st.title("📊 Dashboards & Analytics")
    
    # Pre-procesamiento para evitar errores si faltan columnas en datos viejos
    if st.session_state['leads_db']:
        df_leads = pd.DataFrame(st.session_state['leads_db'])
        cols_leads_req = ['Origen', 'Etapa', 'Industria']
        for col in cols_leads_req:
            if col not in df_leads.columns: df_leads[col] = "Sin Dato"
        df_leads = df_leads.fillna("Sin Dato")
    else: df_leads = pd.DataFrame()

    df_cots = st.session_state['cotizaciones']
    
    tab_gen, tab_lead, tab_sale, tab_bill = st.tabs(["📊 General", "📇 Leads (Funnel)", "📈 Cierre Ventas", "💵 Facturación"])
    
    # 1. GENERAL
    with tab_gen:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Leads", len(df_leads))
        c2.metric("Total Cotizado", f"${df_cots['total'].sum():,.0f}" if not df_cots.empty else "$0")
        
        total_ops = len(df_cots)
        won_ops = len(df_cots[df_cots['estado'].isin(['Aprobada','Facturada'])])
        win_rate = (won_ops/total_ops*100) if total_ops > 0 else 0
        c3.metric("Tasa de Cierre", f"{win_rate:.1f}%")
        
        facturado = df_cots[df_cots['estado']=='Facturada']['total'].sum() if not df_cots.empty else 0
        c4.metric("Total Facturado", f"${facturado:,.0f}")
        
        st.divider()
        if not df_cots.empty:
            fig = px.pie(df_cots, names='estado', title="Distribución Estado Cotizaciones")
            st.plotly_chart(fig, use_container_width=True)

    # 2. LEADS
    with tab_lead:
        if not df_leads.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Funnel por Etapa")
                funnel_data = df_leads['Etapa'].value_counts().reset_index()
                funnel_data.columns = ['Etapa', 'Cantidad']
                fig_funnel = px.funnel(funnel_data, x='Cantidad', y='Etapa', title="Embudo de Ventas")
                st.plotly_chart(fig_funnel, use_container_width=True)
            with c2:
                st.subheader("Leads por Origen")
                fig_source = px.bar(df_leads, x='Origen', title="Fuentes de Leads", color='Origen')
                st.plotly_chart(fig_source, use_container_width=True)
            st.subheader("Leads por Industria")
            st.bar_chart(df_leads['Industria'].value_counts())
        else: st.info("No hay datos de leads.")

    # 3. VENTAS (CIERRE)
    with tab_sale:
        if not df_cots.empty:
            df_cots['fecha_dt'] = pd.to_datetime(df_cots['fecha'])
            df_cots['Mes'] = df_cots['fecha_dt'].dt.strftime('%Y-%m')
            
            df_sales = df_cots[df_cots['estado'].isin(['Aprobada','Facturada'])]
            
            if not df_sales.empty:
                st.subheader("Evolución de Ventas Cerradas (Mensual)")
                sales_time = df_sales.groupby('Mes')['total'].sum().reset_index()
                fig_line = px.line(sales_time, x='Mes', y='total', markers=True, title="Ventas Acumuladas ($)")
                st.plotly_chart(fig_line, use_container_width=True)
                
                st.subheader("Performance por Vendedor")
                fig_bar = px.bar(df_sales, x='vendedor', y='total', color='pais', title="Ventas por Ejecutivo")
                st.plotly_chart(fig_bar, use_container_width=True)
            else: st.info("Aún no hay ventas cerradas.")
            
            st.divider()
            st.subheader("Actividad de Cotización Total")
            act_time = df_cots.groupby('Mes')['total'].count().reset_index()
            fig_act = px.bar(act_time, x='Mes', y='total', title="Cantidad de Cotizaciones Enviadas")
            st.plotly_chart(fig_act, use_container_width=True)
        else: st.info("Sin datos de cotizaciones.")

    # 4. FACTURACIÓN
    with tab_bill:
        df_inv = df_cots[df_cots['estado']=='Facturada']
        if not df_inv.empty:
            c1, c2, c3 = st.columns(3)
            tot_inv = df_inv['total'].sum()
            tot_paid = df_inv[df_inv['pago']=='Pagada']['total'].sum()
            tot_pend = tot_inv - tot_paid
            
            c1.metric("Total Facturado", f"${tot_inv:,.0f}")
            c2.metric("Cobrado (Pagado)", f"${tot_paid:,.0f}", delta=f"{tot_paid/tot_inv*100:.1f}%")
            c3.metric("Por Cobrar (Pendiente)", f"${tot_pend:,.0f}", delta_color="inverse")
            
            st.subheader("Estado de Pagos")
            fig_pay = px.pie(df_inv, names='pago', title="Status de Cobranza", hole=0.4, 
                             color_discrete_map={'Pagada':'green', 'Pendiente':'orange', 'Vencida':'red'})
            st.plotly_chart(fig_pay, use_container_width=True)
        else: st.info("No hay facturas emitidas.")

def modulo_finanzas():
    st.title("💵 Gestión de Cobranza (Tabla)")
    df = st.session_state['cotizaciones']
    if not df.empty:
        df_inv = df[df['estado'] == 'Facturada'].copy()
        if not df_inv.empty:
            st.dataframe(df_inv[['fecha', 'factura', 'oc', 'empresa', 'total', 'moneda', 'pago']].sort_values('factura', ascending=False), use_container_width=True)
        else: st.info("No hay facturas.")
    else: st.info("Sin datos.")

def modulo_admin():
    st.title("Admin Users"); st.dataframe(pd.DataFrame(st.session_state['users_db']).T)

# --- MENU LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    role = st.session_state.get('current_role', 'Comercial')
    opts = ["CRM", "Cotizador", "Seguimiento", "Dashboards", "Finanzas"]; icos = ['person', 'file', 'check', 'bar-chart', 'currency-dollar']
    if role == "Super Admin": opts.append("Usuarios"); icos.append("people")
    menu = option_menu("Menú", opts, icons=icos, default_index=0)
    if st.button("Salir"): logout()

if menu == "CRM": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Seguimiento": modulo_seguimiento()
elif menu == "Dashboards": modulo_dashboard()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Usuarios": modulo_admin()
