# AI News Collector — LangGraph Project Outline

## 1. Project Goal

Build a LangGraph-based AI news collection agent that periodically gathers recent AI updates, filters and ranks them based on Andrew's preferences, summarizes the most relevant items, and produces a personalized digest.

Initial output:

- Local Markdown digest file

Later outputs:

- Gmail draft
- Automated Gmail send
- HTML email digest

Primary focus areas:

- LLMs and reasoning models
- Multimodal models
- Vision-language models
- Video understanding
- AI agents and agent frameworks
- LangGraph
- Google ADK
- OpenAI Agents SDK
- MCP and tool use
- AI infrastructure
- GitHub/Hugging Face model or repo releases
- arXiv papers

Low-priority content:

- Generic AI hype
- Startup funding news
- Business-only articles
- Policy/regulation unless directly relevant to model access, APIs, or deployment

---

## 2. Confirmed Design Decisions

| Step | Decision |
|---|---|
| Trigger | Windows Task Scheduler first; cloud/platform scheduling later |
| Sources | RSS + arXiv + GitHub/Hugging Face |
| Collection | RSS + official APIs; selective webpage extraction |
| Extraction depth | Two-stage extraction |
| Storage | SQLite now; vector store later |
| Deduplication | URL + title matching for MVP; hybrid later |
| Topic classification | Hybrid: keyword first, LLM for shortlisted/ambiguous items |
| Ranking | Branch-specific + two-stage ranking; feedback learning later |
| Final selection | Soft branch quotas |
| Summarization | Tiered summaries |
| Digest format | Importance-first with sections now; HTML multipart later |
| Delivery | Save local file first; Gmail draft second; Gmail send later |
| Feedback | Manual feedback file now; natural-language feedback later |
| Logging | File logs + SQLite run summaries + lightweight decision traces |
| Deployment | Local Task Scheduler now; server/GitHub Actions later; cloud optional |
| Model strategy | Configurable OpenAI/Gemini provider now; task-specific models later |

---

## 3. High-Level Pipeline

```text
Manual Run / Task Scheduler
        ↓
LangGraph Workflow
        ↓
Load Config + Preferences
        ↓
Collect from RSS / arXiv / GitHub / Hugging Face
        ↓
Normalize Items
        ↓
Store Raw Items in SQLite
        ↓
Deduplicate
        ↓
Keyword Topic Classification
        ↓
Cheap Branch-Specific Pre-Ranking
        ↓
Shortlist Candidates
        ↓
Selective Full-Content Extraction
        ↓
LLM Classification + LLM Ranking
        ↓
Soft-Quota Final Selection
        ↓
Tiered Summarization
        ↓
Compose Digest
        ↓
Save Local Digest File
        ↓
Save Run History + Decision Traces
```

Later:

```text
Create Gmail Draft
        ↓
Send Gmail Digest
        ↓
Collect Feedback
        ↓
Update Preferences
```

---

## 4. Recommended Project Structure

```text
ai_news_collector/
│
├── main.py
├── graph.py
├── state.py
├── config.py
├── prompts.py
│
├── configs/
│   ├── sources.yaml
│   ├── preferences.yaml
│   ├── feedback.yaml
│   └── models.yaml
│
├── nodes/
│   ├── load_config.py
│   ├── collect_rss.py
│   ├── collect_arxiv.py
│   ├── collect_github.py
│   ├── collect_huggingface.py
│   ├── normalize_items.py
│   ├── deduplicate.py
│   ├── classify_topics.py
│   ├── cheap_rank.py
│   ├── shortlist.py
│   ├── extract_content.py
│   ├── llm_rank.py
│   ├── final_select.py
│   ├── summarize.py
│   ├── compose_digest.py
│   ├── save_digest.py
│   └── save_history.py
│
├── tools/
│   ├── rss_client.py
│   ├── arxiv_client.py
│   ├── github_client.py
│   ├── huggingface_client.py
│   ├── webpage_extractor.py
│   ├── database.py
│   ├── email_client.py
│   ├── scoring.py
│   └── text_utils.py
│
├── data/
│   └── news_agent.db
│
├── outputs/
│   └── digests/
│
├── logs/
│   └── runs/
│
├── tests/
│
├── .env
├── requirements.txt
└── README.md
```

