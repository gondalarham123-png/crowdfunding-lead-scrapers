# Crowdfunding Lead Generation Scrapers 🚀
Python-based professional web scrapers designed to extract high-value lead data from Kickstarter and Indiegogo for market research and sales outreach.

## Features ✨
- **Anti-Bot Bypass:** Uses `undetected-chromedriver` and human-like random delays to safely bypass Cloudflare and security firewalls.
- **Incremental Scraping:** Automatically cross-references existing CSV data (`kickstarter_clean_leads.csv` / `crowdfunding_clean_leads.csv`) to prevent duplicate entries.
- **Deep-Page Extraction:** Scrapes individual project pages to get precise metrics:
  - Project Name & Clean URL
  - Campaign Creator Name
  - Total Funds Raised
  - Remaining Days / Countdown Stats

## Tech Stack 🛠️
- Python
- Selenium & Undetected ChromeDriver
- Pandas & Regex
