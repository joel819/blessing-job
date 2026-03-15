import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

def scrape_jobs():
    """
    Scrapes UK healthcare/support-worker jobs from findajob.dwp.gov.uk.
    
    Returns:
        list: A list of job dictionaries with title, link, location, salary, and description.
    """
    base_url = "https://findajob.dwp.gov.uk"
    # Searching for healthcare and support worker roles
    queries = [
        "healthcare support worker",
        "care assistant visa sponsorship",
        "healthcare assistant visa sponsorship"
    ]
    
    jobs_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for query in queries:
        search_url = f"{base_url}/search?q={quote_plus(query)}&w=&d=15&pp=20"
        try:
            response = requests.get(search_url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Finding job cards based on typical DWP Find a Job structure
            job_cards = soup.find_all("div", class_="search-result")
            
            for card in job_cards:
                title_el = card.find("h3")
                if not title_el:
                    continue
                    
                link_el = title_el.find("a")
                title = title_el.get_text(strip=True)
                link = urljoin(base_url, link_el["href"]) if link_el else ""
                
                # Extracting metadata like location and salary if available
                metadata = card.find_all("li")
                location = "Not Specified"
                salary = "Not Specified"
                
                for item in metadata:
                    text = item.get_text(strip=True)
                    if "Location:" in text:
                        location = text.replace("Location:", "").strip()
                    elif "Salary:" in text or "£" in text:
                        salary = text.replace("Salary:", "").strip()
                
                # Extracting snippet/description
                description = ""
                desc_el = card.find("p", class_="search-result-description")
                if desc_el:
                    description = desc_el.get_text(strip=True)
                else:
                    # Fallback to general text finding if class varies
                    description = card.get_text(strip=True)
                
                # DWP doesn't always show a clear date on the result list, default to "Today"
                date_posted = "Today" 
                
                jobs_list.append({
                    "title": title,
                    "link": link,
                    "location": location,
                    "salary": salary,
                    "description": description,
                    "date_posted": date_posted,
                    "source": "Find a Job"
                })
        except Exception as e:
            print(f"Error during DWP scraping for '{query}': {e}")
        
    return jobs_list
