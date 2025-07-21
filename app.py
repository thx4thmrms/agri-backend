from flask import Flask, jsonify, request, send_file
import requests
import schedule
import time
import threading
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask_cors import CORS

app = Flask(__name__)

# ========== 跨域配置 ==========
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ========== 历史功能变量 ==========
REPORT_DIR = "policy_data"
os.makedirs(REPORT_DIR, exist_ok=True)

# 完整关键词列表
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
    "温室大棚", "设施农业", "无土栽培", "智能大棚", "温控大棚",
    "大棚蔬菜", "大棚水果", "水肥一体化", "植物工厂", "光照调控",
    "设施园艺", "温室结构", "塑料大棚", "连栋温室", "基质栽培",
    
    # 渔业技术
    "水下鱼类识别", "渔业物联网", "智能监测系统", "水质传感器", "鱼类行为分析",
    "水产养殖机器人", "水下摄像机", "渔业大数据", "精准投喂", "疾病预警",
    "无人机巡检", "卫星遥感", "水产育种", "基因编辑", "鱼类疫苗",
    
    # 大棚技术
    "环境控制系统", "CO2施肥", "LED补光", "智能灌溉", "温室自动化",
    "作物生长模型", "植物光谱", "蔬菜嫁接", "病虫害生物防治", "温室节能",
    
    # 政策与资金通用词
    "渔业政策", "农业农村部资金", "渔业发展专项资金", "乡村振兴资金",
    "农业补贴", "渔业保险", "渔业项目申报", "渔业贷款", "设施农业补贴",
    "现代农业产业园", "渔业绿色发展", "生态补偿", "碳汇渔业"
]

