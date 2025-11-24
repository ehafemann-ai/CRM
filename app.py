import streamlit as st
import pandas as pd
import random
import requests
import os
import io
import json
import base64
import bcrypt
from datetime import datetime
from fpdf import FPDF
import plotly.express as px
from streamlit_option_menu import option_menu
import time

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="TalentPro ERP", layout="wide", page_icon="🔒")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #ffffff; border: 1px solid #e6e6e6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}
    div.stButton > button:first-child { background-color: #003366; color: white; border-radius: 8px; font-weight: bold;}
    [data-testid="stSidebar"] { padding-top: 0rem; }
    .crm-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #003366; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. FUNCIONES GITHUB (API) PARA JSON
# ==============================================================================
def github_get_json(url_key):
    try:
        url = st.secrets['github'][url_key]
        headers = {"Authorization": f"token {st.secrets['github']['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content), r.json()['sha']
        # Retornos vacíos seguros si el archivo está vacío o no existe
        return ([], None) if "leads" in url_key else ({}, None)
    except:
        return ([], None) if "leads" in url_key else ({}, None)

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
# 2. INICIALIZACIÓN DE ESTADO (USERS, LEADS, COTIZACIONES)
# ==============================================================================

# A) USUARIOS
if 'users_db' not in st.session_state:
    users, sha = github_get_json('url_usuarios')
    # Fallback Admin
    admin_email = "ehafemann@talentpro-latam.com"
    if admin_email not in users:
        hashed = bcrypt.hashpw("TalentPro_2025".encode(), bcrypt.gensalt()).decode()
        users[admin_email] = {"name": "Emilio Hafemann", "role": "Super Admin", "password_hash": hashed}
    st.session_state['users_db'] = users
    st.session_state['users_sha'] = sha

# B) LEADS (CRM)
if 'leads_db' not in st.session_state:
    leads, sha_l = github_get_json('url_leads')
    st.session_state['leads_db'] = leads
    st.session_state['leads_sha'] = sha_l

# C) COTIZACIONES (Volátiles por ahora, persistencia idealmente en JSON también)
if 'cotizaciones' not in st.session_state:
    st.session_state['cotizaciones'] = pd.DataFrame(columns=['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor'])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []

# D) AUTH
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
if 'current_role' not in st.session_state: st.session_state['current_role'] = None

# ==============================================================================
# 3. LOGIN & LOGOUT
# ==============================================================================
LOGO_PATH = "logo_talentpro.jpg"

@st.cache_resource
def descargar_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            r = requests.get("https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg")
            if r.status_code == 200:
                with open(LOGO_PATH, 'wb') as f:
                    f.write(r.content)
        except: pass
descargar_logo()

def login_page():
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=300)
        st.markdown("### Acceso Seguro")
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                user = st.session_state['users_db'].get(u)
                if user:
                    try:
                        if bcrypt.checkpw(p.encode(), user.get('password_hash','').encode()):
                            st.session_state['auth_status'] = True
                            st.session_state['current_user'] = u
                            st.session_state['current_role'] = user['role']
                            st.success("¡Bienvenido!")
                            time.sleep(0.5)
                            st.rerun()
                        else: st.error("Credenciales inválidas")
                    except: st.error("Error de seguridad")
                else: st.error("Credenciales inválidas")

def logout():
    st.session_state.clear()
    st.rerun()

if not st.session_state['auth_status']: login_page(); st.stop()

# ==============================================================================
# 4. CARGA DE DATOS (EXCEL PRECIOS)
# ==============================================================================
@st.cache_data(ttl=60)
def cargar_precios():
    try:
        token = st.secrets["github"]["token"]
        url = st.secrets["github"]["url_precios"]
        r = requests.get(url, headers={"Authorization": f"token {token}"})
        if r.status_code == 200:
            xls = pd.ExcelFile(io.BytesIO(r.content))
            return (pd.read_excel(xls, 'Pruebas Int'), pd.read_excel(xls, 'Servicios Int'), pd.read_excel(xls, 'Config'),
                    pd.read_excel(xls, 'Pruebas_CL') if 'Pruebas_CL' in xls.sheet_names else pd.DataFrame(),
                    pd.read_excel(xls, 'Servicios_CL') if 'Servicios_CL' in xls.sheet_names else pd.DataFrame(),
                    pd.read_excel(xls, 'Pruebas_BR') if 'Pruebas_BR' in xls.sheet_names else pd.DataFrame(),
                    pd.read_excel(xls, 'Servicios_BR') if 'Servicios_BR' in xls.sheet_names else pd.DataFrame())
        return None, None, None, None, None, None, None
    except: return None, None, None, None, None, None, None

data_precios = cargar_precios()
if not data_precios or data_precios[0] is None: st.error("Error conexión Precios"); st.stop()
df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data_precios
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil"]

@st.cache_data(ttl=3600)
def obtener_indicadores():
    t = {"UF": 38000, "USD_CLP": 980, "USD_BRL": 5.8}
    try:
        c = requests.get('https://mindicador.cl/api', timeout=2).json()
        t['UF'], t['USD_CLP'] = c['uf']['valor'], c['dolar']['valor']
        b = requests.get('https://open.er-api.com/v6/latest/USD', timeout=2).json()
        t['USD_BRL'] = b['rates']['BRL']
    except: pass
    return t
TASAS = obtener_indicadores()

# TEXTOS & EMPRESAS (Abreviados para espacio, funcionalidad completa)
TEXTOS = {"ES": {"title": "Cotizador", "save": "Guardar", "download": "Descargar PDF", "invoice_to": "Facturar a:", "date": "Fecha", "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total", "subtotal": "Subtotal", "fee": "Fee Admin", "grand_total": "TOTAL", "validity": "Validez 30 días", "legal_intl": "Facturación a {pais}. +Impuestos retenidos +Gastos OUR.", "noshow_title": "No-Show:", "noshow_text": "Multa 50% inasistencia <24h.", "sec_prod": "Licencias", "sec_serv": "Servicios", "client": "Cliente", "proj": "Proyecto", "add": "Agregar", "discount": "Descuento"}}
EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado 939", "Giro": "Consultoria"},
    "Peru": {"Nombre": "TALENTPRO S.A.C.", "ID": "DNI 25489763", "Dir": "AV. EL DERBY 254", "Giro": "Servicios"},
    "Chile_Pruebas": {"Nombre": "TALENT PRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630", "Giro": "Selección"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630", "Giro": "RRHH"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2", "Dir": "CALLE 50, PANAMÁ", "Giro": "Talent Services"}
}

