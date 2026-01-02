from sqlalchemy import create_engine, text
from config import settings
from datetime import datetime

# Create engine
engine = create_engine(settings.DATABASE_URL)

print("=== 数据库检查 ===")

# Check current time
print(f"当前时间: {datetime.now()}")

# Check database connection
print("\n=== 数据库连接测试 ===")
try:
    with engine.connect() as conn:
        # Check if heart_rates table exists
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='heart_rates'")).fetchone()
        if result:
            print("✓ heart_rates 表存在")
            
            # Count records
            count_result = conn.execute(text("SELECT COUNT(*) FROM heart_rates")).fetchone()
            count = count_result[0]
            print(f"✓ 心率记录数量: {count}")
            
            # Check recent records
            if count > 0:
                print("\n=== 最近5条记录 ===")
                records = conn.execute(text("SELECT id, heart_rate, timestamp FROM heart_rates ORDER BY id DESC LIMIT 5")).fetchall()
                for record in records:
                    id_val, hr, ts = record
                    print(f"ID: {id_val}, HR: {hr}, 时间: {ts}")
            else:
                print("\n⚠ 没有找到任何心率记录")
                
            # Check table structure
            print("\n=== 表结构 ===")
            structure = conn.execute(text("PRAGMA table_info(heart_rates)")).fetchall()
            for col in structure:
                print(f"列名: {col[1]}, 类型: {col[2]}, 是否为空: {col[3]}, 默认值: {col[4]}, 主键: {col[5]}")
        else:
            print("⚠ heart_rates 表不存在")
            # Create table if not exists
            print("正在创建表...")
            from app.models.heart_rate import Base
            Base.metadata.create_all(engine)
            print("✓ 表已创建")
except Exception as e:
    print(f"✗ 数据库操作失败: {e}")

print("\n=== 检查完成 ===")
