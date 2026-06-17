import math

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from slope_core import (
    calculate_slices,
    circle_lower_y,
    find_critical_circle,
    ground_y,
    recommended_slice_count,
)


ORANGE = "#ff4b1f"
BG = "#111513"
PANEL = "#171c19"
TEXT = "#f5f4ef"
MUTED = "#a7ada6"
GREEN = "#2ebc66"
BLUE = "#52b7ff"


def to_kn_units(values, unit_system):
    if unit_system == "Toneladas metricas (t/m2, t/m3)":
        factor = 9.80665
        converted = dict(values)
        for key in ("cohesion", "gamma", "gamma_sat", "gamma_water"):
            converted[key] = values[key] * factor
        return converted, factor, "t/m", "t/m2", "t/m3"
    return dict(values), 1.0, "kN/m", "kPa", "kN/m3"


def from_kn(value, factor):
    return value / factor


def draw_slope(values, slices, roots, fellenius, bishop):
    height = values["height"]
    slope_angle = values["slope_angle"]
    cx = values["cx"]
    cy = values["cy"]
    radius = values["radius"]
    water_y = values["water_y"]
    crest_x = height / math.tan(math.radians(slope_angle))

    x_candidates = [cx - radius, cx + radius, -1.5, crest_x + height * 1.2]
    y_candidates = [0, height, water_y, cy - radius, cy + radius * 0.12]
    xmin, xmax = min(x_candidates), max(x_candidates)
    ymin, ymax = min(y_candidates), max(y_candidates)

    fig, ax = plt.subplots(figsize=(11, 5.8), facecolor=BG)
    ax.set_facecolor("#20272c")
    ax.grid(color="#354039", linewidth=0.6)

    ground_x = [xmin, 0, crest_x, xmax]
    ground_y_vals = [0, 0, height, height]
    ax.fill_between(ground_x, [ymin] * 4, ground_y_vals, color="#101612", alpha=1.0)
    ax.plot([xmin, 0, crest_x, xmax], [0, 0, height, height], color=TEXT, linewidth=3)

    if ymin < water_y < ymax:
        ax.axhspan(ymin, water_y, color="#143040", alpha=0.35)
        ax.axhline(water_y, color=BLUE, linestyle=(0, (8, 5)), linewidth=2)
        ax.text(xmin + (xmax - xmin) * 0.03, water_y + height * 0.03, f"NAF = {water_y:.2f} m", color=BLUE, weight="bold")

    arc_x, arc_y = [], []
    for i in range(220):
        x = cx - radius + 2 * radius * i / 219
        y = circle_lower_y(x, cx, cy, radius)
        if y is not None:
            arc_x.append(x)
            arc_y.append(y)
    ax.plot(arc_x, arc_y, color=GREEN, linestyle=(0, (6, 4)), linewidth=2)

    ax.scatter([cx], [cy], color=ORANGE, s=45, zorder=5)
    ax.text(cx, cy + height * 0.05, f"Centro ({cx:.2f}, {cy:.2f})", color=ORANGE, ha="center", weight="bold")

    if roots:
        ax.plot([cx, roots[0]], [cy, ground_y(roots[0], height, slope_angle)], color=GREEN, linestyle="--")
        ax.text((cx + roots[0]) / 2, (cy + ground_y(roots[0], height, slope_angle)) / 2, f"R = {radius:.2f} m", color=GREEN, weight="bold")

    for s in slices:
        top_l = ground_y(s.x_left, height, slope_angle)
        top_r = ground_y(s.x_right, height, slope_angle)
        bot_l = circle_lower_y(s.x_left, cx, cy, radius)
        bot_r = circle_lower_y(s.x_right, cx, cy, radius)
        bot_m = circle_lower_y(s.x_mid, cx, cy, radius)
        if bot_l is None or bot_r is None or bot_m is None:
            continue
        ax.plot([s.x_left, s.x_left], [bot_l, top_l], color="#4d76ff", linewidth=0.9)
        ax.plot([s.x_right, s.x_right], [bot_r, top_r], color="#4d76ff", linewidth=0.9)
        ax.plot([cx, s.x_mid], [cy, bot_m], color="#d22b2b", linewidth=0.7, alpha=0.7)
        ax.text(s.x_mid, bot_m - height * 0.035, str(s.number), color=MUTED, ha="center", va="top", fontsize=8, weight="bold")
        if len(slices) <= 14:
            ax.text(s.x_mid, bot_m - height * 0.09, f"a={s.alpha_deg:.1f} deg", color="#89a7ff", ha="center", fontsize=7)

    ax.annotate(f"H = {height:.2f} m", xy=(0, height), xytext=(-height * 0.25, height / 2), color=ORANGE, arrowprops=dict(arrowstyle="<->", color=ORANGE), ha="center", va="center")
    ax.annotate(f"{crest_x:.2f} m", xy=(crest_x, 0), xytext=(crest_x / 2, ymin + (ymax - ymin) * 0.08), color=ORANGE, arrowprops=dict(arrowstyle="<->", color=ORANGE), ha="center")
    ax.text(crest_x * 0.25, height * 0.15, f"beta = {slope_angle:.1f} deg", color=ORANGE, weight="bold")
    if roots:
        ax.annotate(f"Ancho falla = {roots[-1] - roots[0]:.2f} m", xy=(roots[-1], 0), xytext=((roots[0] + roots[-1]) / 2, ymin + (ymax - ymin) * 0.16), color=ORANGE, arrowprops=dict(arrowstyle="<->", color=ORANGE), ha="center")

    ax.set_title("Talud, NAF, circulo de falla y dovelas", color=TEXT, loc="left", fontweight="bold")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color("#354039")
    ax.set_xlabel("x (m)", color=MUTED)
    ax.set_ylabel("y (m)", color=MUTED)
    return fig


