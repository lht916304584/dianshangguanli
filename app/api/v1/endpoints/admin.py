"""管理员 API — VIP设置/用户列表/统计数据/最近记录（已安全加固）"""

import os
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from app.ai.user_manager import user_manager

router = APIRouter()

_ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
DB_PATH = "data/users.db"


def _require_admin(admin_key: str) -> None:
    if not _ADMIN_KEY:
        raise HTTPException(status_code=503, detail="服务端未配置 ADMIN_KEY，管理接口不可用")
    if not admin_key or admin_key != _ADMIN_KEY:
        raise HTTPException(status_code=403, detail="无权限")


@router.post("/set-vip")
async def set_vip(phone: str, x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    _require_admin(x_admin_key)
    return user_manager.set_vip(phone)


@router.get("/users")
async def list_users(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    _require_admin(x_admin_key)
    return user_manager.list_users()


@router.get("/stats")
async def admin_stats(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    _require_admin(x_admin_key)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM history WHERE action='score'")
    total_scores = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM history WHERE action='generate'")
    total_generates = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT user_id) FROM history WHERE created_at LIKE ?", (today + '%',))
    today_active = c.fetchone()[0]
    conn.close()
    return {
        "total_scores": total_scores,
        "total_generates": total_generates,
        "today_active": today_active,
    }


@router.get("/recent-history")
async def admin_recent_history(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    _require_admin(x_admin_key)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT h.user_id, h.action, h.platform, h.title, h.score, h.created_at, u.phone "
        "FROM history h LEFT JOIN users u ON h.user_id=u.id "
        "ORDER BY h.id DESC LIMIT 50"
    )
    records = []
    for row in c.fetchall():
        records.append({
            "user_id": row[0], "action": row[1], "platform": row[2],
            "title": row[3], "score": row[4], "created_at": row[5], "phone": row[6],
        })
    conn.close()
    return {"records": records}
