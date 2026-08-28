"""Generate one review-ready Japanese article draft from keywords.csv."""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
KEYWORDS_FILE = BASE_DIR / "keywords.csv"
DRAFTS_DIR = BASE_DIR / "_drafts"
POSTS_DIR = BASE_DIR / "_posts"
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MIN_CHARS = 1500
MAX_CHARS = 3200
MAX_GENERATION_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 4000
MAX_API_RETRIES = 3
BANNED_PATTERNS = ("必ず稼げ", "絶対に稼げ", "誰でも簡単に", "放置で月", "コピペだけで")
REQUIRED_HEADINGS = ("結論", "具体的な進め方", "注意点", "よくある質問", "まとめ")
EDITOR_CHECKLIST_HEADING = "公開前に運営者が追記・確認する項目"


def load_first_unused_keyword() -> dict[str, str] | None:
    with KEYWORDS_FILE.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("status", "").strip() == "unused":
                return row
    return None


def update_status(keyword: str, status: str) -> None:
    with KEYWORDS_FILE.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise RuntimeError("keywords.csv にヘッダーがありません。")
    for row in rows:
        if row.get("keyword") == keyword:
            row["status"] = status
    with KEYWORDS_FILE.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_prompt(item: dict[str, str]) -> str:
    return f"""あなたは日本語の実務メディアの編集者です。次のキーワードについて、公開前に人間が独自の経験・検証結果・一次情報を追記するための下書きをMarkdownで作成してください。

キーワード: {item['keyword']}
カテゴリ: {item.get('category', '')}
編集メモ: {item.get('notes', '')}

必須条件:
- 日本語、です・ます調、本文1500〜2500字程度
- 最初に結論を述べ、初心者の検索意図を解決する
- H1は1つだけ。続いて導入、H2の「結論」「具体的な進め方」「注意点」「よくある質問」「まとめ」を含める
- 事実・価格・仕様・法律・規約など、確認が必要なことは断定せず「公式情報を確認してください」と明示する
- 実在しない事例、数値、機能、引用、体験談を作らない
- 誇大表現や、収益を保証する表現をしない
- 他サイトの文を模倣しない
- 末尾に「## 公開前に運営者が追記・確認する項目」を置き、一次情報、実体験、更新日を確認するチェック項目を3つ以上書く
- 記事本文だけをMarkdownで出力する。コードフェンスは不要
"""


