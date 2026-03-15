#!/usr/bin/env python3
"""
job_finder.py — UK Skilled Worker Visa Job Finder & Alert System

Scrapes UK job boards for support worker / care assistant roles
that offer visa sponsorship. Sends alerts via Telegram and Email
every 10 minutes.

Uses Playwright (headless browser) for sites with bot protection,
and Requests + BeautifulSoup for lighter sites.
"""

# ──────────────────────────────────────────────────────────────────
# IMPORTS
# ──────────────────────────────────────────────────────────────────
import os
import re
import sys
import json
import time
import hashlib
import logging
import smtplib
import traceback
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
import schedule

# Playwright (used for Indeed & DWP which block simple HTTP requests)
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────
# 🔥 PART 1 — ADD CV PATH
cv_path = "Blessing_Oyewole_Improved_CV_Updated.pdf"

# Applicant Data
applicant = {
    "name": "Blessing Oyewole",
    "email": "oyewoleblessing61@gmail.com",
    "phone": "07440350609"
}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536955372:AAGMyomvxsNK3s2EEm1oWOfFiwaFHjAC1S0")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "686525754")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "joeljobbot@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "drsa rbrx oiee jjas")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", EMAIL_USERNAME)

CACHE_FILE = "jobs_cache.json"
LOG_FILE = "jobtracker.log"

JOB_TITLES = [
    "support worker",
    "care assistant",
    "health care assistant",
    "healthcare assistant",
    "senior care assistant",
    "domiciliary care worker",
    "live-in carer",
    "live in carer",
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
    "sponsorship not found",
    "sponsorship not available",
    "not available for sponsorship",
    "cannot provide sponsorship",
    "unable to provide sponsorship",
    "not offering sponsorship",
    "must have the right to work in the uk",
    "no tier 2",
    "no skilled worker visa",
]

REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
RETRY_DELAY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ──────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("JobFinder")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

# ──────────────────────────────────────────────────────────────────
# CACHE
# ──────────────────────────────────────────────────────────────────

def load_cache() -> set:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("seen_ids", []))
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("Cache read error: %s", exc)
    return set()


def save_cache(seen_ids: set) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"seen_ids": list(seen_ids), "updated": datetime.now(timezone.utc).isoformat()}, f)
        logger.debug("Cache saved (%d IDs)", len(seen_ids))
    except IOError as exc:
        logger.error("Cache write error: %s", exc)


def job_id(job: Dict) -> str:
    raw = f"{job.get('job_title','')}-{job.get('company_name','')}-{job.get('apply_link','')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ──────────────────────────────────────────────────────────────────

