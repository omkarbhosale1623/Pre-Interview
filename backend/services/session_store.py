"""
services/session_store.py — Storage abstraction. Delegates to SQLiteStore.
"""
from services.postgres_store import PostgresStore

store = PostgresStore()
