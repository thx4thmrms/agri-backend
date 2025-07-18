from flask import Flask, jsonify
import requests
import time
import random
import json
from datetime import datetime, timedelta
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler  # 定时任务库

# 初始化Flask
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文

# 数据存储路径（云服务器上会自动创建）
DATA_DIR = "policy_data"
os.makedirs(DATA_DIR, exist_ok=True)
REPORT_FILE = os.path.join(DATA_DIR, "daily_report.json")  # 每日报告存储文件

# 爬取配置（目标网站+关键词，沿用之前的逻辑）
GOVERNMENT_SITES = {
    "农业农村部": {"url": "http://www.moa.gov.cn", "keywords": ["农业补贴", "渔业资金"]},
    "财政部": {"url": "http://www.mof.gov.cn", "keywords": ["专项资金", "预算公示"]}
}

# 定时任务：每天8点生成报告
def generate_daily_report():
    """爬取数据并生成每日报告"""
    today = datetime.now().strftime("%Y-%m-%d")
    # 1. 爬取当天数据（简化版爬取逻辑，实际会按关键词筛选）
    policies = []
    for site_name, site in GOVERNMENT_SITES.items():
        try:
            # 模拟爬取（实际会请求网页，这里简化为示例数据）
            policies.append({
                "title": f"{site_name}关于{today}的农业补贴政策",
                "content": "今日新增补贴资金500万元，覆盖3个地区...",
                "source": site_name,
                "date": today
            })
            time.sleep(random.uniform(1, 2))  # 模拟爬取间隔
        except Exception as e:
            print(f"爬取{site_name}失败：{e}")

    # 2. 生成报告并保存
    report = {
        "date": today,
        "count": len(policies),
        "policies": policies,
        "summary": f"今日共更新{len(policies)}条政策，主要涉及农业补贴和渔业资金。"
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[{today} 08:00] 每日报告生成成功")

# 启动定时任务
scheduler = BackgroundScheduler()
scheduler.add_job(generate_daily_report, 'cron', hour=8, minute=0)  # 每天8点执行
scheduler.start()

# API接口：供小程序获取每日报告
@app.route("/api/daily_report")
def get_daily_report():
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            return jsonify({"status": "success", "data": json.load(f)})
    return jsonify({"status": "error", "message": "暂无报告，请等待每日8点更新"})

# 启动后端服务
if __name__ == "__main__":
    generate_daily_report()  # 首次运行先生成一份报告
    app.run(host="0.0.0.0", port=5000)  # 云服务器上运行