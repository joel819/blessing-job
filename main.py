import os
import json
import time
import re
import schedule

from sources.gov_find_a_job import scrape_jobs as scrape_dwp
from sources.nhs_jobs import scrape_jobs as scrape_nhs
from sources.reed_jobs import scrape_jobs as scrape_reed
from sources.indeed_jobs import scrape_jobs as scrape_indeed
from sources.carehome_jobs import scrape_jobs as scrape_carehome
from notifications.telegram_client import send_telegram
from notifications.email_client import send_email
from utils.filters import match_keywords, generate_job_id, score_job_quality
from utils.application import generate_cover_letter, skill_match, auto_apply
from config import cv_path, applicant, NOTIFICATION_MODE, DAILY_SUMMARY_TIME

CACHE_FILE = "seen_jobs.json"
DAILY_QUEUE_FILE = "daily_queue.json"


def load_seen_ids():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_seen_ids(seen_ids):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_ids), f)


def load_daily_queue():
    if os.path.exists(DAILY_QUEUE_FILE):
        try:
            with open(DAILY_QUEUE_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []


def save_daily_queue(queue):
    with open(DAILY_QUEUE_FILE, "w") as f:
        json.dump(queue, f)


def clear_daily_queue():
    with open(DAILY_QUEUE_FILE, "w") as f:
        json.dump([], f)


def format_notification(job):
    snippet = job.get('description', 'No summary available').strip()
    snippet = re.sub(r'\s+', ' ', snippet)
    if len(snippet) > 250:
        snippet = snippet[:250] + "..."

    quality = score_job_quality(job)
    quality_stars = "⭐" * int(quality / 2)

    return (
        f"📍 <b>{job['title']}</b>\n"
        f"🏢 <i>{job.get('company', 'Not Specified')}</i> | 📅 {job.get('date_posted', 'Today')}\n"
        f"💰 {job.get('salary', 'Competitive')}\n"
        f"🏠 {job.get('location', 'UK')}\n"
        f"⭐ Quality: {quality}/10 {quality_stars}\n"
        f"📝 {snippet}\n"
        f"🔗 <a href='{job['link']}'>Apply on {job.get('source', 'Site')}</a>\n"
        f"──────────────────"
    )


def send_daily_summary():
    """Send all queued jobs as one daily summary message."""
    queue = load_daily_queue()
    if not queue:
        print("No jobs queued for daily summary.")
        return

    print(f"Sending daily summary of {len(queue)} jobs...")

    # Sort by quality score highest first
    queue.sort(key=lambda j: score_job_quality(j), reverse=True)

    telegram_messages = []
    current_msg = f"🌅 <b>DAILY JOB SUMMARY — {len(queue)} NEW OPPORTUNITIES</b>\n"
    current_msg += f"Sorted by quality score ⭐\n"
    current_msg += f"──────────────────\n\n"

    email_content = f"<h2>🔔 Daily Job Summary — {len(queue)} New Jobs Found</h2><hr>"

    for job in queue:
        job_msg = format_notification(job)

        if len(current_msg) + len(job_msg) > 3500:
            telegram_messages.append(current_msg)
            current_msg = job_msg
        else:
            current_msg += job_msg + "\n\n"

        quality = score_job_quality(job)
        email_content += (
            f"<h3>{job['title']} — Quality: {quality}/10</h3>"
            f"<p><b>🏢 Company:</b> {job.get('company', 'Not Specified')}<br>"
            f"<b>📍 Location:</b> {job.get('location', 'UK')}<br>"
            f"<b>💰 Salary:</b> {job.get('salary', 'Not Specified')}<br>"
            f"<b>📅 Posted:</b> {job.get('date_posted', 'Today')}<br>"
            f"<b>🌐 Source:</b> {job.get('source', 'Job Board')}</p>"
            f"<p><i>{job['description'][:300]}...</i></p>"
            f"<a href='{job['link']}'><b>View Job and Apply</b></a><br><hr>"
        )

    telegram_messages.append(current_msg)

    for msg in telegram_messages:
        send_telegram(msg)

    subject = f"Daily Job Summary — {len(queue)} New Opportunities for Blessing"
    send_email(subject, email_content)

    clear_daily_queue()
    print("Daily summary sent and queue cleared.")


def run_scraper_cycle():
    print(f"--- Scraper Cycle Started at {time.strftime('%H:%M:%S')} ---")

    seen_ids = load_seen_ids()
    all_jobs = []

    print("Scraping DWP Find a Job...")
    try:
        all_jobs.extend(scrape_dwp())
    except Exception as e:
        print(f"Error with DWP: {e}")

    print("Scraping NHS Jobs...")
    try:
        all_jobs.extend(scrape_nhs())
    except Exception as e:
        print(f"Error with NHS: {e}")

    print("Scraping Reed.co.uk...")
    try:
        all_jobs.extend(scrape_reed())
    except Exception as e:
        print(f"Error with Reed: {e}")

    print("Scraping Indeed UK...")
    try:
        all_jobs.extend(scrape_indeed())
    except Exception as e:
        print(f"Error with Indeed: {e}")

    print("Scraping CareHome.co.uk...")
    try:
        all_jobs.extend(scrape_carehome())
    except Exception as e:
        print(f"Error with CareHome: {e}")

    print(f"Total raw jobs found: {len(all_jobs)}")

    new_jobs_found = []
    for job in all_jobs:
        job_id = generate_job_id(job)
        if job_id not in seen_ids:
            if match_keywords(job):
                new_jobs_found.append(job)
                seen_ids.add(job_id)

    print(f"New matching jobs: {len(new_jobs_found)}")

    if new_jobs_found:
        # Auto apply logic
        for job in new_jobs_found:
            job_title = job['title']
            company = job.get('company', 'Not Specified')
            job_description = job.get('description', '')
            job_url = job['link']

            if skill_match(job_description):
                cover_letter = generate_cover_letter(
                    job_title, company, job_description
                )
                max_retries = 3
                attempt = 0
                success = False
                active_platform = "unknown"

                while attempt < max_retries and not success:
                    applied, platform = auto_apply(
                        job_url, cv_path, cover_letter, applicant
                    )
                    active_platform = platform or active_platform
                    if applied:
                        success = True
                    else:
                        attempt += 1

                from utils.application import log_application
                status = "Success" if success else "Failed"
                log_application(
                    job_title, company, job_url, active_platform, status
                )

        if NOTIFICATION_MODE == "DAILY":
            # Add to daily queue
            queue = load_daily_queue()
            queue.extend(new_jobs_found)
            save_daily_queue(queue)
            print(f"Added {len(new_jobs_found)} jobs to daily queue. Total queued: {len(queue)}")
        else:
            # INSTANT mode — send immediately
            telegram_messages = []
            current_msg = f"🔔 <b>{len(new_jobs_found)} NEW OPPORTUNITIES FOUND!</b>\n──────────────────\n\n"
            email_content = f"<h2>🔔 {len(new_jobs_found)} New Jobs Found</h2><hr>"

            for job in new_jobs_found:
                job_msg = format_notification(job)
                if len(current_msg) + len(job_msg) > 3500:
                    telegram_messages.append(current_msg)
                    current_msg = job_msg
                else:
                    current_msg += job_msg + "\n\n"

                quality = score_job_quality(job)
                email_content += (
                    f"<h3>{job['title']} — Quality: {quality}/10</h3>"
                    f"<p>{job.get('company', '')} | {job.get('location', 'UK')} | {job.get('salary', '')}</p>"
                    f"<p>{job['description'][:300]}...</p>"
                    f"<a href='{job['link']}'>Apply</a><hr>"
                )

            telegram_messages.append(current_msg)
            for msg in telegram_messages:
                send_telegram(msg)

            send_email(
                f"🔔 {len(new_jobs_found)} New Job Opportunities",
                email_content
            )

        save_seen_ids(seen_ids)

    else:
        print("No new matching jobs found.")

    print("--- Cycle Finished ---")


def main():
    print("--- Job Scraper Started ---")
    print(f"Mode: {NOTIFICATION_MODE}")

    # Run scraper immediately on start
    run_scraper_cycle()

    # Schedule scraper every 10 minutes
    schedule.every(10).minutes.do(run_scraper_cycle)

    # Schedule daily summary if in DAILY mode
    if NOTIFICATION_MODE == "DAILY":
        schedule.every().day.at(DAILY_SUMMARY_TIME).do(send_daily_summary)
        print(f"Daily summary scheduled at {DAILY_SUMMARY_TIME}")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
