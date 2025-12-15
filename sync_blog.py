import feedparser
import json
import re
from bs4 import BeautifulSoup
import os

# --- 請修改這裡 ---
RSS_URL = 'https://blog.timshan.idv.tw/feeds/posts/default?max-results=999&orderby=updated' # 換成你的 RSS 網址
# -----------------

def get_image(html_content):
    """嘗試從文章內容抓取第一張圖片，如果沒有則回傳 None"""
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    img = soup.find('img')
    if img:
        return img.get('src')
    return "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEg5ObeFcmpieWz7g68vuMXYXrf7sQQpj8IhWUWdqhSmWnYJ887gL1oc6Asf5_klvI7vCB9g1v8hd_w8JjL7Hb5xd_5H8onSZFW1J-OoeSGsLqMAHUMqkL5ExR98NMhOjzbtyi3jMYAesBVXqRSfo-xPKl1c7VNgUhF-lBZuLiENOPhgnFupuckw8rOCQIjd/s1600/coverforall.png?text=No+Image" # 預設圖片

def sync():
    feed = feedparser.parse(RSS_URL)
    posts = []

    print(f"找到 {len(feed.entries)} 篇文章")

    for entry in feed.entries:
        # --- 修改開始：超級摘要抓取邏輯 ---
        
        # 1. 嘗試抓取 Atom 的 summary (通常對應 Blogger 的 '搜尋說明')
        raw_summary = entry.get('summary', '')
        
        # 2. 如果沒有 summary，嘗試抓 description (RSS 格式)
        if not raw_summary:
            raw_summary = entry.get('description', '')

        # 3. 清理 HTML 標籤 (因為有時候 description 會包含 HTML)
        text_summary = clean_summary(raw_summary)

        # 4. 如果上面抓完還是空的 (代表你沒寫搜尋說明)，就從內文切 100 字
        if not text_summary and 'content' in entry:
            # entry.content[0].value 是完整的文章 HTML
            full_content = entry.content[0].value
            text_summary = clean_summary(full_content)[:100] + "..."
        
        # 確保如果還是空的，給個預設字
        if not text_summary:
            text_summary = "點擊閱讀全文..."

        # 抓圖 (維持原樣)
        image_url = get_image(raw_summary) # 先試試摘要裡有沒有圖
        if not image_url and 'content' in entry:
             image_url = get_image(entry.content[0].value) # 沒有就去內文找



        post = {
            "title": entry.title,
            "link": entry.link,
            "date": entry.published,
            "image": image_url,
            "summary": text_summary
        }
        posts.append(post)

    # 存成 JSON 檔案
    with open('blog_data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    print("資料已儲存至 blog_data.json")

if __name__ == "__main__":
    sync()
