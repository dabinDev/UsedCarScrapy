"""快速测试数据库连接和建表"""
import asyncio
import aiomysql
from db_config import DB_CONFIG


async def test():
    # 1. 连接（不指定数据库）
    print("1. 测试连接...")
    conn = await aiomysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset=DB_CONFIG["charset"],
    )
    cur = await conn.cursor()

    # 2. 使用已有数据库
    db_name = DB_CONFIG["database"]
    await cur.execute(f"USE `{db_name}`")
    print(f"2. 使用数据库: {db_name}")

    # 3. 执行建表SQL
    print("3. 执行建表SQL...")
    with open("schema.sql", "r", encoding="utf-8") as f:
        sql_content = f.read()

    # 按分号拆分并逐条执行
    statements = sql_content.split(";")
    table_count = 0
    for stmt in statements:
        # 去掉注释行，保留实际SQL
        lines = [l for l in stmt.strip().splitlines() if l.strip() and not l.strip().startswith("--")]
        clean = "\n".join(lines).strip()
        if not clean:
            continue
        if clean.upper().startswith("CREATE DATABASE") or clean.upper().startswith("USE "):
            continue
        try:
            await cur.execute(clean)
            if "CREATE TABLE" in clean.upper():
                table_count += 1
        except Exception as e:
            print(f"   ⚠️ SQL执行警告: {e}")

    print(f"   ✅ 建表完成，共 {table_count} 张表")

    # 5. 验证表
    await cur.execute("SHOW TABLES")
    tables = await cur.fetchall()
    print(f"4. 当前表: {[t[0] for t in tables]}")

    await cur.close()
    conn.close()
    print("\n✅ 数据库准备就绪!")


if __name__ == "__main__":
    asyncio.run(test())
