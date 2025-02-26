from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine
from app.models import Base
from app.routers import chat, users, auth
from elasticsearch import AsyncElasticsearch

es = AsyncElasticsearch(hosts=["http://elasticsearch:9200"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: tworzymy tabele w bazie danych
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    index_name = "users"
    # Sprawdzamy, czy indeks już istnieje
    if not await es.indices.exists(index=index_name):
        await es.indices.create(
            index=index_name,
            body={
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                },
                "mappings": {
                    "properties": {
                        "username": {"type": "text"},
                    }
                }
            }
        )
    yield
    # Możesz tu dodać kod wykonywany przy zamykaniu aplikacji, np. czyszczenie zasobów

app = FastAPI(lifespan=lifespan)

# Importujemy routery
app.include_router(chat.router)
app.include_router(chat.ws_router)
app.include_router(users.router)
app.include_router(auth.router)