def clean_markdown(text: str) -> str:
    text = re.sub(r"^```(?:markdown)?\s*", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", text).strip()


def revision_prompt(article: str, errors: list[str]) -> str:
    """Ask Gemini to repair its own draft instead of silently truncating it."""
    return f"""次のMarkdown記事を編集し直してください。内容を途中で切り捨てず、見出し構造を保ったまま、本文（H1を除く）を1900〜2600字に必ず収めてください。

修正理由:
{chr(10).join(f'- {error}' for error in errors)}

守る条件:
- H1は1つ、H2の「結論」「具体的な進め方」「注意点」「よくある質問」「まとめ」を残す
- 末尾の「## 公開前に運営者が追記・確認する項目」も残す
- 実在しない事実や体験談を足さない
- 記事本文だけをMarkdownで出力し、前置きやコードフェンスを付けない

編集対象:
{article}
"""


def generate_article(client: object, prompt: str, config: object) -> str:
    """Generate text, retrying temporary Gemini capacity errors."""
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
            return clean_markdown(response.text or "")
        except Exception as error:
            if getattr(error, "code", None) != 503 or attempt == MAX_API_RETRIES:
                raise
            wait_seconds = attempt * 10
            print(f"Geminiが混雑しています。{wait_seconds}秒後に再試行します（{attempt}/{MAX_API_RETRIES}）。")
            time.sleep(wait_seconds)
    raise RuntimeError("Geminiから応答を取得できませんでした。")


def article_body_without_title(article: str) -> str:
    return re.sub(r"^# .+?$", "", article, count=1, flags=re.MULTILINE).strip()


def quality_errors(article: str) -> list[str]:
    body = article_body_without_title(article)
    errors: list[str] = []
    if not re.search(r"^#\s+.+", article, flags=re.MULTILINE):
        errors.append("H1タイトルがありません。")
    if len(body) < MIN_CHARS:
        errors.append(f"本文が短すぎます（{len(body)}字）。")
    if len(body) > MAX_CHARS:
        errors.append(f"本文が長すぎます（{len(body)}字）。")
    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^##\s+{re.escape(heading)}", article, flags=re.MULTILINE):
            errors.append(f"必須見出し「{heading}」がありません。")
    if EDITOR_CHECKLIST_HEADING not in article:
        errors.append("人間による確認項目がありません。")
    for pattern in BANNED_PATTERNS:
        if pattern in article:
            errors.append(f"禁止表現を検出しました: {pattern}")
    return errors


def missing_sections(article: str) -> list[str]:
    missing = [
        heading
        for heading in REQUIRED_HEADINGS
        if not re.search(rf"^##\s+{re.escape(heading)}", article, flags=re.MULTILINE)
    ]
    if EDITOR_CHECKLIST_HEADING not in article:
        missing.append(EDITOR_CHECKLIST_HEADING)
    return missing


def missing_sections_prompt(item: dict[str, str], headings: list[str]) -> str:
    requested = "\n".join(f"## {heading}" for heading in headings)
    return f"""次のキーワードの記事に追加する不足節だけを書いてください。

キーワード: {item['keyword']}
不足している節:
{requested}

条件:
- 上記の見出しを一字も変えず、すべてMarkdownのH2として出力する
- 各節は250〜350字を目安に、初心者に役立つ具体的な判断方法を書く
- 「公開前に運営者が追記・確認する項目」では、一次情報、実体験、更新日を確認するチェック項目を3つ以上箇条書きにする
- 実在しない事実、数値、体験談、引用を作らない
- 見出し以外の前置き・後書き・コードフェンスは出力しない
"""


def only_too_long(errors: list[str]) -> bool:
    return bool(errors) and all("長すぎます" in error for error in errors)


def truncate_at_sentence(text: str, limit: int) -> str:
    """Shorten a section without cutting halfway through the first sentence."""
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(compact) <= limit:
        return compact
    candidate = compact[:limit]
    end = max(candidate.rfind("。"), candidate.rfind("！"), candidate.rfind("？"))
    return candidate[: end + 1].strip() if end >= limit // 2 else candidate.rstrip() + "…"


def compact_article(article: str) -> str:
    """Create a readable review draft when a structurally valid response is too long."""
    blocks = re.split(r"(?=^##\s+)", article, flags=re.MULTILINE)
    if len(blocks) < 2:
        return article
    compacted = [truncate_at_sentence(blocks[0], 280)]
    for block in blocks[1:]:
        heading, _, body = block.partition("\n")
        compacted.append(f"{heading}\n\n{truncate_at_sentence(body, 380)}")
    return "\n\n".join(compacted).strip()


def normalise(text: str) -> set[str]:
    return set(re.findall(r"[ぁ-んァ-ン一-龥A-Za-z0-9]{4,}", text.lower()))


def resembles_existing_article(article: str) -> bool:
    tokens = normalise(article)
    if not tokens:
        return False
    for path in [*DRAFTS_DIR.glob("*.md"), *POSTS_DIR.glob("*.md")]:
        other = normalise(path.read_text(encoding="utf-8"))
        similarity = len(tokens & other) / len(tokens | other) if tokens | other else 0
        if similarity >= 0.65:
            return True
    return False


def slugify(keyword: str) -> str:
    # Windows and Jekyll can use Japanese filenames; retain the keyword so
    # multiple Japanese articles created on the same day do not collide.
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", keyword).strip(" .-")
    return safe_name or "article"


def save_draft(item: dict[str, str], article: str) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = DRAFTS_DIR / f"{today}-{slugify(item['keyword'])}.md"
    title = re.search(r"^#\s+(.+)$", article, flags=re.MULTILINE)
    front_matter = (
        "---\n"
        f'title: "{(title.group(1) if title else item["keyword"]).replace(chr(34), chr(39))}"\n'
        f'keyword: "{item["keyword"].replace(chr(34), chr(39))}"\n'
        f"date: {today}\n"
        "status: review\n"
        f"categories: [{item.get('category', 'guide')}]\n"
        "---\n\n"
    )
    path.write_text(front_matter + article_body_without_title(article) + "\n", encoding="utf-8")
    return path


def main() -> int:
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY が設定されていません。", file=sys.stderr)
        return 2
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("依存ライブラリがありません。pip install -r requirements.txt を実行してください。", file=sys.stderr)
        return 2
    item = load_first_unused_keyword()
    if item is None:
        print("未処理キーワードはありません。")
        return 0
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    generation_config = types.GenerateContentConfig(
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.3,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    completion_config = types.GenerateContentConfig(
        max_output_tokens=2400,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    article = generate_article(client, build_prompt(item), generation_config)
    errors = quality_errors(article)
    if only_too_long(errors):
        article = compact_article(article)
        errors = quality_errors(article)
    for attempt in range(2, MAX_GENERATION_ATTEMPTS + 1):
        if not errors:
            break
        missing = missing_sections(article)
        if missing:
            print(f"不足している節を補完します（{attempt}/{MAX_GENERATION_ATTEMPTS}回目）。")
            addition = generate_article(client, missing_sections_prompt(item, missing), completion_config)
            article = f"{article}\n\n{addition}".strip()
        else:
            print(f"品質条件を満たさないため、Geminiに再編集を依頼します（{attempt}/{MAX_GENERATION_ATTEMPTS}回目）。")
            article = generate_article(client, revision_prompt(article, errors), generation_config)
        errors = quality_errors(article)
        if only_too_long(errors):
            article = compact_article(article)
            errors = quality_errors(article)
    if resembles_existing_article(article):
        errors.append("既存記事との重複度が高すぎます。")
    if errors:
        print("品質チェック不合格:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    path = save_draft(item, article)
    update_status(item["keyword"], "draft")
    print(f"レビュー待ち下書きを作成しました: {path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
