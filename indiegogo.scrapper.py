import logging
import os
import re
import google.generativeai as genai
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- PATH & CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_CSV_FILE = os.path.join(SCRIPT_DIR, "crowdfunding_clean_leads.csv")


def get_live_browser():
  """Opens a real visible Chrome browser for robust scraping."""
  options = Options()
  options.add_argument("--disable-gpu")
  options.add_argument("--no-sandbox")
  options.add_argument("--disable-dev-shm-usage")
  options.add_argument(
      "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
  )

  service = Service(ChromeDriverManager().install())
  driver = webdriver.Chrome(service=service, options=options)
  return driver


def scrape_indiegogo_final_pipeline():
  logger.info("🌐 Opening Chrome browser for smart incremental scraping...")

  # 1. Purani CSV file ko scan karna taakay duplicates skip ho sakein
  existing_urls = set()
  existing_df = pd.DataFrame()

  if os.path.exists(TARGET_CSV_FILE):
    try:
      existing_df = pd.read_csv(TARGET_CSV_FILE)
      if "Project Link" in existing_df.columns:
        existing_urls = set(existing_df["Project Link"].dropna())
      logger.info(
          f"📂 Loaded {len(existing_urls)} existing projects from CSV. Will"
          " skip duplicates."
      )
    except Exception as e:
      logger.warning(f"Could not read existing CSV: {e}")

  new_scraped_leads = []
  driver = get_live_browser()

  categories = [
      ("Tech & Innovation", "https://www.indiegogo.com/explore/tech-innovation"),
      ("Design & Home", "https://www.indiegogo.com/explore/home"),
      ("Gaming", "https://www.indiegogo.com/explore/gaming"),
      ("Health & Fitness", "https://www.indiegogo.com/explore/health"),
      (
          "Creative Works",
          "https://www.indiegogo.com/explore/creative-works",
      ),
      (
          "Community Projects",
          "https://www.indiegogo.com/explore/community",
      ),
  ]

  try:
    for cat_name, url in categories:
      logger.info(
          f"🔍 Exploring category: {cat_name} (Checking for new items)..."
      )
      driver.get(url)
      driver.implicitly_wait(10)

      # Scroll down to load cards
      for _ in range(8):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        driver.implicitly_wait(2)

      cards = driver.find_elements(By.CSS_SELECTOR, ".discovery-card")
      if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='card']")

      project_links = []
      session_seen = set()

      for card in cards:
        if len(project_links) >= 15:  # Har category se 15 fresh leads
          break
        try:
          link_el = card.find_element(By.CSS_SELECTOR, "a")
          p_link = link_el.get_attribute("href")
          if not p_link or "/projects/" not in p_link:
            continue
          clean_url = p_link.split("?")[0]

          # Agar pehle se CSV ya session mein hai toh skip karo
          if clean_url in existing_urls or clean_url in session_seen:
            continue

          session_seen.add(clean_url)
          project_links.append(clean_url)
        except Exception:
          continue

      logger.info(
          f"🔗 Found {len(project_links)} brand new links in {cat_name}. Extracting"
          " individual details..."
      )

      # Har naye project ke page par alag ja kar details nikalna
      for p_link in project_links:
        try:
          driver.get(p_link)
          driver.implicitly_wait(5)

          # 1. Project Name
          p_name = ""
          try:
            title_el = driver.find_element(
                By.CSS_SELECTOR, "h1, [class*='title']"
            )
            if title_el:
              p_name = title_el.text.strip()
          except Exception:
            pass

          if not p_name or len(p_name) < 2:
            slug = p_link.split("/")[-1]
            p_name = slug.replace("-", " ").title()

          # 2. Creator Name
          creator_name = "Campaign Creator"
          try:
            creator_el = driver.find_element(
                By.CSS_SELECTOR, "[class*='creator'], [class*='owner']"
            )
            if creator_el:
              creator_name = creator_el.text.strip()
          except Exception:
            pass

          # 3. Total Funds Raised (Individual Page Scan + Regex)
          total_funds = "N/A"
          try:
            fund_candidates = driver.find_elements(
                By.CSS_SELECTOR,
                "span[class*='money'], div[class*='amount'],"
                " [class*='raised'] span",
            )
            for el in fund_candidates:
              txt = el.text.strip()
              if "$" in txt and any(c.isdigit() for c in txt):
                total_funds = txt
                break

            if total_funds == "N/A":
              body_text = driver.find_element(By.TAG_NAME, "body").text
              match = re.search(r"(\$\s*[\d,]+)", body_text)
              if match:
                total_funds = match.group(1).strip()
          except Exception:
            pass

          # 4. Days Left / Countdown (Individual Page Scan + Regex)
          days_left = "N/A"
          try:
            day_box = driver.find_elements(
                By.CSS_SELECTOR,
                "[class*='countdown'], [class*='time-left'],"
                " [class*='stats'], div[class*='deadline']",
            )
            for box in day_box:
              box_txt = box.text.strip()
              if "DAYS" in box_txt.upper() or "HOURS" in box_txt.upper():
                days_left = " ".join(box_txt.split())
                break

            if days_left == "N/A":
              body_text = driver.find_element(By.TAG_NAME, "body").text
              day_match = re.search(
                  r"(\d+\s*DAYS?[^\n]*\d+\s*HOURS?|[^\\n]*left)",
                  body_text,
                  re.IGNORECASE,
              )
              if day_match:
                days_left = day_match.group(1).strip()
          except Exception:
            pass

          new_scraped_leads.append({
              "Platform": "Indiegogo",
              "Category Name": cat_name,
              "Project Name": p_name,
              "Creator Name": creator_name,
              "Total Funds": total_funds,
              "Days Left": days_left,
              "Project Link": p_link,
          })
        except Exception:
          continue
  except Exception as e:
    logger.error(f"❌ Scraping error: {e}")
  finally:
    try:
      driver.quit()
    except Exception:
      pass

  return new_scraped_leads, existing_df


def run_pipeline():
  logger.info("=== STARTING FINAL SCRAPING PIPELINE ===")

  new_leads, existing_df = scrape_indiegogo_final_pipeline()

  df_new = pd.DataFrame(new_leads)

  # Purane data aur naye data ko apas mein jodna taakay Google Sheet mein sara record update rahy
  if not df_new.empty and not existing_df.empty:
    df_final = pd.concat([existing_df, df_new], ignore_index=True)
  elif not df_new.empty:
    df_final = df_new
  else:
    df_final = existing_df

  if df_final.empty:
    logger.warning("⚠️ No data found to save.")
    return

  df_final.to_csv(TARGET_CSV_FILE, index=False, encoding="utf-8-sig")
  logger.info(
      f"🎉 SUCCESS! Total {len(df_final)} unique leads saved into"
      f" '{TARGET_CSV_FILE}' (Google Sheets Ready)."
  )


if __name__ == "__main__":
  run_pipeline()