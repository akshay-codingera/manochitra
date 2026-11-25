"""Deterministic SVG validation for the assignment's quality gates.

The prompt limits geometry to primitives that this validator can bound. SVG
features whose bounds are difficult to prove (paths, transforms, images,
filters, masks and external references) are rejected rather than guessed.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

MAX_SVG_BYTES = 35_000
MIN_LABELS = 3

SAFE_VISUAL_PROPERTIES = {"opacity", "stroke-dashoffset", "stroke-width", "fill", "stroke"}
SAFE_COORDINATE_PROPERTIES = {"cx", "cy", "x", "y"}
SAFE_ANIMATION_PROPERTIES = SAFE_VISUAL_PROPERTIES | SAFE_COORDINATE_PROPERTIES

MANDATORY_CHECKS = ("valid_svg", "within_viewbox", "title_and_labels", "has_animation")
CUSTOM_CHECKS = ("scientific_terms",)
ADVANCED_CHECKS = ("concept_structure",)
ALL_CHECKS = MANDATORY_CHECKS + CUSTOM_CHECKS + ADVANCED_CHECKS

ALLOWED_ELEMENTS = {
    "svg", "title", "desc", "defs", "style", "g", "rect", "circle", "ellipse",
    "line", "polygon", "polyline", "text", "tspan", "linearGradient", "radialGradient",
    "stop", "animate", "set",
}
DISALLOWED_ELEMENTS = {
    "script", "foreignObject", "image", "use", "path", "filter", "mask", "clipPath",
}

SUPERSCRIPT_TRANSLATION = str.maketrans({"²": "2", "³": "3", "⁴": "4", "₁": "1", "₂": "2", "₃": "3"})


@dataclass
class CheckResult:
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    checks: dict[str, CheckResult]
    parsed_root: ET.Element | None = None

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks.values())

    @property
    def failures(self) -> list[str]:
        return [f"{name}: {result.detail}" for name, result in self.checks.items() if not result.passed]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {name: result.to_dict() for name, result in self.checks.items()}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def extract_svg(response_text: str) -> str:
    """Extract the first complete SVG document, allowing accidental code fences."""
    text = (response_text or "").strip()
    start = text.find("<svg")
    end = text.rfind("</svg>")
    if start < 0 or end < start:
        return ""
    return text[start : end + len("</svg>")].strip()


def _number(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    cleaned = re.sub(r"(?:px|pt|em|rem)$", "", str(value).strip())
    result = float(cleaned)
    if not math.isfinite(result):
        raise ValueError("non-finite coordinate")
    return result


def _style_declarations(style: str) -> dict[str, str]:
    """Parse simple inline CSS declarations."""
    declarations: dict[str, str] = {}
    for item in style.split(";"):
        if ":" not in item:
            continue
        name, value = item.split(":", 1)
        declarations[name.strip().lower()] = value.strip().lower()
    return declarations


def _hidden_by_presentation(element: ET.Element) -> bool:
    style = _style_declarations(element.get("style", ""))
    display = (element.get("display") or style.get("display", "")).lower()
    visibility = (element.get("visibility") or style.get("visibility", "")).lower()
    raw_opacity = element.get("opacity") or style.get("opacity")
    if display == "none" or visibility in {"hidden", "collapse"}:
        return True
    if raw_opacity is not None:
        try:
            if float(raw_opacity) <= 0:
                return True
        except ValueError:
            return True

    tag = _local_name(element.tag)
    if tag == "text":
        raw_font_size = element.get("font-size") or style.get("font-size")
        if raw_font_size is not None:
            try:
                if _number(raw_font_size) <= 0:
                    return True
            except ValueError:
                pass
        fill = (element.get("fill") or style.get("fill", "")).lower()
        stroke = (element.get("stroke") or style.get("stroke", "")).lower()
        raw_stroke_width = element.get("stroke-width") or style.get("stroke-width", "0")
        if fill == "none":
            if not stroke or stroke == "none":
                return True
            try:
                if _number(raw_stroke_width) <= 0:
                    return True
            except ValueError:
                return True

    return False


def _keyframe_blocks(css: str) -> list[tuple[str, str]]:
    """Extract (animation_name, body) for each @keyframes block."""
    blocks: list[tuple[str, str]] = []
    marker = re.compile(r"@(?:-webkit-)?keyframes\s+([\w-]+)\s*\{", re.IGNORECASE)
    for match in marker.finditer(css):
        name = match.group(1)
        opening = css.find("{", match.start())
        depth = 0
        for index in range(opening, len(css)):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((name, css[opening + 1:index]))
                    break
    return blocks


def _parse_keyframes(css: str) -> dict[str, dict[str, list[float]]]:
    """Parse keyframes into mapping: anim_name -> property_name -> list of numeric values."""
    keyframes: dict[str, dict[str, list[float]]] = {}
    for name, block in _keyframe_blocks(css):
        prop_values: dict[str, list[float]] = {}
        for decl_block in re.findall(r"\{([^{}]*)\}", block):
            for item in decl_block.split(";"):
                if ":" not in item:
                    continue
                pname, pval = item.split(":", 1)
                pname = pname.strip().lower()
                pval = pval.strip()
                nums = re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)", pval)
                if nums:
                    try:
                        val = float(nums[0])
                        prop_values.setdefault(pname, []).append(val)
                    except ValueError:
                        pass
        keyframes[name] = prop_values
    return keyframes


def _parse_css_animation_rules(css: str) -> list[tuple[str, str]]:
    """Extract (selector, animation_name) from CSS rules."""
    rules: list[tuple[str, str]] = []
    clean_css = re.sub(r"@(?:-webkit-)?keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[\s\S]*?\}", "", css)
    for match in re.finditer(r"([^{}]+)\{([^{}]+)\}", clean_css):
        selector = match.group(1).strip()
        body = match.group(2)
        decls = _style_declarations(body)
        anim_prop = decls.get("animation-name") or decls.get("animation")
        if anim_prop:
            tokens = anim_prop.split()
            anim_name = tokens[0] if tokens else anim_prop
            rules.append((selector, anim_name))
    return rules


def _element_matches_selector(element: ET.Element, selector: str) -> bool:
    """Check simple CSS selector match for element (tag, #id, .class, [attr])."""
    tag = _local_name(element.tag)
    sel = selector.strip()
    if sel == tag:
        return True
    elem_id = element.get("id")
    if elem_id and (sel == f"#{elem_id}" or sel == f"{tag}#{elem_id}"):
        return True
    elem_class = element.get("class", "")
    classes = elem_class.split()
    if any(sel == f".{cls}" or sel == f"{tag}.{cls}" for cls in classes):
        return True
    return False


def _extract_animated_values(
    element: ET.Element,
    prop: str,
    keyframes: dict[str, dict[str, list[float]]],
    css_rules: list[tuple[str, str]],
) -> list[float]:
    """Find all animated values for a property on an element from SMIL or CSS keyframes."""
    values: list[float] = []

    # 1. SMIL animations directly on element or targeting element
    for child in element:
        if _local_name(child.tag) in {"animate", "set"}:
            attr_name = (child.get("attributeName") or "").strip().lower()
            if attr_name == prop:
                raw_values = child.get("values")
                if raw_values:
                    for v in raw_values.split(";"):
                        v = v.strip()
                        if v:
                            try:
                                values.append(_number(v))
                            except ValueError:
                                pass
                for attr in ("from", "to", "by"):
                    raw = child.get(attr)
                    if raw:
                        try:
                            values.append(_number(raw))
                        except ValueError:
                            pass

    # 2. CSS animations
    elem_style = _style_declarations(element.get("style", ""))
    anim_name = elem_style.get("animation-name") or elem_style.get("animation")
    if anim_name:
        anim_name = anim_name.split()[0]
        if anim_name in keyframes and prop in keyframes[anim_name]:
            values.extend(keyframes[anim_name][prop])

    for selector, rule_anim in css_rules:
        if _element_matches_selector(element, selector):
            if rule_anim in keyframes and prop in keyframes[rule_anim]:
                values.extend(keyframes[rule_anim][prop])

    return values


def _stroke_padding(
    element: ET.Element,
    keyframes: dict[str, dict[str, list[float]]] | None = None,
    css_rules: list[tuple[str, str]] | None = None,
) -> float:
    style = element.attrib.get("style", "")
    match = re.search(r"(?:^|;)\s*stroke-width\s*:\s*([0-9.]+)", style)
    raw = element.attrib.get("stroke-width")
    if raw is None and match:
        raw = match.group(1)
    base_width = _number(raw, 0.0)
    if base_width < 0:
        raise ValueError("stroke-width cannot be negative")

    animated_widths: list[float] = []
    if keyframes is not None and css_rules is not None:
        animated_widths = _extract_animated_values(element, "stroke-width", keyframes, css_rules)

    peak_width = max([base_width] + animated_widths) if animated_widths else base_width
    return peak_width / 2


def _bounds_for_element(
    element: ET.Element,
    keyframes: dict[str, dict[str, list[float]]] | None = None,
    css_rules: list[tuple[str, str]] | None = None,
) -> tuple[float, float, float, float] | None:
    tag = _local_name(element.tag)
    pad = _stroke_padding(element, keyframes, css_rules)

    if tag == "rect":
        x, y = _number(element.get("x")), _number(element.get("y"))
        width, height = _number(element.get("width")), _number(element.get("height"))
        if width <= 0 or height <= 0:
            raise ValueError("rect width and height must be positive")
        xs = [x]
        ys = [y]
        if keyframes is not None and css_rules is not None:
            xs.extend(_extract_animated_values(element, "x", keyframes, css_rules))
            ys.extend(_extract_animated_values(element, "y", keyframes, css_rules))
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return min_x - pad, min_y - pad, max_x + width + pad, max_y + height + pad

    if tag == "circle":
        cx, cy, radius = _number(element.get("cx")), _number(element.get("cy")), _number(element.get("r"))
        if radius <= 0:
            raise ValueError("circle radius must be positive")
        cxs = [cx]
        cys = [cy]
        rs = [radius]
        if keyframes is not None and css_rules is not None:
            cxs.extend(_extract_animated_values(element, "cx", keyframes, css_rules))
            cys.extend(_extract_animated_values(element, "cy", keyframes, css_rules))
            rs.extend(_extract_animated_values(element, "r", keyframes, css_rules))
        min_cx, max_cx = min(cxs), max(cxs)
        min_cy, max_cy = min(cys), max(cys)
        max_r = max(rs)
        return min_cx - max_r - pad, min_cy - max_r - pad, max_cx + max_r + pad, max_cy + max_r + pad

    if tag == "ellipse":
        cx, cy = _number(element.get("cx")), _number(element.get("cy"))
        rx, ry = _number(element.get("rx")), _number(element.get("ry"))
        if rx <= 0 or ry <= 0:
            raise ValueError("ellipse radii must be positive")
        cxs = [cx]
        cys = [cy]
        if keyframes is not None and css_rules is not None:
            cxs.extend(_extract_animated_values(element, "cx", keyframes, css_rules))
            cys.extend(_extract_animated_values(element, "cy", keyframes, css_rules))
        min_cx, max_cx = min(cxs), max(cxs)
        min_cy, max_cy = min(cys), max(cys)
        return min_cx - rx - pad, min_cy - ry - pad, max_cx + rx + pad, max_cy + ry + pad

    if tag == "line":
        x1, y1 = _number(element.get("x1")), _number(element.get("y1"))
        x2, y2 = _number(element.get("x2")), _number(element.get("y2"))
        return min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad

    if tag in {"polygon", "polyline"}:
        raw_points = (element.get("points") or "").strip()
        number_pattern = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
        values = [float(value) for value in re.findall(number_pattern, raw_points)]
        residue = re.sub(number_pattern, "", raw_points).replace(",", "").strip()
        if residue or len(values) < 4 or len(values) % 2:
            raise ValueError(f"{tag} has malformed points")
        xs, ys = values[0::2], values[1::2]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"{tag} has non-finite points")
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad

    if tag == "text":
        x = _number(element.get("x"))
        y = _number(element.get("y"))
        font_size = _number(element.get("font-size"), 18.0)
        if font_size <= 0:
            raise ValueError("text font-size must be positive")
        visible_text = "".join(element.itertext()).strip()
        measured_width = _number(element.get("textLength"), max(0.0, len(visible_text) * font_size * 0.58))
        if measured_width < 0:
            raise ValueError("textLength cannot be negative")
        anchor = element.get("text-anchor", "start")
        if anchor == "middle":
            left, right = x - measured_width / 2, x + measured_width / 2
        elif anchor == "end":
            left, right = x - measured_width, x
        else:
            left, right = x, x + measured_width
        return left - pad, y - font_size - pad, right + pad, y + font_size * 0.25 + pad

    return None


