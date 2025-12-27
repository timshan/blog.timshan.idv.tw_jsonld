import os
import requests
import feedparser
import google.generativeai as genai
import json
import re
import time
from urllib.parse import urlparse

# 設定區
BLOG_RSS = "https://blog.timshan.idv.tw/feeds/posts/default?max-results=999&orderby=updated"
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_KV_NAMESPACE_ID = os.environ["CF_KV_NAMESPACE_ID"]
DAILY_LIMIT = 8

# 初始化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

def get_path_from_url(url):
    parsed = urlparse(url)
    return parsed.path

def get_kv_data(key):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            return response.json()
        except:
            return None
    return None

def write_to_kv(key, value):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.put(url, headers=headers, data=value)
    return True

def generate_faq(content, title):
    print(f"      🤖 Asking Gemini: {title[:15]}...")
    prompt = f"""
    你是一個 SEO 專家。請根據以下文章內容，生成 3 個常見問題 (FAQ) 的 Schema.org JSON-LD 程式碼。
    文章標題: {title}
    文章內容: {content[:6000]} 
    規則:
    1. 嚴格遵守 JSON 格式，不要包含 ```json 或 ``` 標記。
    2. 只回傳 JSON 物件本身。
    3. 結構必須是 "FAQPage"。
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return text
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return None

def main():
    print(f"🔍 Reading RSS...")
    feed = feedparser.parse(BLOG_RSS)
    processed_count = 0 

    for i, entry in enumerate(feed.entries):
        if processed_count >= DAILY_LIMIT:
            print(f"🛑 Done for today ({DAILY_LIMIT} articles).")
            break

        url = entry.link
        path = get_path_from_url(url)
        rss_date = entry.updated
        
        print(f"[{i+1}] Checking: {entry.title[:20]}...")
        kv_data = get_kv_data(path)
        
        needs_run = False
        if kv_data is None:
            needs_run = True # 沒資料，要做
        elif kv_data.get("last_updated") != rss_date:
            needs_run = True # 日期不同，重做
        else:
            print(f"   ⏭️ Pass (Latest version)")
            continue

        if needs_run:
            content = entry.get('content', [{'value': entry.summary}])[0]['value']
            faq = generate_faq(content, entry.title)
            if faq:
                payload = json.dumps({"faq_ld": faq, "last_updated": rss_date})
                write_to_kv(path, payload)
                processed_count += 1
                print(f"   ✅ Saved!")
                time.sleep(2)

if __name__ == "__main__":
    main()
