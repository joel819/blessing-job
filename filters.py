import hashlib
import re
from config import LOCATION_KEYWORDS, MIN_SALARY, MIN_QUALITY_SCORE

ROLE_KEYWORDS = [
    "support worker",
    "care assistant",
    "healthcare assistant",
    "health care assistant",
    "senior care assistant",
    "domiciliary care worker",
    "live-in carer",
    "carer",
]

VISA_KEYWORDS = [
    "visa",
    "sponsorship",
    "skilled worker visa",
    "tier 2",
    "certificate of sponsorship",
]

NEGATIVE_KEYWORDS = [
    "no sponsorship",
    "sponsorship not available",
    "cannot provide sponsorship",
    "unable to provide sponsorship",
    "not offering sponsorship",
    "must have the right to work in the uk",
    "no tier 2",
    "no skilled worker visa",
]

HIGH_QUALITY_SIGNALS = [
    "nhs",
    "care quality commission",
    "cqc",
    "registered",
    "ofsted",
    "enhanced dbs",
    "pension",
    "annual leave",
    "training provided",
    "career development",
]


def generate_job_id(job):
    def normalize(text):
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'\b(ltd|limited|llp|plc|trust|group|care)\b', '', text)
        return "".join(re.findall(r'[a-z0-9]', text))

    title = normalize(job.get("title", ""))
    company = normalize(job.get("company", ""))

    if not company or company == "notspecified":
        desc = normalize(job.get("description", ""))[:50]
        raw_str = f"{title}|{desc}"
    else:
        raw_str = f"{title}|{company}"

    return hashlib.md5(raw_str.encode()).hexdigest()


def extract_salary_number(salary_str):
    """Extract the first number from a salary string."""
    if not salary_str:
        return 0
    numbers = re.findall(r'[\d,]+', salary_str.replace(',', ''))
    if numbers:
        try:
            return int(numbers[0])
        except:
            return 0
    return 0


def score_job_quality(job):
    """
    Score a job from 0-10 based on quality signals.
    Higher score = better quality listing.
    """
    score = 5  # Base score
    text = f"{job.get('title', '')} {job.get('description', '')} {job.get('company', '')}".lower()

    # Boost for quality signals
    for signal in HIGH_QUALITY_SIGNALS:
        if signal in text:
            score += 0.5

    # Boost for salary mentioned
    if job.get('salary') and job['salary'] != 'Competitive':
        score += 1

    # Boost for specific location
    if job.get('location'):
        score += 0.5

    # Boost for recent posting
    if job.get('date_posted') and 'today' in job.get('date_posted', '').lower():
        score += 1

    # Penalise very short descriptions
    if len(job.get('description', '')) < 100:
        score -= 2

    return min(round(score, 1), 10)


def match_keywords(job):
    """
    Multi-layered filter:
    1. Negative check — must NOT say no sponsorship
    2. Role check — must be a care/support role
    3. Visa check — must mention sponsorship
    4. Location check — must be in target location (if set)
    5. Salary check — must meet minimum salary (if set)
    6. Quality score — must meet minimum score (if set)
    """
    title = job.get("title", "").lower()
    description = job.get("description", "").lower()
    location = job.get("location", "").lower()
    text = f"{title} {description}"

    # 1. Negative check
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        return False

    # 2. Role check
    if not any(role in text for role in ROLE_KEYWORDS):
        return False

    # 3. Visa check
    if not any(visa in text for visa in VISA_KEYWORDS):
        return False

    # 4. Location check (only if locations are configured)
    if LOCATION_KEYWORDS:
        location_text = f"{location} {text}"
        if not any(loc in location_text for loc in LOCATION_KEYWORDS):
            return False

    # 5. Salary check (only if minimum is set)
    if MIN_SALARY > 0:
        salary_str = job.get('salary', '')
        salary_num = extract_salary_number(salary_str)
        if salary_num > 0 and salary_num < MIN_SALARY:
            return False

    # 6. Quality score check
    if MIN_QUALITY_SCORE > 0:
        if score_job_quality(job) < MIN_QUALITY_SCORE:
            return False

    return True
