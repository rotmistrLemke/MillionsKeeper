"""
Авторизация: хеши паролей (bcrypt) + JWT access-токены + users.json.

Роли:
  - admin: полный доступ (CRUD потоков, закрытие позиций, управление пользователями)
  - user:  read-only + бэктесты

Bootstrap: при первом запуске, если users.json пустой, создаётся admin
с паролем из env ADMIN_PASSWORD. Если env не задан — генерируется случайный
и печатается в stdout один раз.
"""
import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from passlib.context import CryptContext
from jose import jwt, JWTError

logger = logging.getLogger("Auth")

ROLE_ADMIN = "admin"
ROLE_USER  = "user"
ROLES      = (ROLE_ADMIN, ROLE_USER)

_USERS_FILE    = Path(__file__).parent / "users.json"
_JWT_KEY_FILE  = Path(__file__).parent / ".jwt_secret"
_TOKEN_TTL_MIN = 60 * 24 * 7  # неделя

_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _load_or_create_jwt_secret() -> str:
    """Держим JWT-секрет в файле .jwt_secret (создаётся при первом запуске)."""
    env_key = os.environ.get("JWT_SECRET")
    if env_key:
        return env_key
    if _JWT_KEY_FILE.exists():
        try:
            return _JWT_KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning(f"Не удалось прочитать .jwt_secret: {e}")
    secret = secrets.token_urlsafe(64)
    try:
        _JWT_KEY_FILE.write_text(secret, encoding="utf-8")
        logger.info(f"JWT secret создан в {_JWT_KEY_FILE.name}")
    except OSError as e:
        logger.warning(f"Не удалось сохранить .jwt_secret: {e}")
    return secret


_JWT_SECRET = _load_or_create_jwt_secret()
_JWT_ALG    = "HS256"


@dataclass
class UserRecord:
    username: str
    password_hash: str
    role: str                 # admin | user
    created_at: str           # ISO
    updated_at: str           # ISO
    avatar: str = ""          # data: URL или пусто

    def to_public(self) -> dict:
        """Безопасное представление для REST — без пароля."""
        return {
            "username":   self.username,
            "role":       self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "avatar":     self.avatar,
        }


class UserRegistry:
    def __init__(self):
        self._users: dict[str, UserRecord] = {}
        self._lock = threading.RLock()

    def all(self) -> list[UserRecord]:
        with self._lock:
            return list(self._users.values())

    def get(self, username: str) -> Optional[UserRecord]:
        with self._lock:
            return self._users.get(username.lower())

    def admin_count(self) -> int:
        with self._lock:
            return sum(1 for u in self._users.values() if u.role == ROLE_ADMIN)

    def create(self, username: str, password: str, role: str) -> UserRecord:
        username = (username or "").strip().lower()
        if not username:
            raise ValueError("username пустой")
        if role not in ROLES:
            raise ValueError(f"Неверная роль: {role}")
        if len(password or "") < 6:
            raise ValueError("Пароль должен быть не короче 6 символов")
        with self._lock:
            if username in self._users:
                raise ValueError(f"Пользователь {username} уже существует")
            now = datetime.now(timezone.utc).isoformat()
            rec = UserRecord(
                username=username,
                password_hash=_pwd_ctx.hash(password),
                role=role,
                created_at=now,
                updated_at=now,
            )
            self._users[username] = rec
        save()
        return rec

    def update(self, username: str, *, password: Optional[str] = None,
               role: Optional[str] = None,
               avatar: Optional[str] = None) -> UserRecord:
        username = (username or "").strip().lower()
        with self._lock:
            rec = self._users.get(username)
            if rec is None:
                raise KeyError(username)
            if role is not None:
                if role not in ROLES:
                    raise ValueError(f"Неверная роль: {role}")
                # Нельзя разжаловать последнего админа.
                if rec.role == ROLE_ADMIN and role != ROLE_ADMIN and self.admin_count() <= 1:
                    raise ValueError("Нельзя разжаловать последнего администратора")
                rec.role = role
            if password is not None:
                if len(password) < 6:
                    raise ValueError("Пароль должен быть не короче 6 символов")
                rec.password_hash = _pwd_ctx.hash(password)
            if avatar is not None:
                if avatar and not avatar.startswith("data:image/"):
                    raise ValueError("Аватар должен быть data:image/...")
                if len(avatar) > 300_000:
                    raise ValueError("Аватар слишком большой (макс ~220 КБ после base64)")
                rec.avatar = avatar
            rec.updated_at = datetime.now(timezone.utc).isoformat()
        save()
        return rec

    def delete(self, username: str) -> bool:
        username = (username or "").strip().lower()
        with self._lock:
            rec = self._users.get(username)
            if rec is None:
                return False
            if rec.role == ROLE_ADMIN and self.admin_count() <= 1:
                raise ValueError("Нельзя удалить последнего администратора")
            self._users.pop(username, None)
        save()
        return True

    def verify_password(self, username: str, password: str) -> Optional[UserRecord]:
        rec = self.get(username)
        if rec is None:
            return None
        try:
            if _pwd_ctx.verify(password, rec.password_hash):
                return rec
        except Exception as e:
            logger.warning(f"verify_password failed: {e}")
        return None


