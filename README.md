# AIビジネス・メディア基盤

Gemini で記事の下書きを生成し、機械チェックを通したものだけをレビュー待ちにする静的メディア基盤です。

## この段階でできること

- `keywords.csv` から未処理キーワードを1件選択
- Gemini が日本語記事の**下書き**を生成
- 文字数・見出し・禁止表現・重複を検査
- 合格記事を `_drafts/` に保存し、キーワードを `draft` に更新
- GitHub Actions で毎朝9:30（日本時間）に実行

公開は意図的に自動化していません。内容確認後に `scripts/publish_draft.py` を実行すると `_posts/` へ移動します。独自の経験・検証結果・一次情報を追記してから公開してください。

## 初期設定

1. Google AI Studio で API キーを発行します。
2. GitHub リポジトリの Actions secrets に `GEMINI_API_KEY` を追加します。
3. `keywords.csv` のキーワードを、扱う専門ジャンルに絞って追加します。
4. Cloudflare Pages にリポジトリを接続し、ビルドコマンドを `jekyll build`、出力先を `_site` にします。

ローカルでは Python 3.11 以降を用意して、次の順に実行します。

```powershell
pip install -r requirements.txt
$env:GEMINI_API_KEY = "..."
python scripts/generate_article.py
python scripts/publish_draft.py _drafts/生成済みファイル.md
```

## 収益化前の必須作業

- 独自ドメイン、運営者情報、問い合わせ、プライバシーポリシーを用意する
- 各記事に実体験・検証データ・出典を追加し、事実確認する
- AdSense と各アフィリエイトの審査・規約確認を手動で行う
- Amazonリンクは承認後に、許可された方法で追加する

生成文の公開可否と広告・アフィリエイトの設定は、必ず運営者が最終判断してください。
