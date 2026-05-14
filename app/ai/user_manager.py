"""用户管理系统 - SQLite + JWT（已安全加固）"""

import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import bcrypt
import jwt

DB_PATH = "data/users.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET 环境变量未设置。"
        "请在 .env 中配置：JWT_SECRET=$(openssl rand -hex 32)"
    )
JWT_EXPIRE_HOURS = int(os.environ.get("USER_JWT_EXPIRE_HOURS", "72"))


class UserManager:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._init_db()
        self._dummy_hash = self._hash_password("dummyfortiming")

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
        c.execute('''CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            platform TEXT,
            score REAL DEFAULT 0,
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_config (
            user_id INTEGER PRIMARY KEY,
            image_api_key TEXT DEFAULT '',
            image_base_url TEXT DEFAULT 'https://api.openai.com/v1',
            image_model TEXT DEFAULT 'dall-e-3',
            image_size TEXT DEFAULT '1024x1024',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        conn.commit()
        conn.close()

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith("$2b$"):
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        # 旧 SHA256 验证（迁移用）
        old_hash = hashlib.sha256(f"aititles_salt_2026{password}".encode()).hexdigest()
        return old_hash == password_hash

    def register(self, phone: str, password: str):
        if len(phone) != 11 or not phone.isdigit():
            return {"success": False, "error": "请输入11位手机号"}
        if len(password) < 6:
            return {"success": False, "error": "密码至少6位"}

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id FROM users WHERE phone=?", (phone,))
            if c.fetchone():
                return {"success": False, "error": "该手机号已注册"}

            pw_hash = self._hash_password(password)
            c.execute("INSERT INTO users (phone, password_hash) VALUES (?, ?)", (phone, pw_hash))
            conn.commit()
            user_id = c.lastrowid

            token = self._gen_token(user_id, phone)
            return {"success": True, "token": token, "phone": phone, "plan": "free", "daily_limit": 3}
        except Exception as e:
            return {"success": False, "error": f"注册失败：{str(e)}"}
        finally:
            conn.close()

    def reset_password(self, phone: str, new_password: str):
        if len(phone) != 11 or not phone.isdigit():
            return {"success": False, "error": "请输入11位手机号"}
        if len(new_password) < 6:
            return {"success": False, "error": "密码至少6位"}

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id FROM users WHERE phone=?", (phone,))
            if not c.fetchone():
                return {"success": False, "error": "该手机号未注册"}
            pw_hash = self._hash_password(new_password)
            c.execute("UPDATE users SET password_hash=? WHERE phone=?", (pw_hash, phone))
            conn.commit()
            return {"success": True, "msg": "密码重置成功"}
        except Exception as e:
            return {"success": False, "error": f"重置失败：{str(e)}"}
        finally:
            conn.close()

    def login(self, phone: str, password: str):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id, phone, plan, daily_ai_limit, password_hash FROM users WHERE phone=?", (phone,))
            user = c.fetchone()
            # 防止时序攻击：即使用户不存在也执行一次哈希比对
            dummy_hash = self._dummy_hash
            stored_hash = user[4] if user else dummy_hash
            if not self._verify_password(password, stored_hash) or not user:
                return {"success": False, "error": "手机号或密码错误"}

            # Auto-upgrade old SHA256 hash to bcrypt
            if not user[4].startswith("$2b$"):
                c.execute("UPDATE users SET password_hash=? WHERE id=?", (self._hash_password(password), user[0]))
                conn.commit()

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
            c.execute("SELECT count FROM usage_log WHERE user_id=? AND action='ai_generate' AND date=?", (user_id, today))
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
            c.execute("""INSERT INTO usage_log (user_id, action, date, count)
                        VALUES (?, 'ai_generate', ?, 1)
                        ON CONFLICT(user_id, action, date)
                        DO UPDATE SET count = count + 1""", (user_id, today))
            conn.commit()
            usage["used"] += 1
            usage["remaining"] -= 1
            return {"success": True, "usage": usage}
        finally:
            conn.close()

    def set_vip(self, phone):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("UPDATE users SET plan='vip', daily_ai_limit=9999 WHERE phone=?", (phone,))
            conn.commit()
            return {"success": True, "msg": f"{phone} 已升级为VIP"}
        finally:
            conn.close()

    def save_history(self, user_id, action, platform, title="", score=0, grade="", product_info="", result_json=""):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("""INSERT INTO history (user_id, action, platform, title, score, grade, product_info, result_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (user_id, action, platform, title, score, grade, product_info, result_json))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def get_history(self, user_id, limit=50):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("""SELECT id, action, platform, title, score, grade, product_info, created_at
                        FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?""", (user_id, limit))
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
            c.execute("SELECT id, phone, plan, daily_ai_limit, created_at FROM users ORDER BY id DESC")
            users = []
            for row in c.fetchall():
                users.append({"id": row[0], "phone": row[1], "plan": row[2], "daily_limit": row[3], "created_at": row[4]})
            return users
        finally:
            conn.close()

    def _gen_token(self, user_id, phone):
        payload = {
            "user_id": user_id,
            "phone": phone,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # ── 收藏夹 ──────────────────────────────────────────────────
    def add_favorite(self, user_id, title, platform="", score=0, source=""):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id FROM favorites WHERE user_id=? AND title=? AND platform=?",
                      (user_id, title, platform))
            if c.fetchone():
                return {"success": False, "error": "已收藏过该标题"}
            c.execute("INSERT INTO favorites (user_id, title, platform, score, source) VALUES (?, ?, ?, ?, ?)",
                      (user_id, title, platform, score, source))
            conn.commit()
            return {"success": True, "id": c.lastrowid}
        finally:
            conn.close()

    def remove_favorite(self, user_id, favorite_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (favorite_id, user_id))
            conn.commit()
            return {"success": True}
        finally:
            conn.close()

    def get_favorites(self, user_id, limit=100):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT id, title, platform, score, source, created_at FROM favorites WHERE user_id=? ORDER BY id DESC LIMIT ?",
                      (user_id, limit))
            records = []
            for row in c.fetchall():
                records.append({"id": row[0], "title": row[1], "platform": row[2], "score": row[3], "source": row[4], "created_at": row[5]})
            return records
        finally:
            conn.close()

    # ── 生图配置 ──────────────────────────────────────────────────
    def get_image_config(self, user_id: int):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT image_api_key, image_base_url, image_model, image_size, updated_at FROM user_config WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if not row:
                return {
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "model": "dall-e-3",
                    "size": "1024x1024",
                    "updated_at": "",
                }
            key = row[0]
            # 脱敏显示
            masked = ""
            if key:
                decoded = key
                try:
                    import base64
                    decoded = base64.b64decode(key.encode()).decode()
                except Exception:
                    pass
                if len(decoded) > 8:
                    masked = decoded[:3] + "****" + decoded[-4:]
                else:
                    masked = "****"
            return {
                "api_key": masked,
                "base_url": row[1],
                "model": row[2],
                "size": row[3],
                "updated_at": row[4],
            }
        finally:
            conn.close()

    def save_image_config(self, user_id: int, api_key: str = "", base_url: str = "", model: str = "", size: str = ""):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            # 如果 api_key 为空，保留原值
            if not api_key:
                c.execute("SELECT image_api_key FROM user_config WHERE user_id=?", (user_id,))
                row = c.fetchone()
                if row and row[0]:
                    api_key = row[0]
            else:
                # base64 编码存储
                import base64
                api_key = base64.b64encode(api_key.encode()).decode()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""INSERT INTO user_config (user_id, image_api_key, image_base_url, image_model, image_size, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id)
                        DO UPDATE SET
                            image_api_key=excluded.image_api_key,
                            image_base_url=excluded.image_base_url,
                            image_model=excluded.image_model,
                            image_size=excluded.image_size,
                            updated_at=excluded.updated_at""",
                     (user_id, api_key, base_url or "https://api.openai.com/v1", model or "dall-e-3", size or "1024x1024", now))
            conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def _get_raw_image_api_key(self, user_id: int) -> str:
        """获取未脱敏的 API key（用于后端调用）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT image_api_key FROM user_config WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if not row or not row[0]:
                return ""
            key = row[0]
            try:
                import base64
                return base64.b64decode(key.encode()).decode()
            except Exception:
                return key
        finally:
            conn.close()


user_manager = UserManager()
