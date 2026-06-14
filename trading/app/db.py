"""
SQLAlchemy models: User accounts and wallet transactions.
"""
from __future__ import annotations
from datetime import datetime
import os

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False, default="")
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    wallet_balance = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    transactions = db.relationship("WalletTransaction", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def display_name(self) -> str:
        return self.name or self.email.split("@")[0]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.display_name(),
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "wallet_balance": round(self.wallet_balance, 2),
            "created_at": self.created_at.isoformat(),
        }


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # deposit | adjustment | withdrawal
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="completed", nullable=False)
    stripe_session_id = db.Column(db.String(300))
    note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="transactions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "amount": round(self.amount, 2),
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }


def init_db(app) -> None:
    """Configure SQLite path, initialise SQLAlchemy, create tables, seed admin."""
    data_dir = os.path.expanduser("~/.codon_trading")
    os.makedirs(data_dir, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{data_dir}/app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(email="admin@codon.trade", name="Admin", is_admin=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
