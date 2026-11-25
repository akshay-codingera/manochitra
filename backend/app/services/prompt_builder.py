"""Builds the constrained SVG-generation prompt for one assignment concept."""

from __future__ import annotations

from typing import Any

STYLE_CONTRACT = """
VISUAL ART DIRECTION — follow this consistently:
- Editorial science illustration, calm and refined rather than a generic AI dashboard graphic.
- Warm cream canvas (#F7F4E9), soft lime accents (#C8D96B), muted sage (#8FA58A),
  deep forest green (#244638), and readable near-black green (#1D2C25).
- Topic heading positioned at the top-left, with generous breathing room.
- One large, dominant, scientifically accurate vector illustration in the centre.
- Use precise callout lines and clear labels placed close to the relevant parts.
- Include the exact concept name as a large visible top-left heading, plus at least FOUR meaningful explanatory labels (the heading does not count).
- Use elegant, readable typography; avoid tiny text and crowded annotations.
- A small concise formula or relationship may appear only when it is essential to the concept.
- Use subtle purposeful motion (e.g. a softly moving current marker, orbiting particle,
  photosynthesis light pulse, or gentle highlight). Animation must explain, not distract.
- The SVG should look like a carefully designed textbook illustration, not a UI screenshot.

DO NOT include:
- Product branding, logos, watermarks, badges, chips, numbered key-idea labels or footers.
- A "Science Diagram Maker" heading or any app/interface chrome.
- "Maths · GCSE", "Key Idea 01", "Explore the diagram", "Explore the triangle",
  introductory paragraphs, worked numerical examples, practice questions or solved calculations.
- Unrelated decorative icons, stock-image placeholders, photorealistic textures or 3D effects.
- Extra explanatory prose outside the illustration itself.

SVG ENGINEERING CONTRACT:
- Return ONLY one complete SVG document. No Markdown fences, commentary or JSON wrapper.
- Root element must be <svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">.
- Include non-empty <title> and <desc> elements for accessibility.
- Also render the exact topic name visibly as a large top-left <text> heading; keep it separate from the explanatory labels.
- Use at least FOUR additional visible <text> labels that identify real parts/processes.
- Include at least one real CSS animation (@keyframes + animation declaration) or SMIL animation attached to visible elements.
- Keep every shape, stroke and text anchor inside the viewBox; keep a comfortable 28px inset.
- Use only these visual elements: g, rect, circle, ellipse, line, polygon, polyline, text, tspan,
  title, desc, defs, style, linearGradient, radialGradient, stop, animate, set.
- Do not use path, use, image, foreignObject, script, filters, masks, clipPath, external resources,
  JavaScript, event-handler attributes, or transform attributes. No external fonts or URLs.
- Do not use CSS transforms. Use opacity, stroke-dashoffset, stroke-width, fill, stroke, or
  controlled particle coordinates (cx, cy, x, y) with explicit bounded keyframes for motion.
- Put explicit x, y and font-size attributes on each <text>; set textLength where practical. Use explicit stroke-width attributes.
- Draw with simple geometric primitives so a program can validate all bounds deterministically.
- Keep the full SVG reasonably compact (preferably under 35 KB).
""".strip()

