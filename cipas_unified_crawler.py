import requests
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time

BASE_URL = "https://www.cipas.gov.tw"
TARGET_CATEGORIES = {"investigations": "調查進度", "hearings": "聽證程序", "administrative_actions": "行政處分", "litigations": "相關訴訟"}

def advanced_clean_org(name):
    name = re.sub(r'^[：:「」\s]+', '', name)
    name = re.sub(r'^(認定|命|追徵|凍結|處分|因|關於|就|針對|移轉|及其|及其所有之)', '', name)
    if any(k in name for k in ["中央投資", "中投"]): return "中央投資股份有限公司", "中投"
    if "欣裕台" in name: return "欣裕台股份有限公司", ""
    if "中廣" in name or "中國廣播" in name: return "中國廣播股份有限公司", "中廣"
    if "中影" in name: return "中影股份有限公司", "中影"
    if "婦聯" in name or "婦女聯合會" in name: return "中華民國婦女聯合會", "婦聯會"
    if "救國團" in name or "中國青年救國團" in name: return "社團法人中國青年救國團", "救國團"
    if "救助總會" in name or "救總" in name: return "社團法人中華救助總會", "救總"
    if "中國國民黨" in name: return "中國國民黨", ""
    if name in ["民族", "民權", "國家發展"]: name += "基金會"
    if "基金會" in name and "財團法人" not in name: name = "財團法人" + name
    abbr = ""
    abbr_match = re.search(r'[（\(](.*?)[）\)]', name)
    if abbr_match:
        abbr = abbr_match.group(1)
        name = re.sub(r'[（\(].*?[）\)]', '', name).strip()
    name = re.split(r'(?:是否|將|為|之|所有|座落|特定|違法|名下|不當|因$|及$|案$)', name)[0].strip()
    return (name, abbr) if len(name) >= 4 else (None, "")

def analyze_content(title, cat_name):
    actions = []
    if "認定" in title: actions.append("認定")
    if "移轉" in title: actions.append("移轉")
    if "追徵" in title: actions.append("追徵")
    action_type = "、".join(actions) if actions else cat_name
    match = re.search(r'(?:就|針對|命|認定|追徵|凍結|因|關於|處分)(.*?)(?:是否|將|為|之|所有|違法|特定|應|案|$)', title)
    results = []
    if match:
        raw_segment = match.group(1).strip()
        parts = re.split(r'[、及]', raw_segment)
        prefix = "財團法人" if "財團法人" in raw_segment else ("社團法人" if "社團法人" in raw_segment else "")
        suffix = "股份有限公司" if "股份有限公司" in raw_segment else ("基金會" if "基金會" in raw_segment else "")
        for p in parts:
            p = p.strip()
            if not p: continue
            if prefix and prefix not in p: p = prefix + p
            if suffix and suffix not in p and "國民黨" not in p: p = p + suffix
            clean_name, abbr = advanced_clean_org(p)
            if clean_name: results.append({"org_full": clean_name, "org_abbr": abbr, "action": action_type})
    if not results and "中國國民黨" in title: results.append({"org_full": "中國國民黨", "org_abbr": "", "action": action_type})
    return results

def get_detail(info):
    try:
        res = requests.get(info['url'], timeout=10)
        soup = BeautifulSoup(res.text, 'lxml')
        title_el = soup.find('h1', class_='page-header')
        if not title_el: return None
        title = title_el.text.strip()
        
        events = []
        rows = soup.find_all('div', class_='pg-row')
        for row in rows:
            date_el = row.find('div', class_='date')
            caption_el = row.find('div', class_='caption')
            desc_el = row.find('div', class_='desc') # 【新增】抓取詳細描述 (主文)
            
            caption_text = caption_el.text.strip() if caption_el else ""
            desc_text = desc_el.text.strip() if desc_el else ""
            
            if date_el:
                events.append({
                    "date": date_el.text.strip(),
                    "caption": caption_text,
                    "description": desc_text # 這裡保存了處分主文等細節
                })
        
        return {
            "id": f"{info['cat_key']}_{info['url'].split('/').pop().split('?')[0]}",
            "category": info['cat_name'], "category_key": info['cat_key'],
            "url": info['url'], "title": title, 
            "analysis": analyze_content(title, info['cat_name']), 
            "events": events
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    tasks = []
    # 擴大掃描至 10 頁，確保抓取所有歷史處分
    for k, v in TARGET_CATEGORIES.items():
        print(f"掃描 {v}...")
        for p in range(1, 11):
            try:
                soup = BeautifulSoup(requests.get(f"{BASE_URL}/{k}?&page={p}").text, 'lxml')
                links = soup.select('.doc-gallery-view a.doc-title')
                if not links: break # 如果該頁沒連結就停止
                for a in links:
                    tasks.append({"url": BASE_URL + a.get('href'), "cat_name": v, "cat_key": k})
            except: pass
            
    print(f"開始多線程深度抓取 {len(tasks)} 筆資料...")
    with ThreadPoolExecutor(max_workers=10) as ex:
        data = [r for r in list(ex.map(get_detail, tasks)) if r]
    
    with open('cipas_full_data.js', 'w', encoding='utf-8') as f:
        f.write(f"const cipasFullData = {json.dumps(data, ensure_ascii=False, indent=2)};")
    print(f"完成！已成功抓取詳細描述並擴大掃描範圍。")

if __name__ == "__main__":
    main()
