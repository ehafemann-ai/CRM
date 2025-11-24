import streamlit as st
import pandas as pd
import random
import requests
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
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. TRADUCCIONES Y ENTIDADES (ESTÁTICO)
# ==============================================================================
TEXTOS = {
    "ES": {
        "title": "Cotizador TalentPro", "client": "Datos Cliente", "items": "Selección",
        "add": "Agregar", "desc": "Descripción", "qty": "Cant", "unit": "Unitario", "total": "Total",
        "subtotal": "Subtotal", "fee": "Fee Admin (10%)", "tax": "Impuestos", "discount": "Descuento",
        "grand_total": "TOTAL A PAGAR", "download": "Descargar PDF", "invoice_to": "Facturar a",
        "quote": "COTIZACIÓN", "date": "Fecha", "validity": "Validez: 30 días"
    },
    "EN": {
        "title": "TalentPro Quote Tool", "client": "Client Details", "items": "Selection",
        "add": "Add", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "total": "Total",
        "subtotal": "Subtotal", "fee": "Admin Fee (10%)", "tax": "Taxes", "discount": "Discount",
        "grand_total": "GRAND TOTAL", "download": "Download PDF", "invoice_to": "Bill to",
        "quote": "QUOTATION", "date": "Date", "validity": "Validity: 30 days"
    },
    "PT": {
        "title": "Cotação TalentPro", "client": "Dados do Cliente", "items": "Seleção",
        "add": "Adicionar", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total",
        "subtotal": "Subtotal", "fee": "Taxa Admin (10%)", "tax": "Impostos", "discount": "Desconto",
        "grand_total": "TOTAL A PAGAR", "download": "Baixar PDF", "invoice_to": "Faturar para",
        "quote": "COTAÇÃO", "date": "Data", "validity": "Validade: 30 dias"
    }
}

EMPRESAS = {
    "Brasil": {
        "Nombre": "TalentPRO Brasil Consutoria Ltda.",
        "ID": "CNPJ: 49.704.046/0001-80",
        "Dir": "Av. Marcos Penteado de Ulhoa Rodriguez 939, Andar 8, Tamboré",
        "Giro": "Consultoria em gestão empresarial"
    },
    "Peru": {
        "Nombre": "TALENTPRO SOCIEDAD ANÓNIMA CERRADA",
        "ID": "DNI 25489763",
        "Dir": "AVENIDA EL DERBY 254, SANTIAGO DE SURCO, LIMA, PERÚ",
        "Giro": "Servicios de apoyo a las empresas"
    },
    "Chile_Pruebas": {
        "Nombre": "TALENT PRO SPA",
        "ID": "RUT: 76.743.976-8",
        "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile",
        "Giro": "Servicios de Reclutamiento y Selección"
    },
    "Chile_Servicios": {
        "Nombre": "TALENTPRO SERVICIOS PROFESIONALES LTDA.",
        "ID": "RUT: 77.704.757-4",
        "Dir": "Juan de Valiente 3630, oficina 501, Vitacura, Santiago, Chile",
        "Giro": "Asesoría en Recursos Humanos"
    },
    "Latam": {
        "Nombre": "TALENTPRO LATAM, S.A.",
        "ID": "RUC: 155723672-2-2022 DV 27",
        "Dir": "CALLE 50, PH GLOBAL PLAZA, OFICINA 6D, BELLA VISTA, PANAMÁ",
        "Giro": "Talent Acquisition Services"
    }
}

# --- 2. CARGA DE DATOS (EXCEL) ---
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        xls = pd.ExcelFile('precios.xlsx')
        # Intentamos cargar las hojas con nombres correctos
        df_p_usd = pd.read_excel(xls, 'Pruebas Int')
        df_s_usd = pd.read_excel(xls, 'Servicios Int')
        df_config = pd.read_excel(xls, 'Config')
        
        # Cargas opcionales (locales)
        df_p_cl = pd.read_excel(xls, 'Pruebas_CL') if 'Pruebas_CL' in xls.sheet_names else pd.DataFrame()
        df_s_cl = pd.read_excel(xls, 'Servicios_CL') if 'Servicios_CL' in xls.sheet_names else pd.DataFrame()
        df_p_br = pd.read_excel(xls, 'Pruebas_BR') if 'Pruebas_BR' in xls.sheet_names else pd.DataFrame()
        df_s_br = pd.read_excel(xls, 'Servicios_BR') if 'Servicios_BR' in xls.sheet_names else pd.DataFrame()

        return df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br
    except FileNotFoundError:
        return None, None, None, None, None, None, None
    except Exception as e:
        st.error(f"Error leyendo Excel: {e}")
        return None, None, None, None, None, None, None

