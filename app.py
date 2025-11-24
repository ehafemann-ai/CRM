import streamlit as st
import pandas as pd
import random
import requests
import os
from datetime import datetime
from fpdf import FPDF
import base64
import plotly.express as px
from streamlit_option_menu import option_menu

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="TalentPro ERP", layout="wide", page_icon="🚀")

# ESTILOS CSS
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
# 1. RECURSOS Y CARGA DE DATOS
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
        except:
            pass
descargar_logo()

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
if data[0] is None:
    st.error("Falta 'precios.xlsx'")
    st.stop()

df_p_usd, df_s_usd, df_config, df_p_cl, df_s_cl, df_p_br, df_s_br = data
TODOS_LOS_PAISES = sorted(df_config['Pais'].unique().tolist()) if not df_config.empty else ["Chile", "Brasil"]

# --- INDICADORES ECONÓMICOS (API) ---
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

# --- TEXTOS Y ENTIDADES ---
TEXTOS = {
    "ES": {"title": "Cotizador", "client": "Cliente", "add": "Agregar", "desc": "Descripción", "qty": "Cant.", "unit": "Unitario", "total": "Total", "subtotal": "Subtotal", "fee": "Fee Admin (10%)", "grand_total": "TOTAL", "invoice_to": "Facturar a:", "quote": "COTIZACIÓN", "date": "Fecha", "validity": "Validez: 30 días", "save": "Guardar y Enviar", "download": "Descargar PDF", "sec_prod": "Licencias", "sec_serv": "Servicios", "discount": "Descuento", "tax": "Impuestos", "legal_intl": "Facturación a {pais}. Sumar impuestos retenidos y gastos OUR.", "noshow_title": "Política No-Show:", "noshow_text": "Multa 50% por inasistencia sin aviso 24h."},
    "EN": {"title": "Quote Tool", "client": "Client", "add": "Add", "desc": "Description", "qty": "Qty", "unit": "Price", "total": "Total", "subtotal": "Subtotal", "fee": "Admin Fee", "grand_total": "TOTAL", "invoice_to": "Bill to:", "quote": "QUOTATION", "date": "Date", "validity": "Valid: 30 days", "save": "Save & Send", "download": "Download PDF", "sec_prod": "Licenses", "sec_serv": "Services", "discount": "Discount", "tax": "Taxes", "legal_intl": "Billing to {pais}. Add withholding taxes and OUR bank fees.", "noshow_title": "No-Show Policy:", "noshow_text": "50% fee for absence without 24h notice."},
    "PT": {"title": "Cotação", "client": "Cliente", "add": "Adicionar", "desc": "Descrição", "qty": "Qtd", "unit": "Unitário", "total": "Total", "subtotal": "Subtotal", "fee": "Taxa Admin", "grand_total": "TOTAL", "invoice_to": "Faturar para:", "quote": "COTAÇÃO", "date": "Data", "validity": "Validade: 30 dias", "save": "Salvar e Enviar", "download": "Baixar PDF", "sec_prod": "Licenças", "sec_serv": "Serviços", "discount": "Desconto", "tax": "Impostos", "legal_intl": "Faturamento para {pais}. Adicionar impostos retidos e taxas bancárias.", "noshow_title": "Política No-Show:", "noshow_text": "Multa de 50% por ausência sem aviso de 24h."}
}
EMPRESAS = {
    "Brasil": {"Nombre": "TalentPRO Brasil Ltda.", "ID": "CNPJ: 49.704.046/0001-80", "Dir": "Av. Marcos Penteado 939, Tamboré", "Giro": "Consultoria"},
    "Peru": {"Nombre": "TALENTPRO S.A.C.", "ID": "DNI 25489763", "Dir": "AV. EL DERBY 254, LIMA", "Giro": "Servicios"},
    "Chile_Pruebas": {"Nombre": "TALENT PRO SPA", "ID": "RUT: 76.743.976-8", "Dir": "Juan de Valiente 3630, Vitacura", "Giro": "Selección"},
    "Chile_Servicios": {"Nombre": "TALENTPRO SERVICIOS LTDA.", "ID": "RUT: 77.704.757-4", "Dir": "Juan de Valiente 3630, Vitacura", "Giro": "RRHH"},
    "Latam": {"Nombre": "TALENTPRO LATAM, S.A.", "ID": "RUC: 155723672-2", "Dir": "CALLE 50, GLOBAL PLAZA, PANAMÁ", "Giro": "Talent Services"}
}

