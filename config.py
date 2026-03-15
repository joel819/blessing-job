import os

# ─── Applicant Details ───────────────────────────────────────────────────────
cv_path = "Blessing_Oyewole_Improved_CV_Updated.pdf"

applicant = {
    "name": "Blessing Oyewole",
    "email": os.environ.get("APPLICANT_EMAIL", "oyewoleblessing61@gmail.com"),
    "phone": "07440350609"
}

# ─── Location Filter ─────────────────────────────────────────────────────────
# Add cities or areas where Blessing wants to work
# Leave empty list [] to get jobs from anywhere in the UK
LOCATION_KEYWORDS = [
    "london",
    "manchester",
    "birmingham",
    "leeds",
    "bristol",
    # Add her specific city here
]

# ─── Salary Filter ───────────────────────────────────────────────────────────
# Minimum annual salary to consider (set to 0 to disable)
MIN_SALARY = 20000

# ─── Job Quality Score ───────────────────────────────────────────────────────
# Minimum quality score out of 10 to send alert (set to 0 to disable)
MIN_QUALITY_SCORE = 5

# ─── Notification Schedule ───────────────────────────────────────────────────
# INSTANT: Send alert as soon as jobs are found
# DAILY: Collect all day then send one summary at set time
NOTIFICATION_MODE = "DAILY"  # "INSTANT" or "DAILY"
DAILY_SUMMARY_TIME = "08:00"  # Time to send daily summary (24hr format)

# ─── Legacy Skill Match Keywords ─────────────────────────────────────────────
SKILL_MATCH_KEYWORDS = [
    "support worker", "healthcare assistant", "care assistant",
    "domiciliary", "care home", "senior carer",
    "tier 2", "visa sponsorship", "skilled worker"
]
