from flask import Flask, jsonify, request, send_file
import requests
import time
import threading
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask_cors import CORS
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ========== 配置参数 ==========
REPORT_DIR = "policy_data"
CACHE_FILE = "policy_cache.json"
os.makedirs(REPORT_DIR, exist_ok=True)

# 调整关键词列表，满足要求
KEYWORDS = [
    # 内陆渔业养殖（保持完整）
    "池塘养殖", "淡水养殖", "鱼苗繁育", "循环水养殖", "稻渔综合种养",
    "渔药管理", "水产饲料", "内陆渔业补贴", "养殖尾水处理", "病害防治",
    "渔业生态", "锦鲤养殖", "罗非鱼养殖", "小龙虾养殖", "河蟹养殖",
    
    # 海洋渔业（保持完整）
    "海水养殖", "远洋捕捞", "海洋牧场", "人工鱼礁", "渔具管理",
    "休渔期政策", "海洋渔业补贴", "渔获物加工", "渔业船员培训",
    "水产品质量安全", "深海养殖", "贝类养殖", "藻类养殖", "海水鱼类养殖",
    
    # 渔港与设施
    "渔港建设", "渔港经济区", "渔港升级改造", "渔业码头", "冷藏加工设施",
    "渔船管理", "渔业船舶检验", "渔港环境整治", "避风锚地", "渔港配套服务",
    
    # 大棚种植（仅保留智能大棚）
    "智能大棚",
    
    # 渔业技术（仅保留指定的技术词）
    "水下鱼类识别", "智能监测系统", "鱼类行为分析",
    
    # 政策与资金通用词（保持完整）
    "渔业政策", "农业农村部资金", "渔业发展专项资金", "乡村振兴资金",
    "农业补贴", "渔业保险", "渔业项目申报", "渔业贷款", "设施农业补贴",
    "现代农业产业园", "渔业绿色发展", "生态补偿", "碳汇渔业"
]

# 域名列表（保留主要政府和权威媒体）
ALLOWED_DOMAINS = [
    # 政府网站
    "gov.cn", "agri.gov.cn", "moa.gov.cn", "nynct.gov.cn",
    "ocean.gov.cn", "scsf.gd.gov.cn", "fishery.gov.cn",
    
    # 权威媒体
    "xinhuanet.com", "people.com.cn", "chinafisherynews.com.cn", "modernagri.com.cn",
    
    # 行业网站
    "fish.cn", "fisheryinfo.cn", "chinaaquaculture.com.cn", "greenhouse.cn"
]

# 省份映射（恢复全部省份）
PROVINCE_MAP = {
    "beijing": "北京", "shanghai": "上海", "guangdong": "广东",
    "zhejiang": "浙江", "jiangsu": "江苏", "shandong": "山东",
    "hubei": "湖北", "hunan": "湖南", "sichuan": "四川",
    "henan": "河南", "hebei": "河北", "liaoning": "辽宁",
    "fujian": "福建", "anhui": "安徽", "guangxi": "广西",
    "yunnan": "云南", "guizhou": "贵州", "chongqing": "重庆",
    "tianjin": "天津", "shanxi": "山西", "jilin": "吉林",
    "heilongjiang": "黑龙江", "jiangxi": "江西", "gansu": "甘肃",
    "shaanxi": "陕西", "qinghai": "青海", "ningxia": "宁夏",
    "xinjiang": "新疆", "xizang": "西藏", "hainan": "海南",
    "neimenggu": "内蒙古"
}

# 缓存管理
def load_cached_policies():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                logging.info(f"从缓存加载政策数据: {CACHE_FILE}")
                return json.load(f)
        except Exception as e:
            logging.error(f"加载缓存失败: {e}")
            return []
    return []

def save_cached_policies(policies):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(policies, f, ensure_ascii=False, indent=2)
            logging.info(f"政策数据已保存到缓存: {CACHE_FILE}, 共 {len(policies)} 条")
    except Exception as e:
        logging.error(f"保存缓存失败: {e}")

def merge_policies(old, new):
    old_dict = {p['id']: p for p in old}
    for policy in new:
        old_dict[policy['id']] = policy
    logging.info(f"合并政策数据: 旧数据 {len(old)} 条, 新数据 {len(new)} 条, 合并后 {len(old_dict)} 条")
    return list(old_dict.values())

