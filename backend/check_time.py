from sqlalchemy import create_engine, text
from config import settings
from datetime import datetime, timezone

# Create engine
engine = create_engine(settings.DATABASE_URL)

# Check current time
current_time = datetime.now(timezone.utc)
print(f"当前UTC时间: {current_time}")
print(f"当前本地时间: {datetime.now()}")

# Query database
with engine.connect() as conn:
    result = conn.execute(text('SELECT id, timestamp FROM heart_rates ORDER BY id DESC LIMIT 5'))
    print('\n最近5条记录：')
    for row in result:
        id_val, timestamp_val = row
        print(f"ID: {id_val}, 数据库时间: {timestamp_val}")
        if timestamp_val:
            # Convert to datetime object
            if isinstance(timestamp_val, str):
                # Parse string to datetime
                db_dt = datetime.fromisoformat(timestamp_val)
            else:
                db_dt = timestamp_val
            print(f"  转换为UTC时间: {db_dt}")
            print(f"  转换为本地时间: {db_dt.astimezone()}")
