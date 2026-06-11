from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUALIZATION_DIR = ROOT / "s3fifo_visualization"


def test_s3fifo_visualization_static_assets_exist_and_are_linked():
    html = (VISUALIZATION_DIR / "index.html").read_text(encoding="utf-8")

    assert "How does S3-FIFO work?" in html
    assert 'href="styles.css"' in html
    assert 'src="script.js"' in html
    assert "Small FIFO · S" in html
    assert "Main FIFO · M" in html
    assert "Ghost FIFO · G" in html


def test_s3fifo_visualization_script_models_three_static_queues():
    script = (VISUALIZATION_DIR / "script.js").read_text(encoding="utf-8")

    assert "small: 3" in script
    assert "main: 7" in script
    assert "ghost: 7" in script
    assert "drainSmall" in script
    assert "drainMain" in script
    assert "pushGhost" in script
    assert "Math.min(3" in script
