#!/usr/bin/env python3
"""一次性脚本：删除远程数据库所有表，用新 schema 重建"""

import pymysql
from db_config import DB_CONFIG

def main():
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
    )
    cur = conn.cursor()

    # 1. 查出所有表
    cur.execute("SHOW TABLES")
    tables = [row[0] for row in cur.fetchall()]
    print(f"当前数据库有 {len(tables)} 张表: {tables}")

    if tables:
        # 2. 关闭外键检查，逐表 DROP
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in tables:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
            print(f"  ✅ DROP TABLE `{t}`")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("所有表已删除\n")

    # 3. 读取 schema.sql 并执行建表
    with open("schema.sql", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉注释/空行/USE 语句，按分号聚合完整 SQL
    statements = []
    buffer = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.upper().startswith("USE "):
            continue
        buffer.append(stripped)
        if stripped.endswith(";"):
            stmt = " ".join(buffer).rstrip(";")
            statements.append(stmt)
            buffer = []

    for i, stmt in enumerate(statements):
        try:
            cur.execute(stmt)
            # 提取表名用于打印
            if "CREATE TABLE" in stmt.upper():
                tname = stmt.split("`")[1] if "`" in stmt else f"statement-{i}"
                print(f"  ✅ CREATE TABLE `{tname}`")
        except Exception as e:
            print(f"  ❌ 执行失败: {e}")
            print(f"     SQL: {stmt[:100]}...")

    conn.commit()

    # 4. 验证
    cur.execute("SHOW TABLES")
    tables = [row[0] for row in cur.fetchall()]
    print(f"\n重建完成，当前 {len(tables)} 张表: {tables}")

    # 检查关键字段类型
    for tbl in ["car_detail", "car_overview", "brand", "series"]:
        if tbl in tables:
            cur.execute(f"SHOW COLUMNS FROM `{tbl}` WHERE Field IN ('sku_id','brand_id','series_id','source')")
            cols = cur.fetchall()
            for col in cols:
                print(f"  {tbl}.{col[0]}: {col[1]}")

    cur.close()
    conn.close()
    print("\n✅ 数据库重置完成!")


if __name__ == "__main__":
    main()
