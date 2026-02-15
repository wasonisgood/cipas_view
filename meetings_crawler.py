import requests
from bs4 import BeautifulSoup
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Configuration
BASE_URL = "https://www.cipas.gov.tw"
LIST_URL_TEMPLATE = "https://www.cipas.gov.tw/meetings?&page={}"
MAX_PAGES = 40
OUTPUT_JSON = "meetings_data.json"
OUTPUT_JS = "meetings_data.js"
MAX_WORKERS = 5  # Adjust based on system/network limits

def fetch_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to fetch {url}: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_list_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    
    # Select all meeting items from the list
    # Based on list.html: .col-sm-4 .thumbnail
    thumbnails = soup.select('.col-sm-4 .thumbnail')
    
    for thumb in thumbnails:
        try:
            # Extract Title and Link
            title_tag = thumb.select_one('.caption .doc-title')
            if not title_tag:
                continue
                
            title = title_tag.get_text(strip=True)
            relative_link = title_tag.get('href')
            full_link = BASE_URL + relative_link if relative_link else ""
            
            # Extract ID from link
            # /meetings/508 -> 508
            id_match = re.search(r'/meetings/(\d+)', relative_link)
            item_id = id_match.group(1) if id_match else None
            
            # Extract Date
            date_tag = thumb.select_one('.caption .date')
            date_str = date_tag.get_text(strip=True) if date_tag else ""
            # Format: 2026/02/10 (二) -> 2026/02/10
            clean_date = date_str.split(' ')[0]

            items.append({
                'id': item_id,
                'title': title,
                'date': clean_date,
                'url': full_link,
                'original_date_str': date_str
            })
        except Exception as e:
            print(f"Error parsing item in list: {e}")
            continue
            
    return items

def parse_detail_page(html, item_id):
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract Content
    # Based on item1.html: .article
    article_content = soup.select_one('.article')
    content_html = str(article_content) if article_content else ""
    content_text = article_content.get_text(separator='\\n', strip=True) if article_content else ""
    
    # Extract Files
    # Based on item1.html: .attachfiles li a
    files = []
    file_links = soup.select('.attachfiles li a')
    for link in file_links:
        f_url = link.get('href')
        f_name = link.get('title') or link.get_text(strip=True)
        if f_url:
            files.append({
                'name': f_name.replace('檔案名稱：', '').strip(),
                'url': f_url
            })
            
    return {
        'content_html': content_html,
        'content_text': content_text,
        'files': files
    }

def process_page_range(start_page, end_page):
    all_items = []
    
    # Phase 1: Crawl List Pages
    print(f"Starting crawl for pages {start_page} to {end_page}...")
    
    list_urls = [LIST_URL_TEMPLATE.format(i) for i in range(start_page, end_page + 1)]
    
    # Fetch list pages in parallel
    list_items = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in list_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            html = future.result()
            if html:
                items = parse_list_page(html)
                print(f"Parsed {len(items)} items from {url}")
                list_items.extend(items)
    
    # Deduplicate items based on ID
    unique_items = {item['id']: item for item in list_items if item['id']}
    final_items = list(unique_items.values())
    print(f"Total unique items found: {len(final_items)}")
    
    # Phase 2: Crawl Detail Pages
    print("Starting crawl for detail pages...")
    
    count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_item = {executor.submit(fetch_url, item['url']): item for item in final_items}
        
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                html = future.result()
                details = parse_detail_page(html, item['id'])
                if details:
                    item.update(details)
                else:
                    print(f"Warning: No details found for {item['id']}")
            except Exception as e:
                print(f"Error processing detail {item['id']}: {e}")
            
            count += 1
            if count % 10 == 0:
                print(f"Processed {count}/{len(final_items)} details...")

    return final_items

def save_data(data):
    # Save as JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {OUTPUT_JSON}")
    
    # Save as JS
    js_content = f"const meetingsData = {json.dumps(data, ensure_ascii=False, indent=2)};"
    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"Saved {OUTPUT_JS}")

if __name__ == "__main__":
    # Create a dummy data generator if we can't actually crawl (Agent environment)
    # But the user asked for the crawler code.
    # I will provide the functional crawler code. 
    # To make it usable immediately for the visualization, I will also generating a dummy dataset 
    # if the crawl fails or returns empty (which it might in this restricted env).
    
    try:
        # Attempt to crawl a few pages to see if it works
        # In a real scenario, this runs fully. 
        # For this interaction, I will limit page range if I were running it, 
        # but the code provided is for full 40 pages.
        data = process_page_range(1, MAX_PAGES)
        save_data(data)
    except Exception as e:
        print(f"An error occurred: {e}")
