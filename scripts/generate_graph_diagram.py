"""Generate a visual diagram of the LangGraph navigation graph.

Saves two files to docs/:
  - navigation_graph.png  (via mermaid.ink API — requires internet)
  - navigation_graph.mmd  (Mermaid source, always saved as fallback)

Usage:
    python scripts/generate_graph_diagram.py
"""
from pathlib import Path

from waraq.navigation.graph import build_graph

DOCS_DIR = Path(__file__).parent.parent / "docs"


def main() -> None:
    graph = build_graph()
    mermaid_src = graph.get_graph().draw_mermaid()

    mmd_path = DOCS_DIR / "navigation_graph.mmd"
    mmd_path.write_text(mermaid_src, encoding="utf-8")
    print(f"Mermaid source → {mmd_path}")

    png_path = DOCS_DIR / "navigation_graph.png"
    try:
        png_bytes = graph.get_graph().draw_mermaid_png()
        png_path.write_bytes(png_bytes)
        print(f"PNG diagram   → {png_path}")
    except Exception as exc:
        print(f"PNG generation failed ({exc}); Mermaid source saved as fallback.")


if __name__ == "__main__":
    main()