# 爬取政策数据（优化版）
def fetch_policy_data(full_refresh=False):
    try:
        start_time = time.time()
        logging.info(f"开始爬取数据，{'全量刷新' if full_refresh else '增量更新'}")
        
        policy_list = []
        domains = ALLOWED_DOMAINS if full_refresh else ALLOWED_DOMAINS[:3]  # 非全量时仅爬取部分域名
        
        # 记录各域名爬取情况
        domain_stats = {domain: {"success": 0, "failed": 0} for domain in domains}
        
        for keyword in KEYWORDS:
            for domain in domains:
                try:
                    # 根据域名类型调整搜索URL
                    if domain.endswith(("gov.cn", "agri.gov.cn", "moa.gov.cn")):
                        url = f"https://www.{domain}/s?wd={keyword}"
                    else:
                        url = f"https://www.{domain}/search?q={keyword}"
                    
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
                        "Referer": f"https://www.{domain}/"
                    }
                    
                    # 控制请求频率，增加间隔
                    time.sleep(1.5)
                    
                    request_start = time.time()
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    request_time = time.time() - request_start
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    articles = soup.find_all(['article', 'div', 'li'], 
                                           class_=['news', 'article', 'item'])
                    
                    if not articles:
                        logging.warning(f"在 {domain} 上未找到关于 {keyword} 的文章")
                        continue
                    
                    # 每个页面取前3条数据
                    page_policies = []
                    for article in articles[:3]:
                        title_tag = article.find(['h1', 'h2', 'h3', 'a'], class_=['title', 'news-title'])
                        title = title_tag.text.strip() if title_tag else f"未命名政策_{keyword}"
                        
                        content_tag = article.find(['div', 'p'], class_=['content', 'desc'])
                        content = content_tag.text.strip()[:300] if content_tag else f"关于{keyword}的政策内容"
                        
                        url_tag = article.find('a', href=True)
                        article_url = url_tag['href'] if url_tag else f"https://www.{domain}"
                        if not article_url.startswith(('http://', 'https://')):
                            article_url = f"https://www.{domain}{article_url}"
                        
                        date_tag = article.find(['time', 'span'], class_=['date', 'time'])
                        date = date_tag.text.strip() if date_tag else datetime.now().strftime("%Y-%m-%d")
                        
                        policy = {
                            "title": title,
                            "source": domain,
                            "date": date,
                            "content": content,
                            "url": article_url,
                            "id": f"{domain}-{hash(article_url)}",
                            "category": "policy" if "政策" in keyword else "fund" if "资金" in keyword else "tech",
                            "province": PROVINCE_MAP.get(domain.split('.')[0], "全国")
                        }
                        page_policies.append(policy)
                    
                    policy_list.extend(page_policies)
                    domain_stats[domain]["success"] += 1
                    logging.info(f"从 {domain} 成功爬取 {len(page_policies)} 条关于 {keyword} 的政策，耗时 {request_time:.2f}s")
                    
                except Exception as e:
                    domain_stats[domain]["failed"] += 1
                    logging.error(f"爬取 {domain}（关键词：{keyword}）失败：{str(e)}")
                    continue
        
        # 输出爬取统计
        total_domains = len(domains)
        success_domains = sum(1 for d in domain_stats if domain_stats[d]["success"] > 0)
        total_requests = sum(domain_stats[d]["success"] + domain_stats[d]["failed"] for d in domain_stats)
        success_requests = sum(domain_stats[d]["success"] for d in domain_stats)
        
        logging.info(f"爬取完成：")
        logging.info(f"  - 域名总数：{total_domains}，成功：{success_domains}，失败：{total_domains-success_domains}")
        logging.info(f"  - 请求总数：{total_requests}，成功：{success_requests}，失败：{total_requests-success_requests}")
        logging.info(f"  - 共获取 {len(policy_list)} 条政策数据")
        logging.info(f"  - 总耗时：{time.time()-start_time:.2f}s")
        
        # 合并历史数据
        old_policies = load_cached_policies()
        combined_policies = merge_policies(old_policies, policy_list)
        
        # 保留最近30天的政策，控制数据量
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        recent_policies = [p for p in combined_policies if p['date'] >= thirty_days_ago]
        
        save_cached_policies(recent_policies)
        logging.info(f"数据爬取完成，最终保留 {len(recent_policies)} 条近期政策")
        
        return recent_policies
    
    except Exception as e:
        logging.error(f"整体爬取失败：{str(e)}", exc_info=True)
        return load_cached_policies()

# API接口
@app.route('/api/provinces', methods=['GET'])
def get_provinces():
    provinces = ["all"]
    POLICY_DATA = load_cached_policies()
    if POLICY_DATA:
        unique_provinces = list({policy["province"] for policy in POLICY_DATA})
        provinces.extend(sorted(unique_provinces))
    logging.info(f"获取省份列表：共 {len(provinces)-1} 个省份")
    return jsonify({"code": 200, "data": provinces})

