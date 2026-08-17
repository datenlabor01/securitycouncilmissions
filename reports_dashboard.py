import html
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pyvis.network import Network
import streamlit as st
import streamlit.components.v1 as components

from config import (
    REPORTS_FILE, THEME_COLORS, CONCERN_ORDER, CONCERN_COLORS,
    ACTION_COLORS, REGION_COLORS, ACTOR_CATEGORY_COLORS
)
from utils import load_json_file, normalize_json_payload, metric_card, render_pills


@st.cache_data
def load_report_json(file_path: str):
    data = load_json_file(file_path)

    if data is None:
        return None

    return normalize_json_payload(data)


@st.cache_data
def flatten_reports(reports):
    mission_rows, record_rows, activity_rows, actor_rows = [], [], [], []

    for mission_idx, report in enumerate(reports, start=1):
        mission_id = report.get("document_symbol") or f"mission_{mission_idx}"
        analytics = report.get("mission_analytics", {}) or {}

        mission_rows.append({
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
        })

        for rec in report.get("records", []) or []:
            record_rows.append({
                "mission_id": mission_id,
                "mission_title": report.get("mission_title"),
                "document_symbol": report.get("document_symbol"),
                "document_date": report.get("document_date"),
                "mission_country_or_region": report.get("mission_country_or_region"),
                "record_id": rec.get("record_id"),
                "record_text": rec.get("record_text"),
                "verb": rec.get("verb"),
                "mission_type": analytics.get("mission_type"),
                "mission_subtype": analytics.get("mission_subtype"),
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
            })

        for act in report.get("activities", []) or []:
            activity_rows.append({
                "mission_id": mission_id,
                "mission_title": report.get("mission_title"),
                "document_symbol": report.get("document_symbol"),
                "activity_id": act.get("activity_id"),
                "activity_type": act.get("activity_type"),
                "activity_description": act.get("activity_description"),
            })

        for actor in report.get("actors_met", []) or []:
            actor_rows.append({
                "mission_id": mission_id,
                "mission_title": report.get("mission_title"),
                "document_symbol": report.get("document_symbol"),
                "actor_id": actor.get("actor_id"),
                "actor_name": actor.get("actor_name"),
                "actor_category": actor.get("actor_category"),
            })

    missions_df = pd.DataFrame(mission_rows)
    records_df = pd.DataFrame(record_rows)
    activities_df = pd.DataFrame(activity_rows)
    actors_df = pd.DataFrame(actor_rows)

    if not missions_df.empty:
        missions_df["document_date"] = pd.to_datetime(missions_df["document_date"], errors="coerce")
        missions_df["year"] = missions_df["document_date"].dt.year

    if not records_df.empty:
        records_df["document_date"] = pd.to_datetime(records_df["document_date"], errors="coerce")
        records_df["year"] = records_df["document_date"].dt.year

    return missions_df, records_df, activities_df, actors_df


