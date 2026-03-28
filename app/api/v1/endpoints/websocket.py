"""
WebSocket gateway with Redis pub/sub.

Flow:
  Client --WS--> FastAPI endpoint --> subscribes to Redis channel
  Any service   --> publishes to Redis channel --> broadcast to all subscribers
"""
import asyncio
import json
import logging
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_token
from app.db.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """In-process WebSocket registry (per-instance). For multi-instance deployments
    use Redis pub/sub (see subscribe_and_forward below)."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}  # room_id -> {ws}

    async def connect(self, websocket: WebSocket, room: str) -> None:
        await websocket.accept()
        self._connections.setdefault(room, set()).add(websocket)
        logger.info("WS connected: room=%s total=%d", room, len(self._connections[room]))

    def disconnect(self, websocket: WebSocket, room: str) -> None:
        self._connections.get(room, set()).discard(websocket)
        logger.info("WS disconnected: room=%s", room)

    async def broadcast(self, room: str, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(room, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, room)


manager = ConnectionManager()


async def _get_user_id_from_token(token: str) -> str | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


async def _subscribe_and_forward(
    websocket: WebSocket,
    channel: str,
    redis: aioredis.Redis,
) -> None:
    """Subscribe to a Redis channel and forward messages to the WebSocket."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception as e:
                    logger.warning("Failed to forward WS message: %s", e)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """
    Connect: ws://host/api/v1/ws/{room_id}?token=<JWT>

    On connect, authenticate via query-param JWT, then:
      • Subscribe to Redis channel `ws:room:{room_id}`
      • Forward any published messages to this client
      • Echo client messages back to the room
    """
    token = websocket.query_params.get("token")
    user_id = await _get_user_id_from_token(token) if token else None
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, room_id)
    channel = f"ws:room:{room_id}"

    # Start Redis subscriber in background
    subscriber_task = asyncio.create_task(
        _subscribe_and_forward(websocket, channel, redis)
    )

    try:
        while True:
            data = await websocket.receive_json()
            # Publish to Redis so all instances can broadcast
            payload = json.dumps({"user_id": user_id, "room": room_id, **data})
            await redis.publish(channel, payload)
    except WebSocketDisconnect:
        logger.info("Client disconnected: user=%s room=%s", user_id, room_id)
    finally:
        subscriber_task.cancel()
        manager.disconnect(websocket, room_id)


@router.websocket("/ws/notify/{user_id}")
async def personal_notifications(
    websocket: WebSocket,
    user_id: str,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """
    Personal notification channel: ws://host/api/v1/ws/notify/{user_id}?token=<JWT>
    Backend publishes to `ws:user:{user_id}` to push events to a specific user.
    """
    token = websocket.query_params.get("token")
    token_user_id = await _get_user_id_from_token(token) if token else None
    if token_user_id != user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    channel = f"ws:user:{user_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
