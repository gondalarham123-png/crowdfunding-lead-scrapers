import logging
import os
import random
import re
import time
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- PATH & CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_CSV_FILE = os.path.join(SCRIPT_DIR, "kickstarter_clean_leads.csv")


def get_human_like_browser():
  """Opens an undetected browser that mimics human behavior to bypass firewalls/captchas."""
  options = uc.ChromeOptions()
  options.add_argument("--disable-gpu")
  options.add_argument("--no-sandbox")
  options.add_argument("--disable-dev-shm-usage")
  driver = uc.Chrome(options=options, use_subprocess=True)
  return driver


def scrape_kickstarter_fixed():
  logger.info(
      "🛡️ Opening Human-Like Anti-Bot Browser for Kickstarter Precision"
      " Scraping..."
  )

  # 1. Purani CSV file ko scan karna taakay duplicates skip ho sakein
  existing_urls = set()
  existing_df = pd.DataFrame()

  if os.path.exists(TARGET_CSV_FILE):
    try:
      existing_df = pd.read_csv(TARGET_CSV_FILE)
      if "Project Link" in existing_df.columns:
        existing_urls = set(existing_df["Project Link"].dropna())
      logger.info(
          f"📂 Loaded {len(existing_urls)} existing records from CSV. Skipping"
          " duplicates."
      )
    except Exception as e:
      logger.warning(f"Could not read existing CSV: {e}")

  new_scraped_leads = []
  driver = get_human_like_browser()

  urls_to_explore = [
      (
          "Tech & Innovation",
          "https://www.kickstarter.com/discover/categories/technology",
      ),
      ("Design", "https://www.kickstarter.com/discover/categories/design"),
      ("Games", "https://www.kickstarter.com/discover/categories/games"),
      ("Popular", "https://www.kickstarter.com/discover/popular"),
  ]

  try:
    for cat_name, url in urls_to_explore:
      logger.info(f"🔍 Exploring category like a human: {cat_name}...")
      driver.get(url)
      time.sleep(random.uniform(4, 7))  # Insan ki tarah delay

      # Human ki tarah scroll karna taakay projects load ho jayein
      for _ in range(6):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight/2);"
        )
        time.sleep(random.uniform(2, 3))
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        time.sleep(random.uniform(3, 5))

      # Direct saare project links nikalna (No card dependency)
      all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/projects/']")

      project_links = []
      session_seen = set()

      for link_el in all_links:
        if len(project_links) >= 15:  # Har category se 15 fresh leads
          break
        try:
          p_link = link_el.get_attribute("href")
          if not p_link:
            continue

          # Clean URL (remove query parameters like ?ref=...)
          clean_url = p_link.split("?")[0]

          # Sirf main project link hona chahiye (sub-pages jaise comments/updates nahi)
          if clean_url.count("/") > 5:
            continue

          if clean_url in existing_urls or clean_url in session_seen:
            continue

          session_seen.add(clean_url)
          project_links.append(clean_url)
        except Exception:
          continue

      logger.info(
          f"🔗 Found {len(project_links)} fresh unique links in {cat_name}."
          " Extracting individual details..."
      )

      # Har naye project ke page par alag ja kar exact stats nikalna
      for p_link in project_links:
        try:
          driver.get(p_link)
          time.sleep(random.uniform(4, 7))

          # 1. Project Name
          p_name = ""
          try:
            title_el = driver.find_element(
                By.CSS_SELECTOR, "h1, [class*='Hero'] h2, [data-modal-title]"
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
                By.CSS_SELECTOR,
                "[class*='creator'], [data-creator-name], a[href*='users/']",
            )
            if creator_el:
              creator_name = creator_el.text.strip()
          except Exception:
            pass

          # 3. Total Funds Raised
          total_funds = "N/A"
          try:
            fund_els = driver.find_elements(
                By.CSS_SELECTOR,
                "[data-pledged], [class*='pledged'], span[class*='money'],"
                " div[class*='ns-pledged']",
            )
            for el in fund_els:
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

          # 4. Days Left
          days_left = "N/A"
          try:
            day_els = driver.find_elements(
                By.CSS_SELECTOR,
                "[data-countdown], [class*='countdown'],"
                " [class*='time-left'], [class*='deadline']",
            )
            for el in day_els:
              txt = el.text.strip()
              if any(w in txt.lower() for w in ["day", "hour", "left"]):
                days_left = " ".join(txt.split())
                break

            if days_left == "N/A":
              body_text = driver.find_element(By.TAG_NAME, "body").text
              day_match = re.search(
                  r"(\d+\s*(?:days?|hrs?|hours?)\s*left)",
                  body_text,
                  re.IGNORECASE,
              )
              if day_match:
                days_left = day_match.group(1).strip()
          except Exception:
            pass

          new_scraped_leads.append({
              "Platform": "Kickstarter",
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
  logger.info("=== STARTING KICKSTARTER FIXED PIPELINE ===")

  new_leads, existing_df = scrape_kickstarter_fixed()
  df_new = pd.DataFrame(new_leads)

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
      f"🎉 SUCCESS! Total {len(df_final)} unique Kickstarter records saved"
      f" into '{TARGET_CSV_FILE}'."
  )


if __name__ == "__main__":
  run_pipeline()