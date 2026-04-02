from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import json
from pathlib import Path

from backend.database import get_db
from backend.app.models.notification_log import NotificationLog
from backend.app.schemas.common import ApiResponse, PageResult
from backend.config import settings as _settings

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---------- Pydantic schemas ----------
class NotificationConfigOut(BaseModel):
    dingtalk_webhook_url: str = ""
    dingtalk_webhook_secret: str = ""
    enabled: bool = True


class NotificationConfigUpdate(BaseModel):
    dingtalk_webhook_url: Optional[str] = None
    dingtalk_webhook_secret: Optional[str] = None
    enabled: Optional[bool] = None


class NotificationLogOut(BaseModel):
    id: int
    event_type: str
    related_id: Optional[int] = None
    channel: str = "dingtalk"
    message_title: Optional[str] = None
    message_body: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/notifications", tags=["通知管理"])

# 持久化配置文件路径
_CONFIG_FILE = _settings.data_dir / "notification_config.json"


def _load_config() -> dict:
    """从文件加载通知配置，不存在则从 settings 初始化"""
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "dingtalk_webhook_url": _settings.dingtalk_webhook_url or "",
        "dingtalk_webhook_secret": _settings.dingtalk_webhook_secret or "",
        "enabled": True,
    }


def _save_config(config: dict):
    """保存通知配置到文件"""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


# 启动时从文件加载
_notification_config = _load_config()


@router.get("/config", response_model=ApiResponse[NotificationConfigOut])
async def get_notification_config():
    return ApiResponse(data=NotificationConfigOut(**_notification_config))


@router.put("/config", response_model=ApiResponse[NotificationConfigOut])
async def update_notification_config(data: NotificationConfigUpdate):
    for key, value in data.model_dump(exclude_unset=True).items():
        _notification_config[key] = value
    _save_config(_notification_config)
    return ApiResponse(data=NotificationConfigOut(**_notification_config))


@router.post("/test-send", response_model=ApiResponse)
async def test_send_notification(db: AsyncSession = Depends(get_db)):
    """发送测试通知到钉钉"""
    webhook_url = _notification_config.get("dingtalk_webhook_url", "")
    if not webhook_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="请先配置 Webhook URL")

    webhook_secret = _notification_config.get("dingtalk_webhook_secret", "")

    try:
        from mcp_servers.dingtalk_mcp.client import DingtalkClient
        from backend.config import settings
        client = DingtalkClient(
            app_key=settings.dingtalk_app_key,
            app_secret=settings.dingtalk_app_secret,
        )
        result = await client.send_markdown(
            webhook_url=webhook_url,
            title="QA Master 测试通知",
            content="### QA Master 测试通知\n\n钉钉通知配置验证成功！",
            secret=webhook_secret or None,
        )

        if result.get("errcode") == 0:
            # 记录日志
            log = NotificationLog(
                event_type="test_send",
                channel="dingtalk",
                message_title="QA Master 测试通知",
                message_body="钉钉通知配置验证成功！",
                status="success",
            )
            db.add(log)
            await db.commit()
            return ApiResponse(data={"status": "success", "message": "测试通知发送成功"})
        else:
            error_msg = result.get("errmsg", str(result))
            log = NotificationLog(
                event_type="test_send",
                channel="dingtalk",
                message_title="QA Master 测试通知",
                status="failed",
                error_message=error_msg,
            )
            db.add(log)
            await db.commit()
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"发送失败: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        log = NotificationLog(
            event_type="test_send",
            channel="dingtalk",
            message_title="QA Master 测试通知",
            status="failed",
            error_message=str(e),
        )
        db.add(log)
        await db.commit()
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"发送异常: {str(e)}")


@router.get("/logs", response_model=ApiResponse[PageResult[NotificationLogOut]])
async def list_notification_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(NotificationLog)
    count_query = select(func.count(NotificationLog.id))

    if event_type:
        query = query.where(NotificationLog.event_type == event_type)
        count_query = count_query.where(NotificationLog.event_type == event_type)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(NotificationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [NotificationLogOut.model_validate(log) for log in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))
