from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class CSLog(db.Model):
    __tablename__ = 'cs_logs'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sku = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    log_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text)
    location = db.Column(db.String(10), nullable=False)
    created_by = db.Column(db.String(50), nullable=False)
