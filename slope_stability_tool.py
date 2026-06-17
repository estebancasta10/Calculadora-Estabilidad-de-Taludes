import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk


BG = "#111513"
PANEL = "#171c19"
PANEL_2 = "#202621"
TEXT = "#f5f4ef"
MUTED = "#a7ada6"
ORANGE = "#ff4b1f"
GREEN = "#2ebc66"
BLUE = "#4d76ff"
RED = "#d22b2b"
GRID = "#354039"


@dataclass
class Slice:
    number: int
    x_left: float
    x_right: float
    x_mid: float
    width: float
    height: float
    area: float
    area_above_water: float
    area_below_water: float
    weight: float
    alpha_deg: float
    base_length: float
    pore_force: float
    normal: float
    effective_normal: float
    shear: float
    resistant: float


def ground_y(x, height, slope_angle_deg):
    crest_x = height / math.tan(math.radians(slope_angle_deg))
    if x < 0:
        return 0.0
    if x <= crest_x:
        return x * math.tan(math.radians(slope_angle_deg))
    return height


def circle_lower_y(x, cx, cy, radius):
    dx = x - cx
    if abs(dx) > radius:
        return None
    return cy - math.sqrt(radius * radius - dx * dx)


def automatic_circle(height, slope_angle):
    crest_x = height / math.tan(math.radians(slope_angle))
    cx = crest_x
    cy = height * 1.15
    radius = math.hypot(cx, cy)
    return cx, cy, radius


def find_intersections(height, slope_angle, cx, cy, radius):
    x_min = cx - radius
    x_max = cx + radius
    steps = 2000
    roots = []

    def f(x):
        yb = circle_lower_y(x, cx, cy, radius)
        if yb is None:
            return None
        return ground_y(x, height, slope_angle) - yb

    prev_x = x_min
    prev_y = f(prev_x)
    for i in range(1, steps + 1):
        x = x_min + (x_max - x_min) * i / steps
        y = f(x)
        if y is None or prev_y is None:
            prev_x, prev_y = x, y
            continue
        if abs(y) < 1e-8:
            roots.append(x)
        elif prev_y * y < 0:
            lo, hi = prev_x, x
            for _ in range(60):
                mid = (lo + hi) / 2
                fm = f(mid)
                if fm is None:
                    break
                if f(lo) * fm <= 0:
                    hi = mid
                else:
                    lo = mid
            roots.append((lo + hi) / 2)
        prev_x, prev_y = x, y

    clean = []
    for root in roots:
        if not clean or abs(root - clean[-1]) > 0.02:
            clean.append(root)
    return clean


def recommended_slice_count(height, slope_angle, cx, cy, radius):
    roots = find_intersections(height, slope_angle, cx, cy, radius)
    if len(roots) < 2:
        return None
    sliding_width = roots[-1] - roots[0]
    target_width = max(height / 6.0, 0.75)
    return max(8, min(30, math.ceil(sliding_width / target_width)))


def find_critical_circle(values):
    height = values["height"]
    slope_angle = values["slope_angle"]
    crest_x = height / math.tan(math.radians(slope_angle))
    best = None

    x_steps = 13
    y_steps = 13
    cx_min = max(crest_x * 0.6, height * 0.25)
    cx_max = crest_x + height * 2.2
    cy_min = height * 0.85
    cy_max = height * 2.6

    for i in range(x_steps):
        cx = cx_min + (cx_max - cx_min) * i / (x_steps - 1)
        for j in range(y_steps):
            cy = cy_min + (cy_max - cy_min) * j / (y_steps - 1)
            radius = math.hypot(cx, cy)
            roots = find_intersections(height, slope_angle, cx, cy, radius)
            if len(roots) < 2:
                continue
            x_start, x_end = roots[0], roots[-1]
            if x_start < -height * 0.2 or x_start > height * 0.25:
                continue
            if x_end < crest_x * 0.85:
                continue
            trial = dict(values)
            trial["cx"] = cx
            trial["cy"] = cy
            trial["radius"] = radius
            suggested = recommended_slice_count(height, slope_angle, cx, cy, radius)
            trial["slices"] = suggested or int(values["slices"])
            try:
                _slices, _roots, fellenius, bishop = calculate_slices(trial)
            except ValueError:
                continue
            score = bishop
            if best is None or score < best[0]:
                best = (score, cx, cy, radius, trial["slices"], fellenius, bishop)

    if best is None:
        return automatic_circle(height, slope_angle) + (int(values["slices"]),)
    _score, cx, cy, radius, slices, _fellenius, _bishop = best
    return cx, cy, radius, slices


