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
        # 抓取摘要 (有些 RSS 是 summary, 有些是 description)
        summary_html = entry.get('summary', entry.get('description', ''))
        
        # 清除 HTML 標籤取得純文字摘要
        soup = BeautifulSoup(summary_html, 'html.parser')
        text_summary = soup.get_text()[:100] + "..." # 只取前100字

        # 抓圖
        image_url = get_image(summary_html)
        if not image_url and 'content' in entry:
             image_url = get_image(entry.content[0].value)

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