def _validate_structure(svg: str, raw_text: str = "") -> tuple[ET.Element | None, CheckResult]:
    if re.search(r"<!DOCTYPE|<!ENTITY", f"{raw_text}\n{svg}", re.IGNORECASE):
        return None, CheckResult(False, "XML DOCTYPE and entity declarations are forbidden for security.")
    if not svg:
        return None, CheckResult(False, "No complete <svg>...</svg> document was returned.")
    if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
        return None, CheckResult(False, f"SVG is too large ({len(svg.encode('utf-8'))} bytes; limit {MAX_SVG_BYTES}).")

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return None, CheckResult(False, f"XML parsing failed: {exc}.")

    if _local_name(root.tag) != "svg":
        return None, CheckResult(False, "The XML root element is not <svg>.")
    if not root.tag.startswith("{http://www.w3.org/2000/svg}"):
        return None, CheckResult(False, "The root <svg> is missing the standard SVG namespace.")

    for element in root.iter():
        tag = _local_name(element.tag)
        if tag in DISALLOWED_ELEMENTS or tag not in ALLOWED_ELEMENTS:
            return None, CheckResult(False, f"Unsupported or unsafe SVG element <{tag}>.")
        for attribute, value in element.attrib.items():
            attr_name = _local_name(attribute).lower()
            if attr_name.startswith("on"):
                return None, CheckResult(False, f"Event-handler attribute '{attribute}' is not allowed.")
            if attr_name in {"href", "src"} and not value.startswith("#"):
                return None, CheckResult(False, "External links and embedded resources are not allowed.")
            if attr_name == "transform":
                return None, CheckResult(False, "SVG transforms are disallowed so bounds can be checked reliably.")
            if "url(" in value.lower() and not re.fullmatch(r"\s*url\(#[A-Za-z_][\w.-]*\)\s*", value):
                return None, CheckResult(False, "External CSS/SVG URLs are not allowed.")

    for style_element in (item for item in root.iter() if _local_name(item.tag) == "style"):
        css = style_element.text or ""
        if re.search(r"@import|expression\s*\(|url\s*\(\s*(?!#)", css, re.IGNORECASE):
            return None, CheckResult(False, "External or executable CSS is not allowed.")
        if re.search(r"(?:^|[;{}])\s*transform\s*:", css, re.IGNORECASE):
            return None, CheckResult(False, "CSS transforms are disallowed so bounds can be checked reliably.")

    return root, CheckResult(True, "SVG is well-formed XML with a supported <svg> root and safe elements.")