CONCEPT_STRUCTURAL_GUIDELINES: dict[str, str] = {
    "pythagoras": """
GEOMETRIC SPECIFICATION FOR PYTHAGORAS' THEOREM:
- Draw a true right-angled triangle using <polygon id="right_triangle" points="360,220 360,420 600,420" class="triangle-fill" /> and <polygon points="360,220 360,420 600,420" class="triangle-border" />.
  Right-angle vertex at (360, 420), top vertex at (360, 220), right vertex at (600, 420). Side a = 200 (vertical), side b = 240 (horizontal), side c = 312.4 (hypotenuse).
  The vectors at (360, 420) are strictly orthogonal, and a² + b² = c² holds exactly (200² + 240² = 40000 + 57600 = 97600 = 312.41²).
- Place a right-angle square marker near the corner: <polyline points="360,395 385,395 385,420" stroke="#244638" stroke-width="2" fill="none" />.
- Place side square representations:
  - Square on side a (left): <rect x="220" y="220" width="140" height="200" fill="#C8D96B" opacity="0.2" stroke="#8FA58A" stroke-width="1.5" />.
  - Square on side b (bottom): <rect x="360" y="420" width="240" height="140" fill="#C8D96B" opacity="0.2" stroke="#8FA58A" stroke-width="1.5" />.
- Label the hypotenuse clearly near the midpoint of side c (x ≈ 540, y ≈ 300) with callout and label 'Hypotenuse (c)'.
- Label 'Right angle' near (280, 450) with callout to (372, 407).
- Label 'Side a' near (250, 320) and 'Side b' near (480, 560).
- Display the formula relationship 'a² + b² = c²' in a callout box at x: 660..900, y: 350..460.
- DUAL ANIMATION SPECIFICATION:
  1. MAJOR ANIMATION: Continuous animated pulse along the hypotenuse side c demonstrating the relationship:
     <line x1="360" y1="220" x2="600" y2="420" stroke="#C8D96B" stroke-width="8" stroke-linecap="round">
       <animate attributeName="opacity" values="0.3;1;0.3" dur="3s" repeatCount="indefinite" />
     </line>
  2. SECONDARY ANIMATION: Supporting pulse on the formula equation box or side squares:
     <rect x="660" y="350" width="240" height="110" rx="8" fill="#244638">
       <animate attributeName="stroke" values="#244638;#C8D96B;#244638" dur="3s" repeatCount="indefinite" />
     </rect>
- Keep all coordinates safely inside the canvas with >= 30px margins (40 <= x <= 920, 40 <= y <= 600).
""".strip(),
    "circle": """
GEOMETRIC SPECIFICATION FOR CIRCLE THEOREMS / CIRCLE GEOMETRY:
- Main circle: <circle id="main_circle" cx="480" cy="340" r="180" fill="#C8D96B" fill-opacity="0.12" stroke="#244638" stroke-width="3" />. Strictly use <circle>, never <ellipse>.
- Circle centre: <circle id="circle_centre" cx="480" cy="340" r="5" fill="#244638" />. Label 'Centre' placed at (450, 380).
- Diameter line: Horizontal line spanning across the entire circle through the centre:
  <line id="diameter_line" x1="300" y1="340" x2="660" y2="340" stroke="#244638" stroke-width="2.5" /> (length = 360 = 2r).
  Place label 'Diameter (2r)' near (380, 325).
- Radius line: Angled line starting at the centre (480, 340) and terminating on the circumference at (607, 213) (45° angle, length ≈ 180 = r):
  <line id="radius_line" x1="480" y1="340" x2="607" y2="213" stroke="#244638" stroke-width="2.5" />.
  Place label 'Radius (r)' near (550, 260).
- Circumference callout leader line:
  The leader line must anchor directly on the circumference at (607, 467) (angle 45°: cx + r*cos(45°), cy + r*sin(45°)):
  <line x1="607" y1="467" x2="720" y2="520" stroke="#8FA58A" stroke-width="1.5" stroke-dasharray="4,4" />
  <circle cx="607" cy="467" r="4" fill="#244638" />
  Place label 'Circumference' at (730, 525).
- Formula callout box:
  <rect x="700" y="160" width="200" height="80" rx="6" fill="#F7F4E9" stroke="#8FA58A" stroke-width="1.5" />
  <text x="735" y="195" font-weight="bold">Diameter formula</text>
  <text x="760" y="225" font-weight="bold">d = 2r</text>
- DUAL ANIMATION SPECIFICATION:
  1. MAJOR ANIMATION: Progressive circumference boundary tracing using stroke-dashoffset (perimeter 2*pi*180 ≈ 1131):
     <circle cx="480" cy="340" r="180" fill="none" stroke="#C8D96B" stroke-width="4" stroke-dasharray="1131" stroke-dashoffset="1131">
       <animate attributeName="stroke-dashoffset" values="1131;0;1131" dur="4s" repeatCount="indefinite" />
     </circle>
  2. SECONDARY ANIMATION: Animated highlight pulse along the radius line:
     <line id="radius_line" x1="480" y1="340" x2="607" y2="213" stroke="#244638" stroke-width="3">
       <animate attributeName="opacity" values="0.4;1;0.4" dur="2.5s" repeatCount="indefinite" />
     </line>
- Required visible terms: 'centre' (or 'center'), 'radius', 'diameter', 'circumference'. Keep labels concise (1 to 4 words).
- All coordinates must remain inside 960x640 with at least 30px margin (30 <= x <= 920, 30 <= y <= 610).
""".strip(),
    "series-circuit": """
GEOMETRIC SPECIFICATION FOR SERIES CIRCUIT:
- Single continuous closed electrical loop:
  Draw the circuit loop as a single rounded rectangle wire:
  <rect id="circuit_loop" x="180" y="160" width="600" height="320" rx="16" stroke="#244638" stroke-width="4" fill="none" />
- DC Cell / Battery: Centered on the left vertical wire branch at (180, 320):
  <g id="battery">
    <rect x="156" y="285" width="48" height="70" fill="#F7F4E9" stroke="#244638" stroke-width="2" rx="4" />
    <line x1="168" y1="305" x2="192" y2="305" stroke="#244638" stroke-width="4" />
    <line x1="174" y1="320" x2="186" y2="320" stroke="#244638" stroke-width="2" />
    <line x1="168" y1="335" x2="192" y2="335" stroke="#244638" stroke-width="4" />
    <line x1="174" y1="350" x2="186" y2="350" stroke="#244638" stroke-width="2" />
    <text x="140" y="275" font-weight="bold">+</text>
    <text x="140" y="375" font-weight="bold">-</text>
  </g>
- Series Components: Connect two bulb/lamp symbols in series along the top wire:
  - Lamp 1 at (380, 160): <g id="lamp1"><circle cx="380" cy="160" r="18" fill="#F7F4E9" stroke="#244638" stroke-width="3" /><line x1="367" y1="147" x2="393" y2="173" stroke="#244638" stroke-width="2" /><line x1="393" y1="147" x2="367" y2="173" stroke="#244638" stroke-width="2" /></g>
  - Lamp 2 at (580, 160): <g id="lamp2"><circle cx="580" cy="160" r="18" fill="#F7F4E9" stroke="#244638" stroke-width="3" /><line x1="567" y1="147" x2="593" y2="173" stroke="#244638" stroke-width="2" /><line x1="593" y1="147" x2="567" y2="173" stroke="#244638" stroke-width="2" /></g>
- DUAL ANIMATION SPECIFICATION:
  1. MAJOR ANIMATION: Continuous moving charge indicators along the actual continuous wire loop (animated stroke-dashoffset):
     <rect x="180" y="160" width="600" height="320" rx="16" stroke="#C8D96B" stroke-width="4" fill="none" stroke-dasharray="16, 24" class="animated-flow">
       <animate attributeName="stroke-dashoffset" from="0" to="-80" dur="2s" repeatCount="indefinite" />
     </rect>
     NEVER use detached moving dots. The animation must visibly follow the actual rectangular wire loop path.
  2. SECONDARY ANIMATION: Simultaneous bulb illumination glow pulse on both lamps:
     <circle cx="380" cy="160" r="24" fill="#C8D96B">
       <animate attributeName="opacity" values="0.1;0.5;0.1" dur="2s" repeatCount="indefinite" />
     </circle>
     <circle cx="580" cy="160" r="24" fill="#C8D96B">
       <animate attributeName="opacity" values="0.1;0.5;0.1" dur="2s" repeatCount="indefinite" />
     </circle>
- Explanatory Labels (keep concise, well within canvas bounds):
  - Bottom callout: 'Only one closed loop' at (380, 540) pointing to bottom wire at (480, 480).
  - Top callout: 'Current (I) is the same everywhere in the loop' at (240, 105).
  - Component callout: 'Voltage is shared between components' at (440, 70).
  - Cell callout: 'Cell / Power source' at (60, 320) pointing to battery at (156, 320).
- Required terms: 'one loop', 'current', 'voltage', 'cell'. All labels must stay strictly within x: 40..890, y: 40..600.
""".strip(),
    "photosynthesis": """
GEOMETRIC SPECIFICATION FOR PHOTOSYNTHESIS:
- Central Leaf / Reaction Site:
  Represent the leaf reaction site using a green ellipse:
  <ellipse id="leaf" class="leaf" cx="480" cy="340" rx="160" ry="105" fill="#8FA58A" stroke="#244638" stroke-width="3" />
  Internal leaf veins: <line x1="360" y1="340" x2="600" y2="340" stroke="#244638" stroke-width="3" /> plus diagonal branch lines.
  Label 'Chlorophyll in leaf absorbs light' placed centrally inside or directly above the leaf.
- Directed Inputs (arrows pointing inward toward the leaf centre at (480, 340)):
  - Sunlight: From top-left (200, 160) pointing toward leaf at (380, 270):
    <line id="light_in" x1="200" y1="160" x2="380" y2="270" stroke="#244638" stroke-width="3" />
    Sun graphic: <circle cx="180" cy="150" r="24" fill="#C8D96B" class="sun-glow" />
    Label 'Light energy / Sunlight' at (90, 140).
  - Carbon dioxide: From left (180, 340) pointing into leaf at (320, 340):
    <line id="co2_in" x1="180" y1="340" x2="320" y2="340" stroke="#244638" stroke-width="3" />
    Label 'Carbon dioxide (CO₂)' at (60, 335).
  - Water: From bottom-left (220, 500) pointing into leaf at (380, 410):
    <line id="h2o_in" x1="220" y1="500" x2="380" y2="410" stroke="#244638" stroke-width="3" />
    Label 'Water (H₂O)' at (120, 520).
- Directed Outputs (arrows pointing outward away from the leaf centre):
  - Glucose: From top-right of leaf (580, 270) pointing out to (680, 180):
    <line id="glucose_out" x1="580" y1="270" x2="680" y2="180" stroke="#244638" stroke-width="3" />
    Label 'Glucose (C₆H₁₂O₆)' at (690, 175) with textLength="140" lengthAdjust="spacingAndGlyphs".
  - Oxygen: From right of leaf (640, 340) pointing out to (720, 340):
    <line id="oxygen_out" x1="640" y1="340" x2="720" y2="340" stroke="#244638" stroke-width="3" />
    Label 'Oxygen (O₂)' at (730, 340) with textLength="90" lengthAdjust="spacingAndGlyphs".
- Summary Equation Box:
  <rect x="300" y="550" width="360" height="40" rx="6" fill="#1D2C25" />
  <text x="330" y="575" fill="#F7F4E9" font-weight="bold">6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂</text>
- DUAL ANIMATION SPECIFICATION:
  1. MAJOR ANIMATION: Continuous animated light energy / photon flow from sun into leaf:
     <line x1="200" y1="160" x2="380" y2="270" stroke="#C8D96B" stroke-width="4" stroke-dasharray="8, 12">
       <animate attributeName="stroke-dashoffset" from="40" to="0" dur="1.5s" repeatCount="indefinite" />
     </line>
  2. SECONDARY ANIMATION: Sun pulse glow and chloroplast reaction site energy pulse:
     <circle cx="180" cy="150" r="24" fill="#C8D96B">
       <animate attributeName="opacity" values="0.3;0.9;0.3" dur="2.5s" repeatCount="indefinite" />
     </circle>
  CRITICAL ANIMATION RULE: Only animate 'opacity', 'stroke-dashoffset', 'cx', or 'cy'. NEVER animate 'r', 'rx', 'ry', 'width', or 'height'.
- Required terms: 'carbon dioxide', 'water', 'light', 'chlorophyll', 'glucose', 'oxygen'.
- CRITICAL BOUNDS BUDGET: All right-side text must start at x <= 730 and end before x = 910. Keep labels strictly to 1 to 3 words. All elements strictly inside 960x640 with >= 30px margin.
""".strip(),
    "states-of-matter": """
GEOMETRIC SPECIFICATION FOR STATES OF MATTER:
- Draw three horizontal, non-overlapping containers:
  - Solid: <rect id="solid_container" x="50" y="140" width="260" height="280" rx="12" fill="#F7F4E9" stroke="#244638" stroke-width="2.5" /> with label 'Solid' at (150, 175).
  - Liquid: <rect id="liquid_container" x="350" y="140" width="260" height="280" rx="12" fill="#F7F4E9" stroke="#244638" stroke-width="2.5" /> with label 'Liquid' at (450, 175).
  - Gas: <rect id="gas_container" x="650" y="140" width="260" height="280" rx="12" fill="#F7F4E9" stroke="#244638" stroke-width="2.5" /> with label 'Gas' at (760, 175).
- Particle Arrangement & Spacing Requirements:
  - Solid: Draw 12 particles (<circle class="solid_particle" r="14" ...>) in a regular 3x4 lattice (3 rows, 4 columns: cx at 110, 150, 190, 230; cy at 240, 280, 320). Spacing = 40px, low spacing variance (< 40%).
    Vibrating in place: animate using SMIL <animate attributeName="cx" values="110;113;107;110" dur="0.8s" repeatCount="indefinite" />.
  - Liquid: Draw 10 to 12 particles (<circle class="liquid_particle" r="14" ...>) packed close together with mean spacing ≈ 42px (<= 2.2x solid spacing), mobile, sliding past each other.
    Use smooth motion animation on liquid particles sliding past others (animate cx from 475 to 495 to 475, cy from 265 to 280 to 265).
  - Gas: Draw 4 to 5 particles (<circle class="gas_particle" r="14" ...>) spaced widely apart throughout the container.
    Target mean spacing >= 85px (MUST be >= 2.2x solid spacing).
    Rapidly moving darting animations across the container: animate cx and cy using SMIL (e.g. values="690;820;710;690" dur="2.2s").
- DUAL ANIMATION SPECIFICATION:
  1. MAJOR ANIMATION: Three distinct particle motions (solid vibration in lattice, liquid sliding, gas rapid 2D darting).
  2. SECONDARY ANIMATION: Animated temperature transition arrow showing increasing kinetic energy from Solid to Gas:
     <line x1="80" y1="530" x2="880" y2="530" stroke="#244638" stroke-width="2" stroke-dasharray="12, 8">
       <animate attributeName="stroke-dashoffset" from="40" to="0" dur="2s" repeatCount="indefinite" />
     </line>
- Explanatory Callouts (at bottom):
  - Solid: 'Particles close together' at (60, 480) with textLength="200" lengthAdjust="spacingAndGlyphs".
  - Liquid: 'Particles close, moving past' at (360, 480) with textLength="200" lengthAdjust="spacingAndGlyphs".
  - Gas: 'Particles far apart' at (660, 480) with textLength="160" lengthAdjust="spacingAndGlyphs".
- Required terms: 'solid', 'liquid', 'gas', 'particles', 'vibrate'.
- CRITICAL ANIMATION RULE: NEVER use transform: translate(). Only animate cx, cy, opacity, or stroke-dashoffset with SMIL <animate>.
- Keep all coordinates safely inside x: 40..910, y: 40..600. All text elements on Gas container must end before x = 910.
""".strip(),
}


