from flask import Flask, g, request, render_template, jsonify
from proxypool.exceptions import PoolEmptyException
from proxypool.storages.redis import RedisClient
from proxypool.setting import API_HOST, API_PORT, API_THREADED, API_KEY, IS_DEV, PROXY_RAND_KEY_DEGRADED
from proxypool.setting import REDIS_HOST, REDIS_PORT
import functools
import datetime
import os
import importlib
import pkgutil

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
        if request.headers.get('API-KEY', None) is not None:
            api_key = request.headers.get('API-KEY')
        else:
            return {"message": "Please provide an API key in header"}, 400
        # Check if API key is correct and valid
        if request.method == "GET" and api_key == API_KEY:
            return func(*args, **kwargs)
        else:
            return {"message": "The provided API key is not valid"}, 403

    return decorator


def get_conn():
    """
    get redis client object
    :return:
    """
    if not hasattr(g, 'redis'):
        g.redis = RedisClient()
    return g.redis


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
    key = request.args.get('key')
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
    key = request.args.get('key')

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
    key = request.args.get('key')
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
        score = conn.db.zscore(conn.db.keys('*proxy*')[0], proxy_str) if conn.db.keys('*proxy*') else 0
        proxies_list.append({
            'proxy': proxy_str,
            'score': int(score) if score else 0,
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
    
    return render_template('dashboard.html', 
                          active_page='dashboard',
                          proxy_count=conn.count(),
                          crawler_count=crawler_count,
                          status='运行中',
                          proxies=proxies_list,
                          redis_host=REDIS_HOST,
                          redis_port=REDIS_PORT,
                          api_host=API_HOST,
                          api_port=API_PORT)

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
    import json
    crawlers_info = conn.db.smembers('crawlers')
    plugins = [json.loads(info) for info in crawlers_info]
    return render_template('plugins.html', 
                          active_page='plugins',
                          plugins=plugins)



if __name__ == '__main__':
    app.run(host=API_HOST, port=API_PORT, threaded=API_THREADED)