def _validate_viewbox(root: ET.Element | None) -> tuple[CheckResult, tuple[float, float, float, float] | None]:
    if root is None:
        return CheckResult(False, "Cannot inspect viewBox because SVG parsing failed."), None
    raw = root.get("viewBox")
    if not raw:
        return CheckResult(False, "The root SVG is missing a viewBox attribute."), None
    try:
        values = [float(value) for value in re.split(r"[\s,]+", raw.strip())]
        if len(values) != 4 or not all(math.isfinite(value) for value in values):
            raise ValueError("viewBox must contain four finite numbers")
        x, y, width, height = values
        if width <= 0 or height <= 0:
            raise ValueError("viewBox width and height must be positive")
        return CheckResult(True, f"viewBox is valid ({x:g} {y:g} {width:g} {height:g})."), (x, y, width, height)
    except ValueError as exc:
        return CheckResult(False, f"Invalid viewBox: {exc}."), None


def _validate_bounds(root: ET.Element | None, viewbox: tuple[float, float, float, float] | None) -> CheckResult:
    if root is None or viewbox is None:
        return CheckResult(False, "Cannot verify drawing bounds without parsed SVG and a valid viewBox.")

    vx, vy, width, height = viewbox
    max_x, max_y = vx + width, vy + height

    style_text = "\n".join(element.text or "" for element in root.iter() if _local_name(element.tag) == "style")
    keyframes = _parse_keyframes(style_text)
    css_rules = _parse_css_animation_rules(style_text)

    checked = 0
    try:
        for element in root.iter():
            tag = _local_name(element.tag)
            if tag not in {"rect", "circle", "ellipse", "line", "polygon", "polyline", "text"}:
                continue
            bounds = _bounds_for_element(element, keyframes, css_rules)
            if bounds is None:
                continue
            checked += 1
            left, top, right, bottom = bounds
            if left < vx - 0.01 or top < vy - 0.01 or right > max_x + 0.01 or bottom > max_y + 0.01:
                return CheckResult(
                    False,
                    f"<{tag}> bounds ({left:.1f}, {top:.1f}, {right:.1f}, {bottom:.1f}) exceed the viewBox.",
                )
    except (ValueError, TypeError) as exc:
        return CheckResult(False, f"Could not calculate an element's bounds: {exc}.")

    if checked == 0:
        return CheckResult(False, "No supported visible geometry or text was found to inspect.")
    return CheckResult(True, f"All {checked} supported visible elements fit inside the viewBox.")