def build_generation_prompt(concept: dict[str, Any], failure_reasons: list[str] | None = None) -> str:
    """Create the first-pass prompt or the single validation-repair prompt."""
    sections = [
        "You are a precise scientific illustrator creating an animated SVG for UK GCSE learners.",
        f"CONCEPT: {concept['name']}",
        f"SUBJECT: {concept['subject']}",
        "SOURCE CONTENT (preserve its meaning exactly; do not invent facts):",
        concept["source_text"],
        STYLE_CONTRACT,
    ]

    concept_id = concept.get("id", "")
    if concept_id in CONCEPT_STRUCTURAL_GUIDELINES:
        sections.append(CONCEPT_STRUCTURAL_GUIDELINES[concept_id])

    if failure_reasons:
        sections.extend([
            "\nVALIDATION REPAIR — this is the one permitted corrective generation.",
            "The previous SVG did not pass these code checks:",
            *[f"- {reason}" for reason in failure_reasons],
            "Return a complete corrected SVG. Fix every listed failure while preserving the same",
            "scientific meaning and the requested visual art direction. Do not merely describe the fix.",
        ])
    else:
        sections.append(
            "Create the first SVG attempt. Prioritise correct scientific relationships and legible labels."
        )

    return "\n\n".join(sections)


MANDATORY_ANIMATION_REQUIREMENTS: dict[str, str] = {
    "pythagoras": (
        "MANDATORY ANIMATION REQUIREMENT FOR PYTHAGORAS: "
        "Visible side tracing or prominent hypotenuse pulse highlight along side c. "
        "1. MAJOR ANIMATION: Prominent, visible pulse along the hypotenuse (side c) demonstrating the geometric relation.\n"
        "2. SECONDARY ANIMATION: Supporting pulse on the formula equation box or side squares (a² + b² = c²).\n"
        "Both animations must loop smoothly (2s to 4s) using safe attributes (opacity, stroke, stroke-dashoffset)."
    ),
    "circle": (
        "MANDATORY ANIMATION REQUIREMENT FOR CIRCLE:\n"
        "1. MAJOR ANIMATION: Smooth progressive tracing of the circumference using animated stroke-dashoffset (0 to 360 degrees).\n"
        "2. SECONDARY ANIMATION: Animated highlight pulse along the radius line (r) or diameter line (2r) with formula sync.\n"
        "Both animations must loop smoothly using safe attributes."
    ),
    "series-circuit": (
        "MANDATORY ANIMATION REQUIREMENT FOR SERIES CIRCUIT:\n"
        "1. MAJOR ANIMATION: Continuous electrical current flow animation visibly travelling along the actual continuous wire loop path using animated stroke-dashoffset (no detached dots).\n"
        "2. SECONDARY ANIMATION: Simultaneous illumination glow pulse on both lamps/bulbs.\n"
        "Both animations must loop smoothly."
    ),
    "photosynthesis": (
        "MANDATORY ANIMATION REQUIREMENT FOR PHOTOSYNTHESIS:\n"
        "1. MAJOR ANIMATION: Continuous animated light energy / photon flow indicators from the sun entering the leaf reaction site.\n"
        "2. SECONDARY ANIMATION: Pulsing sun glow and chloroplast reaction site energy conversion glow.\n"
        "Only animate opacity or stroke-dashoffset; never animate radius or dimensions."
    ),
    "states-of-matter": (
        "MANDATORY ANIMATION REQUIREMENT FOR STATES OF MATTER:\n"
        "1. MAJOR ANIMATION: Distinct, visible particle dynamics across all three states (rapid in-place vibration in solid, smooth sliding in liquid, high-speed 2D darting in gas).\n"
        "2. SECONDARY ANIMATION: Flowing temperature transition arrow showing increasing kinetic energy from Solid to Gas.\n"
        "Never use transform: translate(); animate cx/cy and stroke-dashoffset directly."
    ),
}


