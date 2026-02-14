import requests
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time

# --- Configuration ---
BASE_URL = "https://www.cipas.gov.tw"
CATEGORIES = {
    "investigations": "調查進度",
    "hearings": "聽證程序",
    "administrative_actions": "行政處分"
}
MAX_PAGES = 4

def analyze_content(title, category_name):
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
    if "聽證" in title or category_name == "聽證程序":
        actions.append("舉行聽證")
    if "調查" in title or category_name == "調查進度":
        actions.append("啟動調查")
    
    action_type = "、".join(actions) if actions else category_name

    # 2. 組織與簡稱提取
    results = []
    # 針對調查與聽證的特殊模式優化
    # 例如：就「社團法人中華救助總會」是否為「中國國民黨」之附隨組織進行調查
    content_match = re.search(r'(?:就|關於|針對|命|認定|追徵|凍結|因)(.*?)(?:是否|將|為|之|所有|違法|特定|應|案|$)', title)
    
    if content_match:
        org_segment = content_match.group(1).strip()
        org_segment = org_segment.replace("「", "").replace("」", "")
        org_list = re.split(r'[、及]', org_segment)
        
        for item in org_list:
            item = item.strip()
            if not item or len(item) < 2: continue
            
            abbr = ""
            abbr_match = re.search(r'[（\(](.*?)[）\)]', item)
            if abbr_match:
                abbr = abbr_match.group(1)
                item = re.sub(r'[（\(].*?[）\)]', '', item).strip()
            
            # 清理常見描述詞
            item = re.split(r'(?:是否|之|所有|座落|特定|違法)', item)[0].strip()
            if item in ["其", "其所有", "本會"]: continue
            if len(item) < 2: continue

            results.append({
                "org_full": item,
                "org_abbr": abbr,
                "action": action_type
            })
    
    # 保底：若沒抓到組織但有國民黨字眼
    if not results and "中國國民黨" in title:
        results.append({"org_full": "中國國民黨", "org_abbr": "", "action": action_type})

    return results

def get_detail_page(info):
    """
    抓取並解析細節頁面。
    """
    url = info['url']
    cat_name = info['cat_name']
    cat_key = info['cat_key']
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        title_el = soup.find('h1', class_='page-header')
        if not title_el: return None
            
        title = title_el.text.strip()
        analysis = analyze_content(title, cat_name)
        
        # 提取時間軸
        events = []
        rows = soup.find_all('div', class_='pg-row')
        for row in rows:
            date_el = row.find('div', class_='date')
            caption_el = row.find('div', class_='caption')
            if date_el and caption_el:
                events.append({
                    "date": date_el.text.strip(),
                    "caption": caption_el.text.strip()
                })
            
        return {
            "id": url.split('/').pop().split('?')[0],
            "category": cat_name,
            "category_key": cat_key,
            "url": url,
            "title": title,
            "analysis": analysis,
            "events": events
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    all_tasks = []
    
    for cat_key, cat_name in CATEGORIES.items():
        print(f"正在掃描【{cat_name}】列表...")
        for page in range(1, MAX_PAGES + 1):
            try:
                list_url = f"{BASE_URL}/{cat_key}?&page={page}"
                response = requests.get(list_url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    # 抓取連結（調查/聽證/行政處分的 class 與 litigation 相同）
                    links = soup.select('.doc-gallery-view a.doc-title')
                    for a in links:
                        href = a.get('href')
                        if href:
                            full_url = BASE_URL + href if href.startswith('/') else href
                            all_tasks.append({
                                "url": full_url,
                                "cat_name": cat_name,
                                "cat_key": cat_key
                            })
                time.sleep(0.2)
            except Exception as e:
                print(f"掃描 {cat_name} 第 {page} 頁時出錯: {e}")

    print(f"共發現 {len(all_tasks)} 個項目。開始多線程抓取細節頁與標題...")
    
    final_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(get_detail_page, all_tasks))
        final_data = [r for r in results if r]

    # 匯出
    output_filename = 'cipas_all_steps.json'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    with open('cipas_all_steps.js', 'w', encoding='utf-8') as f:
        f.write(f"const cipasAllData = {json.dumps(final_data, ensure_ascii=False, indent=2)};")
        
    print("\n抓取完成！")
    print(f"共抓取 {len(final_data)} 筆資料。")
    print("已匯出至 cipas_all_steps.json 與 cipas_all_steps.js")

if __name__ == "__main__":
    main()
