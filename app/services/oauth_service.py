"""OAuth service (Google + GitHub) via Authlib.

Flow:
1. `authorize(provider)` returns an authorization URL + state.
2. Frontend redirects the browser, Google/GitHub redirects to our callback.
3. `handle_callback(provider, code, state)` exchanges the code, fetches profile,
   links or creates the local user, issues our own tokens.
"""

import secrets
from datetime import datetime, timezone

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.core.redis import redis_cache
from app.core.security import encrypt_secret
from app.models.enums import OAuthProviderEnum
from app.models.user import OAuthAccount
from app.repositories.user import OAuthAccountRepository, UserRepository
from app.schemas.auth import AuthResult
from app.services.auth_service import AuthService


class OAuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.oauth = OAuthAccountRepository(db)
        self.auth = AuthService(db)

    async def authorize(self, provider: OAuthProviderEnum) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        await redis_cache.setex(f"oauth_state:{state}", 600, provider.value)
        if provider == OAuthProviderEnum.GOOGLE:
            client = AsyncOAuth2Client(
                client_id=settings.GOOGLE_CLIENT_ID,
                scope="openid email profile",
                redirect_uri=settings.GOOGLE_REDIRECT_URI,
            )
            url, _ = client.create_authorization_url(
                "https://accounts.google.com/o/oauth2/v2/auth",
                state=state,
                access_type="offline",
                prompt="consent",
            )
            return url, state
        if provider == OAuthProviderEnum.GITHUB:
            client = AsyncOAuth2Client(
                client_id=settings.GITHUB_CLIENT_ID,
                scope="read:user user:email",
                redirect_uri=settings.GITHUB_REDIRECT_URI,
            )
            url, _ = client.create_authorization_url(
                "https://github.com/login/oauth/authorize", state=state
            )
            return url, state
        raise BadRequestError(f"Unsupported provider: {provider}")

    async def _fetch_google_profile(self, code: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code >= 400:
                raise ExternalServiceError("Google OAuth token exchange failed.")
            tokens = token_resp.json()
            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
        return {"tokens": tokens, "profile": profile}

    async def _fetch_github_profile(self, code: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "code": code,
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code >= 400:
                raise ExternalServiceError("GitHub OAuth token exchange failed.")
            tokens = token_resp.json()
            profile_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
            if not profile.get("email"):
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )
                primaries = [e["email"] for e in emails_resp.json() if e.get("primary")]
                if primaries:
                    profile["email"] = primaries[0]
        return {"tokens": tokens, "profile": profile}

    async def handle_callback(
        self,
        provider: OAuthProviderEnum,
        code: str,
        state: str,
        request: Request | None,
    ) -> AuthResult:
        cached = await redis_cache.get(f"oauth_state:{state}")
        if not cached or cached != provider.value:
            raise BadRequestError("Invalid OAuth state.", code="oauth_state_invalid")
        await redis_cache.delete(f"oauth_state:{state}")

        if provider == OAuthProviderEnum.GOOGLE:
            data = await self._fetch_google_profile(code)
            profile = data["profile"]
            provider_account_id = profile["sub"]
            email = profile["email"]
            display_name = profile.get("name") or email.split("@")[0]
            avatar_url = profile.get("picture")
        else:
            data = await self._fetch_github_profile(code)
            profile = data["profile"]
            provider_account_id = str(profile["id"])
            email = profile.get("email") or f"{profile['login']}@users.noreply.github.com"
            display_name = profile.get("name") or profile["login"]
            avatar_url = profile.get("avatar_url")

        oauth = await self.oauth.get(provider, provider_account_id)
        user = None
        if oauth:
            user = await self.users.get(oauth.user_id)
        if user is None:
            user = await self.users.get_by_email(email)
        if user is None:
            base_username = (profile.get("login") or email.split("@")[0]).replace(" ", "-")
            username = base_username
            suffix = 0
            while await self.users.get_by_username(username):
                suffix += 1
                username = f"{base_username}-{suffix}"
            user = await self.users.create_user(
                email=email,
                username=username[:39],
                display_name=display_name,
                hashed_password=None,
                email_verified=True,
            )
            user.avatar_url = avatar_url
            await self.db.flush()

        if oauth is None:
            oauth = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_account_id=provider_account_id,
                access_token_encrypted=encrypt_secret(data["tokens"].get("access_token", "")),
                refresh_token_encrypted=(
                    encrypt_secret(data["tokens"]["refresh_token"])
                    if data["tokens"].get("refresh_token")
                    else None
                ),
                profile_data=profile,
                scopes=data["tokens"].get("scope", "").split(" ") if data["tokens"].get("scope") else [],
            )
            self.db.add(oauth)
        else:
            oauth.access_token_encrypted = encrypt_secret(data["tokens"].get("access_token", ""))
            if data["tokens"].get("refresh_token"):
                oauth.refresh_token_encrypted = encrypt_secret(data["tokens"]["refresh_token"])
            oauth.profile_data = profile

        await self.users.touch_login(
            user, request.client.host if request and request.client else None
        )
        tokens = await self.auth._issue_tokens(user, remember_me=True, request=request)
        return AuthResult(user=self.auth._user_out(user), tokens=tokens)