def _visible_text_elements(root: ET.Element) -> list[ET.Element]:
    """Return visible text nodes outside <defs>, including inherited hidden state."""
    visible: list[ET.Element] = []

    def walk(element: ET.Element, inherited_hidden: bool = False, in_defs: bool = False) -> None:
        tag = _local_name(element.tag)
        hidden = inherited_hidden or _hidden_by_presentation(element)
        inside_defs = in_defs or tag == "defs"
        if tag == "text" and not hidden and not inside_defs and "".join(element.itertext()).strip():
            visible.append(element)
        for child in element:
            walk(child, hidden, inside_defs)

    walk(root)
    return visible


def _validate_title_and_labels(
    root: ET.Element | None,
    concept: dict[str, Any],
    viewbox: tuple[float, float, float, float] | None,
) -> CheckResult:
    if root is None:
        return CheckResult(False, "Cannot inspect title or labels because SVG parsing failed.")
    titles = ["".join(element.itertext()).strip() for element in root if _local_name(element.tag) == "title"]
    descriptions = ["".join(element.itertext()).strip() for element in root if _local_name(element.tag) == "desc"]
    has_title = any(title for title in titles)
    has_description = any(description for description in descriptions)

    visible_text_elements = _visible_text_elements(root)
    visible_texts = ["".join(element.itertext()).strip() for element in visible_text_elements]
    expected_heading = re.sub(r"[^a-z0-9 ]+", "", _normalise_text(concept["name"]))
    headings = [re.sub(r"[^a-z0-9 ]+", "", _normalise_text(label)) for label in visible_texts]
    heading_indices = [index for index, label in enumerate(headings) if expected_heading in label]
    explanatory_labels = [label for label in headings if expected_heading not in label]

    if not has_title:
        return CheckResult(False, "A non-empty <title> element is required.")
    if not has_description:
        return CheckResult(False, "A non-empty <desc> element is required for an accessible diagram.")
    if not heading_indices:
        return CheckResult(False, f"The topic name '{concept['name']}' must appear as a visible top-left text heading.")
    if viewbox is None:
        return CheckResult(False, "Cannot verify the heading position without a valid viewBox.")

    vx, vy, width, height = viewbox
    heading_element = visible_text_elements[heading_indices[0]]
    try:
        heading_x = _number(heading_element.get("x"))
        heading_y = _number(heading_element.get("y"))
    except ValueError as exc:
        return CheckResult(False, f"The topic heading has invalid coordinates: {exc}.")
    if heading_x > vx + width * 0.42 or heading_y > vy + height * 0.28:
        return CheckResult(False, "The topic heading must be positioned in the top-left region of the viewBox.")
    if len(explanatory_labels) < MIN_LABELS:
        return CheckResult(
            False,
            f"Found {len(explanatory_labels)} visible explanatory text labels (excluding the heading); at least {MIN_LABELS} are required.",
        )
    return CheckResult(
        True,
        f"A non-empty <title>/<desc>, top-left '{concept['name']}' heading and {len(explanatory_labels)} visible explanatory labels were found.",
    )


