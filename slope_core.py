import math
from dataclasses import dataclass


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
        raise ValueError("El circulo de falla debe cortar el terreno en dos puntos.")

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


def find_critical_circle(values):
    height = values["height"]
    slope_angle = values["slope_angle"]
    crest_x = height / math.tan(math.radians(slope_angle))
    best = None

    cx_min = max(crest_x * 0.6, height * 0.25)
    cx_max = crest_x + height * 2.2
    cy_min = height * 0.85
    cy_max = height * 2.6

    for i in range(13):
        cx = cx_min + (cx_max - cx_min) * i / 12
        for j in range(13):
            cy = cy_min + (cy_max - cy_min) * j / 12
            radius = math.hypot(cx, cy)
            roots = find_intersections(height, slope_angle, cx, cy, radius)
            if len(roots) < 2:
                continue
            x_start, x_end = roots[0], roots[-1]
            if x_start < -height * 0.2 or x_start > height * 0.25 or x_end < crest_x * 0.85:
                continue
            trial = dict(values, cx=cx, cy=cy, radius=radius)
            trial["slices"] = recommended_slice_count(height, slope_angle, cx, cy, radius) or int(values["slices"])
            try:
                _slices, _roots, fellenius, bishop = calculate_slices(trial)
            except ValueError:
                continue
            if best is None or bishop < best[0]:
                best = (bishop, cx, cy, radius, trial["slices"], fellenius)

    if best is None:
        return automatic_circle(height, slope_angle) + (int(values["slices"]),)
    _bishop, cx, cy, radius, slices, _fellenius = best
    return cx, cy, radius, slices
