from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUALIZATION_DIR = ROOT / "s3fifo_visualization"


def test_s3fifo_visualization_static_assets_exist_and_are_linked():
    html = (VISUALIZATION_DIR / "index.html").read_text(encoding="utf-8")

    assert "How does S3-FIFO work?" in html
    assert 'href="styles.css"' in html
    assert 'src="script.js"' in html
    assert "Small FIFO" in html
    assert "Main FIFO" in html
    assert "Ghost FIFO" in html
    assert "FIFO Tail / In" in html
    assert "FIFO Head / Out" in html


def test_s3fifo_visualization_exposes_required_controls_and_metrics():
    html = (VISUALIZATION_DIR / "index.html").read_text(encoding="utf-8")

    for label in [
        "Play",
        "Pause",
        "Step",
        "Previous Step",
        "Reset",
        "Random Trace",
        "Cache Capacity",
        "Small Queue Ratio",
        "Ghost Capacity",
        "Frequency Cap",
    ]:
        assert label in html

    for metric in [
        "Total Requests",
        "Hits",
        "Misses",
        "Hit Ratio",
        "Evictions",
        "Ghost Hits",
        "Current Request",
        "Current Event",
    ]:
        assert metric in html


def test_s3fifo_visualization_script_models_stepwise_animation_safely():
    script = (VISUALIZATION_DIR / "script.js").read_text(encoding="utf-8")

    assert "planRequest" in script
    assert "previousStep" in script
    assert "state.isAnimating" in script
    assert "lockDuringAnimation" in script
    assert "smallToMain" in script
    assert "smallToGhost" in script
    assert "mainReinsert" in script
    assert "ghostHit" in script
    assert "Trace must contain at least one request key" in script


def test_s3fifo_visualization_accessibility_and_responsive_styles():
    html = (VISUALIZATION_DIR / "index.html").read_text(encoding="utf-8")
    styles = (VISUALIZATION_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'aria-label="Play simulation"' in html
    assert 'aria-label="Pause simulation"' in html
    assert 'aria-label="Advance one animation step"' in html
    assert "prefers-reduced-motion" in styles
    assert "overflow-x: auto" in styles
    assert "min-width: 72px" in styles


def test_s3fifo_visualization_uses_academic_figure_style():
    html = (VISUALIZATION_DIR / "index.html").read_text(encoding="utf-8")
    styles = (VISUALIZATION_DIR / "styles.css").read_text(encoding="utf-8")

    assert "Interactive Figure" in html
    assert "Figure 1." in html
    assert "paper-figure" in html
    assert 'font-family: "Times New Roman", Times, Georgia, serif' in styles
    assert "box-shadow: none" in styles
    assert "border-left: 4px solid var(--queue-color)" in styles
