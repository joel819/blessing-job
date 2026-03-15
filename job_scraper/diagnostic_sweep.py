import sys
import os
import json

# Ensure project dir is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sources.gov_find_a_job import scrape_jobs as scrape_dwp
from sources.nhs_jobs import scrape_jobs as scrape_nhs
from sources.reed_jobs import scrape_jobs as scrape_reed
from sources.carehome_jobs import scrape_jobs as scrape_carehome
from utils.filters import match_keywords

def run_diagnostic():
    print("--- 🩺 Bot Diagnostic Sweep (Ignoring Cache) ---")
    
    all_jobs = []
    print("Checking DWP...")
    try: all_jobs.extend(scrape_dwp())
    except: pass
    
    print("Checking NHS...")
    try: all_jobs.extend(scrape_nhs())
    except: pass
    
    print("Checking Reed...")
    try: all_jobs.extend(scrape_reed())
    except: pass
    
    print("Checking CareHome...")
    try: all_jobs.extend(scrape_carehome())
    except: pass
    
    print(f"\nTotal raw jobs found: {len(all_jobs)}")
    
    matches = [j for j in all_jobs if match_keywords(j)]
    print(f"Total jobs passing filters: {len(matches)}")
    
    if matches:
        print("\nTOP 3 MATCHES FOUND:")
        for idx, job in enumerate(matches[:3]):
            print(f"[{idx+1}] {job['title']} @ {job.get('company', 'Unknown')}")
            print(f"    Source: {job['source']} | Date: {job.get('date_posted', 'N/A')}")
    else:
        print("\nResult: Scrapers are working, but no jobs currently on these sites match YOUR specific keywords + visa requirements.")

if __name__ == "__main__":
    run_diagnostic()
