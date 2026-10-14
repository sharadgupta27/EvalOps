from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import Unauthorized
from app.repositories import Repo
from app.services.core import AuthService
from app.services.security import Principal

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="apiKeyAuth")


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_repo(session: SessionDep) -> Repo:
    return Repo(session)


RepoDep = Annotated[Repo, Depends(get_repo)]


async def get_principal(
    repo: RepoDep,
    settings: SettingsDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> Principal:
    auth = AuthService(repo, settings)
    if creds is not None:
        return await auth.principal_from_jwt(creds.credentials)
    if api_key:
        return await auth.principal_from_api_key(api_key)
    raise Unauthorized("missing credentials: send a Bearer token or X-API-Key")


async def get_api_key_principal(
    repo: RepoDep,
    settings: SettingsDep,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> Principal:
    if not api_key:
        raise Unauthorized("this endpoint requires an X-API-Key header")
    return await AuthService(repo, settings).principal_from_api_key(api_key)


PrincipalDep = Annotated[Principal, Depends(get_principal)]
ApiKeyPrincipalDep = Annotated[Principal, Depends(get_api_key_principal)]
