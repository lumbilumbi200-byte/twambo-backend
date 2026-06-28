import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class FCMService:
    _app = None

    @classmethod
    def _get_app(cls):
        if cls._app is None:
            import firebase_admin
            from firebase_admin import credentials
            if not firebase_admin._apps:
                cred_path = settings.FIREBASE_CREDENTIALS_PATH
                if cred_path:
                    cred = credentials.Certificate(cred_path)
                else:
                    cred = credentials.ApplicationDefault()
                cls._app = firebase_admin.initialize_app(cred)
            else:
                cls._app = firebase_admin.get_app()
        return cls._app

    @classmethod
    def send(cls, token: str, title: str, body: str, data: dict = None) -> bool:
        try:
            from firebase_admin import messaging
            cls._get_app()
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
            )
            messaging.send(message)
            return True
        except Exception as exc:
            logger.warning('FCM send failed: %s', exc)
            return False

    @classmethod
    def send_multicast(cls, tokens: list, title: str, body: str, data: dict = None) -> int:
        if not tokens:
            return 0
        try:
            from firebase_admin import messaging
            cls._get_app()
            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                tokens=tokens,
            )
            response = messaging.send_each_for_multicast(message)
            return response.success_count
        except Exception as exc:
            logger.warning('FCM multicast failed: %s', exc)
            return 0
