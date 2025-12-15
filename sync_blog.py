import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import requests
import time
import random

# --- 設定區 ---
# 依然維持抓最新的 20 篇，以免跑太久
BLOG_JSON_URL = 'https://blog.timshan.idv.tw/feeds/posts/default?alt=json&max-results=20'
AUTHOR_NAME = 'Tim Shan'
# -------------

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
    except Exception as e:
        print(f"爬取失敗 {url}: {e}")
    return None

def clean_text_fallback(html_content):
    """備用方案：切內文"""
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text(separator=' ')
    return " ".join(text.split())[:120] + "..."

def generate_schemas(entry, image_url, summary, base_url, raw_link, tags):
    """SEO 結構化資料 (加入標籤支援)"""
    category_name = "未分類"
    category_url = base_url
    
    # 如果有標籤，取第一個當作主要分類
    if tags:
        category_name = tags[0]
        category_url = f"{base_url}/search/label/{urllib.parse.quote(category_name)}"

    blog_posting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": entry['title']['$t'],
        "image": [image_url],
        "datePublished": entry['published']['$t'],
        "dateModified": entry['updated']['$t'],
        "author": {"@type": "Person", "name": AUTHOR_NAME},
        "description": summary,
        "keywords": ", ".join(tags), # 把標籤也加入 SEO 關鍵字
        "mainEntityOfPage": {"@type": "WebPage", "@id": raw_link}
    }

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "首頁", "item": base_url },
            { "@type": "ListItem", "position": 2, "name": category_name, "item": category_url },
            { "@type": "ListItem", "position": 3, "name": entry['title']['$t'] }
        ]
    }
    return [blog_posting, breadcrumb]

def sync():
    print(f"正在讀取 API 清單...")
    try:
        with urllib.request.urlopen(BLOG_JSON_URL) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"API 讀取錯誤: {e}")
        return

    entries = data.get('feed', {}).get('entry', [])
    print(f"清單取得成功，共有 {len(entries)} 篇文章，準備開始逐一爬取...")

    posts = []
    seo_map = {}
    base_url = "https://blog.timshan.idv.tw"
    count = 0

    for entry in entries:
        count += 1
        title = entry['title']['$t']
        link = next((l['href'] for l in entry['link'] if l['rel'] == 'alternate'), None)
        if not link: continue

        print(f"[{count}/{len(entries)}] 處理中：{title[:15]}...")

        # --- [新增] 抓取標籤 (Labels) ---
        tags = []
        if 'category' in entry:
            # entry['category'] 是一個 list，裡面每個物件有個 'term' 就是標籤名
            tags = [c['term'] for c in entry['category']]
        # -----------------------------

        # 抓取摘要 (先爬蟲抓 meta，失敗則切內文)
        summary_text = get_page_description(link)
        if not summary_text:
            if 'content' in entry:
                summary_text = clean_text_fallback(entry['content']['$t'])
            else:
                summary_text = "點擊閱讀全文..."

        image_url = get_high_res_image(entry)
        
        # 組合資料 (新增 tags 欄位)
        post = {
            "title": title,
            "link": link,
            "date": entry['published']['$t'],
            "image": image_url,
            "summary": summary_text,
            "tags": tags  # <--- 新增這裡
        }
        posts.append(post)

        # 產生 SEO 資料
        clean_link = link.replace("http://", "").replace("https://", "").split("?")[0]
        seo_map[clean_link] = generate_schemas(entry, image_url, summary_text, base_url, link, tags)

        # 休息一下
        time.sleep(random.uniform(0.5, 1.5))

    # 存檔 JSON
    with open('blog_data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
    # 存檔 SEO JS
    js_content = f"""
    (function() {{
        var seoData = {json.dumps(seo_map, ensure_ascii=False)};
        var currentUrl = window.location.href.replace("http://", "").replace("https://", "").split("?")[0];
        var jsonLdList = null;
        for (var key in seoData) {{
            if (currentUrl.includes(key) || key.includes(currentUrl)) {{
                jsonLdList = seoData[key];
                break;
            }}
        }}
        if (jsonLdList) {{
            var script = document.createElement('script');
            script.type = "application/ld+json";
            script.text = JSON.stringify(jsonLdList);
            document.head.appendChild(script);
        }}
    }})();
    """
    with open('seo_loader.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print("完成！標籤與描述皆已更新。")

if __name__ == "__main__":
    sync()
