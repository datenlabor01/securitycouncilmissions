import re
import pandas as pd
import plotly.express as px
import streamlit as st

from config import TOR_FILE, REGION_COLORS
from utils import load_json_file, metric_card


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
                "Countries": mission.get("Countries", []),
                "Countries Label": ", ".join(mission.get("Countries", [])),
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
                "Countries Label",
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

    return mission_df.rename(
        columns={
            "Objective_Types": "Objective Types"
        }
    )

def build_map_df(df):
    rows = []

    for _, row in df.iterrows():
        countries = row.get("Countries", [])

        if not isinstance(countries, list):
            continue

        for country in countries:
            country = str(country).strip()

            if country:
                rows.append({
                    "Country": country,
                    "Mission": row["Mission"],
                    "Document Symbol": row["Document Symbol"],
                    "Year": row["Year"],
                    "Objectives": 1
                })

    return pd.DataFrame(rows)

def render_tor_dashboard():
    data = load_tor_json(TOR_FILE)

    df = flatten_missions(data)

    if df.empty:
        st.warning("The TOR JSON file was loaded, but no objectives were found.")
        return

    st.sidebar.title("Filters for ToR Analysis")
    st.sidebar.markdown("Use the filters below to the ToRs.")

    country_options = sorted(
        {
            country
            for countries in df["Countries"]
            for country in countries
        }
    )
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
        country_filtered_df = df[
            df["Countries"].apply(
                lambda countries: any(
                    country in countries
                    for country in selected_countries
                )
            )
        ]
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

    st.subheader("Terms of Reference Analysis")
    st.caption(
        "Explore Security Council field mission objectives by country, region, theme, objective type, verb, geography, and time."
    )

    mission_df = build_mission_level_df(filtered_df)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        metric_card(
            "Missions (with written ToRs)",
            str(filtered_df["Document Symbol"].nunique())
        )
    with kpi2:
        metric_card("Objectives", str(len(filtered_df)))
    with kpi3:
        metric_card(
            "Countries",
            str(
                len(
                    {
                        country
                        for countries in filtered_df["Countries"]
                        for country in countries
                    }
                )
            )
        )
    with kpi4:
        metric_card("Primary Themes", str(filtered_df["Primary Theme"].nunique()))

    st.markdown("<br>", unsafe_allow_html=True)

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
        fig_time.update_traces(opacity=0.45)
        fig_time.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis_title=None,
            yaxis_title="Number of Objectives",
            hovermode="x unified"
        )
        st.plotly_chart(fig_time, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with map_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Mission Countries Map</div>', unsafe_allow_html=True)
        map_df = build_map_df(filtered_df)

        if map_df.empty:
            st.info("No map coordinates found for the selected countries/regions.")
        else:
            map_counts = (
                map_df
                .groupby("Country")
                .agg(
                    Missions=("Mission", "nunique"),
                    Objectives=("Objectives", "sum"),
                    Years=(
                        "Year",
                        lambda x: ", ".join(
                            map(str, sorted(x.dropna().astype(int).unique()))
                        )
                    )
                )
                .reset_index()
            )

            fig_map = px.scatter_geo(
                map_counts,
                locations="Country",
                locationmode="country names",
                size="Missions",
                color="Objectives",
                hover_name="Country",
                hover_data={
                    "Missions": True,
                    "Objectives": True,
                    "Years": True,
                    "Country": False
                },
                color_continuous_scale="Blues",
                projection="natural earth"
            )
            fig_map.update_traces(marker=dict(line=dict(width=1, color="white"), sizemin=8))
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
            st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Objectives by Primary Theme</div>', unsafe_allow_html=True)

        theme_counts = filtered_df["Primary Theme"].value_counts().reset_index()
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
        fig_theme.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig_theme, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Objective Type Distribution</div>', unsafe_allow_html=True)

        type_counts = filtered_df["Objective Type"].value_counts().reset_index()
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
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02)
        )
        st.plotly_chart(fig_type, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
        fig_verbs.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig_verbs, use_container_width=True)
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
        st.plotly_chart(fig_verb_type, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Mission Summary</div>', unsafe_allow_html=True)

    mission_summary = (
        mission_df
        .sort_values(["Year", "Mission"], ascending=[False, True], na_position="last")
        [[
            "Mission", "Countries Label", "Document Symbol", "Document Date",
            "Objectives", "Themes", "Objective Types"
        ]]
    )
    mission_summary["Countries Label"] = mission_summary["Countries Label"].fillna("")
    st.dataframe(mission_summary, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
    st.plotly_chart(fig_heatmap, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
                lambda row: search_lower in " ".join(row.astype(str).str.lower()),
                axis=1
            )
        ]

    display_columns = [
        "Mission", "Countries Label", "Document Symbol", "Document Date",
        "Objective ID", "Primary Theme", "Objective Type", "Verb",
        "Secondary Themes", "Objective Text"
    ]

    st.dataframe(table_df[display_columns], use_container_width=True, hide_index=True, height=520)

    csv = table_df[display_columns].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download filtered objectives as CSV",
        data=csv,
        file_name="filtered_security_council_objectives.csv",
        mime="text/csv"
    )
    st.markdown("</div>", unsafe_allow_html=True)
