"""
补录脚本：从 details.json 读取已采集但数据库缺失的记录，重新入库
运行方式: python backfill_db.py
"""

import asyncio
import json
import os
from db_manager import DBManager


async def main():
    output_dir = "client_output"
    details_path = os.path.join(output_dir, "details.json")

    if not os.path.exists(details_path):
        print("❌ details.json 不存在")
        return

    with open(details_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    details = data.get("data", [])
    if not details:
        print("❌ 无详情数据")
        return

    print(f"📋 共 {len(details)} 条详情数据，开始补录...")

    db = DBManager()
    await db.connect()

    success = 0
    fail = 0
    try:
        for i, d in enumerate(details, 1):
            sku_id = d.get("sku_id")
            if not sku_id:
                continue
            try:
                await db.upsert_detail(d)
                success += 1
            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"   ⚠️ sku_id={sku_id}: {e}")
                elif fail == 6:
                    print("   ... 后续错误省略")

            if i % 100 == 0:
                print(f"   进度: {i}/{len(details)} (成功={success}, 失败={fail})")

    finally:
        await db.close()

    print(f"\n✅ 补录完成: 成功={success}, 失败={fail}, 总计={len(details)}")


if __name__ == "__main__":
    asyncio.run(main())
