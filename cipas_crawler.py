import requests
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time
import os

# --- Configuration ---
BASE_URL = "https://www.cipas.gov.tw"
LIST_URL = "https://www.cipas.gov.tw/litigations?&page="
MAX_PAGES = 4

def analyze_title(title):
    """
    分析標題，提取針對的組織、其簡稱以及具體行動類型。
    """
    # 1. 行動類型分析
    actions = []
    if "認定" in title and "附隨組織" in title:
        actions.append("認定附隨組織")
    if "移轉" in title:
        actions.append("命其移轉")
    if "追徵" in title:
        actions.append("追徵價額")
    if "凍結" in title:
        actions.append("凍結帳戶")
    if "罰鍰" in title:
        actions.append("處以罰鍰")
    if "提存" in title:
        actions.append("提存法院")
    if "停止執行" in title:
        actions.append("停止執行")
    
    action_type = "、".join(actions) if actions else "其他訴訟"

    # 2. 組織與簡稱提取
    results = []
    content_match = re.search(r'(?:命|認定|追徵|凍結|因)(.*?)(?:將|為|之|所有|違法|特定|應|$)', title)
    if content_match:
        org_segment = content_match.group(1).strip()
        org_list = re.split(r'[、及]', org_segment)
        
        for item in org_list:
            item = item.strip()
            if not item or len(item) < 2: continue
            
            abbr = ""
            abbr_match = re.search(r'[（\(](.*?)[）\)]', item)
            if abbr_match:
                abbr = abbr_match.group(1)
                item = re.sub(r'[（\(].*?[）\)]', '', item).strip()
            
            # 清理組織名稱，移除描述性文字
            item = re.split(r'(?:之|所有|座落|特定|違法)', item)[0].strip()
            
            if item in ["其", "其所有"]: continue
            if len(item) < 2: continue

            results.append({
                "org_full": item,
                "org_abbr": abbr,
                "action": action_type
            })
    
    # 補足「中國國民黨」作為主體的情況
    if "中國國民黨" in title and not any("中國國民黨" in r["org_full"] for r in results):
        results.append({
            "org_full": "中國國民黨",
            "org_abbr": "",
            "action": action_type
        })

    return results

def get_detail_page(url):
    """
    抓取並解析細節頁面。
    """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        title_el = soup.find('h1', class_='page-header')
        if not title_el:
            return None
            
        title = title_el.text.strip()
        analysis = analyze_title(title)
        
        # 提取時間軸/進度
        events = []
        rows = soup.find_all('div', class_='pg-row')
        for row in rows:
            date_el = row.find('div', class_='date')
            caption_el = row.find('div', class_='caption')
            date = date_el.text.strip() if date_el else ""
            caption = caption_el.text.strip() if caption_el else ""
            events.append({"date": date, "caption": caption})
            
        return {
            "url": url,
            "title": title,
            "analysis": analysis,
            "events": events
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    all_links = []
    
    # 1. 抓取列表頁
    print(f"正在掃描前 {MAX_PAGES} 頁列表...")
    for page in range(1, MAX_PAGES + 1):
        try:
            url = f"{LIST_URL}{page}"
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                links = soup.select('.doc-gallery-view a.doc-title')
                for a in links:
                    href = a.get('href')
                    if href:
                        full_url = BASE_URL + href if href.startswith('/') else href
                        all_links.append(full_url)
            time.sleep(0.3)
        except Exception as e:
            print(f"掃描第 {page} 頁時發生錯誤: {e}")

    # 2. 多線程抓取細節頁
    print(f"共發現 {len(all_links)} 個項目。開始多線程抓取...")
    data = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(get_detail_page, all_links))
        data = [r for r in results if r]

    # 3. 匯出結果
    # JSON 格式
    with open('cipas_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # JS 格式
    with open('cipas_data.js', 'w', encoding='utf-8') as f:
        f.write(f"const cipasData = {json.dumps(data, ensure_ascii=False, indent=2)};")
        
    print("\n抓取完成！")
    print(f"共抓取 {len(data)} 筆資料。")
    print("已匯出至 cipas_data.json 與 cipas_data.js")

if __name__ == "__main__":
    main()