@app.route('/api/policies', methods=['GET'])
def get_policies():
    # 每次请求时检查缓存时效性，超过6小时则更新
    cache_age = time.time() - os.path.getmtime(CACHE_FILE) if os.path.exists(CACHE_FILE) else float('inf')
    logging.info(f"检查缓存时效性：缓存存在时间 {cache_age/3600:.2f} 小时")
    
    if not os.path.exists(CACHE_FILE) or cache_age > 6 * 3600:
        logging.info("缓存已过期，开始更新数据...")
        fetch_policy_data()
    
    POLICY_DATA = load_cached_policies()
    
    if not POLICY_DATA:
        logging.warning("政策数据为空，返回服务不可用")
        return jsonify({"code": 503, "message": "数据加载中，请稍后再试"}), 503
    
    category = request.args.get('category', 'policy')
    province = request.args.get('province', 'all')
    keyword = request.args.get('keyword', '').strip()
    
    filtered = [
        p for p in POLICY_DATA
        if p['category'] == category 
        and (province == 'all' or p['province'] == province) 
        and (keyword == '' or keyword in p['title'] or keyword in p['content'])
    ]
    
    logging.info(f"获取政策列表：分类={category}, 省份={province}, 关键词={keyword}，共返回 {len(filtered)} 条结果")
    return jsonify({"code": 200, "data": filtered, "total": len(filtered)})

@app.route('/api/policy/<string:policy_id>', methods=['GET'])
def get_policy_detail(policy_id):
    POLICY_DATA = load_cached_policies()
    
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        logging.warning(f"未找到政策：ID={policy_id}")
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    
    logging.info(f"获取政策详情：ID={policy_id}, 标题={policy['title']}")
    return jsonify({"code": 200, "data": policy})

@app.route('/api/interpret/<string:policy_id>', methods=['GET'])
def get_ai_interpret(policy_id):
    start_time = time.time()
    logging.info(f"开始AI解读：政策ID={policy_id}")
    
    POLICY_DATA = load_cached_policies()
    
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        logging.warning(f"未找到政策：ID={policy_id}")
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    
    # 从环境变量获取API密钥，或使用默认值
    VEI_API_KEY = os.environ.get("VEI_API_KEY", "sk-1e697322aa3f4cbdbaa9d37fef9066e8ya97b7al4xzsvnkf")
    API_URL = "https://ai-gateway.vei.volces.com/v1/chat/completions"
    
    prompt = f"""请作为农业政策解读专家，分析以下政策的核心要点：
    政策标题：{policy['title']}
    政策内容：{policy['content']}
    发布省份：{policy['province']}
    
    要求：
    1. 分点列出核心信息（政策目的、适用范围、补贴标准等）；
    2. 语言简洁，用中文口语化表达；
    3. 不超过300字。
    """
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {VEI_API_KEY}"
        }
        payload = {
            "model": "doubao-seed-1.6-thinking",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300
        }
        
        logging.info(f"调用AI解读API：政策={policy['title']}")
        api_start = time.time()
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        api_time = time.time() - api_start
        
        result = response.json()
        interpretation = result["choices"][0]["message"]["content"]
        
        logging.info(f"AI解读成功：政策={policy['title']}，耗时={api_time:.2f}s")
        return jsonify({"code": 200, "interpretation": interpretation})
    
    except Exception as e:
        logging.error(f"AI解读调用失败: {str(e)}", exc_info=True)
        fallback = f"【政策核心要点】\n1. 政策主题：{policy['title']}\n2. 发布单位：{policy['source']}\n3. 适用地区：{policy['province']}"
        return jsonify({"code": 200, "interpretation": fallback})

@app.route('/api/reports', methods=['GET'])
def get_reports():
    reports = []
    try:
        for file in os.listdir(REPORT_DIR):
            if file.startswith("daily_report_") and file.endswith(".json"):
                date = file.replace("daily_report_", "").replace(".json", "")
                reports.append({
                    "id": date,
                    "title": f"每日政策报告（{date}）",
                    "summary": f"包含政策数据"
                })
        logging.info(f"获取报告列表：共 {len(reports)} 份报告")
    except Exception as e:
        logging.error(f"获取报告列表失败: {e}")
    
    return jsonify({"code": 200, "data": reports})

@app.route('/api/report/<string:report_id>/download', methods=['GET'])
def download_report(report_id):
    report_file = os.path.join(REPORT_DIR, f"daily_report_{report_id}.json")
    if not os.path.exists(report_file):
        logging.warning(f"报告不存在：ID={report_id}")
        return jsonify({"code": 404, "message": "报告不存在"}), 404
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        logging.info(f"下载报告：ID={report_id}")
        return jsonify({
            "code": 200,
            "download_url": f"https://agri-backend-ame6.onrender.com/api/report/{report_id}/pdf",
            "report_data": report_data
        })
    except Exception as e:
        logging.error(f"读取报告失败: {e}")
        return jsonify({"code": 500, "message": "读取报告失败"}), 500

# 健康检查与定时任务
@app.route('/')
def health_check():
    logging.info("健康检查请求")
    return jsonify({"status": "ok", "message": "Service is running"}), 200

# 手动触发全量刷新的接口
@app.route('/api/refresh', methods=['GET'])
def manual_refresh():
    logging.info("收到手动刷新请求，开始全量刷新...")
    fetch_policy_data(full_refresh=True)
    return jsonify({"status": "success", "message": "数据已全量刷新"})

if __name__ == '__main__':
    logging.info(f"应用启动：端口={os.environ.get('PORT', 5000)}")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
