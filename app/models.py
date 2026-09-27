from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='viewer')  # viewer, analyst, admin
    provider = db.Column(db.String(30), default='local')
    provider_id = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DataSource(db.Model):
    __tablename__ = 'data_sources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    source_type = db.Column(db.String(50), default='csv_upload')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Dataset(db.Model):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    stored_path = db.Column(db.String(300), nullable=False)
    row_count = db.Column(db.Integer)
    column_count = db.Column(db.Integer)
    missing_values = db.Column(db.Integer)
    column_names = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_sources.id'), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)