# ==============================================================================
# 2. LÓGICA DE NEGOCIO
# ==============================================================================
if 'cotizaciones' not in st.session_state: 
    st.session_state['cotizaciones'] = pd.DataFrame([
        {'id': 'TP-1001', 'fecha': '2024-11-01', 'empresa': 'Coca Cola', 'pais': 'Chile', 'moneda': 'UF', 'total': 150.5, 'estado': 'Facturada', 'vendedor': 'Comercial 1', 'idioma': 'ES'},
        {'id': 'TP-1002', 'fecha': '2024-11-15', 'empresa': 'Walmart', 'pais': 'Estados Unidos', 'moneda': 'US$', 'total': 5000, 'estado': 'Aprobada', 'vendedor': 'Comercial 2', 'idioma': 'EN'},
        {'id': 'TP-1003', 'fecha': '2024-11-20', 'empresa': 'Embraer', 'pais': 'Brasil', 'moneda': 'R$', 'total': 12000, 'estado': 'Enviada', 'vendedor': 'Comercial 1', 'idioma': 'PT'},
    ])
if 'carrito' not in st.session_state: st.session_state['carrito'] = []

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
    if pais=="Chile": return EMPRESAS["Chile_Pruebas"] if any(i['Ítem']=='Evaluación' for i in items) else EMPRESAS["Chile_Servicios"]
    return EMPRESAS["Latam"]

# --- PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH): self.image(LOGO_PATH, 10, 10, 35)
        self.set_font('Arial', 'B', 18); self.set_text_color(0, 51, 102)
        self.cell(0, 15, getattr(self,'tit','COTIZACIÓN'), 0, 1, 'R')
        self.set_draw_color(0, 51, 102); self.line(10, 30, 200, 30); self.ln(5)
def generar_pdf_final(emp, cli, items, calc, lang, extras, tit):
    pdf = PDF(); pdf.tit=tit; pdf.add_page(); t=TEXTOS[lang]
    pdf.set_font("Arial",'B',10); pdf.set_text_color(0,51,102); pdf.cell(95,5,emp['Nombre'],0,0)
    pdf.set_text_color(100); pdf.cell(95,5,t['invoice_to'],0,1)
    pdf.set_font("Arial",'',9); pdf.set_text_color(50); y=pdf.get_y()
    pdf.cell(95,5,emp['ID'],0,1); pdf.multi_cell(90,5,emp['Dir']); pdf.cell(95,5,emp['Giro'],0,1)
    pdf.set_xy(105,y); pdf.set_font("Arial",'B',10); pdf.set_text_color(0); pdf.cell(95,5,cli['empresa'],0,1)
    pdf.set_xy(105,pdf.get_y()); pdf.set_font("Arial",'',9); pdf.set_text_color(50)
    pdf.cell(95,5,cli['contacto'],0,1); pdf.set_xy(105,pdf.get_y()); pdf.cell(95,5,cli['email'],0,1)
    pdf.ln(5); pdf.set_xy(105,pdf.get_y()); pdf.set_text_color(0,51,102)
    pdf.cell(95,5,f"{t['date']}: {datetime.now().strftime('%d/%m/%Y')} | ID: {extras['id']}",0,1); pdf.ln(10)
    
    # Tabla
    pdf.set_fill_color(0,51,102); pdf.set_text_color(255); pdf.set_font("Arial",'B',9)
    pdf.cell(110,8,t['desc'],0,0,'L',1); pdf.cell(20,8,t['qty'],0,0,'C',1); pdf.cell(30,8,t['unit'],0,0,'R',1); pdf.cell(30,8,t['total'],0,1,'R',1)
    pdf.set_text_color(0); pdf.set_font("Arial",'',8); mon=items[0]['Moneda']
    for i in items:
        q=str(i['Det']).split('(')[0].replace('x','').strip()
        pdf.cell(110,7,f"  {i['Desc'][:55]}",'B',0,'L'); pdf.cell(20,7,q,'B',0,'C')
        pdf.cell(30,7,f"{i['Unit']:,.2f}",'B',0,'R'); pdf.cell(30,7,f"{i['Total']:,.2f}",'B',1,'R')
    pdf.ln(5)
    
    # Totales
    x=120
    def r(l,v,b=False):
        pdf.set_x(x); pdf.set_font("Arial",'B' if b else '',10); pdf.set_text_color(0 if not b else 255)
        if b: pdf.set_fill_color(0,51,102)
        pdf.cell(35,7,l,0,0,'R',b); pdf.cell(35,7,f"{mon} {v:,.2f} ",0,1,'R',b)
    r(t['subtotal'], calc['subtotal'])
    if calc['fee']>0: r(t['fee'], calc['fee'])
    if calc['tax_val']>0: r(calc['tax_name'], calc['tax_val'])
    if extras.get('bank',0)>0: r("Bank Fee", extras['bank'])
    if extras.get('desc',0)>0: r(t['discount'], -extras['desc'])
    pdf.ln(1); r(t['grand_total'], calc['total'], True); pdf.ln(10)
    
    # Legal
    pdf.set_font("Arial",'I',8); pdf.set_text_color(80)
    if emp['Nombre']==EMPRESAS['Latam']['Nombre']: pdf.multi_cell(0,4,t['legal_intl'].format(pais=extras['pais']),0,'L'); pdf.ln(3)
    trigs=['feedback','coaching','entrevista','preparación','preparação','interview']
    if any(any(tr in i['Desc'].lower() for tr in trigs) for i in items):
        pdf.set_font("Arial",'B',8); pdf.cell(0,4,t['noshow_title'],0,1)
        pdf.set_font("Arial",'',8); pdf.multi_cell(0,4,t['noshow_text'],0,'L'); pdf.ln(3)
    pdf.set_text_color(100); pdf.cell(0,5,t['validity'],0,1)
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 3. MÓDULOS (VISTAS)
# ==============================================================================

