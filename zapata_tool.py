import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Configuración de la página
st.set_page_config(page_title="Diseño de Zapatas Aisladas", layout="wide")

st.title("Diseño de Zapata Aislada con Despiece de Acero")
st.markdown("Cálculo estructural, verificación de presiones y generación de planos en planta y corte.")

# --- BARRA LATERAL DE ENTRADAS ---
st.sidebar.header("Datos de Entrada")

# Cargas
st.sidebar.subheader("1. Cargas y Solicitaciones")
P_servicio = st.sidebar.number_input("Carga de Servicio P (kN)", value=450.0, step=10.0)
P_ultima = P_servicio * 1.4  # Simplificación de amplificación (1.2D + 1.6L aprox)

# Geometría inicial
st.sidebar.subheader("2. Geometría propuesta")
B_prop = st.sidebar.slider("Ancho de la zapata B (m)", 1.0, 4.0, 1.8, 0.1)
L_prop = st.sidebar.slider("Largo de la zapata L (m)", 1.0, 4.0, 1.8, 0.1)
H_prop = st.sidebar.slider("Espesor de la zapata H (m)", 0.2, 1.0, 0.4, 0.05)

# Columna
c_ancho = st.sidebar.number_input("Ancho de la columna (m)", value=0.3, step=0.05)
c_largo = st.sidebar.number_input("Largo de la columna (m)", value=0.3, step=0.05)

# Materiales y Suelo
st.sidebar.subheader("3. Materiales y Suelo")
f_c = st.sidebar.selectbox("Concreto f'c (MPa)", [21, 28, 35], index=0)
f_y = st.sidebar.selectbox("Acero f_y (MPa)", [420], index=0)
q_adm = st.sidebar.number_input("Capacidad admisible del suelo (kPa)", value=180.0, step=10.0)
recubrimiento = 0.075  # 7.5 cm por norma para contacto con suelo

# --- CÁLCULOS ESTRUCTURALES ---
Área = B_prop * L_prop
presion_servicio = P_servicio / Área
presion_ultima = P_ultima / Área

# Verificación de Presión admisible
suelo_pasa = presion_servicio <= q_adm

# Cálculo del Acero de Refuerzo (Momento en la cara de la columna)
# Voladizo en el sentido B
voladizo = (B_prop - c_ancho) / 2
M_u = (presion_ultima * voladizo**2) / 2 # kNm/m

# Altura útil d
d = H_prop - recubrimiento
# Cuantía de acero simplificada (Método aproximado USD)
# As = M_u / (phi * f_y * j * d) -> asumiendo jd ≈ 0.9d, phi = 0.9
As_requerido = (M_u * 10**6) / (0.9 * f_y * 0.9 * (d * 1000)) # mm2/m
As_minimo = 0.0018 * 1000 * (H_prop * 1000) # Cuantía mínima por retracción y temperatura
As_diseno = max(As_requerido, As_minimo)

# Selección de barra comercial sugerida (#4 o #5)
# Usando varilla #5 (Diámetro = 15.9 mm, Área = 199 mm2)
area_barra = 199
num_barras_por_metro = As_diseno / area_barra
separacion = min(1.0 / num_barras_por_metro, 0.30) # Máximo 30 cm por norma

# --- INTERFAZ DE RESULTADOS ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Verificaciones de Diseño")
    
    # Métrica de Suelo
    if suelo_pasa:
        st.success(f"✔️ Presión del suelo: {presion_servicio:.2f} kPa ≤ Adm ({q_adm:.0f} kPa)")
    else:
        st.error(f"❌ Esfuerzo excesivo: {presion_servicio:.2f} kPa > Adm ({q_adm:.0f} kPa)")
        
    st.markdown("---")
    st.subheader("Resultados del Refuerzo")
    st.write(f"**Momento Último ($M_u$):** {M_u:.2f} kNm/m")
    st.write(f"**Acero Requerido ($A_s$):** {As_diseno:.1f} $mm^2/m$")
    st.info(f"**Refuerzo sugerido:** Varillas #5 (No. 5) c/ {separacion*100:.0f} cm en ambas direcciones")

