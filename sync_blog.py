import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import requests
import time
import random

# --- 設定區 ---
# 這裡不需要 max-results 了，因為我們會自動翻頁抓全部
# 基礎 URL
BASE_API_URL = 'https://blog.timshan.idv.tw/feeds/posts/default?alt=json&max-results=150'
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
        # 設定 timeout 5秒，避免卡太久
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc.get('content').strip()
    except Exception:
        pass # 失敗就算了，安靜地回傳 None
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
    """SEO 結構化資料"""
    category_name = "未分類"
    category_url = base_url
    
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
        "keywords": ", ".join(tags),
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

def fetch_all_entries():
    """
    [核心新功能] 自動翻頁抓取所有文章清單
    """
    all_entries = []
    next_url = BASE_API_URL
    page_count = 1

    print("開始抓取文章清單...")
    
    while next_url:
        print(f"正在讀取第 {page_count} 頁清單...")
        try:
            with urllib.request.urlopen(next_url) as response:
                data = json.loads(response.read().decode())
                
            feed = data.get('feed', {})
            entries = feed.get('entry', [])
            all_entries.extend(entries)
            
            # 檢查有沒有下一頁 (rel='next')
            next_url = None # 先假設沒有
            for link in feed.get('link', []):
                if link['rel'] == 'next':
                    next_url = link['href']
                    page_count += 1
                    break
        except Exception as e:
            print(f"讀取清單發生錯誤: {e}")
            break
            
    print(f"清單抓取完畢！總共找到 {len(all_entries)} 篇文章。")
    return all_entries

def sync():
    # 1. 先抓取所有文章的原始資料 (這一步很快)
    entries = fetch_all_entries()
    
    posts = []
    seo_map = {}
    base_url = "https://blog.timshan.idv.tw"
    
    # 2. 開始逐一處理 (這一步很慢，因為要爬 meta description)
    total = len(entries)
    print(f"準備開始逐一爬取 {total} 篇文章的描述 (這會花一點時間)...")

    for index, entry in enumerate(entries):
        title = entry['title']['$t']
        
        # 找網址
        link = next((l['href'] for l in entry['link'] if l['rel'] == 'alternate'), None)
        if not link: continue

        # 每 10 篇印一次進度，讓你知道它還在跑
        if (index + 1) % 10 == 0:
            print(f"進度：[{index + 1}/{total}] 處理中...")

        # 抓取標籤
        tags = []
        if 'category' in entry:
            tags = [c['term'] for c in entry['category']]

        # 抓取摘要 (爬 meta -> 失敗切內文)
        summary_text = get_page_description(link)
        if not summary_text:
            if 'content' in entry:
                summary_text = clean_text_fallback(entry['content']['$t'])
            else:
                summary_text = "點擊閱讀全文..."

        image_url = get_high_res_image(entry)
        
        # 組合資料
        post = {
            "title": title,
            "link": link,
            "date": entry['published']['$t'],
            "image": image_url,
            "summary": summary_text,
            "tags": tags
        }
        posts.append(post)

        clean_link = link.replace("http://", "").replace("https://", "").split("?")[0]
        seo_map[clean_link] = generate_schemas(entry, image_url, summary_text, base_url, link, tags)

        # 休息一下 (稍微縮短休息時間，不然幾百篇跑太久)
        time.sleep(random.uniform(0.1, 0.5))

    # 存檔
    with open('blog_data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
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

    print("大功告成！所有文章 (包含舊文章) 都已更新。")

if __name__ == "__main__":
    sync()
