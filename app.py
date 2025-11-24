import streamlit as st
import pandas as pd
import random
import requests
import os
from datetime import datetime
from fpdf import FPDF
import base64

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="TalentPro Global", layout="wide", page_icon="🌎")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; border-radius: 5px;}
    div.stButton > button:first-child { background-color: #003366; color: white; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. RECURSOS (LOGO)
# ==============================================================================
LOGO_URL = "https://bukwebapp-enterprise-chile.s3.amazonaws.com/talentpro/generals/logo_login/logo_login.jpg"
LOGO_PATH = "logo_talentpro.jpg"

@st.cache_resource
def descargar_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            r = requests.get(LOGO_URL)
            if r.status_code == 200:
                with open(LOGO_PATH, 'wb') as f: f.write(r.content)
        except: pass
descargar_logo()

# ==============================================================================
# 2. DATOS MAESTROS
# ==============================================================================
TEXTOS = {
    "ES": {
        "title": "Cotizador TalentPro", "client": "Información del Cliente",
        "add": "Agregar", "desc": "Descripción", "qty": "Cant.", "unit": "Unitario", "total": "Total",
        "subtotal": "Subtotal Neto", "fee": "Fee Admin (10%)", "grand_total": "TOTAL A PAGAR",
        "invoice_to": "Preparado para:", "quote": "COTIZACIÓN", "date": "Fecha", "validity": "Validez: 30 días",
        "save": "Generar Cotización", "download": "Descargar PDF",
        "sec_prod": "Evaluaciones", "sec_serv": "Servicios Profesionales"
    },
    "EN": {
        "title": "TalentPro Quote", "client": "Client Info",
        "add": "Add", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total",
        "subtotal": "Net Subtotal", "fee": "Admin Fee (10%)", "grand_total": "GRAND TOTAL",
        "invoice_to": "Prepared for:", "quote": "QUOTATION", "date": "Date", "validity": "Validity: 30 days",
        "save": "Generate Quote", "download": "Download PDF",
        "sec_prod": "Assessments", "sec_serv": "Professional Services"
    },
    "PT": {
        "title": "Cotação TalentPro", "client": "Dados Cliente",
        "add": "Adicionar", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total",
        "subtotal": "Subtotal Líquido", "fee": "Taxa Admin (10%)", "grand_total": "TOTAL A PAGAR",
        "invoice_to": "Preparado para:", "quote": "COTAÇÃO", "date": "Data", "validity": "Validade: 30 dias",
        "save": "Gerar Cotação", "download": "Baixar PDF",
        "sec_prod": "Avaliações", "sec_serv": "Serviços Profissionais"
    }
}

EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Consutoria Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939, Andar 8", "Giro": "Consultoria em gestão"},
    "Peru": {"Nombre": "TALENTPRO S.A.C.", "ID": "DNI 25489763", "Dir": "AVENIDA EL DERBY 254, SANTIAGO DE SURCO, LIMA", "Giro": "Servicios de apoyo"},
    "Chile_Pruebas": {"Nombre": "TALENT PRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630, of 501, Vitacura, Santiago", "Giro": "Servicios de Selección"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630, of 501, Vitacura, Santiago", "Giro": "Asesoría RRHH"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2-2022 DV 27", "Dir": "CALLE 50, PH GLOBAL PLAZA, OF 6D, PANAMÁ", "Giro": "Talent Services"}
}

# --- CARGAR EXCEL ---
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        xls = pd.ExcelFile('precios.xlsx')
        return (pd.read_excel(xls, 'Pruebas Int'), pd.read_excel(xls, 'Servicios Int'), pd.read_excel(xls, 'Config'),
                pd.read_excel(xls, 'Pruebas_CL') if 'Pruebas_CL' in xls.sheet_names else pd.DataFrame(),
                pd.read_excel(xls, 'Servicios_CL') if 'Servicios_CL' in xls.sheet_names else pd.DataFrame(),
                pd.read_excel(xls, 'Pruebas_BR') if 'Pruebas_BR' in xls.sheet_names else pd.DataFrame(),
                pd.read_excel(xls, 'Servicios_BR') if 'Servicios_BR' in xls.sheet_names else pd.DataFrame())
    except: return None, None, None, None, None, None, None

data = cargar_datos()
if data[0] is None: st.error("Falta 'precios.xlsx'"); st.stop()
df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data

TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil"]

# --- APIS ---
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

