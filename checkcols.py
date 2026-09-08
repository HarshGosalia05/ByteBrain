import asyncio,asyncpg,sys
sys.path.insert(0,'backend')
from db_env import db_config
cfg=db_config()
async def m():
    conn=await asyncpg.connect(host=cfg.host,port=cfg.port,database=cfg.name,user=cfg.user,password=cfg.password,ssl='require',statement_cache_size=0)
    r=await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='daily_attendance_07' ORDER BY ordinal_position")
    print([x['column_name'] for x in r])
    await conn.close()
asyncio.run(m())
