from flask import Flask, jsonify, request, send_file
import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import os
import uuid
from bs4 import BeautifulSoup
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

# 关键词列表
KEYWORDS = [
    # 内陆渔业养殖
    "池塘养殖", "淡水养殖", "鱼苗繁育", "循环水养殖", "稻渔综合种养",
    "渔药管理", "水产饲料", "内陆渔业补贴", "养殖尾水处理", "病害防治",
    "渔业生态", "锦鲤养殖", "罗非鱼养殖", "小龙虾养殖", "河蟹养殖",
    
    # 海洋渔业
    "海水养殖", "远洋捕捞", "海洋牧场", "人工鱼礁", "渔具管理",
    "休渔期政策", "海洋渔业补贴", "渔获物加工", "渔业船员培训",
    "水产品质量安全", "深海养殖", "贝类养殖", "藻类养殖", "海水鱼类养殖",
    
    # 渔港与设施
    "渔港建设", "渔港经济区", "渔港升级改造", "渔业码头", "冷藏加工设施",
    "渔船管理", "渔业船舶检验", "渔港环境整治", "避风锚地", "渔港配套服务",
    
    # 大棚种植
    "智能大棚",
    
    # 渔业技术
    "水下鱼类识别", "智能监测系统", "鱼类行为分析",
    
    # 政策与资金通用词
    "渔业政策", "农业农村部资金", "渔业发展专项资金", "乡村振兴资金",
    "农业补贴", "渔业保险", "渔业项目申报", "渔业贷款", "设施农业补贴",
    "现代农业产业园", "渔业绿色发展", "生态补偿", "碳汇渔业"
]

# 域名列表（移除当前无法访问的域名）
ALLOWED_DOMAINS = [
    # 政府网站
    "gov.cn",
    "agri.gov.cn",  # 农业农村部
    "moa.gov.cn",   # 农业部
    "fishery.gov.cn",  # 渔业局（保留，可能需进一步验证）
    
    # 权威媒体
    "xinhuanet.com",  # 新华网
    "people.com.cn",  # 人民网
    "modernagri.com.cn",  # 现代农业网
    
    # 行业网站
    "fish.cn",  # 中国渔业网
    "fisheryinfo.cn",  # 渔业信息网
    "chinaaquaculture.com.cn"  # 中国水产养殖网
]

# 省份映射
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

# 随机User-Agent池（增加更多浏览器版本）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.46"
]

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

# 多线程爬取函数（优化版）
def crawl_keyword(keyword, domains, result_list, stats):
    """单关键词爬取线程"""
    for domain in domains:
        try:
            # 动态构造URL（根据域名类型选择不同的搜索路径）
            if domain == "gov.cn":
                url = f"https://sousuo.gov.cn/s.htm?q={keyword}"
            elif domain == "people.com.cn":
                url = f"https://search.people.com.cn/search.do?q={keyword}"  # 修正人民网搜索路径
            elif domain in ["agri.gov.cn", "moa.gov.cn"]:
                url = f"https://www.{domain}/s?wd={keyword}"
            else:
                url = f"https://www.{domain}/search?q={keyword}"
            
            # 随机请求头（增加Referer和其他必要headers）
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": f"https://www.{domain}/",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0"
            }
            
            # 随机间隔（1-2秒），降低请求频率
            time.sleep(random.uniform(1.0, 2.0))
            
            # 发送请求（增加重试机制）
            session = requests.Session()
            retries = 3
            for attempt in range(retries):
                try:
                    response = session.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if attempt == retries - 1:
                        raise  # 最后一次重试失败，抛出异常
                    logging.warning(f"请求 {url} 失败，重试 {attempt+1}/{retries}: {e}")
                    time.sleep(2 ** attempt)  # 指数退避
            
            # 解析内容
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all(['article', 'div', 'li'], class_=['news', 'article', 'item', 'list-item'])
            
            if not articles:
                logging.info(f"在 {domain} 上未找到关于 '{keyword}' 的文章")
                continue
            
            # 提取政策信息
            for article in articles[:3]:  # 每页最多提取3条
                title_tag = article.find(['h1', 'h2', 'h3', 'a'], class_=['title', 'news-title', 'article-title'])
                if not title_tag:
                    continue  # 跳过没有标题的项
                
                title = title_tag.text.strip() if title_tag else f"未命名政策_{keyword}"
                
                content_tag = article.find(['div', 'p'], class_=['content', 'desc', 'summary'])
                content = content_tag.text.strip()[:300] if content_tag else f"关于{keyword}的政策内容"
                
                url_tag = article.find('a', href=True)
                if not url_tag:
                    continue  # 跳过没有链接的项
                
                article_url = url_tag['href']
                if not article_url.startswith(('http://', 'https://')):
                    base_url = f"https://www.{domain}"
                    article_url = f"{base_url}{article_url}" if article_url.startswith('/') else f"{base_url}/{article_url}"
                
                date_tag = article.find(['time', 'span', 'div'], class_=['date', 'time', 'publish-time'])
                date = date_tag.text.strip() if date_tag else datetime.now().strftime("%Y-%m-%d")
                
                # 标准化日期格式
                if date and len(date) >= 10:
                    try:
                        date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
                        date = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        # 如果日期格式不符合预期，使用当前日期
                        date = datetime.now().strftime("%Y-%m-%d")
                
                # 生成唯一ID
                policy_id = f"{domain}-{uuid.uuid4().hex[:8]}"
                
                # 确定政策类别
                category = "policy"  # 默认类别
                if "政策" in keyword or "通知" in title or "办法" in title:
                    category = "policy"
                elif "资金" in keyword or "补贴" in title or "支持" in title:
                    category = "fund"
                elif "技术" in keyword or "研究" in title or "系统" in title:
                    category = "tech"
                
                # 确定省份
                province = PROVINCE_MAP.get(domain.split('.')[0], "全国")
                
                policy = {
                    "title": title,
                    "source": domain,
                    "date": date,
                    "content": content,
                    "url": article_url,
                    "id": policy_id,
                    "category": category,
                    "province": province
                }
                
                result_list.append(policy)
                stats[domain]["success"] += 1
                logging.info(f"成功从 {domain} 抓取政策: {title}")
                
        except Exception as e:
            stats[domain]["failed"] += 1
            logging.error(f"爬取 {domain}（关键词：{keyword}）失败：{str(e)}")
            continue