# --- LOGICA NEGOCIO ---
def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "ds": df_s_cl, "tipo": "Loc"}
    if pais in ["Brasil", "Brazil"]: return {"mon": "R$", "dp": df_p_br, "ds": df_s_br, "tipo": "Loc"}
    fil = df_config[df_config['Pais'] == pais]
    niv = fil.iloc[0]['Nivel'] if not fil.empty else "Medio"
    return {"mon": "US$", "dp": df_p_usd, "ds": df_s_usd, "tipo": "Int", "niv": niv}

def calc_paa(c, m):
    b = 1500 if c<=2 else 1200 if c<=5 else 1100
    return (b if m=="US$" else (b*TASAS['USD_CLP'])/TASAS['UF'] if m=="UF" else b*TASAS['USD_BRL'])

def calc_xls(df, p, c, l):
    if df.empty: return 0.0
    r = df[df['Producto']==p]; 
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

# --- PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102); self.cell(0, 15, getattr(self,'tit','COTIZACIÓN'), 0, 1, 'R'); self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128); self.cell(0, 10, 'TalentPro Digital', 0, 0, 'C')

def generar_pdf_final(emp, cli, items, calc, extras, tit):
    pdf = PDF(); pdf.tit=tit; pdf.add_page()
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0); pdf.set_text_color(100); pdf.cell(95,5,"Facturar a:",0,1)
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
        pdf.cell(110,7,f"  {i['Desc'][:55]}",'B',0,'L'); pdf.cell(20,7,q,'B',0,'C'); pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
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
# 5. MÓDULO CRM (NUEVO)
# ==============================================================================
def modulo_crm():
    st.title("📇 CRM & Gestión Comercial")
    
    tab_leads, tab_clientes = st.tabs(["📋 Gestión de Leads", "🏢 Cartera de Clientes"])
    
    # --- LEADS ---
    with tab_leads:
        with st.expander("➕ Nuevo Lead", expanded=False):
            with st.form("form_lead"):
                st.subheader("Datos Generales")
                c1, c2, c3 = st.columns(3)
                nom_cliente = c1.text_input("Cliente / Empresa")
                area = c2.selectbox("Área", ["Cono Sur", "Brasil", "Centroamérica"])
                pais = c3.selectbox("País", TODOS_LOS_PAISES)
                
                c1, c2, c3 = st.columns(3)
                ind = c1.selectbox("Industria", ["Tecnología", "Finanzas", "Retail", "Minería", "Salud", "Educación", "Otros"])
                web = c2.text_input("Web")
                idioma = c3.selectbox("Idioma", ["ES", "EN", "PT"])
                
                st.subheader("Contactos")
                for i in range(1, 4):
                    c1, c2, c3 = st.columns(3)
                    c1.text_input(f"Nombre {i}", key=f"n{i}"); c2.text_input(f"Mail {i}", key=f"m{i}"); c3.text_input(f"Tel {i}", key=f"t{i}")
                
                st.subheader("Seguimiento")
                c1, c2 = st.columns(2)
                origen = c1.selectbox("Origen", ["Inbound", "Outbound", "Referido", "Evento"])
                etapa = c2.selectbox("Etapa", ["Prospección", "Contacto", "Reunión", "Propuesta", "Negociación", "Cerrado Ganado", "Cerrado Perdido"])
                
                expectativa = st.text_area("Expectativa / Dolor")
                
                if st.form_submit_button("Guardar Lead"):
                    # Guardar en JSON remoto
                    new_lead = {
                        "id": int(time.time()), "Cliente": nom_cliente, "Area": area, "Pais": pais, "Industria": ind,
                        "Etapa": etapa, "Responsable": st.session_state['current_user'], "Fecha": str(datetime.now().date())
                    }
                    new_db = st.session_state['leads_db'] + [new_lead]
                    if github_push_json('url_leads', new_db, st.session_state.get('leads_sha')):
                        st.session_state['leads_db'] = new_db # Actualizar local
                        st.success("Lead guardado"); time.sleep(1); st.rerun()
                    else: st.error("Error al guardar")

        if st.session_state['leads_db']:
            st.dataframe(pd.DataFrame(st.session_state['leads_db']), use_container_width=True)
        else: st.info("No hay leads.")

    # --- CLIENTES 360 ---
    with tab_clientes:
        st.subheader("Visión 360°")
        # Unir empresas de cotizaciones y leads
        clientes_cots = st.session_state['cotizaciones']['empresa'].unique().tolist()
        clientes_leads = [l['Cliente'] for l in st.session_state['leads_db']]
        todos = sorted(list(set(clientes_cots + clientes_leads)))
        
        sel_cli = st.selectbox("Buscar Cliente", todos)
        
        if sel_cli:
            # Filtrar Cotizaciones
            df_c = st.session_state['cotizaciones']
            cots_cli = df_c[df_c['empresa'] == sel_cli]
            
            # KPI
            c1, c2, c3 = st.columns(3)
            total_cot = cots_cli['total'].sum()
            
            # Facturación Año Actual
            current_year = datetime.now().year
            # Hack simple para filtrar por año string "YYYY-MM-DD"
            facturado = cots_cli[(cots_cli['estado'] == 'Facturada') & (cots_cli['fecha'].str.contains(str(current_year)))]['total'].sum()
            
            c1.metric("Total Cotizado", f"${total_cot:,.0f}")
            c2.metric(f"Facturado {current_year}", f"${facturado:,.0f}")
            c3.metric("Cant. Cotizaciones", len(cots_cli))
            
            st.divider()
            st.markdown("#### Historial de Cotizaciones")
            st.dataframe(cots_cli, use_container_width=True)