def _validate_animation(root: ET.Element | None) -> CheckResult:
    if root is None:
        return CheckResult(False, "Cannot inspect animation because SVG parsing failed.")

    # Collect visible non-defs elements
    visible_elements: list[ET.Element] = []
    def walk(el: ET.Element, in_defs: bool = False, hidden: bool = False) -> None:
        tag = _local_name(el.tag)
        is_defs = in_defs or tag == "defs"
        is_hidden = hidden or _hidden_by_presentation(el)
        if not is_defs and not is_hidden:
            visible_elements.append(el)
        for child in el:
            walk(child, is_defs, is_hidden)
    walk(root)

    found_safe_animation = False

    # Check SMIL animations
    smil_elements = [
        element for element in root.iter()
        if _local_name(element.tag) in {"animate", "set"}
    ]
    if smil_elements:
        for element in smil_elements:
            attr = (element.get("attributeName") or "").strip()
            if not attr or attr not in SAFE_ANIMATION_PROPERTIES:
                return CheckResult(
                    False,
                    f"SMIL animation may change geometry or an unsupported property: '{attr}'. Only {sorted(SAFE_ANIMATION_PROPERTIES)} are allowed.",
                )
        # Verify at least one SMIL element is attached to a visible element
        smil_on_visible = any(
            any(child in smil_elements for child in el)
            for el in visible_elements
        )
        if smil_on_visible:
            found_safe_animation = True

    # Check CSS animations
    style_text = "\n".join(element.text or "" for element in root.iter() if _local_name(element.tag) == "style")
    keyframe_blocks = _keyframe_blocks(style_text)
    if keyframe_blocks:
        declared_names = {name for name, _ in keyframe_blocks}
        declared_names_lower = {name.lower() for name in declared_names}
        all_properties: set[str] = set()
        for _, block in keyframe_blocks:
            for decl_block in re.findall(r"\{([^{}]*)\}", block):
                for item in decl_block.split(";"):
                    if ":" in item:
                        pname = item.split(":", 1)[0].strip().lower()
                        all_properties.add(pname)

        unsafe_properties = sorted(all_properties - SAFE_ANIMATION_PROPERTIES)
        if unsafe_properties:
            return CheckResult(
                False,
                f"CSS animation includes properties that can alter drawing geometry or bounds: {', '.join(unsafe_properties)}.",
            )

        # Check if animation is attached to at least one visible element
        css_rules = _parse_css_animation_rules(style_text)
        attached_to_visible = False
        for el in visible_elements:
            style = _style_declarations(el.get("style", ""))
            anim_name = style.get("animation-name") or style.get("animation")
            if anim_name and anim_name.split()[0].lower() in declared_names_lower:
                attached_to_visible = True
                break
            for sel, rule_anim in css_rules:
                if rule_anim.lower() in declared_names_lower and _element_matches_selector(el, sel):
                    attached_to_visible = True
                    break
            if attached_to_visible:
                break

        if attached_to_visible and all_properties:
            found_safe_animation = True
        elif not attached_to_visible and keyframe_blocks:
            return CheckResult(
                False,
                "CSS keyframes exist but are not attached to any visible SVG element.",
            )

    if found_safe_animation:
        return CheckResult(True, "At least one SMIL/CSS animation is attached to visible elements and uses only safe properties.")
    return CheckResult(False, "No safe SMIL animation or attached CSS animation was found.")


