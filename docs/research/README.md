# Research & Quantitative Literature Ingestion Folder

Drop your research papers, quantitative finance books, and notes in this folder.

### Supported File Formats:
- **`.pdf`**: Academic papers and books (text will be extracted via Python).
- **`.txt`**: Plain text extracts or book transcriptions.
- **`.epub`** / **`.mobi`**: E-books.
- **`.md`**: Markdown notes, chapter summaries, or existing card extractions.

### Automated Processing:
When you drop files here, notify the assistant in chat (e.g., *"I dropped Sinclair_Positional.pdf and Pan_Poteshman.pdf in docs/research"*).
The assistant will:
1. Parse the text directly on your local machine.
2. Extract mathematical expressions, empirical heuristics, economic rationales, and pitfall warnings.
3. Cross-check against existing cards in `options-kb-master.md`.
4. Inject new quantitative cards into the project's knowledge base and archetype generators.
