from pathlib import Path

# --------------------------------------------------
# File Paths
# --------------------------------------------------
TOR_FILE = "tor_output_analysis_v1.json"
REPORTS_FILE = "SecurityCouncilAnalysis_MissionReports_v1.json"

# --------------------------------------------------
# Custom CSS
# --------------------------------------------------
CUSTOM_CSS = """
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
"""

# --------------------------------------------------
# Color Schemes & Mappings
# --------------------------------------------------
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