def build_feedback_regeneration_prompt(
    concept: dict[str, Any],
    previous_svg: str,
    user_feedback: str,
    failure_reasons: list[str] | None = None,
    visual_quality_issues: list[str] | None = None,
) -> str:
    """Build the revision prompt incorporating user rejection feedback and prior SVG."""
    concept_id = concept.get("id", "")
    anim_req = MANDATORY_ANIMATION_REQUIREMENTS.get(
        concept_id,
        "MANDATORY ANIMATION REQUIREMENT: Produce visible, purposeful motion that directly explains the scientific concept."
    )

    sections = [
        "You are an expert scientific illustrator revising an educational SVG diagram for UK GCSE learners.",
        f"CONCEPT: {concept['name']}",
        f"SUBJECT: {concept['subject']}",
        "SOURCE CONTENT (preserve its meaning exactly; do not invent facts):",
        concept["source_text"],
        STYLE_CONTRACT,
    ]

    if concept_id in CONCEPT_STRUCTURAL_GUIDELINES:
        sections.append(CONCEPT_STRUCTURAL_GUIDELINES[concept_id])

    sections.append(f"ANIMATION SPECIFICATION:\n{anim_req}")

    review_block = [
        "HUMAN EDUCATOR REJECTION FEEDBACK — REVISION REQUIRED:",
        f"The previous version of this diagram was reviewed and REJECTED with this feedback:",
        f'"{user_feedback.strip()}"',
        "",
        "EXPLICIT REVISION MANDATE:",
        "1. CORRECT THE DEFECTS: Directly resolve the specific issues described in the feedback above.",
        "2. PRESERVE ACCURATE GEOMETRY: Retain all scientifically correct geometric relationships and formulas.",
        "3. DO NOT DUPLICATE: Do not simply reproduce the previous SVG; improve visual composition, label spacing, and clarity.",
        "4. IMPROVE LABEL PLACEMENT: Ensure leader lines connect directly to target elements, labels do not collide or obscure geometry, and all text has comfortable margins (>= 28px) inside the viewBox.",
        "5. VISIBLE MEANINGFUL ANIMATION: Ensure animation is immediately noticeable, concept-specific, and smoothly animated. Only animate 'opacity', 'stroke-dashoffset', 'cx', or 'cy'. NEVER animate 'r', 'rx', 'ry', 'width', or 'height'. NEVER use CSS transform: translate.",
        "6. SATISFY ALL SIX MANDATORY QUALITY GATES:",
        "   - valid_svg: Well-formed XML with safe elements only.",
        "   - within_viewbox: All strokes, shapes, and text anchors inside 0 0 960 640.",
        "   - title_and_labels: Visible topic heading + at least 4 explanatory labels.",
        "   - has_animation: Real SMIL or CSS keyframes animation attached to visible elements.",
        "   - scientific_terms: Required scientific vocabulary present verbatim in visible text.",
        "   - concept_structure: Accurate geometric/physical constraints for this concept.",
    ]
    sections.append("\n".join(review_block))

    if failure_reasons:
        sections.append(
            "PREVIOUS VALIDATION FAILURES TO PREVENT:\n"
            + "\n".join(f"- {r}" for r in failure_reasons)
        )

    if visual_quality_issues:
        sections.append(
            "PREVIOUS VISUAL QUALITY ISSUES TO RESOLVE:\n"
            + "\n".join(f"- {i}" for i in visual_quality_issues)
        )

    if previous_svg:
        clean_svg = previous_svg.strip()
        sections.append(f"PREVIOUS REJECTED SVG (FOR REFERENCE & CORRECTION):\n```xml\n{clean_svg}\n```")

    sections.append(
        "Return ONLY the complete corrected SVG document. No markdown fences, no explanatory text, no commentary."
    )

    return "\n\n".join(sections)

