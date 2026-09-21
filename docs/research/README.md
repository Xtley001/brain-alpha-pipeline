# Research Literature

Drop research papers, quantitative finance books, and notes in this folder. The assistant will extract alpha signals and inject them into the knowledge base.

## Supported Formats

- `.pdf` — Academic papers and books (text extracted via Python)
- `.txt` — Plain text extracts or book transcriptions
- `.epub` / `.mobi` — E-books
- `.md` — Markdown notes, chapter summaries, or existing card extractions

## Ingestion Process

When you drop files here, notify the assistant in chat (e.g., "I dropped Sinclair_Positional.pdf and Pan_Poteshman.pdf in docs/research"). The assistant will:

1. Parse the text directly on your local machine.
2. Extract mathematical expressions, empirical heuristics, economic rationales, and pitfall warnings.
3. Cross-check against existing cards in `options-kb-master.md` and `docs/multicategory-kb-master.md`.
4. Inject new quantitative cards into the knowledge base and update archetype generators.

## Current Library

32 institutional papers and books are indexed in `options-kb-master.md` and `docs/multicategory-kb-master.md`. See those files for the full literature map and extracted signal cards.