# 允许的域名列表
ALLOWED_DOMAINS = [
    # 政府网站
    "gov.cn", "agri.gov.cn", "moa.gov.cn", "nynct.gov.cn",
    "ocean.gov.cn", "scsf.gd.gov.cn", "fishery.gov.cn",
    
    # 权威媒体
    "xinhuanet.com", "people.com.cn", "china.com.cn", "cctv.com",
    "chinafisherynews.com.cn", "modernagri.com.cn", "nongnet.com",
    
    # 行业网站
    "fish.cn", "fisheryinfo.cn", "chinaaquaculture.com.cn", "seafishery.cn",
    "greenhouse.cn", "facility-agri.com.cn", "agri-facility.com",
    "aquatech.cn", "fishxun.com", "agri-tech.com.cn", "hydroponics.cn"
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

first_request = True
POLICY_DATA = []


# 爬取政策数据
def fetch_policy_data():
    try:
        policy_list = []
        for keyword in KEYWORDS:
            for domain in ALLOWED_DOMAINS:
                try:
                    url = f"https://{domain}/search?q={keyword}"
                    response = requests.get(url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # 这里需要根据实际网页结构修改选择器
                    articles = soup.find_all('article')
                    for article in articles:
                        title = article.find('h2').text.strip() if article.find('h2') else '未找到标题'
                        content = article.find('p').text.strip() if article.find('p') else '未找到内容'
                        source = domain
                        date = datetime.now().strftime("%Y-%m-%d")
                        article_url = article.find('a')['href'] if article.find('a') else '未找到链接'
                        policy_id = f"{domain}-{hash(article_url)}"
                        category = "policy" if "政策" in keyword else "fund" if "资金" in keyword else "tech"
                        province_code = domain.split('.')[0]
                        province = PROVINCE_MAP.get(province_code, "全国")

                        policy = {
                            "title": title,
                            "source": source,
                            "date": date,
                            "content": content,
                            "url": article_url,
                            "id": policy_id,
                            "category": category,
                            "province": province
                        }
                        policy_list.append(policy)
                except Exception as e:
                    print(f"从 {domain} 爬取 {keyword} 数据失败: {e}")

        # 去重
        unique_policies = []
        seen_urls = set()
        for policy in policy_list:
            if policy["url"] not in seen_urls:
                seen_urls.add(policy["url"])
                unique_policies.append(policy)

        return unique_policies
    except Exception as e:
        print(f"获取政策数据失败: {e}")
        return []


# 获取所有省份接口
@app.route('/api/provinces', methods=['GET'])
def get_provinces():
    provinces = ["all"]
    if POLICY_DATA:
        unique_provinces = list({policy["province"] for policy in POLICY_DATA})
        provinces.extend(sorted(unique_provinces))
    return jsonify({"code": 200, "data": provinces})


# 报告生成逻辑
def generate_daily_report():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        report_file = os.path.join(REPORT_DIR, f"daily_report_{today}.json")
        
        policies = fetch_policy_data()
        category_count = {}
        for keyword in KEYWORDS:
            category_count[keyword] = sum(keyword in policy["title"] for policy in policies)
        
        report = {
            "date": today,
            "total_policies": len(policies),
            "policies": policies,
            "category_count": category_count,
            "summary": f"今日共收集到{len(policies)}条渔业及大棚种植相关政策"
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"报告已生成: {report_file}")
        return report
    except Exception as e:
        print(f"生成报告失败: {e}")
        return {"error": str(e)}


# 政策列表接口
@app.route('/api/policies', methods=['GET'])
def get_policies():
    global POLICY_DATA
    if not POLICY_DATA:
        POLICY_DATA = fetch_policy_data()
    
    category = request.args.get('category', 'policy')
    province = request.args.get('province', 'all')
    keyword = request.args.get('keyword', '').strip()
    
    filtered = [
        p for p in POLICY_DATA
        if p['category'] == category 
        and (province == 'all' or p['province'] == province) 
        and (keyword == '' or keyword in p['title'] or keyword in p['content'])
    ]
    
    return jsonify({"code": 200, "data": filtered, "total": len(filtered)})


# 政策详情接口
@app.route('/api/policy/<string:policy_id>', methods=['GET'])
def get_policy_detail(policy_id):
    global POLICY_DATA
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    return jsonify({"code": 200, "data": policy})


# ========== AI解读接口（已填入你的密钥） ==========
@app.route('/api/interpret/<string:policy_id>', methods=['GET'])
def get_ai_interpret(policy_id):
    global POLICY_DATA
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    
    # 已填入你的密钥
    VEI_API_KEY = "sk-1e697322aa3f4cbdbaa9d37fef9066e8ya97b7al4xzsvnkf"  # 你的密钥
    API_URL = "https://ai-gateway.vei.volces.com/v1/chat/completions"
    
    # 构造提示词
    prompt = f"""请作为农业政策解读专家，分析以下政策的核心要点：
    政策标题：{policy['title']}
    政策内容：{policy['content']}
    发布省份：{policy['province']}
    
    要求：
    1. 分点列出核心信息（政策目的、适用范围、补贴标准等）；
    2. 语言简洁，用中文口语化表达；
    3. 不超过300字。
    """
    
    # 调用豆包模型API
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {VEI_API_KEY}"  # 使用你的密钥进行认证
        }
        payload = {
            "model": "doubao-seed-1.6-thinking",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300
        }
        
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        interpretation = result["choices"][0]["message"]["content"]
        
        return jsonify({"code": 200, "interpretation": interpretation})
    
    except Exception as e:
        print(f"AI解读调用失败: {str(e)}")
        # 失败时的备用解读
        fallback = f"【政策核心要点】\n1. 政策主题：{policy['title']}\n2. 发布单位：{policy['source']}\n3. 适用地区：{policy['province']}"
        return jsonify({"code": 200, "interpretation": fallback})


# 报告列表接口
@app.route('/api/reports', methods=['GET'])
def get_reports():
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


# 报告下载接口
@app.route('/api/report/<string:report_id>/download', methods=['GET'])
def download_report(report_id):
    report_file = os.path.join(REPORT_DIR, f"daily_report_{report_id}.json")
    if not os.path.exists(report_file):
        return jsonify({"code": 404, "message": "报告不存在"}), 404
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    return jsonify({
        "code": 200,
        "download_url": f"https://agri-backend-ame6.onrender.com/api/report/{report_id}/pdf",
        "report_data": report_data
    })


# 健康检查与定时任务
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Service is running"}), 200

def scheduled_task():
    schedule.every().day.at("08:00").do(generate_daily_report)
    print("定时任务已设置：每天08:00生成报告")
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_scheduled_task():
    task_thread = threading.Thread(target=scheduled_task)
    task_thread.daemon = True
    task_thread.start()
    print("定时任务线程已启动")

@app.before_request
def initialize():
    global first_request
    if first_request:
        first_request = False
        start_scheduled_task()
        print("应用初始化完成")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
