from job_scraper.utils.application import generate_cover_letter, skill_match

def test_auto_apply_components():
    print("--- Testing Auto-Apply Components ---")
    
    # 1. Test Cover Letter Generation
    job_title = "Senior Support Worker"
    message = generate_cover_letter(job_title)
    print(f"\n[Cover Letter for '{job_title}']:")
    print(message)
    
    # 2. Test Skill Match
    print("\n[Skill Match Tests]:")
    tests = [
        ("Looking for a Support Worker with visa sponsorship", True),
        ("Care Assistant role in a care home", True),
        ("Software Engineer position", False),
        ("Healthcare Assistant Tier 2 sponsorship available", True),
        ("Plumber required for local area", False)
    ]
    
    for desc, expected in tests:
        result = skill_match(desc)
        status = "PASSED" if result == expected else "FAILED"
        print(f"Desc: '{desc[:40]}...' | Match: {result} | {status}")

if __name__ == "__main__":
    test_auto_apply_components()
