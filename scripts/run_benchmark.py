"""
Benchmark runner — evaluates the full pipeline against data/benchmark_qa.json.

For each question the script runs:
  1. Navigation graph  (classify → navigate_level loop)
  2. Answer generation (generate_answer / generate_greeting / NOT_FOUND_ANSWER)

Output is written to data/benchmark_results.json with this shape per item:
  {
    "id":                  str,
    "question":            str,
    "status":              "found" | "not_found" | "rejected" | "greeting",
    "navigation_path":     list[str],
    "predicted_answer":    str,
    "predicted_citations": [{"node_id", "title", "pages": {"start", "end"}}],
    "reference_answer":    str,
    "reference_pages":     list[int],
    "reference_section_id": str
  }

Usage:
    python scripts/run_benchmark.py [--output PATH] [--ids bq_001 bq_002 ...]
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from waraq.generation.responder import NOT_FOUND_ANSWER, generate_answer, generate_greeting
from waraq.navigation.graph import build_graph

BENCHMARK_PATH = ROOT / "data" / "benchmark_qa.json"
INDEX_PATH = ROOT / "data" / "index.json"
MARKDOWN_DIR = ROOT / "data" / "parsed" / "markdown" / "pages"
DEFAULT_OUTPUT = ROOT / "data" / "benchmark_results.json"

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


def run_one(graph, index: dict, question: str) -> dict:
    """Run the full pipeline for a single question. Returns the result dict."""
    state = graph.invoke(
        {"original_query": question},
        config={"configurable": {"index": index, "markdown_dir": MARKDOWN_DIR}},
    )
    status: str = state.get("status", "")
    nav_path: list[str] = state.get("navigation_path") or []

    if status == "found":
        result = generate_answer(
            query=state.get("query") or question,
            leaf_content=state.get("leaf_content", ""),
            leaf_metadata=state.get("leaf_metadata", []),
        )
        if not result:
            return {
                "status": "error",
                "navigation_path": nav_path,
                "predicted_answer": "",
                "predicted_citations": [],
            }
        return {
            "status": status,
            "navigation_path": nav_path,
            "predicted_answer": result.get("answer", ""),
            "predicted_citations": result.get("citations", []),
        }
    elif status == "greeting":
        answer = generate_greeting(state.get("query") or question)
        return {
            "status": status,
            "navigation_path": nav_path,
            "predicted_answer": answer,
            "predicted_citations": [],
        }
    else:
        return {
            "status": status or "not_found",
            "navigation_path": nav_path,
            "predicted_answer": NOT_FOUND_ANSWER,
            "predicted_citations": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark evaluation")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="ID",
        help="Run only these benchmark IDs (e.g. bq_001 bq_030)",
    )
    args = parser.parse_args()

    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    if args.ids:
        id_set = set(args.ids)
        benchmark = [q for q in benchmark if q["id"] in id_set]
        if not benchmark:
            print(f"No matching IDs found in {BENCHMARK_PATH.name}", file=sys.stderr)
            sys.exit(1)

    graph = build_graph()
    results = []

    total = len(benchmark)
    for i, item in enumerate(benchmark, 1):
        qid = item["id"]
        question = item["question"]
        print(f"[{i}/{total}] {qid} ...", end=" ", flush=True)
        t0 = time.perf_counter()

        try:
            prediction = run_one(graph, index, question)
        except Exception as exc:
            log.exception("Error on %s", qid)
            prediction = {
                "status": "error",
                "navigation_path": [],
                "predicted_answer": f"ERROR: {exc}",
                "predicted_citations": [],
            }

        elapsed = time.perf_counter() - t0
        print(f"{prediction['status']} ({elapsed:.1f}s)")

        results.append({
            "id": qid,
            "question": question,
            **prediction,
            "reference_answer": item.get("answer", ""),
            "reference_pages": item.get("pages", []),
            "reference_section_id": item.get("section_id", ""),
        })

    output_path: Path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    print(f"\nWrote {len(results)} results → {output_path}")

    found = sum(1 for r in results if r["status"] == "found")
    pct = f"{100*found//total}%" if total else "n/a"
    print(f"Navigation: {found}/{total} found ({pct})")


if __name__ == "__main__":
    main()
