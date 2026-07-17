# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A RAG-style extraction agent that pulls structured hardware specs — **linecards** and **optical transceivers** — out of a large networking-switch datasheet PDF (the Huawei CloudEngine 16800). The PDF is too big to feed to an LLM whole (see the git history: "fails due to context window depletion"), so the system navigates a pre-computed document tree to locate relevant sections, then extracts only those page slices.

## Commands

```bash
pip install -r requirements.txt          # install deps

# Create app/.env before running anything (loaded by app/utils/llm.py):
#   LLM_PROVIDER=openrouter        # openrouter | openai | anthropic
#   API_KEY=sk-or-v1-...
#   MODEL=gpt-oss-120b:exacto      # tested path; OpenRouter + gpt-oss-120b:exacto

python -m app.app                        # run Flask web UI on port 5001

pytest                                    # run all tests (pythonpath=. via pytest.ini)
pytest tests/test_tree.py::test_navigation   # run a single test
```

Note: `tests/test_tree.py` loads the structure JSON from `app/database/CE16800_hardware_description_structure.json`, but the committed copy lives at the repo root — the test path may need reconciling before it passes.

## Two-phase pipeline (applied twice: linecards, then optics)

The inputs are always a **PDF** plus its **structure JSON** (`CE16800_hardware_description_structure.json`): a hierarchical tree mirroring the doc's table of contents. Each node has `node_id`, `title`, `summary`, and page range `start_index`/`end_index`.

1. **LOCATE** — an LLM agent walks the tree (it is given navigation *tools*, not the raw tree) and returns the `node_id`s that contain the target components.
2. **EXTRACT** — for each `node_id`, pull the PDF text of just that node's pages (and its descendants') and feed that slice to an LLM to produce structured JSON.

Outputs land in `app/database/linecards/*.json` and `app/database/optics/*.json`, plus intermediate `linecard_nodes.json` / `optic_nodes.json`.

## Key components

- **`app/utils/tree.py` (`TreeExplorer`)** — stateful cursor over the document tree (`go_down`/`go_up`/`get_current_node`). Exposed to LLM agents as tools so they traverse the doc like a filesystem instead of ingesting all of it.
- **`app/utils/pdf_extractor.py` (`PDFExtractor`)** — given a `node_id`, collects that node's page range *plus all descendants'* and extracts raw text for only those pages via PyMuPDF (`fitz`). This produces the small "slice" that Phase 2 consumes.
- **`app/utils/llm.py`** — provider abstraction (OpenRouter / OpenAI / Anthropic) driven by `app/.env`. `get_summary_memory` wraps a `ChatSummaryMemoryBuffer` to keep agent conversations from blowing the context window.
- **`app/agent/`** — the four agents (see table).
- **`app/main.py`** — pipeline orchestration (`extract_linecards`, `extract_optics`, `parse_linecards`, `parse_optics`).
- **`app/app.py`** — Flask UI; upload PDF + structure JSON, runs all four steps, returns JSON. Template in `app/templates/index.html`.

### The four agents

| Module | Phase | Mechanism | Job |
|--------|-------|-----------|-----|
| `linecard_extractor.py` | LOCATE | LlamaIndex `AgentWorkflow` + tree tools | Return linecard `node_id`s |
| `optic_extractor.py` | LOCATE | Same | Return optics `node_id`s |
| `linecard_parser.py` | EXTRACT | Plain `llm.complete()`, no tools | One slice → one linecard JSON |
| `optic_parser.py` | EXTRACT | `AgentWorkflow` + `record_optics` tool | Slice → accumulate into `OpticsRegistry` |

The asymmetry is deliberate: each linecard slice maps to exactly one linecard, parsed as a single stateless completion. Optics use an agent plus an `OpticsRegistry` that dedupes modules/standards into categories (via sets) across many nodes.

## Conventions that matter when editing

- **Agent prompts are ReAct-style and strict** — `Thought/Action/Action Input`, ending with a bare `Answer:` line. The LOCATE prompts return `node_id`s comma-separated with *no* spaces/brackets/quotes; `app/main.py` parses this by splitting on `"Answer: "` then on commas. Changing prompt output format means updating that parsing.
- **The recurring failure mode is the navigation agent stopping too early** (returning a section instead of drilling to individual components) or re-visiting nodes until context depletes. `optic_extractor.py`'s prompt has a long warning that "has children" ≠ "is a group" — read it before touching LOCATE prompts.
- **`parse_linecards` saves raw LLM responses** to `raw_<node_id>.txt` before parsing and only deletes them on success — intentional, to avoid losing paid LLM output on a JSON parse failure. It also strips ```` ```json ```` fences defensively.
- Uploaded files go to `app/uploads/` and are cleaned up after each request.