with col2:
    st.subheader("Planos Estructurales Automáticos")
    tab1, tab2 = st.tabs(["Vista en Planta", "Vista en Corte (Perfil)"])
    
    # Paleta de colores industrial (Carbón y Naranja)
    plt.style.use('dark_background')
    color_naranja = '#ff5e13'
    color_gris_borde = '#2e3440'
    
    with tab1:
        # GRAFICA EN PLANTA
        fig, ax = plt.subplots(figsize=(6, 6))
        
        # Dibujar Zapata
        rect_zapata = plt.Rectangle((-B_prop/2, -L_prop/2), B_prop, L_prop, 
                                    facecolor='#1e222a', edgecolor=color_naranja, linewidth=3, label="Zapata")
        ax.add_patch(rect_zapata)
        
        # Dibujar Columna
        rect_col = plt.Rectangle((-c_ancho/2, -c_largo/2), c_ancho, c_largo, 
                                 facecolor='#4c566a', edgecolor='white', linewidth=2, label="Columna")
        ax.add_patch(rect_col)
        
        # Dibujar parrilla de acero (líneas punteadas/continuas naranjas)
        paso = separacion
        lineas_x = np.arange(-B_prop/2 + recubrimiento, B_prop/2 - recubrimiento + paso, paso)
        lineas_y = np.arange(-L_prop/2 + recubrimiento, L_prop/2 - recubrimiento + paso, paso)
        
        for lx in lineas_x:
            if -B_prop/2 < lx < B_prop/2:
                ax.plot([lx, lx], [-L_prop/2 + recubrimiento, L_prop/2 - recubrimiento], color=color_naranja, alpha=0.4, linewidth=1.5)
        for ly in lineas_y:
            if -L_prop/2 < ly < L_prop/2:
                ax.plot([-B_prop/2 + recubrimiento, B_prop/2 - recubrimiento], [ly, ly], color=color_naranja, alpha=0.4, linewidth=1.5)
        
        # Ajustes de visualización
        ax.set_xlim(-B_prop, B_prop)
        ax.set_ylim(-L_prop, L_prop)
        ax.set_aspect('equal')
        ax.set_title(f"Planta de la Zapata: {B_prop:.2f}m x {L_prop:.2f}m\nRefuerzo: #5 c/{separacion*100:.0f}cm", color='white')
        ax.grid(color='#2e3440', linestyle='--', linewidth=0.5)
        st.pyplot(fig)

    with tab2:
        # GRAFICA EN CORTE
        fig2, ax2 = plt.subplots(figsize=(7, 4))
        
        # Terreno (línea superior)
        ax2.axhline(y=H_prop + 0.3, color='#a3be8c', linestyle='-', linewidth=2, label="Nivel de Terreno")
        
        # Dibujar cuerpo de la zapata
        rect_corte_zap = plt.Rectangle((-B_prop/2, 0), B_prop, H_prop, 
                                       facecolor='#1e222a', edgecolor=color_naranja, linewidth=3)
        ax2.add_patch(rect_corte_zap)
        
        # Dibujar columna saliendo de la zapata
        rect_corte_col = plt.Rectangle((-c_ancho/2, H_prop), c_ancho, 0.5, 
                                       facecolor='#4c566a', edgecolor='white', linewidth=2)
        ax2.add_patch(rect_corte_col)
        
        # Dibujar acero inferior (Corte longitudinal y ganchos)
        ax2.plot([-B_prop/2 + recubrimiento, B_prop/2 - recubrimiento], [recubrimiento, recubrimiento], 
                 color=color_naranja, linewidth=3, label="Acero Principal")
        # Ganchos del acero
        ax2.plot([-B_prop/2 + recubrimiento, -B_prop/2 + recubrimiento], [recubrimiento, recubrimiento + 0.1], color=color_naranja, linewidth=3)
        ax2.plot([B_prop/2 - recubrimiento, B_prop/2 - recubrimiento], [recubrimiento, recubrimiento + 0.1], color=color_naranja, linewidth=3)
        
        # Configuración de ejes
        ax2.set_xlim(-B_prop, B_prop)
        ax2.set_ylim(-0.1, H_prop + 0.6)
        ax2.set_aspect('equal')
        ax2.set_title(f"Corte Estructural (Espesor H = {H_prop:.2f}m)", color='white')
        ax2.grid(color='#2e3440', linestyle='--', linewidth=0.5)
        st.pyplot(fig2)