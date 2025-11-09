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
    import importlib.util
    import inspect
    
    plugins = []
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crawlers', 'public')
    
    if os.path.exists(crawler_path):
        # 遍历所有爬虫文件
        for filename in sorted(os.listdir(crawler_path)):
            if not filename.endswith('.py') or filename == '__init__.py':
                continue
            
            file_path = os.path.join(crawler_path, filename)
            try:
                # 动态导入爬虫模块
                spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
                if spec is None or spec.loader is None:  # type: ignore
                    continue
                module = importlib.util.module_from_spec(spec)  # type: ignore
                spec.loader.exec_module(module)  # type: ignore
                
                # 查找爬虫类（通常继承自 BaseCrawler）
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and hasattr(obj, '__module__') and obj.__module__ == module.__name__:
                        # 获取类的 docstring
                        docstring = inspect.getdoc(obj) or 'N/A'
                        # 只取第一行作为描述
                        description = docstring.split('\n')[0] if docstring else 'N/A'
                        
                        plugins.append({
                            'name': name,
                            'type': 'public',
                            'description': description,
                            'file': filename
                        })
                        break  # 每个文件只处理一个爬虫类
            except Exception as e:
                # 失败的爬虫文件只记录错误，不中断
                print(f'Failed to load crawler {filename}: {e}')
                continue
    
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


@app.route('/api/create_plugin', methods=['POST'])
def create_plugin():
    """
    创建新的爬虫插件
    :return: JSON 创建结果
    """
    try:
        data = request.get_json()  # type: ignore
        
        if not data:
            return jsonify({'success': False, 'message': '请提供插件信息'}), 400
        
        plugin_name = data.get('name', '').strip()
        plugin_description = data.get('description', '').strip()
        plugin_url = data.get('url', '').strip()
        response_example = data.get('response_example', '').strip()
        
        # 验证输入
        if not plugin_name or not plugin_description or not plugin_url:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        # 验证插件名称
        if not plugin_name.replace('_', '').isalnum():
            return jsonify({'success': False, 'message': '插件名称只能包含字母、数字和下划线'}), 400
        
        # 检查插件是否已存在
        private_crawler_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crawlers', 'private')
        plugin_file = os.path.join(private_crawler_path, f'{plugin_name}.py')
        
        if os.path.exists(plugin_file):
            return jsonify({'success': False, 'message': f'插件 {plugin_name} 已存在'}), 400
        
        # 确保 private 文件夹存在
        os.makedirs(private_crawler_path, exist_ok=True)
        
        # 生成插件类名（将下划线转成驻峰命名）
        class_name = ''.join([word.capitalize() for word in plugin_name.split('_')]) + 'Crawler'
        
        # 预义体示例
        example_response = response_example if response_example else '{"data": [{"ip": "127.0.0.1", "port": 8080}]}'
        
        # 生成插件代码——基于真实的爬虫模板
        plugin_code = '''import time
import json
from retrying import RetryError
from loguru import logger
from proxypool.schemas.proxy import Proxy
from proxypool.crawlers.base import BaseCrawler

BASE_URL = '{}'


class {}(BaseCrawler):
    """
    {}
    """
    urls = [BASE_URL]

    def parse(self, html):
        """
        parse html file to get proxies
        :return:
        """
        try:
            result = json.loads(html)
            # 根据实际API响应格式修改此处
            # 示例响应: {}
            proxy_list = result.get('data', [])
            for proxy_item in proxy_list:
                host = proxy_item.get('ip')
                port = proxy_item.get('port')
                if host and port:
                    yield Proxy(host=host, port=int(port) if isinstance(port, str) else port)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f'Failed to parse proxies: {{e}}')
            return


if __name__ == '__main__':
    crawler = {}()
    for proxy in crawler.crawl():
        print(proxy)
'''.format(plugin_url, class_name, plugin_description, example_response, class_name)
        
        # 写入文件
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        return jsonify({
            'success': True,
            'message': f'插件 {plugin_name} 创建成功！',
            'plugin_file': plugin_file
        }), 201
    
    except Exception as e:
        print(f'Error creating plugin: {e}')
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


if __name__ == '__main__':    app.run(host=API_HOST, port=API_PORT, threaded=API_THREADED)
