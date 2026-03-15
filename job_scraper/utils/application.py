import csv
import os
import random
from playwright.sync_api import sync_playwright
try:
    from ..config import cv_path, applicant
except (ImportError, ValueError):
    from config import cv_path, applicant

# 🔥 PART A — ADD APPLICATION LOGGING (Local CSV)
def log_application(job_title, company, job_url, platform, status):
    file_exists = os.path.isfile("application_log.csv")
    with open("application_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Job Title", "Company", "URL", "Platform", "Status"])
        writer.writerow([job_title, company, job_url, platform, status])

# 🔥 PART C — MULTI-TEMPLATE COVER LETTER ROTATION
def generate_cover_letter(job_title, company, job_description):
    templates = [
        f"""
Dear Hiring Manager,

I am applying for the {job_title} role at {company}. 
With two years of direct Support Worker experience,
I have provided person-centered care, safeguarding, and mobility support 
across both care homes and community environments.

I hold a Skilled Worker Visa and I am available immediately.

Kind regards,
Blessing Oyewole
""",

        f"""
Hello,

I would like to express my interest in the {job_title} role at {company}. 
My background includes personal care, medication prompting, companionship, 
and supporting service users with daily routines.

I am reliable, compassionate, and legally able to work in the UK under a Skilled Worker Visa.

Best regards,
Blessing Oyewole
""",

        f"""
Dear Hiring Team,

Please consider me for the {job_title} position. 
I have hands-on experience in delivering high-quality care, ensuring dignity, safety, 
and emotional support for vulnerable individuals. 

Available for immediate start under a Skilled Worker Visa.

Sincerely,
Blessing Oyewole
"""
    ]
    return random.choice(templates)

# 🔥 PART 3 — SIMPLE SKILL MATCH CHECK
def skill_match(job_description):
    keywords = [
        "support worker", "healthcare assistant", "care assistant",
        "domiciliary", "care home", "senior carer",
        "tier 2", "visa sponsorship", "skilled worker"
    ]

    jd = job_description.lower()
    return any(k in jd for k in keywords)

# 🔥 PART F — HUMAN-LIKE TYPING OPTION
def slow_type(page, selector, text, delay=50):
    try:
        page.focus(selector)
        for char in text:
            page.keyboard.type(char)
            page.wait_for_timeout(delay)
        return True
    except:
        return False

# 🔥 PART B & D & E — IMPROVED AUTO-APPLY
def auto_apply(job_url, cv_path, message, applicant):
    try:
        # 🔥 PART D — ENHANCED PLATFORM DETECTION
        platforms = {
            "reed": "reed.co.uk",
            "adzuna": "adzuna.co.uk",
            "cvlibrary": "cv-library.co.uk",
            "totaljobs": "totaljobs.com",
            "indeed": "indeed.co.uk",
            "nhs": "jobs.nhs.uk",
            "carehome": "carehome.co.uk",
            "jobmedic": "jobmedic.co.uk"
        }

        active_platform = "unknown"
        for name, keyword in platforms.items():
            if keyword in job_url:
                active_platform = name
                break

        print(f"[AUTO-APPLY] Opening: {job_url} (Platform: {active_platform})")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            page.goto(job_url, timeout=60000)

            # 🔥 PART E — IMPROVED AUTO-FORM HANDLING
            # Scroll in case elements are off-screen
            page.evaluate("window.scrollBy(0, 500)")
            # Give page more time to load
            page.wait_for_timeout(2000)

            selectors = {
                "name": ["input[name='fullName']", "input[name='name']", "#applicant_name"],
                "email": ["input[name='email']", "#applicant_email"],
                "phone": ["input[name='phone']", "#applicant_phone"],
                "message": ["textarea[name='message']", "#cover_letter", "#applicant_message"],
                "cv": ["input[type='file']", "#cv_upload", "#resume_upload"],
                "submit": ["button[type='submit']", "button.apply", "#submitApplication"]
            }

            def fill_field(field_list, value):
                for selector in field_list:
                    try:
                        # Try normal fill first
                        page.fill(selector, value)
                        return True
                    except:
                        # 🔥 PART F — Fallback to slow type
                        if slow_type(page, selector, value):
                            return True
                return False

            def upload_cv(field_list, path):
                for selector in field_list:
                    try:
                        page.set_input_files(selector, path)
                        return True
                    except:
                        pass
                return False

            fill_field(selectors["name"], applicant["name"])
            fill_field(selectors["email"], applicant["email"])
            fill_field(selectors["phone"], applicant["phone"])
            fill_field(selectors["message"], message)

            upload_cv(selectors["cv"], cv_path)

            for selector in selectors["submit"]:
                try:
                    page.click(selector)
                    print(f"[AUTO-APPLY] Submitted on {active_platform}!")
                    browser.close()
                    return True, active_platform
                except:
                    pass

            browser.close()
            print("[AUTO-APPLY] No submit button found.")
            return False, active_platform

    except Exception as e:
        print(f"[AUTO-APPLY ERROR] {str(e)}")
        return False, None
