import networkx as nx
import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import re
from pyvis.network import Network
import streamlit.components.v1 as components
import html

# --------------------------------------------------
# Page setup
# --------------------------------------------------

st.set_page_config(
    page_title="Security Council Missions Dashboard",
    page_icon="🌐",
    layout="wide"
)

# --------------------------------------------------
# File paths
# --------------------------------------------------

TOR_FILE = "tor_output_with_regions.json"

REPORTS_FILE = "report_output_with_regions.json"

# --------------------------------------------------
# Custom CSS
# --------------------------------------------------

st.markdown(
    """
    <style>
    .main {
        background-color: #f7f9fc;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .dashboard-title {
        font-size: 2.7rem;
        font-weight: 800;
        color: #12355b;
        margin-bottom: 0.2rem;
    }

    .dashboard-subtitle {
        font-size: 1.05rem;
        color: #5f6c7b;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 8px 24px rgba(18, 53, 91, 0.08);
        border: 1px solid #e3ebf6;
        min-height: 112px;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #667085;
        font-weight: 600;
        margin-bottom: 0.4rem;
    }

    .metric-value {
        font-size: 2rem;
        color: #12355b;
        font-weight: 800;
        line-height: 1.1;
    }

    .section-card {
        background: white;
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 8px 24px rgba(18, 53, 91, 0.07);
        border: 1px solid #e8eef7;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.35rem;
        font-weight: 750;
        color: #12355b;
        margin-bottom: 1rem;
    }

    .small-muted {
        color: #667085;
        font-size: 0.92rem;
    }

    .pill {
        display: inline-block;
        padding: 0.28rem 0.65rem;
        margin: 0.15rem 0.15rem 0.15rem 0;
        border-radius: 999px;
        background: #eef5ff;
        color: #12355b;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #d7e8ff;
    }

    .mission-hero {
        padding: 1.35rem 1.55rem;
        border-radius: 22px;
        background: linear-gradient(135deg, #0b1f3a 0%, #143d66 45%, #2563eb 100%);
        color: white;
        margin-bottom: 1.2rem;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.22);
    }

    .mission-hero h2 {
        margin: 0;
        color: white;
        font-size: 1.65rem;
        letter-spacing: -0.03em;
    }

    .mission-hero p {
        margin-top: 0.35rem;
        color: #dbeafe;
        font-size: 0.98rem;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1f3a 0%, #143d66 100%);
    }

    div[data-testid="stSidebar"] h1,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3,
    div[data-testid="stSidebar"] p,
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] .stCaptionContainer {
        color: white !important;
    }

    .stMultiSelect label, .stSelectbox label {
        color: white !important;
        font-weight: 700;
    }

    div[data-testid="stSidebar"] .stMarkdown {
        color: white;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# Shared helper functions
# --------------------------------------------------

def metric_card(label, value):
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
    if not items:
        st.caption(empty_text)
        return

    html = "".join([f'<span class="pill">{item}</span>' for item in items])
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data
def load_json_file(file_path: str):
    path = Path(file_path)

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_json_payload(data):
    """
    Supports:
    - [mission, mission, ...]
    - {"reports": [mission, mission, ...]}
    - {single mission object}
    """
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "reports" in data:
        return data["reports"]

    if isinstance(data, dict):
        return [data]

    return []


# ==================================================
# TAB 1: TERMS OF REFERENCE / OBJECTIVES DASHBOARD
# ==================================================

@st.cache_data
def load_tor_json(file_path: str):
    data = load_json_file(file_path)

    if data is None:
        return None

    if isinstance(data, dict):
        if "reports" in data:
            data = data["reports"]
        else:
            data = [data]

    return data


@st.cache_data
def flatten_missions(data):
    rows = []

    for mission in data:
        objectives = mission.get("objectives", [])

        for obj in objectives:
            secondary_themes = obj.get("secondary_themes", [])

            rows.append({
                "Mission": mission.get("mission_title"),
                "Country": mission.get("mission_country_or_region"),
                "Regions": mission.get("regions", []),
                "Primary Region": (
                    mission.get("regions", [None])[0]
                    if mission.get("regions")
                    else None
                ),
                "Document Symbol": mission.get("document_symbol"),
                "Document Date": mission.get("document_date"),
                "Objective ID": obj.get("objective_id"),
                "Objective Type": obj.get("objective_type"),
                "Primary Theme": obj.get("primary_theme"),
                "Verb": obj.get("verb"),
                "Objective Text": obj.get("objective_text") or "No objective text provided",
                "Secondary Themes": ", ".join(secondary_themes) if secondary_themes else "None",
                "Secondary Theme List": secondary_themes
            })

    df = pd.DataFrame(rows)

    if not df.empty:
        df["Document Date Parsed"] = pd.to_datetime(
            df["Document Date"],
            errors="coerce"
        )
        df["Year"] = df["Document Date Parsed"].dt.year

    return df


@st.cache_data
def build_mission_level_df(df):
    mission_df = (
        df.groupby(
            [
                "Mission",
                "Country",
                "Primary Region",
                "Document Symbol",
                "Document Date",
                "Document Date Parsed",
                "Year"
            ],
            dropna=False
        )
        .agg(
            Objectives=("Objective ID", "count"),
            Themes=("Primary Theme", "nunique"),
            Objective_Types=("Objective Type", "nunique")
        )
        .reset_index()
    )

    mission_df = mission_df.rename(
        columns={
            "Objective_Types": "Objective Types"
        }
    )

    return mission_df


def normalize_country_name(country_name):
    replacements = {
        "the Niger": "Niger",
        "the Syrian Arab Republic": "Syrian Arab Republic",
        "Syrian Arab Republic": "Syria",
        "Democratic Republic of the Congo": "Democratic Republic of the Congo",
        "the Democratic Republic of the Congo": "Democratic Republic of the Congo"
    }

    country_name = country_name.strip()

    return replacements.get(country_name, country_name)


def split_country_region(country_region):
    if not isinstance(country_region, str):
        return []

    text = country_region

    text = text.replace("Lebanon and the Syrian Arab Republic", "Lebanon, Syrian Arab Republic")
    text = text.replace("Mali and the Niger", "Mali, Niger")
    text = text.replace("Mali and Niger", "Mali, Niger")

    parts = re.split(r",| and ", text)

    countries = []
    for part in parts:
        cleaned = normalize_country_name(part)
        if cleaned:
            countries.append(cleaned)

    return countries


def build_map_df(mission_df):
    country_coordinates = {
        "Lebanon": {"lat": 33.8547, "lon": 35.8623},
        "Syria": {"lat": 34.8021, "lon": 38.9968},
        "Syrian Arab Republic": {"lat": 34.8021, "lon": 38.9968},
        "Ethiopia": {"lat": 9.1450, "lon": 40.4897},
        "Colombia": {"lat": 4.5709, "lon": -74.2973},
        "Mali": {"lat": 17.5707, "lon": -3.9962},
        "Niger": {"lat": 17.6078, "lon": 8.0817},
        "South Sudan": {"lat": 6.8770, "lon": 31.3070},
        "Democratic Republic of the Congo": {"lat": -4.0383, "lon": 21.7587},
        "Somalia": {"lat": 5.1521, "lon": 46.1996},
        "Sudan": {"lat": 12.8628, "lon": 30.2176}
    }

    rows = []

    for _, row in mission_df.iterrows():
        countries = split_country_region(row["Country"])

        for country in countries:
            coords = country_coordinates.get(country)

            if coords:
                rows.append({
                    "Country": country,
                    "Mission": row["Mission"],
                    "Document Symbol": row["Document Symbol"],
                    "Year": row["Year"],
                    "Objectives": row["Objectives"],
                    "lat": coords["lat"],
                    "lon": coords["lon"]
                })

    return pd.DataFrame(rows)


def render_tor_dashboard():
    data = load_tor_json(TOR_FILE)

    if data is None:
        st.error(f"Could not find `{TOR_FILE}`. Please check the file path.")
        return

    df = flatten_missions(data)

    if df.empty:
        st.warning("The TOR JSON file was loaded, but no objectives were found.")
        return

    # --------------------------------------------------
    # Sidebar filters for Tab 1
    # --------------------------------------------------

    st.sidebar.title("Filters")
    st.sidebar.markdown("Use the filters below to explore Security Council field mission objectives.")

    country_options = sorted(df["Country"].dropna().unique())
    region_options = sorted(
        {
            region
            for regions in df["Regions"]
            for region in regions
        }
    )

    selected_countries = st.sidebar.multiselect(
        "Countries",
        options=country_options,
        default=[],
        placeholder="All countries",
        key="tor_country_filter"
    )

    selected_regions = st.sidebar.multiselect(
        "Region",
        options=region_options,
        default=[],
        key="tor_region_filter"
    )

    if selected_countries:
        country_filtered_df = df[df["Country"].isin(selected_countries)]
    else:
        country_filtered_df = df.copy()

    if selected_regions:
        country_filtered_df = country_filtered_df[
            country_filtered_df["Regions"].apply(
                lambda x: any(r in x for r in selected_regions)
            )
        ]

    dynamic_theme_options = sorted(
        country_filtered_df["Primary Theme"].dropna().unique()
    )

    selected_themes = st.sidebar.multiselect(
        "Primary Theme",
        options=dynamic_theme_options,
        default=[],
        placeholder="All primary themes",
        key="tor_theme_filter"
    )

    if selected_themes:
        filtered_df = country_filtered_df[
            country_filtered_df["Primary Theme"].isin(selected_themes)
        ]
    else:
        filtered_df = country_filtered_df.copy()

    st.sidebar.markdown("---")
    st.sidebar.caption("Tip: leave a filter empty to include all values.")

    # --------------------------------------------------
    # Header
    # --------------------------------------------------

    st.markdown(
        """
        <div class="dashboard-title">🌐 Security Council Missions Dashboard</div>
        <div class="dashboard-subtitle">
            Explore Security Council field mission objectives by country, region, theme, type, verb, and time.
        </div>
        """,
        unsafe_allow_html=True
    )

    mission_df = build_mission_level_df(filtered_df)

    # --------------------------------------------------
    # KPI cards
    # --------------------------------------------------

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        metric_card("Missions (with written ToRs)", filtered_df["Mission"].nunique())

    with kpi2:
        metric_card("Objectives", len(filtered_df))

    with kpi3:
        metric_card("Countries", filtered_df["Country"].nunique())

    with kpi4:
        metric_card("Primary Themes", filtered_df["Primary Theme"].nunique())

    st.markdown("<br>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Temporal chart and map
    # --------------------------------------------------

    time_col, map_col = st.columns([1, 1.25])

    with time_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Mission Objectives Over Time</div>', unsafe_allow_html=True)

        temporal_df = (
            mission_df
            .dropna(subset=["Year"])
            .groupby(["Year", "Primary Region"])
            .agg(
                Missions=("Mission", "nunique"),
                Objectives=("Objectives", "sum")
            )
            .reset_index()
        )

        REGION_COLORS = {
            "Africa": "#2563EB",
            "Asia": "#14B8A6",
            "Europe": "#8B5CF6",
            "Americas": "#F97316",
            "Middle East": "#DC2626"
        }

        fig_time = px.area(
            temporal_df,
            x="Year",
            y="Objectives",
            color="Primary Region",
            color_discrete_map=REGION_COLORS,
            hover_data={
                "Year": True,
                "Primary Region": True,
                "Objectives": True,
                "Missions": True
            }
        )

        fig_time.update_traces(
            opacity=0.45
        )

        fig_time.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis_title=None,
            yaxis_title="Number of Objectives",
            hovermode="x unified"
        )

        st.plotly_chart(fig_time, width='content')

        st.markdown("</div>", unsafe_allow_html=True)

    with map_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Mission Countries Map</div>', unsafe_allow_html=True)

        map_df = build_map_df(mission_df)

        if map_df.empty:
            st.info(
                "No map coordinates found for the selected countries/regions. "
                "Add the relevant country names to the `country_coordinates` dictionary."
            )
        else:
            map_counts = (
                map_df
                .groupby(["Country", "lat", "lon"])
                .agg(
                    Missions=("Mission", "nunique"),
                    Objectives=("Objectives", "sum"),
                    Years=("Year", lambda x: ", ".join(map(str, sorted(x.dropna().astype(int).unique()))))
                )
                .reset_index()
            )

            fig_map = px.scatter_geo(
                map_counts,
                lat="lat",
                lon="lon",
                size="Missions",
                color="Objectives",
                hover_name="Country",
                hover_data={
                    "Missions": True,
                    "Objectives": True,
                    "Years": True,
                    "lat": False,
                    "lon": False
                },
                color_continuous_scale="Blues",
                projection="natural earth"
            )

            fig_map.update_traces(
                marker=dict(
                    line=dict(width=1, color="white"),
                    sizemin=8
                )
            )

            fig_map.update_layout(
                height=430,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    coastlinecolor="#b0b8c4",
                    showland=True,
                    landcolor="#f1f5f9",
                    showocean=True,
                    oceancolor="#e8f1fb",
                    showcountries=True,
                    countrycolor="#cbd5e1"
                )
            )

            st.plotly_chart(fig_map, width='content')

        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Charts: theme and objective type
    # --------------------------------------------------

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Objectives by Primary Theme</div>', unsafe_allow_html=True)

        theme_counts = (
            filtered_df["Primary Theme"]
            .value_counts()
            .reset_index()
        )
        theme_counts.columns = ["Primary Theme", "Objectives"]

        fig_theme = px.bar(
            theme_counts,
            x="Objectives",
            y="Primary Theme",
            orientation="h",
            color="Objectives",
            color_continuous_scale="Blues",
            text="Objectives"
        )

        fig_theme.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            yaxis_title=None,
            xaxis_title="Number of Objectives",
            coloraxis_showscale=False
        )

        fig_theme.update_traces(
            textposition="outside",
            marker_line_width=0
        )

        st.plotly_chart(fig_theme, width='content')
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Objective Type Distribution</div>', unsafe_allow_html=True)

        type_counts = (
            filtered_df["Objective Type"]
            .value_counts()
            .reset_index()
        )
        type_counts.columns = ["Objective Type", "Objectives"]

        fig_type = px.pie(
            type_counts,
            names="Objective Type",
            values="Objectives",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set3
        )

        fig_type.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02
            )
        )

        st.plotly_chart(fig_type, width='content')
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Verb visual
    # --------------------------------------------------

    verb_col1, verb_col2 = st.columns([1.15, 1])

    with verb_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Most Frequent Verbs</div>', unsafe_allow_html=True)

        verb_counts = (
            filtered_df["Verb"]
            .fillna("Unknown")
            .str.strip()
            .str.lower()
            .value_counts()
            .reset_index()
        )
        verb_counts.columns = ["Verb", "Objectives"]

        fig_verbs = px.bar(
            verb_counts,
            x="Objectives",
            y="Verb",
            orientation="h",
            color="Objectives",
            text="Objectives",
            color_continuous_scale="Teal"
        )

        fig_verbs.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            yaxis_title=None,
            xaxis_title="Number of Objectives",
            coloraxis_showscale=False
        )

        fig_verbs.update_traces(
            textposition="outside",
            marker_line_width=0
        )

        st.plotly_chart(fig_verbs, width='content')

        st.markdown("</div>", unsafe_allow_html=True)

    with verb_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Verb Mix by Objective Type</div>', unsafe_allow_html=True)

        verb_type_df = (
            filtered_df
            .assign(Verb=filtered_df["Verb"].fillna("Unknown").str.strip().str.lower())
            .groupby(["Objective Type", "Verb"])
            .size()
            .reset_index(name="Objectives")
        )

        fig_verb_type = px.treemap(
            verb_type_df,
            path=["Objective Type", "Verb"],
            values="Objectives",
            color="Objectives",
            color_continuous_scale="Blues"
        )

        fig_verb_type.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white"
        )

        st.plotly_chart(fig_verb_type, width='content')

        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Mission-level summary
    # --------------------------------------------------

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Mission Summary</div>', unsafe_allow_html=True)

    mission_summary = (
        mission_df
        .sort_values(["Year", "Mission"], ascending=[False, True], na_position="last")
        [
            [
                "Mission",
                "Country",
                "Document Symbol",
                "Document Date",
                "Objectives",
                "Themes",
                "Objective Types"
            ]
        ]
    )

    st.dataframe(
        mission_summary,
        width='content',
        hide_index=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Theme by mission heatmap
    # --------------------------------------------------

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Theme Intensity by Mission</div>', unsafe_allow_html=True)

    heatmap_df = (
        filtered_df
        .groupby(["Mission", "Primary Theme"])
        .size()
        .reset_index(name="Objectives")
    )

    fig_heatmap = px.density_heatmap(
        heatmap_df,
        x="Primary Theme",
        y="Mission",
        z="Objectives",
        color_continuous_scale="Blues",
        text_auto=True
    )

    fig_heatmap.update_layout(
        height=450,
        margin=dict(l=10, r=10, t=10, b=80),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title=None
    )

    st.plotly_chart(fig_heatmap, width='content')

    st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Detailed objectives table
    # --------------------------------------------------

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Detailed Objectives</div>', unsafe_allow_html=True)

    search_term = st.text_input(
        "Search objective text",
        placeholder="Type a keyword, theme, country, verb, or phrase...",
        key="tor_search"
    )

    table_df = filtered_df.copy()

    if search_term:
        search_lower = search_term.lower()
        table_df = table_df[
            table_df.apply(
                lambda row: search_lower in " ".join(
                    row.astype(str).str.lower()
                ),
                axis=1
            )
        ]

    display_columns = [
        "Mission",
        "Country",
        "Document Symbol",
        "Document Date",
        "Objective ID",
        "Primary Theme",
        "Objective Type",
        "Verb",
        "Secondary Themes",
        "Objective Text"
    ]

    st.dataframe(
        table_df[display_columns],
        width='content',
        hide_index=True,
        height=520
    )

    csv = table_df[display_columns].to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇️ Download filtered objectives as CSV",
        data=csv,
        file_name="filtered_security_council_objectives.csv",
        mime="text/csv"
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ==================================================
# TAB 2: MISSION REPORTS ANALYTICAL DASHBOARD
# ==================================================

THEME_COLORS = {
    "Peace Agreement Implementation": "#2563EB",
    "Ceasefire / Cessation of Hostilities": "#0891B2",
    "Security / Stability": "#DC2626",
    "Sovereignty / Territorial Integrity": "#7C3AED",
    "UN Mission Mandate": "#475569",
    "State Authority / Armed Groups / Weapons": "#EA580C",
    "Border / Regional Issues": "#9333EA",
    "Political Process": "#16A34A",
    "Human Rights": "#DB2777",
    "Humanitarian Issues": "#F59E0B",
    "Rule of Law / Justice": "#0F766E",
    "DDR / Reintegration": "#64748B",
    "Women, Peace and Security": "#C026D3",
    "Youth, Peace and Security": "#65A30D",
    "Regional Cooperation": "#0284C7",
    "Other": "#94A3B8",
}

CONCERN_ORDER = [
    "None",
    "Low",
    "Moderate",
    "High",
    "Critical",
    "Not Applicable",
]

CONCERN_COLORS = {
    "None": "#94A3B8",
    "Low": "#22C55E",
    "Moderate": "#EAB308",
    "High": "#F97316",
    "Critical": "#EF4444",
    "Not Applicable": "#CBD5E1",
}

ACTION_COLORS = {
    "Observation": "#64748B",
    "Assessment": "#2563EB",
    "Warning": "#DC2626",
    "Recommendation": "#16A34A",
    "Request": "#9333EA",
    "Commitment": "#0891B2",
    "Follow-up Action": "#F59E0B",
    "Political Signalling": "#DB2777",
    "Not Applicable": "#CBD5E1",
}

REGION_COLORS = {
    "Africa": "#2563EB",
    "Asia": "#14B8A6",
    "Europe": "#8B5CF6",
    "Americas": "#F97316",
    "Middle East": "#DC2626",
}

@st.cache_data
def load_report_json(file_path: str):
    data = load_json_file(file_path)

    if data is None:
        return None

    return normalize_json_payload(data)


@st.cache_data
def flatten_reports(reports):
    mission_rows = []
    record_rows = []
    activity_rows = []
    actor_rows = []

    for mission_idx, report in enumerate(reports, start=1):
        mission_id = report.get("document_symbol") or f"mission_{mission_idx}"
        analytics = report.get("mission_analytics", {}) or {}

        mission_rows.append(
            {
                "mission_id": mission_id,
                "mission_title": report.get("mission_title"),
                "document_symbol": report.get("document_symbol"),
                "document_date": report.get("document_date"),
                "mission_country_or_region": report.get("mission_country_or_region"),
                "related_tor_document_symbol": report.get("related_tor_document_symbol"),
                "regions": ", ".join(report.get("regions", [])),
                "mission_type": analytics.get("mission_type"),
                "mission_subtype": analytics.get("mission_subtype"),
                "field_exposure": analytics.get("field_exposure"),
                "actor_diversity_assessment": analytics.get("actor_diversity_assessment"),
                "overall_character": analytics.get("overall_character"),
                "main_themes": analytics.get("main_themes", []),
                "main_risks": analytics.get("main_risks", []),
                "main_commitments": analytics.get("main_commitments", []),
                "main_policy_signals": analytics.get("main_policy_signals", []),
                "summary_assessment": analytics.get("summary_assessment"),
                "records_count": len(report.get("records", []) or []),
                "activities_count": len(report.get("activities", []) or []),
                "actors_count": len(report.get("actors_met", []) or []),
            }
        )

        for rec in report.get("records", []) or []:
            record_rows.append(
                {
                    "mission_id": mission_id,
                    "mission_title": report.get("mission_title"),
                    "document_symbol": report.get("document_symbol"),
                    "document_date": report.get("document_date"),
                    "mission_country_or_region": report.get("mission_country_or_region"),
                    "record_id": rec.get("record_id"),
                    "record_text": rec.get("record_text"),
                    "verb": rec.get("verb"),
                    "report_record_type": rec.get("report_record_type"),
                    "primary_theme": rec.get("primary_theme"),
                    "secondary_themes": rec.get("secondary_themes", []),
                    "geographic_scope": rec.get("geographic_scope"),
                    "actor_source": rec.get("actor_source"),
                    "actor_target": rec.get("actor_target"),
                    "level_of_concern": rec.get("level_of_concern"),
                    "degree_of_consensus": rec.get("degree_of_consensus"),
                    "action_orientation": rec.get("action_orientation"),
                    "political_signal": rec.get("political_signal"),
                    "policy_implication": rec.get("policy_implication"),
                }
            )

        for act in report.get("activities", []) or []:
            activity_rows.append(
                {
                    "mission_id": mission_id,
                    "mission_title": report.get("mission_title"),
                    "document_symbol": report.get("document_symbol"),
                    "activity_id": act.get("activity_id"),
                    "activity_type": act.get("activity_type"),
                    "activity_description": act.get("activity_description"),
                }
            )

        for actor in report.get("actors_met", []) or []:
            actor_rows.append(
                {
                    "mission_id": mission_id,
                    "mission_title": report.get("mission_title"),
                    "document_symbol": report.get("document_symbol"),
                    "actor_id": actor.get("actor_id"),
                    "actor_name": actor.get("actor_name"),
                    "actor_category": actor.get("actor_category"),
                }
            )

    missions_df = pd.DataFrame(mission_rows)
    records_df = pd.DataFrame(record_rows)
    activities_df = pd.DataFrame(activity_rows)
    actors_df = pd.DataFrame(actor_rows)

    if not missions_df.empty:
        missions_df["document_date"] = pd.to_datetime(
            missions_df["document_date"], errors="coerce"
        )
        missions_df["year"] = missions_df["document_date"].dt.year

    if not records_df.empty:
        records_df["document_date"] = pd.to_datetime(
            records_df["document_date"], errors="coerce"
        )
        records_df["year"] = records_df["document_date"].dt.year

    return missions_df, records_df, activities_df, actors_df


def make_report_theme_bar(records_df):
    theme_counts = (
        records_df["primary_theme"]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )
    theme_counts.columns = ["primary_theme", "count"]

    fig = px.bar(
        theme_counts.sort_values("count"),
        x="count",
        y="primary_theme",
        orientation="h",
        color="primary_theme",
        color_discrete_map=THEME_COLORS,
        text="count",
        title="Substantive Records by Primary Theme",
    )

    fig.update_layout(
        height=520,
        showlegend=False,
        margin=dict(l=10, r=20, t=60, b=20),
        xaxis_title="Records",
        yaxis_title=None,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def make_record_type_donut(records_df):
    df = (
        records_df["report_record_type"]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )
    df.columns = ["report_record_type", "count"]

    fig = px.pie(
        df,
        names="report_record_type",
        values="count",
        hole=0.56,
        title="Record-Type Mix",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="white",
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
    )

    fig.update_traces(textinfo="percent+label")
    return fig

def make_mission_metadata_chart(
    missions_df,
    column,
    title
):

    df = (
        missions_df
        .groupby([column, "regions"], dropna=False)
        .size()
        .reset_index(name='count')
    )

    fig = px.bar(
        df.sort_values("count"),
        x="count",
        y=column,
        orientation="h",
        color_discrete_map=REGION_COLORS,
        color="regions",
        text="count",
        title=title
    )

    fig.update_layout(
        height=350,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis_title="Missions",
        yaxis_title=None,
        showlegend=False,
        coloraxis_showscale=False
    )

    fig.update_traces(
        textposition="outside"
    )

    return fig

def make_concern_chart(records_df):
    df = (
        records_df["level_of_concern"]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )
    df.columns = ["level_of_concern", "count"]

    order = [x for x in CONCERN_ORDER if x in df["level_of_concern"].tolist()]
    extra = [x for x in df["level_of_concern"].tolist() if x not in order]
    order = order + extra

    df["level_of_concern"] = pd.Categorical(
        df["level_of_concern"], categories=order, ordered=True
    )
    df = df.sort_values("level_of_concern")

    fig = px.bar(
        df,
        x="level_of_concern",
        y="count",
        color="level_of_concern",
        color_discrete_map=CONCERN_COLORS,
        text="count",
        title="Level of Concern",
    )

    fig.update_layout(
        height=380,
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_title=None,
        yaxis_title="Records",
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    fig.update_traces(textposition="outside")
    return fig

def make_regional_engagement_df(missions_df):

    return (
        missions_df
        .groupby("regions", dropna=False)
        .agg(
            Missions=("document_symbol", "nunique"),
            Actors=("actors_count", "sum"),
            Activities=("activities_count", "sum"),
            Records=("records_count", "sum")
        )
        .reset_index()
    )

def make_region_actors_bubble(missions_df):

    df = make_regional_engagement_df(missions_df)

    fig = px.scatter(
        df,
        x="regions",
        y="Actors",
        size="Actors",
        color="Actors",
        text="Actors",
        hover_data={
            "Missions": True,
            "Activities": True,
            "Records": True
        },
        color_continuous_scale="Purples",
        title="Actors Met by Region",
        size_max=80
    )

    fig.update_traces(textposition="top center")

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Actors Met",
        coloraxis_showscale=False
    )

    return fig

def make_region_activities_bubble(missions_df):

    df = make_regional_engagement_df(missions_df)

    fig = px.scatter(
        df,
        x="regions",
        y="Activities",
        size="Activities",
        color="Activities",
        text="Activities",
        hover_data={
            "Missions": True,
            "Actors": True,
            "Records": True
        },
        color_continuous_scale="Greens",
        title="Activities by Region",
        size_max=80
    )

    fig.update_traces(textposition="top center")

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Activities Conducted",
        coloraxis_showscale=False
    )

    return fig

def make_action_treemap(records_df):
    df = (
        records_df.groupby(["action_orientation", "report_record_type"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    df["action_orientation"] = df["action_orientation"].fillna("Unknown")
    df["report_record_type"] = df["report_record_type"].fillna("Unknown")

    fig = px.treemap(
        df,
        path=["action_orientation", "report_record_type"],
        values="count",
        color="action_orientation",
        color_discrete_map=ACTION_COLORS,
        title="Action Orientation by Record Type",
    )

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="white",
    )

    return fig


def make_report_timeline(missions_df):
    df = missions_df.dropna(subset=["document_date"]).copy()

    if df.empty:
        return None

    df = df.sort_values("document_date")
    df["records_count"] = pd.to_numeric(df["records_count"], errors="coerce").fillna(0)

    fig = px.scatter(
        df,
        x="document_date",
        y="document_symbol",
        size="records_count",
        color="overall_character",
        hover_name="mission_title",
        hover_data={
            "document_symbol": True,
            "mission_type": True,
            "records_count": True,
            "document_date": "|%Y-%m-%d",
        },
        title="Mission Report Timeline",
        size_max=36,
    )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    return fig


def make_theme_heatmap(records_df):
    if records_df.empty:
        return None

    df = (
        records_df.groupby(["document_symbol", "primary_theme"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    pivot = df.pivot_table(
        index="document_symbol",
        columns="primary_theme",
        values="count",
        fill_value=0,
        aggfunc="sum",
    )

    fig = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        title="Theme Concentration by Mission Report",
    )

    fig.update_layout(
        height=max(380, 70 + 42 * len(pivot.index)),
        margin=dict(l=20, r=20, t=60, b=80),
        paper_bgcolor="white",
        xaxis_title=None,
        yaxis_title=None,
    )

    return fig

def make_actors_met_chart(missions_df):

    df = (
        missions_df[
            ["document_symbol", "actors_count"]
        ]
        .sort_values("actors_count", ascending=True)
    )

    fig = px.bar(
        df,
        x="actors_count",
        y="document_symbol",
        orientation="h",
        color="actors_count",
        text="actors_count",
        color_continuous_scale="Purples",
        title="Actors Met by Mission"
    )

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_title="Actors Met",
        yaxis_title=None,
        coloraxis_showscale=False
    )

    fig.update_traces(
        textposition="outside"
    )

    return fig

def make_activities_count_chart(missions_df):

    df = (
        missions_df[
            ["document_symbol", "activities_count"]
        ]
        .sort_values("activities_count", ascending=True)
    )

    fig = px.bar(
        df,
        x="activities_count",
        y="document_symbol",
        orientation="h",
        color="activities_count",
        text="activities_count",
        color_continuous_scale="Greens",
        title="Activities Conducted by Mission"
    )

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_title="Activities",
        yaxis_title=None,
        coloraxis_showscale=False
    )

    fig.update_traces(
        textposition="outside"
    )

    return fig

def make_actor_chart(actors_df):
    df = (
        actors_df["actor_category"]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )
    df.columns = ["actor_category", "count"]

    fig = px.bar(
        df.sort_values("count"),
        x="count",
        y="actor_category",
        orientation="h",
        color="actor_category",
        text="count",
        title="Actors Engaged by Category",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_layout(
        height=420,
        showlegend=False,
        margin=dict(l=10, r=20, t=60, b=20),
        xaxis_title="Actors",
        yaxis_title=None,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig

ACTOR_CATEGORY_COLORS = {
    "Government": "#F97316",
    "UN Secretariat / Special Envoy": "#2563EB",
    "UN Country Team": "#0891B2",
    "UN Mission": "#7C3AED",
    "Civil Society": "#16A34A",
    "Affected Community": "#DB2777",
    "Other": "#64748B",
    "Regional Organization": "#9333EA",
    "Armed Group": "#111827",
    "Donor / International Partner": "#EAB308",
    "Private Sector": "#0F766E",
    "Media": "#EC4899",
    "Religious / Community Leader": "#84CC16",
    "Opposition / Political Actor": "#DC2626",
}

def make_pyvis_actor_network_html(
    missions_df,
    actors_df,
    selected_symbols,
    max_actors_per_category=5
):
    """
    PyVis interactive network:

    Selected missions -> Actor categories -> Actual actors

    Features:
    - draggable nodes
    - full-screen width in Streamlit
    - category-specific colors
    - capped actors per category
    - full actor names available on hover
    """

    if missions_df.empty or actors_df.empty or not selected_symbols:
        return None

    selected_symbols = selected_symbols[:5]

    mission_df = missions_df.copy()
    actor_df = actors_df.copy()

    mission_df["document_symbol"] = mission_df["document_symbol"].fillna("Unknown mission")
    mission_df["mission_title"] = mission_df["mission_title"].fillna(mission_df["document_symbol"])

    actor_df["document_symbol"] = actor_df["document_symbol"].fillna("Unknown mission")
    actor_df["mission_title"] = actor_df["mission_title"].fillna(actor_df["document_symbol"])
    actor_df["actor_category"] = actor_df["actor_category"].fillna("Unknown")
    actor_df["actor_name"] = actor_df["actor_name"].fillna("Unnamed actor")

    actor_df = actor_df[actor_df["document_symbol"].isin(selected_symbols)].copy()
    mission_df = mission_df[mission_df["document_symbol"].isin(selected_symbols)].copy()

    if actor_df.empty:
        return None

    def short_label(value, max_chars=34):
        value = str(value)
        if len(value) <= max_chars:
            return value
        return value[:max_chars - 1] + "…"

    mission_lookup = (
        mission_df
        .drop_duplicates(subset=["document_symbol"])
        .set_index("document_symbol")
        .to_dict(orient="index")
    )

    mission_order = [
        symbol for symbol in selected_symbols
        if symbol in actor_df["document_symbol"].unique()
    ]

    category_counts = (
        actor_df
        .groupby("actor_category")
        .size()
        .sort_values(ascending=False)
    )

    category_order = category_counts.index.tolist()

    # Limit actors per category across selected missions
    limited_actor_rows = []

    for category in category_order:
        sub = actor_df[actor_df["actor_category"] == category].copy()

        actor_summary = (
            sub
            .groupby(["actor_category", "actor_name"])
            .agg(
                count=("actor_name", "count"),
                missions=("document_symbol", lambda x: ", ".join(sorted(x.dropna().astype(str).unique())))
            )
            .reset_index()
            .sort_values(["count", "actor_name"], ascending=[False, True])
            .head(max_actors_per_category)
        )

        limited_actor_rows.extend(actor_summary.to_dict(orient="records"))

    limited_actor_df = pd.DataFrame(limited_actor_rows)

    if limited_actor_df.empty:
        return None

    mission_category_df = (
        actor_df
        .groupby(["document_symbol", "actor_category"])
        .size()
        .reset_index(name="count")
    )

    # --------------------------------------------------
    # Create PyVis network
    # --------------------------------------------------

    net = Network(
        height="760px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#000000",
        directed=False,
        cdn_resources="in_line"
    )

    # Turn off physics by default so the layout stays clean.
    # Users can still drag nodes.
    net.set_options(
        """
        {
          "physics": {
            "enabled": false
          },
          "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true,
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          },
          "nodes": {
            "font": {
              "color": "#000000",
              "size": 16,
              "face": "Arial",
              "strokeWidth": 3,
              "strokeColor": "#ffffff"
            },
            "borderWidth": 2,
            "shadow": {
              "enabled": true,
              "color": "rgba(15, 23, 42, 0.18)",
              "size": 8,
              "x": 2,
              "y": 2
            }
          },
          "edges": {
            "smooth": {
              "enabled": true,
              "type": "continuous",
              "roundness": 0.35
            },
            "color": {
              "inherit": false
            },
            "selectionWidth": 2
          }
        }
        """
    )

    # --------------------------------------------------
    # Fixed initial positions: missions left, categories center, actors right
    # Nodes remain draggable.
    # --------------------------------------------------

    def spread(items, top=260, bottom=-260):
        if not items:
            return {}

        if len(items) == 1:
            return {items[0]: 0}

        step = (top - bottom) / (len(items) - 1)

        return {
            item: top - i * step
            for i, item in enumerate(items)
        }

    mission_y = spread(mission_order, top=220, bottom=-220)
    category_y = spread(category_order, top=260, bottom=-260)

    # --------------------------------------------------
    # Mission nodes
    # --------------------------------------------------

    for mission in mission_order:
        meta = mission_lookup.get(mission, {})
        actor_count = actor_df[actor_df["document_symbol"] == mission].shape[0]

        title = (
            f"<b>{html.escape(mission)}</b><br>"
            f"{html.escape(str(meta.get('mission_title', '')))}<br><br>"
            f"<b>Country/Region:</b> {html.escape(str(meta.get('mission_country_or_region', 'N/A')))}<br>"
            f"<b>Mission type:</b> {html.escape(str(meta.get('mission_type', 'N/A')))}<br>"
            f"<b>Actors met:</b> {actor_count}"
        )

        net.add_node(
            f"MISSION::{mission}",
            label=mission,
            title=title,
            x=-520,
            y=mission_y.get(mission, 0),
            size=18,
            color={
                "background": "#2563EB",
                "border": "#1D4ED8",
                "highlight": {
                    "background": "#1D4ED8",
                    "border": "#1E40AF"
                }
            },
            shape="dot",
            font={
                "color": "#000000",
                "size": 17,
                "face": "Arial",
                "strokeWidth": 4,
                "strokeColor": "#ffffff"
            }
        )

    # --------------------------------------------------
    # Category nodes
    # --------------------------------------------------

    for category in category_order:
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")
        count = int(category_counts[category])

        title = (
            f"<b>{html.escape(category)}</b><br>"
            f"<b>Actors across selected missions:</b> {count}"
        )

        net.add_node(
            f"CATEGORY::{category}",
            label=short_label(category, 28),
            title=title,
            x=0,
            y=category_y.get(category, 0),
            size=16,
            color={
                "background": color,
                "border": color,
                "highlight": {
                    "background": color,
                    "border": "#111827"
                }
            },
            shape="diamond",
            font={
                "color": "#000000",
                "size": 15,
                "face": "Arial",
                "strokeWidth": 4,
                "strokeColor": "#ffffff"
            }
        )

    # --------------------------------------------------
    # Actor nodes
    # --------------------------------------------------

    actor_positions = {}

    for category in category_order:
        sub = limited_actor_df[limited_actor_df["actor_category"] == category]
        actors = sub["actor_name"].drop_duplicates().tolist()

        center_y = category_y.get(category, 0)

        if len(actors) == 1:
            offsets = [0]
        else:
            local_step = min(52, 260 / max(len(actors) - 1, 1))
            offsets = [
                ((len(actors) - 1) / 2 - i) * local_step
                for i in range(len(actors))
            ]

        for actor_name, offset in zip(actors, offsets):
            actor_positions[(category, actor_name)] = {
                "x": 520,
                "y": center_y + offset
            }

    for _, row in limited_actor_df.iterrows():
        category = row["actor_category"]
        actor_name = row["actor_name"]
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        coords = actor_positions.get((category, actor_name), {"x": 520, "y": 0})

        title = (
            f"<b>{html.escape(str(actor_name))}</b><br>"
            f"<b>Category:</b> {html.escape(str(category))}<br>"
            f"<b>Missions:</b> {html.escape(str(row.get('missions', '')))}"
        )

        net.add_node(
            f"ACTOR::{category}::{actor_name}",
            label=short_label(actor_name, 42),
            title=title,
            x=coords["x"],
            y=coords["y"],
            size=8,
            color={
                "background": color,
                "border": color,
                "highlight": {
                    "background": color,
                    "border": "#111827"
                }
            },
            shape="dot",
            font={
                "color": "#000000",
                "size": 13,
                "face": "Arial",
                "strokeWidth": 4,
                "strokeColor": "#ffffff"
            }
        )

    # --------------------------------------------------
    # Mission -> Category edges
    # --------------------------------------------------

    for _, row in mission_category_df.iterrows():
        mission = row["document_symbol"]
        category = row["actor_category"]
        count = int(row["count"])

        if mission not in mission_order or category not in category_order:
            continue

        net.add_edge(
            f"MISSION::{mission}",
            f"CATEGORY::{category}",
            value=max(1, min(count, 8)),
            width=max(1, min(count * 0.45, 4)),
            color="rgba(100, 116, 139, 0.35)",
            title=(
                f"<b>{html.escape(str(mission))}</b> → "
                f"<b>{html.escape(str(category))}</b><br>"
                f"Actors in category: {count}"
            )
        )

    # --------------------------------------------------
    # Category -> Actor edges
    # --------------------------------------------------

    for _, row in limited_actor_df.iterrows():
        category = row["actor_category"]
        actor_name = row["actor_name"]
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        net.add_edge(
            f"CATEGORY::{category}",
            f"ACTOR::{category}::{actor_name}",
            width=1.2,
            color=color,
            title=(
                f"<b>{html.escape(str(category))}</b> → "
                f"<b>{html.escape(str(actor_name))}</b><br>"
                f"Missions: {html.escape(str(row.get('missions', '')))}"
            )
        )

    return net.generate_html()

def make_activity_chart(activities_df):
    df = (
        activities_df["activity_type"]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )
    df.columns = ["activity_type", "count"]

    fig = px.funnel(
        df,
        x="count",
        y="activity_type",
        title="Mission Activities Undertaken",
        color="activity_type",
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )

    fig.update_layout(
        height=420,
        showlegend=False,
        margin=dict(l=10, r=20, t=60, b=20),
        paper_bgcolor="white",
    )

    return fig

def make_multi_mission_actor_network(
    missions_df,
    actors_df,
    selected_symbols,
    max_actors_per_category=6
):
    """
    Compact readable network:

    Selected missions -> actor categories -> actors met

    - Supports up to 5 selected missions.
    - Actor categories have distinct colors.
    - Actors are aggregated across selected missions.
    - Actor nodes show the missions in which they appeared on hover.
    """

    if missions_df.empty or actors_df.empty or not selected_symbols:
        return None

    selected_symbols = selected_symbols[:5]

    mission_df = missions_df.copy()
    actor_df = actors_df.copy()

    mission_df["document_symbol"] = mission_df["document_symbol"].fillna("Unknown mission")
    mission_df["mission_title"] = mission_df["mission_title"].fillna(mission_df["document_symbol"])

    actor_df["document_symbol"] = actor_df["document_symbol"].fillna("Unknown mission")
    actor_df["mission_title"] = actor_df["mission_title"].fillna(actor_df["document_symbol"])
    actor_df["actor_category"] = actor_df["actor_category"].fillna("Unknown")
    actor_df["actor_name"] = actor_df["actor_name"].fillna("Unnamed actor")

    actor_df = actor_df[actor_df["document_symbol"].isin(selected_symbols)].copy()
    mission_df = mission_df[mission_df["document_symbol"].isin(selected_symbols)].copy()

    if actor_df.empty:
        return None

    # Mission order follows user selection
    mission_order = [
        symbol for symbol in selected_symbols
        if symbol in actor_df["document_symbol"].unique()
    ]

    # Category counts across selected missions
    category_counts = (
        actor_df
        .groupby("actor_category")
        .size()
        .sort_values(ascending=False)
    )

    category_order = category_counts.index.tolist()

    # Limit actors per category across selected missions
    limited_actor_rows = []

    for category in category_order:
        sub = actor_df[actor_df["actor_category"] == category].copy()

        actor_summary = (
            sub
            .groupby(["actor_category", "actor_name"])
            .agg(
                count=("actor_name", "count"),
                missions=("document_symbol", lambda x: ", ".join(sorted(x.dropna().astype(str).unique())))
            )
            .reset_index()
            .sort_values(["count", "actor_name"], ascending=[False, True])
            .head(max_actors_per_category)
        )

        limited_actor_rows.extend(actor_summary.to_dict(orient="records"))

    limited_actor_df = pd.DataFrame(limited_actor_rows)

    if limited_actor_df.empty:
        return None

    # Mission -> category edges
    mission_category_df = (
        actor_df
        .groupby(["document_symbol", "actor_category"])
        .size()
        .reset_index(name="count")
    )

    # Category -> actor edges
    category_actor_df = limited_actor_df.copy()

    # Mission metadata lookup
    mission_lookup = (
        mission_df
        .drop_duplicates(subset=["document_symbol"])
        .set_index("document_symbol")
        .to_dict(orient="index")
    )

    # -----------------------------
    # Fixed compact three-column layout
    # -----------------------------
    pos = {}

    def spread(items, top=0.85, bottom=-0.85):
        if not items:
            return {}

        if len(items) == 1:
            return {items[0]: 0}

        step = (top - bottom) / (len(items) - 1)

        return {
            item: top - i * step
            for i, item in enumerate(items)
        }

    mission_y = spread(mission_order)
    category_y = spread(category_order)

    for mission in mission_order:
        pos[f"MISSION::{mission}"] = (-1.05, mission_y[mission])

    for category in category_order:
        pos[f"CATEGORY::{category}"] = (0, category_y[category])

    actor_positions = {}

    for category in category_order:
        actors = (
            category_actor_df[category_actor_df["actor_category"] == category]["actor_name"]
            .drop_duplicates()
            .tolist()
        )

        center_y = category_y[category]

        if len(actors) == 1:
            offsets = [0]
        else:
            local_step = min(0.12, 0.48 / max(len(actors) - 1, 1))
            offsets = [
                ((len(actors) - 1) / 2 - i) * local_step
                for i in range(len(actors))
            ]

        for actor_name, offset in zip(actors, offsets):
            actor_node = f"ACTOR::{category}::{actor_name}"
            pos[actor_node] = (1.05, center_y + offset)
            actor_positions[(category, actor_name)] = actor_node

    # -----------------------------
    # Edges
    # -----------------------------
    edge_traces = []

    # Mission -> category edges
    for _, row in mission_category_df.iterrows():
        mission = row["document_symbol"]
        category = row["actor_category"]

        mission_node = f"MISSION::{mission}"
        category_node = f"CATEGORY::{category}"

        if mission_node not in pos or category_node not in pos:
            continue

        x0, y0 = pos[mission_node]
        x1, y1 = pos[category_node]

        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line=dict(
                    width=max(1.2, min(row["count"] * 0.55, 6)),
                    color="rgba(100,116,139,0.25)"
                ),
                hoverinfo="text",
                hovertext=(
                    f"<b>{mission}</b> → <b>{category}</b><br>"
                    f"Actors in category: {row['count']}"
                ),
                showlegend=False
            )
        )

    # Category -> actor edges
    for _, row in category_actor_df.iterrows():
        category = row["actor_category"]
        actor_name = row["actor_name"]

        category_node = f"CATEGORY::{category}"
        actor_node = actor_positions.get((category, actor_name))

        if category_node not in pos or actor_node not in pos:
            continue

        x0, y0 = pos[category_node]
        x1, y1 = pos[actor_node]

        category_color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line=dict(
                    width=1.5,
                    color=category_color
                ),
                opacity=0.32,
                hoverinfo="text",
                hovertext=(
                    f"<b>{category}</b> → <b>{actor_name}</b><br>"
                    f"Missions: {row['missions']}"
                ),
                showlegend=False
            )
        )

    # -----------------------------
    # Mission nodes
    # -----------------------------
    mission_x = []
    mission_y_vals = []
    mission_labels = []
    mission_hover = []
    mission_sizes = []

    def short_label(text, max_chars=34):
        text = str(text)
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 1] + "…"

    for mission in mission_order:
        node = f"MISSION::{mission}"

        if node not in pos:
            continue

        x, y = pos[node]
        meta = mission_lookup.get(mission, {})
        actor_count = actor_df[actor_df["document_symbol"] == mission].shape[0]

        mission_x.append(x)
        mission_y_vals.append(y)
        mission_labels.append(mission)
        mission_sizes.append(34 + min(actor_count * 0.6, 18))

        mission_hover.append(
            f"<b>{mission}</b><br>"
            f"{meta.get('mission_title', '')}<br><br>"
            f"Country/Region: {meta.get('mission_country_or_region', 'N/A')}<br>"
            f"Mission type: {meta.get('mission_type', 'N/A')}<br>"
            f"Actors met: {actor_count}"
        )

    mission_trace = go.Scatter(
        x=mission_x,
        y=mission_y_vals,
        mode="markers+text",
        text=mission_labels,
        textposition="middle left",
        textfont=dict(color = "black", size = 11, family = "Arial"),
        hoverinfo="text",
        hovertext=mission_hover,
        name="Mission reports",
        marker=dict(
            size=[24 + min(size * 0.15, 8) for size in mission_sizes],
            color="#2563EB",
            line=dict(width=1.5, color="white"),
            opacity=0.95
        )
    )

    # -----------------------------
    # Category nodes
    # -----------------------------
    category_traces = []

    for category in category_order:
        node = f"CATEGORY::{category}"

        if node not in pos:
            continue

        x, y = pos[node]
        count = int(category_counts[category])
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        category_traces.append(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                text=[f"<b>{short_label(category, 28)}</b>"],
                textposition="middle center",
                textfont=dict(
                    color="black",
                    size=10,
                    family="Arial"
                ),
                hoverinfo="text",
                hovertext=[
                    f"<b>{category}</b><br>"
                    f"Actors across selected missions: {count}"
                ],
                name=category,
                marker=dict(
                    size=22 + min(count * 0.35, 10),
                    color=color,
                    symbol="diamond",
                    line=dict(width=1.5, color="white"),
                    opacity=0.96
                )
            )
        )

    # -----------------------------
    # Actor nodes
    # -----------------------------
    actor_traces = []

    for category in category_order:
        sub = category_actor_df[category_actor_df["actor_category"] == category]
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        xs = []
        ys = []
        labels = []
        hovers = []

        for _, row in sub.iterrows():
            actor_name = row["actor_name"]
            actor_node = actor_positions.get((category, actor_name))

            if actor_node not in pos:
                continue

            x, y = pos[actor_node]

            xs.append(x)
            ys.append(y)
            labels.append(actor_name)
            hovers.append(
                f"<b>{actor_name}</b><br>"
                f"Category: {category}<br>"
                f"Missions: {row['missions']}"
            )

        actor_traces.append(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                text=labels,
                textposition="middle right",
                hoverinfo="text",
                hovertext=hovers,
                name=f"{category} actors",
                marker=dict(
                    size=13,
                    color=color,
                    opacity=0.75,
                    line=dict(width=1, color="white")
                ),
                showlegend=False
            )
        )

    fig = go.Figure(
        data=edge_traces + [mission_trace] + category_traces + actor_traces
    )

    fig.update_layout(
        title="Mission Actor Network",
        height=720,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=30, r=80, t=70, b=30),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-1.35, 1.45]
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-1.05, 1.05]
        ),
        annotations=[
            dict(x=-1.05, y=1.02, text="<b>Missions</b>", showarrow=False, font=dict(size=13)),
            dict(x=0, y=1.02, text="<b>Categories</b>", showarrow=False, font=dict(size=13)),
            dict(x=1.05, y=1.02, text="<b>Actors</b>", showarrow=False, font=dict(size=13)),
        ]
    )

    return fig

def make_mission_actor_category_network(missions_df, actors_df):
    """
    Network graph:
    - Mission reports are blue circular nodes.
    - Actor categories are orange diamond nodes.
    - Edges connect each mission to the actor categories it engaged.
    - Edge weight = number of actors in that category for that mission.
    """

    if missions_df.empty or actors_df.empty:
        return None

    df = actors_df.copy()

    df["document_symbol"] = df["document_symbol"].fillna("Unknown mission")
    df["mission_title"] = df["mission_title"].fillna(df["document_symbol"])
    df["actor_category"] = df["actor_category"].fillna("Unknown")
    df["actor_name"] = df["actor_name"].fillna("Unnamed actor")

    edge_df = (
        df.groupby(["document_symbol", "mission_title", "actor_category"])
        .agg(
            actor_count=("actor_name", "count"),
            actor_names=("actor_name", lambda x: "<br>".join(sorted(x.astype(str).unique())[:12]))
        )
        .reset_index()
    )

    if edge_df.empty:
        return None

    G = nx.Graph()

    mission_meta = missions_df.copy()

    if "records_count" in mission_meta.columns:
        mission_meta["records_count"] = pd.to_numeric(
            mission_meta["records_count"],
            errors="coerce"
        ).fillna(0)
    else:
        mission_meta["records_count"] = 0

    if "actors_count" in mission_meta.columns:
        mission_meta["actors_count"] = pd.to_numeric(
            mission_meta["actors_count"],
            errors="coerce"
        ).fillna(0)
    else:
        mission_meta["actors_count"] = 0

    mission_lookup = (
        mission_meta
        .drop_duplicates(subset=["document_symbol"])
        .set_index("document_symbol")
        .to_dict(orient="index")
    )

    for _, row in edge_df.iterrows():
        document_symbol = row["document_symbol"]
        mission_title = row["mission_title"]
        actor_category = row["actor_category"]
        actor_count = int(row["actor_count"])
        actor_names = row["actor_names"]

        mission_node = f"MISSION::{document_symbol}"
        category_node = f"CATEGORY::{actor_category}"

        meta = mission_lookup.get(document_symbol, {})

        G.add_node(
            mission_node,
            label=document_symbol,
            node_type="Mission",
            hover=(
                f"<b>{document_symbol}</b><br>"
                f"{mission_title}<br><br>"
                f"Country/Region: {meta.get('mission_country_or_region', 'N/A')}<br>"
                f"Mission type: {meta.get('mission_type', 'N/A')}<br>"
                f"Records: {int(meta.get('records_count', 0))}<br>"
                f"Actors met: {int(meta.get('actors_count', 0))}"
            )
        )

        G.add_node(
            category_node,
            label=actor_category,
            node_type="Actor Category",
            hover=(
                f"<b>{actor_category}</b><br>"
                f"Actor category"
            )
        )

        G.add_edge(
            mission_node,
            category_node,
            weight=actor_count,
            hover=(
                f"<b>{document_symbol}</b> → <b>{actor_category}</b><br>"
                f"Actors in category: {actor_count}<br><br>"
                f"{actor_names}"
            )
        )

    if len(G.nodes) == 0:
        return None

    mission_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs["node_type"] == "Mission"
    ]

    actor_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs["node_type"] == "Actor Category"
    ]

    pos = {}

    # Missions on left
    for i, node in enumerate(sorted(mission_nodes)):
        pos[node] = (-1, -i)

    # Actor categories on right
    for i, node in enumerate(sorted(actor_nodes)):
        pos[node] = (1, -i)

    edge_x = []
    edge_y = []

    edge_hover_x = []
    edge_hover_y = []
    edge_hover_text = []

    for source, target, attrs in G.edges(data=True):
        x0, y0 = pos[source]
        x1, y1 = pos[target]

        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        edge_hover_x.append((x0 + x1) / 2)
        edge_hover_y.append((y0 + y1) / 2)
        edge_hover_text.append(attrs.get("hover", ""))

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(
            width=1.6,
            color="rgba(100, 116, 139, 0.35)"
        ),
        hoverinfo="none",
        showlegend=False
    )

    edge_hover_trace = go.Scatter(
        x=edge_hover_x,
        y=edge_hover_y,
        mode="markers",
        marker=dict(
            size=14,
            color="rgba(0,0,0,0)"
        ),
        hoverinfo="text",
        hovertext=edge_hover_text,
        showlegend=False
    )

    mission_x = []
    mission_y = []
    mission_labels = []
    mission_hover = []
    mission_sizes = []

    category_x = []
    category_y = []
    category_labels = []
    category_hover = []
    category_sizes = []

    for node, attrs in G.nodes(data=True):
        x, y = pos[node]
        weighted_degree = G.degree(node, weight="weight")

        if attrs["node_type"] == "Mission":
            mission_x.append(x)
            mission_y.append(y)
            mission_labels.append(attrs["label"])
            mission_hover.append(attrs["hover"])
            mission_sizes.append(34 + min(weighted_degree * 1.4, 36))

        else:
            category_x.append(x)
            category_y.append(y)
            category_labels.append(attrs["label"])
            category_hover.append(attrs["hover"])
            category_sizes.append(24 + min(weighted_degree * 1.1, 34))

    mission_trace = go.Scatter(
        x=mission_x,
        y=mission_y,
        mode="markers+text",
        text=mission_labels,
        textposition="top center",
        hoverinfo="text",
        hovertext=mission_hover,
        name="Mission reports",
        marker=dict(
            size=mission_sizes,
            color="#2563EB",
            line=dict(width=2, color="white"),
            opacity=0.95
        )
    )

    category_trace = go.Scatter(
        x=category_x,
        y=category_y,
        mode="markers+text",
        text=category_labels,
        textposition="bottom center",
        hoverinfo="text",
        hovertext=category_hover,
        name="Actor categories",
        marker=dict(
            size=category_sizes,
            color="#F97316",
            symbol="diamond",
            line=dict(width=2, color="white"),
            opacity=0.92
        )
    )

    fig = go.Figure(
        data=[
            edge_trace,
            edge_hover_trace,
            mission_trace,
            category_trace
        ]
    )

    fig.update_layout(
        title="Mission–Actor Category Network",
        height=720,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=70, b=10),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        )
    )

    return fig

def make_parallel(records_df):
    df = records_df.copy()

    cols = [
        "report_record_type",
        "primary_theme",
        "action_orientation"
    ]

    for col in cols:
        df[col] = df[col].fillna("Unknown")

    # Keep only top themes
    top_themes = (
        df["primary_theme"]
        .value_counts()
        .head(10)
        .index
    )

    df["primary_theme"] = df["primary_theme"].where(
        df["primary_theme"].isin(top_themes),
        "Other"
    )

    fig = px.parallel_categories(
        df,
        dimensions=[
            "report_record_type",
            "primary_theme",
            "action_orientation"
        ],
        color=df["primary_theme"].astype("category").cat.codes,
        color_continuous_scale=px.colors.sequential.Blues
    )

    fig.update_layout(
        height=650,
        paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=20)
    )

    return fig

def make_sankey(records_df):
    df = records_df.copy()

    cols = ["report_record_type", "primary_theme", "action_orientation"]
    for col in cols:
        df[col] = df[col].fillna("Unknown")

    grouped = (
        df.groupby(["report_record_type", "primary_theme", "action_orientation"])
        .size()
        .reset_index(name="count")
    )

    labels = []
    index = {}

    def get_index(label):
        if label not in index:
            index[label] = len(labels)
            labels.append(label)
        return index[label]

    sources = []
    targets = []
    values = []

    for _, row in grouped.iterrows():
        rt = f"Type: {row['report_record_type']}"
        th = f"Theme: {row['primary_theme']}"
        ac = f"Action: {row['action_orientation']}"

        sources.append(get_index(rt))
        targets.append(get_index(th))
        values.append(row["count"])

        sources.append(get_index(th))
        targets.append(get_index(ac))
        values.append(row["count"])

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=25,
                thickness=70,
                line=dict(color="rgba(15,23,42,0.5)", width=1.5),
                label=labels,
                color="#7DD3FC",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color="rgba(37, 99, 235, 0.08)",
            ),
        )
    )

    fig.update_layout(
        title_text="Analytical Flow: Record Type → Theme → Action Orientation",
        height=640,
        margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="white",
        font_size=11,
    )

    return fig


def apply_report_filters(missions_df, records_df, activities_df, actors_df):
    st.sidebar.title("Report Filters")
    st.sidebar.markdown("Explore extracted Security Council mission report findings.")

    mission_options = ["All"] + missions_df["document_symbol"].dropna().unique().tolist()

    selected_mission = st.sidebar.selectbox(
        "Mission Report",
        mission_options,
        key="report_mission_filter"
    )

    theme_options = ["All"] + sorted(records_df["primary_theme"].dropna().unique().tolist())

    selected_theme = st.sidebar.selectbox(
        "Primary Theme",
        theme_options,
        key="report_theme_filter"
    )

    concern_values = records_df["level_of_concern"].dropna().unique().tolist()
    concern_options = ["All"] + [x for x in CONCERN_ORDER if x in concern_values]

    selected_concern = st.sidebar.selectbox(
        "Level of Concern",
        concern_options,
        key="report_concern_filter"
    )

    record_type_options = ["All"] + sorted(records_df["report_record_type"].dropna().unique().tolist())

    selected_record_type = st.sidebar.selectbox(
        "Record Type",
        record_type_options,
        key="report_record_type_filter"
    )

    action_options = ["All"] + sorted(records_df["action_orientation"].dropna().unique().tolist())

    selected_action = st.sidebar.selectbox(
        "Action Orientation",
        action_options,
        key="report_action_filter"
    )

    filtered_records = records_df.copy()
    filtered_missions = missions_df.copy()
    filtered_activities = activities_df.copy()
    filtered_actors = actors_df.copy()

    if selected_mission != "All":
        filtered_records = filtered_records[filtered_records["document_symbol"] == selected_mission]
        filtered_missions = filtered_missions[filtered_missions["document_symbol"] == selected_mission]
        filtered_activities = filtered_activities[filtered_activities["document_symbol"] == selected_mission]
        filtered_actors = filtered_actors[filtered_actors["document_symbol"] == selected_mission]

    if selected_theme != "All":
        filtered_records = filtered_records[filtered_records["primary_theme"] == selected_theme]

    if selected_concern != "All":
        filtered_records = filtered_records[filtered_records["level_of_concern"] == selected_concern]

    if selected_record_type != "All":
        filtered_records = filtered_records[filtered_records["report_record_type"] == selected_record_type]

    if selected_action != "All":
        filtered_records = filtered_records[filtered_records["action_orientation"] == selected_action]

    symbols_after_record_filters = filtered_records["document_symbol"].dropna().unique().tolist()

    if selected_mission == "All" and symbols_after_record_filters:
        filtered_missions = filtered_missions[
            filtered_missions["document_symbol"].isin(symbols_after_record_filters)
        ]
        filtered_activities = filtered_activities[
            filtered_activities["document_symbol"].isin(symbols_after_record_filters)
        ]
        filtered_actors = filtered_actors[
            filtered_actors["document_symbol"].isin(symbols_after_record_filters)
        ]

    st.sidebar.markdown("---")
    st.sidebar.caption("Tip: select 'All' to include all values.")

    return filtered_missions, filtered_records, filtered_activities, filtered_actors


def render_mission_card(row):
    title = row.get("mission_title") or "Untitled mission"

    st.markdown(
        f"""
        <div class="mission-hero">
            <h2>{title}</h2>
            <p>
                <b>{row.get("document_symbol") or ""}</b>
                &nbsp; | &nbsp;
                {row.get("mission_country_or_region") or ""}
                &nbsp; | &nbsp;
                {row.get("mission_type") or ""}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card("Records", int(row.get("records_count", 0)))

    with c2:
        metric_card("Activities", int(row.get("activities_count", 0)))

    with c3:
        metric_card("Actors Met", int(row.get("actors_count", 0)))

    with c4:
        metric_card("Field Exposure", row.get("field_exposure") or "N/A")

    st.markdown('<div class="section-title">Main Themes</div>', unsafe_allow_html=True)
    render_pills(row.get("main_themes", []))

    st.markdown('<div class="section-title">Summary Assessment</div>', unsafe_allow_html=True)
    st.write(row.get("summary_assessment") or "No summary assessment available.")

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-title">Main Risks</div>', unsafe_allow_html=True)
        risks = row.get("main_risks", [])
        if risks:
            for risk in risks:
                st.markdown(f"- {risk}")
        else:
            st.caption("No main risks recorded.")

    with right:
        st.markdown('<div class="section-title">Main Policy Signals</div>', unsafe_allow_html=True)
        signals = row.get("main_policy_signals", [])
        if signals:
            for signal in signals:
                st.markdown(f"- {signal}")
        else:
            st.caption("No major policy signals recorded.")

    st.markdown('<div class="section-title">Main Commitments / Follow-up</div>', unsafe_allow_html=True)
    commitments = row.get("main_commitments", [])
    if commitments:
        for commitment in commitments:
            st.markdown(f"- {commitment}")
    else:
        st.caption("No commitments recorded.")


