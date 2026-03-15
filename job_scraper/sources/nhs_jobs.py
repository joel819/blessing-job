import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

def scrape_jobs():
    """
    Scrapes UK healthcare/support-worker jobs from NHS Jobs.
    
    Returns:
        list: A list of job dictionaries.
    """
    site_name = "NHS Jobs"
    base_url = "https://www.jobs.nhs.uk"
    
    # Standard search queries for NHS
    queries = [
        "support worker visa sponsorship",
        "care assistant visa sponsorship",
        "healthcare assistant visa"
    ]
    
    jobs_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for query in queries:
        search_url = f"{base_url}/candidate/search/results"
        params = {
            "keyword": query,
            "distance": "50",
            "sort": "publicationDateDesc"
        }
        
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # NHS Jobs uses data-test attributes for their list items
            job_cards = soup.select("li[data-test='search-result']")
            
            for card in job_cards:
                title_el = card.select_one("a[data-test='search-result-job-title']")
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                link = urljoin(base_url, title_el["href"])
                
                # Location and Employer
                location = "Not Specified"
                company = "NHS"
                
                loc_container = card.select_one("[data-test='search-result-location']")
                if loc_container:
                    h3 = loc_container.find("h3")
                    if h3:
                        company = h3.get_text(strip=True)
                    loc_div = loc_container.select_one(".location-font-size")
                    if loc_div:
                        location = loc_div.get_text(strip=True)
                
                # Salary information
                salary = "Not Specified"
                salary_el = card.select_one("li[data-test='search-result-salary']")
                if salary_el:
                    salary = salary_el.get_text(strip=True)
                
                # Attempt to find date in the card text
                description = card.get_text(" ", strip=True)
                date_posted = "Today"
                # Look for "Posted x days ago" patterns in the text
                date_match = re.search(r'([0-9]+\s+days?\s+ago)', description, re.IGNORECASE)
                if date_match:
                    date_posted = date_match.group(1).capitalize()
                
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
