import asyncio
import json
import aioredis
import os
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.auth import get_current_user, verify_token
from app.models import User, Chat
from app.models import Message
from app.search import index_message, search_messages
from typing import Dict, List, Set

router = APIRouter(prefix="/api/chat")
ws_router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

class ConnectionManager:
    """Zarządza połączeniami WebSocket i jednorazowym nasłuchem Redis"""
    
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}  # Przechowuje połączenia WebSocket dla każdego pokoju
        self.redis_tasks: Dict[str, asyncio.Task] = {}  # Przechowuje jednorazowy nasłuch Redis

    async def connect(self, chat_id: str, websocket: WebSocket):
        """Dodaje WebSocket do listy aktywnych połączeń w danym pokoju"""
        await websocket.accept()
        if chat_id not in self.rooms:
            self.rooms[chat_id] = set()
        self.rooms[chat_id].add(websocket)

        # Jeśli jeszcze nie ma nasłuchu dla tego pokoju, uruchamiamy go
        if chat_id not in self.redis_tasks:
            self.redis_tasks[chat_id] = asyncio.create_task(self.listen_to_redis(chat_id))

    async def disconnect(self, chat_id: str, websocket: WebSocket):
        """Usuwa WebSocket z listy aktywnych połączeń"""
        if chat_id in self.rooms:
            self.rooms[chat_id].discard(websocket)
            if not self.rooms[chat_id]:  # Jeśli pokój jest pusty, usuwamy nasłuch Redis
                del self.rooms[chat_id]
                self.redis_tasks[chat_id].cancel()
                del self.redis_tasks[chat_id]

    async def broadcast(self, chat_id: str, message: str):
        """Wysyła wiadomość do wszystkich użytkowników w danym pokoju"""
        if chat_id in self.rooms:
            for connection in self.rooms[chat_id]:
                await connection.send_text(message)

    async def listen_to_redis(self, chat_id: str):
        """Jednorazowy nasłuch Redis dla pokoju czatu"""
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"chat_channel:{chat_id}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await self.broadcast(chat_id, message["data"])

manager = ConnectionManager()

# @router.websocket("/ws/chat/{chat_id}")
# async def chat_endpoint(websocket: WebSocket, chat_id: str):#, db: AsyncSession = Depends(get_db)):
#     """Obsługuje WebSocket dla danego pokoju czatu"""
#     await manager.connect(chat_id, websocket)

#     try:
#         while True:
#             data = await websocket.receive_text()
            
#             # Zapisujemy wiadomość w bazie danych
#             message = Message(chat_id=chat_id, sender="user", content=data)
#             # db.add(message)
#             # await db.commit()

#             # Publikujemy wiadomość w Redis, co wywoła jej przesłanie do WebSocketów
#             redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
#             await redis.publish(f"chat_channel:{chat_id}", data)

#     except WebSocketDisconnect:
#         await manager.disconnect(chat_id, websocket)


@ws_router.websocket("/ws/chat/{chat_id}")
async def chat_endpoint(websocket: WebSocket, chat_id: int, db: AsyncSession = Depends(get_db)):

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)  # 1008: Policy Violation
        return

    # Validate token manually
    try:
        user = verify_token(token)
    except HTTPException as e:
        await websocket.close(code=1008)
        return

    """ WebSocket obsługujący czaty z autoryzacją """
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"chat_channel:{chat_id}")

    user_db = await db.execute(select(User).options(selectinload(User.chats)).where(User.id == user["sub"]))
    user_db = user_db.scalar()

    if not user_db or chat_id not in [chat.id for chat in user_db.chats]:
        await websocket.close()
        return
    await manager.connect(str(chat_id), websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = Message(chat_id=chat_id, sender=user["preferred_username"], content=data)
            # do dodania tam gdzie tworzymy wiadomośc w bazie
            db.add(message)
            await db.commit()
            await index_message(chat_id, user["preferred_username"], data)
            payload = {
                "id": message.id,
                "sender": message.sender,
                "content": data,
            }
            await redis.publish(f"chat_channel:{chat_id}", json.dumps(payload))
    except WebSocketDisconnect:
        await manager.disconnect(str(chat_id), websocket)

class ChatCreate(BaseModel):
    userId: str
    
@router.post("/chats/")
async def create_chat(chat: ChatCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """ Tworzenie nowego czatu """
    participant = chat.userId
    # existing_chat = await db.execute(select(Chat).where(Chat.name == chat_name))
    # if existing_chat.scalar():
    #     raise HTTPException(status_code=400, detail="Chat already exists")

    chat = Chat(name="")
    user_db = await db.execute(select(User).where(User.id == user["sub"]))
    user_2 = await db.execute(select(User).where(User.id == participant))
    user_db = user_db.scalar()
    user_2 = user_2.scalar()

    if not user_db or not user_2:
        raise HTTPException(status_code=400, detail="Użytkownik musi być zarejestrowany")

    chat.participants.append(user_db)
    chat.participants.append(user_2)
    db.add(chat)
    await db.commit()
    return {"message": "Chat created", "chat_id": chat.id}

@router.get("/chats/")
async def list_chats(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.chats).joinedload(Chat.participants)
        )
        .where(User.id == user["sub"])
    )
    user_db = result.unique().scalar_one_or_none()
    if not user_db:
        # Zamiast zwracać 404, zwracamy pustą listę, co informuje, że użytkownik nie ma jeszcze żadnych czatów
        return []
    return [{"id": chat.id, "name": chat.name, "participants": [{"id": p.id, "username": p.username} for p in chat.participants]} for chat in user_db.chats]


@router.get("/chats/{chat_id}/search")
async def search_chat_messages(chat_id: str, query: str):
    """Wyszukuje wiadomości w czacie"""
    messages = await search_messages(query, chat_id)
    return messages



@router.get("/chats/{chat_id}/messages", response_model=List[dict])
async def get_chat_history(chat_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """ Pobiera historię wiadomości dla danego czatu """
    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp.desc()).limit(limit)
    )
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found")

    return [{"id": msg.id, "sender": msg.sender, "content": msg.content, "timestamp": msg.timestamp} for msg in messages]

@router.get("/test")
async def test_endpoint():
    return { "test":"ok" }