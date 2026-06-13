"""FactCheck AI Streamlit application."""

from __future__ import annotations

import os
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from services.claim_extractor import ClaimExtractor
from services.pdf_parser import PDFParser
from services.report_generator import ReportGenerator
from services.verifier import Verifier
from utils.constants import (
    APP_NAME,
    DEFAULT_MODEL,
    ERROR_API_KEY,
    STATUS_COLORS,
    STATUS_UNVERIFIABLE,
    SUPPORTED_MODELS,
)
from utils.helpers import calculate_claim_statistics, truncate_text, validate_pdf_file

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)
BASE_DIR = Path(__file__).parent


def configure_cloud_secrets() -> None:
    for key in ("OPENAI_API_KEY", "TAVILY_API_KEY", "GEMINI_API_KEY"):
        try:
            if not os.getenv(key) and key in st.secrets:
                os.environ[key] = st.secrets[key]
        except Exception:
            continue


configure_cloud_secrets()

st.set_page_config(
    page_title=APP_NAME,
    page_icon=str(BASE_DIR / "assets" / "logo.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #f0f0f0; --ink-bright: #ffffff; --muted: #a8a8a8;
        --line: #404040; --surface: #1a1a1a; --surface-soft: #252525;
        --brand: #3b82f6; --brand-dark: #1e40af; --accent: #60a5fa;
        --success: #10b981; --warning: #f97316; --error: #ef4444;
        --sp-1:.25rem; --sp-2:.5rem; --sp-3:.75rem; --sp-4:1rem;
        --sp-5:1.25rem; --sp-6:1.5rem; --sp-8:2rem; --sp-10:2.5rem;
        --sp-12:3rem; --sp-16:4rem;
        --gap-grid:var(--sp-6); --pad-hero:var(--sp-10);
        --margin-section:var(--sp-8); --radius-card:1rem; --radius-hero:1.5rem;
    }
    *, *::before, *::after { box-sizing: border-box; }
    .stApp { background: transparent !important; color: var(--ink); }
    [data-testid="stAppViewContainer"] { background: transparent !important; }
    [data-testid="stMain"] { background: transparent !important; }
    .main .block-container { background: transparent !important; }
    [data-testid="stHeader"] { background: rgba(10,10,10,.92) !important; backdrop-filter: blur(8px); }
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    .block-container { width:100%; max-width:1400px; margin:0 auto; padding:var(--sp-8) var(--sp-6) var(--sp-16); }

    /* ── Hero ── */
    .hero { position:relative; overflow:hidden; border:2px solid var(--line); border-radius:var(--radius-hero); padding:var(--pad-hero); margin:0 0 var(--sp-6); background:linear-gradient(135deg,#1a1a1a 0%,#252525 100%); box-shadow:0 20px 60px rgba(0,0,0,.5); }
    .hero::after { content:""; position:absolute; width:15rem; height:15rem; right:-5rem; top:-7rem; border-radius:50%; border:3rem solid rgba(59,130,246,.08); pointer-events:none; }
    .eyebrow { color:var(--accent); font-size:.75rem; font-weight:700; letter-spacing:.15em; text-transform:uppercase; margin:0 0 var(--sp-3); opacity:.9; }
    .hero h1 { max-width:760px; margin:0; color:var(--ink-bright); font-size:clamp(1.75rem,4vw,3.25rem); line-height:1.1; letter-spacing:-.02em; font-weight:800; }
    .hero p { max-width:700px; margin:var(--sp-3) 0 0; color:var(--muted); font-size:clamp(.9rem,1.5vw,1.05rem); line-height:1.7; }
    .trust-row { display:flex; flex-wrap:wrap; gap:var(--sp-2); margin-top:var(--sp-5); }
    .trust-chip { padding:var(--sp-2) var(--sp-3); border:1.5px solid var(--line); border-radius:8px; background:rgba(64,64,64,.3); color:var(--ink); font-size:.8rem; font-weight:600; white-space:nowrap; }

    /* ── Workflow steps ── */
    .workflow { display:grid; grid-template-columns:repeat(3,1fr); gap:var(--gap-grid); margin:var(--margin-section) 0; }
    .workflow-step { display:flex; align-items:center; gap:var(--sp-4); min-height:4.5rem; padding:var(--sp-4) var(--sp-5); border:1.5px solid var(--line); border-radius:var(--radius-card); background:var(--surface); transition:border-color .25s,box-shadow .25s,background .25s; }
    .workflow-step.active { border-color:var(--brand); background:rgba(59,130,246,.05); box-shadow:0 0 0 3px rgba(59,130,246,.1); }
    .workflow-step.done { border-color:var(--success); background:rgba(16,185,129,.04); }
    .step-number { flex:0 0 2.2rem; width:2.2rem; height:2.2rem; display:grid; place-items:center; border-radius:50%; background:var(--surface-soft); color:var(--muted); font-size:.85rem; font-weight:800; border:1.5px solid var(--line); }
    .active .step-number { background:var(--brand); color:white; border-color:var(--brand); }
    .done .step-number { background:var(--success); color:white; border-color:var(--success); }
    .step-copy { min-width:0; }
    .step-copy b { display:block; color:var(--ink-bright); font-size:.9rem; font-weight:700; }
    .step-copy span { color:var(--muted); font-size:.8rem; }

    /* ── Section headers ── */
    .section-kicker { color:var(--accent); font-size:.75rem; font-weight:700; letter-spacing:.15em; text-transform:uppercase; margin:0 0 var(--sp-2); opacity:.9; display:block; }
    .section-title { color:var(--ink-bright); font-size:clamp(1.2rem,2.5vw,1.5rem); font-weight:800; letter-spacing:-.01em; margin:0 0 var(--sp-2); display:block; }
    .section-copy { color:var(--muted); margin:0 0 var(--sp-6); font-size:.95rem; line-height:1.6; display:block; }

    /* ── Workspace card labels ── */
    .control-label { display:block; margin:0 0 var(--sp-2); color:var(--accent); font-size:.7rem; font-weight:700; letter-spacing:.15em; text-transform:uppercase; opacity:.9; }
    .control-heading { display:block; color:var(--ink-bright); font-size:1.15rem; font-weight:700; margin:0 0 var(--sp-2); }
    .control-copy { display:block; color:var(--muted); font-size:.875rem; margin:0 0 var(--sp-4); line-height:1.6; }
    .workspace-footer { margin:var(--sp-4) 0 0; padding:var(--sp-4) 0 0; border-top:1px solid var(--line); color:var(--muted); font-size:.82rem; line-height:1.5; display:block; }

    /* ── Cards ── */
    .file-card { border:1.5px solid var(--line); border-radius:1.1rem; padding:var(--sp-5) var(--sp-6); margin:0 0 var(--sp-5); background:var(--surface); box-shadow:0 4px 12px rgba(0,0,0,.3); transition:border-color .25s,box-shadow .25s; }
    .file-card:hover { border-color:var(--brand); box-shadow:0 8px 20px rgba(59,130,246,.15); }
    .file-name { color:var(--ink-bright); font-weight:700; font-size:1rem; word-break:break-all; }
    .file-meta { color:var(--muted); font-size:.85rem; margin:var(--sp-1) 0 0; }

    /* ── Empty states ── */
    .empty-state { padding:var(--sp-12) var(--sp-6); border:2px dashed var(--line); border-radius:1.2rem; background:rgba(37,37,37,.3); text-align:center; }
    .empty-icon { width:3.5rem; height:3.5rem; display:grid; place-items:center; margin:0 auto var(--sp-5); border-radius:1rem; background:var(--surface-soft); color:var(--accent); font-size:1.4rem; font-weight:800; border:1.5px solid var(--line); }
    .empty-state b { display:block; color:var(--ink-bright); margin:0 0 var(--sp-2); font-size:1.1rem; font-weight:700; }
    .empty-state span { color:var(--muted); font-size:.9rem; }

    /* ── Result cards ── */
    .status-card { border:1.5px solid var(--line); border-left-width:4px; border-radius:var(--radius-card); padding:var(--sp-5) var(--sp-6); margin:0 0 var(--sp-4); background:var(--surface); box-shadow:0 4px 12px rgba(0,0,0,.3); }
    .status-line { display:flex; align-items:center; gap:var(--sp-3); margin:0 0 var(--sp-3); flex-wrap:wrap; }
    .status-pill { display:inline-block; padding:var(--sp-1) var(--sp-3); border-radius:.6rem; color:white; font-size:.75rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; white-space:nowrap; }
    .confidence { color:var(--muted); font-size:.85rem; font-weight:600; }
    .claim-text { color:var(--ink-bright); font-size:clamp(.95rem,1.5vw,1.05rem); font-weight:700; line-height:1.6; margin:0 0 var(--sp-3); }
    .reason-text { color:var(--muted); font-size:.95rem; line-height:1.7; }

    /* ── Metrics ── */
    div[data-testid="stMetric"] { border:1.5px solid var(--line); border-radius:var(--radius-card); padding:var(--sp-5) var(--sp-6); background:var(--surface); box-shadow:0 4px 12px rgba(0,0,0,.3); height:100%; }
    div[data-testid="stMetricValue"] { font-size:clamp(1.4rem,2.5vw,1.8rem); color:var(--brand); font-weight:800; line-height:1.1; }
    div[data-testid="stMetricLabel"] { color:var(--muted); font-size:.8rem; font-weight:600; letter-spacing:.05em; text-transform:uppercase; }

    /* ── Tabs ── */
    div[data-testid="stTabs"] { overflow-x:auto; -webkit-overflow-scrolling:touch; }
    div[data-testid="stTabs"] button { font-weight:700; color:var(--muted); font-size:.9rem; border-bottom:2px solid transparent; white-space:nowrap; padding:var(--sp-3) var(--sp-4); }
    div[data-testid="stTabs"] button[aria-selected="true"] { color:var(--ink-bright); border-bottom-color:var(--brand); }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color:var(--brand); height:3px; }

    /* ── Bordered container ── */
    [data-testid="stVerticalBlockBorderWrapper"] { background:var(--surface); border:1.5px solid var(--line) !important; border-radius:1.1rem !important; overflow:hidden; }
    [data-testid="stVerticalBlockBorderWrapper"] > div > div { padding:var(--sp-6) !important; }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"] { margin-bottom:var(--sp-1) !important; }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stFileUploader"],
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stSelectbox"],
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stSlider"] { margin-bottom:var(--sp-3) !important; }
    [data-testid="stToggle"] { margin:var(--sp-2) 0 var(--sp-3) !important; }
    [data-testid="stSlider"] > div { padding:var(--sp-2) 0 !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploaderDropzone"] { background:var(--surface) !important; border:2px dashed var(--line) !important; border-radius:var(--radius-card) !important; padding:var(--sp-8) var(--sp-6) !important; transition:border-color .25s !important; }
    [data-testid="stFileUploaderDropzone"]:hover { border-color:var(--brand) !important; }
    [data-testid="stFileUploaderDropzone"] * { color:var(--muted) !important; }
    [data-testid="stFileUploaderDropzone"] button { background:var(--brand) !important; border-color:var(--brand) !important; color:white !important; font-weight:700 !important; border-radius:.7rem !important; padding:var(--sp-2) var(--sp-5) !important; min-height:44px !important; }

    /* ── Inputs ── */
    [data-baseweb="select"] > div, [data-baseweb="input"] > div,
    [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
        background:var(--surface) !important; border:1.5px solid var(--line) !important;
        border-radius:.8rem !important; color:var(--ink-bright) !important;
        padding:var(--sp-3) var(--sp-4) !important; font-size:.95rem !important;
        min-height:44px !important; transition:border-color .25s,box-shadow .25s !important;
    }
    [data-baseweb="select"] > div:hover,[data-baseweb="input"] > div:hover { border-color:var(--brand) !important; box-shadow:0 0 0 3px rgba(59,130,246,.1) !important; }
    [data-baseweb="select"] > div:focus-within,[data-baseweb="input"] > div:focus-within { border-color:var(--brand) !important; box-shadow:0 0 0 3px rgba(59,130,246,.15) !important; outline:none !important; }
    [data-baseweb="select"] *, [data-baseweb="popover"] *, [role="listbox"] * { color:var(--ink-bright) !important; }
    [data-baseweb="popover"], [role="listbox"] { background:var(--surface-soft) !important; border:1.5px solid var(--line) !important; border-radius:.8rem !important; }

    /* ── Misc widgets ── */
    [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] p,
    [data-testid="stCaptionContainer"], label, small { color:var(--muted) !important; font-weight:500 !important; font-size:.9rem !important; }
    [data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] b { color:var(--ink-bright) !important; font-weight:700 !important; }
    [data-testid="stExpander"] { background:var(--surface); border:1.5px solid var(--line); border-radius:var(--radius-card); padding:0 !important; margin-bottom:var(--sp-3); }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color:var(--ink-bright) !important; font-weight:700 !important; padding:var(--sp-3) var(--sp-4) !important; }
    [data-testid="stDataFrame"] { border:1.5px solid var(--line) !important; border-radius:var(--radius-card) !important; overflow:hidden !important; width:100% !important; }
    [data-testid="stAlert"] { color:var(--ink) !important; background:var(--surface) !important; border:1.5px solid var(--line) !important; border-left-width:4px !important; border-radius:var(--radius-card) !important; padding:var(--sp-4) var(--sp-5) !important; }
    hr { border-color:var(--line) !important; border-width:1px !important; }
    a { color:var(--accent) !important; text-decoration:none !important; font-weight:600 !important; }
    a:hover { color:var(--brand) !important; text-decoration:underline !important; }

    /* ── Buttons ── */
    .stButton > button, .stDownloadButton > button { min-height:44px !important; font-size:.95rem !important; font-weight:700 !important; border-radius:.8rem !important; padding:var(--sp-3) var(--sp-6) !important; transition:box-shadow .25s,transform .25s,background .25s,border-color .25s !important; width:100%; }
    .stButton > button[kind="primary"] { border:none !important; background:linear-gradient(135deg,var(--brand) 0%,var(--brand-dark) 100%) !important; box-shadow:0 4px 15px rgba(59,130,246,.3) !important; color:white !important; }
    .stButton > button[kind="primary"]:hover { box-shadow:0 6px 20px rgba(59,130,246,.45) !important; transform:translateY(-1px) !important; }
    .stButton > button:not([kind="primary"]), .stDownloadButton > button { background:var(--surface) !important; border:1.5px solid var(--line) !important; color:var(--ink-bright) !important; }
    .stButton > button:not([kind="primary"]):hover, .stDownloadButton > button:hover { border-color:var(--brand) !important; background:rgba(59,130,246,.06) !important; box-shadow:0 4px 12px rgba(59,130,246,.15) !important; }

    /* ── Columns ── */
    [data-testid="stHorizontalBlock"] { display:flex; flex-wrap:wrap; gap:var(--gap-grid); width:100%; align-items:stretch; }
    [data-testid="stColumn"] { flex:1 1 0; min-width:min(100%,200px); }

    /* ── Responsive ── */
    @media (max-width:479px) {
        :root { --gap-grid:var(--sp-3); --pad-hero:var(--sp-5); --margin-section:var(--sp-5); --radius-card:.85rem; --radius-hero:1rem; }
        .block-container { padding:var(--sp-4) var(--sp-3) var(--sp-10); }
        .hero::after { display:none; }
        .workflow { grid-template-columns:1fr; margin:var(--sp-4) 0; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex:1 1 100% !important; min-width:100% !important; }
    }
    @media (min-width:480px) and (max-width:767px) {
        :root { --gap-grid:var(--sp-4); --pad-hero:var(--sp-6); --margin-section:var(--sp-6); }
        .block-container { padding:var(--sp-5) var(--sp-4) var(--sp-12); }
        .workflow { grid-template-columns:1fr; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex:1 1 100% !important; min-width:100% !important; }
    }
    @media (min-width:768px) and (max-width:1023px) {
        :root { --gap-grid:var(--sp-5); --pad-hero:var(--sp-8); }
        .block-container { padding:var(--sp-6) var(--sp-5) var(--sp-12); }
        .workflow { grid-template-columns:repeat(3,1fr); }
    }
    @media (min-width:1440px) {
        .block-container { padding:var(--sp-10) var(--sp-8) var(--sp-16); max-width:1400px; margin:0 auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session state ────────────────────────────────────────────────────────────


def init_state() -> None:
    defaults = {
        "extracted_text": "",
        "extracted_claims": [],
        "verification_results": [],
        "document_name": "",
        "document_metadata": {},
        "doc_summary": "",
        "active_tab": 0,
        "extract_error": "",
        "extract_success": "",
        "verify_error": "",
        "verify_success": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def has_required_keys() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("TAVILY_API_KEY"))


def reset_for_new_file(uploaded_file) -> None:
    if uploaded_file and uploaded_file.name != st.session_state.document_name:
        st.session_state.extracted_text = ""
        st.session_state.extracted_claims = []
        st.session_state.verification_results = []
        st.session_state.document_metadata = {}
        st.session_state.doc_summary = ""
        st.session_state.document_name = uploaded_file.name
        st.session_state.extract_error = ""
        st.session_state.extract_success = ""
        st.session_state.verify_error = ""
        st.session_state.verify_success = ""
        st.session_state.active_tab = 0


# ── Actions (run before UI renders) ─────────────────────────────────────────


def action_extract(
    uploaded_file, model: str, remove_duplicates: bool, max_claims: int
) -> None:
    """Run PDF extraction + claim extraction, store results in session state."""
    is_valid, err = validate_pdf_file(uploaded_file)
    if not is_valid:
        st.session_state.extract_error = err
        return

    st.session_state.extract_error = ""
    st.session_state.extract_success = ""

    # PDF text extraction
    with st.spinner("Reading PDF…"):
        parser = PDFParser()
        text, pdf_error = parser.extract_text(uploaded_file)

    if pdf_error:
        st.session_state.extract_error = pdf_error
        return

    st.session_state.extracted_text = text
    st.session_state.document_metadata = parser.get_pdf_metadata(uploaded_file)

    # Claim extraction (builds doc summary internally, stores it)
    with st.spinner("Analysing full document and extracting claims…"):
        extractor = ClaimExtractor(model=model)
        # Build summary first so we can store it for verification
        doc_summary = extractor.llm.summarise_document(text)
        st.session_state.doc_summary = doc_summary
        claims, claim_error = extractor.extract_and_process_claims(
            text, remove_duplicates=remove_duplicates, max_claims=max_claims
        )

    if claim_error:
        st.session_state.extract_error = claim_error
        return

    st.session_state.extracted_claims = claims
    st.session_state.verification_results = []
    st.session_state.extract_success = f"✅ Extracted {len(claims)} factual claims from {st.session_state.document_metadata.get('pages', '?')} page(s)."
    st.session_state.active_tab = 1  # advance to Claims tab


def action_verify(model: str, min_confidence: int) -> None:
    """Run verification for all extracted claims."""
    claims = st.session_state.extracted_claims
    if not claims:
        st.session_state.verify_error = "No claims to verify."
        return

    st.session_state.verify_error = ""
    st.session_state.verify_success = ""

    progress_bar = st.progress(0, text="Starting verification…")
    status_text = st.empty()

    def on_progress(current: int, total: int) -> None:
        pct = int((current / total) * 100) if total else 0
        progress_bar.progress(pct, text=f"Verifying claim {current} of {total}…")
        status_text.caption(f"Claim {min(current + 1, total)} of {total}")

    verifier = Verifier(model=model)
    results, error = verifier.verify_claims(
        claims,
        doc_summary=st.session_state.get("doc_summary", ""),
        progress_callback=on_progress,
        min_confidence=min_confidence,
    )

    progress_bar.empty()
    status_text.empty()

    if error:
        st.session_state.verify_error = error
        return

    st.session_state.verification_results = results
    st.session_state.verify_success = f"✅ Verified {len(results)} claims."
    st.session_state.active_tab = 2  # advance to Evidence tab


# ── Workspace controls ───────────────────────────────────────────────────────


def workspace_controls():
    with st.container(border=True):
        upload_col, settings_col = st.columns([1.05, 0.95], gap="large")

        with upload_col:
            st.markdown(
                '<span class="control-label">Document</span>'
                '<span class="control-heading">Choose a PDF to analyze</span>'
                '<span class="control-copy">Upload a report, article, or whitepaper up to 25 MB.</span>',
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader(
                "Choose a PDF document",
                type=["pdf"],
                help="Maximum size: 25 MB.",
                label_visibility="collapsed",
            )

        with settings_col:
            st.markdown(
                '<span class="control-label">Analysis settings</span>'
                '<span class="control-heading">Configure verification</span>'
                '<span class="control-copy">Control claim extraction and the results included in your report.</span>',
                unsafe_allow_html=True,
            )
            model = st.selectbox(
                "Model",
                SUPPORTED_MODELS,
                index=(
                    SUPPORTED_MODELS.index(DEFAULT_MODEL)
                    if DEFAULT_MODEL in SUPPORTED_MODELS
                    else 0
                ),
            )
            st.markdown(
                '<div style="height:var(--sp-3)"></div>', unsafe_allow_html=True
            )
            remove_duplicates = st.toggle("Remove duplicate claims", value=True)
            st.markdown(
                '<div style="height:var(--sp-3)"></div>', unsafe_allow_html=True
            )
            max_col, conf_col = st.columns(2, gap="medium")
            with max_col:
                max_claims = st.slider("Maximum claims", 5, 100, 40, step=5)
            with conf_col:
                min_confidence = st.slider("Minimum confidence", 0, 100, 0, step=5)

        st.markdown(
            '<span class="workspace-footer">Live web evidence via Tavily, analyzed with OpenAI. '
            "Your PDF is processed only for this session.</span>",
            unsafe_allow_html=True,
        )

    return uploaded_file, model, remove_duplicates, max_claims, min_confidence


# ── Tab renderers ────────────────────────────────────────────────────────────


def render_tab_upload(uploaded_file, model, remove_duplicates, max_claims) -> None:
    st.markdown(
        "<span class='section-kicker'>Step 1</span>"
        "<span class='section-title'>Prepare your document</span>"
        "<span class='section-copy'>Upload a PDF and extract its checkable factual claims.</span>",
        unsafe_allow_html=True,
    )

    if not uploaded_file:
        st.markdown(
            "<div class='empty-state'><div class='empty-icon'>PDF</div>"
            "<b>No document selected</b>"
            "<span>Use the file picker above to choose a PDF.</span></div>",
            unsafe_allow_html=True,
        )
        return

    is_valid, file_error = validate_pdf_file(uploaded_file)
    if file_error:
        st.error(file_error)
    else:
        size_mb = uploaded_file.size / (1024 * 1024)
        st.markdown(
            f"<div class='file-card'>"
            f"<div class='file-name'>{escape(uploaded_file.name)}</div>"
            f"<div class='file-meta'>PDF · {size_mb:.2f} MB · Ready to analyze</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Show persisted messages
    if st.session_state.extract_error:
        st.error(st.session_state.extract_error)
    if st.session_state.extract_success:
        st.success(st.session_state.extract_success)

    if st.button(
        "Extract Text and Claims",
        type="primary",
        use_container_width=True,
        disabled=not is_valid,
    ):
        action_extract(uploaded_file, model, remove_duplicates, max_claims)
        st.rerun()

    metadata = st.session_state.document_metadata
    if metadata:
        st.markdown("<div style='height:var(--sp-4)'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Pages", metadata.get("pages", 0))
        c2.metric("File size", f"{metadata.get('file_size_mb', 0):.2f} MB")
        c3.metric("Characters extracted", f"{len(st.session_state.extracted_text):,}")


def render_tab_claims(model: str, min_confidence: int) -> None:
    st.markdown(
        "<span class='section-kicker'>Step 2</span>"
        "<span class='section-title'>Review extracted claims</span>"
        "<span class='section-copy'>Inspect the factual statements before verifying them against live web sources.</span>",
        unsafe_allow_html=True,
    )

    claims = st.session_state.extracted_claims
    if not claims:
        st.markdown(
            "<div class='empty-state'><div class='empty-icon'>02</div>"
            "<b>No claims yet</b>"
            "<span>Go to the Upload tab, select a PDF, and click Extract Text and Claims.</span></div>",
            unsafe_allow_html=True,
        )
        return

    rows = [
        {"#": i + 1, "Claim": c["claim"], "Type": c["type"]}
        for i, c in enumerate(claims)
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown(
        f"<div style='color:var(--muted);font-size:.85rem;margin:var(--sp-2) 0 var(--sp-5)'>"
        f"{len(claims)} claims ready for verification</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.verify_error:
        st.error(st.session_state.verify_error)
    if st.session_state.verify_success:
        st.success(st.session_state.verify_success)

    if st.button("Begin Verification", type="primary", use_container_width=True):
        action_verify(model, min_confidence)
        st.rerun()


def render_tab_evidence() -> None:
    st.markdown(
        "<span class='section-kicker'>Step 3</span>"
        "<span class='section-title'>Evidence report</span>"
        "<span class='section-copy'>Each claim verdict is paired with a confidence score, reasoning, and the sources used.</span>",
        unsafe_allow_html=True,
    )

    results = st.session_state.verification_results
    if not results:
        st.markdown(
            "<div class='empty-state'><div class='empty-icon'>03</div>"
            "<b>Verification has not run</b>"
            "<span>Go to the Claims tab and click Begin Verification.</span></div>",
            unsafe_allow_html=True,
        )
        return

    # Summary metrics
    stats = calculate_claim_statistics(results)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", stats["total"])
    c2.metric("Verified ✅", stats["verified"])
    c3.metric("Inaccurate ⚠️", stats["inaccurate"])
    c4.metric("False ❌", stats["false"])
    c5.metric("Avg confidence", f"{stats['avg_confidence']}%")

    st.divider()

    for i, result in enumerate(results, start=1):
        status = result.get("status", STATUS_UNVERIFIABLE)
        color = STATUS_COLORS.get(status, STATUS_COLORS[STATUS_UNVERIFIABLE])
        label = f"{i}. [{status}] {truncate_text(result.get('claim', ''), 90)}"
        with st.expander(label, expanded=i <= 2):
            st.markdown(
                f"<div class='status-card' style='border-left-color:{color}'>"
                f"<div class='status-line'>"
                f"<span class='status-pill' style='background:{color}'>{escape(status)}</span>"
                f"<span class='confidence'>{result.get('confidence', 0)}% confidence"
                f" &nbsp;·&nbsp; {escape(str(result.get('type', 'Other')))}</span>"
                f"</div>"
                f"<div class='claim-text'>{escape(str(result.get('claim', '')))}</div>"
                f"<div class='reason-text'>{escape(str(result.get('explanation', '')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if result.get("key_finding"):
                st.info(f"**Key finding:** {result['key_finding']}")
            sources = result.get("sources", [])
            if sources:
                st.markdown("**Sources**")
                for src in sources:
                    st.markdown(
                        f"- [{src.get('title', 'Source')}]({src.get('url', '')})"
                    )
            if result.get("evidence_snippet"):
                with st.popover("View evidence snippet"):
                    st.text(result["evidence_snippet"])


def render_tab_export() -> None:
    st.markdown(
        "<span class='section-kicker'>Step 4</span>"
        "<span class='section-title'>Export report</span>"
        "<span class='section-copy'>Download the completed evidence report in any format.</span>",
        unsafe_allow_html=True,
    )

    results = st.session_state.verification_results
    if not results:
        st.markdown(
            "<div class='empty-state'><div class='empty-icon'>04</div>"
            "<b>No report to export</b>"
            "<span>Complete verification first to unlock all download formats.</span></div>",
            unsafe_allow_html=True,
        )
        return

    generator = ReportGenerator()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    tab_std, tab_extra = st.tabs(["📊 Standard", "📁 Additional"])

    with tab_std:
        st.markdown("<div style='height:var(--sp-4)'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        csv_data, csv_err = generator.generate_csv_report(results)
        with c1:
            st.download_button(
                "📋 Download CSV",
                data=csv_data if not csv_err else "",
                file_name=f"factcheck_{ts}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=bool(csv_err),
            )
            if csv_err:
                st.caption(f"❌ {csv_err}")
            else:
                st.caption("Spreadsheet · Excel · Google Sheets")

        pdf_data, pdf_err = generator.generate_pdf_report(results)
        with c2:
            st.download_button(
                "📄 Download PDF",
                data=pdf_data if not pdf_err else b"",
                file_name=f"factcheck_{ts}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=bool(pdf_err),
            )
            if pdf_err:
                st.caption(f"❌ {pdf_err}")
            else:
                st.caption("Professional report · Print-ready")

        md_data, md_err = generator.generate_markdown_report(results)
        with c3:
            st.download_button(
                "📝 Download Markdown",
                data=md_data if not md_err else "",
                file_name=f"factcheck_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
                disabled=bool(md_err),
            )
            if md_err:
                st.caption(f"❌ {md_err}")
            else:
                st.caption("GitHub · Docs · Blogs")

    with tab_extra:
        st.markdown("<div style='height:var(--sp-4)'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)

        json_data, json_err = generator.generate_json_report(results)
        with c1:
            st.download_button(
                "📦 Download JSON",
                data=json_data if not json_err else "",
                file_name=f"factcheck_{ts}.json",
                mime="application/json",
                use_container_width=True,
                disabled=bool(json_err),
            )
            if json_err:
                st.caption(f"❌ {json_err}")
            else:
                st.caption("APIs · Databases · Data pipelines")

        html_data, html_err = generator.generate_html_report(results)
        with c2:
            st.download_button(
                "🌐 Download HTML",
                data=html_data if not html_err else "",
                file_name=f"factcheck_{ts}.html",
                mime="text/html",
                use_container_width=True,
                disabled=bool(html_err),
            )
            if html_err:
                st.caption(f"❌ {html_err}")
            else:
                st.caption("Interactive · Web sharing · Email")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    init_state()

    st.markdown(
        """
        <div id="fc-bg" aria-hidden="true"></div>
        <style>
        #fc-bg {
            position: fixed; inset: 0; z-index: 0;
            pointer-events: none; overflow: hidden; background: #0a0a0a;
        }
        #fc-bg canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
        #root, .stApp, [data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
        @media (prefers-reduced-motion: reduce) { #fc-bg { display: none; } }
        </style>
        <script>
        (function () {
            if (window._fcBgInit) return;
            window._fcBgInit = true;
            var wrap = document.getElementById('fc-bg');
            var cv = document.createElement('canvas');
            wrap.appendChild(cv);
            var ctx = cv.getContext('2d');
            var W, H, DPR, t = 0, MX = 0, MY = 0;
            var rnd = function(a,b){ return a + Math.random()*(b-a); };
            var PTS = [];
            function buildPts() {
                PTS = [];
                var n = Math.round(Math.min(W,H)/14);
                for (var i=0;i<n;i++) PTS.push({
                    x:rnd(0,W), y:rnd(0,H), vx:rnd(-0.15,0.15), vy:rnd(-0.12,0.12),
                    z:rnd(0.2,1), r:rnd(1,2.8), h:rnd(200,230), a:rnd(0.25,0.65), p:rnd(0,Math.PI*2)
                });
            }
            function resize() {
                DPR = Math.min(window.devicePixelRatio||1,2);
                W = window.innerWidth; H = window.innerHeight;
                cv.width=Math.round(W*DPR); cv.height=Math.round(H*DPR);
                cv.style.width=W+'px'; cv.style.height=H+'px';
                ctx.setTransform(DPR,0,0,DPR,0,0);
                buildPts();
            }
            window.addEventListener('resize',resize,{passive:true});
            resize();
            window.addEventListener('pointermove',function(e){
                MX=(e.clientX/W-0.5)*2; MY=(e.clientY/H-0.5)*2;
            },{passive:true});
            function draw() {
                t+=0.4;
                ctx.fillStyle='rgba(10,10,10,0.82)'; ctx.fillRect(0,0,W,H);
                var blobs=[
                    {cx:W*0.15+MX*40,cy:H*0.12+MY*30,rx:W*0.52,ry:H*0.44,c:'rgba(30,64,175,0.13)',a:Math.sin(t*0.004)*0.4},
                    {cx:W*0.85+MX*-32,cy:H*0.20+MY*22,rx:W*0.48,ry:H*0.40,c:'rgba(16,185,129,0.08)',a:Math.cos(t*0.005)*0.3},
                    {cx:W*0.50+MX*20,cy:H*0.82+MY*-20,rx:W*0.58,ry:H*0.38,c:'rgba(59,130,246,0.10)',a:Math.sin(t*0.003)*0.25}
                ];
                for (var b=0;b<blobs.length;b++) {
                    var bl=blobs[b], R=Math.max(bl.rx,bl.ry);
                    ctx.save(); ctx.translate(bl.cx,bl.cy); ctx.rotate(bl.a); ctx.scale(bl.rx/R,bl.ry/R);
                    var gr=ctx.createRadialGradient(0,0,0,0,0,R);
                    gr.addColorStop(0,bl.c); gr.addColorStop(1,'rgba(0,0,0,0)');
                    ctx.fillStyle=gr; ctx.beginPath(); ctx.arc(0,0,R,0,Math.PI*2); ctx.fill(); ctx.restore();
                }
                var rings=[
                    {rx:Math.min(W,H)*0.42,ry:Math.min(W,H)*0.12,cx:W*0.5+MX*-18,cy:H*0.5+MY*-10,c:'rgba(59,130,246,0.20)',sp:0.0013},
                    {rx:Math.min(W,H)*0.30,ry:Math.min(W,H)*0.085,cx:W*0.5+MX*14,cy:H*0.5+MY*8,c:'rgba(96,165,250,0.13)',sp:-0.002},
                    {rx:Math.min(W,H)*0.20,ry:Math.min(W,H)*0.060,cx:W*0.5+MX*9,cy:H*0.5+MY*5,c:'rgba(16,185,129,0.11)',sp:0.0026}
                ];
                for (var ri=0;ri<rings.length;ri++) {
                    var rg=rings[ri];
                    ctx.save(); ctx.strokeStyle=rg.c; ctx.lineWidth=1;
                    ctx.beginPath(); ctx.ellipse(rg.cx,rg.cy,rg.rx,rg.ry,t*rg.sp,0,Math.PI*2); ctx.stroke();
                    var ta=t*rg.sp*1.6, dnx=rg.cx+Math.cos(ta)*rg.rx, dny=rg.cy+Math.sin(ta)*rg.ry;
                    var gd=ctx.createRadialGradient(dnx,dny,0,dnx,dny,7);
                    gd.addColorStop(0,'rgba(147,197,253,0.95)'); gd.addColorStop(1,'rgba(147,197,253,0)');
                    ctx.fillStyle=gd; ctx.beginPath(); ctx.arc(dnx,dny,7,0,Math.PI*2); ctx.fill(); ctx.restore();
                }
                ctx.globalCompositeOperation='lighter';
                var thresh=Math.min(W,H)*0.20;
                for (var i=0;i<PTS.length;i++) {
                    var p=PTS[i];
                    p.x+=p.vx+MX*0.25*p.z; p.y+=p.vy+MY*0.20*p.z;
                    if(p.x<-20)p.x=W+20; if(p.x>W+20)p.x=-20;
                    if(p.y<-20)p.y=H+20; if(p.y>H+20)p.y=-20;
                    for (var j=i+1;j<PTS.length;j++) {
                        var q=PTS[j], dx=p.x-q.x, dy=p.y-q.y, d=Math.sqrt(dx*dx+dy*dy);
                        if(d<thresh){
                            ctx.strokeStyle='rgba(59,130,246,'+((1-d/thresh)*0.20)+')';
                            ctx.lineWidth=0.6; ctx.beginPath(); ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y); ctx.stroke();
                        }
                    }
                    var gp=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,p.r*3);
                    gp.addColorStop(0,'hsla('+p.h+',85%,65%,'+p.a+')'); gp.addColorStop(1,'hsla('+p.h+',85%,65%,0)');
                    ctx.fillStyle=gp; ctx.beginPath(); ctx.arc(p.x,p.y,p.r*3,0,Math.PI*2); ctx.fill();
                }
                ctx.globalCompositeOperation='source-over';
                for (var si=0;si<PTS.length;si++) {
                    var s=PTS[si], tw=0.4+Math.sin(t*0.022+s.p)*0.6;
                    ctx.fillStyle='hsla(215,70%,88%,'+(s.a*0.5*tw)+')';
                    ctx.beginPath(); ctx.arc(s.x+MX*s.z*6,s.y+MY*s.z*5,s.r*0.5*tw,0,Math.PI*2); ctx.fill();
                }
                requestAnimationFrame(draw);
            }
            draw();
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Evidence-led document review</div>
            <h1>Turn dense PDFs into claims you can trust.</h1>
            <p>Extract factual statements, verify them against live web evidence, and produce a source-backed report in one focused workflow.</p>
            <div class="trust-row">
                <span class="trust-chip">Live source search</span>
                <span class="trust-chip">Claim-level verdicts</span>
                <span class="trust-chip">5 export formats</span>
                <span class="trust-chip">OCR for scanned PDFs</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not has_required_keys():
        st.error(ERROR_API_KEY)
        st.stop()

    uploaded_file, model, remove_duplicates, max_claims, min_confidence = (
        workspace_controls()
    )
    reset_for_new_file(uploaded_file)

    step = st.session_state.active_tab
    has_claims = bool(st.session_state.extracted_claims)
    has_results = bool(st.session_state.verification_results)

    def _cls(idx: int) -> str:
        if idx < step or (idx == 0 and has_claims) or (idx == 1 and has_results):
            return "done"
        if idx == step:
            return "active"
        return ""

    st.markdown(
        f"""
        <div class="workflow">
            <div class="workflow-step {_cls(0)}">
                <div class="step-number">1</div>
                <div class="step-copy"><b>Upload</b><span>Select and process a PDF</span></div>
            </div>
            <div class="workflow-step {_cls(1)}">
                <div class="step-number">2</div>
                <div class="step-copy"><b>Review claims</b><span>Inspect extracted statements</span></div>
            </div>
            <div class="workflow-step {_cls(2)}">
                <div class="step-number">3</div>
                <div class="step-copy"><b>Verify &amp; export</b><span>Evidence check and download</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["01  Upload", "02  Claims", "03  Evidence", "04  Export"])

    with tabs[0]:
        render_tab_upload(uploaded_file, model, remove_duplicates, max_claims)
    with tabs[1]:
        render_tab_claims(model, min_confidence)
    with tabs[2]:
        render_tab_evidence()
    with tabs[3]:
        render_tab_export()


if __name__ == "__main__":
    main()