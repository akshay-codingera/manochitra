from app.validators.svg_validator import extract_svg, validate_svg
from conftest import make_valid_svg


def test_valid_svg_passes_all_five_checks(pythagoras_concept):
    report = validate_svg(make_valid_svg(pythagoras_concept), pythagoras_concept)
    assert report.passed
    assert set(report.checks) == {
        "valid_svg", "within_viewbox", "title_and_labels", "has_animation", "scientific_terms"
    }


def test_extract_svg_removes_markdown_fence():
    source = 'Here you go:\n```svg\n<svg xmlns="http://www.w3.org/2000/svg"></svg>\n```'
    assert extract_svg(source).startswith('<svg xmlns=')
    assert extract_svg(source).endswith('</svg>')


def test_malformed_xml_fails(pythagoras_concept):
    report = validate_svg('<svg><text>unclosed</svg>', pythagoras_concept)
    assert not report.checks["valid_svg"].passed


def test_missing_viewbox_fails(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(' viewBox="0 0 960 640"', '')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed


def test_out_of_bounds_circle_fails(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace('</svg>', '<circle cx="980" cy="250" r="30" /></svg>')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed


def test_four_labels_required(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept)
    start = source.index('<text x="100"')
    end = source.index('</svg>')
    title_and_shapes = source[:start]
    tail = source[end:]
    one_label = '<text x="100" y="120" font-size="16">hypotenuse</text>\n'
    source = title_and_shapes + one_label + tail
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["title_and_labels"].passed


def test_no_animation_fails(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept)
    source = source.replace('<style>@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }.pulse { animation: pulse 2s infinite; }</style>', '')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["has_animation"].passed


def test_script_element_is_rejected(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace('</svg>', '<script>alert(1)</script></svg>')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["valid_svg"].passed


def test_scientific_terms_check_fails_when_terms_missing(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace('hypotenuse', 'longest side').replace('a²', 'side one')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["scientific_terms"].passed


def test_all_five_concepts_can_pass_with_matching_terminology(valid_svg_factory):
    from app.core.concepts import CONCEPTS

    for concept in CONCEPTS:
        report = validate_svg(valid_svg_factory(concept), concept)
        assert report.passed, f"{concept['name']}: {report.failures}"


def test_negative_circle_radius_is_rejected(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace('r="14"', 'r="-14"')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed


def test_heading_must_be_in_the_top_left_region(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '<text x="40" y="65" font-size="28">',
        '<text x="520" y="65" font-size="28">',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["title_and_labels"].passed
    assert "top-left region" in report.checks["title_and_labels"].detail


def test_hidden_text_does_not_count_as_explanatory_labels(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        'font-size="16"', 'font-size="16" opacity="0"'
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["title_and_labels"].passed
    assert "visible explanatory text labels" in report.checks["title_and_labels"].detail


def test_accessible_description_is_required(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '<desc>Fixture used for validator tests.</desc>', ''
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["title_and_labels"].passed
    assert "<desc>" in report.checks["title_and_labels"].detail


def test_smil_animation_cannot_change_geometry(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '</svg>',
        '<circle cx="700" cy="300" r="10"><animate attributeName="r" values="10;90" dur="2s" repeatCount="indefinite" /></circle></svg>',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["has_animation"].passed
    assert "change geometry" in report.checks["has_animation"].detail


def test_css_animation_cannot_change_geometry(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }',
        '@keyframes pulse { from { r: 10; } to { r: 900; } }',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["has_animation"].passed
    assert "geometry or bounds" in report.checks["has_animation"].detail


def test_hidden_text_does_not_satisfy_scientific_terminology(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept)
    source = source.replace(
        '<text x="100" y="105" font-size="16">hypotenuse</text>',
        '<text x="100" y="105" font-size="16" opacity="0">hypotenuse</text>',
    ).replace(
        '<text x="100" y="140" font-size="16">right angle</text>',
        '<text x="100" y="140" font-size="16" opacity="0">right angle</text>',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["scientific_terms"].passed


def test_unsafe_css_animation_is_not_ignored_when_safe_smil_is_also_present(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '<circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b" />',
        '<circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b"><animate attributeName="opacity" values="0.5;1" dur="2s" repeatCount="indefinite" /></circle>',
    ).replace(
        '@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }',
        '@keyframes pulse { from { r: 1; } to { r: 900; } }',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["has_animation"].passed
    assert "geometry or bounds" in report.checks["has_animation"].detail


def test_bounded_particle_coordinate_animation_passes(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace(
        '@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }',
        '@keyframes pulse { 0% { cx: 300; cy: 250; } 50% { cx: 320; cy: 260; } 100% { cx: 300; cy: 250; } }',
    )
    report = validate_svg(source, pythagoras_concept)
    assert report.checks["has_animation"].passed
    assert report.checks["within_viewbox"].passed


def test_particle_coordinate_animation_exceeding_viewbox_fails(pythagoras_concept):
    # viewBox width is 960, animated cx goes to 980 with r=14 -> exceeds 960
    source = make_valid_svg(pythagoras_concept).replace(
        '@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }',
        '@keyframes pulse { 0% { cx: 300; } 50% { cx: 980; } 100% { cx: 300; } }',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed
    assert "bounds" in report.checks["within_viewbox"].detail


def test_stroke_width_pulse_exceeding_viewbox_fails(pythagoras_concept):
    # circle at cx="945" cy="250" r="10" has static right = 955 < 960.
    # animated stroke-width reaches 40 (pad = 20) -> right = 945 + 10 + 20 = 975 > 960!
    source = make_valid_svg(pythagoras_concept).replace(
        '<circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b" />',
        '<circle class="pulse" cx="945" cy="250" r="10" stroke="#c8d96b" stroke-width="2" />',
    ).replace(
        '@keyframes pulse { from { opacity: .5; } to { opacity: 1; } }',
        '@keyframes pulse { 0% { stroke-width: 2; } 50% { stroke-width: 40; } 100% { stroke-width: 2; } }',
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed


def test_xml_doctype_is_rejected(pythagoras_concept):
    source = '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n' + make_valid_svg(pythagoras_concept)
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["valid_svg"].passed
    assert "DOCTYPE" in report.checks["valid_svg"].detail


def test_xml_entity_is_rejected(pythagoras_concept):
    source = make_valid_svg(pythagoras_concept).replace('<svg', '<!ENTITY xxe SYSTEM "file:///etc/passwd"><svg')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["valid_svg"].passed


def test_unattached_css_animation_fails(pythagoras_concept):
    # CSS keyframes exist, but no element uses .pulse or animation property
    source = make_valid_svg(pythagoras_concept).replace(
        '<circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b" />',
        '<circle cx="300" cy="250" r="14" fill="#c8d96b" />',
    ).replace('.pulse { animation: pulse 2s infinite; }', '')
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["has_animation"].passed
    assert "not attached" in report.checks["has_animation"].detail


def test_negative_viewbox_origin_handled(pythagoras_concept):
    # viewBox="-50 -50 1020 700", valid bounds from -50 to 970 and -50 to 650
    source = make_valid_svg(pythagoras_concept).replace(
        'viewBox="0 0 960 640"', 'viewBox="-50 -50 1020 700"'
    ).replace(
        '</svg>', '<circle cx="-40" cy="0" r="5" fill="#fff" /></svg>'
    )
    report = validate_svg(source, pythagoras_concept)
    assert report.checks["within_viewbox"].passed

    # circle at cx="-55" r="5" -> left is -60 < -50
    out_source = source.replace('cx="-40"', 'cx="-55"')
    out_report = validate_svg(out_source, pythagoras_concept)
    assert not out_report.checks["within_viewbox"].passed


def test_pythagoras_overflow_rectangle_regression_fails(pythagoras_concept):
    """Regression test: rectangle at x=360, y=420, width=600, height=240 (bottom coordinate=660) exceeds viewBox (height=640)."""
    source = make_valid_svg(pythagoras_concept).replace(
        '</svg>', '<rect x="360" y="420" width="600" height="240" fill="#8fa58a" /></svg>'
    )
    report = validate_svg(source, pythagoras_concept)
    assert not report.checks["within_viewbox"].passed
    assert "exceed the viewBox" in report.checks["within_viewbox"].detail