# 爬取政策数据（增强版）
def fetch_policy_data(full_refresh=False):
    try:
        start_time = time.time()
        logging.info(f"开始爬取数据，{'全量刷新' if full_refresh else '增量更新'}")
        
        # 结果容器与统计
        policy_list = []
        domains = ALLOWED_DOMAINS
        domain_stats = {domain: {"success": 0, "failed": 0} for domain in domains}
        
        # 多线程爬取（根据服务器配置调整线程数）
        with ThreadPoolExecutor(max_workers=3) as executor:  # 降低线程数以减少压力
            futures = []
            for keyword in KEYWORDS:
                # 每个关键词分配一个线程
                future = executor.submit(
                    crawl_keyword, 
                    keyword, 
                    domains, 
                    policy_list, 
                    domain_stats
                )
                futures.append(future)
            
            # 等待所有线程完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"爬取线程异常: {e}")
        
        # 统计与合并数据
        total_success = sum(stats["success"] for stats in domain_stats.values())
        total_failed = sum(stats["failed"] for stats in domain_stats.values())
        
        logging.info(f"爬取完成：总成功 {total_success} 条，失败 {total_failed} 条，耗时 {time.time()-start_time:.2f}s")
        
        # 合并缓存并过滤
        old_policies = load_cached_policies()
        combined_policies = merge_policies(old_policies, policy_list)
        
        # 保留30天内数据或重要政策（含"政策"、"补贴"等关键词的保留60天）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        
        recent_policies = []
        for p in combined_policies:
            if "政策" in p["title"] or "补贴" in p["title"] or "资金" in p["title"]:
                if p["date"] >= sixty_days_ago:
                    recent_policies.append(p)
            else:
                if p["date"] >= thirty_days_ago:
                    recent_policies.append(p)
        
        # 按日期排序（最新的在前）
        recent_policies.sort(key=lambda x: x["date"], reverse=True)
        
        save_cached_policies(recent_policies)
        return recent_policies
    
    except Exception as e:
        logging.error(f"整体爬取失败：{str(e)}", exc_info=True)
        # 返回现有缓存，避免接口无响应
        return load_cached_policies()

# API接口
@app.route('/api/provinces', methods=['GET'])
def get_provinces():
    provinces = ["all"]
    POLICY_DATA = load_cached_policies()
    if POLICY_DATA:
        unique_provinces = list({policy["province"] for policy in POLICY_DATA})
        provinces.extend(sorted(unique_provinces))
    return jsonify({"code": 200, "data": provinces})

