import time
import threading
import logging
from datetime import datetime
import sys
import os
import socket
import traceback

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'service.log')

# 设置文件日志（只输出到文件，不输出到控制台）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='a')
    ]
)

logger = logging.getLogger(__name__)

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """设置日志格式 - 只使用文件日志"""
    try:
        from src.config import Config
        config = Config()

        # 根据debug配置设置日志级别
        log_level = logging.DEBUG if config.debug else logging.INFO

        # 更新root logger级别
        logging.getLogger().setLevel(log_level)

        logger.info(f"日志级别设置为: {logging.getLevelName(log_level)}")

    except Exception as e:
        logger.error(f"日志设置失败: {e}")


def initialize_session():
    """初始化X会话"""
    try:
        from src.config import Config
        from src.header_generators.transaction_id import initialize_x_session
        from src.api_server import service_state

        config = Config()
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"尝试初始化X会话 ({attempt + 1}/{max_retries})")
                session_data = initialize_x_session(config.home_url)
                service_state.session_data = session_data
                service_state.tid_enabled = True
                service_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info("X会话初始化成功")
                return True
            except Exception as e:
                logger.error(f"会话初始化失败: {e}")
                if attempt == max_retries - 1:
                    logger.warning("无法初始化X会话，服务进入降级模式")
                    service_state.tid_enabled = False
                    return False
                time.sleep(2)
    except Exception as e:
        logger.error(f"初始化会话时发生错误: {e}")
        return False


def background_session_updater():
    """后台会话更新线程"""
    try:
        from src.config import Config
        from src.header_generators.transaction_id import initialize_x_session
        from src.api_server import service_state

        config = Config()
        refresh_interval = config.refresh_interval

        logger.info(f"后台会话更新线程启动，间隔: {refresh_interval}秒")

        while True:
            time.sleep(refresh_interval)
            try:
                logger.debug("后台自动更新X会话")
                session_data = initialize_x_session(config.home_url)
                service_state.session_data = session_data
                service_state.tid_enabled = True
                service_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.debug("后台会话更新成功")
            except Exception as e:
                logger.error(f"后台会话更新失败: {e}")
    except Exception as e:
        logger.error(f"后台线程启动失败: {e}")


def is_port_in_use(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except socket.error:
            return True


def main():
    """主函数"""
    try:
        # 如果是打包环境，重定向标准输出
        if hasattr(sys, 'frozen'):
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')

        logger.info("=" * 50)
        logger.info("开始启动应用")
        logger.info("=" * 50)

        setup_logging()

        from src.config import Config
        config = Config()

        logger.info(f"服务端口: {config.server_port}")

        # 检查端口是否被占用
        if is_port_in_use(config.server_port):
            logger.error(f"端口 {config.server_port} 已被占用")
            # 给用户时间查看日志
            time.sleep(5)
            sys.exit(1)

        # 初始化X会话
        logger.info("预初始化X交易服务")
        initialize_session()

        # 启动后台更新线程
        updater_thread = threading.Thread(target=background_session_updater, daemon=True)
        updater_thread.start()
        logger.info("后台会话更新线程已启动")

        # 启动API服务器
        logger.info("启动API服务器")

        from src.api_server import app
        import uvicorn

        # 配置uvicorn也使用文件日志
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=config.server_port,
            log_config=None,  # 禁用uvicorn的默认日志配置
            access_log=False  # 禁用访问日志
        )

    except KeyboardInterrupt:
        logger.info("服务正常退出")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        logger.error(traceback.format_exc())
        # 给用户时间查看日志
        time.sleep(10)
    finally:
        logger.info("服务停止")


if __name__ == "__main__":
    main()