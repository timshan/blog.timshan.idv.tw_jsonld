import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import requests
import time
import random
import os
import google.generativeai as genai

# --- 設定區 ---
# 從 GitHub Secrets 讀取 API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 設定 Gemini 模型 (依照您的指定)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 注意：請確認您的 API Key 帳號權限已開通此預覽模型
    model = genai.GenerativeModel('models/gemini-3-pro-preview')
else:
    print("警告：未偵測到 GEMINI_API_KEY，將跳過 AI 生成步驟。")
    model = None

# 資料來源 (依照您的指定)
FEED_URL = 'https://blog.timshan.idv.tw/feeds/posts/default?alt=json&max-results=999&orderby=updated'
DB_FILENAME = 'blog_data.json'
# -------------

def get_gemini_keywords(text_content):
    """
    呼叫 Gemini API 針對文章內容產生關鍵字
    """
    if not model:
        return []
    
    if not text_content or len(text_content) < 50:
        return []

    try:
        # 限制送給 AI 的字數 (取前 3000 字通常足夠判斷重點)
        prompt = f"""
        請閱讀以下文章內容，並萃取最核心的「10個關鍵字」。
        規則：
        1. 輸出格式僅需關鍵字，用逗號分隔 (例如: 關鍵字1, 關鍵字2, ...)。
        2. 不要包含任何其他說明文字。
        3. 關鍵字請精準，適合用於搜尋引擎或 Chatbot 檢索。
        
        文章內容：
        {text_content[:3000]}
        """
        response = model.generate_content(prompt)
        keywords_str = response.text.strip()
        # 處理回傳格式，轉成 List
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        return keywords[:10]
    except Exception as e:
        print(f"Gemini API 呼叫失敗: {e}")
        return []

def get_high_res_image(entry):
    """取得高畫質縮圖"""
    if 'media$thumbnail' in entry:
        return entry['media$thumbnail']['url'].replace('/s72-c/', '/s1600/')
    return "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEg5ObeFcmpieWz7g68vuMXYXrf7sQQpj8IhWUWdqhSmWnYJ887gL1oc6Asf5_klvI7vCB9g1v8hd_w8JjL7Hb5xd_5H8onSZFW1J-OoeSGsLqMAHUMqkL5ExR98NMhOjzbtyi3jMYAesBVXqRSfo-xPKl1c7VNgUhF-lBZuLiENOPhgnFupuckw8rOCQIjd/s1600/coverforall.png?text=No+Image"

def get_page_description(url):
    """直接飛去該網址，抓取 meta description"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc.get('content').strip()
    except Exception:
        pass
    return None

def clean_text_from_html(html_content):
    """將 HTML 轉為純文字"""
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text(separator=' ')
    return " ".join(text.split())

def load_existing_data():
    """讀取本地現有的 JSON 資料庫"""
    if os.path.exists(DB_FILENAME):
        try:
            with open(DB_FILENAME, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 轉成 Dict 結構，Key 是文章連結 (Link)
                return {item['link']: item for item in data}
        except Exception as e:
            print(f"讀取舊資料失敗: {e}")
    return {}

def fetch_feed_entries():
    """抓取 Atom Feed 資料"""
    print(f"正在抓取 Feed: {FEED_URL} ...")
    try:
        with urllib.request.urlopen(FEED_URL) as response:
            data = json.loads(response.read().decode())
        return data.get('feed', {}).get('entry', [])
    except Exception as e:
        print(f"Feed 抓取失敗: {e}")
        return []

def sync():
    existing_db = load_existing_data()
    print(f"目前資料庫已有 {len(existing_db)} 篇文章。")

    entries = fetch_feed_entries()
    print(f"線上 Feed 共有 {len(entries)} 篇文章。")
    
    final_posts = []
    update_count = 0
    skip_count = 0

    print("開始比對與同步...")

    for index, entry in enumerate(entries):
        title = entry['title']['$t']
        published_date = entry['published']['$t']
        updated_date = entry['updated']['$t']
        
        # 找網址
        link = next((l['href'] for l in entry['link'] if l['rel'] == 'alternate'), None)
        if not link: continue
        
        # --- 增量更新判斷 ---
        need_update = False
        
        # 1. 新文章
        if link not in existing_db:
            print(f"[發現新文章] {title}")
            need_update = True
        # 2. 文章已更新 (比對時間戳記)
        elif existing_db[link].get('updated_date') != updated_date:
            print(f"[文章已更新] {title}")
            need_update = True
        # 3. 缺少 AI 關鍵字 (補跑資料)
        elif 'ai_keywords' not in existing_db[link]:
            print(f"[補充 AI 關鍵字] {title}")
            need_update = True

        if not need_update:
            # 不需要更新，沿用舊資料
            post_data = existing_db[link]
            skip_count += 1
            if index % 50 == 0:
                print(f"跳過未變更文章... (目前進度 {index}/{len(entries)})")
        else:
            # 執行更新
            update_count += 1
            
            raw_content = entry['content']['$t'] if 'content' in entry else ""
            clean_text = clean_text_from_html(raw_content)
            
            summary_text = get_page_description(link)
            if not summary_text:
                summary_text = clean_text[:120] + "..." if clean_text else "點擊閱讀全文..."

            print(f"   L 呼叫 Gemini ({title[:10]}...)...")
            ai_keywords = get_gemini_keywords(clean_text)
            
            image_url = get_high_res_image(entry)
            tags = [c['term'] for c in entry['category']] if 'category' in entry else []

            post_data = {
                "title": title,
                "link": link,
                "published_date": published_date,
                "updated_date": updated_date, # 儲存更新時間
                "image": image_url,
                "summary": summary_text,
                "tags": tags,
                "ai_keywords": ai_keywords,
                "full_text_search": clean_text[:2000] # Line Bot 搜尋用
            }
            
            # 避免 API Rate Limit
            time.sleep(2) 

        final_posts.append(post_data)

    # 存檔
    with open(DB_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_posts, f, ensure_ascii=False, indent=4)

    print("-" * 30)
    print(f"同步完成！")
    print(f"總文章數: {len(final_posts)}")
    print(f"新抓取/更新: {update_count} 篇")
    print(f"未變更/跳過: {skip_count} 篇")

if __name__ == "__main__":
    sync()
