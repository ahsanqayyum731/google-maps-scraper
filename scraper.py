import time
import re
import threading
import sys
import os
from playwright.sync_api import sync_playwright

# Global scraper state
scraper_state = {
    "status": "idle",       # "idle", "running", "stopping", "completed", "failed"
    "progress": 0,          # 0 to 100
    "message": "Ready to scrape",
    "results": [],          # List of scraped business dicts
    "logs": [],             # Log messages for the console UI
    "current_query": "",
    "current_location": "",
    "total_found": 0,
    "scraped_count": 0
}

state_lock = threading.Lock()

def add_log(message):
    timestamp = time.strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with state_lock:
        scraper_state["logs"].append(log_line)
        # Keep only the last 100 logs
        if len(scraper_state["logs"]) > 100:
            scraper_state["logs"].pop(0)

def set_status(status, message=None, progress=None):
    with state_lock:
        scraper_state["status"] = status
        if message is not None:
            scraper_state["message"] = message
        if progress is not None:
            scraper_state["progress"] = progress

def run_scraper(category, location, limit, headless=True):
    global scraper_state
    
    with state_lock:
        scraper_state["status"] = "running"
        scraper_state["progress"] = 0
        scraper_state["message"] = "Initializing browser..."
        scraper_state["results"] = []
        scraper_state["logs"] = []
        scraper_state["current_query"] = category
        scraper_state["current_location"] = location
        scraper_state["total_found"] = 0
        scraper_state["scraped_count"] = 0
        
    add_log(f"Starting scraper for category: '{category}' in location: '{location}'")
    add_log(f"Limit: {limit} listings. Headless mode: {headless}")
    
    try:
        with sync_playwright() as p:
            browserless_url = os.environ.get("BROWSERLESS_URL")
            if browserless_url:
                add_log("Connecting to remote browser...")
                browser = p.chromium.connect_over_cdp(browserless_url)
            else:
                add_log("Launching Chromium browser locally...")
                browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            
            # Format query for URL
            query = f"{category} in {location}"
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            
            add_log(f"Navigating to Google Maps...")
            page.goto(search_url)
            
            # Wait for search results or body to load
            page.wait_for_timeout(5000)
            
            # Check for consent page or redirections
            if "consent.google.com" in page.url:
                add_log("Consent dialog detected. Accepting...")
                # Try to accept consent
                try:
                    accept_btn = page.locator('form[action*="consent.google.com"] button').first
                    if accept_btn.count() > 0:
                        accept_btn.click()
                        page.wait_for_timeout(3000)
                except Exception as e:
                    add_log(f"Error handling consent page: {e}")
            
            # Wait for feed
            feed_selector = 'div[role="feed"]'
            add_log("Waiting for search results feed...")
            
            try:
                page.wait_for_selector(feed_selector, timeout=10000)
                add_log("Search results feed loaded successfully.")
            except Exception:
                # If there's no scrollable feed, it might be a single result or direct place page
                add_log("Scrollable list feed not found. Checking if Google redirected directly to a single business page...")
                name_elem = page.locator("h1.DUwDvf")
                if name_elem.count() > 0:
                    # Yes, single business page
                    name = name_elem.inner_text()
                    add_log(f"Direct business page found: {name}")
                    # Scrape this single business
                    scraped_data = extract_place_details(page)
                    with state_lock:
                        scraper_state["results"].append(scraped_data)
                        scraper_state["progress"] = 100
                        scraper_state["scraped_count"] = 1
                        scraper_state["total_found"] = 1
                    set_status("completed", f"Scraped 1 business (direct match: {name})", 100)
                    browser.close()
                    return
                else:
                    # Check if there are no results
                    no_results = page.locator('div:has-text("Google Maps can\'t find")')
                    if no_results.count() > 0:
                        raise Exception("Google Maps returned no results for this query.")
                    else:
                        raise Exception("Failed to load search results. Please try again.")
            
            # Scrolling to collect unique place URLs
            add_log("Scrolling panel to discover listings...")
            seen_urls = set()
            no_change_count = 0
            prev_len = 0
            
            feed = page.locator(feed_selector)
            
            while len(seen_urls) < limit:
                with state_lock:
                    if scraper_state["status"] == "stopping":
                        break
                        
                # Scroll down
                try:
                    feed.first.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                except Exception as scroll_err:
                    add_log(f"Scroll helper error: {scroll_err}")
                    break
                page.wait_for_timeout(2000)
                
                # Extract listing hrefs currently loaded in DOM
                try:
                    links = page.locator('a[href*="/maps/place/"]').all()
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href not in seen_urls:
                            seen_urls.add(href)
                except Exception as link_err:
                    add_log(f"Error fetching links: {link_err}")
                
                curr_len = len(seen_urls)
                add_log(f"Found {curr_len} businesses so far...")
                
                with state_lock:
                    scraper_state["total_found"] = curr_len
                
                if curr_len >= limit:
                    add_log(f"Reached target limit of {limit} businesses.")
                    break
                    
                if curr_len == prev_len:
                    no_change_count += 1
                    if no_change_count >= 5:
                        # Check if "You've reached the end of the list." text is visible
                        end_text = page.locator('span:has-text("You\'ve reached the end of the list.")')
                        if end_text.count() > 0:
                            add_log("Reached the end of the list on Google Maps.")
                        else:
                            add_log("No new listings loaded after multiple scrolls. Stopping discovery.")
                        break
                else:
                    no_change_count = 0
                    
                prev_len = curr_len
            
            urls_to_scrape = list(seen_urls)[:limit]
            total_to_scrape = len(urls_to_scrape)
            add_log(f"Starting detailed scraping of {total_to_scrape} businesses...")
            
            with state_lock:
                scraper_state["total_found"] = total_to_scrape
            
            # Scrape details
            for idx, place_url in enumerate(urls_to_scrape):
                with state_lock:
                    if scraper_state["status"] == "stopping":
                        add_log("Scraping stopped by user.")
                        break
                
                add_log(f"Scraping ({idx+1}/{total_to_scrape}) details...")
                
                # Hybrid approach: Try to find listing element in DOM first.
                # If found, click it to avoid full page reload.
                # If not found (virtualized out of DOM), navigate to it directly in the same tab.
                scraped_successfully = False
                
                try:
                    safe_url = place_url.replace('"', '\\"')
                    listing_locator = page.locator(f'a[href="{safe_url}"]')
                    
                    if listing_locator.count() > 0:
                        # Element is in DOM, use fast click
                        listing_locator.first.scroll_into_view_if_needed()
                        page.wait_for_timeout(300)
                        listing_locator.first.evaluate("el => el.click()")
                        page.wait_for_timeout(2000) # Wait for panel update
                        
                        # Verify the title loaded in the panel matches the URL
                        # (just checking if some h1 is visible)
                        if page.locator("h1.DUwDvf").count() > 0:
                            scraped_data = extract_place_details(page)
                            # Add URL
                            scraped_data["maps_url"] = page.url
                            with state_lock:
                                scraper_state["results"].append(scraped_data)
                            add_log(f"Scraped via Click: {scraped_data['name']}")
                            scraped_successfully = True
                    
                    if not scraped_successfully:
                        # Element not in DOM, or click failed to load details. Navigate directly.
                        add_log("Listing not in DOM view. Navigating directly...")
                        page.goto(place_url)
                        page.wait_for_timeout(3000) # Wait for direct load
                        
                        if page.locator("h1.DUwDvf").count() > 0:
                            scraped_data = extract_place_details(page)
                            scraped_data["maps_url"] = place_url
                            with state_lock:
                                scraper_state["results"].append(scraped_data)
                            add_log(f"Scraped via Direct Nav: {scraped_data['name']}")
                            scraped_successfully = True
                        else:
                            add_log("Failed to load details page.")
                            
                except Exception as item_err:
                    add_log(f"Error scraping listing {idx+1}: {item_err}")
                
                with state_lock:
                    scraper_state["scraped_count"] = len(scraper_state["results"])
                    scraper_state["progress"] = int(((idx + 1) / total_to_scrape) * 100)
            
            browser.close()
            
        with state_lock:
            current_status = scraper_state["status"]
            
        if current_status == "stopping":
            set_status("stopped", f"Scraping stopped. Scraped {len(scraper_state['results'])} businesses.")
        else:
            set_status("completed", f"Scraping completed! Successfully scraped {len(scraper_state['results'])} businesses.", 100)
            
    except Exception as e:
        err_msg = str(e)
        if not os.environ.get("BROWSERLESS_URL") and ("Executable doesn't exist" in err_msg or "executable" in err_msg.lower()):
            friendly_err = "Error: Chromium executable not found. Since you are running on Vercel, you must configure a remote browser. Please set the BROWSERLESS_URL environment variable in your Vercel project settings."
            add_log(friendly_err)
            set_status("failed", friendly_err)
        else:
            add_log(f"Scraper error: {err_msg}")
            set_status("failed", f"Failed: {err_msg}")