def integrate_area(x1, x2, height, slope_angle, cx, cy, radius, samples=24):
    if x2 <= x1:
        return 0.0
    dx = (x2 - x1) / samples
    area = 0.0
    for i in range(samples):
        xa = x1 + i * dx
        xb = xa + dx
        xm = (xa + xb) / 2
        top = ground_y(xm, height, slope_angle)
        bottom = circle_lower_y(xm, cx, cy, radius)
        if bottom is None:
            continue
        area += max(0.0, top - bottom) * dx
    return area


def integrate_water_areas(x1, x2, height, slope_angle, cx, cy, radius, water_y, samples=32):
    if x2 <= x1:
        return 0.0, 0.0
    dx = (x2 - x1) / samples
    above = 0.0
    below = 0.0
    for i in range(samples):
        xm = x1 + (i + 0.5) * dx
        top = ground_y(xm, height, slope_angle)
        bottom = circle_lower_y(xm, cx, cy, radius)
        if bottom is None:
            continue
        total_height = max(0.0, top - bottom)
        saturated_height = max(0.0, min(top, water_y) - bottom)
        saturated_height = min(saturated_height, total_height)
        below += saturated_height * dx
        above += max(0.0, total_height - saturated_height) * dx
    return above, below


def calculate_slices(values):
    c = values["cohesion"]
    phi = math.radians(values["phi"])
    gamma = values["gamma"]
    gamma_sat = values.get("gamma_sat", gamma)
    gamma_water = values.get("gamma_water", 9.81)
    water_y = values.get("water_y", -1e9)
    height = values["height"]
    slope_angle = values["slope_angle"]
    cx = values["cx"]
    cy = values["cy"]
    radius = values["radius"]
    n = int(values["slices"])

    roots = find_intersections(height, slope_angle, cx, cy, radius)
    if len(roots) < 2:
        raise ValueError(
            "El circulo de falla debe cortar el terreno en dos puntos. "
            "Ajusta X centro, Y centro o radio."
        )

    x_start, x_end = roots[0], roots[-1]
    if x_end <= x_start:
        raise ValueError("No se pudo definir el ancho de la masa deslizante.")

    slices = []
    width = (x_end - x_start) / n
    for idx in range(n):
        x_left = x_start + idx * width
        x_right = x_left + width
        x_mid = (x_left + x_right) / 2
        y_mid = circle_lower_y(x_mid, cx, cy, radius)
        if y_mid is None:
            continue
        top_mid = ground_y(x_mid, height, slope_angle)
        area_above, area_below = integrate_water_areas(x_left, x_right, height, slope_angle, cx, cy, radius, water_y)
        area = area_above + area_below
        weight = area_above * gamma + area_below * gamma_sat
        slope = (x_mid - cx) / max(1e-9, math.sqrt(max(1e-9, radius * radius - (x_mid - cx) ** 2)))
        alpha = math.atan(slope)
        base_length = width / max(1e-9, math.cos(alpha))
        pore_pressure = gamma_water * max(0.0, water_y - y_mid)
        pore_force = pore_pressure * base_length
        normal = weight * math.cos(alpha)
        effective_normal = max(0.0, normal - pore_force)
        shear = weight * math.sin(alpha)
        resistant = c * base_length + effective_normal * math.tan(phi)
        slices.append(
            Slice(
                number=idx + 1,
                x_left=x_left,
                x_right=x_right,
                x_mid=x_mid,
                width=width,
                height=max(0.0, top_mid - y_mid),
                area=area,
                area_above_water=area_above,
                area_below_water=area_below,
                weight=weight,
                alpha_deg=math.degrees(alpha),
                base_length=base_length,
                pore_force=pore_force,
                normal=normal,
                effective_normal=effective_normal,
                shear=shear,
                resistant=resistant,
            )
        )

    driving = sum(s.shear for s in slices)
    if abs(driving) < 1e-9:
        raise ValueError("El esfuerzo actuante es cero o invalido para esta geometria.")

    fellenius = sum(s.resistant for s in slices) / driving
    bishop = bishop_simplified(slices, c, phi, driving)
    return slices, roots, fellenius, bishop


