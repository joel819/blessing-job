import os
import json
import time
import schedule

# Importing modular components
from sources.gov_find_a_job import scrape_jobs as scrape_dwp
from sources.nhs_jobs import scrape_jobs as scrape_nhs
from sources.reed_jobs import scrape_jobs as scrape_reed
from sources.indeed_jobs import scrape_jobs as scrape_indeed
from sources.carehome_jobs import scrape_jobs as scrape_carehome
from notifications.telegram_client import send_telegram
from notifications.email_client import send_email
from utils.filters import match_keywords, generate_job_id
from utils.application import generate_cover_letter, skill_match, auto_apply
from config import cv_path, applicant

# Configuration
# ROLE_KEYWORDS and VISA_KEYWORDS are now managed in utils/filters.py
CACHE_FILE = "seen_jobs.json"

def load_seen_ids():
    """Load previously seen job IDs to avoid duplicate notifications."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_seen_ids(seen_ids):
    """Save seen job IDs to a persistent JSON file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_ids), f)

def format_notification(job):
    """Format the job information into a professional summary."""
    snippet = job.get('description', 'No summary available').strip()
    # Clean up excess whitespace/newlines in snippet
    snippet = re.sub(r'\s+', ' ', snippet)
    if len(snippet) > 250:
        snippet = snippet[:250] + "..."
        
    return (
        f"📍 <b>{job['title']}</b>\n"
        f"🏢 <i>{job.get('company', 'Not Specified')}</i> | 📅 {job.get('date_posted', 'Today')}\n"
        f"💰 {job.get('salary', 'Competitive')}\n"
        f"🏠 {job.get('location', 'UK')}\n"
        f"📝 {snippet}\n"
        f"🔗 <a href='{job['link']}'>Apply on {job.get('source', 'Site')}</a>\n"
        f"──────────────────"
    )

def run_scraper_cycle():
    """Execution cycle for the job scraper."""
    print(f"--- Job Scraper Cycle Started at {time.strftime('%H:%M:%S')} ---")
    
    seen_ids = load_seen_ids()
    
    # 1. Scrape all jobs from all sources
    all_jobs = []
    
    print("Scraping DWP Find a Job...")
    try: all_jobs.extend(scrape_dwp())
    except Exception as e: print(f"Error with DWP: {e}")
    
    print("Scraping NHS Jobs...")
    try: all_jobs.extend(scrape_nhs())
    except Exception as e: print(f"Error with NHS: {e}")
    
    print("Scraping Reed.co.uk...")
    try: all_jobs.extend(scrape_reed())
    except Exception as e: print(f"Error with Reed: {e}")
    
    print("Scraping Indeed UK...")
    try: all_jobs.extend(scrape_indeed())
    except Exception as e: print(f"Error with Indeed: {e}")
    
    print("Scraping CareHome.co.uk...")
    try: all_jobs.extend(scrape_carehome())
    except Exception as e: print(f"Error with CareHome: {e}")
    
    print(f"Total raw jobs found: {len(all_jobs)}")
    
    # 2. Filter for keywords and new IDs
    new_jobs_found = []
    for job in all_jobs:
        job_id = generate_job_id(job)
        if job_id not in seen_ids:
            if match_keywords(job):
                new_jobs_found.append(job)
                seen_ids.add(job_id)
    
    # 3. Handle alerts
    if new_jobs_found:
        print(f"Found {len(new_jobs_found)} NEW matching jobs!")
        
        # Prepare consolidated Email body (HTML)
        email_content = f"<h2>🔔 {len(new_jobs_found)} New Jobs Found</h2><hr>"
        
        # Prepare consolidated Telegram body
        telegram_messages = []
        current_telegram_msg = f"🔔 <b>{len(new_jobs_found)} NEW OPPORTUNITIES FOUND!</b>\n"
        current_telegram_msg += f"──────────────────\n\n"
        
        for job in new_jobs_found:
            # 🔥 PART 5 — INTEGRATE INTO MAIN LOOP
            job_title = job['title']
            company = job.get('company', 'Not Specified')
            job_description = job.get('description', '')
            job_url = job['link']

            # Use the user's prescriptive skill_match and auto_apply logic
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
                
                # 🔥 PART A — ADD APPLICATION LOGGING (Local CSV)
                from utils.application import log_application
                
                if success:
                    log_application(job_title, company, job_url, active_platform, "Success")
                    send_telegram(f"Applied successfully on attempt {attempt+1}: {job_title} at {company} on {active_platform}")
                    send_email("Job Applied", f"Applied: {job_title}\nPlatform: {active_platform}\n{job_url}")
                    auto_apply_status = f"✅ <b>[AUTO-APPLIED on {active_platform}]</b>\n"
                else:
                    log_application(job_title, company, job_url, active_platform, "Failed")
                    print("[AUTO-APPLY] Failed after retries.")
                    auto_apply_status = ""
            else:
                auto_apply_status = ""
                # continue # The user's snippet said continue, but we want to still notify if not auto-applied
            
            # Format for Telegram (Original redesigned format)
            job_msg = format_notification(job)
            if auto_apply_status:
                job_msg = auto_apply_status + job_msg
            
            # Check Telegram character limit (4096). Let's be safe at 3500.
            if len(current_telegram_msg) + len(job_msg) > 3500:
                telegram_messages.append(current_telegram_msg)
                current_telegram_msg = job_msg
            else:
                current_telegram_msg += job_msg + "\n\n"
            
            # Format for Email (HTML)
            auto_apply_label = f"<p style='color: green; font-weight: bold;'>[AUTO-APPLIED]</p>" if auto_apply_status else ""
            email_content += (
                f"{auto_apply_label}"
                f"<h3>{job['title']}</h3>"
                f"<p><b>🏢 Company:</b> {job.get('company', 'Not Specified')}<br>"
                f"<b>📍 Location:</b> {job.get('location', 'UK')}<br>"
                f"<b>💰 Salary:</b> {job.get('salary', 'Not Specified')}<br>"
                f"<b>📅 Posted:</b> {job.get('date_posted', 'Today')}<br>"
                f"<b>🌐 Source:</b> {job.get('source', 'Job Board')}</p>"
                f"<p><i>{job['description'][:300]}...</i></p>"
                f"<a href='{job['link']}'><b>View Job & Apply</b></a><br>"
                f"<hr>"
            )
        
        telegram_messages.append(current_telegram_msg)
        
        # Send Consolidated Telegram Messages
        for msg in telegram_messages:
            send_telegram(msg)
            
        # Send Consolidated Email
        subject = f"🔔 {len(new_jobs_found)} New Job Opportunities Found"
        send_email(subject, email_content)
            
        save_seen_ids(seen_ids)
    else:
        print("No new matching jobs found this round.")
        
    print("--- Job Scraper Cycle Finished ---")

def main():
    """Main entry point with 10-minute scheduler."""
    print("--- Job Scraper Scheduler Started ---")
    
    # Run once immediately
    run_scraper_cycle()
    
    # Schedule to run every 10 minutes
    schedule.every(10).minutes.do(run_scraper_cycle)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
