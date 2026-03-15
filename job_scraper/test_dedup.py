import sys
import os

# Ensure the job_scraper directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.filters import generate_job_id, match_keywords

def test_deduplication():
    print("--- Testing Cross-Platform Deduplication ---")
    
    # Case 1: Same job, different links
    job_board_a = {
        "title": "Support Worker (Visa Sponsorship)",
        "company": "Better Care LTD",
        "location": "London",
        "link": "https://gov-site.com/job/123"
    }
    
    job_board_b = {
        "title": "Support Worker (Visa Sponsorship)",
        "company": "Better Care LTD",
        "location": "London",
        "link": "https://reed.co.uk/job/abc"
    }
    
    id_a = generate_job_id(job_board_a)
    id_b = generate_job_id(job_board_b)
    
    print(f"Job A ID: {id_a}")
    print(f"Job B ID: {id_b}")
    
    if id_a == id_b:
        print("[PASSED] Same job on different sites generated identical IDs.")
    else:
        print("[FAILED] Same job on different sites generated different IDs.")
        
    # Case 2: Different jobs
    job_c = {
        "title": "Care Assistant",
        "company": "Better Care LTD",
        "location": "London",
        "link": "https://gov-site.com/job/456"
    }
    
    id_c = generate_job_id(job_c)
    print(f"Job C ID: {id_c}")
    
    if id_a != id_c:
        print("[PASSED] Different jobs generated different IDs.")
    else:
        print("[FAILED] Different jobs generated identical IDs.")

if __name__ == "__main__":
    test_deduplication()