@app.route('/api/policies', methods=['GET'])
def get_policies():
    try:
        # 检查缓存状态
        cache_exists = os.path.exists(CACHE_FILE)
        cache_age = time.time() - os.path.getmtime(CACHE_FILE) if cache_exists else float('inf')
        
        if not cache_exists or cache_age > 6 * 3600:  # 缓存超过6小时
            logging.info("缓存已过期，开始更新数据...")
            fetch_policy_data()
        else:
            logging.info(f"使用现有缓存，缓存年龄: {cache_age/3600:.2f} 小时")
        
        POLICY_DATA = load_cached_policies()
        if not POLICY_DATA:
            return jsonify({"code": 503, "message": "数据加载中，请稍后再试"}), 503
        
        # 处理查询参数
        category = request.args.get('category', 'policy')
        province = request.args.get('province', 'all')
        keyword = request.args.get('keyword', '').strip()
        
        # 过滤数据
        filtered = [
            p for p in POLICY_DATA
            if p['category'] == category 
            and (province == 'all' or p['province'] == province) 
            and (keyword == '' or keyword.lower() in p['title'].lower() or keyword.lower() in p['content'].lower())
        ]
        
        return jsonify({"code": 200, "data": filtered, "total": len(filtered)})
    
    except Exception as e:
        logging.error(f"获取政策列表失败: {str(e)}")
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500

@app.route('/api/policy/<string:policy_id>', methods=['GET'])
def get_policy_detail(policy_id):
    try:
        POLICY_DATA = load_cached_policies()
        policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
        
        if not policy:
            return jsonify({"code": 404, "message": "政策不存在"}), 404
        
        return jsonify({"code": 200, "data": policy})
    except Exception as e:
        logging.error(f"获取政策详情失败: {str(e)}")
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500

@app.route('/api/interpret/<string:policy_id>', methods=['GET'])
def get_ai_interpret(policy_id):
    try:
        POLICY_DATA = load_cached_policies()
        policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
        
        if not policy:
            return jsonify({"code": 404, "message": "政策不存在"}), 404
        
        # AI解读逻辑
        VEI_API_KEY = os.environ.get("VEI_API_KEY", "sk-1e697322aa3f4cbdbaa9d37fef9066e8ya97b7al4xzsvnkf")
        API_URL = "https://ai-gateway.vei.volces.com/v1/chat/completions"
        
        prompt = f"""请作为农业政策解读专家，分析以下政策的核心要点：
        政策标题：{policy['title']}
        政策内容：{policy['content']}
        发布省份：{policy['province']}
        
        要求：
        1. 分点列出核心信息；
        2. 语言简洁，中文口语化；
        3. 不超过300字。
        """
        
        try:
            response = requests.post(
                API_URL,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {VEI_API_KEY}"},
                json={
                    "model": "doubao-seed-1.6-thinking",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300
                },
                timeout=20
            )
            response.raise_for_status()
            interpretation = response.json()["choices"][0]["message"]["content"]
            return jsonify({"code": 200, "interpretation": interpretation})
        
        except Exception as e:
            logging.error(f"AI解读失败: {str(e)}")
            fallback = f"【政策核心要点】\n1. 政策主题：{policy['title']}\n2. 发布单位：{policy['source']}\n3. 适用地区：{policy['province']}"
            return jsonify({"code": 200, "interpretation": fallback})
    
    except Exception as e:
        logging.error(f"获取AI解读失败: {str(e)}")
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500

@app.route('/api/reports', methods=['GET'])
def get_reports():
    try:
        reports = []
        for file in os.listdir(REPORT_DIR):
            if file.startswith("daily_report_") and file.endswith(".json"):
                date = file.replace("daily_report_", "").replace(".json", "")
                reports.append({
                    "id": date,
                    "title": f"每日政策报告（{date}）",
                    "summary": f"包含政策数据"
                })
        return jsonify({"code": 200, "data": reports})
    except Exception as e:
        logging.error(f"获取报告列表失败: {e}")
        return jsonify({"code": 500, "message": "获取报告列表失败"}), 500

@app.route('/api/report/<string:report_id>/download', methods=['GET'])
def download_report(report_id):
    try:
        report_file = os.path.join(REPORT_DIR, f"daily_report_{report_id}.json")
        if not os.path.exists(report_file):
            return jsonify({"code": 404, "message": "报告不存在"}), 404
        
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        # 构建下载链接
        current_host = request.host_url.rstrip('/')
        download_url = f"{current_host}/api/report/{report_id}/pdf"
        
        return jsonify({
            "code": 200,
            "download_url": download_url,
            "report_data": report_data
        })
    except Exception as e:
        logging.error(f"读取报告失败: {e}")
        return jsonify({"code": 500, "message": "读取报告失败"}), 500

# 健康检查与手动刷新接口
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Service is running"}), 200

@app.route('/api/refresh', methods=['GET'])
def manual_refresh():
    try:
        fetch_policy_data(full_refresh=True)
        return jsonify({"status": "success", "message": "数据已全量刷新"})
    except Exception as e:
        logging.error(f"手动刷新失败: {e}")
        return jsonify({"status": "error", "message": "刷新失败，请稍后再试"}), 500

if __name__ == '__main__':
    # 生产环境建议使用Gunicorn启动，此处保持Flask开发服务器用于调试
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)    