registry = UserRegistry()


def save() -> None:
    items = [asdict(u) for u in registry.all()]
    try:
        _USERS_FILE.write_text(
            json.dumps({"users": items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"Не удалось сохранить {_USERS_FILE.name}: {e}")


def load() -> None:
    if not _USERS_FILE.exists():
        _bootstrap_admin()
        return
    try:
        data = json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Не удалось прочитать {_USERS_FILE.name}: {e}")
        return
    items = data.get("users", []) if isinstance(data, dict) else data
    with registry._lock:
        registry._users.clear()
        for d in items or []:
            try:
                rec = UserRecord(
                    username=str(d["username"]).lower(),
                    password_hash=str(d["password_hash"]),
                    role=str(d.get("role", ROLE_USER)),
                    created_at=str(d.get("created_at") or datetime.now(timezone.utc).isoformat()),
                    updated_at=str(d.get("updated_at") or datetime.now(timezone.utc).isoformat()),
                    avatar=str(d.get("avatar") or ""),
                )
                registry._users[rec.username] = rec
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Пропуск некорректной записи пользователя: {e}")

    if registry.admin_count() == 0:
        logger.warning("users.json не содержит админов — создаю из bootstrap")
        _bootstrap_admin()
    else:
        logger.info(f"Загружено пользователей: {len(registry.all())}")


def _bootstrap_admin() -> None:
    password = os.environ.get("ADMIN_PASSWORD")
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True
    try:
        registry.create(username="admin", password=password, role=ROLE_ADMIN)
        if generated:
            # Печатаем только в этот раз — в последующие запуски пароль берут из users.json.
            logger.warning("=" * 60)
            logger.warning(f"  Создан админ 'admin' со случайным паролем: {password}")
            logger.warning("  Сохраните его — повторно он не будет показан.")
            logger.warning("=" * 60)
        else:
            logger.info("Создан админ 'admin' (пароль из env ADMIN_PASSWORD)")
    except Exception as e:
        logger.error(f"Bootstrap admin failed: {e}")


# ── JWT ──────────────────────────────────────────────────────────────

def create_access_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  username,
        "role": role,
        "iat":  int(now.timestamp()),
        "exp":  int((now + timedelta(minutes=_TOKEN_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
    except JWTError:
        return None


def user_from_token(token: str) -> Optional[UserRecord]:
    payload = decode_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    rec = registry.get(username)
    if rec is None:
        return None
    # Если роль в токене разошлась с актуальной (например, админ разжалован
    # после выдачи токена), то считаем токен недействительным.
    if payload.get("role") != rec.role:
        return None
    return rec
