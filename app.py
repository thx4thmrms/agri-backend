from flask import Flask, jsonify, request
import requests
import random
import time
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime, timedelta
import sqlite3
from fake_useragent import UserAgent

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ================= 核心配置（无强制代理） =================
KEYWORDS = [
    "大棚 政策", "温室大棚 补贴", "设施农业 扶持", 
    "渔业 新政策", "水产养殖 补贴", "休渔期 调整"
]
SEARCH_ENGINES = [  # 移除腾讯相关，专注通用引擎
    "https://www.baidu.com/s?wd=",   # 百度
    "https://www.bing.com/search?q=",# 必应
    "https://www.so.com/s?q=",       # 360搜索（可选）
]
DB_PATH = "policies.db"  # 数据库存储

# ================= 基础功能（无代理） =================
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            date TEXT,
            content TEXT,
            url TEXT,
            crawled_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fetch_policy_data():
    """核心爬取逻辑（无代理，兼容免费代理可选）"""
    init_db()
    three_months_ago = datetime.now() - timedelta(days=90)
    policy_list = []
    ua = UserAgent()
    
    # 加载历史URL去重
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM policies')
    existing_urls = set(row[0] for row in cursor.fetchall())
    conn.close()

    for keyword in KEYWORDS:
        encoded_keyword = quote(keyword + " 近一季度")
        for engine in SEARCH_ENGINES:
            url = f"{engine}{encoded_keyword}"
            headers = {"User-Agent": ua.random}
            
            try:
                # 无代理模式（默认）
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 通用解析（适配百度/必应/360）
                articles = soup.find_all(['div', 'li'], class_=['result', 'b_algo', 'res-list'])
                for article in articles[:5]:  # 每引擎取前5条，防反爬
                    title_tag = article.find('h3') or article.find('a')
                    if not title_tag:
                        continue
                    
                    title = title_tag.text.strip()
                    url_tag = article.find('a', href=True)
                    article_url = url_tag['href']
                    
                    # 过滤无效链接/重复内容
                    if not article_url.startswith('http') or article_url in existing_urls:
                        continue
                    
                    # 提取摘要（兼容不同引擎结构）
                    content_tag = article.find('p') or article.find('div', class_=['c-abstract', 'res-desc'])
                    content = content_tag.text.strip()[:200] if content_tag else "无摘要..."
                    
                    # 提取日期（百度格式：2025-07-20，必应格式：2025年7月20日）
                    date_tag = article.find('span', class_=['c-color-gray2', 'b_tween', 'res-date'])
                    article_date = datetime.now()
                    if date_tag:
                        date_str = date_tag.text.strip()
                        try:
                            article_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except:
                            try:
                                article_date = datetime.strptime(date_str, '%Y年%m月%d日')
                            except:
                                pass
                    
                    if article_date >= three_months_ago:
                        domain = article_url.split('/')[2]
                        policy_id = f"{domain}-{hash(article_url)}"
                        policy_list.append({
                            "id": policy_id,
                            "title": title,
                            "source": domain,
                            "date": article_date.strftime("%Y-%m-%d"),
                            "content": content,
                            "url": article_url,
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        existing_urls.add(article_url)
                
                time.sleep(random.uniform(1, 3))  # 防反爬延迟
                
            except Exception as e:
                print(f"爬取失败（{engine} | {keyword}）：{str(e)}")
                continue

    # 存储新数据
    if policy_list:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for p in policy_list:
            try:
                cursor.execute('''
                    INSERT INTO policies (id, title, source, date, content, url, crawled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (p['id'], p['title'], p['source'], p['date'], p['content'], p['url'], p['crawled_at']))
            except sqlite3.IntegrityError:
                pass  # 跳过重复
        conn.commit()
        conn.close()

    # 兜底：返回数据库历史数据（最近7天）
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM policies 
        WHERE date >= date('now', '-7 days') 
        ORDER BY crawled_at DESC 
        LIMIT 10
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": row[0], "title": row[1], "source": row[2], 
             "date": row[3], "content": row[4], "url": row[5]} for row in rows]

# ================= 接口定义 =================
@app.route('/api/policies', methods=['GET'])
def get_policies():
    """政策列表接口（无代理，纯搜索引擎爬取）"""
    keyword = request.args.get('keyword', '').strip()
    policies = fetch_policy_data()
    
    # 关键词过滤
    if keyword:
        policies = [p for p in policies if keyword in p['title'] or keyword in p['content']]
    
    return jsonify({
        "code": 200,
        "data": policies,
        "total": len(policies),
        "message": "无代理模式，数据来自搜索引擎（百度/必应）",
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/')
def health_check():
    """健康检查（显示数据库数据量）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM policies')
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({
        "status": "ok",
        "database_count": count,
        "message": "服务运行中（无代理模式，支持关键词搜索）"
    }), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
