from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(token: str):
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import TokenError
    from apps.accounts.models import User
    try:
        payload = AccessToken(token)
        return User.objects.get(pk=payload['user_id'])
    except (TokenError, User.DoesNotExist, Exception):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Reads ?token=<JWT> from the WebSocket URL and authenticates the user.
    Falls back to AnonymousUser if token is missing or invalid.
    """
    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope.get('query_string', b'').decode())
        tokens = qs.get('token', [])
        scope['user'] = await _user_from_token(tokens[0]) if tokens else AnonymousUser()
        return await super().__call__(scope, receive, send)
