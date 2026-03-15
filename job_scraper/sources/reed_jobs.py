import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

def scrape_jobs():
    """
    Scrapes UK healthcare/support-worker jobs from Reed.co.uk.
    
    Returns:
        list: A list of job dictionaries.
    """
    site_name = "Reed.co.uk"
    base_url = "https://www.reed.co.uk"
    
    # Reed search paths
    queries = [
        "support-worker-visa-sponsorship",
        "care-assistant-visa-sponsorship",
        "healthcare-assistant-visa-sponsorship",
        "health-care-assistant-visa-sponsorship"
    ]
    
    jobs_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for query in queries:
        search_url = f"{base_url}/jobs/{query}"
        params = {"sortby": "DisplayDate"}
        
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Reed uses article tags for job cards
            job_cards = soup.select("article")
            
            for card in job_cards:
                title_el = card.select_one("h2 a") or card.select_one("h3 a")
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                link = urljoin(base_url, title_el["href"])
                
                # Company
                company = "Not Specified"
                comp_el = card.select_one(".posted-by a") or card.select_one(".gtmJobListingPostedBy")
                if comp_el:
                    company = comp_el.get_text(strip=True)
                
                # Location
                location = "UK"
                loc_el = card.select_one(".location") or card.select_one("li[data-qa='job-card-location']")
                if loc_el:
                    location = loc_el.get_text(strip=True)
                
                # Salary
                salary = "Competitive"
                salary_el = card.select_one(".salary") or card.select_one("li[data-qa='job-card-salary']")
                if salary_el:
                    salary = salary_el.get_text(strip=True)
                
                # Description
                description = ""
                desc_el = card.select_one(".description") or card.select_one(".job-result-description")
                if desc_el:
                    description = desc_el.get_text(strip=True)
                else:
                    description = card.get_text(" ", strip=True)
                
                # Date Posted
                date_el = card.select_one(".time") or card.select_one(".posted")
                date_posted = date_el.get_text(strip=True) if date_el else "Today"
                # If date_posted accidentally picked up salary info like "a year"
                if "year" in date_posted.lower() and "ago" not in date_posted.lower():
                    date_posted = "Today"
                
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