# Cargar y verificar
data = cargar_datos()
if data[0] is None:
    st.error("⚠️ Error crítico: No se pudo leer 'precios.xlsx'. Revisa que esté en GitHub y tenga las hojas correctas.")
    st.stop()

df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data

# --- CONSTRUIR LISTA DE PAÍSES DESDE EL EXCEL ---
if not df_config.empty and 'Pais' in df_config.columns:
    TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist())
else:
    st.error("⚠️ La hoja 'Config' del Excel está vacía o no tiene la columna 'Pais'.")
    TODOS_LOS_PAISES = ["Chile", "Brasil"] # Fallback

# --- 3. APIS INDICADORES ---
@st.cache_data(ttl=3600)
def obtener_indicadores():
    tasas = {"UF": 38000, "USD_CLP": 980, "USD_BRL": 5.8, "Status": "Offline"}
    try:
        r_cl = requests.get('https://mindicador.cl/api', timeout=5).json()
        tasas['UF'] = r_cl['uf']['valor']
        tasas['USD_CLP'] = r_cl['dolar']['valor']
        r_br = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5).json()
        tasas['USD_BRL'] = r_br['rates']['BRL']
        tasas['Status'] = "Online"
    except: pass
    return tasas

TASAS_DIA = obtener_indicadores()

# --- LÓGICA DE NEGOCIO ---
def obtener_contexto_pais(pais):
    if pais == "Chile": 
        return {"moneda": "UF", "df_p": df_p_cl, "df_s": df_s_cl, "tipo": "Local"}
    elif pais in ["Brasil", "Brazil"]: 
        return {"moneda": "R$", "df_p": df_p_br, "df_s": df_s_br, "tipo": "Local"}
    else:
        # Busca el nivel en el dataframe de Config cargado del Excel
        fila = df_config[df_config['Pais'] == pais]
        nivel = fila.iloc[0]['Nivel'] if not fila.empty else "Medio"
        return {"moneda": "US$", "df_p": df_p_usd, "df_s": df_s_usd, "tipo": "Internacional", "nivel": nivel}

def determinar_empresa_facturadora(pais, items_carrito):
    if pais == "Brasil": return EMPRESAS["Brasil"]
    if pais in ["Perú", "Peru"]: return EMPRESAS["Peru"]
    if pais == "Chile":
        hay_pruebas = any(item['Ítem'] == 'Evaluación' for item in items_carrito)
        return EMPRESAS["Chile_Pruebas"] if hay_pruebas else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

def calcular_impuestos(pais, subtotal, total_pruebas):
    nombre, monto = "", 0.0
    if pais == "Chile":
        nombre = "IVA (19% s/Pruebas)"
        monto = total_pruebas * 0.19
    elif pais in ["Panamá", "Panama"]:
        nombre = "ITBMS (7%)"
        monto = subtotal * 0.07
    elif pais == "Honduras":
        nombre = "Retención (11.11%)"
        monto = subtotal * 0.1111
    return nombre, monto

# --- GENERADOR PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 51, 102) # Azul oscuro
        self.cell(0, 10, 'TALENTPRO', 0, 1, 'L')
        self.ln(5)

