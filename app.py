"""FilamentMonitor — Main Streamlit application entry point."""
import logging
import sys
from pathlib import Path

import streamlit as st

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Database init ─────────────────────────────────────────────────────────────
from db.schema import init_db
init_db()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(ROOT / "data" / "app.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FilamentMonitor 🧵",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
css_path = ROOT / "assets" / "style.css"
if css_path.exists():
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style='text-align: center; padding: 0.5rem 0 1rem 0;'>
        <h1 style='margin: 0; font-size: 2rem;'>🧵 FilamentMonitor</h1>
        <p style='color: #888; margin: 0;'>Моніторинг цін · Склад · Журнал друку · Аналітика</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Tab routing ───────────────────────────────────────────────────────────────
TABS = [
    "🛒 Моніторинг цін",
    "📦 Мій склад",
    "🖨️ Журнал друку",
    "📊 Аналітика",
]

# Support switching tabs programmatically (e.g. from inventory → prices)
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 0

tab_objects = st.tabs(TABS)

with tab_objects[0]:
    try:
        from pages.tab1_monitoring import render as render_prices
        render_prices()
    except Exception as e:
        st.error(f"Помилка у вкладці «Моніторинг цін»: {e}")
        logger.exception("Tab 1 error")

with tab_objects[1]:
    try:
        from pages.tab2_inventory import render as render_inventory
        render_inventory()
    except Exception as e:
        st.error(f"Помилка у вкладці «Мій склад»: {e}")
        logger.exception("Tab 2 error")

with tab_objects[2]:
    try:
        from pages.tab3_journal import render as render_journal
        render_journal()
    except Exception as e:
        st.error(f"Помилка у вкладці «Журнал друку»: {e}")
        logger.exception("Tab 3 error")

with tab_objects[3]:
    try:
        from pages.tab4_analytics import render as render_analytics
        render_analytics()
    except Exception as e:
        st.error(f"Помилка у вкладці «Аналітика»: {e}")
        logger.exception("Tab 4 error")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "FilamentMonitor v1.0 · Python + Streamlit + SQLite · Дані зберігаються локально в `data/filament.db`"
)