def render_records_explorer(records_df):
    st.markdown("### Records Explorer")

    search_text = st.text_input(
        "Search record text, actor source, actor target, political signal, policy implication or geography",
        "",
        key="report_record_search"
    )

    df = records_df.copy()

    if search_text.strip():
        q = search_text.strip().lower()
        searchable_cols = [
            "record_text",
            "actor_source",
            "actor_target",
            "political_signal",
            "policy_implication",
            "geographic_scope",
            "primary_theme",
            "report_record_type",
            "action_orientation",
        ]

        mask = pd.Series(False, index=df.index)
        for col in searchable_cols:
            if col in df.columns:
                mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)

        df = df[mask]

    display_cols = [
        "document_symbol",
        "record_id",
        "report_record_type",
        "primary_theme",
        "level_of_concern",
        "action_orientation",
        "degree_of_consensus",
        "actor_source",
        "actor_target",
        "geographic_scope",
        "record_text",
        "political_signal",
        "policy_implication",
    ]

    display_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(
        df[display_cols],
        width='content',
        hide_index=True,
        height=520,
    )

    csv = df[display_cols].to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download filtered records as CSV",
        csv,
        file_name="filtered_mission_report_records.csv",
        mime="text/csv",
    )


def render_reports_dashboard():
    reports = load_report_json(REPORTS_FILE)

    if reports is None:
        st.error(f"Could not find `{REPORTS_FILE}`. Please check the file path.")
        return

    if not reports:
        st.warning("The reports JSON file was loaded, but no reports were found.")
        return

    missions_df, records_df, activities_df, actors_df = flatten_reports(reports)

    if missions_df.empty:
        st.error("No mission report metadata found in the JSON file.")
        return

    if records_df.empty:
        st.warning("Mission report metadata loaded, but no substantive records were found.")
        return

    filtered_missions, filtered_records, filtered_activities, filtered_actors = apply_report_filters(
        missions_df, records_df, activities_df, actors_df
    )

    st.markdown(
        """
        <div class="dashboard-title">📊 Mission Reports Analytics</div>
        <div class="dashboard-subtitle">
            Analyze extracted mission metadata, activities, actors engaged, findings, risks, recommendations, commitments and political signals.
        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------
    # KPI cards
    # --------------------------------------------------

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        metric_card("Mission Reports", len(filtered_missions))

    with k2:
        metric_card("Substantive Records", len(filtered_records))

    with k3:
        metric_card("Activities", len(filtered_activities))

    with k4:
        metric_card("Actors Met", len(filtered_actors))

    with k5:
        high_count = filtered_records[
            filtered_records["level_of_concern"].isin(["High", "Critical"])
        ].shape[0]
        metric_card("High / Critical", high_count)

    st.markdown("<br>", unsafe_allow_html=True)

    overview_tab, analytics_tab, mission_tab, records_tab, actors_tab, data_tab = st.tabs(
        [
            "Overview",
            "Analytical Flows",
            "Mission Deep Dive",
            "Records Explorer",
            "Actors & Activities",
            "Data Tables",
        ]
    )

    # --------------------------------------------------
    # Overview
    # --------------------------------------------------

    with overview_tab:
        c1, c2 = st.columns([1.3, 1])

        with c1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_records.empty:
                st.plotly_chart(make_report_theme_bar(filtered_records), width='content', key = "1")
            else:
                st.info("No records available for the current filters.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_records.empty:
                st.plotly_chart(make_record_type_donut(filtered_records), width='content', key = "2")
            else:
                st.info("No record-type data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        c5, c6 = st.columns(2)

        with c5:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            st.plotly_chart(
                make_region_actors_bubble(filtered_missions),
                width='content'
            )

            st.markdown("</div>", unsafe_allow_html=True)

        with c6:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            st.plotly_chart(
                make_region_activities_bubble(filtered_missions),
                width='content'
            )

            st.markdown("</div>", unsafe_allow_html=True)

        c3, c4 = st.columns([1, 1])

        with c3:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            fig = make_report_timeline(filtered_missions)
            if fig is not None:
                st.plotly_chart(fig, width='content')
            else:
                st.info("No mission dates available for timeline.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c4:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_records.empty:
                st.plotly_chart(make_concern_chart(filtered_records), width='content')
            else:
                st.info("No concern data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        c7, c8, c9 = st.columns(3)

        with c7:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_mission_metadata_chart(
                filtered_missions,
                "mission_type",
                "Mission Type"
            )

            st.plotly_chart(fig, width='content')

            st.markdown("</div>", unsafe_allow_html=True)

        with c8:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_mission_metadata_chart(
                filtered_missions,
                "field_exposure",
                "Field Exposure"
            )

            st.plotly_chart(fig, width='content')

            st.markdown("</div>", unsafe_allow_html=True)

        with c9:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_mission_metadata_chart(
                filtered_missions,
                "overall_character",
                "Mission Character"
            )

            st.plotly_chart(fig, width='content')

            st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Analytics
    # --------------------------------------------------

    with analytics_tab:
        c1, c2 = st.columns([1, 1])

        with c1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_records.empty:
                st.plotly_chart(make_action_treemap(filtered_records), width='content')
            else:
                st.info("No analytical records available.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            fig = make_theme_heatmap(filtered_records)
            if fig is not None:
                st.plotly_chart(fig, width='content')
            else:
                st.info("No heatmap data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        if not filtered_records.empty:
            st.plotly_chart(make_sankey(filtered_records), width='content')
        else:
            st.info("No Sankey data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Mission Deep Dive
    # --------------------------------------------------

    with mission_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        mission_symbols = filtered_missions["document_symbol"].dropna().tolist()

        if not mission_symbols:
            st.info("No missions match the current filters.")
        else:
            def format_mission_symbol(x):
                row = filtered_missions[filtered_missions["document_symbol"] == x].iloc[0]
                return f"{x} — {row.get('mission_country_or_region', '')}"

            selected_symbol = st.selectbox(
                "Select mission for deep dive",
                mission_symbols,
                format_func=format_mission_symbol,
                key="deep_dive_select"
            )

            selected_row = (
                filtered_missions[filtered_missions["document_symbol"] == selected_symbol]
                .iloc[0]
                .to_dict()
            )

            render_mission_card(selected_row)

            st.markdown("### Mission-Specific Analytical Distribution")

            mission_records = filtered_records[
                filtered_records["document_symbol"] == selected_symbol
            ]

            if not mission_records.empty:
                c1, c2 = st.columns(2)

                with c1:
                    st.plotly_chart(make_record_type_donut(mission_records), width='content')

                with c2:
                    st.plotly_chart(make_concern_chart(mission_records), width='content')

                cols = [
                    "record_id",
                    "report_record_type",
                    "primary_theme",
                    "level_of_concern",
                    "action_orientation",
                    "record_text",
                ]

                st.dataframe(
                    mission_records[cols],
                    column_config={
                        "record_id": st.column_config.NumberColumn(width="small"),
                        "report_record_type": st.column_config.TextColumn(width="small"),
                        "primary_theme": st.column_config.TextColumn(width="small"),
                        "level_of_concern": st.column_config.TextColumn(width="small"),
                        "action_orientation": st.column_config.TextColumn(width="small"),
                        "record_text": st.column_config.TextColumn(width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                )
            else:
                st.info("No records available for this mission under the current filters.")

        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Records Explorer
    # --------------------------------------------------

    with records_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        if not filtered_records.empty:
            render_records_explorer(filtered_records)
        else:
            st.info("No records match the current filters.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Actors and Activities
    # --------------------------------------------------

    with actors_tab:

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">Interactive Mission Actor Network</div>',
            unsafe_allow_html=True
        )

        network_missions = (
            filtered_actors["document_symbol"]
            .dropna()
            .drop_duplicates()
            .tolist()
        )

        if not network_missions:
            st.info("No actor network data available for the current filters.")
        else:
            default_network_missions = network_missions[:1]

            selected_network_missions = st.multiselect(
                "Select up to 5 missions for the actor network",
                options=network_missions,
                default=default_network_missions,
                max_selections=5,
                key="pyvis_actor_network_mission_select"
            )

            max_actors_per_category = st.slider(
                "Maximum actors shown per category",
                min_value=3,
                max_value=10,
                value=5,
                step=1,
                key="pyvis_max_actors_per_category"
            )

            network_html = make_pyvis_actor_network_html(
                filtered_missions,
                filtered_actors,
                selected_network_missions,
                max_actors_per_category=max_actors_per_category
            )

            if network_html is not None:
                components.html(
                    network_html,
                    height=820,
                    scrolling=True
                )

                st.caption(
                    "Drag nodes to rearrange the network. Missions appear on the left, "
                    "actor categories in the center, and selected actors on the right. "
                    "Hover over nodes or edges for full details."
                )
            else:
                st.info("Select at least one mission with actor data to display the network.")

        st.markdown("</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_actors.empty:
                st.plotly_chart(make_actor_chart(filtered_actors), width='content', key = "networkactors")
            else:
                st.info("No actor data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            if not filtered_activities.empty:
                st.plotly_chart(make_activity_chart(filtered_activities), width='content', key = "activitychart")
            else:
                st.info("No activity data available.")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Actor Engagement Matrix</div>', unsafe_allow_html=True)

        if not filtered_actors.empty:
            actor_matrix = (
                filtered_actors.groupby(["document_symbol", "actor_category"])
                .size()
                .reset_index(name="count")
                .pivot_table(
                    index="document_symbol",
                    columns="actor_category",
                    values="count",
                    fill_value=0,
                )
            )

            fig = px.imshow(
                actor_matrix,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Purples",
                title="Actors Met by Mission and Category",
            )

            fig.update_layout(
                height=max(360, 80 + 45 * len(actor_matrix.index)),
                margin=dict(l=20, r=20, t=60, b=80),
                paper_bgcolor="white",
            )

            st.plotly_chart(fig, width='content')
        else:
            st.info("No actor matrix available.")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Activity Matrix</div>', unsafe_allow_html=True)

        if not filtered_activities.empty:
            activity_matrix = (
                filtered_activities.groupby(["document_symbol", "activity_type"])
                .size()
                .reset_index(name="count")
                .pivot_table(
                    index="document_symbol",
                    columns="activity_type",
                    values="count",
                    fill_value=0,
                )
            )

            fig = px.imshow(
                activity_matrix,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Greens",
                title="Activities by Mission and Type",
            )

            fig.update_layout(
                height=max(360, 80 + 45 * len(activity_matrix.index)),
                margin=dict(l=20, r=20, t=60, b=80),
                paper_bgcolor="white",
            )

            st.plotly_chart(fig, width='content')
        else:
            st.info("No activity matrix available.")

        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------
    # Data Tables
    # --------------------------------------------------

    with data_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Mission Metadata</div>', unsafe_allow_html=True)
        st.dataframe(filtered_missions, width='content', hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Activities</div>', unsafe_allow_html=True)
        st.dataframe(filtered_activities, width='content', hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Actors Met</div>', unsafe_allow_html=True)
        st.dataframe(filtered_actors, width='content', hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Substantive Records</div>', unsafe_allow_html=True)
        st.dataframe(filtered_records, width='content', hide_index=True)

        export_payload = {
            "missions": filtered_missions.to_dict(orient="records"),
            "activities": filtered_activities.to_dict(orient="records"),
            "actors_met": filtered_actors.to_dict(orient="records"),
            "records": filtered_records.to_dict(orient="records"),
        }

        st.download_button(
            "⬇️ Download filtered report dashboard data as JSON",
            data=json.dumps(export_payload, ensure_ascii=False, indent=2, default=str),
            file_name="filtered_mission_report_dashboard_data.json",
            mime="application/json",
        )

        st.markdown("</div>", unsafe_allow_html=True)


# ==================================================
# MAIN APP TABS
# ==================================================

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
