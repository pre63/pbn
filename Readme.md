# Private Blog Network (PBN) Experiment

Welcome to the **Private Blog Network (PBN)** project, where we’re throwing expired domains and generative AI into a blender to see what kind of SEO smoothie comes out. This is a half-baked experiment to poke Google’s algorithms with a stick, figure out how they handle AI-generated content on resurrected domains, and answer the age-old question: *Will this get us banned or make us SEO gods?* Spoiler: It’s research *and* a wild ride, so buckle up.

I bought a bunch of expired domains because, you know, YOLO, and I couldn’t find a decent open-source project doing this. So here we are, building a multi-domain blog platform powered by xAI’s Grok API to churn out New York Times-style editorials (because nothing screams “legit” like 800-word thinkpieces on quantum computing). The goal? Learn if Google and friends penalize AI content, how expired domains rank, and whether this PBN tactic is genius or a one-way ticket to the sandbox.

This is as much a science project as it is a middle finger to boring SEO tutorials. Let’s see what breaks first: the code, the rankings, or my patience.

## One Shot
```
  make install generate dates cross_post images deploy
```


## Setup

No rocket science here, just the usual dev dance.

```bash
make install
```

```fish
set -x XAI_API_KEY "your-xai-api-key"
```

Oh, and make sure you’ve got Python 3.8+ and `pip`. If you’re still on Python 2, I’m judging you harder than Google judges duplicate content.

## Dev

Wanna hack on this? Fire up the Flask dev server and pray it doesn’t crash:

```bash
make
```

This runs `src/app.py` with Flask’s dev server. The app serves multiple domains (e.g., `connectnews24.com`, `hilltopsnewspaper.com`, etc.) from a single instance, using `domains/[domain].yml` for config and `content/[domain]/articles` for AI-generated articles. Check `localhost:8080` or whatever port you’ve configured (see `src/config.py`).

Pro tip: If you break the templates in `templates/`, don’t blame me when your CSS looks like a 90s Geocities page.

## Generate Articles

Here’s where the magic (or chaos) happens. To generate NYT-style editorials for all domains:

```bash
make generate
```

This runs `scripts/article.py`, which:
- Reads article specs from `content/[domain]/gen.yml`.
- Hits up the xAI Grok API to churn out 800–1200 word articles that sound like they belong in a Sunday op-ed.
- Saves them as Markdown files in `content/[domain]/articles/[slug].md` with front matter like:

```markdown
---
title: The Rise of Quantum Computing
slug: rise-quantum-computing
author: Jane Techson
date: 2025-07-03
meta_description: Exploring how quantum computing could revolutionize industries, from cryptography to drug discovery.
meta_keywords: [quantum computing, technology, innovation, AI, future tech]
og_title: The Rise of Quantum Computing - Connect News 24
og_description: Exploring how quantum computing could revolutionize industries, from cryptography to drug discovery.
og_image: /content/assets/tech-bg.jpg
---
# The Rise of Quantum Computing
...
```

Each domain has a `gen.yml` (e.g., `content/connectnews24.com/gen.yml`) with article specs like title, topic, keywords, and description. Edit these to generate whatever content you want. If you’re feeling lazy, the provided samples cover tech, rural life, sports, global news, sustainable construction, and renewable energy. Because, you know, variety is the spice of SEO.


## Features

- **Multi-Domain Blogs**: Each domain (e.g., `connectnews24.com`, `powersporta.com`) has its own config (`domains/[domain].yml`) and articles (`content/[domain]/articles`).
- **AI-Generated Articles**: Uses xAI’s Grok API to generate NYT-style editorials based on `gen.yml` specs. Think deep dives on quantum computing or rural farming tech.
- **Search**: Full-text search across articles using TF-IDF and cosine similarity (`src/text_analytics.py`). Because who needs Elasticsearch when you’ve got Python?
- **Related Articles**: Suggests related content on every page, powered by the same TF-IDF magic.
- **Sneaky 404 Handler**: Returns a 200 status with relevant articles or a fallback page, because Google hates 404s more than I hate uncommented code.
- **Config-Driven**: Everything from site name to categories is driven by YAML. Change `domains/[domain].yml` and `content/[domain]/gen.yml` to rebrand faster than a startup pivots.

## Contributing

Oh, you wanna contribute? *leans back, smirks* Look, I’m not holding my breath. If you’re gonna send a PR, make it good—none of that half-assed, “I added a comma” nonsense. You know what real open-source looks like: clean code, tests (ha, who am I kidding?), and commit messages that don’t read like a toddler’s tantrum. Fork it, hack it, and if it’s subpar, I’ll yeet it into the void faster than Google deindexes a spammy PBN. Impress me, or don’t bother.

## License

**MIT License**

Do whatever the hell you want with this. Clone it, tweak it, sell it to your cousin for crypto— I don’t care. Just don’t sue me when Google slaps your domains into oblivion. Full license text in `LICENSE` (go write it yourself, it’s MIT, you know the drill).

## Why This Exists

This is a research experiment to see if AI-generated content on expired domains can game the SEO system or if it’ll crash and burn. Will Google’s algo sniff out our Grok-generated prose? Will expired domains give us a ranking boost? Or will we end up in the digital gulag? Only one way to find out: deploy, monitor, and probably cry a little.

Got questions? Ping me at `info@whatever-your-domain-is.com`. Or don’t. I’m not your mom.
