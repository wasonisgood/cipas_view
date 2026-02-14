import requests
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time

BASE_URL = "https://www.cipas.gov.tw"
TARGET_CATEGORIES = {"investigations": "調查進度", "hearings": "聽證程序", "administrative_actions": "行政處分", "litigations": "相關訴訟"}

# 預定義的高頻率核心組織白名單
ORG_WHITE_LIST = [
    "民生建設基金會", "欣光華股份有限公司", "中央投資股份有限公司", 
    "欣裕台股份有限公司", "中影股份有限公司", "中廣股份有限公司", 
    "中國廣播股份有限公司", "中華民國婦女聯合會", "中國青年救國團",
    "中華救助總會", "民族基金會", "民權基金會", "國家發展基金會", "中視"
]

def advanced_clean_org(name):
    # 移除開頭雜訊與動詞
    name = re.sub(r'^[：:「」\s]+', '', name)
    name = re.sub(r'^(認定|命|追徵|凍結|處分|因|關於|就|針對|移轉|及其|及其所有之|申請再次舉行|舉行|關於)', '', name)
    
    # 移除文號 (如：(105)民生字第025號)
    name = re.sub(r'[\(（].*?第.*?號[\)）]', '', name)

    # 智慧補完與正規化
    if "中央投資" in name or "中投" in name: return "中央投資股份有限公司"
    if "欣裕台" in name: return "欣裕台股份有限公司"
    if "民生建設" in name: return "財團法人民生建設基金會"
    if "欣光華" in name: return "欣光華股份有限公司"
    if "婦聯" in name: return "中華民國婦女聯合會"
    if "中影" in name: return "中影股份有限公司"
    if "中廣" in name or "中國廣播" in name: return "中國廣播股份有限公司"
    if "救國團" in name: return "社團法人中國青年救國團"
    if "救助總會" in name or "救總" in name: return "社團法人中華救助總會"
    if "民族基金" in name: return "財團法人民族基金會"
    if "民權基金" in name: return "財團法人民權基金會"
    if "國家發展基金" in name: return "財團法人國家發展基金會"

    # 清理結尾
    name = re.split(r'(?:是否|將|為|之|所有|座落|特定|違法|名下|不當|因$|及$|案$|申請|舉行|預備聽證)', name)[0].strip()
    
    if "中國國民黨" in name: return "中國國民黨"
    if "財團法人" in name or "社團法人" in name or "公司" in name: return name
    
    return name if len(name) >= 4 else None

def analyze_content(title, cat_name):
    results = []
    
    # 策略 1：掃描標題中是否存在白名單組織 (最高優先級)
    for org in ORG_WHITE_LIST:
        if org in title or (len(org) > 4 and org[:4] in title):
            # 這裡我們取標準化後的名稱
            clean, _ = (advanced_clean_org(org), "")
            if clean: results.append({"org_full": clean, "org_abbr": "", "action": cat_name})
    
    if not results:
        # 策略 2：引導式解析 (Regex v5)
        match = re.search(r'(?:就|針對|命|認定|追徵|凍結|因|關於|處分|為|關於)(.*?)(?:是否|將|為|之|所有|違法|特定|應|案|申請|舉行|$)', title)
        if match:
            raw = match.group(1).strip()
            parts = re.split(r'[、及]', raw)
            for p in parts:
                clean = advanced_clean_org(p)
                if clean: results.append({"org_full": clean, "org_abbr": "", "action": cat_name})
        
        # 策略 3：首位式解析 (如果標題開頭就是組織)
        if not results:
            first_words = title[:20]
            # 匹配「財團法人...」、「社團法人...」、「...公司」
            m = re.search(r'^([財社]團法人.*?基金會|[財社]團法人.*?總會|.*?股份有限公司)', first_words)
            if m:
                clean = advanced_clean_org(m.group(1))
                if clean: results.append({"org_full": clean, "org_abbr": "", "action": cat_name})

    if not results and "中國國民黨" in title:
        results.append({"org_full": "中國國民黨", "org_abbr": "", "action": cat_name})
        
    return results

def get_detail(info):
    try:
        res = requests.get(info['url'], timeout=10)
        soup = BeautifulSoup(res.text, 'lxml')
        title = soup.find('h1', class_='page-header').text.strip()
        events = [{"date": r.find('div', class_='date').text.strip(), 
                   "caption": r.find('div', class_='caption').text.strip(),
                   "description": r.find('div', class_='desc').text.strip() if r.find('div', class_='desc') else ""} 
                  for r in soup.find_all('div', class_='pg-row') if r.find('div', class_='date')]
        return {
            "id": f"{info['cat_key']}_{info['url'].split('/').pop().split('?')[0]}",
            "category": info['cat_name'], "category_key": info['cat_key'],
            "url": info['url'], "title": title, "analysis": analyze_content(title, info['cat_name']), "events": events
        }
    except: return None

def main():
    tasks = []
    for k, v in TARGET_CATEGORIES.items():
        for p in range(1, 11):
            try:
                soup = BeautifulSoup(requests.get(f"{BASE_URL}/{k}?&page={p}").text, 'lxml')
                links = soup.select('.doc-gallery-view a.doc-title')
                if not links: break
                for a in links: tasks.append({"url": BASE_URL + a.get('href'), "cat_name": v, "cat_key": k})
            except: pass
    with ThreadPoolExecutor(max_workers=10) as ex:
        data = [r for r in list(ex.map(get_detail, tasks)) if r]
    with open('cipas_full_data.js', 'w', encoding='utf-8') as f:
        f.write(f"const cipasFullData = {json.dumps(data, ensure_ascii=False, indent=2)};")
    print(f"完成！已大幅提升組織解析覆蓋率。")

if __name__ == "__main__":
    main()