def _normalise_text(text: str) -> str:
    normalised = text.lower().translate(SUPERSCRIPT_TRANSLATION)
    normalised = re.sub(r"\^\s*([234])", r"\1", normalised)
    return " ".join(normalised.split())


def _validate_scientific_content(root: ET.Element | None, concept: dict[str, Any]) -> CheckResult:
    """Additional custom check: required concept-specific terminology coverage."""
    if root is None:
        return CheckResult(False, "Cannot inspect scientific terminology because SVG parsing failed.")
    visible_text = " ".join("".join(element.itertext()) for element in _visible_text_elements(root))
    normalised = _normalise_text(visible_text)
    terms = concept.get("required_terms", [])
    matched = [term for term in terms if _normalise_text(term) in normalised]
    required_count = math.ceil(len(terms) * float(concept.get("minimum_term_fraction", 1.0)))
    passed = len(matched) >= required_count
    detail = f"Matched {len(matched)}/{len(terms)} required terms; {required_count} needed."
    if matched:
        detail += " Found: " + ", ".join(matched) + "."
    missing = [term for term in terms if term not in matched]
    if missing:
        detail += " Missing: " + ", ".join(missing) + "."
    return CheckResult(passed, detail)


def validate_svg(
    response_text: str,
    concept: dict[str, Any],
    include_structure: bool = False,
) -> ValidationReport:
    """Run SVG validation.
    
    Default runs the original 4 mandatory checks + 1 custom terminology check.
    If include_structure is True, also evaluates the 6th advanced concept_structure check.
    """
    svg = extract_svg(response_text)
    root, structure_check = _validate_structure(svg, raw_text=response_text)
    viewbox_check, viewbox = _validate_viewbox(root)
    checks: dict[str, CheckResult] = {
        "valid_svg": structure_check,
        "within_viewbox": _validate_bounds(root, viewbox),
        "title_and_labels": _validate_title_and_labels(root, concept, viewbox),
        "has_animation": _validate_animation(root),
        "scientific_terms": _validate_scientific_content(root, concept),
    }
    if include_structure:
        from app.validators.concept_structure_validator import validate_concept_structure
        checks["concept_structure"] = validate_concept_structure(root, concept)

    return ValidationReport(checks=checks, parsed_root=root)