Core idea:

- `nodes/`: LangGraph workflow steps
- `tools/`: reusable helper functions
- `configs/`: editable configuration files
- `data/`: SQLite database
- `outputs/`: generated digest files
- `logs/`: run logs

---

## 5. LangGraph Workflow Plan

Main graph:

```text
START
  ↓
load_config
  ↓
collect_all_sources
  ↓
normalize_items
  ↓
save_raw_items
  ↓
deduplicate_items
  ↓
classify_topics_keyword
  ↓
cheap_rank_by_branch
  ↓
shortlist_candidates
  ↓
extract_full_content_for_shortlist
  ↓
llm_classify_and_rank
  ↓
final_select_with_soft_quotas
  ↓
summarize_selected_items
  ↓
compose_digest
  ↓
save_digest_file
  ↓
save_run_history
  ↓
END
```

For MVP, source collection can be sequential:

```text
collect_rss
collect_arxiv
collect_github
collect_huggingface
```

Later, source collection can become parallel branches:

```text
             ┌─ collect_rss ─────────┐
             ├─ collect_arxiv ───────┤
START ───────┼─ collect_github ──────┼→ merge_collected_items
             └─ collect_huggingface ─┘
```

---

## 6. State Design

The graph should pass around a shared state object.

Conceptual `NewsState`:

```text
NewsState
- run_id
- run_datetime
- lookback_days
- config
- preferences
- feedback
- raw_items
- normalized_items
- deduped_items
- classified_items
- cheap_ranked_items
- shortlisted_items
- enriched_items
- llm_ranked_items
- selected_items
- summaries
- digest_subject
- digest_body
- output_path
- errors
- stats
```

Each node reads from this state and returns updates.

Examples:

```text
collect_all_sources
adds:
- raw_items
- stats.collection_counts

deduplicate_items
adds:
- deduped_items
- stats.duplicate_count

llm_rank
adds:
- llm_ranked_items
- stats.token_estimate

compose_digest
adds:
- digest_subject
- digest_body

save_digest
adds:
- output_path
```

---

## 7. Source Plan

### 7.1 RSS Branch

Purpose:

Collect news, company announcements, blog updates, model release posts, and AI engineering posts.

Initial source categories:

Official/company/model sources:

- OpenAI
- Google DeepMind
- Anthropic
- Meta AI
- Mistral AI
- Hugging Face
- NVIDIA AI / developer blog
- Microsoft Research / AI blog

AI news/analysis:

- The Decoder
- VentureBeat AI
- TechCrunch AI
- MIT Technology Review AI
- The Batch

Each RSS item should produce:

```text
title
url
source_name
source_type = rss
published_at
snippet
raw_summary
collected_at
```

### 7.2 arXiv Branch

Purpose:

Collect research papers related to LLMs, VLMs, video models, AI agents, RAG, benchmarks, and inference.

Initial categories:

- `cs.CL`
- `cs.CV`
- `cs.AI`
- `cs.LG`

Important query/filter topics:

- large language model
- reasoning
- multimodal
- vision-language
- video understanding
- agent
- tool use
- retrieval augmented generation
- benchmark
- evaluation
- inference
- diffusion
- world model

Each arXiv item should produce:

```text
title
url
arxiv_id
authors
published_at
abstract
source_type = arxiv
categories
```

### 7.3 GitHub Branch

Purpose:

Track established or fast-growing repos related to AI agents, LLM tooling, VLMs, model serving, evaluation, and MCP.

Possible signals:

- stars
- forks
- recent update time
- repo description
- topics
- release date
- organization
- programming language

Useful filters:

- minimum stars
- recently updated
- topics include: `llm`, `agents`, `rag`, `multimodal`, `vision-language`, `inference`, `mcp`
- exclude tiny toy repos when possible

Each GitHub item should produce:

```text
repo_name
owner
url
description
stars
forks
updated_at
created_at
topics
source_type = github
```

### 7.4 Hugging Face Branch

Purpose:

Track models, datasets, spaces, and papers relevant to LLMs, VLMs, video models, and multimodal AI.

