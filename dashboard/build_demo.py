"""Package the shared application with a browser-only demonstration adapter."""
import argparse
import json
import shutil
from pathlib import Path


def build(database, output):
    data = json.loads(Path(database).read_text(encoding="utf-8"))
    if not isinstance(data.get("config", {}).get("schema", {}).get("fields"), list):
        raise ValueError("Database requires config.schema.fields")
    for name in ("contracts", "cases", "progress", "review_versions", "review_comments"):
        if not isinstance(data.get(name), list):
            raise ValueError(f"Database requires the {name} collection")
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "app"
    if not source.exists():
        source = Path(__file__).parent.parent / "面板"
    for item in source.iterdir():
        if item.is_file():
            shutil.copyfile(item, target / item.name)
    html = (source / "index.html").read_text(encoding="utf-8")
    html = html.replace('<script src="app.js">', '<script src="demo-data.js"></script><script src="browser-datasource.js"></script><script src="app.js">')
    (target / "index.html").write_text(html, encoding="utf-8")
    (target / "demo-data.js").write_text("window.CONTRACT_DEMO_DATA=" + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(args.db, args.out)


if __name__ == "__main__":
    main()