def make_report_theme_bar(records_df):
    theme_counts = records_df["primary_theme"].fillna("Unknown").value_counts().reset_index()
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
    df = records_df["report_record_type"].fillna("Unknown").value_counts().reset_index()
    df.columns = ["report_record_type", "count"]

    fig = px.pie(
        df,
        names="report_record_type",
        values="count",
        hole=0.56,
        title="Record-Type Mix",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_layout(height=430, margin=dict(l=20, r=20, t=60, b=20), paper_bgcolor="white", showlegend=False)
    fig.update_traces(textinfo="percent+label")
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


def _prepare_temporal_region_df(missions_df, value_col, value_label, period="Y"):
    df = missions_df.copy()

    if df.empty:
        return pd.DataFrame()

    df = _clean_region_values(df)

    if "document_date" not in df.columns or value_col not in df.columns:
        return pd.DataFrame()

    df["document_date"] = pd.to_datetime(df["document_date"], errors="coerce")
    df = df.dropna(subset=["document_date"])

    if df.empty:
        return pd.DataFrame()

    # Split comma-separated region combinations so each region gets its own line
    df["regions"] = df["regions"].astype(str).str.split(",")
    df = df.explode("regions")
    df["regions"] = (
        df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    # Create a real temporal period
    if period == "Q":
        df["period"] = df["document_date"].dt.to_period("Q").dt.to_timestamp()
        x_title = "Quarter"
        tickformat = "%Y Q%q"
    elif period == "M":
        df["period"] = df["document_date"].dt.to_period("M").dt.to_timestamp()
        x_title = "Month"
        tickformat = "%b %Y"
    else:
        df["period"] = df["document_date"].dt.to_period("Y").dt.to_timestamp()
        x_title = "Year"
        tickformat = "%Y"

    trend_df = (
        df
        .groupby(["period", "regions"], dropna=False)
        .agg(
            Value=(value_col, "sum"),
            Mission_Reports=("document_symbol", "nunique"),
            Records=("records_count", "sum"),
            Actors_Met=("actors_count", "sum"),
            Activities=("activities_count", "sum")
        )
        .reset_index()
        .sort_values(["regions", "period"])
    )

    trend_df["Metric"] = value_label

    return trend_df, x_title, tickformat

def _prepare_detail_temporal_region_df(
    detail_df,
    missions_df,
    value_id_col,
    selected_regions=None
):
    df = detail_df.copy()
    missions = missions_df.copy()

    if df.empty or missions.empty:
        return pd.DataFrame()

    if "document_symbol" not in df.columns or "document_symbol" not in missions.columns:
        return pd.DataFrame()

    mission_lookup = (
        missions[
            [
                "document_symbol",
                "document_date",
                "regions"
            ]
        ]
        .drop_duplicates(subset=["document_symbol"])
        .copy()
    )

    mission_lookup = _clean_region_values(mission_lookup)
    mission_lookup["document_date"] = pd.to_datetime(
        mission_lookup["document_date"],
        errors="coerce"
    )

    df = df.merge(
        mission_lookup,
        on="document_symbol",
        how="left",
        suffixes=("", "_mission")
    )

    df = df.dropna(subset=["document_date"])

    if df.empty:
        return pd.DataFrame()

    df["regions"] = df["regions"].astype(str).str.split(",")
    df = df.explode("regions")

    df["regions"] = (
        df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    if selected_regions and "All Regions" not in selected_regions:
        df = df[df["regions"].isin(selected_regions)]

    if df.empty:
        return pd.DataFrame()

    # Prevent double counting when several selected regions match the same multi-region mission.
    dedupe_cols = ["document_symbol"]

    if value_id_col in df.columns:
        dedupe_cols.append(value_id_col)
    else:
        dedupe_cols.append(df.index.name or "document_symbol")

    dedupe_cols = [col for col in dedupe_cols if col in df.columns]

    if dedupe_cols:
        df = df.drop_duplicates(subset=dedupe_cols)

    df["year"] = df["document_date"].dt.year

    return df


def get_available_regions(missions_df):
    if missions_df.empty:
        return ["All Regions"]

    df = _clean_region_values(missions_df)

    df["regions"] = df["regions"].astype(str).str.split(",")
    df = df.explode("regions")

    df["regions"] = (
        df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    regions = sorted(df["regions"].dropna().unique().tolist())

    return ["All Regions"] + regions

def make_primary_theme_temporal_bar(
    records_df,
    missions_df,
    selected_regions=None,
    bucket_size=5
):
    df = _prepare_detail_temporal_region_df(
        detail_df=records_df,
        missions_df=missions_df,
        value_id_col="record_id",
        selected_regions=selected_regions
    )

    if df.empty:
        return None

    df["primary_theme"] = (
        df["primary_theme"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)

    # Create 5-year buckets, for example 1960-1964, 1965-1969
    df["year_bucket_start"] = (df["year"] // bucket_size) * bucket_size
    df["year_bucket_end"] = df["year_bucket_start"] + bucket_size - 1
    df["year_bucket"] = (
        df["year_bucket_start"].astype(str)
        + "-"
        + df["year_bucket_end"].astype(str)
    )

    chart_df = (
        df
        .groupby(
            ["year_bucket_start", "year_bucket", "primary_theme"],
            dropna=False
        )
        .size()
        .reset_index(name="Records")
        .sort_values(["year_bucket_start", "primary_theme"])
    )

    if chart_df.empty:
        return None

    bucket_order = (
        chart_df[["year_bucket_start", "year_bucket"]]
        .drop_duplicates()
        .sort_values("year_bucket_start")["year_bucket"]
        .tolist()
    )

    fig = px.bar(
        chart_df,
        x="year_bucket",
        y="Records",
        color="primary_theme",
        color_discrete_map=THEME_COLORS,
        barmode="stack",
        title="Primary Themes per Record Over Time",
        category_orders={
            "year_bucket": bucket_order
        },
        custom_data=[
            "primary_theme",
            "Records"
        ]
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Period: %{x}<br>"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        bargap=0.22,
        bargroupgap=0.04,
        hovermode="closest",
        xaxis_title=None,
        yaxis_title="Records",
        margin=dict(
            l=20,
            r=20,
            t=65,
            b=70
        ),
        font=dict(color="#111827")
    )

    fig.update_xaxes(
        title_text="",
        showgrid=False,
        tickangle=-35
    )

    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=bucket_order,
        showgrid=False,
        tickangle=-35
    )

    fig.update_yaxes(
        rangemode="tozero",
        gridcolor="rgba(148,163,184,0.25)",
        zerolinecolor="rgba(148,163,184,0.45)"
    )

    return fig

def make_actor_category_temporal_bar(
    actors_df,
    missions_df,
    selected_regions=None,
    bucket_size=5
):
    df = _prepare_detail_temporal_region_df(
        detail_df=actors_df,
        missions_df=missions_df,
        value_id_col="actor_id",
        selected_regions=selected_regions
    )

    if df.empty:
        return None

    df["actor_category"] = (
        df["actor_category"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)

    # Create 5-year buckets, for example:
    df["year_bucket_start"] = (df["year"] // bucket_size) * bucket_size
    df["year_bucket_end"] = df["year_bucket_start"] + bucket_size - 1

    df["year_bucket"] = (
        df["year_bucket_start"].astype(str)
        + "-"
        + df["year_bucket_end"].astype(str)
    )

    chart_df = (
        df
        .groupby(
            ["year_bucket_start", "year_bucket", "actor_category"],
            dropna=False
        )
        .size()
        .reset_index(name="Actors")
        .sort_values(["year_bucket_start", "actor_category"])
    )

    if chart_df.empty:
        return None

    bucket_order = (
        chart_df[["year_bucket_start", "year_bucket"]]
        .drop_duplicates()
        .sort_values("year_bucket_start")["year_bucket"]
        .tolist()
    )

    fig = px.bar(
        chart_df,
        x="year_bucket",
        y="Actors",
        color="actor_category",
        color_discrete_map=ACTOR_CATEGORY_COLORS,
        barmode="stack",
        title="Actor Categories Met Over Time",
        category_orders={
            "year_bucket": bucket_order
        },
        custom_data=[
            "actor_category",
            "Actors"
        ]
    )

    fig.update_traces(
        hovertemplate=(
            "Period: %{x}<br>"
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        bargap=0.22,
        bargroupgap=0.04,
        hovermode="closest",
        xaxis_title="5-Year Period",
        yaxis_title="Actors Met",
        margin=dict(
            l=20,
            r=20,
            t=65,
            b=75
        ),
        font=dict(color="#111827")
    )

    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=bucket_order,
        showgrid=False,
        tickangle=-35
    )

    fig.update_yaxes(
        rangemode="tozero",
        gridcolor="rgba(148,163,184,0.25)",
        zerolinecolor="rgba(148,163,184,0.45)"
    )

    return fig

ACTOR_DIVERSITY_MAP = {
    "Low": 1,
    "Moderate": 2,
    "High": 3
}

ACTIVITY_TYPE_COLORS = {
    "Meeting": "#2563EB",
    "Site Visit": "#16A34A",
    "Briefing": "#F97316",
    "Consultation": "#9333EA",
    "Engagement Session": "#0891B2",
    "Dialogue": "#65A30D",
    "Field Visit": "#64748B",
    "Visit to UN Facility": "#DB2777",
    "Press Stakeout": "#DC2626",
    "Other": "#94A3B8",
    "Unknown": "#CBD5E1",
}

def make_actor_diversity_temporal_line(missions_df, bucket_size=5):
    df = missions_df.copy()

    if df.empty:
        return None

    required_cols = [
        "document_symbol",
        "document_date",
        "regions",
        "actor_diversity_assessment"
    ]

    for col in required_cols:
        if col not in df.columns:
            return None

    df = _explode_regions(df)

    df["document_date"] = pd.to_datetime(
        df["document_date"],
        errors="coerce"
    )

    df = df.dropna(subset=["document_date"])

    if df.empty:
        return None

    df["actor_diversity_assessment"] = (
        df["actor_diversity_assessment"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    df["year"] = df["document_date"].dt.year.astype(int)

    df["year_bucket_start"] = (
        df["year"] // bucket_size
    ) * bucket_size

    df["year_bucket_end"] = (
        df["year_bucket_start"] + bucket_size - 1
    )

    df["year_bucket"] = (
        df["year_bucket_start"].astype(str)
        + "-"
        + df["year_bucket_end"].astype(str)
    )

    # One mission should count once per region and period
    base_df = df.drop_duplicates(
        subset=[
            "year_bucket",
            "regions",
            "document_symbol"
        ]
    )

    trend_df = (
        base_df
        .groupby(
            [
                "year_bucket_start",
                "year_bucket",
                "regions"
            ],
            dropna=False
        )
        .agg(
            Mission_Reports=("document_symbol", "nunique")
        )
        .reset_index()
        .sort_values(["regions", "year_bucket_start"])
    )

    if trend_df.empty:
        return None

    # Assessment category breakdown for hover
    breakdown_df = (
        df
        .drop_duplicates(
            subset=[
                "year_bucket",
                "regions",
                "document_symbol",
                "actor_diversity_assessment"
            ]
        )
        .groupby(
            [
                "year_bucket",
                "regions",
                "actor_diversity_assessment"
            ],
            dropna=False
        )
        .agg(
            Count=("document_symbol", "nunique")
        )
        .reset_index()
    )

    hover_breakdown = (
        breakdown_df
        .pivot_table(
            index=["year_bucket", "regions"],
            columns="actor_diversity_assessment",
            values="Count",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    for col in ["Low", "Moderate", "High", "Unknown"]:
        if col not in hover_breakdown.columns:
            hover_breakdown[col] = 0

    trend_df = trend_df.merge(
        hover_breakdown,
        on=["year_bucket", "regions"],
        how="left"
    )

    for col in ["Low", "Moderate", "High", "Unknown"]:
        trend_df[col] = trend_df[col].fillna(0).astype(int)

    bucket_order = (
        trend_df[
            [
                "year_bucket_start",
                "year_bucket"
            ]
        ]
        .drop_duplicates()
        .sort_values("year_bucket_start")["year_bucket"]
        .tolist()
    )

    fig = px.line(
        trend_df,
        x="year_bucket",
        y="Mission_Reports",
        color="regions",
        markers=True,
        color_discrete_map=REGION_COLORS,
        title="Actor Diversity Assessment Over Time by Region",
        category_orders={
            "year_bucket": bucket_order
        },
        custom_data=[
            "regions",
            "Mission_Reports",
            "Low",
            "Moderate",
            "High",
            "Unknown"
        ]
    )

    fig.update_traces(
        mode="lines+markers",
        line=dict(
            width=2.8,
            shape="linear"
        ),
        marker=dict(
            size=6,
            line=dict(
                color="white",
                width=1
            ),
            opacity=1
        ),
        opacity=1,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Period: %{x}<br>"
            "Mission reports: %{customdata[1]}<br>"
            "Low: %{customdata[2]}<br>"
            "Moderate: %{customdata[3]}<br>"
            "High: %{customdata[4]}<br>"
            "Unknown: %{customdata[5]}"
            "<extra></extra>"
        )
    )

    total_df = (
        base_df
        .groupby(
            [
                "year_bucket_start",
                "year_bucket"
            ],
            dropna=False
        )
        .agg(
            Mission_Reports=("document_symbol", "nunique")
        )
        .reset_index()
        .sort_values("year_bucket_start")
    )

    fig.add_trace(
        go.Scatter(
            x=total_df["year_bucket"],
            y=total_df["Mission_Reports"],
            mode="lines",
            name="Total",
            line=dict(
                color="rgba(17, 24, 39, 0.85)",
                width=3,
                shape="linear"
            ),
            hovertemplate=(
                "<b>Total</b><br>"
                "Period: %{x}<br>"
                "Mission reports: %{y}"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        height=470,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Mission Reports",
        hovermode="x unified",
        margin=dict(
            l=20,
            r=150,
            t=70,
            b=50
        ),
        font=dict(color="#111827"),
        legend_title_text="Region",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=12)
        )
    )

    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=bucket_order,
        showgrid=False,
        tickangle=-35,
        title_text=""
    )

    fig.update_yaxes(
        rangemode="tozero",
        gridcolor="rgba(148, 163, 184, 0.25)",
        zerolinecolor="rgba(148, 163, 184, 0.45)"
    )

    return fig

def make_region_temporal_line(
    missions_df,
    value_col,
    value_label,
    title,
    y_title,
    period="Y",
    smooth_window=3
):
    prepared = _prepare_temporal_region_df(
        missions_df=missions_df,
        value_col=value_col,
        value_label=value_label,
        period=period
    )

    if isinstance(prepared, pd.DataFrame) and prepared.empty:
        return None

    trend_df, x_title, tickformat = prepared

    if trend_df.empty:
        return None

    # Smooth regional values slightly to reduce jagged mission-report spikes.
    # Set smooth_window=None or 1 if you want raw values only.
    trend_df = trend_df.sort_values(["regions", "period"]).copy()

    if smooth_window and smooth_window > 1:
        trend_df["Display_Value"] = (
            trend_df
            .groupby("regions")["Value"]
            .transform(
                lambda x: x.rolling(
                    window=smooth_window,
                    min_periods=1,
                    center=True
                ).mean()
            )
        )
    else:
        trend_df["Display_Value"] = trend_df["Value"]

    fig = px.line(
        trend_df,
        x="period",
        y="Display_Value",
        color="regions",
        markers=True,
        color_discrete_map=REGION_COLORS,
        title=title,
        custom_data=[
            "regions",
            "Value",
            "Mission_Reports",
            "Actors_Met",
            "Activities",
            "Records"
        ]
    )

    # Regional lines: clean, visible, but not oversized
    fig.update_traces(
        mode="lines+markers",
        line=dict(
            width=2.8,
            shape="linear"
        ),
        marker=dict(
            size=6,
            line=dict(color="white", width=1),
            opacity=1
        ),
        opacity=1,
        hovertemplate=(
            "Mission reports: %{customdata[2]}<br>"
            + "Actors met: %{customdata[3]}<br>"
            + "Activities: %{customdata[4]}<br>"
            + "Records: %{customdata[5]}"
            + "<extra></extra>"
        )
    )

    # Total line across all regions
    total_df = (
        trend_df
        .groupby("period", dropna=False)
        .agg(
            Value=("Value", "sum"),
            Mission_Reports=("Mission_Reports", "sum"),
            Actors_Met=("Actors_Met", "sum"),
            Activities=("Activities", "sum"),
            Records=("Records", "sum")
        )
        .reset_index()
        .sort_values("period")
    )

    if smooth_window and smooth_window > 1:
        total_df["Display_Value"] = (
            total_df["Value"]
            .rolling(
                window=smooth_window,
                min_periods=1,
                center=True
            )
            .mean()
        )
    else:
        total_df["Display_Value"] = total_df["Value"]

    # Total: straight line, no dots, visually secondary but still clear
    fig.add_trace(
        go.Scatter(
            x=total_df["period"],
            y=total_df["Display_Value"],
            mode="lines",
            name="Total",
            line=dict(
                color="rgba(17, 24, 39, 0.82)",
                width=3,
                dash="solid",
                shape="linear"
            ),
            customdata=total_df[
                [
                    "Value",
                    "Mission_Reports",
                    "Actors_Met",
                    "Activities",
                    "Records"
                ]
            ],
            hovertemplate=(
                "<b>Total</b><br>"
                + "Mission reports: %{customdata[1]}<br>"
                + "Actors met: %{customdata[2]}<br>"
                + "Activities: %{customdata[3]}<br>"
                + "Records: %{customdata[4]}"
                + "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        height=470,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=x_title,
        yaxis_title=y_title,
        legend_title_text="Region",
        hovermode="x unified",
        margin=dict(l=20, r=150, t=70, b=50),
        font=dict(color="#111827"),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(203,213,225,0.8)",
            borderwidth=1,
            font=dict(size=12)
        )
    )

    fig.update_xaxes(
        type="date",
        tickformat=tickformat,
        showgrid=False,
        tickangle=0,
        rangeslider=dict(visible=False)
    )

    fig.update_yaxes(
        rangemode="tozero",
        gridcolor="rgba(148, 163, 184, 0.25)",
        zerolinecolor="rgba(148, 163, 184, 0.45)"
    )

    return fig

def make_region_actors_temporal_line(missions_df):
    return make_region_temporal_line(
        missions_df=missions_df,
        value_col="actors_count",
        value_label="Actors met",
        title="Actors Met Over Time by Region",
        y_title="Actors Met",
        period="Y"
    )


def make_region_activities_temporal_line(missions_df):
    return make_region_temporal_line(
        missions_df=missions_df,
        value_col="activities_count",
        value_label="Activities",
        title="Activities Over Time by Region",
        y_title="Activities Conducted",
        period="Y"
    )

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
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor="white")
    return fig


def make_theme_sunburst(records_df):
    if records_df.empty:
        return None

    df = records_df.copy()
    cols = ["primary_theme", "report_record_type", "level_of_concern", "action_orientation"]

    for col in cols:
        df[col] = df[col].fillna("Unknown")

    fig = px.sunburst(
        df,
        path=[
            px.Constant("All Records"),
            "primary_theme",
            "report_record_type",
            "level_of_concern",
            "action_orientation"
        ],
        color="primary_theme",
        color_discrete_map=THEME_COLORS,
        title="Theme Drilldown"
    )

    fig.update_traces(maxdepth=2, textinfo="label+percent parent", insidetextorientation="radial")
    fig.update_layout(
        height=700,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=20),
        font=dict(color="#111827")
    )
    return fig

def make_pyvis_actor_network_html(
    missions_df,
    actors_df,
    selected_symbols=None,
    show_actor_names=False,
    max_actors_per_category=8
):
    if missions_df.empty or actors_df.empty:
        return None

    actor_df = actors_df.copy()
    mission_df = missions_df.copy()

    required_actor_cols = [
        "document_symbol",
        "mission_title",
        "actor_category",
        "actor_name"
    ]

    for col in required_actor_cols:
        if col not in actor_df.columns:
            actor_df[col] = None

    for col in ["document_symbol", "mission_title"]:
        if col not in mission_df.columns:
            mission_df[col] = None

    actor_df["document_symbol"] = (
        actor_df["document_symbol"]
        .fillna("Unknown mission")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown mission",
            "nan": "Unknown mission",
            "None": "Unknown mission"
        })
    )

    actor_df["mission_title"] = (
        actor_df["mission_title"]
        .fillna(actor_df["document_symbol"])
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown mission",
            "nan": "Unknown mission",
            "None": "Unknown mission"
        })
    )

    actor_df["actor_category"] = (
        actor_df["actor_category"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    actor_df["actor_name"] = (
        actor_df["actor_name"]
        .fillna("Unnamed actor")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unnamed actor",
            "nan": "Unnamed actor",
            "None": "Unnamed actor",
            "Unknown": "Unnamed actor"
        })
    )

    mission_df["document_symbol"] = (
        mission_df["document_symbol"]
        .fillna("Unknown mission")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown mission",
            "nan": "Unknown mission",
            "None": "Unknown mission"
        })
    )

    mission_df["mission_title"] = (
        mission_df["mission_title"]
        .fillna(mission_df["document_symbol"])
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown mission",
            "nan": "Unknown mission",
            "None": "Unknown mission"
        })
    )

    if selected_symbols:
        selected_symbols = [
            str(symbol)
            for symbol in selected_symbols
            if symbol is not None
        ]

        actor_df = actor_df[
            actor_df["document_symbol"].isin(selected_symbols)
        ].copy()

        mission_df = mission_df[
            mission_df["document_symbol"].isin(selected_symbols)
        ].copy()

    if actor_df.empty:
        return None

    def short_label(value, max_chars=34):
        value = str(value)

        if len(value) <= max_chars:
            return value

        return value[: max_chars - 1] + "…"

    def safe_html(value):
        return html.escape(str(value))

    def spread(items, top=300, bottom=-300):
        if not items:
            return {}

        if len(items) == 1:
            return {items[0]: 0}

        step = (top - bottom) / (len(items) - 1)

        return {
            item: top - i * step
            for i, item in enumerate(items)
        }

    net = Network(
        height="820px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#111827",
        directed=False,
        cdn_resources="in_line"
    )

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
              "color": "#111827",
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

    # ---------------------------------------------------------------------
    # MODE 1: Aggregate view
    # All filtered missions -> actor categories only
    # Triggered when no mission is selected in the multiselect.
    # ---------------------------------------------------------------------
    if not show_actor_names:
        category_counts = (
            actor_df
            .groupby("actor_category", dropna=False)
            .size()
            .sort_values(ascending=False)
        )

        if category_counts.empty:
            return None

        category_order = category_counts.index.tolist()
        category_y = spread(category_order, top=320, bottom=-320)

        total_actors = int(category_counts.sum())
        total_missions = int(actor_df["document_symbol"].nunique())

        max_count = max(category_counts.max(), 1)
        min_count = max(category_counts.min(), 1)

        root_title = (
            f"<b>All Filtered Missions</b><br>"
            f"Mission reports: {total_missions}<br>"
            f"Actor entries: {total_actors}<br>"
            f"Actor categories: {len(category_order)}"
        )

        net.add_node(
            "ALL_MISSIONS",
            label="All Filtered Missions",
            title=root_title,
            x=-460,
            y=0,
            size=34,
            color={
                "background": "#2563EB",
                "border": "#1D4ED8",
                "highlight": {
                    "background": "#1D4ED8",
                    "border": "#1E40AF"
                }
            },
            shape="dot"
        )

        for category in category_order:
            count = int(category_counts[category])
            color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

            # Nonlinear scaling makes differences visible without making large nodes too huge.
            normalized = count / max_count
            node_size = 14 + 42 * (normalized ** 0.55)
            edge_width = 1.2 + 9 * (normalized ** 0.65)

            # Optional: make very small categories still visible.
            node_size = max(14, min(node_size, 56))
            edge_width = max(1.2, min(edge_width, 10))

            title = (
                f"<b>{safe_html(category)}</b><br>"
                f"Actor entries: {count}<br>"
                f"Share: {count / total_actors:.1%}"
            )

            net.add_node(
                f"CATEGORY::{category}",
                label=short_label(category, 34),
                title=title,
                x=360,
                y=category_y.get(category, 0),
                size=node_size,
                color={
                    "background": color,
                    "border": color,
                    "highlight": {
                        "background": color,
                        "border": "#111827"
                    }
                },
                shape="diamond"
            )

            net.add_edge(
                "ALL_MISSIONS",
                f"CATEGORY::{category}",
                value=max(1, min(count, 18)),
                width=edge_width,
                color="rgba(100, 116, 139, 0.38)",
                title=(
                    f"<b>All Filtered Missions</b> → "
                    f"<b>{safe_html(category)}</b><br>"
                    f"Actor entries: {count}"
                )
            )

        return net.generate_html()

    # ---------------------------------------------------------------------
    # MODE 2: Selected mission drilldown
    # Selected mission(s) -> actor categories -> actor names
    # Triggered when one or more missions are selected in the multiselect.
    # ---------------------------------------------------------------------
    if not selected_symbols:
        return None

    selected_symbols = [
        str(symbol)
        for symbol in selected_symbols
        if symbol is not None
    ]

    if not selected_symbols:
        return None

    actor_df = actor_df[
        actor_df["document_symbol"].isin(selected_symbols)
    ].copy()

    mission_df = mission_df[
        mission_df["document_symbol"].isin(selected_symbols)
    ].copy()

    if actor_df.empty:
        return None

    mission_lookup = (
        mission_df
        .drop_duplicates(subset=["document_symbol"])
        .set_index("document_symbol")
        .to_dict(orient="index")
    )

    mission_order = [
        symbol
        for symbol in selected_symbols
        if symbol in actor_df["document_symbol"].unique()
    ]

    if not mission_order:
        return None

    category_counts = (
        actor_df
        .groupby("actor_category", dropna=False)
        .size()
        .sort_values(ascending=False)
    )

    if category_counts.empty:
        return None

    category_order = category_counts.index.tolist()

    mission_y = spread(mission_order, top=260, bottom=-260)
    category_y = spread(category_order, top=300, bottom=-300)

    # Mission nodes
    for mission in mission_order:
        meta = mission_lookup.get(mission, {})

        mission_title = meta.get("mission_title", mission)
        mission_country = meta.get("mission_country_or_region", "N/A")
        mission_type = meta.get("mission_type", "N/A")

        mission_actor_count = actor_df[
            actor_df["document_symbol"] == mission
        ].shape[0]

        mission_node_title = (
            f"<b>{safe_html(mission)}</b><br>"
            f"{safe_html(mission_title)}<br><br>"
            f"<b>Country/Region:</b> {safe_html(mission_country)}<br>"
            f"<b>Mission type:</b> {safe_html(mission_type)}<br>"
            f"<b>Actors met:</b> {mission_actor_count}"
        )

        net.add_node(
            f"MISSION::{mission}",
            label=short_label(mission, 30),
            title=mission_node_title,
            x=-560,
            y=mission_y.get(mission, 0),
            size=24,
            color={
                "background": "#2563EB",
                "border": "#1D4ED8",
                "highlight": {
                    "background": "#1D4ED8",
                    "border": "#1E40AF"
                }
            },
            shape="dot"
        )

    # Category nodes
    max_category_count = max(category_counts.max(), 1)

    for category in category_order:
        count = int(category_counts[category])
        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")

        title = (
            f"<b>{safe_html(category)}</b><br>"
            f"Actor entries across selected mission(s): {count}"
        )

        node_size = 14 + 20 * (count / max_category_count)

        net.add_node(
            f"CATEGORY::{category}",
            label=short_label(category, 32),
            title=title,
            x=0,
            y=category_y.get(category, 0),
            size=node_size,
            color={
                "background": color,
                "border": color,
                "highlight": {
                    "background": color,
                    "border": "#111827"
                }
            },
            shape="diamond"
        )

    # Mission -> Category edges
    mission_category_df = (
        actor_df
        .groupby(
            ["document_symbol", "actor_category"],
            dropna=False
        )
        .size()
        .reset_index(name="count")
    )

    for _, row in mission_category_df.iterrows():
        mission = row["document_symbol"]
        category = row["actor_category"]
        count = int(row["count"])

        if mission not in mission_order:
            continue

        net.add_edge(
            f"MISSION::{mission}",
            f"CATEGORY::{category}",
            value=max(1, min(count, 10)),
            width=max(1.2, min(count * 0.45, 5)),
            color="rgba(100, 116, 139, 0.35)",
            title=(
                f"<b>{safe_html(mission)}</b> → "
                f"<b>{safe_html(category)}</b><br>"
                f"Actors in category: {count}"
            )
        )

    # Actor names, limited per category
    limited_actor_rows = []

    for category in category_order:
        sub = actor_df[
            actor_df["actor_category"] == category
        ].copy()

        actor_summary = (
            sub.groupby(
                [
                    "actor_category",
                    "actor_name"
                ],
                dropna=False
            )
            .agg(
                count=("actor_name", "count"),
                missions=(
                    "document_symbol",
                    lambda x: ", ".join(
                        sorted(
                            x.dropna()
                            .astype(str)
                            .unique()
                            .tolist()
                        )
                    )
                )
            )
            .reset_index()
            .sort_values(
                ["count", "actor_name"],
                ascending=[False, True]
            )
            .head(max_actors_per_category)
        )

        limited_actor_rows.extend(
            actor_summary.to_dict(orient="records")
        )

    limited_actor_df = pd.DataFrame(limited_actor_rows)

    if limited_actor_df.empty:
        return net.generate_html()

    actor_positions = {}

    for category in category_order:
        sub = limited_actor_df[
            limited_actor_df["actor_category"] == category
        ]

        actors = sub["actor_name"].drop_duplicates().tolist()
        center_y = category_y.get(category, 0)

        if len(actors) == 1:
            offsets = [0]
        else:
            local_step = min(52, 280 / max(len(actors) - 1, 1))
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
        count = int(row["count"])
        missions_str = row.get("missions", "")

        color = ACTOR_CATEGORY_COLORS.get(category, "#94A3B8")
        coords = actor_positions.get(
            (category, actor_name),
            {
                "x": 520,
                "y": 0
            }
        )

        actor_title = (
            f"<b>{safe_html(actor_name)}</b><br>"
            f"<b>Category:</b> {safe_html(category)}<br>"
            f"<b>Entries:</b> {count}<br>"
            f"<b>Missions:</b> {safe_html(missions_str)}"
        )

        net.add_node(
            f"ACTOR::{category}::{actor_name}",
            label=short_label(actor_name, 42),
            title=actor_title,
            x=coords["x"],
            y=coords["y"],
            size=8 + min(count, 5),
            color={
                "background": color,
                "border": color,
                "highlight": {
                    "background": color,
                    "border": "#111827"
                }
            },
            shape="dot"
        )

        net.add_edge(
            f"CATEGORY::{category}",
            f"ACTOR::{category}::{actor_name}",
            width=1.2,
            color=color,
            title=(
                f"<b>{safe_html(category)}</b> → "
                f"<b>{safe_html(actor_name)}</b><br>"
                f"Entries: {count}<br>"
                f"Missions: {safe_html(missions_str)}"
            )
        )

    return net.generate_html()

