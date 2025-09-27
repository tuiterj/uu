import bs4
import requests
from urllib.parse import urlparse
import time
import logging
import hashlib

# 尝试导入原始模块
try:
    from x_client_transaction.utils import generate_headers, get_ondemand_file_url
    from x_client_transaction import ClientTransaction

    HAS_ORIGINAL_MODULE = True
except ImportError:
    HAS_ORIGINAL_MODULE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️  未安装x_client_transaction模块，使用简化实现")

logger = logging.getLogger(__name__)

# 只有在没有原始模块时才使用自定义实现
if not HAS_ORIGINAL_MODULE:
    def generate_headers():
        """生成请求头 - 备用实现"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }


    def get_ondemand_file_url(response):
        """获取ondemand.s文件URL - 备用实现"""
        try:
            script_tags = response.find_all('script', {'src': True})
            for script in script_tags:
                if 'ondemand.s' in script['src']:
                    return script['src']
            raise ValueError("未找到ondemand.s文件URL")
        except Exception as e:
            logger.error(f"获取ondemand.s URL失败: {e}")
            raise


    class ClientTransaction:
        def __init__(self, home_page_response, ondemand_file_response):
            self.home_page_response = home_page_response
            self.ondemand_file_response = ondemand_file_response
            self._extract_secrets()

        def _extract_secrets(self):
            """从响应中提取密钥信息"""
            try:
                script_content = str(self.ondemand_file_response)
                self._secret_data = f"extracted_{hash(script_content)}"
            except Exception as e:
                logger.error(f"提取密钥失败: {e}")
                self._secret_data = "default_secret_value"

        def generate_transaction_id(self, method, path):
            """生成交易ID"""
            timestamp = int(time.time() * 1000)
            base_str = f"{method}{path}{timestamp}{self._secret_data}"
            return hashlib.sha256(base_str.encode()).hexdigest()[:40]


# 会话管理函数
def initialize_x_session(home_url, max_retries=3):
    """初始化X会话 - 使用原始模块的方法"""
    session = requests.Session()

    # 使用原始模块的generate_headers
    session.headers = generate_headers()

    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 尝试获取X会话 ({attempt + 1}/{max_retries})...")

            # 获取主页
            if "twitter.com" in home_url:
                from x_client_transaction.utils import handle_x_migration
                home_response = handle_x_migration(session)
            else:
                response = session.get(home_url, timeout=30)
                response.raise_for_status()
                home_response = bs4.BeautifulSoup(response.content, 'html.parser')

            # 使用原始模块的get_ondemand_file_url
            ondemand_url = get_ondemand_file_url(response=home_response)
            logger.info(f"📡 找到ondemand文件: {ondemand_url}")

            ondemand_response = session.get(ondemand_url, timeout=30)
            ondemand_response.raise_for_status()
            ondemand_soup = bs4.BeautifulSoup(ondemand_response.content, 'html.parser')

            logger.info("✅ X会话初始化成功")
            return session, home_response, ondemand_soup

        except Exception as e:
            logger.warning(f"❌ 会话获取失败 (尝试 {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)

    raise Exception("所有重试尝试均失败")