def generar_pdf(empresa_emisora, cliente, items, calculos, idioma):
    pdf = PDF()
    pdf.add_page()
    t = TEXTOS[idioma]
    
    # Datos Emisor
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, empresa_emisora['Nombre'], 0, 1)
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, empresa_emisora['ID'], 0, 1)
    pdf.multi_cell(0, 5, empresa_emisora['Dir']) # Multicell para direcciones largas
    pdf.cell(0, 5, empresa_emisora['Giro'], 0, 1)
    pdf.ln(8)
    
    # Datos Cliente
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, f"{t['invoice_to']}", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, f"{t['client']}: {cliente['empresa']}", 0, 1)
    pdf.cell(0, 5, f"At: {cliente['contacto']} ({cliente['email']})", 0, 1)
    pdf.cell(0, 5, f"{t['date']}: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
    pdf.ln(8)
    
    # Tabla
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(100, 8, t['desc'], 1, 0, 'L', 1)
    pdf.cell(20, 8, t['qty'], 1, 0, 'C', 1)
    pdf.cell(30, 8, t['unit'], 1, 0, 'R', 1)
    pdf.cell(40, 8, t['total'], 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 8)
    for item in items:
        desc = (item['Desc'][:55] + '..') if len(item['Desc']) > 55 else item['Desc']
        pdf.cell(100, 8, desc, 1)
        # Hack visual para cantidad (quita paréntesis del rol si es servicio)
        qty_str = str(item['Det']).split('(')[0].replace('x','').replace('pers','').strip()
        try: 
            if not qty_str[0].isdigit(): qty_str = "1" 
        except: qty_str="1"
            
        pdf.cell(20, 8, qty_str, 1, 0, 'C')
        pdf.cell(30, 8, f"{item['Unit']:,.2f}", 1, 0, 'R')
        pdf.cell(40, 8, f"{item['Total']:,.2f}", 1, 1, 'R')
    
    pdf.ln(5)
    
    # Totales
    mon = items[0]['Moneda']
    def fila_total(label, valor, bold=False):
        pdf.set_font("Arial", 'B' if bold else '', 9 if not bold else 10)
        pdf.cell(140)
        pdf.cell(25, 6, label, 0, 0, 'R')
        pdf.cell(25, 6, f"{mon} {valor:,.2f}", 0, 1, 'R')

    fila_total(t['subtotal'], calculos['subtotal'])
    if calculos['fee'] > 0: fila_total(t['fee'], calculos['fee'])
    if calculos['tax_val'] > 0: fila_total(calculos['tax_name'], calculos['tax_val'])
    if calculos['bank'] > 0: fila_total("Bank Fee", calculos['bank'])
    if calculos['desc'] > 0: fila_total(t['discount'], -calculos['desc'])
    
    pdf.ln(2)
    fila_total(t['grand_total'], calculos['total'], bold=True)
    
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, t['validity'], 0, 1, 'C')
    pdf.cell(0, 5, "Generado por TalentPro App", 0, 1, 'C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- UI ---
if 'cotizaciones' not in st.session_state: st.session_state['cotizaciones'] = pd.DataFrame(columns=['id', 'fecha', 'empresa', 'pais', 'total', 'moneda', 'estado', 'vendedor'])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []

def calcular_paa(cantidad, moneda_destino):
    if cantidad <= 2: base_usd = 1500
    elif cantidad <= 5: base_usd = 1200
    else: base_usd = 1100
    
    if moneda_destino == "US$": return base_usd, f"Tramo USD: ${base_usd}"
    elif moneda_destino == "UF": return (base_usd * TASAS_DIA['USD_CLP']) / TASAS_DIA['UF'], "(USD*Dolar)/UF"
    elif moneda_destino == "R$": return base_usd * TASAS_DIA['USD_BRL'], f"USD * {TASAS_DIA['USD_BRL']}"
    return 0.0, "Err"

def calc_excel(df, prod, cant, es_local):
    if df.empty: return 0.0
    fila = df[df['Producto'] == prod]
    if fila.empty: return 0.0
    tramos = [50, 100, 200, 300, 500, 1000, 'Infinito'] if es_local else [100, 200, 300, 500, 1000, 'Infinito']
    for t in tramos:
        lim = float('inf') if t == 'Infinito' else t
        if cant <= lim:
            try: return float(fila.iloc[0][t])
            except: 
                try: return float(fila.iloc[0][str(t)])
                except: return 0.0
    return 0.0

def cotizador():
    col_lang, col_tit = st.columns([1, 6])
    idioma = col_lang.selectbox("🌐", ["ES", "EN", "PT"])
    txt = TEXTOS[idioma]
    col_tit.title(txt['title'])

    # 1. PAIS (DINÁMICO DESDE EXCEL)
    c1, c2 = st.columns([1, 2])
    idx_cl = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    pais_sel = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx_cl)
    
    ctx = obtener_contexto_pais(pais_sel)
    c2.info(f"Moneda: **{ctx['moneda']}** | Tipo: **{ctx['tipo']}** {f'({ctx.get('nivel','')})' if ctx['tipo']=='Internacional' else ''}")

    # 2. CLIENTE
    st.markdown("---")
    cc1, cc2, cc3, cc4 = st.columns(4)
    empresa = cc1.text_input(txt['client'])
    contacto = cc2.text_input("Contacto")
    email = cc3.text_input("Email")
    vendedor = cc4.selectbox("Ejecutivo", ["Comercial 1", "Comercial 2", "Gerencia"])

    # 3. ITEMS
    st.markdown("---")
    tp, ts = st.tabs(["🧩 Evaluaciones", "💼 Servicios"])
    
    with tp:
        # PRUEBAS
        cp1, cp2, cp3, cp4 = st.columns([3, 1, 1, 1])
        lst_p = ctx['df_p']['Producto'].unique().tolist() if not ctx['df_p'].empty else []
        if lst_p:
            sel_p = cp1.selectbox("Item", lst_p, key="p_sel")
            cant_p = cp2.number_input(txt['qty'], 1, 10000, 10, key="p_cant")
            es_loc = (ctx['tipo'] == 'Local')
            up = calc_excel(ctx['df_p'], sel_p, cant_p, es_loc)
            cp3.metric(txt['unit'], f"{ctx['moneda']} {up:,.2f}")
            if cp4.button(txt['add'], key="ap"):
                st.session_state['carrito'].append({"Ítem": "Evaluación", "Desc": sel_p, "Det": f"x{cant_p}", "Moneda": ctx['moneda'], "Unit": up, "Total": up*cant_p})
                st.rerun()

    with ts:
        # SERVICIOS
        cs1, cs2, cs3, cs4 = st.columns([3, 2, 1, 1])
        lst_s_xls = ctx['df_s']['Servicio'].unique().tolist() if not ctx['df_s'].empty else []
        lst_full = ["Certificación PAA (Transversal)"] + lst_s_xls
        
        if lst_full:
            sel_s = cs1.selectbox("Servicio", lst_full, key="s_sel")
            
            if sel_s == "Certificación PAA (Transversal)":
                c_rol, c_qty = cs2.columns([1, 30])
                c_rol.write("")
                cant_s = c_qty.number_input(txt['qty'], 1, 1000, 1, key="s_cant")
                us, _ = calcular_paa(cant_s, ctx['moneda'])
                det_txt = f"{cant_s} pers"
            else:
                c_rol, c_qty = cs2.columns(2)
                # Si es local no hay roles en columna, si es int sí
                cols_serv = ctx['df_s'].columns.tolist()
                posibles_roles = ['Angelica', 'Senior', 'BM', 'BP']
                roles_validos = [r for r in posibles_roles if r in cols_serv]
                
                if roles_validos:
                    rol = c_rol.selectbox("Rol", roles_validos)
                else:
                    rol = cols_serv[-1] # Fallback si no hay roles estandar
                
                cant_s = c_qty.number_input(txt['qty'], 1, 1000, 1)
                
                us = 0.0
                if ctx['tipo'] == "Internacional":
                    row = ctx['df_s'][(ctx['df_s']['Servicio']==sel_s) & (ctx['df_s']['Nivel']==ctx['nivel'])]
                else:
                    row = ctx['df_s'][ctx['df_s']['Servicio']==sel_s]
                
                if not row.empty: us = float(row.iloc[0][rol]) if rol in row.columns else 0.0
                det_txt = f"{rol} ({cant_s})"

            cs3.metric(txt['unit'], f"{ctx['moneda']} {us:,.2f}")
            if cs4.button(txt['add'], key="as"):
                st.session_state['carrito'].append({"Ítem": "Servicio", "Desc": sel_s, "Det": det_txt, "Moneda": ctx['moneda'], "Unit": us, "Total": us*cant_s})
                st.rerun()

    # 4. RESUMEN
    if st.session_state['carrito']:
        st.markdown("---")
        df_c = pd.DataFrame(st.session_state['carrito'])
        
        if len(df_c['Moneda'].unique()) > 1: st.error("Error: Monedas mezcladas.")
        else:
            mon = df_c['Moneda'].unique()[0]
            st.dataframe(df_c[['Desc', 'Det', 'Unit', 'Total']], use_container_width=True)
            
            subtotal = df_c['Total'].sum()
            tot_eval = df_c[df_c['Ítem']=='Evaluación']['Total'].sum()
            
            cL, cR = st.columns([3, 1])
            with cR:
                fee = st.checkbox(txt['fee'], value=False)
                bank = st.number_input("Bank Fee", 0.0, value=30.0 if mon=="US$" else 0.0)
                desc = st.number_input(txt['discount'], 0.0)
                
                val_fee = tot_eval * 0.10 if fee else 0.0
                tax_name, val_tax = calcular_impuestos(pais_sel, subtotal, tot_eval)
                final = subtotal + val_fee + val_tax + bank - desc
                
                st.markdown(f"""
                **{txt['subtotal']}:** {mon} {subtotal:,.2f}  
                **Fee:** {mon} {val_fee:,.2f}  
                **{tax_name}:** {mon} {val_tax:,.2f}  
                **Bank:** {mon} {bank:,.2f}  
                **Desc:** -{mon} {desc:,.2f}  
                ### {txt['grand_total']}: {mon} {final:,.2f}
                """)
                
                if st.button(txt['save'], type="primary"):
                    if not empresa: st.error("Error: Falta Empresa")
                    else:
                        nid = f"TP-{random.randint(1000,9999)}"
                        entidad = determinar_empresa_facturadora(pais_sel, st.session_state['carrito'])
                        calcs = {'subtotal':subtotal, 'fee':val_fee, 'tax_name':tax_name, 'tax_val':val_tax, 'bank':bank, 'desc':desc, 'total':final}
                        cli = {'empresa':empresa, 'contacto':contacto, 'email':email}
                        
                        pdf_bytes = generar_pdf(entidad, cli, st.session_state['carrito'], calcs, idioma)
                        b64 = base64.b64encode(pdf_bytes).decode('latin-1')
                        href = f'<a href="data:application/pdf;base64,{b64}" download="Cotizacion_{nid}.pdf" style="background-color:#FF4B4B;color:white;padding:8px 12px;text-decoration:none;border-radius:4px;">{txt["download"]}</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        
                        st.session_state['cotizaciones'] = pd.concat([st.session_state['cotizaciones'], pd.DataFrame([{
                            'id': nid, 'fecha': datetime.now().strftime("%Y-%m-%d"), 'empresa': empresa, 'pais': pais_sel,
                            'total': final, 'moneda': mon, 'estado': 'Enviada', 'vendedor': vendedor
                        }])], ignore_index=True)
                        st.session_state['carrito'] = []
                        st.success("OK")
            with cL:
                if st.button("🗑️"): st.session_state['carrito']=[]; st.rerun()

def dashboard():
    st.title("📊 Dashboard")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No data"); return
    c1, c2 = st.columns(2)
    c1.dataframe(df.groupby('moneda')['total'].sum())
    c2.metric("Total", len(df))

def finanzas():
    st.title("💰 Finanzas")
    df = st.session_state['cotizaciones']
    if df.empty: return
    ed = st.data_editor(df, disabled=["id"], hide_index=True)
    if not ed.equals(df): st.session_state['cotizaciones'] = ed

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    op = st.radio("Menu", ["Cotizador", "Dashboard", "Finanzas"])

if op == "Cotizador": cotizador()
elif op == "Dashboard": dashboard()
elif op == "Finanzas": finanzas()
