from loguru import logger
from proxypool.storages.redis import RedisClient
from proxypool.setting import PROXY_NUMBER_MAX
from proxypool.testers import __all__ as testers_cls
# new imports for hot reload
import importlib
import pkgutil
import inspect
import json
import proxypool.crawlers
from proxypool.crawlers.base import BaseCrawler


class Getter(object):
    """
    getter of proxypool
    """

    def __init__(self):
        """
        init db and crawlers
        """
        self.redis = RedisClient()
        self.testers_cls = testers_cls
        self.testers = [tester_cls() for tester_cls in self.testers_cls]

    def _load_crawlers(self):
        """
        动态加载和重新加载 proxypool.crawlers 包中的爬虫。
        """
        crawlers = []
        crawler_names = []

        for loader, name, is_pkg in pkgutil.walk_packages(proxypool.crawlers.__path__):
            # 构造完整的模块名称，例如 proxypool.crawlers.public.daili66
            module_name = f'proxypool.crawlers.{name}'
            try:
                # 导入或重新加载模块
                module = importlib.import_module(module_name)
                importlib.reload(module)

                # 判断爬虫类型
                crawler_type = '公共' if 'public' in module_name else '私有'

                # 在重新加载的模块中查找 BaseCrawler 的子类
                for member_name, member_obj in inspect.getmembers(module):
                    if (inspect.isclass(member_obj) and
                            issubclass(member_obj, BaseCrawler) and
                            member_obj is not BaseCrawler and
                            not getattr(member_obj, 'ignore', False)):
                        logger.debug(f"发现爬虫: {member_obj.__name__}")
                        crawlers.append(member_obj())
                        # 存储为 JSON 字符串
                        crawler_info = {
                            'name': member_obj.__name__,
                            'type': crawler_type
                        }
                        crawler_names.append(json.dumps(crawler_info, ensure_ascii=False))
            except Exception as e:
                logger.error(f"加载或重新加载爬虫 '{name}' 失败: {e}")

        logger.info(f"成功加载 {len(crawlers)} 个爬虫。")
        
        # 使用 Redis 事务来更新爬虫列表
        pipe = self.redis.db.pipeline()
        pipe.delete('crawlers')
        if crawler_names:
            pipe.sadd('crawlers', *crawler_names)
        pipe.execute()
        
        return crawlers

    def is_full(self):
        """
        if proxypool if full
        return: bool
        """
        return self.redis.count() >= PROXY_NUMBER_MAX

    @logger.catch
    def run(self):
        """
        run crawlers to get proxy
        :return:
        """
        if self.is_full():
            return
        
        crawlers = self._load_crawlers()
        for crawler in crawlers:
            logger.info(f'crawler {crawler} to get proxy')
            for proxy in crawler.crawl():
                self.redis.add(proxy)
                [self.redis.add(proxy, redis_key=tester.key) for tester in self.testers]


if __name__ == '__main__':
    getter = Getter()
    getter.run()
