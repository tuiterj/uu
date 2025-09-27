import json
import os
import sys
from typing import Dict, Any
import logging


def get_config_path():
    """获取配置文件路径 - 兼容打包和开发环境"""
    if getattr(sys, 'frozen', False):
        # 打包成EXE后的情况：从EXE所在目录读取
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'config.json')
    else:
        # 开发环境：从项目根目录读取
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')


class Config:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """加载配置文件"""
        config_path = get_config_path()

        # 调试信息，帮助确认路径
        print(f"🔄 配置文件路径: {config_path}")
        print(f"📁 文件是否存在: {os.path.exists(config_path)}")

        if not os.path.exists(config_path):
            # 如果配置文件不存在，创建默认配置
            self._config = {
                "debug": False,
                "show_cmd_window": True,
                "server_port": 13625,
                "x_client_transaction": {
                    "home_url": "https://x.com",
                    "refresh_interval_minutes": 60
                },
                "xpff": {
                    "base_key": "0e6be1f1e21ffc33590b888fd4dc81b19713e570e805d4e5df80a493c9571a05",
                    "default_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                }
            }
            # 尝试创建默认配置文件
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                print(f"✅ 创建默认配置文件: {config_path}")
            except Exception as e:
                print(f"❌ 创建配置文件失败: {e}")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            print(f"✅ 配置文件加载成功: {config_path}")
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            # 使用默认配置
            self._config = {
                "debug": False,
                "show_cmd_window": True,
                "server_port": 13625,
                "x_client_transaction": {
                    "home_url": "https://x.com",
                    "refresh_interval_minutes": 60
                },
                "xpff": {
                    "base_key": "0e6be1f1e21ffc33590b888fd4dc81b19713e570e805d4e5df80a493c9571a05",
                    "default_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                }
            }

    def get(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def debug(self):
        return self.get('debug', False)

    @property
    def show_cmd_window(self):
        return self.get('show_cmd_window', True)

    @property
    def server_port(self):
        return self.get('server_port', 13625)

    @property
    def home_url(self):
        return self.get('x_client_transaction.home_url', 'https://x.com')

    @property
    def refresh_interval(self):
        return self.get('x_client_transaction.refresh_interval_minutes', 10) * 60  # 转换为秒

    @property
    def base_key(self):
        return self.get('xpff.base_key')

    @property
    def default_user_agent(self):
        return self.get('xpff.default_user_agent')