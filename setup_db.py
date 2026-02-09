"""
一键创建数据库 + 建表
解决 used-car 数据库名含连字符的问题
"""
import pymysql
from db_config import DB_CONFIG


def main():
    db_name = DB_CONFIG["database"]

    # 1. 不指定数据库连接，创建数据库
    print("1. 连接MySQL服务器...")
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
    )
    cur = conn.cursor()

    print(f"2. 创建数据库 `{db_name}`...")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    conn.commit()

    # 2. 切换到目标数据库
    cur.execute(f"USE `{db_name}`")
    print(f"   ✅ 数据库 `{db_name}` 就绪")

    # 3. 执行建表SQL
    print("3. 执行建表SQL...")
    with open("schema.sql", "r", encoding="utf-8") as f:
        sql_content = f.read()

    statements = sql_content.split(";")
    table_count = 0
    for stmt in statements:
        lines = [l for l in stmt.strip().splitlines() if l.strip() and not l.strip().startswith("--")]
        clean = "\n".join(lines).strip()
        if not clean:
            continue
        if clean.upper().startswith("USE "):
            continue
        try:
            cur.execute(clean)
            if "CREATE TABLE" in clean.upper():
                table_count += 1
        except Exception as e:
            print(f"   ⚠️ SQL执行警告: {e}")

    conn.commit()
    print(f"   ✅ 建表完成，共 {table_count} 张表")

    # 4. 验证
    cur.execute("SHOW TABLES")
    tables = await_result = cur.fetchall()
    table_names = [t[0] for t in tables]
    print(f"4. 当前表 ({len(table_names)}): {table_names}")

    cur.close()
    conn.close()
    print("\n✅ 数据库初始化完成!")


if __name__ == "__main__":
    main()
