"""Shared look for CAMR's Streamlit screens (the personal app and the inspector).

Dark, high-contrast and minimal. The accent colours are the validated figure
palette used in docs/figures (blue #2a78d6, green #1baf7a, orange #eb6834), so
screenshots and charts read as one product. No web fonts are fetched: the app
must work offline, so a system font stack is used.
"""

from __future__ import annotations

ACCENT, GOOD, WARN = "#2a78d6", "#1baf7a", "#eb6834"
BG, SURFACE, SURFACE_2, BORDER = "#0b0e14", "#121722", "#18202e", "#243044"
TEXT, MUTED = "#e6e9ef", "#8b93a7"

# Passed to `streamlit run` so the base theme (widgets, charts) matches the CSS below.
STREAMLIT_FLAGS = [
    "--theme.base", "dark",
    "--theme.primaryColor", ACCENT,
    "--theme.backgroundColor", BG,
    "--theme.secondaryBackgroundColor", SURFACE,
    "--theme.textColor", TEXT,
    "--browser.gatherUsageStats", "false",
    "--server.fileWatcherType", "none",  # the watcher crawls torch/transformers modules and floods the log
]

CSS = f"""
<style>
:root {{ --accent:{ACCENT}; --good:{GOOD}; --warn:{WARN}; --bg:{BG}; --surface:{SURFACE};
        --surface2:{SURFACE_2}; --border:{BORDER}; --text:{TEXT}; --muted:{MUTED}; }}
html, body, [class*="css"], .stApp {{
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
}}
.stApp {{ background: radial-gradient(1200px 600px at 80% -10%, #14213a 0%, var(--bg) 55%) fixed; }}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 650; }}
h1 {{ font-size: 2.0rem; }}
section[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] .stRadio label {{ padding: 6px 10px; border-radius: 8px; }}
section[data-testid="stSidebar"] .stRadio label:hover {{ background: var(--surface2); }}
[data-testid="stMetric"] {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 14px 18px; }}
[data-testid="stMetricLabel"] {{ color: var(--muted); text-transform: uppercase; font-size: .72rem;
  letter-spacing: .06em; }}
[data-testid="stMetricValue"] {{ font-weight: 650; }}
[data-testid="stDataFrame"], .stTable {{ border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
.stProgress > div > div > div {{ background: linear-gradient(90deg, var(--accent), #5aa2f0); }}
.stButton > button, .stDownloadButton > button {{ border-radius: 10px; border: 1px solid var(--border);
  background: var(--surface2); color: var(--text); }}
.stButton > button:hover {{ border-color: var(--accent); color: #fff; }}
[data-testid="stChatMessage"] {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 10px 14px; }}
[data-testid="stChatInput"] textarea {{ background: var(--surface2); }}
.camr-brand {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.15rem; }}
.camr-dot {{ width:12px; height:12px; border-radius:50%; background: conic-gradient(var(--accent), var(--good), var(--accent));
  box-shadow: 0 0 14px var(--accent); }}
.camr-sub {{ color: var(--muted); font-size: .82rem; margin-top: -4px; }}
.camr-chip {{ display:inline-block; margin:4px 6px 0 0; padding:3px 10px; border-radius:999px; font-size:.78rem;
  background: var(--surface2); border:1px solid var(--border); color: var(--text); }}
.camr-chip b {{ color: var(--accent); font-weight:600; }}
.camr-pill-good {{ color: var(--good); }} .camr-pill-warn {{ color: var(--warn); }}
.camr-card {{ background: var(--surface); border:1px solid var(--border); border-radius:16px; padding:16px 18px;
  margin-bottom: 12px; }}
.camr-muted {{ color: var(--muted); }}
.camr-hero {{ font-size: 2.4rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; }}
.camr-hero span {{ background: linear-gradient(90deg, var(--accent), var(--good)); -webkit-background-clip: text;
  background-clip: text; color: transparent; }}
</style>
"""


def apply(st) -> None:
    """Inject the shared stylesheet into a Streamlit page."""
    st.markdown(CSS, unsafe_allow_html=True)


def brand(st, subtitle: str) -> None:
    st.markdown(f'<div class="camr-brand"><div class="camr-dot"></div>CAMR</div>'
                f'<div class="camr-sub">{subtitle}</div>', unsafe_allow_html=True)
