from flask import Flask, jsonify
import requests
import schedule
import time
import threading
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)

# 健康检查路由
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "message": "Service is running"}), 200

# 政策数据存储路径
REPORT_DIR = "policy_data"
os.makedirs(REPORT_DIR, exist_ok=True)

# 关键词列表（聚焦渔业养殖、海洋牧场、大棚种植 + 技术细分）
KEYWORDS = [
    # ===== 内陆渔业养殖 =====
    "池塘养殖", "淡水养殖", "鱼苗繁育", "循环水养殖", "稻渔综合种养",
    "渔药管理", "水产饲料", "内陆渔业补贴", "养殖尾水处理", "病害防治",
    "渔业生态", "锦鲤养殖", "罗非鱼养殖", "小龙虾养殖", "河蟹养殖",
    
    # ===== 海洋渔业 =====
    "海水养殖", "远洋捕捞", "海洋牧场", "人工鱼礁", "渔具管理",
    "休渔期政策", "海洋渔业补贴", "渔获物加工", "渔业船员培训",
    "水产品质量安全", "深海养殖", "贝类养殖", "藻类养殖", "海水鱼类养殖",
    
    # ===== 渔港与设施 =====
    "渔港建设", "渔港经济区", "渔港升级改造", "渔业码头", "冷藏加工设施",
    "渔船管理", "渔业船舶检验", "渔港环境整治", "避风锚地", "渔港配套服务",
    
    # ===== 大棚种植 =====
    "温室大棚", "设施农业", "无土栽培", "智能大棚", "温控大棚",
    "大棚蔬菜", "大棚水果", "水肥一体化", "植物工厂", "光照调控",
    "设施园艺", "温室结构", "塑料大棚", "连栋温室", "基质栽培",
    
    # ===== 渔业技术（新增） =====
    "水下鱼类识别", "渔业物联网", "智能监测系统", "水质传感器", "鱼类行为分析",
    "水产养殖机器人", "水下摄像机", "渔业大数据", "精准投喂", "疾病预警",
    "无人机巡检", "卫星遥感", "水产育种", "基因编辑", "鱼类疫苗",
    
    # ===== 大棚技术（新增） =====
    "环境控制系统", "CO2施肥", "LED补光", "智能灌溉", "温室自动化",
    "作物生长模型", "植物光谱", "蔬菜嫁接", "病虫害生物防治", "温室节能",
    
    # ===== 政策与资金通用词 =====
    "渔业政策", "农业农村部资金", "渔业发展专项资金", "乡村振兴资金",
    "农业补贴", "渔业保险", "渔业项目申报", "渔业贷款", "设施农业补贴",
    "现代农业产业园", "渔业绿色发展", "生态补偿", "碳汇渔业"
]

# 允许的域名（扩展至权威媒体和行业网站）
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

# 全局标志，确保只在首次请求时执行初始化
first_request = True

# 模拟获取政策数据（实际使用时替换为真实API调用）
def fetch_policy_data():
    try:
        policy_list = []
        
        # 模拟从不同来源获取数据
        for keyword in KEYWORDS:
            # 模拟API请求（实际应替换为真实API）
            for domain in ALLOWED_DOMAINS:
                # 模拟根据关键词和域名获取政策
                response = {
                    "title": f"2025年{keyword}技术指南与政策支持 - {domain}",
                    "source": domain,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "content": f"关于{keyword}的最新技术发展和补贴标准...该政策由{domain}发布，详细内容包括...",
                    "url": f"https://{domain}/policy/{keyword}/{datetime.now().strftime('%Y%m%d')}"
                }
                policy_list.append(response)
        
        # 内容去重（基于标题和URL）
        unique_policies = []
        seen_urls = set()
        seen_titles = set()
        
        for policy in policy_list:
            url_hash = hash(policy["url"])
            title_hash = hash(policy["title"][:50])  # 取标题前50个字符作为哈希
            
            if url_hash not in seen_urls and title_hash not in seen_titles:
                seen_urls.add(url_hash)
                seen_titles.add(title_hash)
                unique_policies.append(policy)
        
        return unique_policies
    
    except Exception as e:
        print(f"获取政策数据失败: {e}")
        return []

# 生成每日报告
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

# API接口：获取最新报告
@app.route('/api/daily_report')
def get_daily_report():
    try:
        # 查找最新报告
        today = datetime.now().strftime("%Y-%m-%d")
        report_file = os.path.join(REPORT_DIR, f"daily_report_{today}.json")
        
        # 如果今天的报告不存在，尝试获取昨天的
        if not os.path.exists(report_file):
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            report_file = os.path.join(REPORT_DIR, f"daily_report_{yesterday}.json")
            
            if not os.path.exists(report_file):
                return jsonify({"status": "error", "message": "暂无报告，请等待每日8点更新"}), 404
        
        # 读取报告
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        return jsonify({"status": "success", "data": report})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 定时任务：每天8点生成报告
def scheduled_task():
    schedule.every().day.at("08:00").do(generate_daily_report)
    print("定时任务已设置：每天08:00生成报告")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# 启动定时任务线程
def start_scheduled_task():
    task_thread = threading.Thread(target=scheduled_task)
    task_thread.daemon = True
    task_thread.start()
    print("定时任务线程已启动")

# 应用启动时初始化
@app.before_request
def initialize():
    global first_request
    if first_request:
        first_request = False
        start_scheduled_task()
        print("应用初始化完成")

# 运行应用
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
