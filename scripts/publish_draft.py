"""Move a reviewed draft into Jekyll posts. Run only after human review."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DRAFTS_DIR = BASE_DIR / "_drafts"
POSTS_DIR = BASE_DIR / "_posts"
KEYWORDS_FILE = BASE_DIR / "keywords.csv"


def mark_keyword_published(content: str) -> None:
    match = re.search(r'^keyword:\s*"(.+?)"\s*$', content, flags=re.MULTILINE)
    if not match:
        print("キーワード情報がないため、keywords.csv の状態は変更しませんでした。")
        return
    keyword = match.group(1)
    with KEYWORDS_FILE.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise RuntimeError("keywords.csv にヘッダーがありません。")
    for row in rows:
        if row.get("keyword") == keyword:
            row["status"] = "published"
    with KEYWORDS_FILE.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="レビュー済み下書きを公開記事へ移動します。")
    parser.add_argument("draft", type=Path, help="_drafts/ 内のMarkdownファイル")
    args = parser.parse_args()
    source = args.draft.resolve()
    if DRAFTS_DIR.resolve() not in source.parents or source.suffix != ".md":
        parser.error("_drafts/ 内のMarkdownファイルを指定してください。")
    if not source.exists():
        parser.error("指定された下書きが見つかりません。")
    content = source.read_text(encoding="utf-8").replace("status: review", "status: published", 1)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = POSTS_DIR / source.name
    if destination.exists():
        parser.error("同名の記事が既に存在します。")
    destination.write_text(content, encoding="utf-8")
    source.unlink()
    mark_keyword_published(content)
    print(f"公開記事に移動しました: {destination.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
