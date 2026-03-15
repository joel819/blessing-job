import sys
import os

# Ensure the job_scraper directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.filters import match_keywords

def test_filtering_accuracy():
    print("--- Testing Stricter Filtering Accuracy ---")
    
    test_cases = [
        {
            "name": "Relevant Case: Support Worker with Visa",
            "job": {
                "title": "Support Worker (Visa Sponsorship)",
                "description": "Looking for a dedicated support worker. We offer skilled worker visa sponsorship for the right candidate."
            },
            "expected": True
        },
        {
            "name": "Irrelevant Case: Podiatrist with Visa",
            "job": {
                "title": "Specialist Podiatrist",
                "description": "Join our healthcare team as a specialist podiatrist. Sponsorship available."
            },
            "expected": False
        },
        {
            "name": "Negative Case: Care Assistant (No Sponsorship)",
            "job": {
                "title": "Care Assistant",
                "description": "Experience required. Note: We cannot provide sponsorship at this time."
            },
            "expected": False
        },
        {
            "name": "Broad Match Case: Random Job with 'Care' word",
            "job": {
                "title": "Customer Care Specialist",
                "description": "Deliver excellent service. Sponsorship not available."
            },
            "expected": False
        }
    ]
    
    passed = 0
    for case in test_cases:
        result = match_keywords(case["job"])
        status = "PASSED" if result == case["expected"] else "FAILED"
        print(f"[{status}] {case['name']} - Got: {result}")
        if status == "PASSED":
            passed += 1
            
    print(f"\n--- Result: {passed}/{len(test_cases)} tests passed ---")
    return passed == len(test_cases)

if __name__ == "__main__":
    test_filtering_accuracy()
