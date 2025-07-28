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

# ================= 核心配置 =================
KEYWORDS = [
    # 农业政策
    "农业补贴", "农村金融", "农业用地", "农产品流通",
    "农业合作社", "农业规划", "农业投资", "三农政策",
    
    # 渔业政策（新增渔港、海洋牧场相关）
    "渔业管理", "水产养殖", "渔业资源", "渔港", 
    "渔港建设", "海洋牧场", "远洋渔业", "渔业安全",
    "水生生物", "渔业科技", "渔业经济", "渔业生态",
    
    # 设施农业
    "大棚", "温室", "智能农业", "无土栽培",
    "垂直农业", "植物工厂", "设施农业", "农业设施",
    
    # 科技前沿
    "农业科技", "智慧农业", "数字农业", "农业AI",
    "农业物联网", "农业大数据", "农业机器人", "农业自动化"
]

# 自动扩展关键词（添加"政策"后缀提高命中率）
def expand_keywords(original_keywords):
    expanded = []
    for kw in original_keywords:
        expanded.append(kw)
        if "政策" not in kw and "补贴" not in kw:
            expanded.append(f"{kw} 政策")
    return expanded

EXPANDED_KEYWORDS = expand_keywords(KEYWORDS)
DB_PATH = "policies.db"

# ================= 基础功能 =================
def init_db():
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
            crawled_at TEXT,
            category TEXT
        )
    ''')
    conn.commit()
    conn.close()

def classify_policy(policy):
    """根据标题和内容分类政策类型"""
    title = policy['title']
    content = policy.get('content', '')
    
    if any(kw in title for kw in ['补贴', '资金', '扶持', '奖补', '专项']):
        return "新增专项资金类"
    elif any(kw in title for kw in ['科技', 'AI', '物联网', '数字', '智慧', '创新']):
        return "科技前沿类"
    elif any(kw in title for kw in ['政策', '条例', '办法', '通知', '规划', '意见']):
        return "新增政策类"
    elif any(kw in title for kw in ['渔港', '海洋牧场', '养殖基地', '渔业基地']):
        return "渔港海洋牧场类"
    else:
        return "其他"

def fetch_policy_data():
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

    for keyword in EXPANDED_KEYWORDS:
        encoded_keyword = quote(keyword)
        for engine in ["https://www.baidu.com/s?wd=", "https://www.bing.com/search?q="]:
            url = f"{engine}{encoded_keyword}"
            headers = {"User-Agent": ua.random}
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                articles = soup.find_all(['div', 'li'], class_=['result', 'b_algo'])
                for article in articles[:5]:
                    title_tag = article.find('h3') or article.find('a')
                    if not title_tag:
                        continue
                    
                    title = title_tag.text.strip()
                    url_tag = article.find('a', href=True)
                    article_url = url_tag['href']
                    
                    if not article_url.startswith('http') or article_url in existing_urls:
                        continue
                    
                    content_tag = article.find('p') or article.find('div', class_=['c-abstract', 'b_caption'])
                    content = content_tag.text.strip()[:200] if content_tag else "无摘要..."
                    
                    date_tag = article.find('span', class_=['c-color-gray2', 'b_tween'])
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
                        
                        policy = {
                            "id": policy_id,
                            "title": title,
                            "source": domain,
                            "date": article_date.strftime("%Y-%m-%d"),
                            "content": content,
                            "url": article_url,
                            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # 分类并存储
                        policy['category'] = classify_policy(policy)
                        policy_list.append(policy)
                        existing_urls.add(article_url)
                
                time.sleep(random.uniform(3, 5))  # 延长间隔防反爬
                
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
                    INSERT INTO policies (id, title, source, date, content, url, crawled_at, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (p['id'], p['title'], p['source'], p['date'], p['content'], p['url'], p['crawled_at'], p['category']))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        conn.close()

    # 返回最近7天数据
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM policies 
        WHERE date >= date('now', '-7 days') 
        ORDER BY crawled_at DESC 
        LIMIT 50
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": row[0], "title": row[1], "source": row[2], 
             "date": row[3], "content": row[4], "url": row[5],
             "category": row[6]} for row in rows]

# ================= 接口定义 =================
@app.route('/api/policies', methods=['GET'])
def get_policies():
    keyword = request.args.get('keyword', '').strip()
    policies = fetch_policy_data()
    
    if keyword:
        policies = [p for p in policies if keyword in p['title'] or keyword in p['content']]
    
    return jsonify({
        "code": 200,
        "data": policies,
        "total": len(policies),
        "message": "数据来自搜索引擎（百度/必应）",
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/')
def health_check():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM policies')
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({
        "status": "ok",
        "database_count": count,
        "message": "服务运行中（支持分类和关键词搜索）"
    }), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
