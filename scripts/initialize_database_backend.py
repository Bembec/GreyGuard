"""Initialize every GreyGuard table through the configured database backend."""
import asyncio
from backend.app.api import app,lifespan
from backend.app.db_compat import backend_name
async def initialize():
 async with lifespan(app):print(f"GreyGuard {backend_name()} schema initialization passed.")
if __name__=="__main__":asyncio.run(initialize())