# --- LOGICA ---
def obtener_contexto(pais):
    if pais == "Chile": return {"mon": "UF", "dp": df_p_cl, "ds": df_s_cl, "tipo": "Loc"}
    if pais in ["Brasil", "Brazil"]: return {"mon": "R$", "dp": df_p_br, "ds": df_s_br, "tipo": "Loc"}
    fil = df_config[df_config['Pais'] == pais]
    niv = fil.iloc[0]['Nivel'] if not fil.empty else "Medio"
    return {"mon": "US$", "dp": df_p_usd, "ds": df_s_usd, "tipo": "Int", "niv": niv}

def calc_paa(cant, mon):
    if cant <= 2: usd = 1500
    elif cant <= 5: usd = 1200
    else: usd = 1100
    if mon == "US$": return usd
    if mon == "UF": return (usd * TASAS['USD_CLP']) / TASAS['UF']
    if mon == "R$": return usd * TASAS['USD_BRL']
    return 0.0

def calc_xls(df, prod, cant, local):
    if df.empty: return 0.0
    row = df[df['Producto'] == prod]
    if row.empty: return 0.0
    tramos = [50, 100, 200, 300, 500, 1000, 'Infinito'] if local else [100, 200, 300, 500, 1000, 'Infinito']
    for t in tramos:
        lim = float('inf') if t == 'Infinito' else t
        if cant <= lim:
            try: return float(row.iloc[0][t])
            except: 
                try: return float(row.iloc[0][str(t)])
                except: return 0.0
    return 0.0

# --- PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 40)
        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 51, 102)
        self.cell(0, 15, self.title_text, 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.set_line_width(0.5); self.line(10, 30, 200, 30); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, 'TalentPro Digital Services', 0, 0, 'C')

def crear_pagina(pdf, empresa, cliente, items, moneda, idioma, extras, titulo):
    pdf.title_text = titulo # Set title for header
    pdf.add_page()
    t = TEXTOS[idioma]
    
    # Info
    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 51, 102)
    pdf.cell(95, 5, empresa['Nombre'], 0, 0)
    pdf.set_text_color(100); pdf.cell(95, 5, t['invoice_to'], 0, 1)
    
    pdf.set_font("Arial", '', 9); pdf.set_text_color(50)
    y = pdf.get_y()
    pdf.cell(95, 5, empresa['ID'], 0, 1); pdf.multi_cell(90, 5, empresa['Dir']); pdf.cell(95, 5, empresa['Giro'], 0, 1)
    
    pdf.set_xy(105, y); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0)
    pdf.cell(95, 5, cliente['empresa'], 0, 1)
    pdf.set_xy(105, pdf.get_y()); pdf.set_font("Arial", '', 9); pdf.set_text_color(50)
    pdf.cell(95, 5, cliente['contacto'], 0, 1)
    pdf.set_xy(105, pdf.get_y()); pdf.cell(95, 5, cliente['email'], 0, 1)
    
    pdf.ln(10)
    
    # Tables function
    def draw_table(lista_items, titulo_seccion):
        if not lista_items: return 0
        pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 8, titulo_seccion, 0, 1, 'L')
        
        pdf.set_fill_color(0, 51, 102); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 9)
        pdf.cell(110, 8, t['desc'], 0, 0, 'L', 1)
        pdf.cell(20, 8, t['qty'], 0, 0, 'C', 1)
        pdf.cell(30, 8, t['unit'], 0, 0, 'R', 1)
        pdf.cell(30, 8, t['total'], 0, 1, 'R', 1)
        
        pdf.set_text_color(0); pdf.set_font("Arial", '', 9)
        pdf.set_fill_color(245)
        sum_local = 0
        for i in lista_items:
            sum_local += i['Total']
            desc = i['Desc'][:55]
            qty = str(i['Det']).split('(')[0].replace('x','').strip()
            pdf.cell(110, 7, f"  {desc}", 'B', 0, 'L', 1)
            pdf.cell(20, 7, qty, 'B', 0, 'C', 1)
            pdf.cell(30, 7, f"{i['Unit']:,.2f}", 'B', 0, 'R', 1)
            pdf.cell(30, 7, f"{i['Total']:,.2f}", 'B', 1, 'R', 1)
        pdf.ln(3)
        return sum_local

    # Separar items si es una sola pagina
    i_pruebas = [x for x in items if x['Ítem']=='Evaluación']
    i_servs = [x for x in items if x['Ítem']=='Servicio']
    
    total_p = draw_table(i_pruebas, t['sec_prod'])
    total_s = draw_table(i_servs, t['sec_serv'])
    
    # Totals
    subtotal = total_p + total_s
    
    # Cálculos específicos de esta página
    fee_val = total_p * 0.10 if extras['fee'] else 0
    
    # Impuestos Locales de esta página
    tax_name, tax_val = "", 0
    if extras['pais'] == "Chile":
        # En Chile si es pagina Pruebas -> IVA. Si es Servicios -> 0.
        if total_p > 0: tax_name, tax_val = "IVA (19%)", total_p * 0.19
    elif extras['pais'] in ["Panamá", "Panama"]: tax_name, tax_val = "ITBMS (7%)", subtotal * 0.07
    elif extras['pais'] == "Honduras": tax_name, tax_val = "Retención (11.11%)", subtotal * 0.1111
    
    final = subtotal + fee_val + tax_val + extras['bank'] - extras['desc']
    
    # Draw Totals
    x_tab = 120
    def row(txt, val, bold=False):
        pdf.set_x(x_tab); pdf.set_font("Arial", 'B' if bold else '', 10)
        pdf.set_text_color(0 if not bold else 255)
        if bold: pdf.set_fill_color(0, 51, 102)
        pdf.cell(35, 7, txt, 0, 0, 'R', bold)
        pdf.cell(35, 7, f"{moneda} {val:,.2f} ", 0, 1, 'R', bold)

    row(t['subtotal'], subtotal)
    if fee_val > 0: row(t['fee'], fee_val)
    if tax_val > 0: row(tax_name, tax_val)
    if extras['bank'] > 0: row("Bank Fee", extras['bank'])
    if extras['desc'] > 0: row("Descuento", -extras['desc'])
    pdf.ln(1)
    row(t['grand_total'], final, True)
    
    pdf.ln(10)
    pdf.set_text_color(100); pdf.set_font("Arial", '', 8)
    pdf.cell(0, 5, f"ID: {extras['id']} | {t['validity']}", 0, 1)

