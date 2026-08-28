---
layout: default
title: ホーム
---

# AIビジネス研究室

AIと自動化を、日々の仕事や小さな事業で役立つ形に整理します。

## 新着記事

{% for post in site.posts limit: 10 %}
- [{{ post.title }}]({{ post.url | relative_url }})
{% endfor %}

## このサイトについて

生成AIの一般論だけでなく、実際に試した手順、前提条件、注意点を明記することを大切にします。
