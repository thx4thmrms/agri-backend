import random
import time
import logging
import requests
import pickle
import os
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='app.log'
)

# 全局配置
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

# 代理池配置（实际使用时需替换为有效代理）
PROXY_POOL = [
    # "http://user:pass@proxy1.example.com:8080",
    # "http://user:pass@proxy2.example.com:8080",
]

# 关键词列表
KEYWORDS = [
    "稻渔综合种养",
    "水产饲料",
    "渔药管理",
    "内陆渔业补贴",
    "渔业保险"
]

# 域名状态管理
def load_domain_status():
    """加载域名状态信息"""
    if os.path.exists('domain_status.pkl'):
        with open('domain_status.pkl', 'rb') as f:
            return pickle.load(f)
    return {}

def save_domain_status(status):
    """保存域名状态信息"""
    with open('domain_status.pkl', 'wb') as f:
        pickle.dump(status, f)

# 基础域名列表
BASE_DOMAINS = [
    # 政府网站
    "gov.cn",
    "agri.gov.cn",  # 农业农村部
    "moa.gov.cn",   # 农业部
    
    # 权威媒体
    "xinhuanet.com",  # 新华网
    "people.com.cn",  # 人民网
    "modernagri.com.cn",  # 现代农业网
    
    # 行业网站
    "fish.cn",  # 中国渔业网
    "fisheryinfo.cn",  # 渔业信息网
    "chinaaquaculture.com.cn",  # 中国水产养殖网
    
    # 备用数据源
    "xxgk.moa.gov.cn",  # 农业农村部信息公开平台
    "www.agri.gov.cn",  # 中国农业信息网
]

