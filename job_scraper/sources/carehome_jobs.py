import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

def scrape_jobs():
    """
    Scrapes UK healthcare/support-worker jobs from CareHome.co.uk.
    
    Returns:
        list: A list of job dictionaries.
    """
    site_name = "CareHome.co.uk"
    base_url = "https://www.carehome.co.uk"
    
    queries = ["support worker", "care assistant", "healthcare assistant"]
    
    jobs_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for term in queries:
        search_url = f"{base_url}/jobs/search.cfm"
        params = {"keyword": term}
        
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Using specific container for job listings
            job_cards = soup.select("div.job-listing") or soup.select("div.job-result")
            
            for card in job_cards:
                title_el = card.find("a", href=True)
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                link = urljoin(base_url, title_el["href"])
                
                company = "Not Specified"
                location = "UK"
                salary = "Not Specified"
                
                # Attempting to find metadata in the text/tags
                all_text = card.get_text(" ", strip=True)
                
                jobs_list.append({
                    "title": title,
                    "link": link,
                    "location": location,
                    "salary": salary,
                    "company": company,
                    "description": all_text,
                    "date_posted": "Today",
                    "source": site_name
                })
                
        except Exception as e:
            print(f"Error scraping {site_name} for '{term}': {e}")
            
    return jobs_list
