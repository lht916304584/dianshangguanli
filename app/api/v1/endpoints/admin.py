"""管理员 API — VIP设置/用户列表/统计数据/最近记录"""

import sqlite3
from datetime import datetime

from fastapi import APIRouter

from app.ai.user_manager import user_manager

router = APIRouter()

ADMIN_KEY = "aititles2026admin"


def _check_admin(admin_key: str):
    return admin_key == ADMIN_KEY


@router.get("/set-vip")
async def set_vip(phone: str, admin_key: str = ""):
    if not _check_admin(admin_key):
        return {"success": False, "error": "无权限"}
    return user_manager.set_vip(phone)


@router.get("/users")
async def list_users(admin_key: str = ""):
    if not _check_admin(admin_key):
        return {"success": False, "error": "无权限"}
    return user_manager.list_users()


@router.get("/stats")
async def admin_stats(admin_key: str = ""):
    if not _check_admin(admin_key):
        return {"success": False, "error": "无权限"}
    conn = sqlite3.connect("data/users.db")
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
async def admin_recent_history(admin_key: str = ""):
    if not _check_admin(admin_key):
        return {"success": False, "error": "无权限"}
    conn = sqlite3.connect("data/users.db")
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