# 多线程爬取函数（增强版）
def crawl_keyword(keyword, domains, result_list, stats, failed_domains, domain_status):
    """单关键词爬取线程，支持域名状态管理和代理"""
    for domain in domains:
        # 检查域名状态
        if domain in domain_status:
            status = domain_status[domain]
            if status.get('disabled', False) and status.get('disabled_until', 0) > time.time():
                logging.debug(f"域名 {domain} 暂时禁用，剩余时间: {status['disabled_until'] - time.time():.0f}秒")
                continue
        
        try:
            # 动态构造URL
            if domain == "gov.cn":
                url = f"https://sousuo.gov.cn/s.htm?q={keyword}"
            elif domain == "people.com.cn":
                url = f"https://search.people.com.cn/search.do?q={keyword}"
            elif domain in ["agri.gov.cn", "moa.gov.cn", "xxgk.moa.gov.cn"]:
                url = f"https://www.{domain}/s?wd={keyword}"
            else:
                url = f"https://www.{domain}/search?q={keyword}"
            
            # 随机请求头
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": f"https://www.{domain}/",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0"
            }
            
            # 使用会话和重试机制
            session = requests.Session()
            retries = Retry(total=5, backoff_factor=1, 
                           status_forcelist=[500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            
            # 随机间隔（2-5秒，降低爬取频率）
            time.sleep(random.uniform(2.0, 5.0))
            
            # 选择代理（如果有配置）
            proxies = None
            if PROXY_POOL:
                proxies = {"http": random.choice(PROXY_POOL), "https": random.choice(PROXY_POOL)}
            
            # 发送请求
            response = session.get(url, headers=headers, timeout=20, proxies=proxies)
            response.raise_for_status()
            
            # 处理404错误
            if response.status_code == 404:
                logging.error(f"404错误: {url}")
                # 标记域名暂时不可用（1小时）
                domain_status[domain] = {
                    'disabled': True,
                    'disabled_until': time.time() + 3600,
                    'last_checked': time.time()
                }
                stats[domain]["failed"] += 1
                save_domain_status(domain_status)
                continue
            
            # 解析内容
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all(['article', 'div', 'li'], class_=['news', 'article', 'item', 'list-item'])
            
            if not articles:
                logging.info(f"在 {domain} 上未找到关于 '{keyword}' 的文章")
                continue
            
            # 提取政策信息
            for article in articles[:5]:  # 限制每个域名最多提取5篇
                try:
                    title = article.find('a').text.strip()
                    link = article.find('a')['href']
                    if not link.startswith('http'):
                        link = f"https://www.{domain}{link}"
                    
                    # 提取发布日期
                    date_element = article.find(['time', 'span'], class_=['date', 'time', 'pubtime'])
                    date = date_element.text.strip() if date_element else "未知日期"
                    
                    # 提取摘要
                    summary = article.find('p').text.strip() if article.find('p') else "无摘要"
                    
                    # 添加到结果列表
                    result_list.append({
                        'title': title,
                        'link': link,
                        'date': date,
                        'summary': summary,
                        'source': domain,
                        'keyword': keyword,
                        'crawl_time': time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    stats[domain]["success"] += 1
                    logging.info(f"成功获取: {title} from {domain}")
                except Exception as e:
                    logging.error(f"解析文章出错: {e}")
                    stats[domain]["failed"] += 1
        
        except requests.exceptions.RequestException as e:
            logging.error(f"请求 {url} 失败: {e}")
            # 标记域名暂时不可用（30分钟）
            domain_status[domain] = {
                'disabled': True,
                'disabled_until': time.time() + 1800,
                'last_checked': time.time()
            }
            stats[domain]["failed"] += 1
            save_domain_status(domain_status)
        except Exception as e:
            logging.error(f"爬取 {domain} 时发生未知错误: {e}")
            stats[domain]["failed"] += 1

# 爬取政策数据（增强版）
def fetch_policy_data(full_refresh=False):
    try:
        start_time = time.time()
        logging.info(f"开始爬取数据，{'全量刷新' if full_refresh else '增量更新'}")
        
        # 加载域名状态
        domain_status = load_domain_status()
        
        # 过滤可用域名
        current_time = time.time()
        active_domains = [
            domain for domain in BASE_DOMAINS 
            if domain not in domain_status 
            or not domain_status[domain].get('disabled', False) 
            or domain_status[domain].get('disabled_until', 0) < current_time
        ]
        
        logging.info(f"可用域名: {len(active_domains)}/{len(BASE_DOMAINS)}: {', '.join(active_domains)}")
        
        # 结果容器与统计
        policy_list = []
        domain_stats = {domain: {"success": 0, "failed": 0} for domain in BASE_DOMAINS}
        
        # 多线程爬取
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for keyword in KEYWORDS:
                # 每个关键词分配一个线程
                future = executor.submit(
                    crawl_keyword, 
                    keyword, 
                    active_domains, 
                    policy_list, 
                    domain_stats,
                    set(),  # 不再使用failed_domains参数
                    domain_status
                )
                futures.append(future)
            
            # 等待所有线程完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"爬取线程异常: {e}")
        
        # 保存域名状态
        save_domain_status(domain_status)
        
        # 统计结果
        total_success = sum(stats["success"] for stats in domain_stats.values())
        total_failed = sum(stats["failed"] for stats in domain_stats.values())
        success_rate = total_success / (total_success + total_failed) if (total_success + total_failed) > 0 else 0
        
        logging.info(f"爬取完成，共获取 {len(policy_list)} 条政策，成功率: {success_rate:.2%}")
        logging.info(f"域名统计: {domain_stats}")
        
        # 检查成功率，低于阈值时发送警报
        if success_rate < 0.3:
            send_alert(f"政策爬虫成功率过低: {success_rate:.2%}")
        
        # 保存结果到数据库或文件
        # 实际项目中需要添加数据库操作
        
        end_time = time.time()
        logging.info(f"爬取任务完成，耗时: {end_time - start_time:.2f}秒")
        
        return policy_list
        
    except Exception as e:
        logging.critical(f"爬取过程中发生严重错误: {e}")
        # 可以添加更高级的错误恢复机制
        return []

# 发送警报函数
def send_alert(message):
    """发送异常警报（需配置邮件或短信服务）"""
    try:
        # 实际使用时需配置SMTP服务器
        logging.warning(f"发送警报: {message}")
        # 以下为示例代码，需根据实际情况修改
        # import smtplib
        # from email.mime.text import MIMEText
        # msg = MIMEText(message)
        # msg['Subject'] = '政策爬虫异常通知'
        # msg['From'] = 'alert@example.com'
        # msg['To'] = 'admin@example.com'
        # s = smtplib.SMTP('smtp.example.com')
        # s.send_message(msg)
        # s.quit()
    except Exception as e:
        logging.error(f"发送警报失败: {e}")

# API接口部分（Flask框架）
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/api/policies', methods=['GET'])
def get_policies():
    """获取政策数据API"""
    try:
        # 支持增量更新和全量更新
        full_refresh = request.args.get('full_refresh', 'false').lower() == 'true'
        
        # 获取政策数据
        policies = fetch_policy_data(full_refresh)
        
        # 返回JSON响应
        return jsonify({
            'status': 'success',
            'count': len(policies),
            'data': policies
        })
    except Exception as e:
        logging.error(f"API请求处理失败: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # 生产环境建议使用Gunicorn等WSGI服务器
    app.run(host='0.0.0.0', port=5000, debug=False)    