st.set_page_config(page_title="Estabilidad de taludes", layout="wide")
st.markdown(
    f"""
    <style>
    .stApp {{ background: {BG}; color: {TEXT}; }}
    section[data-testid="stSidebar"] {{ background: {PANEL}; }}
    .metric-card {{ background:{PANEL}; border:1px solid #2b332e; padding:18px; border-radius:8px; }}
    .metric-label {{ color:{ORANGE}; font-size:13px; font-weight:800; }}
    .metric-value {{ color:{TEXT}; font-size:34px; font-weight:900; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Calculadora de estabilidad de taludes")
st.caption("Fellenius y Bishop simplificado con nivel freatico y unidades seleccionables.")

with st.sidebar:
    st.header("Datos")
    unit_system = st.selectbox("Sistema de unidades", ["SI (kPa, kN/m3)", "Toneladas metricas (t/m2, t/m3)"])
    stress_unit = "kPa" if unit_system.startswith("SI") else "t/m2"
    gamma_unit = "kN/m3" if unit_system.startswith("SI") else "t/m3"

    cohesion = st.number_input(f"c' cohesion ({stress_unit})", min_value=0.0, value=14.72 if unit_system.startswith("SI") else 1.0, step=0.1)
    phi = st.number_input("Phi efectivo (grados)", min_value=0.0, max_value=60.0, value=15.0, step=0.5)
    gamma = st.number_input(f"Gamma sobre NAF ({gamma_unit})", min_value=0.01, value=18.0 if unit_system.startswith("SI") else 1.8, step=0.1)
    gamma_sat = st.number_input(f"Gamma saturado ({gamma_unit})", min_value=0.01, value=19.12 if unit_system.startswith("SI") else 1.9, step=0.1)
    gamma_water = st.number_input(f"Gamma agua ({gamma_unit})", min_value=0.01, value=9.81 if unit_system.startswith("SI") else 1.0, step=0.05)

    height = st.number_input("Altura H (m)", min_value=0.1, value=12.0, step=0.5)
    slope_angle = st.number_input("Angulo del talud beta (grados)", min_value=1.0, max_value=89.0, value=60.0, step=1.0)
    water_y = st.number_input("Nivel freatico Y (m)", value=0.0, step=0.5)

    auto_circle = st.checkbox("Buscar circulo critico automaticamente", value=True)
    auto_slices = st.checkbox("Numero de dovelas automatico", value=True)
    slices = st.number_input("Numero de dovelas", min_value=2, max_value=80, value=10, step=1, disabled=auto_slices)

    cx = st.number_input("Centro X (m)", value=9.0, step=0.5, disabled=auto_circle)
    cy = st.number_input("Centro Y (m)", value=14.0, step=0.5, disabled=auto_circle)
    radius = st.number_input("Radio R (m)", min_value=0.1, value=14.0, step=0.5, disabled=auto_circle)

raw_values = {
    "cohesion": cohesion,
    "phi": phi,
    "gamma": gamma,
    "gamma_sat": gamma_sat,
    "gamma_water": gamma_water,
    "water_y": water_y,
    "height": height,
    "slope_angle": slope_angle,
    "cx": cx,
    "cy": cy,
    "radius": radius,
    "slices": int(slices),
}

values, conversion_factor, force_unit, stress_unit, gamma_unit = to_kn_units(raw_values, unit_system)

if auto_circle:
    cx_auto, cy_auto, radius_auto, n_auto = find_critical_circle(values)
    values.update({"cx": cx_auto, "cy": cy_auto, "radius": radius_auto})
    if auto_slices:
        values["slices"] = n_auto
elif auto_slices:
    recommended = recommended_slice_count(values["height"], values["slope_angle"], values["cx"], values["cy"], values["radius"])
    if recommended:
        values["slices"] = recommended

try:
    slices_data, roots, fellenius, bishop = calculate_slices(values)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>FELLENIUS</div><div class='metric-value'>F.S. {fellenius:.3f}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>BISHOP SIMPLIFICADO</div><div class='metric-value'>F.S. {bishop:.3f}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>CIRCULO / DOVELAS</div><div class='metric-value'>{values['slices']} dovelas</div></div>", unsafe_allow_html=True)

st.pyplot(draw_slope(values, slices_data, roots, fellenius, bishop), clear_figure=True)

st.subheader("Tabla por dovela")
table = pd.DataFrame(
    [
        {
            "Dovela": s.number,
            "Area (m2)": s.area,
            f"W ({force_unit})": from_kn(s.weight, conversion_factor),
            f"uL ({force_unit})": from_kn(s.pore_force, conversion_factor),
            "alpha (deg)": s.alpha_deg,
            "L arco (m)": s.base_length,
            f"N' ({force_unit})": from_kn(s.effective_normal, conversion_factor),
            f"T ({force_unit})": from_kn(s.shear, conversion_factor),
        }
        for s in slices_data
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)

with st.expander("Valores usados"):
    display_values = dict(values)
    for key in ("cohesion", "gamma", "gamma_sat", "gamma_water"):
        display_values[key] = from_kn(display_values[key], conversion_factor)
    st.json(display_values)
