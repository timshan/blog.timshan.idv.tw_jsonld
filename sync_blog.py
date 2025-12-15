import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

# --- 設定區 ---
# 注意：這裡改用 alt=json，並抓取最新的 500 篇文章
BLOG_JSON_URL = 'https://blog.timshan.idv.tw/feeds/posts/default?alt=json&max-results=500'
AUTHOR_NAME = 'Tim Shan'
# -------------

def clean_text(html_content):
    """清除 HTML 標籤取得純文字"""
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text().strip()

def get_high_res_image(entry):
    """
    從 JSON 資料中直接取得縮圖，並轉換為高畫質。
    Blogger JSON 預設給 s72-c (72px小圖)，我們把它換成 s1600 (原圖)。
    """
    if 'media$thumbnail' in entry:
        thumb_url = entry['media$thumbnail']['url']
        # 把 /s72-c/ 替換成 /s1600/ 以取得大圖
        return thumb_url.replace('/s72-c/', '/s1600/')
    
    # 如果真的沒圖，回傳預設圖
    return "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEg5ObeFcmpieWz7g68vuMXYXrf7sQQpj8IhWUWdqhSmWnYJ887gL1oc6Asf5_klvI7vCB9g1v8hd_w8JjL7Hb5xd_5H8onSZFW1J-OoeSGsLqMAHUMqkL5ExR98NMhOjzbtyi3jMYAesBVXqRSfo-xPKl1c7VNgUhF-lBZuLiENOPhgnFupuckw8rOCQIjd/s1600/coverforall.png?text=No+Image"

def generate_schemas(entry, image_url, summary, base_url, raw_link):
    """產生 SEO 結構化資料 (與之前邏輯相同)"""
    
    # 1. 抓取分類 (Labels)
    category_name = "未分類"
    category_url = base_url
    
    if 'category' in entry:
        # 取第一個標籤
        tag_term = entry['category'][0]['term']
        category_name = tag_term
        category_url = f"{base_url}/search/label/{urllib.parse.quote(tag_term)}"

    # 2. BlogPosting Schema
    blog_posting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": entry['title']['$t'],
        "image": [image_url],
        "datePublished": entry['published']['$t'],
        "dateModified": entry['updated']['$t'],
        "author": {
            "@type": "Person",
            "name": AUTHOR_NAME
        },
        "description": summary,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": raw_link
        }
    }

    # 3. Breadcrumb Schema
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
    print(f"正在讀取 Blogger JSON API: {BLOG_JSON_URL}")
    
    try:
        with urllib.request.urlopen(BLOG_JSON_URL) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"讀取錯誤: {e}")
        return

    entries = data.get('feed', {}).get('entry', [])
    print(f"找到 {len(entries)} 篇文章")

    posts = []
    seo_map = {}
    
    # 設定首頁網址
    base_url = "https://blog.timshan.idv.tw"

    for entry in entries:
        # 1. 抓取標題
        title = entry['title']['$t']
        
        # 2. 抓取網址 (JSON 裡面的 link 是一個陣列，要找到 rel='alternate' 的那個)
        link = next((l['href'] for l in entry['link'] if l['rel'] == 'alternate'), None)
        if not link: continue

        # 3. 抓取摘要 (這是你最痛的點)
        # 邏輯：如果有 summary 欄位 (搜尋說明)，就用它；否則抓 content (內文) 切 100 字
        if 'summary' in entry:
            summary_text = clean_text(entry['summary']['$t'])
        elif 'content' in entry:
            summary_text = clean_text(entry['content']['$t'])[:100] + "..."
        else:
            summary_text = "點擊閱讀全文..."

        # 確保摘要不為空
        if not summary_text: summary_text = "點擊閱讀全文..."

        # 4. 抓取圖片 (直接用 JSON 欄位，超準)
        image_url = get_high_res_image(entry)
        
        # --- 組合資料 ---
        
        # 給 LINE 用的
        post = {
            "title": title,
            "link": link,
            "date": entry['published']['$t'],
            "image": image_url,
            "summary": summary_text
        }
        posts.append(post)

        # 給 SEO 用的
        clean_link = link.replace("http://", "").replace("https://", "").split("?")[0]
        seo_map[clean_link] = generate_schemas(entry, image_url, summary_text, base_url, link)

    # 存檔 1: LINE 用的 JSON
    with open('blog_data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
    # 存檔 2: SEO 用的 JS
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
            console.log("SEO Data Injected Successfully");
        }}
    }})();
    """
    
    with open('seo_loader.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print("完成！資料已更新 (JSON API 版本)")

if __name__ == "__main__":
    sync()
