import streamlit as st
from config import CUSTOM_CSS
from tor_dashboard import render_tor_dashboard
from reports_dashboard import render_reports_dashboard

# --------------------------------------------------
# Page Setup
# --------------------------------------------------
st.set_page_config(
    page_title="Security Council Missions Dashboard",
    page_icon="🌐",
    layout="wide"
)

# Apply CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# App Header
st.markdown(
    """
    <div class="dashboard-title">🌐 Security Council Missions Dashboard</div>
    <div class="dashboard-subtitle">
    AI-generated analysis for Security Council Missions.
    </div>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# Tabs
# --------------------------------------------------
main_tab_1, main_tab_2 = st.tabs(
    [
        "Mission TOR Objectives",
        "Mission Reports Analytics"
    ]
)

with main_tab_1:
    render_tor_dashboard()

with main_tab_2:
    render_reports_dashboard()