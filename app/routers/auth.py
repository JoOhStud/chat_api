from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_keycloak import FastAPIKeycloak
from keycloak.keycloak_openid import KeycloakOpenID
from fastapi.security import OAuth2PasswordBearer
import os
from time import sleep
import traceback
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User

router = APIRouter()
keycloak = None

keycloak_openid = KeycloakOpenID(
    server_url=os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080/auth/"),
    realm_name=os.getenv("KEYCLOAK_REALM", "chat_realm"),
    client_id=os.getenv("KEYCLOAK_CLIENT_ID", "chat_client"), # klient skonfigurowany jako bearer-only w Keycloak
    verify=True,
)
# def get_keycloak():
#     global keycloak
#     if keycloak is not None:
#         return keycloak
    
#     while keycloak is None:
#         sleep(5)

#         try:
#             # keycloak = FastAPIKeycloak(
#             #     server_url=os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080/"),
#             #     realm=os.getenv("KEYCLOAK_REALM", "chat_realm"),
#             #     client_id=os.getenv("KEYCLOAK_CLIENT_ID", "chat_client"),
#             #     client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET", "secret"),
#             #     admin_client_secret=os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", "admin-secret"),
#             #     callback_uri=os.getenv("KEYCLOAK_CALLBACK_URI", "http://localhost:8082/auth/callback"),
#             # )
            
#         except Exception as e:
#             print(traceback.format_exc())


#     keycloak.add_swagger_config(router)
#     return keycloak


# tokenUrl nie jest używany w trybie bearer-only, ale musi być podany – możesz użyć dowolnej wartości
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        public_key = (
            "-----BEGIN PUBLIC KEY-----\n"
            + "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5VkAT4Kw/1MYC2pR+XYIHx/j0iZMjfkgpBUXkVfVux4y58WDnekUpyagTd604xIN4ajX4gSgzXx0FGbEcyM7uiFNPfvFlZRyo3eievFaxmkCejYgaRiS2/sFHOoQ/bytf+rjWL4nZv7eAatmOUajjxJZNpVzy2k1c6/945PHzHAa+tI9MD1OV5xwmJsuQF75IZJIlog1xgQdup+EQRGN9JwKa1cvTIdG3cq7oVCmdMn4RHQhldVGqmg484EbfQg6DqRilos2ng1iqoAiLK6A0tZSC8ye7V6CFu/cjJvnwQTh2fk2K3BRAQXL3zIfDjOt7RHVmch6uCvWsTAjvFhjvwIDAQAB"
            + "\n-----END PUBLIC KEY-----"
        )
        decoded_token = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_aud": False})
        return decoded_token
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/protected")
async def get_current_user(user=Depends(verify_token), db: AsyncSession = Depends(get_db)):
    user_db = await db.execute(select(User).where(User.id == user["sub"]))
    user_db = user_db.scalar()
    if not user_db:
        user_db = User(id=user["sub"], username=user["preferred_username"])
        db.add(user_db)
    return user