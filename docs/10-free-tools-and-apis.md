# 10 · Free Tools & APIs — the Entire Pipeline at Zero Cost

Every tool below is free (or has a generous free tier). None requires a paid key; where a key is needed, it is free to obtain from the official service — **never commit keys to a repository** (GitHub secret-scanning will flag them and attackers mine them). Use `.env` + `.gitignore` (see the repo root).

---

## 1. Scholarly data & reference APIs (no key required)

| API | Use | Endpoint example |
|-----|-----|------------------|
| **CrossRef** | DOI → metadata/BibTeX; citation counts | `https://api.crossref.org/works/{DOI}` (see `scripts/doi2bib.py`) |
| **OpenAlex** | 250M works; authors, institutions, journals; no key; polite pool | `https://api.openalex.org/works?filter=…` (used to build this repo's dataset) |
| **Semantic Scholar** | Papers, citations, abstracts, graphs | `https://api.semanticscholar.org/graph/v1/paper/{DOI}` (rate-limited, free) |
| **PubMed/E-utilities** | Bio/med chemistry literature | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` |
| **CORE API** | Open-access full text | free tier key via core.ac.uk |
| **ChemSpider / PubChem** | Compound data, spectra, synonyms | PubChem free REST API; ChemSpider free key (Royal Society of Chemistry) |
| **IUCr checkCIF** | CIF validation | https://checkcif.iucr.org (free service) |

## 2. Free API keys (official free tiers — sign up, never share)

| Service | Free tier | Get it at |
|---------|-----------|-----------|
| **Google AI Studio (Gemini)** | generous free tier for text/vision | aistudio.google.com |
| **Mistral La Plateforme** | free tier API key | console.mistral.ai |
| **Groq** | free tier, very fast LLM inference | console.groq.com |
| **OpenRouter** | free models with daily limits | openrouter.ai |
| **Cohere** | free trial key | cohere.com |
| **Hugging Face** | free inference API on many models | huggingface.co (token) |
| **MyMemory** | free translation API (no key for light use) | mymemory.translated.net |
| **LibreTranslate** | free translation; self-hostable (truly free/private) | libretranslate.com |
| **Ollama** | **local** LLMs — zero cloud, zero key, fully private | ollama.com |

> **Why local matters for confidential research:** thesis chapters and unpublished results should never transit a third-party AI cloud without institutional approval. `ollama run llama3.1:8b` gives you a private assistant on a laptop.

## 2b. Verified free-API directories on GitHub (checked 2026-08)

These are the **authentic, high-star community directories** of free APIs/keys — audit any key before use:

| Repo | Stars | What it is |
|------|-------|------------|
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | ~455K | The canonical list of free public APIs (CrossRef, OpenAlex, PubChem, MyMemory, LibreTranslate, …) |
| [mnfst/awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis) | ~6.3K | Permanent free LLM APIs and how to obtain their free keys |
| [reorx/awesome-chatgpt-api](https://github.com/reorx/awesome-chatgpt-api) | ~6.4K | Free/open tools & proxies for LLM APIs |
| [zebbern/no-cost-ai](https://github.com/zebbern/no-cost-ai) | ~2.1K | 80+ free AI services (chat, image, video, voice, APIs) |

> ⚠️ **Security warning (important):** repos that publish *already-leaked* keys (e.g., "FREE-openai-api-keys" style collections) are both unethical to use and useless in practice — providers scan GitHub, revoke leaked keys within hours, and GitHub's secret-scanning removes them. **Never use a key you didn't create yourself.** The professional workflow is: pick the service from the directory → sign up at the official site → get *your own* free key → store it in `.env` (gitignored).

## 3. Writing, grammar & style (free tiers)

| Tool | Use | Notes |
|------|-----|-------|
| **LanguageTool** | grammar/style (better than most for science) | free tier; local server option |
| **Vale** | prose linter (open source) | configurable rules; CI-friendly |
| **write-good / textlint** | clarity linter | npm, free |
| **Zotero + Better BibTeX** | references | free, open source |
| **JabRef** | BibTeX manager | free, open source |
| **Pandoc** | markdown → LaTeX/Word/PDF | free, the backbone of `templates/markdown/` |
| **Overleaf** | LaTeX online with git + version history | free tier (authorship evidence built-in) |

## 4. Chemistry-specific free tools

| Tool | Use |
|------|-----|
| **ChemDraw Free / Ketcher / RDKit** | structures (RDKit = Python, fully free, scriptable) |
| **Avogadro** | molecular modelling/visualisation (free) |
| **Pymol (open-source build)** | structure visualisation |
| **GAMESS / ORCA** | free quantum chemistry (ORCA free for academics) |
| **PLATON** | crystallography validation (free for academia) |
| **MestReNova trial / NMRglue (Python)** | NMR processing (NMRglue is free/open) |
| **Origin free alternative: SciDAVis / Veusz / Matplotlib** | plots with error bars, publication quality |
| **ImageJ/Fiji** | microscopy image analysis |

## 5. Reference styles (CSL/BibTeX) for the portfolio journals

- **ACS**: `achemso` LaTeX class + ACS `.bst` styles — [github.com/josephwright/achemso](https://github.com/josephwright/achemso)
- **RSC/Wiley**: `rsc` package styles — [github.com/josephwright/rsc](https://github.com/josephwright/rsc)
- **CSL files** for Zotero/Word: [Zotero style repository](https://www.zotero.org/styles) — search "Journal of the American Chemical Society", "Angewandte Chemie", "Royal Society of Chemistry".

## 6. Plagiarism/AI self-check before submission (legit options)

- **Your institution's Turnitin/Urkund** — the *actual* tool used; always the best self-check (run drafts through the institute portal).
- **Similarity self-check**: Google Scholar "related articles" + manual phrase checks; free text-comparison via `grep`-style checks on your own old theses/papers (self-plagiarism is the common silent killer — check your own corpus first).
- **AI-risk profile**: `scripts/text_stats.py` (rhythm/variance analysis — treat as a false-positive alarm per `docs/09`, not a bypass).

---

*Next: [../checklists/pre-submission-checklist.md](../checklists/pre-submission-checklist.md)*