def modulo_cotizador():
    cl, ct = st.columns([1,5]); idi = cl.selectbox("🌐", ["ES","EN","PT"]); txt = TEXTOS[idi]; ct.title(txt['title'])
    
    # INDICADORES
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("UF (CL)", f"${TASAS['UF']:,.0f}")
    k2.metric("USD (CL)", f"${TASAS['USD_CLP']:,.0f}")
    k3.metric("USD (BR)", f"R$ {TASAS['USD_BRL']:.2f}")
    
    st.markdown("---")
    
    c1, c2 = st.columns([1,2]); idx = TODOS_LOS_PAISES.index("Chile") if "Chile" in TODOS_LOS_PAISES else 0
    ps = c1.selectbox("🌎 País", TODOS_LOS_PAISES, index=idx); ctx = obtener_contexto(ps)
    c2.info(f"Moneda: **{ctx['mon']}** | Tarifas: **{ctx['tipo']}** {ctx.get('niv','')}")
    
    st.markdown("---"); cc1,cc2,cc3,cc4=st.columns(4)
    emp=cc1.text_input(txt['client']); con=cc2.text_input("Contacto"); ema=cc3.text_input("Email"); ven=cc4.selectbox("Ejecutivo",["Comercial 1","Comercial 2"])
    
    st.markdown("---"); tp, ts = st.tabs([txt['sec_prod'], txt['sec_serv']])
    with tp:
        c1,c2,c3,c4=st.columns([3,1,1,1]); lp=ctx['dp']['Producto'].unique().tolist() if not ctx['dp'].empty else []
        if lp:
            sp=c1.selectbox("Item",lp,key="p1"); qp=c2.number_input(txt['qty'],1,10000,10,key="q1")
            up=calc_xls(ctx['dp'],sp,qp,ctx['tipo']=='Loc'); c3.metric(txt['unit'],f"{up:,.2f}")
            if c4.button(txt['add'],key="b1"): st.session_state['carrito'].append({"Ítem":"Evaluación","Desc":sp,"Det":f"x{qp}","Moneda":ctx['mon'],"Unit":up,"Total":up*qp}); st.rerun()
    with ts:
        c1,c2,c3,c4=st.columns([3,2,1,1]); ls=ctx['ds']['Servicio'].unique().tolist() if not ctx['ds'].empty else []
        lf=["Certificación PAA (Transversal)"]+ls
        if lf:
            ss=c1.selectbox("Serv",lf,key="s1")
            if "PAA" in ss: c2.write(""); qs=c2.number_input("Pers",1,1000,1,key="q2"); us=calc_paa(qs,ctx['mon']); dt=f"{qs} pers"
            else:
                r,q=c2.columns(2); cs=ctx['ds'].columns.tolist(); rv=[x for x in ['Angelica','Senior','BM','BP'] if x in cs]
                rol=r.selectbox("Rol",rv) if rv else cs[-1]; qs=q.number_input(txt['qty'],1,1000,1); us=0.0
                rw=ctx['ds'][(ctx['ds']['Servicio']==ss)&(ctx['ds']['Nivel']==ctx['niv'])] if ctx['tipo']=="Int" else ctx['ds'][ctx['ds']['Servicio']==ss]
                if not rw.empty: us=float(rw.iloc[0][rol])
                dt=f"{rol} ({qs})"
            c3.metric(txt['unit'],f"{us:,.2f}"); 
            if c4.button(txt['add'],key="b2"): st.session_state['carrito'].append({"Ítem":"Servicio","Desc":ss,"Det":dt,"Moneda":ctx['mon'],"Unit":us,"Total":us*qs}); st.rerun()

    if st.session_state['carrito']:
        st.markdown("---"); dfc=pd.DataFrame(st.session_state['carrito'])
        if len(dfc['Moneda'].unique())>1: st.error("Error: Monedas mezcladas"); return
        mon=dfc['Moneda'].unique()[0]; st.dataframe(dfc[['Desc','Det','Unit','Total']],use_container_width=True)
        sub=dfc['Total'].sum(); eva=dfc[dfc['Ítem']=='Evaluación']['Total'].sum()
        
        cL, cR = st.columns([3,1])
        with cR:
            fee=st.checkbox(txt['fee'],False); bnk=st.number_input("Bank Fee",0.0,value=30.0 if mon=="US$" else 0.0); dsc=st.number_input(txt['discount'],0.0)
            vfee=eva*0.10 if fee else 0; tn,tv=get_impuestos(ps,sub,eva); fin=sub+vfee+tv+bnk-dsc
            st.metric(txt['grand_total'],f"{mon} {fin:,.2f}")
            
            if st.button(txt['save'],type="primary"):
                if not emp: st.error("Falta Empresa"); return
                nid=f"TP-{random.randint(1000,9999)}"; cli={'empresa':emp,'contacto':con,'email':ema}
                ext={'fee':fee,'bank':bnk,'desc':dsc,'pais':ps,'id':nid}
                pdf_b=None
                
                pr, sv = [x for x in st.session_state['carrito'] if x['Ítem']=='Evaluación'], [x for x in st.session_state['carrito'] if x['Ítem']=='Servicio']
                if ps=="Chile" and pr and sv:
                    # SPLIT CHILE
                    ex1=ext.copy(); ex1.update({'bank':0,'desc':0})
                    # Solo generamos el PDF de Servicios para el usuario en este paso,
                    # pero en un sistema real se enviarían los dos. Aquí para no complicar la UI
                    # generamos un PDF de Servicios pero con una nota visual.
                    # Lo ideal es generar el PDF que contiene los servicios primero.
                    pdf_b = generar_pdf_final(EMPRESAS['Chile_Servicios'],cli,sv,{'subtotal':sum(x['Total'] for x in sv),'fee':0,'tax_val':0,'tax_name':'','total':sum(x['Total'] for x in sv)+bnk-dsc},idi,ext,txt['quote'])
                    st.warning("ℹ️ Chile Mixto: Has mezclado Pruebas y Servicios. Legalmente requieren facturas separadas. Este PDF muestra la parte de Servicios. Deberías generar otra cotización solo para las Pruebas.")
                else:
                    ent=get_empresa(ps,st.session_state['carrito'])
                    calc={'subtotal':sub,'fee':vfee,'tax_name':tn,'tax_val':tv,'total':fin}
                    pdf_b = generar_pdf_final(ent,cli,st.session_state['carrito'],calc,idi,ext,txt['quote'])
                
                b64=base64.b64encode(pdf_b).decode('latin-1')
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Cot_{nid}.pdf" class="stButton">{txt["download"]}</a>',unsafe_allow_html=True)
                
                st.session_state['cotizaciones']=pd.concat([st.session_state['cotizaciones'], pd.DataFrame([{
                    'id':nid, 'fecha':datetime.now().strftime("%Y-%m-%d"), 'empresa':emp, 'pais':ps,
                    'total':fin, 'moneda':mon, 'estado':'Enviada', 'vendedor':ven, 'idioma':idi
                }])], ignore_index=True)
                st.session_state['carrito']=[]; st.success("Guardado Exitoso")
        with cL:
            if st.button("Limpiar"): st.session_state['carrito']=[]; st.rerun()

