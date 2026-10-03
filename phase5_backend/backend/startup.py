# phase5_backend/backend/startup.py
"""
Initialization & Database Setup script.
"""
import asyncio
from pathlib import Path
from .database import db_manager
from .security.tls import generate_self_signed_cert

async def init_system():
    print("[STARTUP] Initializing database tables...")
    await db_manager.create_tables()
    print("✅ Database tables created.")
    
    cert_path = Path("./certs/server.crt")
    key_path = Path("./certs/server.key")
    if not cert_path.exists():
        print("[STARTUP] Generating self-signed TLS certificates for development...")
        generate_self_signed_cert(cert_path, key_path)
        print("✅ TLS certificates generated.")

if __name__ == "__main__":
    asyncio.run(init_system())