def bishop_simplified(slices, cohesion, phi, driving):
    fs = 1.0
    tan_phi = math.tan(phi)
    for _ in range(100):
        numerator = 0.0
        for s in slices:
            alpha = math.radians(s.alpha_deg)
            m_alpha = math.cos(alpha) + (math.sin(alpha) * tan_phi / max(fs, 1e-9))
            numerator += (cohesion * s.base_length + max(0.0, s.weight - s.pore_force) * tan_phi) / max(m_alpha, 1e-9)
        new_fs = numerator / driving
        if abs(new_fs - fs) < 1e-5:
            return new_fs
        fs = new_fs
    return fs


class SlopeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Taludes | Fellenius y Bishop")
        self.geometry("1220x760")
        self.minsize(1060, 680)
        self.configure(bg=BG)
        self.values = {}
        self.slices = []
        self.roots = []
        self.last_fellenius = None
        self.last_bishop = None
        self._build_style()
        self._build_ui()
        self.calculate()

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=26)
        style.configure("Treeview.Heading", background=ORANGE, foreground="white", font=("Arial", 9, "bold"))
        style.map("Treeview", background=[("selected", ORANGE)])

    def _build_ui(self):
        header = tk.Frame(self, bg=BG, padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="■", fg=ORANGE, bg=BG, font=("Arial", 11, "bold")).pack(side="left")
        tk.Label(
            header,
            text="  CALCULADORA DE ESTABILIDAD DE TALUDES",
            fg=TEXT,
            bg=BG,
            font=("Arial Black", 14),
        ).pack(side="left")
        tk.Label(
            header,
            text="Fellenius / Bishop simplificado",
            fg=MUTED,
            bg=BG,
            font=("Arial", 9, "bold"),
        ).pack(side="right")

        body = tk.Frame(self, bg=BG, padx=22, pady=4)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=PANEL, padx=18, pady=16, highlightbackground="#2b332e", highlightthickness=1)
        left.pack(side="left", fill="y")

        tk.Frame(left, bg=ORANGE, height=3, width=58).pack(anchor="w", pady=(0, 10))
        tk.Label(left, text="DATOS DE ENTRADA", fg=TEXT, bg=PANEL, font=("Arial Black", 18)).pack(anchor="w")
        tk.Label(
            left,
            text="Define geometria, suelo y numero de dovelas.",
            fg=MUTED,
            bg=PANEL,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(0, 14))

        self.inputs = {}
        self.auto_circle = tk.BooleanVar(value=True)
        self.auto_slices = tk.BooleanVar(value=True)
        defaults = [
            ("cohesion", "c' cohesion (kPa)", 14.72),
            ("phi", "Angulo phi (grados)", 15.0),
            ("gamma", "Gamma sobre NAF (kN/m3)", 18.0),
            ("gamma_sat", "Gamma saturado (kN/m3)", 19.12),
            ("gamma_water", "Gamma agua (kN/m3)", 9.81),
            ("water_y", "Nivel freatico Y (m)", 0.0),
            ("height", "Altura H (m)", 12.0),
            ("slope_angle", "Angulo del talud beta (grados)", 60.0),
            ("cx", "Centro X del circulo (m)", 9.0),
            ("cy", "Centro Y del circulo (m)", 14.0),
            ("radius", "Radio R (m)", 14.0),
            ("slices", "Numero de dovelas", 10),
        ]
        for key, label, default in defaults:
            self._field(left, key, label, default)

        auto_row = tk.Checkbutton(
            left,
            text="Buscar circulo critico automaticamente",
            variable=self.auto_circle,
            command=self.calculate,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#0f1311",
            activebackground=PANEL,
            activeforeground=TEXT,
            font=("Arial", 9, "bold"),
        )
        auto_row.pack(anchor="w", pady=(8, 0))

        auto_slices_row = tk.Checkbutton(
            left,
            text="Numero de dovelas automatico",
            variable=self.auto_slices,
            command=self.calculate,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#0f1311",
            activebackground=PANEL,
            activeforeground=TEXT,
            font=("Arial", 9, "bold"),
        )
        auto_slices_row.pack(anchor="w", pady=(4, 0))
        tk.Label(
            left,
            text="Auto: 8 a 30 dovelas, ancho aprox. H/6.",
            fg=MUTED,
            bg=PANEL,
            font=("Arial", 8),
        ).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(left, bg=PANEL)
        btns.pack(fill="x", pady=(14, 0))
        tk.Button(
            btns,
            text="CALCULAR",
            command=self.calculate,
            bg=ORANGE,
            fg="white",
            activebackground="#ff6a3d",
            activeforeground="white",
            relief="flat",
            font=("Arial", 10, "bold"),
            padx=18,
            pady=10,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            btns,
            text="LIMPIAR",
            command=self.reset_defaults,
            bg=PANEL_2,
            fg=TEXT,
            activebackground="#2b332e",
            activeforeground=TEXT,
            relief="flat",
            font=("Arial", 10, "bold"),
            padx=18,
            pady=10,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        result = tk.Frame(left, bg=PANEL_2, padx=14, pady=14)
        result.pack(fill="x", pady=(18, 0))
        tk.Label(result, text="FACTOR DE SEGURIDAD", fg=ORANGE, bg=PANEL_2, font=("Arial", 9, "bold")).pack(anchor="w")
        self.fs_fellenius = tk.Label(result, text="Fellenius: --", fg=TEXT, bg=PANEL_2, font=("Arial Black", 14))
        self.fs_fellenius.pack(anchor="w", pady=(8, 0))
        self.fs_bishop = tk.Label(result, text="Bishop: --", fg=TEXT, bg=PANEL_2, font=("Arial Black", 14))
        self.fs_bishop.pack(anchor="w")

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        summary = tk.Frame(right, bg=BG)
        summary.pack(fill="x", pady=(0, 14))
        self.card_fellenius_value = self._summary_card(summary, "FELLENIUS", "F.S. --")
        self.card_bishop_value = self._summary_card(summary, "BISHOP SIMPLIFICADO", "F.S. --")

        canvas_panel = tk.Frame(right, bg=PANEL, padx=12, pady=12, highlightbackground="#2b332e", highlightthickness=1)
        canvas_panel.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_panel, bg="#20272c", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw())

        table_panel = tk.Frame(right, bg=PANEL, padx=12, pady=12, highlightbackground="#2b332e", highlightthickness=1)
        table_panel.pack(fill="x", pady=(14, 0))
        cols = ("n", "area", "W", "uL", "alpha", "L", "N", "T")
        self.table = ttk.Treeview(table_panel, columns=cols, show="headings", height=7)
        headings = {
            "n": "Dovela",
            "area": "Area m2",
            "W": "W kN/m",
            "uL": "uL kN/m",
            "alpha": "alpha deg",
            "L": "L arco",
            "N": "N' efectiva",
            "T": "Actuante",
        }
        for col in cols:
            self.table.heading(col, text=headings[col])
            self.table.column(col, width=85, anchor="center")
        self.table.pack(fill="x")

    def _field(self, parent, key, label, default):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, fg=MUTED, bg=PANEL, font=("Arial", 9, "bold")).pack(anchor="w")
        var = tk.StringVar(value=str(default))
        entry = tk.Entry(
            row,
            textvariable=var,
            bg="#0f1311",
            fg=TEXT,
            insertbackground=ORANGE,
            relief="flat",
            font=("Arial", 11),
            width=25,
        )
        entry.pack(fill="x", pady=(3, 0), ipady=7)
        entry.bind("<Return>", lambda _event: self.calculate())
        self.inputs[key] = var

    def _summary_card(self, parent, title, value):
        card = tk.Frame(parent, bg=PANEL, padx=18, pady=14, highlightbackground="#2b332e", highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=(0, 12))
        tk.Label(card, text=title, fg=ORANGE, bg=PANEL, font=("Arial", 9, "bold")).pack(anchor="w")
        value_label = tk.Label(card, text=value, fg=TEXT, bg=PANEL, font=("Arial Black", 24))
        value_label.pack(anchor="w", pady=(4, 0))
        return value_label

    def read_values(self):
        values = {}
        for key, var in self.inputs.items():
            text = var.get().strip().replace(",", ".")
            values[key] = int(float(text)) if key == "slices" else float(text)
        if values["slices"] < 2:
            raise ValueError("Usa al menos 2 dovelas.")
        if values["radius"] <= 0 or values["height"] <= 0:
            raise ValueError("Altura y radio deben ser mayores que cero.")
        if values["gamma"] <= 0 or values["gamma_sat"] <= 0 or values["gamma_water"] <= 0:
            raise ValueError("Los pesos unitarios deben ser mayores que cero.")
        if not 1 <= values["slope_angle"] <= 89:
            raise ValueError("El angulo del talud debe estar entre 1 y 89 grados.")
        if self.auto_circle.get():
            cx, cy, radius, auto_n = find_critical_circle(values)
            values["cx"] = cx
            values["cy"] = cy
            values["radius"] = radius
            self.inputs["cx"].set(f"{cx:.2f}")
            self.inputs["cy"].set(f"{cy:.2f}")
            self.inputs["radius"].set(f"{radius:.2f}")
            if self.auto_slices.get():
                values["slices"] = auto_n
                self.inputs["slices"].set(str(auto_n))
        if self.auto_slices.get():
            recommended = recommended_slice_count(
                values["height"],
                values["slope_angle"],
                values["cx"],
                values["cy"],
                values["radius"],
            )
            if recommended is not None:
                values["slices"] = recommended
                self.inputs["slices"].set(str(recommended))
        return values

    def calculate(self):
        try:
            self.values = self.read_values()
            self.slices, self.roots, fellenius, bishop = calculate_slices(self.values)
        except Exception as exc:
            messagebox.showerror("Revisa los datos", str(exc))
            return

        self.last_fellenius = fellenius
        self.last_bishop = bishop
        self.fs_fellenius.config(text=f"Fellenius: {fellenius:.3f}", fg=ORANGE if fellenius < 1.5 else GREEN)
        self.fs_bishop.config(text=f"Bishop: {bishop:.3f}", fg=ORANGE if bishop < 1.5 else GREEN)
        self.card_fellenius_value.config(text=f"F.S. {fellenius:.3f}", fg=ORANGE if fellenius < 1.5 else GREEN)
        self.card_bishop_value.config(text=f"F.S. {bishop:.3f}", fg=ORANGE if bishop < 1.5 else GREEN)
        self.fill_table()
        self.draw()

    def reset_defaults(self):
        defaults = {
            "cohesion": 14.72,
            "phi": 15.0,
            "gamma": 18.0,
            "gamma_sat": 19.12,
            "gamma_water": 9.81,
            "water_y": 0.0,
            "height": 12.0,
            "slope_angle": 60.0,
            "cx": 9.0,
            "cy": 14.0,
            "radius": 14.0,
            "slices": 10,
        }
        for key, value in defaults.items():
            self.inputs[key].set(str(value))
        self.auto_circle.set(True)
        self.auto_slices.set(True)
        self.calculate()

    def fill_table(self):
        self.table.delete(*self.table.get_children())
        for s in self.slices:
            self.table.insert(
                "",
                "end",
                values=(
                    s.number,
                    f"{s.area:.2f}",
                    f"{s.weight:.2f}",
                    f"{s.pore_force:.2f}",
                    f"{s.alpha_deg:.2f}",
                    f"{s.base_length:.2f}",
                    f"{s.effective_normal:.2f}",
                    f"{s.shear:.2f}",
                ),
            )

    def draw(self):
        if not self.values or not self.slices:
            return
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 400)
        h = max(c.winfo_height(), 280)
        pad = 46
        height = self.values["height"]
        slope_angle = self.values["slope_angle"]
        cx = self.values["cx"]
        cy = self.values["cy"]
        radius = self.values["radius"]
        water_y = self.values.get("water_y", -1e9)
        crest_x = height / math.tan(math.radians(slope_angle))
        x_points = [cx - radius, cx + radius, -1.5, crest_x + height * 1.2]
        y_points = [0, height, cy + radius * 0.1, cy - radius, water_y]
        xmin = min(x_points)
        xmax = max(x_points)
        ymin = min(y_points)
        ymax = max(y_points)
        span_x = max(1.0, xmax - xmin)
        span_y = max(1.0, ymax - ymin)

        def sx(x):
            return pad + (x - xmin) / span_x * (w - 2 * pad)

        def sy(y):
            return h - pad - (y - ymin) / span_y * (h - 2 * pad)

        def arrow_line(x1, y1, x2, y2, color=ORANGE, width=2, dash=None):
            c.create_line(x1, y1, x2, y2, fill=color, width=width, dash=dash, arrow="both", arrowshape=(8, 10, 4))

        def label_box(x, y, text, color=TEXT, fill="#111513", anchor="center", font=("Arial", 8, "bold")):
            item = c.create_text(x, y, text=text, fill=color, anchor=anchor, font=font)
            bbox = c.bbox(item)
            if bbox:
                rect = c.create_rectangle(
                    bbox[0] - 5,
                    bbox[1] - 3,
                    bbox[2] + 5,
                    bbox[3] + 3,
                    fill=fill,
                    outline="#2b332e",
                )
                c.tag_lower(rect, item)
            return item

        def dimension(x1, y1, x2, y2, text, offset_x=0, offset_y=0, color=ORANGE):
            px1, py1 = sx(x1), sy(y1)
            px2, py2 = sx(x2), sy(y2)
            arrow_line(px1 + offset_x, py1 + offset_y, px2 + offset_x, py2 + offset_y, color=color)
            c.create_line(px1, py1, px1 + offset_x, py1 + offset_y, fill=color, dash=(3, 3))
            c.create_line(px2, py2, px2 + offset_x, py2 + offset_y, fill=color, dash=(3, 3))
            label_box((px1 + px2) / 2 + offset_x, (py1 + py2) / 2 + offset_y, text, color=color)

        for i in range(7):
            x = pad + i * (w - 2 * pad) / 6
            c.create_line(x, pad, x, h - pad, fill=GRID)
            y = pad + i * (h - 2 * pad) / 6
            c.create_line(pad, y, w - pad, y, fill=GRID)

        ground_poly = [
            sx(xmin),
            sy(ymin),
            sx(xmin),
            sy(ground_y(xmin, height, slope_angle)),
            sx(0),
            sy(0),
            sx(crest_x),
            sy(height),
            sx(xmax),
            sy(height),
            sx(xmax),
            sy(ymin),
        ]
        c.create_polygon(ground_poly, fill="#101612", outline="")
        c.create_line(sx(xmin), sy(0), sx(0), sy(0), fill=TEXT, width=3)
        c.create_line(sx(0), sy(0), sx(crest_x), sy(height), fill=TEXT, width=4)
        c.create_line(sx(crest_x), sy(height), sx(xmax), sy(height), fill=TEXT, width=4)

        if ymin < water_y < ymax:
            c.create_rectangle(sx(xmin), sy(water_y), sx(xmax), sy(ymin), fill="#143040", outline="", stipple="gray25")
            c.create_line(sx(xmin), sy(water_y), sx(xmax), sy(water_y), fill="#52b7ff", width=2, dash=(8, 5))
            label_box(sx(xmin) + 70, sy(water_y) - 14, f"NAF = {water_y:.2f} m", color="#52b7ff")
            c.create_line(sx(xmin), sy(0), sx(0), sy(0), fill=TEXT, width=3)
            c.create_line(sx(0), sy(0), sx(crest_x), sy(height), fill=TEXT, width=4)
            c.create_line(sx(crest_x), sy(height), sx(xmax), sy(height), fill=TEXT, width=4)

        dimension(0, 0, 0, height, f"H = {height:.2f} m", offset_x=-38, color=ORANGE)
        dimension(0, 0, crest_x, 0, f"{crest_x:.2f} m", offset_y=30, color=ORANGE)
        dimension(crest_x, height, xmax, height, f"Corona {(xmax - crest_x):.2f} m", offset_y=-25, color=MUTED)

        angle_r = min(54, max(28, abs(sx(crest_x) - sx(0)) * 0.22))
        base_x, base_y = sx(0), sy(0)
        c.create_arc(
            base_x - angle_r,
            base_y - angle_r,
            base_x + angle_r,
            base_y + angle_r,
            start=0,
            extent=slope_angle,
            outline=ORANGE,
            width=2,
            style="arc",
        )
        angle_mid = math.radians(slope_angle / 2)
        label_box(
            base_x + math.cos(angle_mid) * (angle_r + 18),
            base_y - math.sin(angle_mid) * (angle_r + 18),
            f"beta = {slope_angle:.1f} deg",
            color=ORANGE,
        )

        arc = []
        samples = 160
        for i in range(samples + 1):
            x = cx - radius + 2 * radius * i / samples
            y = circle_lower_y(x, cx, cy, radius)
            if y is not None and ymin <= y <= ymax:
                arc.extend([sx(x), sy(y)])
        if len(arc) >= 4:
            c.create_line(*arc, fill=GREEN, width=2, dash=(6, 4))

        c.create_oval(sx(cx) - 4, sy(cy) - 4, sx(cx) + 4, sy(cy) + 4, fill=ORANGE, outline="")
        label_box(sx(cx), sy(cy) - 18, f"Centro ({cx:.2f}, {cy:.2f})", color=ORANGE)
        if len(self.roots) >= 2:
            root_x = self.roots[0]
            root_y = ground_y(root_x, height, slope_angle)
            arrow_line(sx(cx), sy(cy), sx(root_x), sy(root_y), color=GREEN, width=2, dash=(5, 4))
            label_box(
                (sx(cx) + sx(root_x)) / 2,
                (sy(cy) + sy(root_y)) / 2 - 16,
                f"R = {radius:.2f} m",
                color=GREEN,
            )

        for s in self.slices:
            top_l = ground_y(s.x_left, height, slope_angle)
            top_r = ground_y(s.x_right, height, slope_angle)
            bot_l = circle_lower_y(s.x_left, cx, cy, radius)
            bot_r = circle_lower_y(s.x_right, cx, cy, radius)
            if bot_l is None or bot_r is None:
                continue
            c.create_line(sx(s.x_left), sy(top_l), sx(s.x_left), sy(bot_l), fill=BLUE, width=1)
            c.create_line(sx(s.x_right), sy(top_r), sx(s.x_right), sy(bot_r), fill=BLUE, width=1)
            c.create_line(sx(cx), sy(cy), sx(s.x_mid), sy(circle_lower_y(s.x_mid, cx, cy, radius)), fill=RED, width=1)
            c.create_text(
                sx(s.x_mid),
                sy(circle_lower_y(s.x_mid, cx, cy, radius)) + 18,
                text=str(s.number),
                fill=MUTED,
                font=("Arial", 10, "bold"),
            )
            if len(self.slices) <= 14:
                bottom_mid = circle_lower_y(s.x_mid, cx, cy, radius)
                label_box(
                    sx(s.x_mid),
                    sy(bottom_mid) + 34,
                    f"a={s.alpha_deg:.1f} deg",
                    color=BLUE,
                    font=("Arial", 7, "bold"),
                )

        if self.slices:
            first = self.slices[0]
            dimension(
                first.x_left,
                circle_lower_y(first.x_left, cx, cy, radius) or 0,
                first.x_right,
                circle_lower_y(first.x_right, cx, cy, radius) or 0,
                f"b = {first.width:.2f} m",
                offset_y=48,
                color=BLUE,
            )

        if len(self.roots) >= 2:
            c.create_oval(sx(self.roots[0]) - 4, sy(ground_y(self.roots[0], height, slope_angle)) - 4, sx(self.roots[0]) + 4, sy(ground_y(self.roots[0], height, slope_angle)) + 4, fill=ORANGE, outline="")
            c.create_oval(sx(self.roots[-1]) - 4, sy(ground_y(self.roots[-1], height, slope_angle)) - 4, sx(self.roots[-1]) + 4, sy(ground_y(self.roots[-1], height, slope_angle)) + 4, fill=ORANGE, outline="")
            dimension(
                self.roots[0],
                0,
                self.roots[-1],
                0,
                f"Ancho falla = {(self.roots[-1] - self.roots[0]):.2f} m",
                offset_y=62,
                color=ORANGE,
            )

        c.create_text(
            pad,
            pad - 20,
            text="TALUD Y SUPERFICIE DE FALLA",
            fill=TEXT,
            anchor="w",
            font=("Arial Black", 13),
        )
        c.create_text(
            w - pad,
            h - pad + 24,
            text="Azul: dovelas  |  Verde: circulo de falla  |  Rojo: radios",
            fill=MUTED,
            anchor="e",
            font=("Arial", 9, "bold"),
        )


if __name__ == "__main__":
    app = SlopeApp()
    app.mainloop()