def modulo_seguimiento():
    st.title("🤝 Seguimiento Comercial")
    df = st.session_state['cotizaciones']
    if df.empty: st.info("No hay cotizaciones."); return
    
    col_f1, col_f2 = st.columns(2)
    filtro_vend = col_f1.multiselect("Filtrar por Ejecutivo", df['vendedor'].unique())
    df_view = df[df['vendedor'].isin(filtro_vend)] if filtro_vend else df
    df_act = df_view[df_view['estado'].isin(['Enviada', 'Aprobada', 'Rechazada'])]
    
    st.write("### Mis Cotizaciones Activas")
    for index, row in df_act.iterrows():
        with st.expander(f"{row['id']} | {row['empresa']} | {row['moneda']} {row['total']:,.2f} | {row['estado']}"):
            c1, c2, c3 = st.columns([2,2,1])
            c1.write(f"**Fecha:** {row['fecha']}"); c1.write(f"**País:** {row['pais']}")
            new_status = c2.selectbox("Estado", ["Enviada", "Aprobada", "Rechazada"], index=["Enviada", "Aprobada", "Rechazada"].index(row['estado']), key=f"st_{row['id']}")
            if new_status != row['estado']:
                if c3.button("Actualizar", key=f"btn_{row['id']}"):
                    st.session_state['cotizaciones'].at[index, 'estado'] = new_status; st.rerun()

