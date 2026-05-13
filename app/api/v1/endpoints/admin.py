"""管理员 API — VIP设置/用户列表/统计数据/最近记录（已安全加固）"""

import os
from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.ai.user_manager import user_manager

router = APIRouter()

# 从环境变量读取管理员密钥，不提供硬编码默认值
_ADMIN_KEY = os.environ.get("ADMIN_SECRET_KEY", "")
DB_PATH = "data/users.db"


def _require_admin(admin_key: str) -> None:
    """校验管理员密钥（通过 Header 传入，而非 URL 参数）。"""
    if not _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务端未配置 ADMIN_SECRET_KEY，管理接口不可用",
        )
    if not admin_key or admin_key != _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限",
        )


class SetVipRequest(BaseModel):
    phone: str


@router.post("/set-vip")
async def set_vip(
    req: SetVipRequest,
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
):
    """将指定手机号升级为 VIP（需要 X-Admin-Key Header）。"""
    _require_admin(x_admin_key)
    return user_manager.set_vip(req.phone)


@router.get("/users")
async def list_users(
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
):
    """获取所有用户列表。"""
    _require_admin(x_admin_key)
    return user_manager.list_users()


@router.get("/stats")
async def admin_stats(
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
):
    """获取平台统计数据（异步 SQLite，不阻塞事件循环）。"""
    _require_admin(x_admin_key)
    today = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM history WHERE action='score'") as cur:
            total_scores = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM history WHERE action='generate'") as cur:
            total_generates = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM history WHERE created_at LIKE ?",
            (today + "%",),
        ) as cur:
            today_active = (await cur.fetchone())[0]

    return {
        "total_scores": total_scores,
        "total_generates": total_generates,
        "today_active": today_active,
    }


@router.get("/recent-history")
async def admin_recent_history(
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
):
    """获取最近50条操作历史（异步 SQLite）。"""
    _require_admin(x_admin_key)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT h.user_id, h.action, h.platform, h.title, h.score, h.created_at, u.phone "
            "FROM history h LEFT JOIN users u ON h.user_id=u.id "
            "ORDER BY h.id DESC LIMIT 50"
        ) as cur:
            rows = await cur.fetchall()

    records = [
        {
            "user_id": row[0], "action": row[1], "platform": row[2],
            "title": row[3], "score": row[4], "created_at": row[5], "phone": row[6],
        }
        for row in rows
    ]
    return {"records": records}