# --- UI PRINCIPAL ---
if 'cotizaciones' not in st.session_state: st.session_state['cotizaciones'] = pd.DataFrame(columns=['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor'])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []

def cotizador():
    col_lang, col_tit = st.columns([1, 5])
    idioma = col_lang.selectbox("🌐", ["ES", "EN", "PT"])
    txt = TEXTOS[idioma]
    col_tit.title(txt['title'])

    c1, c2 = st.columns([1, 2])
    idx_cl = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    pais_sel = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx_cl)
    ctx = obtener_contexto(pais_sel)
    c2.info(f"Mon: **{ctx['mon']}** | Tipo: **{ctx['tipo']}** {ctx.get('niv','')}")

    st.markdown("---")
    cc1, cc2, cc3, cc4 = st.columns(4)
    empresa = cc1.text_input(txt['client'])
    contacto = cc2.text_input("Contacto")
    email = cc3.text_input("Email")
    vendedor = cc4.selectbox("Ejecutivo", ["Comercial 1", "Comercial 2"])

    st.markdown("---")
    tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    
    with tp:
        cp1, cp2, cp3, cp4 = st.columns([3, 1, 1, 1])
        lp = ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp = cp1.selectbox("Item", lp, key="ps")
            qp = cp2.number_input(txt['qty'], 1, 10000, 10, key="pq")
            up = calc_xls(ctx['dp'], sp, qp, ctx['tipo']=='Loc')
            cp3.metric(txt['unit'], f"{ctx['mon']} {up:,.2f}")
            if cp4.button(txt['add'], key="b1"):
                st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sp, "Det": f"x{qp}", "Moneda": ctx['mon'], "Unit": up, "Total": up*qp})
                st.rerun()

    with ts:
        cs1, cs2, cs3, cs4 = st.columns([3, 2, 1, 1])
        ls = ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        lf = ["Certificación PAA (Transversal)"] + ls
        if lf:
            ss = cs1.selectbox("Servicio", lf, key="ss")
            if ss.startswith("Cert"):
                cs2.write(""); qs = cs2.number_input("Pers", 1, 1000, 1, key="sq")
                us = calc_paa(qs, ctx['mon']); dt = f"{qs} pers"
            else:
                crol, cqty = cs2.columns(2)
                cols = ctx['ds'].columns.tolist()
                rv = [r for r in ['Angelica','Senior','BM','BP'] if r in cols]
                rol = crol.selectbox("Rol", rv) if rv else cols[-1]
                qs = cqty.number_input(txt['qty'], 1, 1000, 1, key="sq")
                us = 0.0
                row = ctx['ds'][(ctx['ds']['Servicio']==ss) & (ctx['ds']['Nivel']==ctx['niv'])] if ctx['tipo']=="Int" else ctx['ds'][ctx['ds']['Servicio']==ss]
                if not row.empty: us = float(row.iloc[0][rol])
                dt = f"{rol} ({qs})"
            cs3.metric(txt['unit'], f"{ctx['mon']} {us:,.2f}")
            if cs4.button(txt['add'], key="b2"):
                st.session_state['carrito'].append({"Ítem": "Servicio", "Desc": ss, "Det": dt, "Moneda": ctx['mon'], "Unit": us, "Total": us*qs})
                st.rerun()

    if st.session_state['carrito']:
        st.markdown("---")
        dfc = pd.DataFrame(st.session_state['carrito'])
        if len(dfc['Moneda'].unique()) > 1: st.error("Error Moneda")
        else:
            mon = dfc['Moneda'].unique()[0]
            st.dataframe(dfc[['Desc','Det','Unit','Total']], use_container_width=True)
            
            subt = dfc['Total'].sum()
            evals = dfc[dfc['Ítem']=='Evaluación']['Total'].sum()
            
            colL, colR = st.columns([3, 1])
            with colR:
                fee = st.checkbox(txt['fee'], value=False)
                bank = st.number_input("Bank Fee", 0.0, value=30.0 if mon=="US$" else 0.0)
                desc = st.number_input(txt['discount'], 0.0)
                
                val_fee = evals * 0.10 if fee else 0
                # Impuesto visual aproximado (solo referencia, el real va en PDF)
                taxn, taxv = calcular_impuestos(pais_sel, subt, evals)
                fin = subt + val_fee + taxv + bank - desc
                
                st.metric(txt['grand_total'], f"{mon} {fin:,.2f}")
                
                if st.button(txt['save'], type="primary"):
                    if not empresa: st.error("Falta Empresa")
                    else:
                        nid = f"TP-{random.randint(1000,9999)}"
                        cli_data = {'empresa':empresa, 'contacto':contacto, 'email':email}
                        extras = {'fee':fee, 'bank':bank, 'desc':desc, 'pais':pais_sel, 'id':nid}
                        
                        pdf = PDF()
                        pdf.title_text = txt['quote']
                        
                        # LOGICA SPLIT CHILE
                        pruebas = [x for x in st.session_state['carrito'] if x['Ítem']=='Evaluación']
                        servs = [x for x in st.session_state['carrito'] if x['Ítem']=='Servicio']
                        
                        if pais_sel == "Chile" and pruebas and servs:
                            # 2 PAGINAS
                            # P1 Pruebas
                            ex1 = extras.copy(); ex1['bank']=0; ex1['desc']=0 # Simplificacion: Bank/Desc solo en una?
                            crear_pagina(pdf, EMPRESAS['Chile_Pruebas'], cli_data, pruebas, mon, idioma, ex1, txt['quote'])
                            # P2 Servicios
                            crear_pagina(pdf, EMPRESAS['Chile_Servicios'], cli_data, servs, mon, idioma, extras, txt['quote'])
                        else:
                            # 1 PAGINA
                            ent = determinar_empresa_facturadora(pais_sel, st.session_state['carrito'])
                            crear_pagina(pdf, ent, cli_data, st.session_state['carrito'], mon, idioma, extras, txt['quote'])
                            
                        b64 = base64.b64encode(pdf.output(dest='S').encode('latin-1')).decode('latin-1')
                        href = f'<a href="data:application/pdf;base64,{b64}" download="Cotizacion_{nid}.pdf" style="background:#003366;color:white;padding:10px;border-radius:5px;text-decoration:none;">{txt["download"]}</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("OK")
            with colL:
                if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

# --- UTILS ---
def determinar_empresa_facturadora(pais, items):
    if pais == "Brasil": return EMPRESAS["Brasil"]
    if pais in ["Perú", "Peru"]: return EMPRESAS["Peru"]
    if pais == "Chile":
        return EMPRESAS["Chile_Pruebas"] if any(i['Ítem']=='Evaluación' for i in items) else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

def calcular_impuestos(pais, sub, eva):
    if pais == "Chile": return "IVA (19%)", eva*0.19
    if pais in ["Panamá", "Panama"]: return "ITBMS (7%)", sub*0.07
    if pais == "Honduras": return "Retención", sub*0.1111
    return "", 0

def dashboard():
    st.title("Dashboard"); df = st.session_state['cotizaciones']
    if not df.empty: st.dataframe(df)

def finanzas():
    st.title("Finanzas"); df = st.session_state['cotizaciones']
    if not df.empty: st.data_editor(df, disabled=["id"], hide_index=True)

with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=130)
    op = st.radio("Menu", ["Cotizador", "Dashboard", "Finanzas"])

if op == "Cotizador": cotizador()
elif op == "Dashboard": dashboard()
elif op == "Finanzas": finanzas()
