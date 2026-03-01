import secrets
from datetime import datetime
from src.models.user import db


class Subscriber(db.Model):
    __tablename__ = 'newsletter_subscribers'

    id              = db.Column(db.Integer, primary_key=True)
    email           = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name            = db.Column(db.String(100), nullable=True)
    plex_username   = db.Column(db.String(100), nullable=True, index=True)

    # Confirmation / unsubscribe
    confirmed       = db.Column(db.Boolean, default=False, nullable=False)
    confirm_token   = db.Column(db.String(64), unique=True, nullable=True)
    unsub_token     = db.Column(db.String(64), unique=True, nullable=False)

    # Notification preferences
    notify_requests = db.Column(db.Boolean, default=True)   # Overseerr request fulfilled
    notify_weekly   = db.Column(db.Boolean, default=True)   # Weekly digest

    # Timestamps
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at    = db.Column(db.DateTime, nullable=True)
    last_emailed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Subscriber {self.email}>'

    @classmethod
    def new(cls, email, name=None, plex_username=None,
            notify_requests=True, notify_weekly=True):
        return cls(
            email=email.lower().strip(),
            name=name or None,
            plex_username=plex_username or None,
            confirmed=False,
            confirm_token=secrets.token_urlsafe(32),
            unsub_token=secrets.token_urlsafe(32),
            notify_requests=notify_requests,
            notify_weekly=notify_weekly,
        )