def modulo_finanzas():
    st.title("💰 Facturación y Cobranza")
    df = st.session_state['cotizaciones']
    k1, k2 = st.columns(2)
    ready = len(df[df['estado'] == 'Aprobada'])
    k1.metric("Por Facturar (Aprobadas)", f"{ready}")
    st.markdown("---"); st.subheader("🔔 Cotizaciones Listas para Facturar")
    df_ready = df[df['estado'] == 'Aprobada']
    if df_ready.empty: st.info("No hay pendientes.")
    else:
        for index, row in df_ready.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                c1.write(f"**{row['id']}**"); c2.write(f"{row['empresa']} ({row['pais']})"); c3.write(f"**{row['moneda']} {row['total']:,.2f}**")
                if c4.button("✅ Facturar", key=f"fin_{row['id']}"):
                    st.session_state['cotizaciones'].at[index, 'estado'] = 'Facturada'; st.rerun()
                st.divider()
    st.markdown("---"); st.subheader("📚 Histórico Facturado"); st.dataframe(df[df['estado'] == 'Facturada'], use_container_width=True)

def modulo_dashboard():
    st.title("📊 Tablero de Control")
    df = st.session_state['cotizaciones']
    if df.empty: st.warning("Sin datos."); return
    st.sidebar.markdown("### Filtros Dashboard")
    f_pais = st.sidebar.multiselect("País", df['pais'].unique())
    f_vend = st.sidebar.multiselect("Ejecutivo", df['vendedor'].unique())
    df_d = df.copy()
    if f_pais: df_d = df_d[df_d['pais'].isin(f_pais)]
    if f_vend: df_d = df_d[df_d['vendedor'].isin(f_vend)]
    
    c1, c2 = st.columns(2)
    status_counts = df_d['estado'].value_counts().reset_index(); status_counts.columns = ['Estado', 'Cantidad']
    fig_pie = px.pie(status_counts, values='Cantidad', names='Estado', title='Estado Pipeline', color='Estado', color_discrete_map={'Enviada':'orange', 'Aprobada':'green', 'Facturada':'blue', 'Rechazada':'red'})
    c1.plotly_chart(fig_pie, use_container_width=True)
    
    df_sales = df_d[df_d['estado'].isin(['Aprobada', 'Facturada'])]
    if not df_sales.empty:
        sales_by_country = df_sales.groupby(['pais', 'moneda'])['total'].sum().reset_index()
        fig_bar = px.bar(sales_by_country, x='pais', y='total', color='moneda', title='Ventas por País', barmode='group')
        c2.plotly_chart(fig_bar, use_container_width=True)
    
    st.markdown("### 🔎 Detalle"); st.dataframe(df_d, use_container_width=True)

# --- NAVEGACIÓN LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=180)
    st.markdown("---")
    menu = option_menu("Menú", ["Cotizador", "Seguimiento", "Finanzas", "Dashboard"], 
        icons=['file-earmark-plus', 'clipboard-check', 'currency-dollar', 'bar-chart-fill'], 
        menu_icon="cast", default_index=0,
        styles={"nav-link-selected": {"background-color": "#003366"}})
    st.caption("v4.2 - TalentPro Enterprise")

if menu == "Cotizador": modulo_cotizador()
elif menu == "Seguimiento": modulo_seguimiento()
elif menu == "Finanzas": modulo_finanzas()
elif menu == "Dashboard": modulo_dashboard()
