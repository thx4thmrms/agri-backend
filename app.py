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

# ========== 【保留】跨域配置（原代码不变） ==========
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ========== 【保留】历史功能变量（完整列出，无省略） ==========
REPORT_DIR = "policy_data"
os.makedirs(REPORT_DIR, exist_ok=True)

# 【完整保留】所有关键词（原列表全量复制）
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

# 【完整保留】所有允许的域名（原列表全量复制）
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

first_request = True  # 【保留】首次请求标志

# ========== 【新增】前端接口专用：政策数据存储（复用原模拟逻辑） ==========
POLICY_DATA = []  # 存储政策数据（复用原fetch_policy_data的格式）


# ========== 【保留】原模拟政策数据逻辑（完全不变） ==========
def fetch_policy_data():
    try:
        policy_list = []
        for keyword in KEYWORDS:
            for domain in ALLOWED_DOMAINS:
                response = {
                    "title": f"2025年{keyword}技术指南与政策支持 - {domain}",
                    "source": domain,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "content": f"关于{keyword}的最新技术发展和补贴标准...该政策由{domain}发布，详细内容包括补贴申请条件、技术应用规范等。",
                    "url": f"https://{domain}/policy/{keyword}/{datetime.now().strftime('%Y%m%d')}",
                    "id": f"{domain}-{keyword}-{datetime.now().strftime('%Y%m%d')}",  # 唯一ID（前端需用）
                    "category": "policy" if "政策" in keyword else "fund" if "资金" in keyword else "tech",  # 按关键词自动分类
                    "province": "全国" if "gov.cn" in domain else domain.split('.')[0]  # 简单省份判断
                }
                policy_list.append(response)
        
        # 【保留】原去重逻辑
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


# ========== 【保留】原报告生成逻辑（完全不变） ==========
def generate_daily_report():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        report_file = os.path.join(REPORT_DIR, f"daily_report_{today}.json")
        
        # 获取政策数据
        policies = fetch_policy_data()
        
        # 按关键词分类统计
        category_count = {}
        for keyword in KEYWORDS:
            category_count[keyword] = sum(keyword in policy["title"] for policy in policies)
        
        # 生成报告
        report = {
            "date": today,
            "total_policies": len(policies),
            "policies": policies,
            "category_count": category_count,
            "summary": f"今日共收集到{len(policies)}条渔业及大棚种植相关政策"
        }
        
        # 保存报告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"报告已生成: {report_file}")
        return report
    except Exception as e:
        print(f"生成报告失败: {e}")
        return {"error": str(e)}


# ========== 【新增】前端专属接口（与历史功能解耦，不影响原有逻辑） ==========

# 1. 政策列表接口（支持分类、省份、关键词筛选）
@app.route('/api/policies', methods=['GET'])
def get_policies():
    global POLICY_DATA
    # 首次请求时初始化政策数据（复用原fetch_policy_data）
    if not POLICY_DATA:
        POLICY_DATA = fetch_policy_data()
    
    # 前端参数：category（政策/资金/科技）、province、keyword
    category = request.args.get('category', 'policy')
    province = request.args.get('province', 'all')
    keyword = request.args.get('keyword', '').strip()
    
    # 筛选逻辑
    filtered = [
        p for p in POLICY_DATA
        if p['category'] == category 
        and (province == 'all' or p['province'] == province) 
        and (keyword == '' or keyword in p['title'] or keyword in p['content'])
    ]
    
    return jsonify({"code": 200, "data": filtered, "total": len(filtered)})


# 2. 政策详情接口
@app.route('/api/policy/<string:policy_id>', methods=['GET'])
def get_policy_detail(policy_id):
    global POLICY_DATA
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    return jsonify({"code": 200, "data": policy})


# 3. AI解读接口（模拟，后续可替换为豆包API）
@app.route('/api/interpret/<string:policy_id>', methods=['GET'])
def get_ai_interpret(policy_id):
    global POLICY_DATA
    policy = next((p for p in POLICY_DATA if p["id"] == policy_id), None)
    if not policy:
        return jsonify({"code": 404, "message": "政策不存在"}), 404
    
    # 模拟AI解读（核心要点提炼）
    interpretation = f"【政策核心要点】\n1. 政策主题：{policy['title']}\n2. 发布单位：{policy['source']}\n3. 关键内容：{policy['content'][:100]}...\n4. 适用范围：{policy['province']}地区"
    return jsonify({"code": 200, "interpretation": interpretation})


# 4. 报告列表接口（复用原报告数据）
@app.route('/api/reports', methods=['GET'])
def get_reports():
    reports = []
    for file in os.listdir(REPORT_DIR):
        if file.startswith("daily_report_") and file.endswith(".json"):
            date = file.replace("daily_report_", "").replace(".json", "")
            reports.append({
                "id": date,
                "title": f"每日政策报告（{date}）",
                "summary": f"包含{len(json.load(open(os.path.join(REPORT_DIR, file))))}条政策数据"
            })
    return jsonify({"code": 200, "data": reports})


# 5. 报告下载接口（模拟PDF下载，实际返回JSON内容）
@app.route('/api/report/<string:report_id>/download', methods=['GET'])
def download_report(report_id):
    report_file = os.path.join(REPORT_DIR, f"daily_report_{report_id}.json")
    if not os.path.exists(report_file):
        return jsonify({"code": 404, "message": "报告不存在"}), 404
    
    # 读取报告内容（模拟PDF下载，实际需用fpdf2生成PDF）
    with open(report_file, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    return jsonify({
        "code": 200,
        "download_url": f"https://agri-backend-ame6.onrender.com/api/report/{report_id}/pdf",  # 模拟PDF链接
        "report_data": report_data
    })


# ========== 【保留】原健康检查、定时任务（完全不变） ==========
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
