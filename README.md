# FactCheck AI

Automated PDF claim verification with OCR support and multi-format export. Built with Streamlit, OpenAI, Tavily Search, Google Gemini Vision, PyMuPDF, pdfplumber, and ReportLab.

Upload a PDF — marketing report, research paper, whitepaper, financial document, or any article. The app extracts text (including scanned PDFs via OCR), identifies factual claims, verifies each claim against live web evidence, classifies results, and exports a report in your preferred format.

## What Gets Verified

Claims containing statistics, percentages, dates, financial figures, market sizes, growth rates, technical specifications, and user/adoption metrics.

Each claim is classified as:

- `Verified` — credible evidence directly supports the claim
- `Inaccurate` — partially correct but outdated, incomplete, or materially modified
- `False` — contradicted by credible evidence or unsupported as stated
- `Unverifiable` — insufficient evidence returned from search

## Architecture

```
Streamlit UI
  -> PDFParser
      -> pdfplumber (primary)
      -> PyMuPDF (fallback)
      -> OCRService / Gemini Vision (scanned PDF fallback)
  -> ClaimExtractor
      -> OpenAI JSON claim extraction
      -> duplicate removal and validation
  -> Verifier
      -> Tavily query: "Verify claim: {claim}"
      -> evidence bundle with top source snippets
      -> OpenAI JSON verification reasoning
  -> ReportGenerator
      -> CSV, PDF, Markdown, JSON, HTML exports
```

## Project Structure

```
factcheck-ai/
├── app.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── services/
│   ├── pdf_parser.py        # pdfplumber + PyMuPDF + OCR fallback
│   ├── ocr_service.py       # Google Gemini Vision OCR
│   ├── claim_extractor.py
│   ├── llm_service.py
│   ├── search_service.py
│   ├── verifier.py
│   └── report_generator.py  # CSV, PDF, Markdown, JSON, HTML
├── utils/
│   ├── helpers.py
│   └── constants.py
├── assets/
│   └── logo.png
└── output/
```

## Installation

```bash
git clone https://github.com/your-username/factcheck-ai.git
cd factcheck-ai
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

```bash
cp .env.example .env
```

Required:

```text
OPENAI_API_KEY=sk-your-openai-api-key
TAVILY_API_KEY=tvly-your-tavily-api-key
```

Optional (OCR for scanned PDFs):

```text
GEMINI_API_KEY=your-gemini-api-key
```

Other optional settings:

```text
LLM_MODEL=gpt-4o-mini
SEARCH_RESULTS_COUNT=5
REQUEST_TIMEOUT_SECONDS=30
```

Get a Gemini API key at https://aistudio.google.com/app/apikey — free tier is sufficient for most use.

Never commit `.env`. It is ignored by `.gitignore`.

## Running Locally

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Workflow

1. Upload a PDF up to 25 MB.
2. Extract text — standard parsers first, Gemini OCR as automatic fallback for scanned PDFs.
3. Use OpenAI to extract factual claims as JSON.
4. Remove duplicate or near-duplicate claims.
5. Search Tavily with `Verify claim: {claim}`.
6. Compare the claim against web evidence with OpenAI.
7. Classify each claim as `Verified`, `Inaccurate`, `False`, or `Unverifiable`.
8. Export in any of five formats.

## OCR — Scanned PDF Support

When standard text extraction returns fewer than 50 characters, the app automatically switches to OCR:

1. Each page is rendered to a high-DPI PNG (2× matrix).
2. The image is sent to Gemini Vision (`gemini-2.0-flash`).
3. Extracted text is reassembled with page markers.

No manual action required — the UI shows a status message when OCR is active. Typical processing time is 30–90 seconds per document depending on page count and complexity.

## Export Formats

| Format | Use case |
|--------|----------|
| CSV | Excel, Google Sheets, BI tools |
| PDF | Professional reports, printing, archival |
| Markdown | GitHub, documentation, blogs |
| JSON | APIs, databases, data pipelines |
| HTML | Web sharing, email distribution, client presentations |

The download section is organised into two tabs: **Standard** (CSV, PDF, Markdown) and **Additional** (JSON, HTML).

## Streamlit UI

- Sidebar PDF uploader and settings
- Model selection and confidence threshold
- Progress bars during extraction and verification
- Expandable result cards with confidence scores and source links
- Status badges: 🟢 Verified · 🟡 Inaccurate · 🔴 False · ⚪ Unverifiable
- Tabbed export section with format descriptions

## Deployment

### Streamlit Cloud

1. Push this project to GitHub.
2. Go to https://share.streamlit.io and click **New app**.
3. Select the repository, branch, and set main file to `app.py`.
4. Add secrets in the Streamlit Cloud dashboard:

```toml
OPENAI_API_KEY = "sk-your-openai-api-key"
TAVILY_API_KEY = "tvly-your-tavily-api-key"
GEMINI_API_KEY = "your-gemini-api-key"
LLM_MODEL = "gpt-4o-mini"
```

### Docker

```bash
docker-compose up --build
# Access at http://localhost:8501
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for AWS, Heroku, and other options.

## Security

- Uploaded files validated by MIME type and size (25 MB limit).
- Extracted text sanitized before LLM processing.
- API keys loaded from `.env` locally or Streamlit secrets in production.
- Reports generated in memory — nothing persisted to disk by default.
- All external API calls use HTTPS.

## Troubleshooting

**Missing API keys:**
```
Missing API configuration. Set OPENAI_API_KEY and TAVILY_API_KEY.
```
Fix: add keys to `.env` or Streamlit Cloud secrets.

**No extractable text (non-scanned PDF):**
```
Failed to extract text from PDF.
```
Fix: ensure the PDF is not corrupted, password-protected, or under 25 MB.

**OCR not triggering:**
Fix: add `GEMINI_API_KEY` to `.env`. Without it the app skips OCR and returns an insufficient-text error.

**Rate limits:**
Fix: wait and retry, reduce maximum claims, or upgrade your API tier.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for a full reference.

## Future Enhancements

- Batch PDF processing
- REST API endpoints
- Database persistence and report history
- Source credibility scoring
- Custom export templates
- Email delivery
- Multi-language claim extraction
