"""Test configuration.

Safe defaults so the unit tests run anywhere (CI, a fresh clone) without a `.env` file.
Tests that need a real database skip themselves when it is not reachable.
"""
import os

os.environ.setdefault("ODOO_DB_DSN", "postgresql://ai_readonly:unused@localhost:5432/demo")
os.environ.setdefault("VECTOR_DB_DSN", "postgresql://rag:unused@localhost:5432/rag")
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")
