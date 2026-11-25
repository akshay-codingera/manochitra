"""Deterministic concept structure and geometric relationship validation.

This validator acts as the advanced quality gate (Check 6), verifying actual
geometric relationships rather than relying solely on keyword matching or semantic IDs.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass
class StructureCheckResult:
    passed: bool
    detail: str
    metrics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {"passed": self.passed, "detail": self.detail}
        if self.metrics:
            result["metrics"] = self.metrics
        return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _number(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        val = float(value)
        return val if math.isfinite(val) else default
    except ValueError:
        return default


def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _visible_text_content(root: ET.Element) -> str:
    texts: list[str] = []
    for elem in root.iter():
        if _local_name(elem.tag) == "text":
            display = (elem.get("display") or "").lower()
            visibility = (elem.get("visibility") or "").lower()
            if display != "none" and visibility not in {"hidden", "collapse"}:
                texts.append("".join(elem.itertext()).strip())
    return " ".join(texts).lower()


def _validate_pythagoras(root: ET.Element) -> StructureCheckResult:
    """Verify right-angled triangle geometry, right-angle marker, hypotenuse and formula."""
    triangles: list[list[tuple[float, float]]] = []
    triangle_elems: list[ET.Element] = []

    # 1. Look for polygon with 3 points
    for elem in root.iter():
        if _local_name(elem.tag) == "polygon":
            raw = (elem.get("points") or "").strip()
            nums = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)", raw)]
            if len(nums) == 6:
                triangles.append([(nums[0], nums[1]), (nums[2], nums[3]), (nums[4], nums[5])])
                triangle_elems.append(elem)

    # 2. Look for 3 connected lines if no polygon
    if not triangles:
        lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for elem in root.iter():
            if _local_name(elem.tag) == "line":
                p1 = (_number(elem.get("x1")), _number(elem.get("y1")))
                p2 = (_number(elem.get("x2")), _number(elem.get("y2")))
                if _dist(p1, p2) > 10:
                    lines.append((p1, p2))
        if len(lines) >= 3:
            pts = set()
            for p1, p2 in lines[:3]:
                pts.add((round(p1[0], 1), round(p1[1], 1)))
                pts.add((round(p2[0], 1), round(p2[1], 1)))
            if len(pts) == 3:
                triangles.append(list(pts))

    if not triangles:
        return StructureCheckResult(False, "No 3-vertex right-angled triangle polygon found.")

    pts = triangles[0]
    p1, p2, p3 = pts

    # Calculate side vectors and squared lengths
    v12 = (p2[0] - p1[0], p2[1] - p1[1])
    v23 = (p3[0] - p2[0], p3[1] - p2[1])
    v31 = (p1[0] - p3[0], p1[1] - p3[1])

    d12 = math.hypot(*v12)
    d23 = math.hypot(*v23)
    d31 = math.hypot(*v31)

    area = 0.5 * abs(p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
    if area < 200:
        return StructureCheckResult(False, f"Triangle is degenerate or too small (area={area:.1f}).")

    sides = sorted([(d12, p3, (p1, p2)), (d23, p1, (p2, p3)), (d31, p2, (p3, p1))], key=lambda s: s[0])
    a, opp_a, seg_a = sides[0]
    b, opp_b, seg_b = sides[1]
    c, right_vertex, hypotenuse_seg = sides[2]

    # Verify Pythagorean equality a² + b² ≈ c²
    pyth_diff = abs(a ** 2 + b ** 2 - c ** 2) / (c ** 2)
    if pyth_diff > 0.08:
        return StructureCheckResult(
            False,
            f"Triangle sides ({a:.1f}, {b:.1f}, {c:.1f}) violate Pythagoras: a²+b²={a**2+b**2:.0f} != c²={c**2:.0f} (error {pyth_diff*100:.1f}%).",
        )

    # Verify right angle at right_vertex
    h_p1, h_p2 = hypotenuse_seg
    va = (h_p1[0] - right_vertex[0], h_p1[1] - right_vertex[1])
    vb = (h_p2[0] - right_vertex[0], h_p2[1] - right_vertex[1])
    dot = va[0] * vb[0] + va[1] * vb[1]
    cos_theta = abs(dot / (math.hypot(*va) * math.hypot(*vb)))
    if cos_theta > 0.08:
        return StructureCheckResult(
            False,
            f"Vertex at ({right_vertex[0]:.1f}, {right_vertex[1]:.1f}) is not a right angle (cos θ = {cos_theta:.3f}).",
        )

    # Verify right-angle indicator exists near right_vertex
    has_marker = False
    for elem in root.iter():
        if elem in triangle_elems:
            continue
        elem_id = (elem.get("id") or "").lower()
        elem_class = (elem.get("class") or "").lower()
        tag = _local_name(elem.tag)
        if "marker" in elem_id or "marker" in elem_class or "corner" in elem_id:
            has_marker = True
            break
        if tag in {"rect", "polyline", "polygon"}:
            if tag == "rect":
                rx, ry = _number(elem.get("x")), _number(elem.get("y"))
                rw, rh = _number(elem.get("width")), _number(elem.get("height"))
                if rw < 35 and rh < 35 and _dist((rx, ry), right_vertex) < 45:
                    has_marker = True
                    break
            elif tag in {"polyline", "polygon"}:
                raw = (elem.get("points") or "").strip()
                p_nums = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)", raw)]
                if 4 <= len(p_nums) <= 8:
                    pts_m = [(p_nums[i], p_nums[i + 1]) for i in range(0, len(p_nums), 2)]
                    if any(_dist(pm, right_vertex) < 35 for pm in pts_m):
                        has_marker = True
                        break

    if not has_marker:
        return StructureCheckResult(
            False,
            f"Right-angle indicator marker is missing near right-angle corner ({right_vertex[0]:.1f}, {right_vertex[1]:.1f}).",
        )

    # Verify hypotenuse label/identification near side c
    hyp_mid = ((h_p1[0] + h_p2[0]) / 2, (h_p1[1] + h_p2[1]) / 2)
    has_hyp_label = False
    for elem in root.iter():
        if _local_name(elem.tag) == "text":
            txt = "".join(elem.itertext()).lower()
            if "hypotenuse" in txt or txt.strip() == "c":
                tx, ty = _number(elem.get("x")), _number(elem.get("y"))
                if _dist((tx, ty), hyp_mid) < c * 0.7:
                    has_hyp_label = True
                    break

    if not has_hyp_label:
        return StructureCheckResult(False, "Hypotenuse label is not associated with the longest side c.")

    # Verify formula in text
    all_text = _visible_text_content(root)
    norm = all_text.replace("²", "2").replace("^2", "2").replace(" ", "")
    if "a2+b2=c2" not in norm and "c2=a2+b2" not in norm:
        return StructureCheckResult(False, "Formula a² + b² = c² is missing from visible labels.")

    return StructureCheckResult(
        True,
        f"Right-angled triangle verified (a={a:.1f}, b={b:.1f}, c={c:.1f}), right angle at ({right_vertex[0]:.1f}, {right_vertex[1]:.1f}), hypotenuse identified, and formula present.",
        metrics={"side_a": round(a, 2), "side_b": round(b, 2), "side_c": round(c, 2), "pyth_error_pct": round(pyth_diff * 100, 2)},
    )


def _validate_circle(root: ET.Element) -> StructureCheckResult:
    """Verify centre, radius, diameter, circumference and d = 2r relationship."""
    circles = []
    for elem in root.iter():
        if _local_name(elem.tag) == "circle":
            r = _number(elem.get("r"))
            cx = _number(elem.get("cx"))
            cy = _number(elem.get("cy"))
            if r >= 60:
                circles.append((elem, cx, cy, r))

    if not circles:
        return StructureCheckResult(False, "Main circle element with radius >= 60px not found.")

    _, cx, cy, radius = max(circles, key=lambda c: c[3])

    centre_pt = (cx, cy)
    has_centre_marker = False
    for elem in root.iter():
        if _local_name(elem.tag) == "circle":
            r = _number(elem.get("r"))
            if r <= 8 and _dist((_number(elem.get("cx")), _number(elem.get("cy"))), centre_pt) <= 5:
                has_centre_marker = True
                break

    all_text = _visible_text_content(root)
    if "centre" not in all_text and "center" not in all_text:
        return StructureCheckResult(False, "Circle centre label is missing.")
    if not has_centre_marker:
        return StructureCheckResult(False, f"Circle centre marker not found at ({cx:.1f}, {cy:.1f}).")

    lines = []
    for elem in root.iter():
        if _local_name(elem.tag) == "line":
            p1 = (_number(elem.get("x1")), _number(elem.get("y1")))
            p2 = (_number(elem.get("x2")), _number(elem.get("y2")))
            length = _dist(p1, p2)
            lines.append((p1, p2, length, elem))

    # Identify radius line
    radius_lines = [
        (p1, p2, L) for p1, p2, L in [(l[0], l[1], l[2]) for l in lines]
        if (_dist(p1, centre_pt) <= 8 and abs(_dist(p2, centre_pt) - radius) <= 8)
        or (_dist(p2, centre_pt) <= 8 and abs(_dist(p1, centre_pt) - radius) <= 8)
    ]

    if not radius_lines:
        return StructureCheckResult(
            False,
            f"Radius line connecting centre ({cx:.1f}, {cy:.1f}) to circumference (R={radius:.1f}) not found.",
        )

    r_len = radius_lines[0][2]
    if abs(r_len - radius) > radius * 0.08:
        return StructureCheckResult(False, f"Radius line length ({r_len:.1f}) does not match circle radius ({radius:.1f}).")

    # Identify diameter line
    diameter_lines = []
    for p1, p2, L, _ in lines:
        d1 = abs(_dist(p1, centre_pt) - radius)
        d2 = abs(_dist(p2, centre_pt) - radius)
        if d1 <= 8 and d2 <= 8 and L > radius * 1.5:
            area2 = abs((p2[1] - p1[1]) * cx - (p2[0] - p1[0]) * cy + p2[0] * p1[1] - p2[1] * p1[0])
            dist_to_centre = area2 / L if L > 0 else 999.0
            if dist_to_centre <= 6.0:
                diameter_lines.append((p1, p2, L))

    if not diameter_lines:
        return StructureCheckResult(
            False,
            "Diameter line passing through the centre and spanning both circumference edges not found.",
        )

    d_len = diameter_lines[0][2]
    if abs(d_len - 2 * radius) > radius * 0.12:
        return StructureCheckResult(False, f"Diameter length ({d_len:.1f}) does not equal 2R ({2*radius:.1f}).")

    diam_ratio_diff = abs(d_len - 2 * r_len) / d_len
    if diam_ratio_diff > 0.06:
        return StructureCheckResult(False, f"Diameter ({d_len:.1f}) is not twice the radius ({r_len:.1f}).")

    if "radius" not in all_text:
        return StructureCheckResult(False, "Radius label is missing.")
    if "diameter" not in all_text:
        return StructureCheckResult(False, "Diameter label is missing.")
    if "circumference" not in all_text:
        return StructureCheckResult(False, "Circumference label is missing.")

    return StructureCheckResult(
        True,
        f"Circle geometry verified: Centre ({cx:.1f}, {cy:.1f}), Radius line ({r_len:.1f}px), Diameter line ({d_len:.1f}px = 2r ±{diam_ratio_diff*100:.1f}%), and Circumference verified.",
        metrics={"radius": round(radius, 2), "radius_line": round(r_len, 2), "diameter_line": round(d_len, 2)},
    )


def _validate_series_circuit(root: ET.Element) -> StructureCheckResult:
    """Verify single closed circuit loop, power cell, series components and annotations."""
    has_loop = False
    loop_rect = None

    for elem in root.iter():
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        tag = _local_name(elem.tag)
        if "loop" in elem_id or "circuit" in elem_id or "wire" in elem_id:
            has_loop = True
            if tag == "rect":
                loop_rect = elem
            break
        if tag == "rect":
            w = _number(elem.get("width"))
            h = _number(elem.get("height"))
            fill = (elem.get("fill") or "").lower()
            stroke = elem.get("stroke")
            if w >= 250 and h >= 150 and (fill in {"none", "transparent"} or stroke):
                has_loop = True
                loop_rect = elem

    if not has_loop:
        lines = [elem for elem in root.iter() if _local_name(elem.tag) == "line"]
        if len(lines) >= 4:
            has_loop = True

    if not has_loop:
        return StructureCheckResult(False, "No closed circuit loop (rectangular or polygonal wiring) found.")

    # Parallel branch / shunt detection
    for elem in root.iter():
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        if any(term in elem_id or term in elem_cls for term in ("parallel", "branch", "shunt")):
            return StructureCheckResult(
                False,
                f"Parallel branch or shunt detected ('{elem_id or elem_cls}'); series circuit must contain only a single loop with no parallel branches.",
            )

    if loop_rect is not None:
        rx = _number(loop_rect.get("x"))
        ry = _number(loop_rect.get("y"))
        rw = _number(loop_rect.get("width"))
        rh = _number(loop_rect.get("height"))
        if rw > 0 and rh > 0:
            for elem in root.iter():
                if _local_name(elem.tag) == "line":
                    x1 = _number(elem.get("x1"))
                    y1 = _number(elem.get("y1"))
                    x2 = _number(elem.get("x2"))
                    y2 = _number(elem.get("y2"))
                    # Vertical or horizontal internal bridge wire
                    if abs(x1 - x2) < 5 and (rx + 20 < x1 < rx + rw - 20):
                        if (abs(y1 - ry) < 15 and abs(y2 - (ry + rh)) < 15) or (abs(y2 - ry) < 15 and abs(y1 - (ry + rh)) < 15):
                            return StructureCheckResult(
                                False,
                                "Parallel branch detected bridging circuit wires; series circuit must be a single loop.",
                            )

    has_cell = False
    for elem in root.iter():
        tag = _local_name(elem.tag)
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        if tag in {"rect", "g", "line", "path", "circle"}:
            if "cell" in elem_id or "battery" in elem_id or "cell" in elem_cls or "battery" in elem_cls:
                has_cell = True
                break

    if not has_cell:
        return StructureCheckResult(False, "Power cell/battery graphic component is missing from the circuit.")

    component_count = 0
    for elem in root.iter():
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        if any(term in elem_id or term in elem_cls for term in ("lamp", "resistor", "bulb", "component", "meter")):
            component_count += 1

    if component_count < 2:
        symbol_count = 0
        for elem in root.iter():
            tag = _local_name(elem.tag)
            elem_id = (elem.get("id") or "").lower()
            if tag == "circle" and "centre" not in elem_id:
                r = _number(elem.get("r"))
                if 12 <= r <= 35:
                    symbol_count += 1
            elif tag == "rect" and elem is not loop_rect:
                w = _number(elem.get("width"))
                h = _number(elem.get("height"))
                if 20 <= w <= 80 and 10 <= h <= 40:
                    symbol_count += 1
        component_count = max(component_count, symbol_count)

    if component_count < 2:
        return StructureCheckResult(
            False,
            f"Series circuit requires at least two components along the loop; found {component_count}.",
        )

    all_text = _visible_text_content(root)
    has_current = "current" in all_text or re.search(r"\b[iI]\b", all_text)
    has_voltage = "voltage" in all_text or "volt" in all_text or re.search(r"\b[vV]\b", all_text)

    if not has_current:
        return StructureCheckResult(False, "Current annotation/label is missing from the series circuit.")
    if not has_voltage:
        return StructureCheckResult(False, "Voltage annotation/label is missing from the series circuit.")

    return StructureCheckResult(
        True,
        f"Series circuit verified: single continuous loop, cell/battery, {component_count} series components, and current/voltage annotations verified.",
        metrics={"components_found": component_count, "closed_loop": True},
    )


def _validate_photosynthesis(root: ET.Element) -> StructureCheckResult:
    """Verify leaf reaction site, light energy, water/CO2 inputs and glucose/O2 outputs."""
    all_text = _visible_text_content(root)

    has_leaf = False
    for elem in root.iter():
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        tag = _local_name(elem.tag)
        if "leaf" in elem_id or "leaf" in elem_cls or "chloroplast" in elem_id:
            has_leaf = True
            break
        if tag in {"ellipse", "polygon", "path"} and (
            "green" in (elem.get("fill") or "").lower()
            or (elem.get("fill") or "").lower() in {"#8fa58a", "#244638", "#c8d96b", "#1d2c25"}
        ):
            has_leaf = True

    if not has_leaf and "leaf" in all_text:
        has_leaf = True

    if not has_leaf:
        return StructureCheckResult(False, "Central leaf / chloroplast reaction site illustration not found.")

    if "chlorophyll" not in all_text:
        return StructureCheckResult(False, "Chlorophyll identification is missing from the leaf reaction site.")

    has_light = "light" in all_text or "sun" in all_text
    if not has_light:
        return StructureCheckResult(False, "Light energy input is missing.")

    has_water = "water" in all_text or "h2o" in all_text or "h₂o" in all_text
    has_co2 = "carbon dioxide" in all_text or "co2" in all_text or "co₂" in all_text

    if not has_water:
        return StructureCheckResult(False, "Water input (H₂O) is missing from photosynthesis inputs.")
    if not has_co2:
        return StructureCheckResult(False, "Carbon dioxide input (CO₂) is missing from photosynthesis inputs.")

    has_glucose = "glucose" in all_text or "sugar" in all_text
    has_oxygen = "oxygen" in all_text or "o2" in all_text or "o₂" in all_text

    if not has_glucose:
        return StructureCheckResult(False, "Glucose output is missing from photosynthesis products.")
    if not has_oxygen:
        return StructureCheckResult(False, "Oxygen output (O₂) is missing from photosynthesis products.")

    arrows = [elem for elem in root.iter() if _local_name(elem.tag) in {"line", "polyline", "polygon"}]
    if len(arrows) < 4:
        return StructureCheckResult(False, "Photosynthesis diagram lacks directional arrows for inputs and outputs.")

    leaf_cx, leaf_cy = 480.0, 320.0
    for elem in root.iter():
        elem_id = (elem.get("id") or "").lower()
        if "leaf" in elem_id or "chloroplast" in elem_id:
            tag = _local_name(elem.tag)
            if tag in {"ellipse", "circle"}:
                leaf_cx = _number(elem.get("cx"), 480.0)
                leaf_cy = _number(elem.get("cy"), 320.0)
                break
            elif tag == "rect":
                leaf_cx = _number(elem.get("x"), 480.0) + _number(elem.get("width"), 0.0) / 2
                leaf_cy = _number(elem.get("y"), 320.0) + _number(elem.get("height"), 0.0) / 2
                break

    for elem in root.iter():
        if _local_name(elem.tag) == "line":
            elem_id = (elem.get("id") or "").lower()
            elem_cls = (elem.get("class") or "").lower()
            x1, y1 = _number(elem.get("x1")), _number(elem.get("y1"))
            x2, y2 = _number(elem.get("x2")), _number(elem.get("y2"))
            d1 = math.hypot(x1 - leaf_cx, y1 - leaf_cy)
            d2 = math.hypot(x2 - leaf_cx, y2 - leaf_cy)
            ident = f"{elem_id} {elem_cls}".lower()
            is_input = bool(re.search(r"(?:^|[_\W])(?:in|input|inflow|light|ray|co2|h2o|water)(?:[_\W]|$)", ident))
            is_output = bool(re.search(r"(?:^|[_\W])(?:out|output|outflow|glucose|o2|oxygen|product)(?:[_\W]|$)", ident))
            if is_input and not is_output:
                if d2 > d1:
                    return StructureCheckResult(False, f"Photosynthesis input line '{elem_id or 'input'}' points away from the leaf reaction site.")
            elif is_output and not is_input:
                if d2 < d1:
                    return StructureCheckResult(False, f"Photosynthesis output line '{elem_id or 'output'}' points into the leaf reaction site instead of away.")

    return StructureCheckResult(
        True,
        "Photosynthesis reaction structure verified: Leaf reaction site, chlorophyll pigment, light energy, inputs (H₂O, CO₂), and products (glucose, O₂).",
        metrics={"inputs_verified": True, "outputs_verified": True, "chlorophyll_present": True},
    )


def _validate_states_of_matter(root: ET.Element) -> StructureCheckResult:
    """Verify 3 distinct particle regions: ordered solid, mobile liquid (not resting at bottom), spaced gas."""
    containers = []
    id_matched = [
        (_number(elem.get("x")), _number(elem.get("y")), _number(elem.get("width")), _number(elem.get("height")), elem)
        for elem in root.iter()
        if _local_name(elem.tag) == "rect"
        and any(term in (elem.get("id") or "").lower() or term in (elem.get("class") or "").lower() for term in ("container", "vessel", "box"))
        and _number(elem.get("width")) >= 100 and _number(elem.get("height")) >= 180
    ]
    if len(id_matched) >= 3:
        containers = id_matched
    else:
        for elem in root.iter():
            if _local_name(elem.tag) == "rect":
                w = _number(elem.get("width"))
                h = _number(elem.get("height"))
                x = _number(elem.get("x"))
                y = _number(elem.get("y"))
                if 100 <= w <= 350 and 180 <= h <= 450:
                    containers.append((x, y, w, h, elem))

    containers.sort(key=lambda c: c[0])
    if len(containers) < 3:
        by_id = [
            elem for elem in root.iter()
            if any(term in (elem.get("id") or "").lower() for term in ("solid", "liquid", "gas"))
            and _local_name(elem.tag) in {"rect", "g"}
        ]
        if len(by_id) < 3:
            return StructureCheckResult(False, f"Found {len(containers)} containers; 3 distinct containers (solid, liquid, gas) are required.")

    if len(containers) >= 3:
        for i in range(len(containers) - 1):
            c1 = containers[i]
            c2 = containers[i + 1]
            if c1[0] + c1[2] > c2[0] + 5:
                return StructureCheckResult(False, "Particle containers overlap; each state requires a distinct region.")

    all_particles = []
    for elem in root.iter():
        if _local_name(elem.tag) == "circle":
            r = _number(elem.get("r"))
            cx = _number(elem.get("cx"))
            cy = _number(elem.get("cy"))
            if 3 <= r <= 25:
                all_particles.append((cx, cy, r, elem))

    if len(all_particles) < 18:
        return StructureCheckResult(
            False,
            f"Insufficient particle circles found across the three states ({len(all_particles)} found; >= 18 required).",
        )

    min_x = min(p[0] for p in all_particles)
    max_x = max(p[0] for p in all_particles)
    span = (max_x - min_x) / 3.0

    solid_particles = [p for p in all_particles if p[0] < min_x + span]
    liquid_particles = [p for p in all_particles if min_x + span <= p[0] < min_x + 2 * span]
    gas_particles = [p for p in all_particles if p[0] >= min_x + 2 * span]

    if len(solid_particles) < 6:
        return StructureCheckResult(False, f"Solid state has insufficient particles ({len(solid_particles)}; >= 6 required).")
    if len(liquid_particles) < 6:
        return StructureCheckResult(False, f"Liquid state has insufficient particles ({len(liquid_particles)}; >= 6 required).")
    if len(gas_particles) < 3:
        return StructureCheckResult(False, f"Gas state has insufficient particles ({len(gas_particles)}; >= 3 required).")

    def nearest_distances(pts: list[tuple[float, float, float, Any]]) -> list[float]:
        distances = []
        for i, p1 in enumerate(pts):
            dists = [_dist((p1[0], p1[1]), (p2[0], p2[1])) for j, p2 in enumerate(pts) if i != j]
            if dists:
                distances.append(min(dists))
        return distances

    solid_dists = nearest_distances(solid_particles)
    liquid_dists = nearest_distances(liquid_particles)
    gas_dists = nearest_distances(gas_particles)

    mean_solid = sum(solid_dists) / len(solid_dists) if solid_dists else 1.0
    mean_liquid = sum(liquid_dists) / len(liquid_dists) if liquid_dists else 1.0
    mean_gas = sum(gas_dists) / len(gas_dists) if gas_dists else 1.0

    variance_solid = sum((d - mean_solid) ** 2 for d in solid_dists) / len(solid_dists)
    std_solid = math.sqrt(variance_solid)
    cov_solid = std_solid / mean_solid if mean_solid > 0 else 1.0

    if cov_solid > 0.40:
        return StructureCheckResult(
            False,
            f"Solid particles are not in an ordered lattice arrangement (spacing variability {cov_solid*100:.1f}% > 40%).",
        )

    # Liquid particles: close together
    if mean_liquid > mean_solid * 2.2:
        return StructureCheckResult(
            False,
            f"Liquid particles are too dispersed (mean spacing {mean_liquid:.1f}px > 2.2x solid {mean_solid:.1f}px).",
        )

    # Gas particles: widely separated
    if mean_gas < mean_solid * 1.8:
        return StructureCheckResult(
            False,
            f"Gas particles are not sufficiently separated (mean spacing {mean_gas:.1f}px < 1.8x solid {mean_solid:.1f}px).",
        )

    # Liquid motion check: at least one liquid particle must have explicit motion animation
    has_liquid_motion = False
    for _, _, _, elem in liquid_particles:
        elem_id = (elem.get("id") or "").lower()
        elem_cls = (elem.get("class") or "").lower()
        for child in elem:
            c_tag = _local_name(child.tag)
            if c_tag in {"animate", "animatetransform"}:
                attr = (child.get("attributeName") or "").lower()
                if attr in {"cx", "cy", "x", "y", "transform"} or c_tag == "animatetransform":
                    has_liquid_motion = True
                    break
        if has_liquid_motion:
            break
        style = (elem.get("style") or "").lower()
        if "animation" in style and any(m in style for m in ("drift", "flow", "move", "liquid", "translate")):
            has_liquid_motion = True
            break
        if any(m in elem_cls for m in ("drift", "flow", "liquid_anim", "move")):
            has_liquid_motion = True
            break

    if not has_liquid_motion:
        # Check if root <style> defines keyframes targeting liquid elements
        style_texts = []
        for s in root.iter():
            if _local_name(s.tag) == "style":
                style_texts.append("".join(s.itertext()))
        joined_styles = " ".join(style_texts)
        for _, _, _, elem in liquid_particles:
            eid = elem.get("id")
            ecls = elem.get("class")
            if eid and f"#{eid}" in joined_styles and "keyframes" in joined_styles:
                has_liquid_motion = True
                break
            if ecls and f".{ecls}" in joined_styles and "keyframes" in joined_styles:
                has_liquid_motion = True
                break

    if not has_liquid_motion:
        return StructureCheckResult(
            False,
            "Liquid particles lack motion animation; liquid particles must exhibit movement past one another.",
        )

    return StructureCheckResult(
        True,
        f"States of matter verified: 3 regions, Solid (ordered lattice, spacing {mean_solid:.1f}px), Liquid (close particles {mean_liquid:.1f}px with mobile arrangement), Gas (widely separated {mean_gas:.1f}px = {mean_gas/mean_solid:.1f}x solid).",
        metrics={
            "mean_solid_spacing": round(mean_solid, 1),
            "mean_liquid_spacing": round(mean_liquid, 1),
            "mean_gas_spacing": round(mean_gas, 1),
            "solid_lattice_order": round(cov_solid, 2),
        },
    )


def validate_concept_structure(root: ET.Element | None, concept: dict[str, Any], svg_text: str = "") -> StructureCheckResult:
    """Entry point for Check 6: Concept Structure Validation."""
    if root is None:
        return StructureCheckResult(False, "Cannot inspect concept structure because SVG parsing failed.")

    concept_id = concept.get("id")
    if concept_id == "pythagoras":
        return _validate_pythagoras(root)
    elif concept_id == "circle":
        return _validate_circle(root)
    elif concept_id == "series-circuit":
        return _validate_series_circuit(root)
    elif concept_id == "photosynthesis":
        return _validate_photosynthesis(root)
    elif concept_id == "states-of-matter":
        return _validate_states_of_matter(root)
    else:
        return StructureCheckResult(False, f"Unknown concept id '{concept_id}'.")
