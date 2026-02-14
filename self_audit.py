import os
import re

def audit_dashboard():
    print("--- 開始自我稽核程序 ---")
    files_to_check = ['dashboard.html', 'cipas_data.js', 'cipas_all_steps.js']
    errors = []

    # 1. 檢查檔案是否存在
    for f in files_to_check:
        if os.path.exists(f):
            print(f"[*] 檢查檔案: {f} ... 存在")
        else:
            errors.append(f"錯誤: 找不到檔案 {f}")

    if not os.path.exists('dashboard.html'):
        return

    with open('dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 2. 檢查 JS 變數引用
    js_vars = {
        'cipas_data.js': 'cipasData',
        'cipas_all_steps.js': 'cipasAllData'
    }
    
    for js_file, var_name in js_vars.items():
        if os.path.exists(js_file):
            with open(js_file, 'r', encoding='utf-8') as jf:
                js_content = jf.read()
                if var_name not in js_content:
                    errors.append(f"錯誤: {js_file} 中找不到變數 {var_name}")
                if var_name not in content:
                    errors.append(f"警告: dashboard.html 似乎沒有引用 {var_name}")

    # 3. 檢查常見的 JS 錯誤 (如未定義的函數)
    required_functions = ['router', 'renderOverview', 'renderOrgFlow', 'renderCaseCard', 'renderCaseDetail']
    for func in required_functions:
        if f"function {func}" not in content and f"const {func}" not in content:
            errors.append(f"錯誤: dashboard.html 中缺少必要的函數 {func}")

    # 4. 檢查 HTML 標籤閉合 (簡易檢查)
    if content.count('<div') != content.count('</div'):
        errors.append(f"警告: <div> 標籤可能未正確閉合 (開: {content.count('<div')}, 閉: {content.count('</div')})")

    print("\n--- 稽核結果 ---")
    if not errors:
        print("✅ 沒發現明顯錯誤！一切運作正常。")
    else:
        for err in errors:
            print(f"❌ {err}")
    
    return errors

if __name__ == "__main__":
    audit_dashboard()
