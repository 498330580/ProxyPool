from flask import Flask, g, request, render_template, jsonify
from typing import TYPE_CHECKING
from proxypool.exceptions import PoolEmptyException
from proxypool.storages.redis import RedisClient
from proxypool.setting import API_HOST, API_PORT, API_THREADED, API_KEY, IS_DEV, PROXY_RAND_KEY_DEGRADED
from proxypool.setting import REDIS_HOST, REDIS_PORT, ENABLE_GETTER, ENABLE_TESTER, CYCLE_GETTER, CYCLE_TESTER, ENABLE_SERVER
import functools
import datetime
import os
import importlib
import pkgutil
import json

if TYPE_CHECKING:
    pass  # type: ignore

__all__ = ['app']

app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
if IS_DEV:
    app.debug = True

# 添加模板过滤器
@app.template_filter('now')
def filter_now(format_="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.now().strftime(format_)

# 添加now函数到全局上下文
@app.context_processor
def inject_now():
    def format_now(format_="%Y-%m-%d %H:%M:%S"):
        return datetime.datetime.now().strftime(format_)
    return {'now': format_now}


def auth_required(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        # conditional decorator, when setting API_KEY is set, otherwise just ignore this decorator
        if API_KEY == "":
            return func(*args, **kwargs)
        if request.headers.get('API-KEY', None) is not None:  # type: ignore
            api_key = request.headers.get('API-KEY')  # type: ignore
        else:
            return {"message": "Please provide an API key in header"}, 400
        # Check if API key is correct and valid
        if request.method == "GET" and api_key == API_KEY:
            return func(*args, **kwargs)
        else:
            return {"message": "The provided API key is not valid"}, 403

    return decorator


def get_conn() -> RedisClient:  # type: ignore
    """
    get redis client object
    :return:
    """
    if not hasattr(g, 'redis'):
        g.redis = RedisClient()
    return g.redis  # type: ignore


@app.route('/')
@auth_required
def index():
    """
    get home page, you can define your own templates
    :return:
    """
    conn = get_conn()
    return render_template('index.html', count=conn.count())


@app.route('/random')
@auth_required
def get_proxy():
    """
    get a random proxy, can query the specific sub-pool according the (redis) key
    if PROXY_RAND_KEY_DEGRADED is set to True, will get a universal random proxy if no proxy found in the sub-pool
    :return: get a random proxy
    """
    key = request.args.get('key')  # type: ignore
    conn = get_conn()
    # return conn.random(key).string() if key else conn.random().string()
    if key:
        try:
            return conn.random(key).string()
        except PoolEmptyException:
            if not PROXY_RAND_KEY_DEGRADED:
                raise
    return conn.random().string()


@app.route('/all')
@auth_required
def get_proxy_all():
    """
    get a random proxy
    :return: get a random proxy
    """
    key = request.args.get('key')  # type: ignore

    conn = get_conn()
    proxies = conn.all(key) if key else conn.all()
    proxies_string = ''
    if proxies:
        for proxy in proxies:
            proxies_string += str(proxy) + '\n'

    return proxies_string


@app.route('/count')
@auth_required
def get_count():
    """
    get the count of proxies
    :return: count, int
    """
    conn = get_conn()
    key = request.args.get('key')  # type: ignore
    return str(conn.count(key)) if key else str(conn.count())
    
# 管理面板路由
@app.route('/admin')
def admin_dashboard():
    """
    管理面板首页
    :return: 管理面板首页
    """
    conn = get_conn()
    proxies = conn.all()
    proxies_list = []
    
    # 获取最新20条代理
    for proxy in proxies[:20]:
        # 获取代理分数
        proxy_str = str(proxy)
        try:
            redis_key = list(conn.db.keys('proxies:*'))[0] if conn.db.keys('proxies:*') else None  # type: ignore
            if redis_key:
                score = conn.db.zscore(redis_key, proxy_str) or 0  # type: ignore
            else:
                score = 0
        except Exception:
            score = 0
        proxies_list.append({
            'proxy': proxy_str,
            'score': int(score) if isinstance(score, (int, float)) else 0,
            'last_checked': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # 获取爬虫数量
    crawler_count = 0
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crawlers', 'public')
    if os.path.exists(crawler_path):
        crawler_count = len([name for name in os.listdir(crawler_path) 
                           if os.path.isfile(os.path.join(crawler_path, name)) 
                           and name.endswith('.py') 
                           and name != '__init__.py'])
    
    # 获取当前访问API地址（主机名或IP + 端口）
    api_host_display = request.host.split(':')[0]  # type: ignore
    api_port_display = request.host.split(':')[1] if ':' in request.host else API_PORT  # type: ignore
    
    return render_template('dashboard.html', 
                          active_page='dashboard',
                          proxy_count=conn.count(),
                          crawler_count=crawler_count,
                          status='运行中',
                          proxies=proxies_list,
                          redis_host=REDIS_HOST,
                          redis_port=REDIS_PORT,
                          api_host=api_host_display,
                          api_port=api_port_display)

@app.route('/admin/help')
def admin_help():
    """
    管理面板帮助页面
    :return: 管理面板帮助页面
    """
    return render_template('help.html', 
                          active_page='help',
                          api_host=API_HOST,
                          api_port=API_PORT)

@app.route('/admin/plugins')
def admin_plugins():
    """
    管理面板插件页面
    :return: 管理面板插件页面
    """
    conn = get_conn()
    crawlers_info = conn.db.smembers('crawlers')  # type: ignore
    plugins = [json.loads(info) for info in crawlers_info] if crawlers_info else []  # type: ignore
    return render_template('plugins.html', 
                          active_page='plugins',
                          plugins=plugins)


# API 接口路由
@app.route('/api/stats')
def api_stats():
    """
    获取统计信息
    :return: JSON 统计数据
    """
    conn = get_conn()
    
    # 获取爬虫数量
    crawler_count = 0
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crawlers', 'public')
    if os.path.exists(crawler_path):
        crawler_count = len([name for name in os.listdir(crawler_path) 
                           if os.path.isfile(os.path.join(crawler_path, name)) 
                           and name.endswith('.py') 
                           and name != '__init__.py'])
    
    # 计算平均分
    proxies = conn.all()
    avg_score = 0
    if proxies:
        try:
            redis_keys = conn.db.keys('proxies:*')  # type: ignore
            redis_key = list(redis_keys)[0] if redis_keys else None  # type: ignore
            if redis_key:
                scores = conn.db.zrange(redis_key, 0, -1, withscores=True)  # type: ignore
                if scores and isinstance(scores, list):
                    avg_score = int(sum(score[1] for score in scores) / len(scores))
        except Exception:
            avg_score = 0
    
    return jsonify({
        'proxy_count': conn.count(),
        'crawler_count': crawler_count,
        'status': '运行中' if proxies else '空闲',
        'avg_score': avg_score,
        'getter_enabled': ENABLE_GETTER,
        'tester_enabled': ENABLE_TESTER,
        'server_enabled': ENABLE_SERVER,
        'cycle_getter': CYCLE_GETTER,
        'cycle_tester': CYCLE_TESTER
    })


@app.route('/api/proxies')
def api_proxies():
    """
    获取代理列表（按分数由高到低排序）
    :return: JSON 代理列表
    """
    conn = get_conn()
    limit = request.args.get('limit', 20, type=int)  # type: ignore
    offset = request.args.get('offset', 0, type=int)  # type: ignore
    
    try:
        redis_key = list(conn.db.keys('proxies:*'))[0] if conn.db.keys('proxies:*') else None  # type: ignore
        
        if redis_key:
            # 从 Redis 按分数批量获取代理（按分数由高到低）
            all_proxies_with_scores = conn.db.zrevrange(redis_key, 0, -1, withscores=True)  # type: ignore
            total = len(all_proxies_with_scores) if all_proxies_with_scores else 0  # type: ignore
            
            # 分页处理
            paginated_proxies = (all_proxies_with_scores or [])[offset:offset + limit]  # type: ignore
            
            proxies_data = []
            for proxy_str, score in paginated_proxies:
                proxies_data.append({
                    'proxy': proxy_str,
                    'score': int(score) if isinstance(score, (int, float)) else 0,
                    'last_checked': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        else:
            # 没有 Redis key，推退到 conn.all()
            all_proxies = conn.all()
            total = len(all_proxies)
            paginated_proxies = all_proxies[offset:offset + limit]
            
            proxies_data = []
            for proxy in paginated_proxies:
                proxy_str = str(proxy)
                proxies_data.append({
                    'proxy': proxy_str,
                    'score': 0,
                    'last_checked': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception as e:
        # 错误处理，返回空列表
        print(f'Error fetching proxies: {e}')
        return jsonify({
            'proxies': [],
            'total': 0,
            'limit': limit,
            'offset': offset
        })
    
    return jsonify({
        'proxies': proxies_data,
        'total': total,
        'limit': limit,
        'offset': offset
    })



if __name__ == '__main__':
    app.run(host=API_HOST, port=API_PORT, threaded=API_THREADED)
