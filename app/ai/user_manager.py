"""用户管理系统 - SQLite + JWT（已安全加固）"""

import os
import sqlite3
import secrets
from datetime import datetime, timedelta

import bcrypt
import jwt

DB_PATH = "data/users.db"
# 从环境变量读取，不提供硬编码默认值——启动时若未配置会快速失败
JWT_SECRET = os.environ.get("USER_JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError(
        "USER_JWT_SECRET 环境变量未设置。"
        "请在 .env 中配置：USER_JWT_SECRET=$(openssl rand -hex 32)"
    )
JWT_EXPIRE_HOURS = int(os.environ.get("USER_JWT_EXPIRE_HOURS", "72"))


class UserManager:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            daily_ai_limit INTEGER DEFAULT 3,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            date TEXT,
            count INTEGER DEFAULT 0,
            UNIQUE(user_id, action, date)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            platform TEXT,
            title TEXT,
            score REAL,
            grade TEXT,
            product_info TEXT,
            result_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()

    # ── 密码哈希（bcrypt + 随机 salt，每次不同）────────────────────────
    def _hash_password(self, password: str) -> str:
        """使用 bcrypt 哈希密码，salt 随机生成并内嵌在结果中"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def register(self, phone: str, password: str):
        if len(phone) != 11 or not phone.isdigit():
            return {"success": False, "error": "请输入11位手机号"}
        if len(password) < 8:
            return {"success": False, "error": "密码至少8位"}

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id FROM users WHERE phone=?", (phone,))
            if c.fetchone():
                return {"success": False, "error": "该手机号已注册"}

            pw_hash = self._hash_password(password)
            c.execute(
                "INSERT INTO users (phone, password_hash) VALUES (?, ?)",
                (phone, pw_hash),
            )
            conn.commit()
            user_id = c.lastrowid
            token = self._gen_token(user_id, phone)
            return {"success": True, "token": token, "phone": phone, "plan": "free", "daily_limit": 3}
        except Exception as e:
            return {"success": False, "error": f"注册失败：{str(e)}"}
        finally:
            conn.close()

    def login(self, phone: str, password: str):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "SELECT id, phone, plan, daily_ai_limit, password_hash FROM users WHERE phone=?",
                (phone,),
            )
            user = c.fetchone()
            # 防止时序攻击：即使用户不存在也执行一次哈希比对
            dummy_hash = "$2b$12$invalidhashfortimingprotection000000000000000000000000"
            stored_hash = user[4] if user else dummy_hash
            if not self._verify_password(password, stored_hash) or not user:
                return {"success": False, "error": "手机号或密码错误"}

            token = self._gen_token(user[0], user[1])
            return {
                "success": True,
                "token": token,
                "phone": user[1],
                "plan": user[2],
                "daily_limit": user[3],
            }
        finally:
            conn.close()

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return {"valid": True, "user_id": payload["user_id"], "phone": payload["phone"]}
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "登录已过期，请重新登录"}
        except Exception:
            return {"valid": False, "error": "无效的登录状态"}

    def get_usage(self, user_id: int):
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "SELECT count FROM usage_log WHERE user_id=? AND action='ai_generate' AND date=?",
                (user_id, today),
            )
            row = c.fetchone()
            used = row[0] if row else 0

            c.execute("SELECT plan, daily_ai_limit FROM users WHERE id=?", (user_id,))
            user = c.fetchone()
            plan = user[0] if user else "free"
            limit = user[1] if user else 3

            if plan == "vip":
                limit = 9999

            return {"used": used, "limit": limit, "remaining": max(0, limit - used), "plan": plan}
        finally:
            conn.close()

    def use_credit(self, user_id: int):
        usage = self.get_usage(user_id)
        if usage["remaining"] <= 0:
            return {"success": False, "error": "今日次数已用完", "usage": usage}

        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                """INSERT INTO usage_log (user_id, action, date, count)
                   VALUES (?, 'ai_generate', ?, 1)
                   ON CONFLICT(user_id, action, date)
                   DO UPDATE SET count = count + 1""",
                (user_id, today),
            )
            conn.commit()
            usage["used"] += 1
            usage["remaining"] -= 1
            return {"success": True, "usage": usage}
        finally:
            conn.close()

    def set_vip(self, phone: str):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "UPDATE users SET plan='vip', daily_ai_limit=9999 WHERE phone=?",
                (phone,),
            )
            conn.commit()
            return {"success": True, "msg": f"{phone} 已升级为VIP"}
        finally:
            conn.close()

    def save_history(
        self,
        user_id: int,
        action: str,
        platform: str,
        title: str = "",
        score: float = 0,
        grade: str = "",
        product_info: str = "",
        result_json: str = "",
    ):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                """INSERT INTO history
                   (user_id, action, platform, title, score, grade, product_info, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, action, platform, title, score, grade, product_info, result_json),
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def get_history(self, user_id: int, limit: int = 50):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                """SELECT id, action, platform, title, score, grade, product_info, created_at
                   FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            )
            records = []
            for row in c.fetchall():
                records.append({
                    "id": row[0], "action": row[1], "platform": row[2],
                    "title": row[3], "score": row[4], "grade": row[5],
                    "product_info": row[6], "created_at": row[7],
                })
            return records
        finally:
            conn.close()

    def list_users(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "SELECT id, phone, plan, daily_ai_limit, created_at FROM users ORDER BY id DESC"
            )
            users = []
            for row in c.fetchall():
                users.append({
                    "id": row[0], "phone": row[1], "plan": row[2],
                    "daily_limit": row[3], "created_at": row[4],
                })
            return users
        finally:
            conn.close()

    def _gen_token(self, user_id: int, phone: str) -> str:
        payload = {
            "user_id": user_id,
            "phone": phone,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
            "jti": secrets.token_hex(16),   # 唯一 ID，便于后续实现黑名单
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


user_manager = UserManager()
