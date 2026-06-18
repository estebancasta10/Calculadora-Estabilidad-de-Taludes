import math

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from report_utils import AUTHOR, add_streamlit_signature, build_technical_pdf


ORANGE = "#ff4b1f"
BG = "#111513"
PANEL = "#171c19"
TEXT = "#f5f4ef"
MUTED = "#a7ada6"
GREEN = "#2ebc66"
BLUE = "#52b7ff"
RED = "#ff5f56"

STANDARD_LOADS_KN = {
    2.5: 13.24,
    5.0: 19.96,
}

DEFAULT_POINTS = [
    {"Grupo": "Muestra 1", "Penetracion": 0.0, "Carga": 0.00},
    {"Grupo": "Muestra 1", "Penetracion": 0.5, "Carga": 1.10},
    {"Grupo": "Muestra 1", "Penetracion": 1.0, "Carga": 2.25},
    {"Grupo": "Muestra 1", "Penetracion": 1.5, "Carga": 3.50},
    {"Grupo": "Muestra 1", "Penetracion": 2.0, "Carga": 4.75},
    {"Grupo": "Muestra 1", "Penetracion": 2.5, "Carga": 6.05},
    {"Grupo": "Muestra 1", "Penetracion": 4.0, "Carga": 8.90},
    {"Grupo": "Muestra 1", "Penetracion": 5.0, "Carga": 10.35},
    {"Grupo": "Muestra 1", "Penetracion": 7.5, "Carga": 13.20},
]


def penetration_to_mm(value, unit):
    if unit == "pulgadas (in)":
        return value * 25.4
    return value


def load_to_kn(value, unit):
    if unit == "kgf":
        return value * 0.00980665
    if unit == "lbf":
        return value * 0.0044482216
    return value


def kn_to_display(value, unit):
    if unit == "kgf":
        return value / 0.00980665
    if unit == "lbf":
        return value / 0.0044482216
    return value


def mm_to_display(value, unit):
    if unit == "pulgadas (in)":
        return value / 25.4
    return value


def clean_group_name(value):
    value = str(value).strip()
    return value if value else "Muestra"


def prepare_rows(rows, penetration_unit, load_unit):
    prepared = []
    for row in rows:
        try:
            penetration = float(row["Penetracion"])
            load = float(row["Carga"])
        except (TypeError, ValueError, KeyError):
            continue
        if not math.isfinite(penetration) or not math.isfinite(load):
            continue
        prepared.append(
            {
                "Grupo": clean_group_name(row.get("Grupo", "Muestra")),
                "penetracion_mm": penetration_to_mm(penetration, penetration_unit),
                "carga_kn": load_to_kn(load, load_unit),
            }
        )
    return prepared


def grouped_points(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["Grupo"], []).append((row["penetracion_mm"], row["carga_kn"]))
    cleaned = {}
    for name, points in groups.items():
        ordered = sorted(points)
        merged = {}
        for penetration, load in ordered:
            merged.setdefault(penetration, []).append(load)
        cleaned[name] = [(x, float(np.mean(y_values))) for x, y_values in merged.items()]
    return cleaned


def interpolate_load(points, penetration_mm):
    x = np.array([point[0] for point in points], dtype=float)
    y = np.array([point[1] for point in points], dtype=float)
    if len(x) < 2 or penetration_mm < np.min(x) or penetration_mm > np.max(x):
        return None
    return float(np.interp(penetration_mm, x, y))


def cbr_results(groups):
    results = []
    for name, points in groups.items():
        load_25 = interpolate_load(points, 2.5)
        load_50 = interpolate_load(points, 5.0)
        cbr_25 = None if load_25 is None else load_25 / STANDARD_LOADS_KN[2.5] * 100
        cbr_50 = None if load_50 is None else load_50 / STANDARD_LOADS_KN[5.0] * 100
        selected = None
        if cbr_25 is not None and cbr_50 is not None:
            selected = max(cbr_25, cbr_50)
        elif cbr_25 is not None:
            selected = cbr_25
        elif cbr_50 is not None:
            selected = cbr_50
        results.append(
            {
                "Grupo": name,
                "Carga 2.5 mm (kN)": load_25,
                "CBR 2.5 mm (%)": cbr_25,
                "Carga 5.0 mm (kN)": load_50,
                "CBR 5.0 mm (%)": cbr_50,
                "CBR adoptado (%)": selected,
            }
        )
    return results


def dispersion_summary(results, threshold_percent):
    values = [row["CBR adoptado (%)"] for row in results if row["CBR adoptado (%)"] is not None]
    if len(values) < 2:
        return False, None
    mean_value = float(np.mean(values))
    if mean_value <= 0:
        return False, None
    cov = float(np.std(values, ddof=1) / mean_value * 100)
    return cov >= threshold_percent, cov


