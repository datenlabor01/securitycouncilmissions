import json
from pathlib import Path
import streamlit as st


def metric_card(label: str, value: str):
    """Renders a styled metric card with label and value."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_pills(items, empty_text="None recorded"):
    """Renders a list of items as styled CSS pills."""
    if not items:
        st.caption(empty_text)
        return

    html_str = "".join([f'<span class="pill">{item}</span>' for item in items])
    st.markdown(html_str, unsafe_allow_html=True)


@st.cache_data
def load_json_file(file_path: str):
    """Safely loads a JSON file from a given path."""
    path = Path(file_path)

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_json_payload(data):
    """Normalizes JSON payload structure into a standard list format."""
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "reports" in data:
        return data["reports"]

    if isinstance(data, dict):
        return [data]

    return []