"""
Test script for JobStreet Indonesia scraper.
Run: python test_jobstreet.py
"""
from jobspy import scrape_jobs

def test_jobstreet_basic():
    """Test scraping JobStreet Indonesia."""
    print("🧪 Testing JobStreet Indonesia scraper...")
    
    jobs = scrape_jobs(
        site_name="jobstreet",
        search_term="software engineer",
        location="Jakarta",
        results_wanted=5,
        verbose=2,
    )
    
    print(f"\n✅ Found {len(jobs)} jobs")
    
    if len(jobs) > 0:
        print("\n📋 Sample results:")
        print(jobs[["site", "title", "company", "location", "job_url"]].head())
    else:
        print("⚠️  No jobs found. This could be due to:")
        print("   - Anti-bot protection")
        print("   - Network issues")
        print("   - HTML structure changes")
        print("\n💡 Try using proxies:")
        print("   proxies=['http://user:pass@proxy:port']")


def test_jobstreet_with_proxies():
    """Test with proxy support."""
    print("\n🧪 Testing JobStreet with proxy support...")
    
    # Replace with your actual proxy
    proxy = None  # "http://user:pass@proxy:port"
    
    if not proxy:
        print("⚠️  No proxy configured. Skipping proxy test.")
        print("   To test with proxy, set proxy variable in script.")
        return
    
    jobs = scrape_jobs(
        site_name="jobstreet",
        search_term="data analyst",
        location="Surabaya",
        results_wanted=3,
        proxies=[proxy],
        verbose=2,
    )
    
    print(f"\n✅ Found {len(jobs)} jobs with proxy")


if __name__ == "__main__":
    test_jobstreet_basic()
    # test_jobstreet_with_proxies()  # Uncomment when proxy is available
    
    print("\n🎉 Test complete!")