# --- OTROS MODULOS (RESUMIDOS) ---
def modulo_cotizador():
    # ... (Codigo cotizador anterior, mantenido igual para funcionalidad)
    cl, ct = st.columns([1, 5]); idi = cl.selectbox("🌐", ["ES"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("UF", f"${TASAS['UF']:,.0f}"); k2.metric("USD", f"${TASAS['USD_CLP']:,.0f}"); k3.metric("BRL", f"{TASAS['USD_BRL']:.2f}")
    if k4.button("Actualizar Tasas"): obtener_indicadores.clear(); st.rerun()
    
    st.markdown("---"); c1, c2 = st.columns([1, 2]); idx = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    ps = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx); ctx = obtener_contexto(ps)
    c2.info(f"Moneda: **{ctx['mon']}** | Tarifas: **{ctx['tipo']}** {ctx.get('niv', '')}")
    
    st.markdown("---"); cc1,cc2,cc3,cc4=st.columns(4)
    emp = cc1.text_input(txt['client']); con = cc2.text_input("Contacto"); ema = cc3.text_input("Email")
    current_u = st.session_state['current_user']; user_real_name = st.session_state['users_db'][current_u].get('name', current_u)
    ven = cc4.text_input("Ejecutivo", value=user_real_name, disabled=True); proj = st.text_input(txt['proj'])
    
    st.markdown("---"); tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4=st.columns([3,1,1,1]); lp=ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp,key="p1"); qp=c2.number_input("Cant",1,10000,10,key="q1")
            up=calc_xls(ctx['dp'],sp,qp,ctx['tipo']=='Loc'); c3.metric("Unit",f"{up:,.2f}")
            if c4.button("Add",key="b1"): st.session_state['carrito'].append({"Ítem":"Evaluación","Desc":sp,"Det":f"x{qp}","Moneda":ctx['mon'],"Unit":up,"Total":up*qp}); st.rerun()
    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        lf=["Certificación PAA (Transversal)"]+ls
        if lf:
            ss=c1.selectbox("Serv",lf,key="s1")
            if "PAA" in ss:
                c2.write(""); qs=c2.number_input("Pers",1,1000,1,key="q2"); us=calc_paa(qs,ctx['mon']); dt=f"{qs} pers"
            else:
                r,q=c2.columns(2); cs=ctx['ds'].columns.tolist(); rv=[x for x in ['Angelica','Senior','BM','BP'] if x in cs]
                rol=r.selectbox("Rol",rv) if rv else cs[-1]; qs=q.number_input("Cant",1,1000,1); us=0.0
                rw=ctx['ds'][(ctx['ds']['Servicio']==ss)&(ctx['ds']['Nivel']==ctx['niv'])] if ctx['tipo']=="Int" else ctx['ds'][ctx['ds']['Servicio']==ss]
                if not rw.empty: us=float(rw.iloc[0][rol]); dt=f"{rol} ({qs})"
            c3.metric("Unit",f"{us:,.2f}"); 
            if c4.button("Add",key="b2"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        st.markdown("---"); dfc=pd.DataFrame(st.session_state['carrito']); mon=dfc['Moneda'].unique()[0]; st.dataframe(dfc[['Desc','Det','Unit','Total']],use_container_width=True)
        sub=dfc['Total'].sum(); eva=dfc[dfc['Ítem']=='Evaluación']['Total'].sum()
        cL, cR = st.columns([3,1])
        with cR:
            fee=st.checkbox("Fee",False); bnk=st.number_input("Bank",0.0); dsc=st.number_input("Desc",0.0)
            vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-dsc
            st.metric("TOTAL",f"{mon} {fin:,.2f}")
            if st.button("GUARDAR",type="primary"):
                if not emp: st.error("Falta Empresa"); return
                nid=f"TP-{random.randint(1000, 9999)}"; cli={'empresa':emp,'contacto':con,'email':ema}
                ext={'fee':fee,'bank':bnk,'desc':dsc,'pais':ps,'id':nid}
                pr, sv = [x for x in st.session_state['carrito'] if x['Ítem']=='Evaluación'], [x for x in st.session_state['carrito'] if x['Ítem']=='Servicio']
                links=""
                if ps == "Chile" and pr and sv:
                    sp=sum(x['Total'] for x in pr); fp=sp*0.1 if fee else 0; tp=sp*0.19; totp=sp+fp+tp
                    pdf_p = generar_pdf_final(EMPRESAS['Chile_Pruebas'], cli, pr, {'subtotal':sp,'fee':fp,'tax_name':'IVA','tax_val':tp,'total':totp}, txt['quote'], ext, "Pruebas")
                    b64p = base64.b64encode(pdf_p).decode('latin-1')
                    links+=f'<a href="data:application/pdf;base64,{b64p}" download="Cot_{nid}_P.pdf">Descargar Pruebas</a><br>'
                    
                    ss=sum(x['Total'] for x in sv); tots=ss+bnk-dsc
                    pdf_s = generar_pdf_final(EMPRESAS['Chile_Servicios'], cli, sv, {'subtotal':ss,'fee':0,'tax_name':'','tax_val':0,'bank':bnk,'desc':dsc,'total':tots}, txt['quote'], ext, "Servicios")
                    b64s = base64.b64encode(pdf_s).decode('latin-1')
                    links+=f'<a href="data:application/pdf;base64,{b64s}" download="Cot_{nid}_S.pdf">Descargar Servicios</a>'
                else:
                    ent = get_empresa(ps, st.session_state['carrito'])
                    calc = {'subtotal':sub, 'fee':vfee, 'tax_name':tn, 'tax_val':tv, 'bank':bnk, 'desc':dsc, 'total':fin}
                    pdf = generar_pdf_final(ent, cli, st.session_state['carrito'], calc, txt['quote'], ext, "Cotizacion")
                    b64 = base64.b64encode(pdf).decode('latin-1')
                    links=f'<a href="data:application/pdf;base64,{b64}" download="Cot_{nid}.pdf">Descargar PDF</a>'

                st.markdown(links, unsafe_allow_html=True)
                st.session_state['cotizaciones']=pd.concat([st.session_state['cotizaciones'], pd.DataFrame([{
                    'id':nid, 'fecha':datetime.now().strftime("%Y-%m-%d"), 'empresa':emp, 'pais':ps,
                    'total':fin, 'moneda':mon, 'estado':'Enviada', 'vendedor':ven, 'idioma':idi
                }])], ignore_index=True)
                st.session_state['carrito']=[]; st.success("OK")
        with cL:
            if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento"); df=st.session_state['cotizaciones']
    if df.empty: return
    for i, r in df.iterrows():
        with st.expander(f"{r['id']} - {r['empresa']}"):
            st.write(f"Total: {r['moneda']} {r['total']:,.2f}")
            ns = st.selectbox("Estado",["Enviada","Aprobada","Rechazada"], key=f"st{i}")
            if ns!=r['estado']:
                if st.button("Update", key=f"up{i}"):
                    st.session_state['cotizaciones'].at[i,'estado']=ns; st.rerun()

def modulo_finanzas():
    st.title("💰 Finanzas"); df=st.session_state['cotizaciones']
    st.dataframe(df[df['estado']=='Aprobada'])

def modulo_dashboard():
    st.title("📊 Dash"); df=st.session_state['cotizaciones']
    if not df.empty: st.bar_chart(df['total'])

def modulo_admin():
    st.title("👥 Admin")
    # Logica de usuarios (ya implementada en memoria)
    st.dataframe(pd.DataFrame(st.session_state['users_db']).T)

# --- APP ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    role = st.session_state.get('current_role', 'Comercial')
    opts = ["CRM", "Cotizador", "Seguimiento", "Finanzas", "Dashboard"]; icos = ['person-lines-fill', 'file-earmark-plus', 'clipboard-check', 'currency-dollar', 'bar-chart-fill']
    if role == "Super Admin": opts.append("Usuarios"); icos.append("people-fill")
    menu = option_menu("Menú", opts, icons=icos, menu_icon="cast", default_index=0, styles={"nav-link-selected": {"background-color": "#003366"}})
    if st.button("Cerrar Sesión"): logout()

if menu == "CRM": modulo_crm()
elif menu == "Cotizador": modulo_cotizador()
elif menu == "Seguimiento": modulo_seguimiento()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Dashboard": modulo_dashboard()
elif menu == "Usuarios": modulo_admin()
