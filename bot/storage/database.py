"""Database connection and setup."""
import logging
import threading

import psycopg2
from psycopg2 import InterfaceError, OperationalError
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from typing import Optional
from bot.config import Config

logger = logging.getLogger(__name__)

# Eng yomon holatda ham hech qachon cheksiz osilmaslik uchun barcha
# tarmoq operatsiyalariga qattiq vaqt chegaralari qo'yiladi.
CONNECT_TIMEOUT_SECONDS = 10
STATEMENT_TIMEOUT_MS = 15000  # bitta SQL so'rov maksimal 15s
# TCP keepalive: jimgina o'lib qolgan ulanishni OS o'zi aniqlab uzadi.
KEEPALIVES_IDLE_SECONDS = 30
KEEPALIVES_INTERVAL_SECONDS = 10
KEEPALIVES_COUNT = 3


class Database:
    """Database connection manager."""

    def __init__(self, config: Config):
        """Initialize database connection pool."""
        self.config = config
        self.pool: Optional[ThreadedConnectionPool] = None
        self._lock = threading.Lock()

    def _connect_kwargs(self) -> dict:
        """Connection parametrlari: timeout + keepalive + statement_timeout."""
        return {
            "host": self.config.POSTGRES_HOST,
            "port": self.config.POSTGRES_PORT,
            "user": self.config.POSTGRES_USER,
            "password": self.config.POSTGRES_PASSWORD,
            "database": self.config.POSTGRES_DB,
            "sslmode": self.config.POSTGRES_SSLMODE,
            # Yangi ulanish ochishda ham cheksiz kutmaslik uchun.
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            # O'lik (half-open) TCP ulanishni OS darajasida aniqlab uzish.
            "keepalives": 1,
            "keepalives_idle": KEEPALIVES_IDLE_SECONDS,
            "keepalives_interval": KEEPALIVES_INTERVAL_SECONDS,
            "keepalives_count": KEEPALIVES_COUNT,
            # Server tomonda har bir so'rovga qattiq chegara: osilib qolgan
            # so'rov 15s dan keyin xato bilan tugaydi, loopni bloklamaydi.
            "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
        }

    def connect(self):
        """Create connection pool."""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                **self._connect_kwargs(),
            )
            # Test connection
            conn = self.pool.getconn()
            self.pool.putconn(conn)
        except Exception as e:
            raise Exception(f"Failed to connect to database: {e}")

    def get_connection(self):
        """Get a connection from the pool."""
        if not self.pool:
            self.connect()
        return self.pool.getconn()

    def put_connection(self, conn, close: bool = False):
        """Return a connection to the pool (or discard a broken one)."""
        if self.pool:
            self.pool.putconn(conn, close=close)

    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
        """Execute a query and return results.

        O'lik ulanish aniqlansa, u pool'ga qaytarilmaydi (close=True) — shunday
        qilib keyingi so'rovlar yangi, tirik ulanishdan foydalanadi.
        """
        conn = self.get_connection()
        broken = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch_one:
                    result = cur.fetchone()
                    conn.commit()
                    return result
                elif fetch_all:
                    result = cur.fetchall()
                    conn.commit()
                    return result
                else:
                    conn.commit()
                    return cur.rowcount
        except (OperationalError, InterfaceError) as e:
            # Ulanish uzilgan/o'lgan — uni pool'dan butunlay chiqarib tashlaymiz.
            broken = True
            logger.error(f"[DB] Connection error, discarding connection: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            try:
                self.put_connection(conn, close=broken)
            except Exception as e:
                logger.error(f"[DB] Failed to return connection to pool: {e}")

    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
