import os
import time
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

from .header_generators.transaction_id import ClientTransaction, initialize_x_session
from .header_generators.xpff import XPFFHeaderGenerator
from .config import Config

logger = logging.getLogger(__name__)
config = Config()

app = FastAPI(title="X Header Generator API", version="1.0.0")


# 全局状态变量
class ServiceState:
    def __init__(self):
        self.start_time = time.time()
        self.tid_enabled = False
        self.last_update = None
        self.session_data = None  # (session, home_response, ondemand_response)


service_state = ServiceState()
xpff_generator = XPFFHeaderGenerator(config.base_key)


@app.get("/gen_tid")
async def generate_transaction_id(path: str, method: str = "GET", count: int = 1):
    """生成X-Client-Transaction ID"""
    if not service_state.tid_enabled:
        raise HTTPException(status_code=503, detail="服务不可用：缺少有效的X会话")

    if not path.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="path参数必须是完整的URL")

    try:
        # 提取URL路径
        parsed_url = urlparse(path)
        api_path = parsed_url.path

        # 生成多个Transaction ID
        session, home_response, ondemand_response = service_state.session_data
        client_transaction = ClientTransaction(home_response, ondemand_response)

        transaction_ids = []
        for _ in range(count):
            tid = client_transaction.generate_transaction_id(method.upper(), api_path)
            transaction_ids.append(tid)

        logger.info(f"✅ 成功生成 {count} 个Transaction ID")
        return PlainTextResponse("\n".join(transaction_ids))

    except Exception as e:
        logger.error(f"生成Transaction ID失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.get("/gen_xpff")
async def generate_xpff_header(guest_id: str, ua: Optional[str] = None):
    """生成X-Xp-Forwarded-For头"""
    try:
        logger.info(f"📨 接收到生成XPFF请求: guest_id={guest_id}, ua={ua}")

        # FastAPI会自动URL解码，所以我们需要重新编码回去
        if ":" in guest_id and "%3A" not in guest_id:
            # 将冒号重新编码为%3A
            import urllib.parse
            guest_id = guest_id.replace(":", "%3A")
            logger.debug(f"🔁 重新编码guest_id: {guest_id}")

        # 使用当前时间戳
        timestamp = int(time.time() * 1000)

        # 使用传入的UA或默认UA
        user_agent = ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"

        # 使用true，与官方一致
        payload_str = f'{{"navigator_properties":{{"hasBeenActive":"true","userAgent":"{user_agent}","webdriver":"false"}},"created_at":{timestamp}}}'

        # 生成加密头 - 使用重新编码后的guest_id
        xpff_header = xpff_generator.generate_xpff(payload_str, guest_id)
        logger.info(f"✅ 成功生成XPFF头，长度: {len(xpff_header)}字符")

        return JSONResponse({
            "status": "success",
            "xpff_header": xpff_header,
            "length": len(xpff_header),
            "guest_id_used": guest_id,
            "has_been_active": "true"
        })

    except Exception as e:
        logger.error(f"生成XPFF头失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.get("/status")
async def get_status(action: Optional[str] = None):
    """获取服务状态"""
    if action == "refresh_session":
        return await refresh_session()

    # 返回简洁的状态信息
    status_info = {
        "status": "running",
        "services": {
            "gen_tid": {
                "enabled": service_state.tid_enabled,
                "health": "healthy" if service_state.tid_enabled else "unhealthy"
            },
            "gen_xpff": {
                "enabled": True,
                "health": "healthy"
            }
        },
        "server_port": config.server_port,
        "process_id": os.getpid(),
        "uptime": int(time.time() - service_state.start_time)
    }

    # 添加最后更新时间（如果存在）
    if service_state.last_update:
        status_info["last_update"] = service_state.last_update

    return JSONResponse(status_info)


async def refresh_session():
    """手动刷新会话"""
    try:
        logger.info("手动刷新X会话...")
        session_data = initialize_x_session(config.home_url)
        service_state.session_data = session_data
        service_state.tid_enabled = True
        service_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = {
            "action": "refresh_session",
            "success": True,
            "message": "X会话手动更新成功",
            "status": {
                "gen_tid_enabled": True,
                "last_update": service_state.last_update
            }
        }
        logger.info("手动刷新成功")
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"手动刷新失败: {e}")
        result = {
            "action": "refresh_session",
            "success": False,
            "message": f"刷新失败: {str(e)}",
            "status": {
                "gen_tid_enabled": service_state.tid_enabled,
                "last_update": service_state.last_update
            }
        }
        return JSONResponse(result, status_code=500)