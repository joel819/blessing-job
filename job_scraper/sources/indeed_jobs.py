import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

def scrape_jobs():
    """
    Scrapes UK healthcare/support-worker jobs from Indeed UK.
    Note: Indeed often blocks simple requests, so we use common headers.
    
    Returns:
        list: A list of job dictionaries.
    """
    site_name = "Indeed UK"
    base_url = "https://uk.indeed.com"
    
    queries = [
        "support worker visa sponsorship",
        "care assistant visa sponsorship",
        "healthcare assistant visa sponsorship"
    ]
    
    jobs_list = []
    # Indeed is very sensitive; these headers might help but may still fail without Playwright
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    for query in queries:
        search_url = f"{base_url}/jobs"
        params = {
            "q": query,
            "l": "United Kingdom",
            "sort": "date",
            "fromage": "2"
        }
        
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            if response.status_code == 403:
                print(f"Warning: Indeed blocked access (Status 403).")
                continue
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Indeed's structure can be tricky
            job_cards = soup.select("div.job_seen_beacon")
            
            for card in job_cards:
                title_el = card.select_one("a.jcs-JobTitle")
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                link = urljoin(base_url, title_el["href"])
                
                company = "Not Specified"
                comp_el = card.select_one("[data-testid='company-name']")
                if comp_el:
                    company = comp_el.get_text(strip=True)
                
                location = "UK"
                loc_el = card.select_one("[data-testid='text-location']")
                if loc_el:
                    location = loc_el.get_text(strip=True)
                
                salary = "Not Specified"
                salary_el = card.select_one(".salary-snippet-container") or card.select_one(".estimated-salary-container")
                if salary_el:
                    salary = salary_el.get_text(strip=True)
                
                date_el = card.select_one(".date")
                date_posted = date_el.get_text(strip=True) if date_el else "Recently"
                
                description = card.get_text(" ", strip=True)
                
                jobs_list.append({
                    "title": title,
                    "link": link,
                    "location": location,
                    "salary": salary,
                    "company": company,
                    "description": description,
                    "date_posted": date_posted,
                    "source": site_name
                })
                
        except Exception as e:
            print(f"Error scraping {site_name} for '{query}': {e}")
            
    return jobs_list