def extract_place_details(page):
    """Helper to extract details from the opened place details panel"""
    # Name
    name_elem = page.locator("h1.DUwDvf")
    name = name_elem.inner_text() if name_elem.count() > 0 else "N/A"
    
    # Rating & Reviews count
    rating = "N/A"
    reviews = "N/A"
    rating_container = page.locator("div.F7nice")
    if rating_container.count() > 0:
        try:
            spans = rating_container.first.locator("span").all()
            text_spans = [s.inner_text().strip() for s in spans if s.inner_text().strip()]
            
            # Robust parsing of spans
            for s_text in text_spans:
                if s_text.startswith("(") and s_text.endswith(")"):
                    reviews = s_text.replace("(", "").replace(")", "").replace(",", "").strip()
                elif "review" in s_text.lower():
                    reviews = "".join(filter(str.isdigit, s_text))
                elif (s_text.replace(".", "").isdigit() or s_text.replace(",", "").isdigit()) and len(s_text) <= 3 and rating == "N/A":
                    rating = s_text
        except Exception:
            pass
            
    # Category
    category_elem = page.locator("button[jsaction*='category']")
    category = category_elem.first.inner_text() if category_elem.count() > 0 else "N/A"
    
    # Address
    address_elem = page.locator("button[data-item-id='address']")
    address = address_elem.inner_text() if address_elem.count() > 0 else "N/A"
    address = address.replace("", "").strip()
    
    # Website
    website_elem = page.locator("a[data-item-id='authority']")
    website = website_elem.get_attribute("href") if website_elem.count() > 0 else "N/A"
    
    # Phone
    phone_elem = page.locator("button[data-item-id^='phone:tel:']")
    phone = phone_elem.inner_text() if phone_elem.count() > 0 else "N/A"
    phone = phone.replace("", "").strip()
    
    return {
        "name": name,
        "rating": rating,
        "reviews_count": reviews,
        "category": category,
        "address": address,
        "website": website,
        "phone": phone
    }
