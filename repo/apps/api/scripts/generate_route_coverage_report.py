from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.main import create_app


@dataclass(frozen=True)
class RouteKey:
    method: str
    path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate API route-to-test coverage inventory from route-hit logs.")
    parser.add_argument("--hits-file", required=True, help="JSONL file written by HH_ROUTE_COVERAGE_FILE middleware")
    parser.add_argument("--output-json", required=True, help="Output JSON inventory path")
    parser.add_argument("--output-md", required=True, help="Output Markdown inventory path")
    return parser.parse_args()


def load_routes() -> list[RouteKey]:
    app = create_app()
    routes: set[RouteKey] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or not path.startswith("/api/v1"):
            continue
        methods = sorted(method for method in (route.methods or set()) if method not in {"HEAD", "OPTIONS"})
        for method in methods:
            routes.add(RouteKey(method=method, path=path))
    return sorted(routes, key=lambda item: (item.method, item.path))


def load_hits(hits_file: Path) -> tuple[dict[RouteKey, int], dict[RouteKey, set[str]], list[dict[str, str]]]:
    if not hits_file.exists():
        raise FileNotFoundError(f"Route-hit file not found: {hits_file}")

    counts: dict[RouteKey, int] = defaultdict(int)
    tests_by_route: dict[RouteKey, set[str]] = defaultdict(set)
    rows: list[dict[str, str]] = []

    for raw_line in hits_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        method = str(payload.get("method", "")).upper()
        route_path = str(payload.get("route_path", ""))
        if not method or not route_path:
            continue
        key = RouteKey(method=method, path=route_path)
        counts[key] += 1
        test_id = str(payload.get("test_id", "")).strip()
        if test_id:
            tests_by_route[key].add(test_id)
        rows.append(payload)

    return counts, tests_by_route, rows


def write_markdown(
    output_path: Path,
    *,
    total_routes: int,
    covered_routes: int,
    percentage: float,
    inventory_rows: list[dict[str, object]],
    unmatched_hits: list[dict[str, str]],
) -> None:
    lines: list[str] = []
    lines.append("# API Route Coverage Inventory")
    lines.append("")
    lines.append(f"- Total route surface: **{total_routes}**")
    lines.append(f"- Covered routes: **{covered_routes}**")
    lines.append(f"- Coverage percentage: **{percentage:.2f}%**")
    lines.append("")
    lines.append("## Route inventory")
    lines.append("")
    lines.append("| Method | Path | Covered | Hit Count | Example Tests |")
    lines.append("|---|---|---:|---:|---|")
    for row in inventory_rows:
        tests = row["example_tests"]
        if isinstance(tests, list):
            tests_label = "<br>".join(tests) if tests else "-"
        else:
            tests_label = "-"
        lines.append(
            f"| {row['method']} | `{row['path']}` | {('✅' if row['covered'] else '❌')} | {row['hit_count']} | {tests_label} |"
        )

    lines.append("")
    lines.append("## Unmatched hits")
    lines.append("")
    if not unmatched_hits:
        lines.append("No unmatched hit records.")
    else:
        lines.append("These hits did not map to a registered API route template:")
        lines.append("")
        for row in unmatched_hits:
            lines.append(
                f"- `{row.get('method', '')} {row.get('request_path', '')}` (route_path: `{row.get('route_path', '')}`)"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    hits_file = Path(args.hits_file)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    routes = load_routes()
    hit_counts, tests_by_route, raw_rows = load_hits(hits_file)
    route_set = set(routes)

    inventory_rows: list[dict[str, object]] = []
    for route in routes:
        tests = sorted(tests_by_route.get(route, set()))
        inventory_rows.append(
            {
                "method": route.method,
                "path": route.path,
                "covered": route in hit_counts,
                "hit_count": hit_counts.get(route, 0),
                "example_tests": tests[:3],
                "test_count": len(tests),
            }
        )

    covered_routes = sum(1 for row in inventory_rows if row["covered"])
    total_routes = len(inventory_rows)
    percentage = (covered_routes / total_routes * 100.0) if total_routes else 0.0

    unmatched_hits = []
    for row in raw_rows:
        key = RouteKey(method=str(row.get("method", "")).upper(), path=str(row.get("route_path", "")))
        if key not in route_set:
            unmatched_hits.append(row)

    payload = {
        "summary": {
            "total_routes": total_routes,
            "covered_routes": covered_routes,
            "coverage_percentage": round(percentage, 2),
        },
        "routes": inventory_rows,
        "unmatched_hits": unmatched_hits,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    write_markdown(
        output_md,
        total_routes=total_routes,
        covered_routes=covered_routes,
        percentage=percentage,
        inventory_rows=inventory_rows,
        unmatched_hits=unmatched_hits,
    )

    print(f"Route coverage: {covered_routes}/{total_routes} ({percentage:.2f}%)")
    print(f"JSON report: {output_json}")
    print(f"Markdown report: {output_md}")


if __name__ == "__main__":
    main()
