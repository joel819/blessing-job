import hashlib

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

import re

def generate_job_id(job):
    """
    Generate a unique ID for a job based on its title and company.
    We exclude location because location strings vary wildly between job boards.
    """
    # Normalize text: lowercase, remove non-alphanumeric, and strip whitespace
    def normalize(text):
        if not text: return ""
        text = text.lower()
        # Remove common company suffixes to match "Care Ltd" with "Care"
        text = re.sub(r'\b(ltd|limited|llp|plc|trust|group|care)\b', '', text)
        # Remove all special chars
        return "".join(re.findall(r'[a-z0-9]', text))

    title = normalize(job.get("title", ""))
    company = normalize(job.get("company", ""))
    
    # If company is not specified, we must use a bit of the description or link to avoid 
    # collapsing different jobs with the same title into one ID.
    if not company or company == "notspecified":
        # Use first 50 alphanumeric chars of description as a fallback identifier
        desc = normalize(job.get("description", ""))[:50]
        raw_str = f"{title}|{desc}"
    else:
        raw_str = f"{title}|{company}"
        
    return hashlib.md5(raw_str.encode()).hexdigest()

def match_keywords(job, keywords=None):
    """
    Stricter multi-layered filter:
    1. Role Check: Must be a Support/Care role.
    2. Visa Check: Must mention sponsorship/visa.
    3. Negative Check: Must NOT mention 'no sponsorship'.
    """
    title = job.get("title", "").lower()
    description = job.get("description", "").lower()
    text = f"{title} {description}"
    
    # 1. Negative Check
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        return False
        
    # 2. Role Check (Search title primarily, then description)
    role_match = any(role in text for role in ROLE_KEYWORDS)
    if not role_match:
        return False
        
    # 3. Visa Check
    visa_match = any(visa in text for visa in VISA_KEYWORDS)
    if not visa_match:
        return False
        
    return True