def plot_cbr(groups, results, penetration_unit, load_unit, show_trend=True, title="Curvas CBR"):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor("#20272c")

    colors = [ORANGE, GREEN, BLUE, "#c792ea", "#ffd166", "#f78c6c"]
    result_map = {row["Grupo"]: row for row in results}

    for index, (name, points) in enumerate(groups.items()):
        color = colors[index % len(colors)]
        x = np.array([point[0] for point in points], dtype=float)
        y = np.array([point[1] for point in points], dtype=float)
        xd = [mm_to_display(value, penetration_unit) for value in x]
        yd = [kn_to_display(value, load_unit) for value in y]
        ax.plot(xd, yd, marker="o", linewidth=2.5, color=color, label=name)

        if show_trend and len(x) >= 2:
            slope, intercept = np.polyfit(x, y, 1)
            x_line = np.linspace(np.min(x), np.max(x), 80)
            y_line = slope * x_line + intercept
            ax.plot(
                [mm_to_display(value, penetration_unit) for value in x_line],
                [kn_to_display(value, load_unit) for value in y_line],
                linestyle="--",
                linewidth=1.8,
                color=color,
                alpha=0.75,
            )

        group_result = result_map.get(name, {})
        for penetration in (2.5, 5.0):
            load = group_result.get(f"Carga {penetration:.1f} mm (kN)")
            cbr = group_result.get(f"CBR {penetration:.1f} mm (%)")
            if load is None or cbr is None:
                continue
            ax.scatter(
                [mm_to_display(penetration, penetration_unit)],
                [kn_to_display(load, load_unit)],
                s=120,
                color=color,
                edgecolor=TEXT,
                linewidth=1.2,
                zorder=5,
            )
            ax.annotate(
                f"CBR {penetration:.1f} = {cbr:.1f}%",
                (mm_to_display(penetration, penetration_unit), kn_to_display(load, load_unit)),
                xytext=(8, 10),
                textcoords="offset points",
                color=TEXT,
                fontsize=10,
                weight="bold",
            )

    for penetration in (2.5, 5.0):
        ax.axvline(mm_to_display(penetration, penetration_unit), color=MUTED, linestyle=":", linewidth=1.2)

    ax.set_title(title, color=TEXT, fontsize=16, fontweight="bold")
    ax.set_xlabel(f"Penetracion ({'in' if penetration_unit == 'pulgadas (in)' else 'mm'})")
    ax.set_ylabel(f"Carga ({load_unit})")
    ax.grid(color="#354039", linestyle="--", linewidth=0.7, alpha=0.8)
    ax.legend(facecolor=PANEL, edgecolor="#2b332e")
    fig.tight_layout()
    return fig


def format_number(value, decimals=2):
    if value is None:
        return "Fuera de rango"
    return f"{value:.{decimals}f}"


