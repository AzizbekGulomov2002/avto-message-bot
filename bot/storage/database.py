"""Database connection and setup."""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from typing import Optional
from bot.config import Config


class Database:
    """Database connection manager."""
    
    def __init__(self, config: Config):
        """Initialize database connection pool."""
        self.config = config
        self.pool: Optional[ThreadedConnectionPool] = None
    
    def connect(self):
        """Create connection pool."""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD,
                database=self.config.POSTGRES_DB,
            )
            # Test connection
            conn = self.pool.getconn()
            conn.close()
            self.pool.putconn(conn)
        except Exception as e:
            raise Exception(f"Failed to connect to database: {e}")
    
    def get_connection(self):
        """Get a connection from the pool."""
        if not self.pool:
            self.connect()
        return self.pool.getconn()
    
    def put_connection(self, conn):
        """Return a connection to the pool."""
        if self.pool:
            self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
        """Execute a query and return results."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch_one:
                    result = cur.fetchone()
                    conn.commit()  # Commit after fetch_one to ensure data is saved
                    return result
                elif fetch_all:
                    result = cur.fetchall()
                    conn.commit()  # Commit after fetch_all
                    return result
                else:
                    conn.commit()
                    return cur.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.put_connection(conn)
    
    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()

