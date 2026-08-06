from dotenv import load_dotenv
from google import genai
import json
import os
import pandas as pd
import requests
from io import BytesIO
from pypdf import PdfReader

# Read Excel file
df = pd.read_excel("Security Council Missions iSCAD.xlsx")

def get_pdf_url(symbol):
    return f"https://documents.un.org/api/symbol/access?s={symbol}&l=en&t=pdf"

# Read JSON
output_file = "SecurityCouncilAnalysis_MissionReports.json"
try:
    with open(output_file, "r", encoding="utf-8") as f:
        results = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    results = []

load_dotenv(r'C:\Users\PKOULOUBAN\OneDrive - United Nations\Documents\PycharmProjects\gemini-api.env')
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY")
    )

# Extract links into a list
report_links = (
    df["Mission Report"]
    .dropna()
    .astype(str)
    .tolist()
)

# Build set of already processed report URLs
existing_report_urls = {
    r.get("report_url")
    for r in results
    if isinstance(r, dict) and r.get("report_url")
}

for report_url in report_links:

    if str(report_url).strip().lower() == "not available":
        print("Skipping: Not available")
        continue

    if report_url in existing_report_urls:
        print(f"Skipping (already analyzed): {report_url}")
        continue

    print(f"Processing {report_url}")
    pdf_url = get_pdf_url(report_url)

    pdf = requests.get(pdf_url, timeout=30)
    pdf.raise_for_status()

    reader = PdfReader(BytesIO(pdf.content))
    report_text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    prompt = f"""
You are an analyst of United Nations Security Council mission reports.

Your task is to extract mission metadata, activities undertaken, actors engaged, mission-level analytical findings, and classify every substantive finding, observation, stakeholder position, concern, assessment, conclusion, recommendation, commitment, follow-up action, or political message contained in the mission report.

This is the mission report: {report_text}

1. Extract each substantive point as a separate record.
1A. Prioritize Security Council mission activities, observations, assessments, conclusions, recommendations, follow-up actions, and political messages. Extract stakeholder views only when they are significant, substantive, or clearly contribute to the mission's findings, assessments, or conclusions.
2. Use the exact text whenever possible.
3. Select exactly ONE report_record_type.
4. Select exactly ONE primary_theme.
5. Assign secondary_themes only when clearly supported.
6. Identify the principal verb.
7. Use the theme taxonomy below.
8. Do not invent information.
9. Use null when information cannot be determined.
10. Return ONLY valid JSON.
11. Extract all mission activities separately from substantive findings.
12. Extract all actors engaged separately from substantive findings.
13. Distinguish between mission observations, stakeholder views, risks, recommendations, commitments and political signals. Prioritize mission-generated findings over stakeholder statements when both address the same issue.
14. Analytical classifications must be evidence-based and conservative.
15. Do not infer consensus, concern levels, policy implications or political signals unless reasonably supported by the text.
16. Avoid duplicate records. Each record should capture a unique substantive point.
17. Mission-level analytics must be based on the overall content of the report, not a single passage.

REPORT RECORD TYPES

- Situation Assessment
- Stakeholder Position
- Mission Observation
- Progress Assessment
- Challenge / Risk
- Recommendation / Call for Action
- Political Signalling
- Mandate-Relevant Reporting

Stakeholder Position records should be created only for substantive positions, requests, concerns, commitments, disagreements, or recommendations. Do not create Stakeholder Position records for routine briefings, descriptive remarks, greetings, protocol statements, or factual updates unless they have clear analytical significance for the mission.

ACTIVITY TYPES

Extract every activity undertaken by the Security Council mission.

Examples include:

- Meeting
- Briefing
- Site Visit
- Field Visit
- Press Stakeout
- Press Conference
- Roundtable
- Consultation
- Dialogue
- Inspection
- Engagement Session
- Visit to UN Facility
- Visit to Government Institution
- Visit to Community or Project Site
- Other

ACTORS MET

Identify all actors engaged by the mission.

ACTOR CATEGORIES

- Government
- Opposition / Political Actor
- UN Mission
- UN Secretariat / Special Envoy
- UN Country Team
- Regional Organization
- Civil Society
- Women's Organization
- Youth Organization
- Armed Group / Non-State Actor
- Affected Community
- Other
- Unknown

THEMES

- Peace Agreement Implementation
- Ceasefire / Cessation of Hostilities
- Security / Stability
- Sovereignty / Territorial Integrity
- UN Mission Mandate
- State Authority / Armed Groups / Weapons
- Border / Regional Issues
- Political Process
- Human Rights
- Humanitarian Issues
- Rule of Law / Justice
- DDR / Reintegration
- Women, Peace and Security
- Youth, Peace and Security
- Regional Cooperation
- Other

ANALYTICAL FIELDS

level_of_concern

Select one:

- None
- Low
- Moderate
- High
- Not Applicable

degree_of_consensus

Select one:

- Consensus
- Partial Consensus
- Divergence
- Unclear
- Not Applicable

action_orientation

Select one:

- Observation
- Assessment
- Warning
- Recommendation
- Request
- Commitment
- Follow-up Action
- Political Signalling
- Not Applicable

MISSION ANALYTICS GUIDANCE

mission_type

Select one:

- Political Engagement Mission
  (demonstrate Council commitment; express support; political signaling)

- Implementation Review Mission
  (assess implementation of resolutions, mandates, agreements, ceasefires)

- Situation Assessment Mission
  (assess developments on the ground; understand challenges and conflict dynamics)

- Peace Process Support Mission
  (support negotiations, mediation, dispute settlement, implementation of agreements)

- UN Mission Oversight Mission
  (review peacekeeping or special political missions and mandate implementation)

- Investigative Mission
  (fact-finding or investigation of alleged violations or incidents)

- Hybrid/Mixed Mission
  (combines multiple mission purposes)

field_exposure examples:

- None
- Limited
- Moderate
- Extensive

actor_diversity_assessment examples:

- Low
- Moderate
- High

overall_character examples:

- Primarily political
- Primarily security-focused
- Primarily humanitarian
- Primarily institutional
- Mixed political-security
- Mixed political-humanitarian
- Mixed

main_themes should contain the most prominent themes recurring throughout the report.

main_risks should summarize major risks or concerns identified in the report.

main_commitments should summarize commitments, agreed actions, follow-up actions or requests for future engagement.

main_policy_signals should summarize the most important political messages conveyed by the mission or stakeholders.

summary_assessment should provide a concise evidence-based synthesis of the mission.

OUTPUT FORMAT

{{
  "mission_title": "",
  "document_symbol": "",
  "document_date": "",
  "mission_country_or_region": "",
  "related_tor_document_symbol": "",

  "mission_analytics": {{
    "mission_type": "",
    "mission_subtype": "",
    "field_exposure": "",
    "actor_diversity_assessment": "",
    "overall_character": "",
    "main_themes": [],
    "main_risks": [],
    "main_commitments": [],
    "main_policy_signals": [],
    "summary_assessment": ""
  }},

  "activities": [
    {{
      "activity_id": 1,
      "activity_type": "",
      "activity_description": ""
    }}
  ],

  "actors_met": [
    {{
      "actor_id": 1,
      "actor_name": "",
      "actor_category": ""
    }}
  ],

  "records": [
    {{
      "record_id": 1,
      "record_text": "",
      "verb": "",

      "report_record_type": "",
      "primary_theme": "",
      "secondary_themes": [],

      "geographic_scope": "",
      "actor_source": "",
      "actor_target": "",

      "level_of_concern": "",
      "degree_of_consensus": "",
      "action_orientation": "",

      "political_signal": "",
      "policy_implication": ""
    }}
  ]
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        response_text = response.text.strip()

        # Remove markdown JSON fences if Gemini adds them
        response_text = response_text.replace("```json", "")
        response_text = response_text.replace("```", "").strip()

        parsed_json = json.loads(response_text)

        # Add source TOR URL to output
        parsed_json["report_url"] = report_url

        # Append to results
        results.append(parsed_json)

        # Save after every successful request
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print("✓ Saved")

    except Exception as e:
        print(f"✗ Error for {report_url}: {e}")

print("Finished.")
