"""Neural Chess design system: warm charcoal, bone white, and brass gold.

The palette is inspired by the CHESS GAME UI reference and the existing
interactive board, using a dark room-like background with a single warm metal
accent so the chessboard remains the focal point.
"""

THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@500;600;700;800&display=swap');

    :root {
        --bg: #141311;
        --bg-deep: #0F0E0C;
        --surface: #1E1D1A;
        --surface-2: #26241F;
        --surface-3: #2C2B29;
        --border: rgba(244, 239, 228, 0.08);
        --border-strong: rgba(244, 239, 228, 0.16);
        --text: #F4EFE4;
        --muted: #A9A296;
        --faint: #726D64;
        --gold: #D8B45A;
        --gold-bright: #E8C87C;
        --gold-soft: rgba(216, 180, 90, 0.13);
        --gold-line: rgba(216, 180, 90, 0.34);
        --green: #8FBF6A;
        --green-soft: rgba(143, 191, 106, 0.13);
        --red: #E07A6A;
        --red-soft: rgba(224, 122, 106, 0.13);
        --blue: #86A9C9;
    }

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .stApp {
        background:
            radial-gradient(80% 55% at 78% -10%, rgba(216, 180, 90, 0.10), transparent 55%),
            radial-gradient(60% 45% at 0% 15%, rgba(143, 191, 106, 0.05), transparent 50%),
            linear-gradient(180deg, #171614 0%, var(--bg) 45%, var(--bg-deep) 100%) !important;
        color: var(--text) !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
    }
    [data-testid="stToolbar"], #MainMenu, footer { display: none !important; }

    .block-container {
        max-width: 1380px !important;
        padding: 1.4rem 2.2rem 4rem 2.2rem !important;
    }

    h1, h2, h3, h4, h5, .section-title, .hero-title, .auth-hero-title {
        font-family: 'Sora', 'Inter', sans-serif !important;
        color: var(--text) !important;
        letter-spacing: -0.02em;
    }
    p, li, .stMarkdown { color: var(--text); }
    .stCaption, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
    a { color: var(--gold) !important; text-decoration: none; }
    a:hover { color: var(--gold-bright) !important; }

    /* ---------------------------------------------------------------- Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #121110 0%, #100F0D 100%) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebarUserContent"] {
        padding: 1.35rem 1rem 2rem 1rem !important;
    }
    [data-testid="stSidebar"] .stMarkdown p { margin-bottom: 0; }
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 3px !important;
        display: flex;
        flex-direction: column;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        width: 100%;
        padding: 10px 12px !important;
        border-radius: 10px !important;
        border: 1px solid transparent;
        background: transparent !important;
        color: var(--muted) !important;
        font-size: 0.86rem !important;
        font-weight: 600 !important;
        transition: background .15s ease, color .15s ease, border-color .15s ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255, 255, 255, 0.035) !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: var(--gold-soft) !important;
        border-color: var(--gold-line) !important;
        color: var(--gold-bright) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* --------------------------------------------------------------- Main radio chips */
    [data-testid="stMain"] div[role="radiogroup"] {
        flex-direction: row !important;
        flex-wrap: wrap;
        gap: 8px !important;
    }
    [data-testid="stMain"] div[role="radiogroup"] > label {
        padding: 8px 15px !important;
        border-radius: 999px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
        color: var(--muted) !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        transition: all .15s ease;
    }
    [data-testid="stMain"] div[role="radiogroup"] > label:hover {
        border-color: var(--border-strong) !important;
        color: var(--text) !important;
    }
    [data-testid="stMain"] div[role="radiogroup"] > label:has(input:checked) {
        border-color: var(--gold-line) !important;
        background: var(--gold-soft) !important;
        color: var(--gold-bright) !important;
    }
    [data-testid="stMain"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* ------------------------------------------------------------------ Buttons */
    .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.86rem !important;
        border-radius: 10px !important;
        border: 1px solid var(--border-strong) !important;
        background: var(--surface-2) !important;
        color: var(--text) !important;
        padding: 0.55rem 1.05rem !important;
        transition: transform .15s ease, background .15s ease, border-color .15s ease, box-shadow .15s ease !important;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
        background: var(--surface-3) !important;
        border-color: var(--gold-line) !important;
        transform: translateY(-1px);
    }
    .stButton > button:focus, .stFormSubmitButton > button:focus {
        box-shadow: 0 0 0 2px rgba(216, 180, 90, 0.25) !important;
    }
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, var(--gold-bright), #C49B45) !important;
        border: none !important;
        color: #171410 !important;
        box-shadow: 0 8px 22px rgba(216, 180, 90, 0.18) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        filter: brightness(1.05);
        box-shadow: 0 10px 26px rgba(216, 180, 90, 0.27) !important;
    }
    .stButton > button p, .stFormSubmitButton > button p { font-size: 0.86rem !important; }

    /* ------------------------------------------------------------------- Inputs */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background: #12110F !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
        padding: 0.7rem 0.85rem !important;
        font-size: 0.9rem !important;
        transition: border-color .15s ease, box-shadow .15s ease !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
        border-color: var(--gold-line) !important;
        box-shadow: 0 0 0 3px rgba(216, 180, 90, 0.10) !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--faint) !important; }
    .stTextInput label p, .stTextArea label p, .stNumberInput label p,
    .stSelectbox label p, .stFileUploader label p, .stRadio label p {
        color: var(--muted) !important;
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    [data-baseweb="select"] > div {
        background: #12110F !important;
        border-color: var(--border-strong) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }
    [data-baseweb="popover"] [role="listbox"] {
        background: var(--surface-2) !important;
        border: 1px solid var(--border-strong) !important;
    }

    /* --------------------------------------------------------------------- Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        background: #12110F !important;
        padding: 5px !important;
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important;
        padding: 8px 16px !important;
        color: var(--muted) !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
    }
    .stTabs [aria-selected="true"] {
        background: var(--surface-2) !important;
        color: var(--gold-bright) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background: transparent !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ------------------------------------------------------------------- Forms */
    [data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        padding: 0.35rem !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 1rem 1.1rem !important;
    }

    /* ------------------------------------------------------------- File uploader */
    [data-testid="stFileUploaderDropzone"] {
        background: #12110F !important;
        border: 1px dashed var(--border-strong) !important;
        border-radius: 12px !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background: var(--surface-2) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }

    /* ---------------------------------------------------------------- Expander */
    [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: var(--text) !important;
    }
    [data-testid="stExpander"] summary:hover { color: var(--gold-bright) !important; }

    /* ------------------------------------------------------------------ Alerts */
    [data-testid="stAlert"] {
        border-radius: 12px !important;
        border: 1px solid var(--border-strong) !important;
        background: var(--surface) !important;
    }

    /* ------------------------------------------------------------------ Divider */
    hr, [data-testid="stDivider"] { border-color: var(--border) !important; }

    /* =========================================================== Custom classes */
    .brand { display: flex; align-items: center; gap: 12px; padding: 2px 2px 18px 2px; }
    .brand-mark {
        width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
        background: linear-gradient(135deg, rgba(216,180,90,.24), rgba(216,180,90,.05));
        border: 1px solid var(--gold-line); color: var(--gold);
        box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
    }
    .brand-copy { line-height: 1.1; }
    .brand-name {
        font-family: 'Sora', sans-serif; font-weight: 800; font-size: 0.8rem;
        letter-spacing: 0.17em; color: var(--text);
    }
    .brand-tag {
        margin-top: 5px; font-size: 0.62rem; letter-spacing: 0.12em;
        text-transform: uppercase; color: var(--faint);
    }

    .avatar {
        border-radius: 50%; display: grid; place-items: center; overflow: hidden;
        background: linear-gradient(135deg, #3A362F, #242321);
        border: 1px solid var(--border-strong);
        color: var(--gold-bright); font-family: 'Sora', sans-serif; font-weight: 700;
        flex-shrink: 0; letter-spacing: 0.02em;
    }
    .avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }

    .hero {
        position: relative; overflow: hidden; border: 1px solid var(--border);
        border-radius: 22px; padding: 34px 36px; margin-bottom: 18px;
        background:
            radial-gradient(110% 160% at 92% 0%, rgba(216,180,90,.16), transparent 55%),
            linear-gradient(135deg, #27251F 0%, #1A1916 55%, #171614 100%);
    }
    .hero::after {
        content: ""; position: absolute; right: -70px; bottom: -110px;
        width: 300px; height: 300px; opacity: 0.06; color: var(--gold);
        background: currentColor;
        mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3.2 7.4l4.3 3.7L12 4.6l4.5 6.5 4.3-3.7-1.7 10.2a1.2 1.2 0 0 1-1.2 1H6.1a1.2 1.2 0 0 1-1.2-1L3.2 7.4z'/%3E%3C/svg%3E") center / contain no-repeat;
        -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3.2 7.4l4.3 3.7L12 4.6l4.5 6.5 4.3-3.7-1.7 10.2a1.2 1.2 0 0 1-1.2 1H6.1a1.2 1.2 0 0 1-1.2-1L3.2 7.4z'/%3E%3C/svg%3E") center / contain no-repeat;
    }
    .hero > * { position: relative; z-index: 1; }
    .hero-kicker {
        font-size: 0.7rem; letter-spacing: 0.18em; text-transform: uppercase;
        color: var(--gold); font-weight: 700; margin-bottom: 10px;
    }
    .hero-title {
        font-size: 2.45rem; font-weight: 800; line-height: 1.06; margin: 0;
        color: var(--text);
    }
    .hero-title .accent { color: var(--gold-bright); }
    .hero-sub { color: var(--muted); font-size: 0.95rem; margin-top: 12px; max-width: 560px; line-height: 1.6; }
    .hero-actions { display: flex; gap: 10px; margin-top: 22px; flex-wrap: wrap; }

    .section-head { margin: 26px 0 12px 0; }
    .section-kicker {
        font-size: 0.66rem; letter-spacing: 0.18em; text-transform: uppercase;
        color: var(--gold); font-weight: 700; margin-bottom: 5px;
    }
    .section-title { font-size: 1.25rem; font-weight: 700; color: var(--text); }
    .section-sub { color: var(--muted); font-size: 0.86rem; margin-top: 4px; }

    .stat-card {
        background: linear-gradient(160deg, var(--surface-2), var(--surface));
        border: 1px solid var(--border); border-radius: 15px;
        padding: 16px 18px; min-height: 104px;
    }
    .stat-label {
        font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
        color: var(--faint); font-weight: 700;
    }
    .stat-value {
        font-family: 'Sora', sans-serif; font-size: 1.75rem; font-weight: 700;
        color: var(--text); margin-top: 6px; line-height: 1.1;
    }
    .stat-hint { font-size: 0.74rem; color: var(--muted); margin-top: 4px; }
    .stat-gold .stat-value { color: var(--gold-bright); }
    .stat-green .stat-value { color: var(--green); }

    .challenge-list { display: flex; flex-direction: column; gap: 6px; }
    .challenge-row {
        display: grid; grid-template-columns: 40px 1fr auto auto; align-items: center;
        gap: 12px; padding: 10px 12px; border-radius: 12px;
        border: 1px solid transparent; background: rgba(255,255,255,.018);
    }
    .challenge-row:hover { border-color: var(--border); background: var(--surface-2); }
    .challenge-info { min-width: 0; }
    .challenge-name {
        font-weight: 700; font-size: 0.86rem; color: var(--text);
        letter-spacing: 0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .challenge-meta { font-size: 0.72rem; color: var(--muted); margin-top: 2px; }
    .challenge-time {
        font-family: 'Sora', sans-serif; font-weight: 700; font-size: 0.88rem;
        color: var(--gold-bright); font-variant-numeric: tabular-nums;
    }
    .challenge-side {
        font-size: 0.62rem; letter-spacing: 0.1em; text-transform: uppercase;
        color: var(--faint); border: 1px solid var(--border); border-radius: 999px;
        padding: 4px 9px;
    }

    .board-table { display: flex; flex-direction: column; gap: 4px; }
    .board-row {
        display: grid; grid-template-columns: 34px 38px 1fr auto; align-items: center;
        gap: 12px; padding: 10px 12px; border-radius: 12px; border: 1px solid transparent;
    }
    .board-row:hover { background: var(--surface-2); border-color: var(--border); }
    .board-row.is-me { background: var(--gold-soft); border-color: var(--gold-line); }
    .board-rank {
        font-family: 'Sora', sans-serif; font-size: 0.78rem; font-weight: 700;
        color: var(--faint); font-variant-numeric: tabular-nums;
    }
    .board-row.is-me .board-rank { color: var(--gold); }
    .board-name { font-weight: 600; font-size: 0.88rem; color: var(--text); min-width: 0; }
    .board-name > div:first-child { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .board-sub { font-size: 0.72rem; color: var(--muted); font-weight: 400; margin-top: 2px; }
    .board-rating {
        font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1rem;
        color: var(--gold-bright); font-variant-numeric: tabular-nums;
    }
    .board-side { font-size: 0.75rem; }

    .pill {
        display: inline-flex; align-items: center; gap: 5px; border-radius: 999px;
        padding: 4px 10px; font-size: 0.66rem; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase; border: 1px solid transparent;
    }
    .pill-gold { background: var(--gold-soft); color: var(--gold-bright); border-color: var(--gold-line); }
    .pill-green { background: var(--green-soft); color: var(--green); border-color: rgba(143,191,106,.3); }
    .pill-red { background: var(--red-soft); color: var(--red); border-color: rgba(224,122,106,.3); }
    .pill-muted { background: rgba(255,255,255,.05); color: var(--muted); border-color: var(--border); }

    .empty-state {
        border: 1px dashed var(--border-strong); border-radius: 16px;
        padding: 34px 22px; text-align: center; background: rgba(255,255,255,.014);
    }
    .empty-crown { color: var(--gold); opacity: 0.7; margin-bottom: 10px; }
    .empty-title { font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1rem; }
    .empty-text { color: var(--muted); font-size: 0.83rem; margin-top: 5px; }

    .user-chip {
        display: flex; align-items: center; gap: 12px; background: var(--surface);
        border: 1px solid var(--border); border-radius: 14px; padding: 12px;
    }
    .user-chip .name { font-weight: 700; font-size: 0.86rem; line-height: 1.2; }
    .user-chip .meta { color: var(--gold); font-size: 0.72rem; margin-top: 3px; }
    .side-label {
        font-size: 0.62rem; letter-spacing: 0.16em; text-transform: uppercase;
        color: var(--faint); font-weight: 700; margin: 18px 0 8px 2px;
    }
    .side-card {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 13px; padding: 12px 13px;
    }
    .statusline { display: flex; align-items: center; gap: 8px; font-size: 0.74rem; color: var(--muted); }
    .statusline + .statusline { margin-top: 7px; }
    .status-dot {
        width: 7px; height: 7px; border-radius: 50%; background: var(--green);
        box-shadow: 0 0 9px rgba(143,191,106,.65); flex-shrink: 0;
    }
    .status-dot.off { background: var(--faint); box-shadow: none; }
    .status-dot.gold { background: var(--gold); box-shadow: 0 0 9px rgba(216,180,90,.55); }

    .auth-hero {
        position: relative; overflow: hidden; border-radius: 24px; border: 1px solid var(--border);
        min-height: 640px; padding: 42px 44px; display: flex; flex-direction: column;
        background:
            radial-gradient(95% 75% at 18% 0%, rgba(216,180,90,.20), transparent 58%),
            radial-gradient(70% 60% at 100% 100%, rgba(143,191,106,.07), transparent 60%),
            linear-gradient(165deg, #28251F 0%, #191815 55%, #12110F 100%);
    }
    .auth-hero::before {
        content: ""; position: absolute; inset: 0; opacity: 0.5;
        background-image:
            linear-gradient(45deg, rgba(216,180,90,.055) 25%, transparent 25%, transparent 75%, rgba(216,180,90,.055) 75%),
            linear-gradient(45deg, rgba(216,180,90,.055) 25%, transparent 25%, transparent 75%, rgba(216,180,90,.055) 75%);
        background-size: 52px 52px; background-position: 0 0, 26px 26px;
        mask-image: linear-gradient(to bottom, rgba(0,0,0,.55), transparent 78%);
        -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,.55), transparent 78%);
    }
    .auth-hero > * { position: relative; z-index: 1; }
    .auth-hero-title {
        font-family: 'Sora', sans-serif; font-size: 2.9rem; font-weight: 800;
        line-height: 1.03; margin: 26px 0 0 0;
    }
    .auth-hero-title .accent { color: var(--gold-bright); }
    .auth-hero-sub { color: var(--muted); font-size: 0.96rem; line-height: 1.65; margin-top: 16px; max-width: 430px; }
    .auth-points { display: grid; gap: 12px; margin-top: auto; padding-top: 34px; }
    .auth-point { display: flex; align-items: center; gap: 12px; color: var(--text); font-size: 0.86rem; }
    .auth-point-icon {
        width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center;
        background: rgba(216,180,90,.10); border: 1px solid var(--gold-line); color: var(--gold);
        flex-shrink: 0;
    }
    .auth-card-title { font-family: 'Sora', sans-serif; font-size: 1.55rem; font-weight: 700; margin: 0; }
    .auth-card-sub { color: var(--muted); font-size: 0.85rem; margin: 5px 0 18px 0; }
    .auth-switch { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 10px; }
    .auth-switch b { color: var(--gold); }

    .page-top {
        display: flex; align-items: flex-end; justify-content: space-between;
        gap: 18px; margin-bottom: 6px;
    }
    .page-top .eyebrow {
        font-size: 0.66rem; letter-spacing: 0.18em; text-transform: uppercase;
        color: var(--gold); font-weight: 700;
    }
    .page-top .title { font-family: 'Sora', sans-serif; font-size: 1.7rem; font-weight: 700; margin-top: 3px; }
    .page-top .sub { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }

    .feature-card {
        height: 100%; border: 1px solid var(--border); border-radius: 16px;
        padding: 18px; background: linear-gradient(160deg, var(--surface-2), var(--surface));
        transition: border-color .15s ease, transform .15s ease;
    }
    .feature-card:hover { border-color: var(--gold-line); transform: translateY(-2px); }
    .feature-kicker { font-size: 0.62rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--gold); font-weight: 700; }
    .feature-title { font-family: 'Sora', sans-serif; font-size: 1.02rem; font-weight: 700; margin-top: 6px; }
    .feature-text { color: var(--muted); font-size: 0.8rem; line-height: 1.55; margin-top: 6px; }
    .feature-meta { color: var(--faint); font-size: 0.7rem; margin-top: 12px; }

    .lesson-row {
        display: flex; justify-content: space-between; gap: 16px; align-items: center;
        padding: 14px 2px; border-bottom: 1px solid var(--border);
    }
    .lesson-row:last-child { border-bottom: none; }
    .lesson-title { font-weight: 600; font-size: 0.9rem; }
    .lesson-meta { color: var(--muted); font-size: 0.76rem; margin-top: 2px; }

    .board-wrap {
        border: 1px solid var(--border); border-radius: 18px; overflow: hidden;
        background: #12110F;
    }
    .board-caption {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px 16px; border-bottom: 1px solid var(--border);
        background: var(--surface);
    }
    .board-caption .label { font-size: 0.7rem; letter-spacing: 0.13em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
    .board-caption .value { color: var(--gold-bright); font-weight: 700; font-size: 0.85rem; }

    .muted { color: var(--muted) !important; }
    .faint { color: var(--faint) !important; }
    .gold { color: var(--gold-bright) !important; }
    .mono { font-family: 'Sora', monospace !important; font-variant-numeric: tabular-nums; }
    .tiny { font-size: 0.72rem; }
    .divider { height: 1px; background: var(--border); margin: 16px 0; }

    @media (max-width: 980px) {
        .block-container { padding: 1rem 1rem 3rem 1rem !important; }
        .hero { padding: 26px 22px; }
        .hero-title { font-size: 1.85rem; }
        .auth-hero { min-height: 380px; padding: 30px 26px; }
        .auth-hero-title { font-size: 2.1rem; }
        .auth-points { display: none; }
        .challenge-row { grid-template-columns: 34px 1fr auto; }
        .challenge-side { display: none; }
    }
</style>
"""