def fetch_page(url: str, params: dict = None) -> Optional[BeautifulSoup]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Fetching [%d/%d]: %s", attempt, MAX_RETRIES, url)
            resp = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as exc:
            logger.warning("Attempt %d failed for %s: %s", attempt, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    logger.error("All %d attempts failed for %s", MAX_RETRIES, url)
    return None


def fetch_with_playwright(url: str, wait_selector: str = None, wait_ms: int = 5000) -> Optional[BeautifulSoup]:
    """Fetch a page using a real headless browser (bypasses bot detection)."""
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright not installed — cannot fetch %s", url)
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Playwright fetch [%d/%d]: %s", attempt, MAX_RETRIES, url)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    locale="en-GB",
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Dismiss cookie banners if present
                for sel in ["#onetrust-accept-btn-handler", "#accept-all-cookies",
                            "button[data-accept-cookies]", ".cookie-accept",
                            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            time.sleep(0.5)
                    except Exception:
                        pass

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=15000)
                    except PlaywrightTimeout:
                        logger.debug("Selector '%s' not found, continuing anyway", wait_selector)

                page.wait_for_timeout(wait_ms)
                html = page.content()
                browser.close()
                return BeautifulSoup(html, "html.parser")

        except Exception as exc:
            logger.warning("Playwright attempt %d failed for %s: %s", attempt, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    logger.error("All Playwright attempts failed for %s", url)
    return None



# ──────────────────────────────────────────────────────────────────
# 🔥 PART A — ADD APPLICATION LOGGING (Local CSV)
# ──────────────────────────────────────────────────────────────────
import csv
import os

def log_application(job_title, company, job_url, platform, status):
    file_exists = os.path.isfile("application_log.csv")
    with open("application_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Job Title", "Company", "URL", "Platform", "Status"])
        writer.writerow([job_title, company, job_url, platform, status])


# ──────────────────────────────────────────────────────────────────
# 🔥 PART C — MULTI-TEMPLATE COVER LETTER ROTATION
# ──────────────────────────────────────────────────────────────────
import random

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


# ──────────────────────────────────────────────────────────────────
# 🔥 PART 3 — SIMPLE SKILL MATCH CHECK
# ──────────────────────────────────────────────────────────────────
def skill_match(job_description):
    keywords = [
        "support worker", "healthcare assistant", "care assistant",
        "domiciliary", "care home", "senior carer",
        "tier 2", "visa sponsorship", "skilled worker"
    ]

    jd = job_description.lower()
    return any(k in jd for k in keywords)


# ──────────────────────────────────────────────────────────────────
# 🔥 PART F — HUMAN-LIKE TYPING OPTION
# ──────────────────────────────────────────────────────────────────
def slow_type(page, selector, text, delay=50):
    try:
        page.focus(selector)
        for char in text:
            page.keyboard.type(char)
            page.wait_for_timeout(delay)
        return True
    except:
        return False


# ──────────────────────────────────────────────────────────────────
# 🔥 PART B & D & E — IMPROVED AUTO-APPLY
# ──────────────────────────────────────────────────────────────────
from playwright.sync_api import sync_playwright

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
                        # Fallback to slow type
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


# ──────────────────────────────────────────────────────────────────
# FILTER / MATCHING
# ──────────────────────────────────────────────────────────────────

def matches_title(text: str) -> bool:
    text_lower = text.lower()
    return any(title in text_lower for title in JOB_TITLES)


def has_visa_keywords(text: str) -> bool:
    text_lower = text.lower()
    
    # Check for negative phrases first
    if any(neg in text_lower for neg in NEGATIVE_KEYWORDS):
        return False
        
    # Then check for positive keywords
    return any(kw in text_lower for kw in VISA_KEYWORDS)


def is_recent(date_str: str, hours: int = 48) -> bool:
    if not date_str:
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    lower = date_str.lower().strip()

    if any(w in lower for w in ["just now", "just posted", "today", "hour ago",
                                  "hours ago", "minute ago", "minutes ago",
                                  "1 day ago", "yesterday"]):
        return True
    m = re.match(r"(\d+)\s*days?\s*ago", lower)
    if m:
        return int(m.group(1)) <= 2

    formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
               "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= cutoff
        except ValueError:
            continue
    return True


def clean(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# ──────────────────────────────────────────────────────────────────
# SCRAPERS
# ──────────────────────────────────────────────────────────────────

def scrape_findajob() -> List[Dict]:
    """DWP Find a Job — uses Playwright (site is slow / blocks requests)."""
    site = "Find a Job (DWP)"
    jobs = []
    logger.info("Scraping %s ...", site)

    queries = ["support worker visa sponsorship", "care assistant visa sponsorship"]

    for query in queries:
        url = f"https://findajob.dwp.gov.uk/search?q={quote_plus(query)}&d=2&pp=25&sb=date&sd=down"
        soup = fetch_with_playwright(url, wait_selector=".search-result, h3", wait_ms=4000)
        if not soup:
            continue

        results = soup.select("div.search-result")
        if not results:
            results = soup.find_all("div", id=re.compile(r"^job-"))

        for item in results:
            try:
                title_el = item.find("h3")
                if not title_el:
                    continue
                a_tag = title_el.find("a")
                if not a_tag:
                    continue

                job_title = clean(a_tag.get_text())
                if not matches_title(job_title):
                    continue

                link = a_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin("https://findajob.dwp.gov.uk", link)

                company = ""
                comp_el = item.find("strong")
                if comp_el:
                    company = clean(comp_el.get_text())

                location = ""
                for tag in item.find_all(["span", "p"]):
                    t = clean(tag.get_text())
                    if "location" in t.lower() or "," in t:
                        location = t.replace("Location:", "").strip()
                        break

                date_posted = ""
                for tag in item.find_all(["span", "p"]):
                    t = clean(tag.get_text())
                    if "posted" in t.lower() or re.search(r"\d{1,2}\s+\w+\s+\d{4}", t):
                        date_posted = t.replace("Posted on:", "").strip()
                        break

                snippet = clean(item.get_text())[:300]
                visa_found = has_visa_keywords(snippet)

                if visa_found and is_recent(date_posted):
                    jobs.append({
                        "job_title": job_title,
                        "company_name": company or "Not specified",
                        "location": location or "UK",
                        "date_posted": date_posted or "Recent",
                        "description_snippet": snippet,
                        "apply_link": link,
                        "visa_sponsorship_found": True,
                        "source": site,
                    })
            except Exception as exc:
                logger.debug("Parse error in %s: %s", site, exc)

    logger.info("%s: found %d matching jobs", site, len(jobs))
    return jobs


def scrape_indeed() -> List[Dict]:
    """Indeed UK — uses Playwright (403 with plain requests)."""
    site = "Indeed UK"
    jobs = []
    logger.info("Scraping %s ...", site)

    search_queries = [
        "support worker visa sponsorship",
        "care assistant visa sponsorship",
        "healthcare assistant visa sponsorship",
    ]

    for query in search_queries:
        url = f"https://uk.indeed.com/jobs?q={quote_plus(query)}&l=United+Kingdom&sort=date&fromage=2"
        soup = fetch_with_playwright(url, wait_selector=".job_seen_beacon, .jobsearch-ResultsList", wait_ms=5000)
        if not soup:
            continue

        cards = soup.select("div.job_seen_beacon")
        if not cards:
            cards = soup.select("div.cardOutline")

        for card in cards:
            try:
                # Title
                title_el = card.select_one("a.jcs-JobTitle") or card.select_one("h2.jobTitle a") or card.select_one("h2.jobTitle")
                if not title_el:
                    continue

                a_tag = title_el if title_el.name == "a" else title_el.find("a")
                job_title = clean((a_tag or title_el).get_text())
                if not matches_title(job_title):
                    continue

                link = ""
                if a_tag and a_tag.get("href"):
                    link = a_tag["href"]
                    if not link.startswith("http"):
                        link = urljoin("https://uk.indeed.com", link)

                # Company
                company = ""
                comp_el = card.select_one("[data-testid='company-name']") or card.select_one("span.companyName")
                if comp_el:
                    company = clean(comp_el.get_text())

                # Location
                location = ""
                loc_el = card.select_one("[data-testid='text-location']") or card.select_one("div.companyLocation")
                if loc_el:
                    location = clean(loc_el.get_text())

                # Date
                date_posted = ""
                date_el = card.select_one("span.date") or card.select_one("[data-testid='myJobsState']")
                if date_el:
                    date_posted = clean(date_el.get_text())

                # Snippet
                snippet = ""
                snip_el = card.select_one("div.job-snippet") or card.select_one(".underShelfFooter")
                if snip_el:
                    snippet = clean(snip_el.get_text())[:300]
                else:
                    snippet = clean(card.get_text())[:300]

                full_text = f"{job_title} {snippet} {company}".lower()
                visa_found = has_visa_keywords(full_text)

                if visa_found and is_recent(date_posted):
                    jobs.append({
                        "job_title": job_title,
                        "company_name": company or "Not specified",
                        "location": location or "UK",
                        "date_posted": date_posted or "Recent",
                        "description_snippet": snippet,
                        "apply_link": link,
                        "visa_sponsorship_found": True,
                        "source": site,
                    })
            except Exception as exc:
                logger.debug("Parse error in %s: %s", site, exc)

    logger.info("%s: found %d matching jobs", site, len(jobs))
    return jobs


def scrape_carehome() -> List[Dict]:
    """CareHome.co.uk — uses Playwright."""
    site = "CareHome.co.uk"
    jobs = []
    logger.info("Scraping %s ...", site)

    for term in ["support worker", "care assistant"]:
        url = f"https://www.carehome.co.uk/jobs/search.cfm?keyword={quote_plus(term)}"
        soup = fetch_with_playwright(url, wait_selector="div, a", wait_ms=4000)
        if not soup:
            continue

        # Find job listings — CareHome uses various containers
        results = soup.select("div.job-listing") or soup.select("div.job-result") or \
                  soup.select("tr.job-row") or soup.find_all("div", class_=re.compile(r"job|listing|result", re.I))

        for item in results:
            try:
                a_tag = item.find("a", href=True)
                if not a_tag:
                    continue

                job_title = clean(a_tag.get_text())
                if not matches_title(job_title):
                    continue

                link = a_tag["href"]
                if not link.startswith("http"):
                    link = urljoin("https://www.carehome.co.uk", link)

                full_text = clean(item.get_text())
                company, location, date_posted = "", "", ""

                for tag in item.find_all(["span", "div", "p", "td"]):
                    cls = " ".join(tag.get("class", []))
                    t = clean(tag.get_text())
                    if re.search(r"company|employer|provider|home", cls, re.I) and not company:
                        company = t
                    elif re.search(r"location|area|region", cls, re.I) and not location:
                        location = t
                    elif re.search(r"date|time|posted", cls, re.I) and not date_posted:
                        date_posted = t

                visa_found = has_visa_keywords(full_text)

                if visa_found and is_recent(date_posted):
                    jobs.append({
                        "job_title": job_title,
                        "company_name": company or "Not specified",
                        "location": location or "UK",
                        "date_posted": date_posted or "Recent",
                        "description_snippet": full_text[:300],
                        "apply_link": link,
                        "visa_sponsorship_found": True,
                        "source": site,
                    })
            except Exception as exc:
                logger.debug("Parse error in %s: %s", site, exc)

    logger.info("%s: found %d matching jobs", site, len(jobs))
    return jobs


def scrape_reed() -> List[Dict]:
    """Reed.co.uk — uses requests + BeautifulSoup with correct selectors."""
    site = "Reed.co.uk"
    jobs = []
    logger.info("Scraping %s ...", site)

    search_queries = [
        "support-worker-visa-sponsorship",
        "care-assistant-visa-sponsorship",
        "healthcare-assistant-visa-sponsorship",
    ]

    for query in search_queries:
        url = f"https://www.reed.co.uk/jobs/{query}"
        params = {"sortby": "DisplayDate"}

        soup = fetch_page(url, params=params)
        if not soup:
            # Fallback to Playwright
            full_url = f"{url}?sortby=DisplayDate"
            soup = fetch_with_playwright(full_url, wait_selector="article", wait_ms=4000)
        if not soup:
            continue

        # Reed uses <article> cards
        articles = soup.select("article")
        if not articles:
            articles = soup.find_all("article", class_=re.compile(r"card|job", re.I))

        for article in articles:
            try:
                # Title: h2 > a with class containing jobTitle or gtmJobTitle
                title_el = article.select_one("h2 a") or article.select_one("h3 a")
                if not title_el:
                    continue

                job_title = clean(title_el.get_text())
                if not matches_title(job_title):
                    continue

                link = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin("https://www.reed.co.uk", link)

                # Company: a.gtmJobListingPostedBy or similar
                company = ""
                comp_el = article.select_one("a.gtmJobListingPostedBy") or \
                          article.select_one("a[class*='profileUrl']") or \
                          article.find("a", class_=re.compile(r"postedBy|employer|company", re.I))
                if comp_el:
                    company = clean(comp_el.get_text())

                # Location: li with location data
                location = ""
                loc_el = article.select_one("li[data-qa='job-card-location']")
                if not loc_el:
                    # Fallback: find li that looks like a location (contains comma)
                    for li in article.find_all("li"):
                        t = clean(li.get_text())
                        if "," in t and len(t) < 60:
                            location = t
                            break
                else:
                    location = clean(loc_el.get_text())

                # Date posted
                date_posted = ""
                # Look for date-like text in the card metadata
                for el in article.find_all(["span", "li", "div"]):
                    t = clean(el.get_text())
                    if re.search(r"\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", t, re.I):
                        date_posted = t
                        break
                    elif any(w in t.lower() for w in ["today", "yesterday", "day ago", "days ago", "hour"]):
                        date_posted = t
                        break

                # Description snippet
                snippet = ""
                desc_el = article.select_one("div[class*='Description']") or \
                          article.select_one("p[class*='description']")
                if desc_el:
                    snippet = clean(desc_el.get_text())[:300]
                else:
                    snippet = clean(article.get_text())[:300]

                full_text = f"{job_title} {snippet} {company}".lower()
                visa_found = has_visa_keywords(full_text)

                if visa_found and is_recent(date_posted):
                    jobs.append({
                        "job_title": job_title,
                        "company_name": company or "Not specified",
                        "location": location or "UK",
                        "date_posted": date_posted or "Recent",
                        "description_snippet": snippet,
                        "apply_link": link,
                        "visa_sponsorship_found": True,
                        "source": site,
                    })
            except Exception as exc:
                logger.debug("Parse error in %s: %s", site, exc)

    logger.info("%s: found %d matching jobs", site, len(jobs))
    return jobs


def scrape_nhs() -> List[Dict]:
    """NHS Jobs — uses requests + BeautifulSoup with data-test selectors."""
    site = "NHS Jobs"
    jobs = []
    logger.info("Scraping %s ...", site)

    search_queries = [
        "support worker visa sponsorship",
        "care assistant visa sponsorship",
        "healthcare assistant visa",
    ]

    for query in search_queries:
        url = "https://www.jobs.nhs.uk/candidate/search/results"
        params = {"keyword": query, "distance": "50", "sort": "publicationDateDesc"}

        soup = fetch_page(url, params=params)
        if not soup:
            full_url = f"{url}?keyword={quote_plus(query)}&distance=50&sort=publicationDateDesc"
            soup = fetch_with_playwright(full_url, wait_selector="[data-test='search-result']", wait_ms=4000)
        if not soup:
            continue

        # NHS uses data-test attributes
        results = soup.select("li[data-test='search-result']")
        if not results:
            # Fallback selectors
            results = soup.select(".nhsuk-list-panel") or soup.find_all("li", class_=re.compile(r"vacancy|result", re.I))

        for item in results:
            try:
                # Title: a[data-test="search-result-job-title"]
                title_el = item.select_one("a[data-test='search-result-job-title']")
                if not title_el:
                    title_el = item.select_one("h3 a") or item.find("a")
                if not title_el:
                    continue

                job_title = clean(title_el.get_text())
                if not matches_title(job_title):
                    continue

                link = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin("https://www.jobs.nhs.uk", link)

                # Employer: h3 inside [data-test="search-result-location"]
                company = ""
                loc_container = item.select_one("[data-test='search-result-location']")
                if loc_container:
                    h3 = loc_container.find("h3")
                    if h3:
                        # Employer is the direct text (not the nested location div)
                        company = clean(h3.get_text())

                # Location: .location-font-size inside the location container
                location = ""
                if loc_container:
                    loc_div = loc_container.select_one(".location-font-size")
                    if loc_div:
                        location = clean(loc_div.get_text())

                # Date: li[data-test="search-result-publicationDate"] strong
                date_posted = ""
                date_el = item.select_one("li[data-test='search-result-publicationDate'] strong")
                if not date_el:
                    date_el = item.select_one("li[data-test='search-result-publicationDate']")
                if date_el:
                    date_posted = clean(date_el.get_text())

                # Full text for visa check
                full_text = clean(item.get_text())
                visa_found = has_visa_keywords(full_text) or has_visa_keywords(job_title)

                # For NHS, we searched with "visa sponsorship" so likely all results are relevant
                if is_recent(date_posted):
                    jobs.append({
                        "job_title": job_title,
                        "company_name": company or "NHS",
                        "location": location or "UK",
                        "date_posted": date_posted or "Recent",
                        "description_snippet": full_text[:300],
                        "apply_link": link,
                        "visa_sponsorship_found": visa_found,
                        "source": site,
                    })
            except Exception as exc:
                logger.debug("Parse error in %s: %s", site, exc)

    logger.info("%s: found %d matching jobs", site, len(jobs))
    return jobs


# ──────────────────────────────────────────────────────────────────
# AGGREGATION & DEDUP
# ──────────────────────────────────────────────────────────────────

def scrape_all_sites() -> List[Dict]:
    all_jobs = []
    scrapers = [
        ("Reed.co.uk", scrape_reed),
        ("NHS Jobs", scrape_nhs),
        ("Indeed UK", scrape_indeed),
        ("CareHome.co.uk", scrape_carehome),
        ("Find a Job (DWP)", scrape_findajob),
    ]

    for name, fn in scrapers:
        try:
            all_jobs.extend(fn())
        except Exception as exc:
            logger.error("Scraper '%s' crashed: %s", name, exc)
            logger.debug(traceback.format_exc())

    logger.info("Total raw jobs from all sources: %d", len(all_jobs))
    return all_jobs


def deduplicate(jobs: List[Dict], seen_ids: set) -> List[Dict]:
    new_jobs = []
    for job in jobs:
        jid = job_id(job)
        if jid not in seen_ids:
            new_jobs.append(job)
            seen_ids.add(jid)
    return new_jobs


# ──────────────────────────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────────────────────────

def escape_html(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_telegram(jobs: List[Dict]) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set — skipping")
        return False

    top = jobs[:5]
    lines = [f"🔔 <b>UK Visa Sponsorship Job Alert</b>\n",
             f"Found <b>{len(jobs)}</b> new job(s). Top {len(top)} shown:\n"]

    for i, j in enumerate(top, 1):
        lines.append(f"<b>{i}. {escape_html(j['job_title'])}</b>")
        lines.append(f"🏢 {escape_html(j['company_name'])}")
        lines.append(f"📍 {escape_html(j['location'])}")
        lines.append(f"📅 {escape_html(j['date_posted'])}")
        lines.append(f"🌐 {escape_html(j['source'])}")
        lines.append(f'🔗 <a href="{j["apply_link"]}">Apply</a>')
        lines.append("")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                              json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                logger.info("Telegram alert sent (%d jobs)", len(top))
                return True
            logger.warning("Telegram API %d: %s", r.status_code, r.text[:200])
        except requests.RequestException as exc:
            logger.warning("Telegram attempt %d: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    logger.error("Telegram alert failed")
    return False


def send_telegram_direct(text: str) -> bool:
    """Send a single raw text message to Telegram (used for auto-apply status)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                          json=payload, timeout=REQUEST_TIMEOUT)
        return r.status_code == 200
    except:
        return False


def send_email_direct(subject: str, body: str) -> bool:
    """Send a single raw text email (used for auto-apply status)."""
    if not EMAIL_HOST or not EMAIL_USERNAME or not EMAIL_PASSWORD:
        return False
    recipient = EMAIL_RECIPIENT or EMAIL_USERNAME
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USERNAME
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain"))
    try:
        if EMAIL_PORT == 465:
            with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=REQUEST_TIMEOUT) as s:
                s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                s.sendmail(EMAIL_USERNAME, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=REQUEST_TIMEOUT) as s:
                s.ehlo(); s.starttls(); s.ehlo()
                s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                s.sendmail(EMAIL_USERNAME, [recipient], msg.as_string())
        return True
    except:
        return False


# ──────────────────────────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────────────────────────

def send_email(jobs: List[Dict]) -> bool:
    if not EMAIL_HOST or not EMAIL_USERNAME or not EMAIL_PASSWORD:
        logger.warning("Email credentials not set — skipping")
        return False

    recipient = EMAIL_RECIPIENT or EMAIL_USERNAME
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 {len(jobs)} New Visa-Sponsored Care Jobs — {datetime.now().strftime('%d %b %Y %H:%M')}"
    msg["From"] = EMAIL_USERNAME
    msg["To"] = recipient
    msg.attach(MIMEText(build_email_html(jobs), "html", "utf-8"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if EMAIL_PORT == 465:
                with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=REQUEST_TIMEOUT) as s:
                    s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                    s.sendmail(EMAIL_USERNAME, [recipient], msg.as_string())
            else:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=REQUEST_TIMEOUT) as s:
                    s.ehlo(); s.starttls(); s.ehlo()
                    s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                    s.sendmail(EMAIL_USERNAME, [recipient], msg.as_string())
            logger.info("Email sent to %s (%d jobs)", recipient, len(jobs))
            return True
        except Exception as exc:
            logger.warning("Email attempt %d: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    logger.error("Email alert failed")
    return False


def build_email_html(jobs: List[Dict]) -> str:
    rows = ""
    for i, j in enumerate(jobs, 1):
        bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:10px;border:1px solid #ddd">{i}</td>
          <td style="padding:10px;border:1px solid #ddd"><strong>{j['job_title']}</strong></td>
          <td style="padding:10px;border:1px solid #ddd">{j['company_name']}</td>
          <td style="padding:10px;border:1px solid #ddd">{j['location']}</td>
          <td style="padding:10px;border:1px solid #ddd">{j['date_posted']}</td>
          <td style="padding:10px;border:1px solid #ddd">{j['source']}</td>
          <td style="padding:10px;border:1px solid #ddd">✅</td>
          <td style="padding:10px;border:1px solid #ddd">
            <a href="{j['apply_link']}" style="color:#1a73e8">Apply →</a>
          </td>
        </tr>"""

    no_results = '<p style="margin-top:15px;color:#666">No matching jobs found in this scan.</p>' if not jobs else ''

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:20px;background:#f0f4f8">
  <div style="max-width:950px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)">
    <div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:30px;color:#fff">
      <h1 style="margin:0;font-size:22px">🔔 UK Visa Sponsorship Job Alert</h1>
      <p style="margin:8px 0 0;opacity:.9">{len(jobs)} new care/support worker position(s)<br>
        <small>{datetime.now().strftime('%A, %d %B %Y at %H:%M')}</small></p>
    </div>
    <div style="padding:20px;overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr style="background:#1a73e8;color:#fff">
          <th style="padding:10px;border:1px solid #ddd">#</th>
          <th style="padding:10px;border:1px solid #ddd">Title</th>
          <th style="padding:10px;border:1px solid #ddd">Company</th>
          <th style="padding:10px;border:1px solid #ddd">Location</th>
          <th style="padding:10px;border:1px solid #ddd">Posted</th>
          <th style="padding:10px;border:1px solid #ddd">Source</th>
          <th style="padding:10px;border:1px solid #ddd">Visa</th>
          <th style="padding:10px;border:1px solid #ddd">Link</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>{no_results}
    </div>
    <div style="background:#f5f5f5;padding:15px 30px;text-align:center;color:#888;font-size:12px">
      Job Finder Bot — Scanning 5 UK job boards every 10 minutes
    </div>
  </div>
</body></html>"""


# ──────────────────────────────────────────────────────────────────
# TERMINAL OUTPUT
# ──────────────────────────────────────────────────────────────────

def print_jobs(jobs: List[Dict]) -> None:
    if not jobs:
        print("\n  No new matching jobs found in this scan.\n")
        return
    print(f"\n{'='*70}")
    print(f"  🔔 FOUND {len(jobs)} NEW JOB(S) WITH VISA SPONSORSHIP")
    print(f"{'='*70}\n")
    for i, j in enumerate(jobs, 1):
        print(f"  [{i}] {j['job_title']}")
        print(f"      🏢 {j['company_name']}")
        print(f"      📍 {j['location']}")
        print(f"      📅 {j['date_posted']}")
        print(f"      🌐 {j['source']}")
        print(f"      🔗 {j['apply_link']}")
        print()
    print(f"{'='*70}\n")


# ──────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────────────

def run_job_search() -> None:
    logger.info("=" * 60)
    logger.info("Starting job search cycle at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    seen_ids = load_cache()
    logger.info("Cache: %d previously seen jobs", len(seen_ids))

    all_jobs = scrape_all_sites()
    new_jobs = deduplicate(all_jobs, seen_ids)
    logger.info("New unique jobs after dedup: %d", len(new_jobs))

    save_cache(seen_ids)
    print_jobs(new_jobs)

    if new_jobs:
        # 🔥 PART 5 — INTEGRATE INTO MAIN LOOP
        for job in new_jobs:
            job_title = job['job_title']
            company = job['company_name']
            job_description = job['description_snippet']
            job_url = job['apply_link']

            if skill_match(job_description):
                # 🔥 PART C — MULTI-TEMPLATE COVER LETTER ROTATION
                cover_letter = generate_cover_letter(job_title, company, job_description)

                # 🔥 PART B — RETRY SYSTEM FOR FAILED APPLICATIONS
                max_retries = 3
                attempt = 0
                success = False
                active_platform = "unknown"

                while attempt < max_retries and not success:
                    applied, platform = auto_apply(
                        job_url,
                        cv_path,
                        cover_letter,
                        applicant
                    )
                    active_platform = platform or active_platform
                    if applied:
                        success = True
                    else:
                        attempt += 1
                        print(f"[RETRY] Attempt {attempt} failed — retrying...")

                if success:
                    log_application(job_title, company, job_url, active_platform, "Success")
                    send_telegram_direct(f"Applied successfully on attempt {attempt+1}: {job_title} at {company} on {active_platform} | {job_url}")
                    send_email_direct("Job Applied", f"Applied: {job_title}\nPlatform: {active_platform}\n{job_url}")
                else:
                    log_application(job_title, company, job_url, active_platform, "Failed")
                    print("[AUTO-APPLY] Failed after retries.")
            else:
                continue

        # PART 6 — Standard Notifications
        send_telegram(new_jobs)
        send_email(new_jobs)
    else:
        logger.info("No new jobs — waiting for next scan")

    logger.info("Cycle complete. Next scan in 10 minutes.\n")


def main() -> None:
    print(r"""
     ╔═══════════════════════════════════════════════════════════╗
     ║        UK Visa Sponsorship Job Finder v2.0               ║
     ║   Support Worker · Care Assistant · HCA · Senior Care    ║
     ║                                                          ║
     ║   Sites: Reed | NHS Jobs | Indeed UK | CareHome | DWP    ║
     ║   Engine: Playwright + BeautifulSoup                     ║
     ║   Alerts: Telegram + Email every 10 minutes              ║
     ╚═══════════════════════════════════════════════════════════╝
    """)

    logger.info("Job Finder v2.0 started")

    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("⚠  Playwright not installed — Indeed & DWP scraping disabled")
        logger.warning("   Install: pip install playwright && python -m playwright install chromium")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠  Telegram not configured — alerts disabled")
    if not EMAIL_HOST or not EMAIL_USERNAME or not EMAIL_PASSWORD:
        logger.warning("⚠  Email not configured — alerts disabled")

    # Run immediately
    run_job_search()

    # Schedule every 10 minutes
    schedule.every(10).minutes.do(run_job_search)
    logger.info("Scheduler active — every 10 minutes. Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("\n  👋 Job Finder stopped. Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
