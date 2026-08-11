TASK: Implement MD-06 — Admin Career Readiness, Lifestyle Correlation and Institution Academic Health.

PRECONDITION
MD-01 through MD-05 complete.

OBJECTIVE
Cover the remaining major KDAC-3 business requirements using existing datasets without creating speculative systems.

PART A — CAREER READINESS

Route:
 /admin/career

Source:
career_preferences and other existing career-related data only.

KPIs:
- Placement readiness where actual field exists
- Internship status where actual field exists
- Higher studies interest
- Entrepreneurship interest
- Certification interest

Do NOT invent fields if they do not exist.

CAREER DOMAIN CHART
Top preferred career domains.

JOB ROLE CHART
Top preferred roles.

READINESS DISTRIBUTION
Only if actual readiness field/rule exists.

DEPARTMENT COMPARISON
Career preference/readiness by department where data supports it.

No placement management.
No job application CRUD.
No recommendation engine.

PART B — LIFESTYLE

Route:
 /admin/lifestyle

Source:
lifestyle_survey.

PRIVACY REQUIREMENT:
Only aggregate/anonymized institution-level insights.
Do not expose unnecessary individual lifestyle records.

Analyze actual available factors such as:
- study hours
- sleep
- screen time
- stress
- physical activity

Compare against:
- academic percentage
- SGPA
- attendance

VISUALS:
1. Study hours vs percentage
2. Sleep vs SGPA
3. Screen time vs percentage
4. Stress vs percentage
Only create a visualization when sufficient real data exists.

CORRELATION TABLE:
Factor
Correlation
Direction
Sample size

IMPORTANT:
Calculate actual correlations.
Never hardcode example values.

Use appropriate statistical calculation.
Handle NULLs correctly.
Do not imply causation from correlation.

PART C — INSTITUTION ACADEMIC HEALTH

Create:
Institution Academic Health Score

Use existing Student Academic Health methodology where appropriate, but define an institution-level aggregation clearly.

Potential components based only on already existing metrics:
- academic performance
- attendance
- backlogs
- risk

Do not invent arbitrary weights if an existing canonical health-score configuration exists.

Display:
- Overall institutional score
- Department scores
- Score components

Department comparison:
Bar chart.

Show methodology/tooltip so Admin understands what the score means.

Do not introduce ML into this score yet.

TEST:
- career aggregation
- NULL handling
- correlation calculations
- sample-size behavior
- health-score aggregation
- department comparison
- privacy scoping

DO NOT implement:
GenAI
Notifications
ML
Admin settings