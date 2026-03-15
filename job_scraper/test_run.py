import sys
import os

# Ensure the job_scraper directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from notifications.telegram_client import send_telegram
from notifications.email_client import send_email

def test_upgrade_notifications():
    print("--- Testing Modular Upgrade Notifications ---")
    
    test_job = {
        "title": "Upgrade Test: Healthcare Support Worker",
        "location": "Modular System Test",
        "salary": "N/A",
        "link": "https://example.com/test-job",
        "description": "This is a test notification confirming that the modular upgrade of your job scraper is successful and connected to your alerts."
    }
    
    message = (
        f"🚀 <b>Modular Upgrade Test</b>\n\n"
        f"<b>Title:</b> {test_job['title']}\n"
        f"<b>Location:</b> {test_job['location']}\n"
        f"<b>Link:</b> {test_job['link']}\n"
        f"\n{test_job['description']}"
    )
    
    print("Sending test Telegram alert...")
    send_telegram(message)
    
    print("Sending test Email alert...")
    send_email("Modular Upgrade Test Successful", message.replace("\n", "<br>"))
    
    print("--- Test Complete ---")

if __name__ == "__main__":
    test_upgrade_notifications()