def make_sankey(records_df):
    df = records_df.copy()

    if df.empty:
        return None

    cols = [
        "report_record_type",
        "primary_theme"
    ]

    for col in cols:
        if col not in df.columns:
            df[col] = "Unknown"

        df[col] = (
            df[col]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace({
                "": "Unknown",
                "nan": "Unknown",
                "None": "Unknown"
            })
        )

    grouped = (
        df.groupby(
            [
                "report_record_type",
                "primary_theme"
            ],
            dropna=False
        )
        .size()
        .reset_index(name="count")
    )

    if grouped.empty:
        return None

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
        record_type = f"Type: {row['report_record_type']}"
        theme = f"Theme: {row['primary_theme']}"

        sources.append(get_index(record_type))
        targets.append(get_index(theme))
        values.append(row["count"])

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=42,
                thickness=30,
                line=dict(
                    color="rgba(15,23,42,0.45)",
                    width=1
                ),
                label=labels,
                color="#7DD3FC"
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color="rgba(37, 99, 235, 0.12)"
            )
        )
    )

    fig.update_layout(
        title=dict(
            text="Analytical Flow: Record Type → Primary Theme",
            x=0.01,
            y=0.98,
            xanchor="left",
            yanchor="top"
        ),
        height=760,
        margin=dict(
            l=10,
            r=10,
            t=120,
            b=10
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(
            size=10,
            color="#111827"
        )
    )

    return fig

def apply_report_filters(missions_df, records_df, activities_df, actors_df):
    st.sidebar.title("Report Filters")
    st.sidebar.markdown("Explore extracted Security Council mission report findings.")

    mission_options = ["All"] + missions_df["document_symbol"].dropna().unique().tolist()
    selected_mission = st.sidebar.selectbox("Mission Report", mission_options, key="report_mission_filter")

    theme_options = ["All"] + sorted(records_df["primary_theme"].dropna().unique().tolist())
    selected_theme = st.sidebar.selectbox("Primary Theme", theme_options, key="report_theme_filter")

    concern_values = records_df["level_of_concern"].dropna().unique().tolist()
    concern_options = ["All"] + [x for x in CONCERN_ORDER if x in concern_values]
    selected_concern = st.sidebar.selectbox("Level of Concern", concern_options, key="report_concern_filter")

    record_type_options = ["All"] + sorted(records_df["report_record_type"].dropna().unique().tolist())
    selected_record_type = st.sidebar.selectbox("Record Type", record_type_options, key="report_record_type_filter")

    action_options = ["All"] + sorted(records_df["action_orientation"].dropna().unique().tolist())
    selected_action = st.sidebar.selectbox("Action Orientation", action_options, key="report_action_filter")

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
        filtered_missions = filtered_missions[filtered_missions["document_symbol"].isin(symbols_after_record_filters)]
        filtered_activities = filtered_activities[filtered_activities["document_symbol"].isin(symbols_after_record_filters)]
        filtered_actors = filtered_actors[filtered_actors["document_symbol"].isin(symbols_after_record_filters)]

    st.sidebar.markdown("---")
    st.sidebar.caption("Tip: select 'All' to include all values.")

    return filtered_missions, filtered_records, filtered_activities, filtered_actors

def _clean_region_values(df):
    df = df.copy()

    if "regions" not in df.columns:
        df["regions"] = "Unknown"

    df["regions"] = (
        df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    return df

def _explode_regions(df):
    df = _clean_region_values(df)

    df["regions"] = df["regions"].astype(str).str.split(",")
    df = df.explode("regions")

    df["regions"] = (
        df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    return df

def make_regional_average_summary(
    filtered_missions,
    filtered_records,
    filtered_activities,
    filtered_actors
):
    missions = _clean_region_values(filtered_missions)

    region_lookup = (
        missions[["document_symbol", "regions"]]
        .dropna(subset=["document_symbol"])
        .drop_duplicates()
    )

    records = filtered_records.merge(region_lookup, on="document_symbol", how="left")
    activities = filtered_activities.merge(region_lookup, on="document_symbol", how="left")
    actors = filtered_actors.merge(region_lookup, on="document_symbol", how="left")

    records = _clean_region_values(records)
    activities = _clean_region_values(activities)
    actors = _clean_region_values(actors)

    mission_summary = (
        missions
        .groupby("regions", dropna=False)
        .agg(Mission_Reports=("document_symbol", "nunique"))
        .reset_index()
    )

    record_totals = (
        records
        .groupby("regions", dropna=False)
        .agg(
            Total_Records=("record_id", "count"),
            Unique_Verbs=("verb", lambda x: x.dropna().nunique()),
            Total_Verb_Count=("verb", lambda x: x.dropna().shape[0]),
            Unique_Primary_Themes=("primary_theme", lambda x: x.dropna().nunique())
        )
        .reset_index()
    )

    activity_totals = (
        activities
        .groupby("regions", dropna=False)
        .agg(Total_Activities=("activity_id", "count"))
        .reset_index()
    )

    actor_totals = (
        actors
        .groupby("regions", dropna=False)
        .agg(
            Total_Actors=("actor_id", "count"),
            Unique_Actor_Categories=("actor_category", lambda x: x.dropna().nunique())
        )
        .reset_index()
    )

    records_per_mission = (
        records
        .groupby(["regions", "document_symbol"], dropna=False)
        .agg(Records=("record_id", "count"))
        .reset_index()
    )

    themes_per_mission = (
        records
        .dropna(subset=["primary_theme"])
        .groupby(["regions", "document_symbol"], dropna=False)
        .agg(Theme_Count=("primary_theme", "nunique"))
        .reset_index()
    )

    verbs_per_mission = (
        records
        .dropna(subset=["verb"])
        .groupby(["regions", "document_symbol"], dropna=False)
        .agg(Verb_Count=("verb", "count"))
        .reset_index()
    )

    unique_verbs_per_mission = (
        records
        .dropna(subset=["verb"])
        .groupby(["regions", "document_symbol"], dropna=False)
        .agg(Unique_Verb_Count=("verb", "nunique"))
        .reset_index()
    )

    actor_categories_per_mission = (
        actors
        .dropna(subset=["actor_category"])
        .groupby(["regions", "document_symbol"], dropna=False)
        .agg(Actor_Category_Count=("actor_category", "nunique"))
        .reset_index()
    )

    avg_records = (
        records_per_mission
        .groupby("regions", dropna=False)
        .agg(Avg_Records_Per_Mission=("Records", "mean"))
        .reset_index()
    )

    avg_themes = (
        themes_per_mission
        .groupby("regions", dropna=False)
        .agg(Avg_Theme_Count_Per_Mission=("Theme_Count", "mean"))
        .reset_index()
    )

    avg_verbs = (
        verbs_per_mission
        .groupby("regions", dropna=False)
        .agg(Avg_Verb_Count_Per_Mission=("Verb_Count", "mean"))
        .reset_index()
    )

    avg_unique_verbs = (
        unique_verbs_per_mission
        .groupby("regions", dropna=False)
        .agg(Avg_Unique_Verbs_Per_Mission=("Unique_Verb_Count", "mean"))
        .reset_index()
    )

    avg_actor_categories = (
        actor_categories_per_mission
        .groupby("regions", dropna=False)
        .agg(Avg_Actor_Categories_Met_Per_Mission=("Actor_Category_Count", "mean"))
        .reset_index()
    )

    summary = mission_summary.copy()

    for df in [
        record_totals,
        activity_totals,
        actor_totals,
        avg_records,
        avg_themes,
        avg_verbs,
        avg_unique_verbs,
        avg_actor_categories
    ]:
        summary = summary.merge(df, on="regions", how="left")

    numeric_cols = [col for col in summary.columns if col != "regions"]
    summary[numeric_cols] = summary[numeric_cols].fillna(0)

    average_cols = [
        "Avg_Records_Per_Mission",
        "Avg_Theme_Count_Per_Mission",
        "Avg_Verb_Count_Per_Mission",
        "Avg_Unique_Verbs_Per_Mission",
        "Avg_Actor_Categories_Met_Per_Mission"
    ]

    for col in average_cols:
        if col in summary.columns:
            summary[col] = summary[col].round(2)

    return summary, records, activities, actors


def make_theme_prevalence_region_heatmap(missions_df):
    missions = missions_df.copy()

    if missions.empty:
        return None

    required_cols = ["document_symbol", "regions", "main_themes"]

    for col in required_cols:
        if col not in missions.columns:
            return None

    missions = _explode_regions(missions)

    missions["main_themes"] = missions["main_themes"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # Denominator: number of unique missions in each region
    region_totals = (
        missions
        .dropna(subset=["document_symbol"])
        .drop_duplicates(subset=["regions", "document_symbol"])
        .groupby("regions", dropna=False)
        .agg(Regional_Missions=("document_symbol", "nunique"))
        .reset_index()
    )

    if region_totals.empty:
        return None

    theme_df = missions[
        [
            "document_symbol",
            "regions",
            "main_themes"
        ]
    ].copy()

    theme_df = theme_df.explode("main_themes")

    theme_df["main_themes"] = (
        theme_df["main_themes"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    theme_df = theme_df.drop_duplicates(
        subset=[
            "regions",
            "document_symbol",
            "main_themes"
        ]
    )

    prevalence_df = (
        theme_df
        .groupby(["main_themes", "regions"], dropna=False)
        .agg(Missions_With_Theme=("document_symbol", "nunique"))
        .reset_index()
        .merge(region_totals, on="regions", how="left")
    )

    prevalence_df["Prevalence"] = (
        prevalence_df["Missions_With_Theme"]
        / prevalence_df["Regional_Missions"]
        * 100
    )

    prevalence_df["Prevalence"] = prevalence_df["Prevalence"].round(1)

    if prevalence_df.empty:
        return None

    heatmap_matrix = (
        prevalence_df
        .pivot(
            index="main_themes",
            columns="regions",
            values="Prevalence"
        )
        .fillna(0)
    )

    # Sort themes by average prevalence so the most relevant themes appear higher
    heatmap_matrix = heatmap_matrix.loc[
        heatmap_matrix.mean(axis=1).sort_values(ascending=False).index
    ]

    fig = px.imshow(
        heatmap_matrix,
        text_auto=".1f",
        color_continuous_scale="Blues",
        aspect="auto",
        title="Theme Prevalence by Region"
    )

    fig.update_traces(
        hovertemplate=(
            "<b>Theme:</b> %{y}<br>"
            "<b>Region:</b> %{x}<br>"
            "<b>Missions with theme:</b> %{z:.1f}%"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=max(500, 32 * len(heatmap_matrix.index)),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title=None,
        coloraxis_colorbar=dict(
            title="% of missions"
        ),
        margin=dict(l=20, r=20, t=70, b=70),
        font=dict(color="#111827")
    )

    fig.update_xaxes(tickangle=-35)

    return fig

def make_mission_type_composition_region_chart(missions_df):
    missions = missions_df.copy()

    if missions.empty:
        return None

    required_cols = [
        "document_symbol",
        "regions",
        "mission_type"
    ]

    for col in required_cols:
        if col not in missions.columns:
            return None

    missions = _explode_regions(missions)

    missions["mission_type"] = (
        missions["mission_type"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    chart_df = (
        missions
        .drop_duplicates(
            subset=[
                "regions",
                "document_symbol",
                "mission_type"
            ]
        )
        .groupby(
            ["regions", "mission_type"],
            dropna=False
        )
        .agg(Missions=("document_symbol", "nunique"))
        .reset_index()
    )

    if chart_df.empty:
        return None

    chart_df["Pct"] = (
        chart_df["Missions"]
        / chart_df.groupby("regions")["Missions"].transform("sum")
        * 100
    )

    region_order = (
        chart_df
        .groupby("regions")["Missions"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    fig = px.bar(
        chart_df,
        x="regions",
        y="Pct",
        color="mission_type",
        barmode="stack",
        title="Mission Type Composition by Region",
        category_orders={
            "regions": region_order
        },
        custom_data=[
            "mission_type",
            "Missions",
            "Pct"
        ]
    )

    fig.update_traces(
        texttemplate="%{y:.0f}%",
        textposition="inside",
        insidetextfont=dict(size=10),
        showlegend=False,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Region: %{x}<br>"
            "Mission reports: %{customdata[1]}<br>"
            "Share of regional missions: %{customdata.1f}%"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="% of Mission Reports",
        margin=dict(l=20, r=20, t=60, b=70),
        hovermode="closest",
        legend_title_text="Mission Type",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        font=dict(color="#111827")
    )

    fig.update_yaxes(
        range=[0, 100],
        ticksuffix="%",
        gridcolor="rgba(148,163,184,0.25)",
        zerolinecolor="rgba(148,163,184,0.45)"
    )

    fig.update_xaxes(
        tickangle=-25,
        showgrid=False
    )

    return fig

def make_avg_themes_region_chart(summary):
    df = summary.sort_values("Avg_Theme_Count_Per_Mission", ascending=True)

    fig = px.bar(
        df,
        x="regions",
        y="Avg_Theme_Count_Per_Mission",
        text="Avg_Theme_Count_Per_Mission",
        color="regions",
        color_discrete_map=REGION_COLORS,
        title="Average Theme Count per Mission by Region",
        hover_data={
            "Mission_Reports": True,
            "Unique_Primary_Themes": True,
            "Avg_Theme_Count_Per_Mission": ":.2f"
        }
    )

    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside"
    )

    fig.update_layout(
        height=450,
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Average unique primary themes per mission",
        margin=dict(l=20, r=20, t=60, b=80)
    )

    fig.update_xaxes(tickangle=-35)

    return fig

def make_avg_verbs_region_chart(summary):
    df = summary.sort_values("Avg_Verb_Count_Per_Mission", ascending=False)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["regions"],
            y=df["Avg_Verb_Count_Per_Mission"],
            mode="markers+lines+text",
            text=df["Avg_Verb_Count_Per_Mission"].round(2),
            textposition="top center",
            marker=dict(
                size=df["Avg_Verb_Count_Per_Mission"].clip(lower=1) * 4,
                color=df["Avg_Verb_Count_Per_Mission"],
                colorscale="Viridis",
                line=dict(color="white", width=2),
                opacity=0.9
            ),
            line=dict(
                color="rgba(37, 99, 235, 0.35)",
                width=3,
                shape="spline"
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Average verb count per mission: %{y:.2f}<br>"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Average Verb Count per Mission by Region",
        height=450,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Average verb count per mission",
        margin=dict(l=20, r=20, t=60, b=80)
    )

    fig.update_xaxes(tickangle=-35, showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.25)")

    return fig

def make_region_actor_flow(actors):

    actor_df = actors.copy()

    if actor_df.empty:
        return None

    for col in ["regions", "actor_category"]:
        if col not in actor_df.columns:
            actor_df[col] = "Unknown"

    actor_df["regions"] = (
        actor_df["regions"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    actor_df["actor_category"] = (
        actor_df["actor_category"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    flow_df = (
        actor_df
        .groupby(["regions", "actor_category"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    if flow_df.empty:
        return None

    region_totals = (
        flow_df
        .groupby("regions")["count"]
        .sum()
        .sort_values(ascending=False)
    )

    actor_totals = (
        flow_df
        .groupby("actor_category")["count"]
        .sum()
        .sort_values(ascending=False)
    )

    regions = region_totals.index.tolist()
    actor_categories = actor_totals.index.tolist()

    max_rows = max(len(regions), len(actor_categories), 1)

    def centered_positions(items):
        if len(items) == 1:
            return {items[0]: 0}

        start = (len(items) - 1) / 2
        return {
            item: start - i
            for i, item in enumerate(items)
        }

    region_y = centered_positions(regions)
    actor_y = centered_positions(actor_categories)

    pos = {}

    for region in regions:
        pos[f"REGION::{region}"] = (0, region_y[region])

    for category in actor_categories:
        pos[f"ACTOR::{category}"] = (1.35, actor_y[category])

    max_count = flow_df["count"].max()

    fig = go.Figure()

    for _, row in flow_df.iterrows():
        region = row["regions"]
        category = row["actor_category"]
        count = row["count"]

        x0, y0 = pos[f"REGION::{region}"]
        x1, y1 = pos[f"ACTOR::{category}"]

        region_color = REGION_COLORS.get(region, "#2563EB")
        actor_color = ACTOR_CATEGORY_COLORS.get(category, "#A855F7")

        width = 1.2 + 7 * (count / max_count)

        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(
                    width=width,
                    color="rgba(100,116,139,0.24)",
                    shape="spline"
                ),
                hoverinfo="text",
                text=(
                    f"<b>{region}</b> → <b>{category}</b><br>"
                    f"Actors: {count}"
                ),
                showlegend=False
            )
        )

        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(
                    width=max(1, width * 0.35),
                    color=actor_color,
                    shape="spline"
                ),
                opacity=0.22,
                hoverinfo="skip",
                showlegend=False
            )
        )

    node_x = []
    node_y = []
    node_text = []
    node_size = []
    node_color = []
    node_border = []
    node_hover = []

    for region in regions:
        x, y = pos[f"REGION::{region}"]
        total = int(region_totals[region])

        node_x.append(x)
        node_y.append(y)
        node_text.append(region)
        node_size.append(24 + min(total, 80) * 0.35)
        node_color.append(REGION_COLORS.get(region, "#2563EB"))
        node_border.append("#1E3A8A")
        node_hover.append(
            f"<b>{region}</b><br>"
            f"Total actor-category links: {total}"
        )

    for category in actor_categories:
        x, y = pos[f"ACTOR::{category}"]
        total = int(actor_totals[category])

        node_x.append(x)
        node_y.append(y)
        node_text.append(category)
        node_size.append(22 + min(total, 80) * 0.35)
        node_color.append(ACTOR_CATEGORY_COLORS.get(category, "#A855F7"))
        node_border.append("#4C1D95")
        node_hover.append(
            f"<b>{category}</b><br>"
            f"Actors across regions: {total}"
        )

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition=[
                "middle left" if x > 0 else "middle right"
                for x in node_x
            ],
            hoverinfo="text",
            hovertext=node_hover,
            marker=dict(
                size=node_size,
                color=node_color,
                line=dict(
                    color=node_border,
                    width=2
                ),
                opacity=0.95
            ),
            textfont=dict(
                size=12,
                color="#111827"
            ),
            showlegend=False
        )
    )

    fig.add_annotation(
        x=0,
        y=max(region_y.values()) + 0.8 if region_y else 0.8,
        text="<b>Regions</b>",
        showarrow=False,
        font=dict(size=14, color="#1F2937")
    )

    fig.add_annotation(
        x=1.35,
        y=max(actor_y.values()) + 0.8 if actor_y else 0.8,
        text="<b>Actor Categories</b>",
        showarrow=False,
        font=dict(size=14, color="#1F2937")
    )

    fig.update_layout(
        title="Regional Actor Engagement Network",
        height=max(620, 70 * max_rows),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_color="#111827"
        ),
        xaxis=dict(
            visible=False,
            range=[-0.35, 1.75],
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            visible=False,
            showgrid=False,
            zeroline=False
        ),
        margin=dict(l=30, r=30, t=70, b=30)
    )

    return fig

def make_region_theme_lollipop(records_df, selected_theme):

    df = records_df.copy()

    if df.empty:
        return None

    if selected_theme != "All Themes":
        df = df[df["primary_theme"] == selected_theme]

    if df.empty:
        return None

    per_mission = (
        df.groupby(
            ["regions", "document_symbol"],
            dropna=False
        )
        .size()
        .reset_index(name="records")
    )

    region_avg = (
        per_mission
        .groupby("regions")
        .agg(
            Avg_Records=("records", "mean"),
            Missions=("document_symbol", "nunique")
        )
        .reset_index()
        .sort_values("Avg_Records")
    )

    if region_avg.empty:
        return None

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=region_avg["Avg_Records"],
            y=region_avg["regions"],
            mode="markers",
            marker=dict(
                size=22,
                color=[
                    REGION_COLORS.get(r, "#2563EB")
                    for r in region_avg["regions"]
                ],
                line=dict(
                    color="white",
                    width=2
                )
            ),
            customdata=region_avg["Missions"],
            hovertemplate=
            "<b>%{y}</b><br>"
            "Avg Records/Mission: %{x:.2f}<br>"
            "Mission Reports: %{customdata}<br>"
            "<extra></extra>"
        )
    )

    for _, row in region_avg.iterrows():

        fig.add_shape(
            type="line",
            x0=0,
            x1=row["Avg_Records"],
            y0=row["regions"],
            y1=row["regions"],
            line=dict(
                color="rgba(148,163,184,0.45)",
                width=3
            )
        )

    fig.update_layout(
        title=f"Average Records per Mission by Region<br><sup>{selected_theme}</sup>",
        height=650,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        margin=dict(l=20, r=20, t=80, b=20),
        xaxis_title="Average Records per Mission",
        yaxis_title=None
    )

    return fig

def render_region_comparison(
    filtered_missions,
    filtered_records,
    filtered_activities,
    filtered_actors
):
    st.markdown("### Regional Comparison")
    st.caption(
        "Regional metrics are normalized as averages per mission report, making regions easier to compare even when report volumes differ."
    )

    summary, records, activities, actors = make_regional_average_summary(
        filtered_missions,
        filtered_records,
        filtered_activities,
        filtered_actors
    )

    if summary.empty:
        st.info("No regional data available for the current filters.")
        return

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        metric_card(
            "Avg Records / Mission",
            f"{summary['Avg_Records_Per_Mission'].mean():.2f}"
        )

    with k2:
        metric_card(
            "Avg Themes / Mission",
            f"{summary['Avg_Theme_Count_Per_Mission'].mean():.2f}"
        )

    with k3:
        metric_card(
            "Avg Actor Categories",
            f"{summary['Avg_Actor_Categories_Met_Per_Mission'].mean():.2f}"
        )

    with k4:
        metric_card(
            "Avg Verb Count",
            f"{summary['Avg_Verb_Count_Per_Mission'].mean():.2f}"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        fig = make_theme_prevalence_region_heatmap(filtered_missions)

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="regional_theme_prevalence"
            )
        else:
            st.info("No mission-level theme prevalence data available for the current filters.")

    with c2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        fig = make_avg_themes_region_chart(summary)
        st.plotly_chart(fig, use_container_width=True, key="regional_avg_themes")

    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        fig = make_region_actor_flow(actors)

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="regional_actor_flow_redesigned"
            )
        else:
            st.info("No actor engagement data available for the current filters.")

    with c4:

        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        theme_options = (
                ["All Themes"]
                + sorted(
            records["primary_theme"]
            .dropna()
            .unique()
            .tolist()
        )
        )

        selected_theme = st.selectbox(
            "Theme",
            theme_options,
            key="regional_theme_filter"
        )

        fig = make_region_theme_lollipop(
            records,
            selected_theme
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="regional_theme_lollipop"
            )
        else:
            st.info("No theme data available.")


    c5, c6 = st.columns(2)

    with c5:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        activity_type_df = (
            activities
            .groupby(["regions", "activity_type"], dropna=False)
            .size()
            .reset_index(name="count")
        )

        if not activity_type_df.empty:
            activity_matrix = (
                activity_type_df
                .pivot(index="activity_type", columns="regions", values="count")
                .fillna(0)
            )

            fig = px.imshow(
                activity_matrix,
                text_auto=True,
                color_continuous_scale="Blues",
                aspect="auto",
                title="Activity Types by Region"
            )

            fig.update_layout(
                height=500,
                paper_bgcolor="white",
                margin=dict(l=20, r=20, t=60, b=20)
            )

            st.plotly_chart(fig, use_container_width=True, key="regional_activity_heatmap")
        else:
            st.info("No activity-type data available for the current filters.")


    with c6:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        fig = make_mission_type_composition_region_chart(
            filtered_missions
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="regional_mission_type_composition"
            )
        else:
            st.info("No mission-type data available for the current filters.")

    display_summary = summary.rename(columns={
        "regions": "Region",
        "Mission_Reports": "Mission Reports",
        "Total_Records": "Total Records",
        "Total_Activities": "Total Activities",
        "Total_Actors": "Total Actors",
        "Unique_Primary_Themes": "Unique Primary Themes",
        "Unique_Verbs": "Unique Verbs",
        "Unique_Actor_Categories": "Unique Actor Categories",
        "Avg_Records_Per_Mission": "Avg Records / Mission",
        "Avg_Theme_Count_Per_Mission": "Avg Themes / Mission",
        "Avg_Actor_Categories_Met_Per_Mission": "Avg Actor Categories / Mission",
        "Avg_Verb_Count_Per_Mission": "Avg Verb Count / Mission",
        "Avg_Unique_Verbs_Per_Mission": "Avg Unique Verbs / Mission",
        "Total_Verb_Count": "Total Verb Count"
    })

    preferred_cols = [
        "Region",
        "Mission Reports",
        "Total Records",
        "Avg Records / Mission",
        "Unique Primary Themes",
        "Avg Themes / Mission",
        "Total Actors",
        "Unique Actor Categories",
        "Avg Actor Categories / Mission",
        "Total Verb Count",
        "Unique Verbs",
        "Avg Verb Count / Mission",
        "Avg Unique Verbs / Mission",
        "Total Activities"
    ]

    preferred_cols = [col for col in preferred_cols if col in display_summary.columns]

    st.dataframe(
        display_summary[preferred_cols],
        use_container_width=True,
        hide_index=True
    )

def render_mission_card(row):
    title = row.get("mission_title") or "Untitled mission"
    doc_symbol = row.get("document_symbol") or ""
    country_region = row.get("mission_country_or_region") or ""
    mission_type = row.get("mission_type") or ""

    st.markdown(
        f"""
        <div class="mission-hero">
            <h2>{title}</h2>
            <p>
                <b>{doc_symbol}</b> &nbsp; | &nbsp;
                {country_region} &nbsp; | &nbsp;
                {mission_type}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Records", str(int(row.get("records_count", 0))))
    with c2:
        metric_card("Activities", str(int(row.get("activities_count", 0))))
    with c3:
        metric_card("Actors Met", str(int(row.get("actors_count", 0))))
    with c4:
        metric_card("Field Exposure", str(row.get("field_exposure") or "N/A"))

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

def get_mission_display_name(symbol, missions_df):
    if not symbol or missions_df.empty:
        return str(symbol or "Unknown mission")

    row_df = missions_df[missions_df["document_symbol"] == symbol]

    if row_df.empty:
        return str(symbol)

    row = row_df.iloc[0]
    title = row.get("mission_title") or "Untitled mission"
    doc_symbol = row.get("document_symbol") or symbol

    return f"{title} ({doc_symbol})"

def add_mission_display_names(mission_a, mission_b):
    mission_a["display_name"] = get_mission_display_from_meta(mission_a)
    mission_b["display_name"] = get_mission_display_from_meta(mission_b)
    return mission_a, mission_b

def get_mission_display_from_meta(mission):
    meta = mission.get("meta")

    if meta is None or meta.empty:
        return str(mission.get("symbol", "Unknown mission"))

    row = meta.iloc[0]
    title = row.get("mission_title") or "Untitled mission"
    symbol = row.get("document_symbol") or mission.get("symbol", "")

    return f"{title} ({symbol})"

def get_comparison_mission_data(
    selected_symbol,
    missions_df,
    records_df,
    activities_df,
    actors_df
):
    mission_meta = missions_df[
        missions_df["document_symbol"] == selected_symbol
    ].copy()

    mission_records = records_df[
        records_df["document_symbol"] == selected_symbol
    ].copy()

    mission_activities = activities_df[
        activities_df["document_symbol"] == selected_symbol
    ].copy()

    mission_actors = actors_df[
        actors_df["document_symbol"] == selected_symbol
    ].copy()

    return {
        "symbol": selected_symbol,
        "meta": mission_meta,
        "records": mission_records,
        "activities": mission_activities,
        "actors": mission_actors,
    }

def make_two_mission_metric_bar(mission_a, mission_b):
    rows = [
        {
            "Mission": mission_a["symbol"],
            "Records": len(mission_a["records"]),
            "Activities": len(mission_a["activities"]),
            "Actors Met": len(mission_a["actors"]),
        },
        {
            "Mission": mission_b["symbol"],
            "Records": len(mission_b["records"]),
            "Activities": len(mission_b["activities"]),
            "Actors Met": len(mission_b["actors"]),
        },
    ]

    df = pd.DataFrame(rows)

    long_df = df.melt(
        id_vars="Mission",
        value_vars=["Records", "Activities", "Actors Met"],
        var_name="Metric",
        value_name="Count"
    )

    fig = px.bar(
        long_df,
        x="Metric",
        y="Count",
        color="Mission",
        barmode="group",
        text="Count",
        title="Mission Volume Comparison"
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Count",
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig

def make_two_mission_concern_comparison(mission_a, mission_b):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    df_a["Mission"] = mission_a["symbol"]
    df_b["Mission"] = mission_b["symbol"]

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["level_of_concern"] = df["level_of_concern"].fillna("Unknown")

    chart_df = (
        df.groupby(["Mission", "level_of_concern"])
        .size()
        .reset_index(name="Records")
    )

    order = [x for x in CONCERN_ORDER if x in chart_df["level_of_concern"].tolist()]
    extra = [x for x in chart_df["level_of_concern"].tolist() if x not in order]
    order = order + extra

    chart_df["level_of_concern"] = pd.Categorical(
        chart_df["level_of_concern"],
        categories=order,
        ordered=True
    )

    chart_df = chart_df.sort_values("level_of_concern")

    fig = px.bar(
        chart_df,
        x="level_of_concern",
        y="Records",
        color="Mission",
        barmode="group",
        text="Records",
        title="Level of Concern Compared"
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Records",
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig

def make_two_mission_verb_comparison(mission_a, mission_b, top_n=15):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["verb"] = (
        df["verb"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    chart_df = (
        df.groupby(["Mission", "verb"])
        .size()
        .reset_index(name="Records")
    )

    top_verbs = (
        chart_df
        .groupby("verb")["Records"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index
        .tolist()
    )

    chart_df = chart_df[
        chart_df["verb"].isin(top_verbs)
    ]

    fig = px.bar(
        chart_df,
        y="verb",
        x="Records",
        color="Mission",
        barmode="group",
        orientation="h",
        text="Records",
        title="Most Common Verbs Compared"
    )

    fig.update_layout(
        height=500,
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis_title=None,
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig

def make_two_mission_theme_radar(mission_a, mission_b):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["primary_theme"] = (
        df["primary_theme"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    chart_df = (
        df.groupby(["Mission", "primary_theme"], dropna=False)
        .size()
        .reset_index(name="Records")
    )

    if chart_df.empty:
        return None

    theme_order = (
        chart_df
        .groupby("primary_theme")["Records"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    # Ensure both missions have every theme so the radar shapes are comparable.
    full_index = pd.MultiIndex.from_product(
        [
            [mission_a_label, mission_b_label],
            theme_order
        ],
        names=["Mission", "primary_theme"]
    )

    chart_df = (
        chart_df
        .set_index(["Mission", "primary_theme"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    # Close the radar loop by repeating the first theme at the end for each mission.
    closed_rows = []

    for mission_label in [mission_a_label, mission_b_label]:
        sub = chart_df[chart_df["Mission"] == mission_label].copy()

        if not sub.empty:
            closed_rows.append(sub)
            closed_rows.append(sub.iloc[[0]])

    radar_df = pd.concat(closed_rows, ignore_index=True)

    colors = {
        mission_a_label: "#2563EB",
        mission_b_label: "#F97316"
    }

    fig = go.Figure()

    for mission_label in [mission_a_label, mission_b_label]:
        sub = radar_df[radar_df["Mission"] == mission_label]

        fig.add_trace(
            go.Scatterpolar(
                r=sub["Records"],
                theta=sub["primary_theme"],
                fill="toself",
                name=mission_label,
                line=dict(
                    color=colors.get(mission_label, "#64748B"),
                    width=3
                ),
                fillcolor=(
                    "rgba(37, 99, 235, 0.18)"
                    if mission_label == mission_a_label
                    else "rgba(249, 115, 22, 0.18)"
                ),
                marker=dict(size=6),
                hovertemplate=(
                    f"<b>{mission_label}</b><br>"
                    "Theme: %{theta}<br>"
                    "Records: %{r}"
                    "<extra></extra>"
                )
            )
        )

    max_value = max(chart_df["Records"].max(), 1)

    fig.update_layout(
        title="Theme Profile Radar",
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        polar=dict(
            bgcolor="white",
            radialaxis=dict(
                visible=True,
                range=[0, max_value + max(1, max_value * 0.15)],
                gridcolor="rgba(148, 163, 184, 0.25)",
                linecolor="rgba(148, 163, 184, 0.35)"
            ),
            angularaxis=dict(
                gridcolor="rgba(148, 163, 184, 0.25)",
                linecolor="rgba(148, 163, 184, 0.35)"
            )
        ),
        showlegend=False,
        margin=dict(l=30, r=30, t=70, b=30),
        font=dict(color="#111827")
    )

    return fig

def make_two_mission_record_type_dumbbell(
    mission_a,
    mission_b,
    top_n=12
):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    mission_a_label = mission_a.get(
        "display_name",
        mission_a["symbol"]
    )

    mission_b_label = mission_b.get(
        "display_name",
        mission_b["symbol"]
    )

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat(
        [df_a, df_b],
        ignore_index=True
    )

    if df.empty:
        return None

    df["report_record_type"] = (
        df["report_record_type"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    chart_df = (
        df.groupby(
            [
                "report_record_type",
                "Mission"
            ],
            dropna=False
        )
        .size()
        .reset_index(name="Records")
    )

    if chart_df.empty:
        return None

    pivot_df = (
        chart_df
        .pivot_table(
            index="report_record_type",
            columns="Mission",
            values="Records",
            fill_value=0
        )
        .reset_index()
    )

    for mission_label in [
        mission_a_label,
        mission_b_label
    ]:
        if mission_label not in pivot_df.columns:
            pivot_df[mission_label] = 0

    pivot_df["Difference"] = (
        pivot_df[mission_b_label]
        - pivot_df[mission_a_label]
    ).abs()

    pivot_df["Total"] = (
        pivot_df[mission_a_label]
        + pivot_df[mission_b_label]
    )

    pivot_df = (
        pivot_df
        .sort_values(
            ["Difference", "Total"],
            ascending=[False, False]
        )
        .head(top_n)
        .sort_values("Total")
    )

    fig = go.Figure()

    for _, row in pivot_df.iterrows():
        fig.add_shape(
            type="line",
            x0=row[mission_a_label],
            x1=row[mission_b_label],
            y0=row["report_record_type"],
            y1=row["report_record_type"],
            line=dict(
                color="rgba(148,163,184,0.55)",
                width=3
            ),
            layer="below"
        )

    fig.add_trace(
        go.Scatter(
            x=pivot_df[mission_a_label],
            y=pivot_df["report_record_type"],
            mode="markers+text",
            text=pivot_df[mission_a_label],
            textposition="middle left",
            marker=dict(
                size=16,
                color="#2563EB",
                line=dict(
                    color="white",
                    width=2
                )
            ),
            name=mission_a_label,
            hovertemplate=(
                f"<b>{mission_a_label}</b><br>"
                "Record Type: %{y}<br>"
                "Records: %{x}"
                "<extra></extra>"
            )
        )
    )

    fig.add_trace(
        go.Scatter(
            x=pivot_df[mission_b_label],
            y=pivot_df["report_record_type"],
            mode="markers+text",
            text=pivot_df[mission_b_label],
            textposition="middle right",
            marker=dict(
                size=16,
                color="#F97316",
                line=dict(
                    color="white",
                    width=2
                )
            ),
            name=mission_b_label,
            hovertemplate=(
                f"<b>{mission_b_label}</b><br>"
                "Record Type: %{y}<br>"
                "Records: %{x}"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Record Type Difference",
        height=max(
            520,
            45 * len(pivot_df)
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        xaxis_title="Records",
        yaxis_title=None,
        margin=dict(
            l=20,
            r=20,
            t=70,
            b=30
        )
    )

    return fig

def make_two_mission_action_comparison(mission_a, mission_b):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    df_a["Mission"] = mission_a["symbol"]
    df_b["Mission"] = mission_b["symbol"]

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["action_orientation"] = df["action_orientation"].fillna("Unknown")

    chart_df = (
        df.groupby(["Mission", "action_orientation"])
        .size()
        .reset_index(name="Records")
    )

    fig = px.bar(
        chart_df,
        x="Records",
        y="action_orientation",
        color="Mission",
        barmode="group",
        orientation="h",
        text="Records",
        title="Action Orientation Compared"
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="Records",
        yaxis_title=None,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig

def make_single_mission_record_theme_heatmap(
    mission,
    colorscale="Blues",
    cmax=None
):
    df = mission["records"].copy()

    if df.empty:
        return None

    df["report_record_type"] = (
        df["report_record_type"]
        .fillna("Unknown")
        .astype(str)
    )

    df["primary_theme"] = (
        df["primary_theme"]
        .fillna("Unknown")
        .astype(str)
    )

    matrix = (
        df.groupby(
            [
                "report_record_type",
                "primary_theme"
            ],
            dropna=False
        )
        .size()
        .reset_index(name="Records")
        .pivot(
            index="report_record_type",
            columns="primary_theme",
            values="Records"
        )
        .fillna(0)
    )

    if matrix.empty:
        return None

    fig = px.imshow(
        matrix,
        text_auto=True,
        aspect="auto",
        color_continuous_scale=colorscale,
        title=mission.get(
            "display_name",
            mission["symbol"]
        )
    )

    if cmax is not None:
        fig.update_coloraxes(
            cmin=0,
            cmax=cmax
        )

    fig.update_layout(
        height=max(
            420,
            45 * len(matrix.index)
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        coloraxis_showscale=False,
        margin=dict(
            l=20,
            r=20,
            t=70,
            b=20
        )
    )

    fig.update_xaxes(
        tickangle=-35
    )

    return fig

def make_two_mission_action_flow_sankey(mission_a, mission_b):

    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    for col in [
        "Mission",
        "action_orientation",
        "primary_theme",
        "level_of_concern"
    ]:
        df[col] = df[col].fillna("Unknown")

    labels = []
    index_map = {}

    def get_idx(label):
        if label not in index_map:
            index_map[label] = len(labels)
            labels.append(label)
        return index_map[label]

    source = []
    target = []
    value = []

    grouped = (
        df.groupby(
            [
                "Mission",
                "action_orientation",
                "primary_theme",
                "level_of_concern"
            ]
        )
        .size()
        .reset_index(name="count")
    )

    for _, row in grouped.iterrows():

        mission = f"Mission: {row['Mission']}"
        action = f"Action: {row['action_orientation']}"
        theme = f"Theme: {row['primary_theme']}"
        concern = f"Concern: {row['level_of_concern']}"

        source.append(get_idx(mission))
        target.append(get_idx(action))
        value.append(row["count"])

        source.append(get_idx(action))
        target.append(get_idx(theme))
        value.append(row["count"])

        source.append(get_idx(theme))
        target.append(get_idx(concern))
        value.append(row["count"])

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=28,
                line=dict(color="white", width=1),
                label=labels,
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
            )
        )
    )

    fig.update_layout(
        title="Action → Theme → Concern Flow",
        height=600,
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=60, b=10)
    )

    return fig

def make_two_mission_actor_category_comparison(mission_a, mission_b):
    df_a = mission_a["actors"].copy()
    df_b = mission_b["actors"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["actor_category"] = (
        df["actor_category"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    df["actor_name"] = (
        df["actor_name"]
        .fillna("Unnamed actor")
        .astype(str)
        .str.strip()
        .replace({"": "Unnamed actor", "nan": "Unnamed actor", "None": "Unnamed actor"})
    )

    chart_df = (
        df.groupby(
            ["Mission", "actor_category", "actor_name"],
            dropna=False
        )
        .size()
        .reset_index(name="Meetings")
    )

    if chart_df.empty:
        return None

    fig = px.treemap(
        chart_df,
        path=[
            "Mission",
            "actor_category",
            "actor_name"
        ],
        values="Meetings",
        color="actor_category",
        color_discrete_map=ACTOR_CATEGORY_COLORS,
        title="Actors Met by Category and Mission",
        custom_data=[
            "Mission",
            "actor_category",
            "actor_name",
            "Meetings"
        ]
    )

    fig.update_traces(
        textinfo="label+value",
        hovertemplate=(
            "<b>%{customdata[2]}</b><br>"
            "Mission: %{customdata[0]}<br>"
            "Actor category: %{customdata[1]}<br>"
            "Meetings / mentions: %{customdata[3]}"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=560,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=70, b=10),
        font=dict(color="#111827")
    )

    return fig


def make_two_mission_activity_type_comparison(mission_a, mission_b):
    df_a = mission_a["activities"].copy()
    df_b = mission_b["activities"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["activity_type"] = (
        df["activity_type"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    chart_df = (
        df.groupby(["Mission", "activity_type"], dropna=False)
        .size()
        .reset_index(name="Activities")
    )

    activity_order = (
        chart_df
        .groupby("activity_type")["Activities"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    fallback_palette = px.colors.qualitative.Set3
    updated_activity_colors = ACTIVITY_TYPE_COLORS.copy()

    for i, activity_type in enumerate(activity_order):
        if activity_type not in updated_activity_colors:
            updated_activity_colors[activity_type] = fallback_palette[i % len(fallback_palette)]

    fig = px.pie(
        chart_df,
        names="activity_type",
        values="Activities",
        facet_col="Mission",
        color="activity_type",
        color_discrete_map=updated_activity_colors,
        category_orders={
            "activity_type": activity_order,
            "Mission": [mission_a_label, mission_b_label],
        },
        title="Activity-Type Distribution Compared",
        hole=0.42,
    )

    fig.update_traces(
        textinfo="percent+label",
        textposition="inside",
        sort=False,
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Activities: %{value}<br>"
            "Share: %{percent}"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=470,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=True,
        legend_title_text="Activity Type",
        margin=dict(l=20, r=20, t=80, b=30),
        font=dict(color="#111827")
    )

    fig.for_each_annotation(
        lambda a: a.update(
            text=a.text.replace("Mission=", "")
        )
    )

    return fig

def make_two_mission_record_theme_heatmap(
    mission_a,
    mission_b
):
    df_a = mission_a["records"].copy()
    df_b = mission_b["records"].copy()

    mission_a_label = mission_a.get("display_name", mission_a["symbol"])
    mission_b_label = mission_b.get("display_name", mission_b["symbol"])

    df_a["Mission"] = mission_a_label
    df_b["Mission"] = mission_b_label

    df = pd.concat([df_a, df_b], ignore_index=True)

    if df.empty:
        return None

    df["report_record_type"] = (
        df["report_record_type"]
        .fillna("Unknown")
    )

    df["primary_theme"] = (
        df["primary_theme"]
        .fillna("Unknown")
    )

    # combine missions
    df["Cell"] = (
        df["Mission"]
        + "<br>"
        + df["report_record_type"]
    )

    matrix = (
        df.groupby(
            [
                "Cell",
                "primary_theme"
            ]
        )
        .size()
        .reset_index(name="Records")
        .pivot(
            index="Cell",
            columns="primary_theme",
            values="Records"
        )
        .fillna(0)
    )

    fig = px.imshow(
        matrix,
        text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
        title="Record Type × Primary Theme"
    )

    fig.update_layout(
        height=max(450, 40 * len(matrix.index)),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(
            l=20,
            r=20,
            t=70,
            b=20
        )
    )

    return fig

def render_mission_comparison_tab(
    filtered_missions,
    filtered_records,
    filtered_activities,
    filtered_actors
):
    st.markdown("### Mission Comparison")
    st.caption(
        "Select two mission reports and compare their records, themes, concern levels, actions, actors and activities."
    )

    mission_options = (
        filtered_missions["document_symbol"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    if len(mission_options) < 2:
        st.info("At least two mission reports are needed for comparison.")
        return

    def format_comparison_mission(symbol):
        return get_mission_display_name(symbol, filtered_missions)

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        selected_mission_a = st.selectbox(
            "Mission A",
            options=mission_options,
            index=0,
            format_func=format_comparison_mission,
            key="compare_mission_a"
        )

    default_b_index = 1 if len(mission_options) > 1 else 0

    with filter_col2:
        selected_mission_b = st.selectbox(
            "Mission B",
            options=mission_options,
            index=default_b_index,
            format_func=format_comparison_mission,
            key="compare_mission_b"
        )

    if selected_mission_a == selected_mission_b:
        st.warning("Select two different missions to compare them side by side.")
        return

    mission_a = get_comparison_mission_data(
        selected_mission_a,
        filtered_missions,
        filtered_records,
        filtered_activities,
        filtered_actors
    )

    mission_b = get_comparison_mission_data(
        selected_mission_b,
        filtered_missions,
        filtered_records,
        filtered_activities,
        filtered_actors
    )
    mission_a, mission_b = add_mission_display_names(mission_a, mission_b)

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        fig = make_two_mission_metric_bar(mission_a, mission_b)
        st.plotly_chart(fig, use_container_width=True, key="compare_metric_bar")

    with c2:
        fig = make_two_mission_activity_type_comparison(mission_a, mission_b)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="compare_activity_type_pies"
            )
        else:
            st.info("No activity-type data available for the selected missions.")

    c3, c4 = st.columns(2)

    with c3:
        fig = make_two_mission_theme_radar(
            mission_a,
            mission_b
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="compare_theme_radar"
            )
        else:
            st.info("No theme data available for the selected missions.")

    with c4:

        fig = make_two_mission_record_type_dumbbell(
            mission_a,
            mission_b,
            top_n=12
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="compare_record_type_dumbbell"
            )
        else:
            st.info("No theme comparison data available for the selected missions.")

    c5, c6 = st.columns(2)

    with c5:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        fig = make_two_mission_verb_comparison(
            mission_a,
            mission_b
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="compare_actor_source_target_sankey"
            )
        else:
            st.info("No actor source/target data available for the selected missions.")


    with c6:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        fig = make_two_mission_actor_category_comparison(mission_a, mission_b)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, key="compare_actor_categories")
        else:
            st.info("No actor category data available for the selected missions.")

    max_heatmap_value = max(
        mission_a["records"]
        .groupby(
            ["report_record_type", "primary_theme"]
        )
        .size()
        .max(),

        mission_b["records"]
        .groupby(
            ["report_record_type", "primary_theme"]
        )
        .size()
        .max()
    )

    h1, h2 = st.columns(2)

    with h1:
        fig = make_single_mission_record_theme_heatmap(
            mission_a,
            colorscale="Blues",
            cmax=max_heatmap_value
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="mission_a_record_theme_heatmap"
            )

    with h2:
        fig = make_single_mission_record_theme_heatmap(
            mission_b,
            colorscale="Oranges",
            cmax=max_heatmap_value
        )

        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="mission_b_record_theme_heatmap"
            )

    selected_mission_a_label = mission_a.get("display_name", selected_mission_a)
    selected_mission_b_label = mission_b.get("display_name", selected_mission_b)

    summary_df = pd.DataFrame([
        {
            "Metric": "Records",
            selected_mission_a_label: len(mission_a["records"]),
            selected_mission_b_label: len(mission_b["records"]),
        },
        {
            "Metric": "Activities",
            selected_mission_a_label: len(mission_a["activities"]),
            selected_mission_b_label: len(mission_b["activities"]),
        },
        {
            "Metric": "Actors Met",
            selected_mission_a_label: len(mission_a["actors"]),
            selected_mission_b_label: len(mission_b["actors"]),
        },
        {
            "Metric": "Unique Primary Themes",
            selected_mission_a_label: mission_a["records"]["primary_theme"].nunique(),
            selected_mission_b_label: mission_b["records"]["primary_theme"].nunique(),
        },
        {
            "Metric": "High or Critical Records",
            selected_mission_a_label: mission_a["records"][
                mission_a["records"]["level_of_concern"].isin(["High", "Critical"])
            ].shape[0],
            selected_mission_b_label: mission_b["records"][
                mission_b["records"]["level_of_concern"].isin(["High", "Critical"])
            ].shape[0],
        },
    ])

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

def make_mission_assessment_temporal_bar(
    missions_df,
    assessment_col,
    title,
    selected_regions=None,
    bucket_size=5
):
    df = missions_df.copy()

    if df.empty:
        return None

    required_cols = [
        "document_symbol",
        "document_date",
        "regions",
        assessment_col
    ]

    for col in required_cols:
        if col not in df.columns:
            return None

    df = _explode_regions(df)

    if selected_regions and "All Regions" not in selected_regions:
        df = df[df["regions"].isin(selected_regions)]

    if df.empty:
        return None

    df["document_date"] = pd.to_datetime(
        df["document_date"],
        errors="coerce"
    )

    df = df.dropna(subset=["document_date"])

    if df.empty:
        return None

    df[assessment_col] = (
        df[assessment_col]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace({
            "": "Unknown",
            "nan": "Unknown",
            "None": "Unknown"
        })
    )

    df["year"] = df["document_date"].dt.year.astype(int)

    df["year_bucket_start"] = (
        df["year"] // bucket_size
    ) * bucket_size

    df["year_bucket_end"] = (
        df["year_bucket_start"] + bucket_size - 1
    )

    df["year_bucket"] = (
        df["year_bucket_start"].astype(str)
        + "-"
        + df["year_bucket_end"].astype(str)
    )

    # Count unique mission reports by period, assessment category and region.
    chart_df = (
        df
        .drop_duplicates(
            subset=[
                "year_bucket",
                "regions",
                assessment_col,
                "document_symbol"
            ]
        )
        .groupby(
            [
                "year_bucket_start",
                "year_bucket",
                assessment_col,
                "regions"
            ],
            dropna=False
        )
        .agg(
            Mission_Reports=("document_symbol", "nunique")
        )
        .reset_index()
        .sort_values(
            [
                "year_bucket_start",
                assessment_col,
                "regions"
            ]
        )
    )

    if chart_df.empty:
        return None

    bucket_order = (
        chart_df[
            [
                "year_bucket_start",
                "year_bucket"
            ]
        ]
        .drop_duplicates()
        .sort_values("year_bucket_start")["year_bucket"]
        .tolist()
    )

    assessment_order = (
        chart_df
        .groupby(assessment_col)["Mission_Reports"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    fig = px.bar(
        chart_df,
        x="year_bucket",
        y="Mission_Reports",
        color="regions",
        facet_col=assessment_col,
        facet_col_wrap=3,
        barmode="stack",
        color_discrete_map=REGION_COLORS,
        title=title,
        category_orders={
            "year_bucket": bucket_order,
            assessment_col: assessment_order
        },
        custom_data=[
            assessment_col,
            "regions",
            "Mission_Reports"
        ]
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Region: %{customdata[1]}<br>"
            "Period: %{x}<br>"
            "Mission reports: %{customdata[2]}"
            "<extra></extra>"
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=True,
        legend_title_text="Region",
        hovermode="closest",
        xaxis_title=None,
        yaxis_title="Mission Reports",
        margin=dict(
            l=20,
            r=20,
            t=75,
            b=70
        ),
        font=dict(color="#111827")
    )

    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=bucket_order,
        tickangle=-35,
        showgrid=False
    )

    fig.update_yaxes(
        rangemode="tozero",
        gridcolor="rgba(148,163,184,0.25)",
        zerolinecolor="rgba(148,163,184,0.45)"
    )

    fig.for_each_annotation(
        lambda a: a.update(
            text=a.text.replace(f"{assessment_col}=", "")
        )
    )

    fig.for_each_xaxis(
        lambda axis: axis.update(title_text="")
    )

    return fig

def make_field_exposure_temporal_bar(
    missions_df,
    selected_regions=None
):
    return make_mission_assessment_temporal_bar(
        missions_df=missions_df,
        assessment_col="field_exposure",
        title="Field Exposure Over Time by Region",
        selected_regions=selected_regions,
        bucket_size=5
    )


def make_actor_diversity_temporal_bar(
    missions_df,
    selected_regions=None
):
    return make_mission_assessment_temporal_bar(
        missions_df=missions_df,
        assessment_col="actor_diversity_assessment",
        title="Actor Diversity Assessment Over Time by Region",
        selected_regions=selected_regions,
        bucket_size=5
    )

def render_reports_dashboard():
    reports = load_report_json(REPORTS_FILE)

    if reports is None:
        st.error(f"Could not find file at `{REPORTS_FILE}`. Please check the file path.")
        return

    if not reports:
        st.warning("The reports JSON file was loaded, but no reports were found.")
        return

    missions_df, records_df, activities_df, actors_df = flatten_reports(reports)

    if missions_df.empty or records_df.empty:
        st.error("No valid mission report or substantive records found in the JSON file.")
        return

    filtered_missions, filtered_records, filtered_activities, filtered_actors = apply_report_filters(
        missions_df, records_df, activities_df, actors_df
    )

    st.subheader("📊 Mission Reports Analytics")
    st.caption("Analyze extracted mission metadata, activities, actors engaged, findings, risks, recommendations, commitments and political signals.")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        metric_card("Mission Reports", str(len(filtered_missions)))
    with kpi2:
        metric_card("Substantive Records", str(len(filtered_records)))
    with kpi3:
        metric_card("Activities", str(len(filtered_activities)))
    with kpi4:
        metric_card("Actors Met", str(len(filtered_actors)))
    with kpi5:
        high_count = filtered_records[filtered_records["level_of_concern"].isin(["High", "Critical"])].shape[0]
        metric_card("High / Critical", str(high_count))

    st.markdown("<br>", unsafe_allow_html=True)

    overview_tab, mission_tab, regions_tab, actors_tab, compare_tab = st.tabs(
        [
            "Overview",
            "Mission Deep Dive",
            "Regional Comparison",
            "Actors & Activities",
            "Mission Comparison",
        ]
    )

    with overview_tab:
        c1, c2 = st.columns([1.3, 1])

        with c1:
            st.plotly_chart(
                make_report_theme_bar(filtered_records),
                use_container_width=True,
                key="overview_theme_bar"
            )

        with c2:
            st.plotly_chart(
                make_record_type_donut(filtered_records),
                use_container_width=True,
                key="overview_record_type_donut"
            )

        c5, c6 = st.columns([1, 1])

        with c5:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_region_actors_temporal_line(filtered_missions)

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="actors_temporal_by_region"
                )
            else:
                st.info("No dated actor engagement data available for the current filters.")


        with c6:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_region_activities_temporal_line(filtered_missions)

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="activities_temporal_by_region"
                )
            else:
                st.info("No dated activity data available for the current filters.")


        st.markdown("### Temporal Composition")

        region_options = get_available_regions(filtered_missions)

        selected_temporal_regions = st.multiselect(
            "Filter temporal bar charts by region",
            options=region_options,
            default=["All Regions"],
            key="overview_temporal_region_filter"
        )

        if not selected_temporal_regions:
            selected_temporal_regions = ["All Regions"]

        c7, c8 = st.columns(2)

        with c7:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_primary_theme_temporal_bar(
                records_df=filtered_records,
                missions_df=filtered_missions,
                selected_regions=selected_temporal_regions
            )

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="primary_theme_temporal_bar"
                )
            else:
                st.info("No primary-theme temporal data available for the selected region filter.")


        with c8:

            fig = make_actor_category_temporal_bar(
                actors_df=filtered_actors,
                missions_df=filtered_missions,
                selected_regions=selected_temporal_regions
            )

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="actor_category_temporal_bar"
                )
            else:
                st.info("No actor-category temporal data available for the selected region filter.")

        st.markdown("### Mission Assessment Trends")

        c11, c12 = st.columns(2)

        with c11:

            fig = make_field_exposure_temporal_bar(
                missions_df=filtered_missions,
                selected_regions=selected_temporal_regions
            )

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="field_exposure_temporal_bar"
                )
            else:
                st.info(
                    "No field-exposure data available for the selected region filter."
                )


        with c12:

            fig = make_actor_diversity_temporal_line(
                filtered_missions
            )

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="actor_diversity_temporal_line"
                )
            else:
                st.info("No actor-diversity assessment data available.")


        st.markdown("### Analytical Composition")

        c9, c10 = st.columns([1, 1])

        with c9:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_action_treemap(filtered_records)

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="overview_action_treemap"
                )
            else:
                st.info("No action-orientation data available.")

        with c10:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)

            fig = make_theme_sunburst(filtered_records)

            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="overview_theme_sunburst"
                )
            else:
                st.info("No theme drilldown data available.")

    with mission_tab:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        mission_symbols = filtered_missions["document_symbol"].dropna().tolist()

        if mission_symbols:
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

    with regions_tab:
        render_region_comparison(filtered_missions, filtered_records, filtered_activities, filtered_actors)

    with actors_tab:
        st.markdown("### Actors & Activities")

        st.caption(
            "This tab combines the analytical flow view with the actor network. "
            "Leave the mission selector empty to see the aggregate actor-category network. "
            "Select one or more missions to drill down to named actors."
        )

        st.markdown("#### Analytical Flow")

        sankey_fig = make_sankey(filtered_records)

        if sankey_fig is not None:
            st.plotly_chart(
                sankey_fig,
                use_container_width=True,
                key="actors_activities_sankey"
            )
        else:
            st.info("No analytical flow data available for the current filters.")

        st.markdown("#### Actor Network")

        mission_options_for_network = (
            filtered_actors["document_symbol"]
            .dropna()
            .drop_duplicates()
            .tolist()
        )

        if not mission_options_for_network:
            st.info("No missions with actor data are available for the current filters.")
        else:
            selected_actor_network_missions = st.multiselect(
                "Select mission(s) to show named actors",
                options=mission_options_for_network,
                default=[],
                format_func=lambda symbol: get_mission_display_name(
                    symbol,
                    filtered_missions
                ),
                key="actor_network_multiselect"
            )

            if not selected_actor_network_missions:
                st.caption(
                    "Aggregate view: no mission selected. All currently filtered missions are summarized by actor category only."
                )

                aggregate_network_html = make_pyvis_actor_network_html(
                    filtered_missions,
                    filtered_actors,
                    selected_symbols=None,
                    show_actor_names=False
                )

                if aggregate_network_html:
                    components.html(
                        aggregate_network_html,
                        height=860,
                        scrolling=True
                    )
                else:
                    st.info("No aggregate actor network data available for the current filters.")

            else:
                st.caption(
                    "Mission drilldown: selected mission(s) are shown with actor categories and named actors."
                )

                detail_network_html = make_pyvis_actor_network_html(
                    filtered_missions,
                    filtered_actors,
                    selected_symbols=selected_actor_network_missions,
                    show_actor_names=True,
                    max_actors_per_category=8
                )

                if detail_network_html:
                    components.html(
                        detail_network_html,
                        height=920,
                        scrolling=True
                    )
                else:
                    st.info("No named actor network data available for the selected mission(s).")

    with compare_tab:
        render_mission_comparison_tab(
            filtered_missions,
            filtered_records,
            filtered_activities,
            filtered_actors
        )