Possible item types:

- models
- datasets
- spaces
- papers
- blog posts

Useful signals:

- downloads
- likes
- tags
- pipeline tag
- organization
- last modified date
- model card summary

Each Hugging Face item should produce:

```text
name
url
item_type
author_or_org
tags
downloads
likes
last_modified
summary
source_type = huggingface
```

---

## 8. Normalized Content Item Format

Even though RSS, arXiv, GitHub, and Hugging Face are different, normalize them into one shared format.

Conceptual `ContentItem`:

```text
ContentItem
- id
- external_id
- source_type
- source_name
- title
- url
- published_at
- collected_at
- snippet
- full_text
- authors_or_org
- tags
- metadata
- branch
- status
```

Example `branch` values:

- `news`
- `research`
- `development`

Mapping:

```text
RSS → news
arXiv → research
GitHub → development
Hugging Face → development/research depending on item type
```

---

## 9. Storage Plan

Use SQLite.

### Main Tables

#### `content_items`

Stores all collected items.

```text
id
external_id
source_type
source_name
branch
title
url
published_at
collected_at
snippet
full_text
authors_or_org
tags_json
metadata_json
status
content_hash
```

#### `runs`

Stores each execution.

```text
run_id
started_at
finished_at
lookback_days
status
num_raw_items
num_deduped_items
num_shortlisted
num_selected
digest_path
error_count
estimated_tokens
```

#### `item_decisions`

Stores why each item moved forward or got skipped.

```text
id
run_id
item_id
stage
decision
score
reason
created_at
```

Example stages:

- `dedupe`
- `keyword_classification`
- `cheap_ranking`
- `shortlist`
- `llm_ranking`
- `final_selection`
- `summary`

#### `summaries`

Stores generated summaries.

```text
id
run_id
item_id
summary_short
summary_detailed
why_it_matters
relevance_to_user
created_at
```

#### `feedback`

Stores manual feedback.

```text
id
item_id
url
feedback_type
feedback_text
created_at
```

---

## 10. Deduplication Plan

### MVP Deduplication

Use:

1. Exact URL match
2. Canonical URL normalization
3. Normalized title similarity

Canonical URL normalization:

- remove tracking parameters
- strip trailing slashes
- lowercase domain
- normalize HTTP/HTTPS where appropriate

Title normalization:

- lowercase
- remove punctuation
- remove common stopwords
- compare similarity

MVP duplicate logic:

```text
If same canonical URL:
    duplicate

Else if title similarity is very high and source dates are close:
    probable duplicate

Else:
    unique
```

### Later Hybrid Deduplication

Add:

- embedding similarity
- LLM clustering for shortlisted candidates
- cross-branch grouping

Important later behavior:

```text
If official blog + news coverage discuss the same release,
show official blog as the main link and news coverage as related links.
```

---

## 11. Topic Classification Plan

### Stage 1: Keyword Classification

Apply cheap rules to every item.

Example topic labels:

- LLM
- reasoning
- multimodal
- vision-language model
- video model
- image generation
- AI agent
- agent framework
- MCP
- RAG
- benchmark
- inference
- deployment
- open-source model
- dataset
- GitHub repo
- Hugging Face model
- research paper
- business
- funding
- regulation

### Stage 2: LLM Classification

Apply only to shortlisted or ambiguous items.

The LLM should output structured tags:

```text
primary_topic
secondary_topics
content_type
technical_depth
hype_level
personal_relevance_hint
```

Example:

```json
{
  "primary_topic": "AI agent",
  "secondary_topics": ["LangGraph", "tool use", "workflow automation"],
  "content_type": "framework update",
  "technical_depth": "medium",
  "hype_level": "low",
  "personal_relevance_hint": "high"
}
```

---

## 12. Ranking Plan

Ranking is the core intelligence of the system.

### Stage 1: Cheap Branch-Specific Ranking

Use deterministic scoring first.

Scoring features:

- topic match
- source quality
- recency
- branch priority
- keyword match
- GitHub stars/downloads/likes
- arXiv title/abstract relevance
- business/hype penalty

Branch-specific scoring:

RSS/news:

