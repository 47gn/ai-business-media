---
layout: default
title: ホーム
---

# PCパーツ研究室

PCパーツの価格動向、性能差、対応規格を、用途別に分かりやすく整理します。

## 新着記事

{% for post in site.posts limit: 10 %}
- [{{ post.title }}]({{ post.url | relative_url }})
{% endfor %}

## このサイトについて

価格・在庫・性能の情報は変動するため、確認日と参照元を明記し、実測や公式仕様と区別して掲載します。
