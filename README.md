# AI Intelligence Ingestion Pipeline

An end-to-end AI intelligence pipeline built to collect, process, enrich, and organize information from multiple AI-focused sources.

The pipeline focuses on reliable data collection, asynchronous processing, freshness checks, LLM-based extraction, entity resolution, and scalable architecture.

## 📊 Dataset Coverage

The current pipeline produces:

| Dataset | Records |
|---|---:|
| Startups | 1,730 |
| Products | 1,198 |
| Research Papers | 1,000 |
| Fresh News | 25 |
| Fresh Jobs | 88 |

The final datasets pass schema validation with **0 schema errors**.

> The pipeline never invents missing information. When a value cannot be reliably determined, it is kept as `null`.

---

## 🎯 What This Project Does

The pipeline follows a simple flow:

**Collect → Clean → Normalize → Enrich → Resolve → Validate → Export**

It brings together several types of AI intelligence:

- AI startups
- AI products
- Research papers
- AI news
- AI job listings
- GitHub repository information

Each stage is separated into independent modules so that individual crawlers and processing components can be improved without changing the entire pipeline.

---

## 🏗️ Architecture

### Current Pipeline

```text
                    ┌──────────────────┐
                    │   AI Sources     │
                    └────────┬─────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
        Startups          Products       Research
        News              Jobs           Papers
             │               │               │
             └───────────────┼───────────────┘
                             ↓
                   Async Data Collection
                             ↓
                    Freshness Filtering
                             ↓
                    Data Normalization
                             ↓
                   LLM-based Extraction
                             ↓
                   Entity Resolution
                             ↓
                     Deduplication
                             ↓
                       Validation
                             ↓
                    Excel / CSV Export