- boost official sources
- boost model releases
- boost agent framework updates
- boost LLM/VLM/video relevance
- penalize funding-only news
- penalize vague AI productivity articles

arXiv:

- boost LLM/VLM/video/agent/eval topics
- boost strong benchmark/evaluation focus
- boost practical method or model release
- penalize generic surveys unless highly relevant
- penalize weak keyword matches

GitHub/HF:

- boost established repos
- boost stars/downloads
- boost recently updated items
- boost relevant topics
- boost known organizations
- penalize tiny toy repos
- penalize unclear README/model cards

### Stage 2: Shortlist

Target approximate shortlist:

```text
RSS/news: top 20
arXiv: top 15
GitHub/HF: top 15
```

Total LLM-ranking candidates:

```text
around 40–50 items
```

### Stage 3: LLM Ranking

LLM scores each shortlisted item with a strict rubric.

Scoring dimensions:

```text
technical_relevance: 0–5
personal_relevance: 0–5
novelty: 0–5
practical_usefulness: 0–5
source_credibility: 0–5
hype_penalty: 0 to -3
duplicate_penalty: 0 to -3
final_score: 0–5
reason
```

Personal relevance boost:

- LLMs
- reasoning models
- VLMs
- multimodal models
- video models
- AI agents
- LangGraph
- Google ADK
- OpenAI Agents SDK
- MCP
- AI infrastructure
- corruption detection
- graphics debugging
- model evaluation

---

## 13. Selective Full-Content Extraction Plan

To control token cost, do not fetch full content for everything.

Recommended sequence:

```text
Raw collected items:
title + snippet + metadata only

Cheap ranking:
no full content

LLM ranking:
mostly title + snippet + abstract/description

Full extraction:
only top 15–20 candidates

Final summary:
only selected 8–12 items
```

Recommended counts:

```text
Collected: 150–300 items
After dedupe: 100–220 items
Cheap shortlist: 40–50 items
Full content extraction: 15–20 items
Final digest: 8–12 items
```

Optional cost-control limits:

```yaml
limits:
  max_raw_items_per_run: 300
  max_shortlist_items: 50
  max_full_text_items: 20
  max_final_items: 12
  max_article_chars_for_llm: 8000
```

---

## 14. Final Selection Plan

Use soft branch quotas.

Target final digest:

```text
8–12 total items
```

Default branch distribution:

```text
Top Picks:
3 items from any branch

News & Model Releases:
3–5 items

Research Papers:
2–3 items

Repos, Tools & Models:
2–3 items
```

Soft constraints:

- do not include weak items just to fill a branch
- only include items above the score threshold
- allow one branch to dominate only if genuinely important

Suggested threshold:

```text
final_score >= 3.5 / 5
```

---

## 15. Summarization Plan

Use tiered summaries.

### Top 3 Items

Detailed structured summary:

```text
What happened:
Why it matters:
Technical details:
Relevance to Andrew:
Link:
```

### Other Selected Items

Shorter summary:

```text
Summary:
Why included:
Link:
```

### arXiv-Specific Format

```text
Problem:
Key idea:
Why it matters:
Potential relevance:
Link:
```

### GitHub/HF-Specific Format

```text
What it is:
Why useful:
Maturity signal:
Potential use:
Link:
```

Maturity signal may include:

- stars
- downloads
- organization
- recent update
- community adoption

---

## 16. Digest Format Plan

Initial format: Markdown/plaintext.

Use importance-first sections.

Example structure:

```markdown
# AI Digest: LLMs, Vision & Agents — YYYY-MM-DD

Hi Andrew,

Here are the most relevant AI updates from the last few days, focused on LLMs, multimodal/vision models, AI agents, and useful engineering tools.

## Top Picks

### 1. Title
Source: ...
Date: ...
Score: ...
What happened:
Why it matters:
Relevance to you:
Link:

## News & Model Releases

...

## Research Papers

...

## Repos, Tools & Models

...

## Patterns I Noticed

- ...
- ...

## Lower-Priority but Saved

- ...
```

Later HTML version:

- styled cards
- source/date badges
- score labels
- feedback buttons

---

## 17. Feedback Plan

### MVP

Use fixed `preferences.yaml`.

### Early Version

