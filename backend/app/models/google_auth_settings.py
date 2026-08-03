from app.extensions import db
from app.crypto import get_fernet


class GoogleAuthSettings(db.Model):
    """Singleton row (always id=1) holding the platform's Google OAuth app config."""

    __tablename__ = "google_auth_settings"

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    client_id = db.Column(db.String(255), nullable=True)
    _client_secret_encrypted = db.Column("client_secret_encrypted", db.Text, nullable=True)

    @property
    def client_secret(self) -> str:
        if not self._client_secret_encrypted:
            return ""
        return get_fernet().decrypt(self._client_secret_encrypted.encode()).decode()

    @client_secret.setter
    def client_secret(self, plaintext: str):
        if plaintext:
            self._client_secret_encrypted = get_fernet().encrypt(plaintext.encode()).decode()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self._client_secret_encrypted)

    @classmethod
    def get_or_create(cls) -> "GoogleAuthSettings":
        settings = db.session.get(cls, 1)
        if not settings:
            settings = cls(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f"<GoogleAuthSettings enabled={self.enabled} configured={self.is_configured}>"
