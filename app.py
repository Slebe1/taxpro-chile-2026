import streamlit as st
import pandas as pd
import textwrap

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(
    page_title="TaxPro Chile 2026", 
    layout="wide", 
    page_icon="🍊",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS "CLEAN & ORANGE" ---
st.markdown("""
<style>
    .stApp { background-color: #FAFAFA; color: #1D1D1F; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    header, footer, #MainMenu {visibility: hidden;}
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] { background-color: #FFFFFF; padding: 5px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; gap: 5px; }
    .stTabs [data-baseweb="tab"] { height: 40px; border-radius: 8px; color: #86868B; font-weight: 500; border: none; }
    .stTabs [aria-selected="true"] { background-color: #FFF0E0; color: #FF9500; font-weight: 600; }
    
    /* TARJETAS (CARDS) */
    .clean-card { background-color: #FFFFFF; border-radius: 20px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); border: 1px solid #F2F2F7; }
    
    /* TYPOGRAPHY */
    .step-number { color: #FF9500; font-weight: 700; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    .card-title { color: #1D1D1F; font-size: 18px; font-weight: 600; margin-bottom: 15px; }
    
    .row-item { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 15px; color: #555; }
    .row-item.bold { font-weight: 600; color: #1D1D1F; border-top: 1px solid #E5E5EA; padding-top: 8px; margin-top: 8px; }
    .row-item.sub { font-size: 13px; color: #888; padding-left: 10px; }
    
 
    /* RESULTADO FINAL */
    .result-box { background: #FFF8F0; border-left: 6px solid #FF9500; padding: 30px; border-radius: 15px; margin-top: 20px; }
    
    /* INPUTS */
    div.stButton > button:first-child { background: linear-gradient(135deg, #FF9500 0%, #FF5E00 100%); color: white; border-radius: 14px; border: none; font-size: 17px; font-weight: 600; padding: 14px 24px; width: 100%; box-shadow: 0 4px 12px rgba(255, 94, 0, 0.2); transition: transform 0.2s ease; }
    div.stButton > button:first-child:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(255, 94, 0, 0.3); }
    .stNumberInput input, div[data-baseweb="select"] > div { background-color: #FFFFFF !important; border: 1px solid #E5E5EA !important; border-radius: 10px; color: #1D1D1F; }
    
    h1 { color: #1D1D1F !important; letter-spacing: -1px !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. MOTOR TRIBUTARIO (AUDITADO) ---

def calcular_impuesto_tabla(base_imponible, valor_uta, tabla_igc):
    base_uta = base_imponible / valor_uta
    factor, rebaja = 0, 0
    for tramo in tabla_igc:
        if tramo[0] < base_uta <= tramo[1]:
            factor, rebaja = tramo[2], tramo[3] * valor_uta
            break
    return max(0, (base_imponible * factor) - rebaja)

def formato_pesos(valor):
    return f"${valor:,.0f}".replace(",", ".")

def procesar_calculo(datos):
    # NOTA AUDITOR: Tabla IGC Vigente para AT 2026
    TABLA_IGC = [(0, 13.5, 0, 0), (13.5, 30, 0.04, 0.54), (30, 50, 0.08, 1.74), 
                 (50, 70, 0.135, 4.49), (70, 90, 0.23, 11.14), (90, 120, 0.304, 17.8), 
                 (120, 310, 0.35, 23.32), (310, 999999, 0.40, 38.82)]
    
    # --- PASO 1: INGRESOS BRUTOS ---
ingresos_brutos = datos['sueldo'] + datos['hon_bruto'] + datos['retiros'] + datos['otros']
    
    # --- PASO 2: DEPURACIÓN Y BASES ---

    # A. Previsión (Ingeniería Inversa)
    # NOTA AUDITOR: Se actualiza tope imponible a 87.8 UF para 2026
    tope_anual_pesos = 87.8 * 12 * datos['uf'] 
    
    # Brutear sueldo para estimar cupo usado
    sueldo_imponible_estimado = datos['sueldo'] / 0.815
    cupo_usado_sueldo = min(sueldo_imponible_estimado, tope_anual_pesos)
    cupo_disponible_honorarios = max(0, tope_anual_pesos - cupo_usado_sueldo)
    base_cotizable_hon = min(datos['hon_bruto'] * 0.8, cupo_disponible_honorarios)
    
    # Tasas
    tasa_seguros = 0.03 # Aprox SIS+Mutual+SANNA
    tasa_salud = 0.07   
    tasa_afp_base = 0.10 
    tasa_comision = datos['afp_comision'] / 100 
    
    # Costos
    costo_seguros = base_cotizable_hon * tasa_seguros
    if datos['cobertura'] == 'Total':
        costo_variable = base_cotizable_hon * (tasa_salud + tasa_afp_base + tasa_comision)
    else:
        factor_parcial = datos['factor_parcial'] / 100 
        base_parcial = base_cotizable_hon * factor_parcial
        costo_variable = base_parcial * (tasa_salud + tasa_afp_base + tasa_comision)
        
    deuda_previsional = costo_seguros + costo_variable
    
    # B. Gastos Honorarios
    tope_gp = 15 * datos['uta']
    gasto_hon = min(datos['hon_bruto']*0.3, tope_gp) if datos['usa_gp'] else datos['gasto_real']
    
    # C. Base Honorarios Neta
    hon_neto = datos['hon_bruto'] - gasto_hon - deuda_previsional
    
    # D. Incremento Empresa (Gross Up)
    inc = 0
    if datos['retiros'] > 0:
        tef = datos['tasa_emp'] / 100
        inc = datos['retiros'] * (tef / (1 - tef))
        
    # E. Renta Bruta Global (Base preliminar)
    rbg = datos['sueldo'] + hon_neto + (datos['retiros'] + inc) + datos['otros']
    
    # F. Beneficios (Rebajas a la Base)
    
    # NOTA AUDITOR (CORRECCIÓN): El tope de 90/150 UTA para intereses hipotecarios
    # se debe calcular sobre la renta ANTES de rebajar el APV.
    # Usamos 'rbg' que es la suma de flujos.
    rbg_para_tope_hip = rbg # Definición explícita para la auditoría
    rbg_uta_ref = rbg_para_tope_hip / datos['uta']
    
    top_int = 8 * datos['uta']
    reb_hip = 0
    
    # Lógica de tramos 55 bis
    if rbg_uta_ref <= 90: 
        reb_hip = min(datos['hipo'], top_int)
    elif rbg_uta_ref <= 150: 
        reb_hip = min(datos['hipo'], top_int) * ((150 - rbg_uta_ref)/60)
    else:
        reb_hip = 0
        
    reb_apv = min(datos['apv'], 600 * datos['uf'])
    
    # BASE IMPONIBLE FINAL (Aquí sí se resta el APV)
    base_imponible = max(0, rbg - reb_hip - reb_apv)
    
    # --- PASO 3: IMPUESTOS ---
    # Lógica de tramos manual para sacar la tasa marginal
    base_uta = base_imponible / datos['uta']
    factor, rebaja = 0, 0
    tasa_marginal = 0 
    
    for tramo in TABLA_IGC:
        if tramo[0] < base_uta <= tramo[1]:
            factor, rebaja = tramo[2], tramo[3] * datos['uta']
            tasa_marginal = factor
            break
            
    imp_determinado = max(0, (base_imponible * factor) - rebaja)
    
    # Restitución (Débito) - Solo si NO es ProPyme
    restit = (inc * 0.35) if datos['regimen'] != 'ProPyme' else 0
    impuesto_final = imp_determinado + restit
    
    # --- PASO 4: CRÉDITOS (LO QUE YA PAGASTE) ---
    cred_iusc = calcular_impuesto_tabla(datos['sueldo'], datos['uta'], TABLA_IGC) if datos['auto_iusc'] else datos['man_iusc']
    cred_emp = inc
    retencion_hon = (datos['hon_bruto'] * (datos['tasa_ret']/100)) if datos['auto_ret'] else datos['man_ret']
    
    # --- PASO 5: SALDO ---
    # Saldo Honorarios (La devolución de retención que sobra tras pagar previsión)
    saldo_hon_liquido = 0
    if datos['flag_retencion_total']:
        saldo_hon_liquido = retencion_hon - deuda_previsional
        
    # Cálculo Final de Bolsillo
    saldo_bolsillo = impuesto_final - (cred_iusc + cred_emp + saldo_hon_liquido)

    return {
        "ingresos_brutos": ingresos_brutos,
        "desglose_ingresos": (datos['sueldo'], datos['hon_bruto'], datos['retiros'], datos['otros']),
        "descuentos_total": gasto_hon + deuda_previsional + reb_hip + reb_apv,
        "desglose_descuentos": (gasto_hon, deuda_previsional, reb_hip, reb_apv),
        "base_imponible": base_imponible,
        "impuesto_final": impuesto_final,
        "tasa_marginal": tasa_marginal,
        "creditos_total": cred_iusc + cred_emp + saldo_hon_liquido,
        "desglose_creditos": (cred_iusc, cred_emp, saldo_hon_liquido), 
        "saldo_bolsillo": saldo_bolsillo,
        "retencion_hon_bruta": retencion_hon, 
        "deuda_previsional": deuda_previsional
    }

# --- 4. INTERFAZ VISUAL ---

st.markdown("<h1 style='text-align: left; margin-bottom: 5px; color:#1D1D1F;'>Tax<span style='color:#FF9500'>Pro</span> Chile</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #86868B; margin-bottom: 30px; font-size: 16px;'>Simulador AT 2026 (Auditado)</p>", unsafe_allow_html=True)

col_inputs, col_blank, col_summary = st.columns([1.1, 0.1, 1.2])

with col_inputs:
    tab1, tab2, tab3, tab4 = st.tabs(["1. Ingresos", "2. Empresa", "3. Rebajas", "4. Pagos"])
    
    with tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        sueldo = st.number_input("Sueldos Tributables (Anual)", value=0, step=500000)
        hon = st.number_input("Honorarios Brutos (Anual)", value=12000000, step=500000)
        
        if hon > 0:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.caption("Configuración Previsional 2026")
            c_cob, c_afp = st.columns(2)
            cobertura = c_cob.selectbox("Cobertura", ["Parcial", "Total"], index=0)
            tasas_afp = {"Modelo (0.58%)": 0.58, "Uno (0.49%)": 0.49, "Habitat (1.27%)": 1.27, "Cuprum (1.44%)": 1.44, "Provida (1.45%)": 1.45, "Capital (1.44%)": 1.44, "PlanVital (1.16%)": 1.16}
            nom_afp = c_afp.selectbox("AFP", list(tasas_afp.keys()), index=0)
            afp_comision = tasas_afp[nom_afp]
            st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)
            factor_parcial = st.slider("Factor Cobertura %", min_value=47, max_value=100, value=67, help="Proyección legal 2026: 67%")
            flag_ret = st.toggle("¿Tiene Retención Total?", value=True)
        else:
            cobertura = "Parcial"; afp_comision = 0.58; factor_parcial = 67; flag_ret = True

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        gp = st.toggle("Aplicar Gasto Presunto (30%)", value=True)
        g_real = 0 if gp else st.number_input("Gastos Reales", value=0)
        
    with tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        ret = st.number_input("Retiros Efectivos", value=0, step=500000)
        c1, c2 = st.columns(2)
        reg = c1.selectbox("Régimen", ["ProPyme", "Semi Integrado"])
        # NOTA AUDITOR: Tasa ProPyme ajustada a 12.5% por defecto
        tasa_defecto = 12.5 if "ProPyme" in reg else 27.0
        tasa = c2.number_input("Tasa TEF %", value=tasa_defecto)
        otros = st.number_input("Otros Ingresos", value=0)

    with tab3:
        st.markdown("<br>", unsafe_allow_html=True)
        hipo = st.number_input("Intereses Hipotecarios (55 bis)", value=0)
        apv = st.number_input("APV Régimen B", value=0)
        
    with tab4:
        st.markdown("<br>", unsafe_allow_html=True)
        auto_iusc = st.toggle("Auto-Calcular IUSC", value=True)
        man_iusc = 0 if auto_iusc else st.number_input("IUSC Manual", value=0)
        st.divider()
        auto_ret = st.toggle("Auto-Calcular Retención", value=True)
        man_ret = 0 if auto_ret else st.number_input("Retención Manual", value=0)
        with st.expander("⚙️ Parámetros"):
            uta = st.number_input("Valor UTA", value=834000)
            uf = st.number_input("Valor UF", value=39720)
            # NOTA AUDITOR: Tasa Retención 2026 fijada en 15.25%
            tasa_ret = st.number_input("Tasa Retención %", value=15.25)

    st.markdown("<br>", unsafe_allow_html=True)
    calcular = st.button("CALCULAR HISTORIA ➔")

# --- SECCIÓN DE RESULTADOS (HISTORIA VISUAL) ---
with col_summary:
    if calcular:
        data = {
            'uta': uta, 'uf': uf, 'sueldo': sueldo, 'hon_bruto': hon, 'usa_gp': gp, 'gasto_real': g_real,
            'retiros': ret, 'regimen': reg, 'tasa_emp': tasa, 'otros': otros,
            'hipo': hipo, 'apv': apv, 'auto_iusc': auto_iusc, 'man_iusc': man_iusc,
            'auto_ret': auto_ret, 'man_ret': man_ret, 'tasa_ret': tasa_ret,
            'cobertura': cobertura, 'afp_comision': afp_comision, 
            'flag_retencion_total': flag_ret, 'factor_parcial': factor_parcial
        }
        res = procesar_calculo(data)
        
        # --- TARJETA 1: TUS INGRESOS ---
        st.markdown(f"""
        <div class="clean-card">
            <div class="step-number">PASO 1: TU AÑO FINANCIERO</div>
            <div class="card-title">¿Cuánto ganaste en total?</div>
            <div class="row-item"><span>Sueldos:</span> <span>{formato_pesos(res['desglose_ingresos'][0])}</span></div>
            <div class="row-item"><span>Honorarios Brutos:</span> <span>{formato_pesos(res['desglose_ingresos'][1])}</span></div>
            <div class="row-item"><span>Retiros/Dividendos:</span> <span>{formato_pesos(res['desglose_ingresos'][2])}</span></div>
            <div class="row-item"><span>Otros Ingresos:</span> <span>{formato_pesos(res['desglose_ingresos'][3])}</span></div>
            <div class="row-item bold"><span>TOTAL INGRESOS BRUTOS</span> <span>{formato_pesos(res['ingresos_brutos'])}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- TARJETA 2: DEDUCCIONES ---
        st.markdown(f"""
        <div class="clean-card">
            <div class="step-number">PASO 2: LIMPIEZA DE LA BASE</div>
            <div class="card-title">¿Qué descontamos para bajar el impuesto?</div>
            <div class="row-item"><span>(-) Gastos Honorarios:</span> <span style="color:#FF3B30">-{formato_pesos(res['desglose_descuentos'][0])}</span></div>
            <div class="row-item"><span>(-) Deuda Previsional (AFP/Salud):</span> <span style="color:#FF3B30">-{formato_pesos(res['desglose_descuentos'][1])}</span></div>
            <div class="row-item"><span>(-) Beneficio Hipotecario:</span> <span style="color:#34C759">-{formato_pesos(res['desglose_descuentos'][2])}</span></div>
            <div class="row-item"><span>(-) Beneficio APV:</span> <span style="color:#34C759">-{formato_pesos(res['desglose_descuentos'][3])}</span></div>
            <div class="row-item bold"><span>BASE IMPONIBLE (REAL)</span> <span>{formato_pesos(res['base_imponible'])}</span></div>
            <div class="row-item sub">Sobre este monto final se calcula tu impuesto.</div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- TARJETA 3: LA BALANZA (ACTUALIZADA CON TRAMO) ---
        saldo_hon = res['desglose_creditos'][2]
        color_hon = "#34C759" if saldo_hon >= 0 else "#FF3B30"
        signo_hon = "+" if saldo_hon >= 0 else ""
        
        # Formateo del tramo
        pct_tramo = res['tasa_marginal'] * 100
        if pct_tramo == 0:
            texto_tramo = "TRAMO EXENTO (0%)"
            estilo_tramo = "background-color: #E5E5EA; color: #1D1D1F;"
        else:
            texto_tramo = (
                f"TRAMO DEL {pct_tramo:.1f}%"
                if pct_tramo % 1 != 0
                else f"TRAMO DEL {int(pct_tramo)}%"
            )
            estilo_tramo = "background-color: #FFF0E0; color: #FF9500; border: 1px solid #FFDbb3;"
        
        # Construir el HTML sin sangría (usando textwrap.dedent)
        balanza_html = textwrap.dedent(f"""
        <div class="clean-card">
            <div class="step-number">PASO 3: LA BALANZA</div>
            <div class="card-title">Impuesto vs. Lo que ya tienes</div>
            <div style="display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 11px;
                 font-weight: 700; letter-spacing: 0.5px; margin-bottom: 8px; {estilo_tramo}">
                {texto_tramo}
            </div>
            <div class="row-item bold" style="font-size:16px; margin-bottom:15px; margin-top:0px;">
                <span>IMPUESTO ANUAL DETERMINADO</span>
                <span style="color:#1D1D1F">{formato_pesos(res['impuesto_final'])}</span>
            </div>
            <div style="background-color:#F5F5F7; padding:10px; border-radius:10px;">
                <div style="font-size:12px; color:#888; font-weight:600; margin-bottom:5px;">TUS CRÉDITOS (A FAVOR)</div>
                <div class="row-item"><span>Impuesto Único (Sueldos):</span> <span>-{formato_pesos(res['desglose_creditos'][0])}</span></div>
                <div class="row-item"><span>Crédito Empresa:</span> <span>-{formato_pesos(res['desglose_creditos'][1])}</span></div>
                <div class="row-item">
                    <span>Saldo Líquido Retenciones:</span>
                    <span style="color:{color_hon}; font-weight:600">{signo_hon}{formato_pesos(saldo_hon)}</span>
                </div>
                <div class="row-item sub" style="line-height:1.2; margin-top:5px;">
                    *Tu retención ({formato_pesos(res['retencion_hon_bruta'])}) pagó tu previsión ({formato_pesos(res['deuda_previsional'])}) y sobró {formato_pesos(saldo_hon)}.
                </div>
            </div>
        </div>
        """)
        
        # Mostrar la tarjeta con Markdown
        st.markdown(balanza_html, unsafe_allow_html=True)

        
        
        # --- TARJETA 4: FINAL ---
        if res['saldo_bolsillo'] <= 0:
            color_res = "#34C759"; texto_res = "TE DEVUELVEN"; signo = ""
        else:
            color_res = "#FF3B30"; texto_res = "TIENES QUE PAGAR"; signo = ""
    
        st.markdown(f"""
        <div class="result-box">
            <div class="step-number">RESULTADO FINAL</div>
            <div style="font-size: 42px; font-weight: 700; color: {color_res}; letter-spacing: -1px; margin-top: 5px;">
                {signo}{formato_pesos(abs(res['saldo_bolsillo']))}
            </div>
            <div style="color: #1D1D1F; font-weight: 600; font-size: 18px; margin-top: 5px;">
                {texto_res}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    else:
             st.info("Ingresa tus datos en el panel izquierdo para ver tu historia financiera.")
