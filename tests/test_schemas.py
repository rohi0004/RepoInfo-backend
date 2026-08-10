from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.auth import UserOut


def test_user_out_camel_alias():
    payload = UserOut(
        id=uuid4(),
        email="a@b.co",
        username="alice",
        display_name="Alice",
        avatar_url=None,
        bio=None,
        plan="free",
        email_verified=True,
        github_connected=False,
        google_connected=False,
        created_at=datetime.now(timezone.utc),
        two_factor_enabled=False,
    ).model_dump(by_alias=True)
    assert "displayName" in payload
    assert "emailVerified" in payload
    assert "githubConnected" in payload