Add manual `feedback.yaml`.

Example:

```yaml
global_notes:
  - "Prefer technical model releases over business news."
  - "More agent framework updates."
  - "Less startup funding news."

liked_topics:
  - "multimodal LLMs"
  - "video understanding"
  - "LangGraph"
  - "open-source VLMs"

disliked_topics:
  - "startup fundraising"
  - "generic AI productivity tools"

liked_items:
  - url: "..."
    reason: "Useful for my agent project."

disliked_items:
  - url: "..."
    reason: "Too shallow."
```

### Later Version

Natural-language feedback:

```text
This digest was too paper-heavy. Next time, include more repos and model releases.
```

The system can parse this into updated preferences.

### Much Later

Email feedback buttons:

- Useful
- Not relevant
- More like this
- Less like this

---

## 18. Logging and Debugging Plan

The system should log enough to answer:

- What did the system collect?
- What did it filter out?
- Why did it select these items?
- How many LLM calls were made?
- How much token usage happened?
- What failed?

### Console Logs

Basic progress:

```text
Collected 82 RSS items
Collected 64 arXiv papers
Collected 35 GitHub/HF items
Deduped to 139 items
Shortlisted 45 items
Selected 10 final items
Saved digest to outputs/digests/...
```

### File Logs

Save:

```text
logs/runs/run_YYYY_MM_DD.log
```

### SQLite Run Record

Store:

- run stats
- counts by branch
- errors
- token estimates
- selected items
- ranking scores

### Per-Item Decision Trace

For selected and shortlisted items, store:

- score
- reason
- tags
- why selected
- why skipped
- dedupe group

---

## 19. Model Strategy Plan

Use a configurable model provider.

### MVP

Default:

```text
OpenAI
```

Gemini can be supported later or used optionally.

### Config Design

```yaml
models:
  default_provider: openai

  openai:
    ranking_model: "small/efficient model"
    summarization_model: "small/efficient model"
    digest_model: "small/efficient model"

  gemini:
    ranking_model: "fast Gemini model"
    summarization_model: "stronger Gemini model"
    digest_model: "stronger Gemini model"
```

The graph should not care which provider is used. Only the model factory should care.

### Later Task-Specific Strategy

```text
Cheap filtering:
small/fast model or deterministic rules

Ranking:
OpenAI or Gemini fast model

Final summary:
stronger model if needed

Quality check:
optional second model
```

### Experimental Strategy

Occasionally run:

```text
OpenAI ranking vs Gemini ranking
```

Then compare which one better matches Andrew's taste.

---

## 20. Configuration Files

### `sources.yaml`

Purpose:

Control which sources are active.

Conceptual structure:

```yaml
rss:
  enabled: true
  sources:
    - name: OpenAI Blog
      url: ...
      priority: high
      branch: news

arxiv:
  enabled: true
  categories:
    - cs.CL
    - cs.CV
    - cs.AI
    - cs.LG
  keywords:
    - large language model
    - multimodal
    - vision-language
    - agent
    - benchmark

github:
  enabled: true
  queries:
    - llm agent
    - langgraph
    - mcp
    - vision language model
  min_stars: 500

huggingface:
  enabled: true
  model_tags:
    - text-generation
    - image-text-to-text
    - video-text-to-text
    - sentence-similarity
```

### `preferences.yaml`

Purpose:

Define ranking preferences.

Conceptual structure:

```yaml
high_priority:
  - LLMs
  - reasoning models
  - multimodal models
  - vision-language models
  - video understanding
  - AI agents
  - LangGraph
  - MCP
  - OpenAI Agents SDK
  - Google ADK

medium_priority:
  - inference optimization
  - benchmarks
  - open-source models
  - datasets
  - AI infrastructure

low_priority:
  - business news
  - funding
  - regulation unless deployment-relevant

digest:
  target_items: 10
  max_items: 12
  tone: concise but technical
```

### `models.yaml`

Purpose:

Switch OpenAI/Gemini without changing graph logic.

### `feedback.yaml`

Purpose:

Store manual feedback after reviewing digests.

---

## 21. MVP Graph Node List

For the first coding version, build these nodes:

```text
1. load_config
2. collect_rss
3. collect_arxiv
4. collect_github_hf
5. normalize_items
6. save_raw_items
7. deduplicate_items
8. keyword_classify
9. cheap_rank
10. shortlist_candidates
11. extract_full_content
12. llm_rank
13. final_select
14. summarize_selected
15. compose_digest
16. save_digest
17. save_history
```

To reduce complexity, nodes 2–4 can initially be wrapped under:

```text
collect_all_sources
```

Then split later.

---

## 22. Final MVP Behavior

When running:

```bash
python main.py
```

The system should:

1. Read configs.
2. Create a new run record.
3. Collect recent items from RSS, arXiv, GitHub, and Hugging Face.
4. Normalize all items into one format.
5. Save raw items.
6. Remove duplicates and already-sent items.
7. Classify topics using keyword rules.
8. Cheap-score items by branch.
9. Shortlist top candidates.
10. Extract fuller content for shortlisted candidates.
11. LLM-rank the shortlist.
12. Select 8–12 final items using soft quotas.
13. Generate tiered summaries.
14. Compose a Markdown digest.
15. Save it under `outputs/digests/`.
16. Save scores, decisions, and run history to SQLite.
17. Print a run summary.

Example final console output:

```text
Run complete.

RSS collected: 72
arXiv collected: 88
GitHub/HF collected: 41
After dedupe: 143
Shortlisted: 47
Full content extracted: 18
Final selected: 10

Digest saved:
outputs/digests/ai_digest_2026_06_02.md
```

---

## 23. Recommended MVP Scope

Must-have:

- LangGraph workflow
- RSS + arXiv + GitHub/HF collection
- SQLite
- URL/title dedupe
- keyword classification
- cheap ranking
- LLM ranking
- local Markdown digest
- logs

Nice-to-have but not first:

- Gmail draft
- HTML email
- vector store
- semantic dedupe
- feedback buttons
- cloud deployment

---

## 24. Version Roadmap

### Version 0 — Planning Complete

Current stage.

Output:

- pipeline plan
- architecture
- design choices

### Version 1 — Local MVP

Goal:

Generate a local Markdown digest.

Includes:

- RSS collection
- arXiv collection
- basic GitHub/HF collection
- SQLite storage
- URL/title dedupe
- keyword classification
- cheap ranking
- LLM ranking
- tiered summaries
- local digest file
- logs

Does not include yet:

- Gmail draft/send
- feedback learning
- vector store
- HTML email
- parallel graph branches

### Version 2 — Better Source Branches

Goal:

Improve source quality and branch independence.

Add:

- separate branch quotas
- better GitHub/HF filters
- curated `sources.yaml`
- more robust arXiv query filtering
- source quality scoring

### Version 3 — Gmail Draft

Goal:

Create Gmail draft automatically.

Add:

- Gmail API integration
- draft email creation
- manual review before send

### Version 4 — Feedback Learning

Goal:

Improve personalization.

Add:

- `feedback.yaml`
- manual feedback parsing
- ranking adjustment based on liked/disliked items

### Version 5 — Automated Send

Goal:

Send trusted digest automatically.

Add:

- Gmail send
- Task Scheduler automation
- failure alerts
- send logs

### Version 6 — Advanced Agent System

Goal:

More autonomous and research-capable system.

Add:

- vector store
- semantic duplicate detection
- LLM clustering
- multi-source research for top stories
- OpenAI/Gemini comparison mode
- LangSmith tracing
- HTML multipart email
- cloud deployment

---

## 25. Final Blueprint Summary

```text
Framework:
LangGraph

Execution:
Manual run + Windows Task Scheduler later

Sources:
RSS + arXiv + GitHub + Hugging Face

Storage:
SQLite

Deduplication:
URL + title similarity MVP

Classification:
Keyword first, LLM for shortlisted items

Ranking:
Branch-specific cheap ranking, then LLM ranking

Selection:
Soft branch quotas, 8–12 final items

Summarization:
Tiered summaries

Output:
Markdown/plaintext local digest first

Later:
Gmail draft → Gmail send → feedback learning → vector store → cloud deployment

Model:
Configurable OpenAI/Gemini provider
OpenAI default first
```