st.set_page_config(page_title="Calculo CBR", layout="wide")
st.markdown(
    f"""
    <style>
    .stApp {{ background: {BG}; color: {TEXT}; }}
    section[data-testid="stSidebar"] {{ background: {PANEL}; }}
    .metric-card {{ background:{PANEL}; border:1px solid #2b332e; padding:18px; border-radius:8px; }}
    .metric-label {{ color:{ORANGE}; font-size:13px; font-weight:800; }}
    .metric-value {{ color:{TEXT}; font-size:38px; font-weight:900; }}
    .metric-note {{ color:{MUTED}; font-size:13px; margin-top:4px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Calculadora CBR")
st.caption("Ingreso de datos de penetracion-carga, cambio de unidades, curvas, rectas de tendencia y CBR a 2.5 mm y 5.0 mm.")

with st.sidebar:
    st.header("Datos de ensayo")
    penetration_unit = st.selectbox("Unidad de penetracion", ["mm", "pulgadas (in)"])
    load_unit = st.selectbox("Unidad de carga", ["kN", "kgf", "lbf"])
    dispersion_limit = st.slider("Umbral para graficos separados por dispersion (%)", 10, 60, 25, 5)
    show_trend = st.checkbox("Mostrar rectas de tendencia", value=True)
    st.markdown("---")
    st.info("Agrega filas en la tabla. Usa el campo Grupo para separar muestras, moldes o repeticiones.")

rows = st.data_editor(
    DEFAULT_POINTS,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Grupo": st.column_config.TextColumn("Grupo"),
        "Penetracion": st.column_config.NumberColumn(f"Penetracion ({'in' if penetration_unit == 'pulgadas (in)' else 'mm'})", min_value=0.0, step=0.1),
        "Carga": st.column_config.NumberColumn(f"Carga ({load_unit})", min_value=0.0, step=0.1),
    },
)

prepared_rows = prepare_rows(rows, penetration_unit, load_unit)
groups = grouped_points(prepared_rows)

if not groups:
    st.warning("Ingresa al menos dos puntos validos de penetracion y carga.")
    st.stop()

results = cbr_results(groups)
is_dispersed, cov = dispersion_summary(results, dispersion_limit)
valid_results = [row for row in results if row["CBR adoptado (%)"] is not None]
best_result = max(valid_results, key=lambda row: row["CBR adoptado (%)"]) if valid_results else None

col1, col2, col3 = st.columns(3)
with col1:
    value = "N/D" if best_result is None else f"{best_result['CBR adoptado (%)']:.1f}%"
    st.markdown(f"<div class='metric-card'><div class='metric-label'>CBR ADOPTADO MAYOR</div><div class='metric-value'>{value}</div><div class='metric-note'>Segun 2.5 mm y 5.0 mm</div></div>", unsafe_allow_html=True)
with col2:
    value = "N/D" if not valid_results else f"{np.mean([row['CBR adoptado (%)'] for row in valid_results]):.1f}%"
    st.markdown(f"<div class='metric-card'><div class='metric-label'>PROMEDIO DE GRUPOS</div><div class='metric-value'>{value}</div><div class='metric-note'>{len(valid_results)} grupo(s) con resultado</div></div>", unsafe_allow_html=True)
with col3:
    if cov is None:
        value = "N/D"
        note = "Se requiere mas de un grupo"
    else:
        value = f"{cov:.1f}%"
        note = "Disperso" if is_dispersed else "Dentro del umbral"
    st.markdown(f"<div class='metric-card'><div class='metric-label'>DISPERSION</div><div class='metric-value'>{value}</div><div class='metric-note'>{note}</div></div>", unsafe_allow_html=True)

st.pyplot(plot_cbr(groups, results, penetration_unit, load_unit, show_trend))

if len(groups) > 1 and is_dispersed:
    st.subheader("Graficos separados por dispersion")
    for name, points in groups.items():
        group_result = [row for row in results if row["Grupo"] == name]
        st.pyplot(plot_cbr({name: points}, group_result, penetration_unit, load_unit, show_trend, f"Curva CBR - {name}"))

st.subheader("Resultados")
display_rows = []
for row in results:
    display_rows.append(
        {
            "Grupo": row["Grupo"],
            "Carga 2.5 mm (kN)": format_number(row["Carga 2.5 mm (kN)"]),
            "CBR 2.5 mm (%)": format_number(row["CBR 2.5 mm (%)"]),
            "Carga 5.0 mm (kN)": format_number(row["Carga 5.0 mm (kN)"]),
            "CBR 5.0 mm (%)": format_number(row["CBR 5.0 mm (%)"]),
            "CBR adoptado (%)": format_number(row["CBR adoptado (%)"]),
        }
    )
st.dataframe(display_rows, use_container_width=True, hide_index=True)

pdf_sections = [
    (
        "Descripcion",
        [
            "Informe tecnico de calculo CBR a partir de datos de penetracion y carga.",
            f"Unidad de penetracion usada en pantalla: {penetration_unit}.",
            f"Unidad de carga usada en pantalla: {load_unit}.",
            "Los calculos internos se realizan en mm y kN.",
        ],
    ),
    (
        "Resultados principales",
        [
            f"CBR adoptado mayor: {'N/D' if best_result is None else format_number(best_result['CBR adoptado (%)']) + '%'}",
            f"Promedio de grupos: {'N/D' if not valid_results else format_number(np.mean([row['CBR adoptado (%)'] for row in valid_results])) + '%'}",
            f"Coeficiente de variacion: {'N/D' if cov is None else format_number(cov) + '%'}",
            f"Autor: {AUTHOR}.",
        ],
    ),
    (
        "Criterio",
        [
            "CBR 2.5 mm = carga interpolada a 2.5 mm / 13.24 kN * 100.",
            "CBR 5.0 mm = carga interpolada a 5.0 mm / 19.96 kN * 100.",
            "El CBR adoptado toma el mayor entre 2.5 mm y 5.0 mm cuando ambos existen.",
        ],
    ),
]
pdf_bytes = build_technical_pdf(
    "Informe tecnico - Calculo CBR",
    pdf_sections,
    tables=[
        {
            "title": "Resultados CBR",
            "columns": list(display_rows[0].keys()) if display_rows else [],
            "rows": [list(row.values()) for row in display_rows],
        }
    ],
)
st.download_button(
    "Descargar informe tecnico PDF",
    data=pdf_bytes,
    file_name="informe_tecnico_cbr.pdf",
    mime="application/pdf",
)

with st.expander("Criterio usado"):
    st.markdown(
        """
        - CBR 2.5 mm = carga interpolada a 2.5 mm / 13.24 kN * 100.
        - CBR 5.0 mm = carga interpolada a 5.0 mm / 19.96 kN * 100.
        - El CBR adoptado toma el mayor entre 2.5 mm y 5.0 mm cuando ambos existen.
        - Si la penetracion 2.5 mm o 5.0 mm queda fuera del rango de datos, ese punto no se calcula.
        """
    )

add_streamlit_signature(st)
