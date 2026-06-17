import math

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
    width_px, height_px = 1100, 580
    pad = 56

    def sx(x):
        return pad + (x - xmin) / max(1e-9, xmax - xmin) * (width_px - 2 * pad)

    def sy(y):
        return height_px - pad - (y - ymin) / max(1e-9, ymax - ymin) * (height_px - 2 * pad)

    def point_list(points):
        return " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)

    def line(x1, y1, x2, y2, color, stroke=2, dash="", marker=""):
        return (
            f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-dasharray="{dash}" {marker}/>'
        )

    def text(x, y, value, color=TEXT, size=13, anchor="middle", weight="700"):
        return (
            f'<text x="{sx(x):.1f}" y="{sy(y):.1f}" fill="{color}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}" font-family="Arial, sans-serif">{value}</text>'
        )

    elements = [
        f'<svg viewBox="0 0 {width_px} {height_px}" width="100%" height="580" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        f'<marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="{ORANGE}"/></marker>',
        "</defs>",
        f'<rect x="0" y="0" width="{width_px}" height="{height_px}" rx="8" fill="#20272c"/>',
    ]

    for i in range(7):
        gx = pad + i * (width_px - 2 * pad) / 6
        gy = pad + i * (height_px - 2 * pad) / 6
        elements.append(f'<line x1="{gx:.1f}" y1="{pad}" x2="{gx:.1f}" y2="{height_px - pad}" stroke="#354039" stroke-width="1"/>')
        elements.append(f'<line x1="{pad}" y1="{gy:.1f}" x2="{width_px - pad}" y2="{gy:.1f}" stroke="#354039" stroke-width="1"/>')

    ground_poly = [(xmin, ymin), (xmin, ground_y(xmin, height, slope_angle)), (0, 0), (crest_x, height), (xmax, height), (xmax, ymin)]
    elements.append(f'<polygon points="{point_list(ground_poly)}" fill="#101612"/>')
    elements.append(f'<polyline points="{point_list([(xmin, 0), (0, 0), (crest_x, height), (xmax, height)])}" fill="none" stroke="{TEXT}" stroke-width="4"/>')

    if ymin < water_y < ymax:
        elements.append(
            f'<rect x="{sx(xmin):.1f}" y="{sy(water_y):.1f}" width="{sx(xmax) - sx(xmin):.1f}" '
            f'height="{sy(ymin) - sy(water_y):.1f}" fill="#143040" opacity="0.45"/>'
        )
        elements.append(line(xmin, water_y, xmax, water_y, BLUE, 2, "8 6"))
        elements.append(text(xmin + (xmax - xmin) * 0.08, water_y + height * 0.05, f"NAF = {water_y:.2f} m", BLUE, 13, "start"))

    arc_points = []
    for i in range(220):
        x = cx - radius + 2 * radius * i / 219
        y = circle_lower_y(x, cx, cy, radius)
        if y is not None:
            arc_points.append((x, y))
    elements.append(f'<polyline points="{point_list(arc_points)}" fill="none" stroke="{GREEN}" stroke-width="3" stroke-dasharray="8 6"/>')
    elements.append(f'<circle cx="{sx(cx):.1f}" cy="{sy(cy):.1f}" r="5" fill="{ORANGE}"/>')
    elements.append(text(cx, cy + height * 0.06, f"Centro ({cx:.2f}, {cy:.2f})", ORANGE, 13))

    if roots:
        root_y = ground_y(roots[0], height, slope_angle)
        elements.append(line(cx, cy, roots[0], root_y, GREEN, 2, "6 5"))
        elements.append(text((cx + roots[0]) / 2, (cy + root_y) / 2 + height * 0.04, f"R = {radius:.2f} m", GREEN, 13))

    for s in slices:
        top_l = ground_y(s.x_left, height, slope_angle)
        top_r = ground_y(s.x_right, height, slope_angle)
        bot_l = circle_lower_y(s.x_left, cx, cy, radius)
        bot_r = circle_lower_y(s.x_right, cx, cy, radius)
        bot_m = circle_lower_y(s.x_mid, cx, cy, radius)
        if bot_l is None or bot_r is None or bot_m is None:
            continue
        elements.append(line(s.x_left, bot_l, s.x_left, top_l, "#4d76ff", 1))
        elements.append(line(s.x_right, bot_r, s.x_right, top_r, "#4d76ff", 1))
        elements.append(line(cx, cy, s.x_mid, bot_m, "#d22b2b", 1))
        elements.append(text(s.x_mid, bot_m - height * 0.04, str(s.number), MUTED, 12))
        if len(slices) <= 14:
            elements.append(text(s.x_mid, bot_m - height * 0.1, f"a={s.alpha_deg:.1f} deg", "#89a7ff", 10))

    elements.append(line(0, 0, 0, height, ORANGE, 2, "", 'marker-start="url(#arrow)" marker-end="url(#arrow)"'))
    elements.append(text(-height * 0.08, height / 2, f"H = {height:.2f} m", ORANGE, 13, "end"))
    elements.append(line(0, 0, crest_x, 0, ORANGE, 2, "", 'marker-start="url(#arrow)" marker-end="url(#arrow)"'))
    elements.append(text(crest_x / 2, ymin + (ymax - ymin) * 0.08, f"{crest_x:.2f} m", ORANGE, 13))
    elements.append(text(crest_x * 0.25, height * 0.15, f"beta = {slope_angle:.1f} deg", ORANGE, 13))
    if roots:
        elements.append(line(roots[0], 0, roots[-1], 0, ORANGE, 2, "", 'marker-start="url(#arrow)" marker-end="url(#arrow)"'))
        elements.append(text((roots[0] + roots[-1]) / 2, ymin + (ymax - ymin) * 0.17, f"Ancho falla = {roots[-1] - roots[0]:.2f} m", ORANGE, 13))

    elements.append(f'<text x="{pad}" y="28" fill="{TEXT}" font-size="16" font-weight="900" font-family="Arial, sans-serif">Talud, NAF, circulo de falla y dovelas</text>')
    elements.append("</svg>")
    return "\n".join(elements)


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

st.markdown(draw_slope(values, slices_data, roots, fellenius, bishop), unsafe_allow_html=True)

st.subheader("Tabla por dovela")
table = [
    {
        "Dovela": s.number,
        "Area (m2)": round(s.area, 3),
        f"W ({force_unit})": round(from_kn(s.weight, conversion_factor), 3),
        f"uL ({force_unit})": round(from_kn(s.pore_force, conversion_factor), 3),
        "alpha (deg)": round(s.alpha_deg, 3),
        "L arco (m)": round(s.base_length, 3),
        f"N' ({force_unit})": round(from_kn(s.effective_normal, conversion_factor), 3),
        f"T ({force_unit})": round(from_kn(s.shear, conversion_factor), 3),
    }
    for s in slices_data
]
st.dataframe(table, use_container_width=True, hide_index=True)

with st.expander("Valores usados"):
    display_values = dict(values)
    for key in ("cohesion", "gamma", "gamma_sat", "gamma_water"):
        display_values[key] = from_kn(display_values[key], conversion_factor)
    st.json(display_values)
