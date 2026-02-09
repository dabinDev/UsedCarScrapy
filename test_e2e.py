"""
端到端测试：采集1条详情 -> 验证入库（含参数+金额清洗）
"""
import asyncio
import json
from dongchedi_api import DongchediAPI
from db_manager import DBManager


async def main():
    api = DongchediAPI(headless=True)
    db = DBManager()
    await db.connect()

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        sku_id = "21794373"
        print(f"1. 采集详情: sku_id={sku_id}")
        detail = await api.fetch_car_detail(page, sku_id)
        await browser.close()

    if not detail:
        print("❌ 详情采集失败")
        await db.close()
        return

    print(f"   ✅ 采集成功: {detail.get('title')}")

    # 验证关键字段
    print("\n2. 验证关键字段:")
    checks = {
        "sh_price": detail.get("sh_price"),
        "official_price": detail.get("official_price"),
        "include_tax_price": detail.get("include_tax_price"),
        "detail_params": f"{len(detail.get('detail_params', []))} groups" if detail.get("detail_params") else "None",
        "params": f"{len(detail.get('params', {}))} items" if detail.get("params") else "None",
        "images": f"{len(detail.get('images', []))} images",
        "shop.shop_id": detail.get("shop", {}).get("shop_id"),
        "shop.shop_short_name": detail.get("shop", {}).get("shop_short_name"),
        "highlights": f"{len(detail.get('highlights', []))} items",
        "tags": detail.get("tags"),
    }
    for k, v in checks.items():
        print(f"   {k}: {v}")

    # 验证金额清洗
    print("\n3. 金额清洗验证:")
    from db_manager import _clean_price
    test_prices = ["18.61万", "24.39万", 11.48, None, "暂无报价", "22.21万", "8417.0元"]
    for tp in test_prices:
        print(f"   _clean_price({repr(tp)}) = {_clean_price(tp)}")

    # 入库测试
    print("\n4. 入库测试...")
    try:
        await db.upsert_detail(detail)
        print("   ✅ 入库成功!")
    except Exception as e:
        print(f"   ❌ 入库失败: {e}")
        await db.close()
        return

    # 验证数据库数据
    print("\n5. 验证数据库数据:")
    async with db._pool.acquire() as conn:
        async with conn.cursor() as cur:
            # car_detail
            await cur.execute("SELECT sku_id, title, sh_price, official_price, include_tax_price FROM car_detail WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            print(f"   car_detail: sku_id={row[0]}, title={row[1]}, sh={row[2]}, official={row[3]}, include_tax={row[4]}")

            # car_params
            await cur.execute("SELECT sku_id, register_city, displacement, transmission FROM car_params WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            if row:
                print(f"   car_params: city={row[1]}, displacement={row[2]}, transmission={row[3]}")
            else:
                print("   car_params: (empty)")

            # car_config
            await cur.execute("SELECT sku_id, LENGTH(detail_params) as dp_len FROM car_config WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            if row:
                print(f"   car_config: detail_params length={row[1]} bytes")
            else:
                print("   car_config: (empty)")

            # shop
            await cur.execute("SELECT shop_id, shop_name, shop_short_name, city FROM shop LIMIT 1")
            row = await cur.fetchone()
            if row:
                print(f"   shop: id={row[0]}, name={row[1]}, short={row[2]}, city={row[3]}")

            # car_image
            await cur.execute("SELECT COUNT(*) FROM car_image WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            print(f"   car_image: {row[0]} images")

            # car_highlight
            await cur.execute("SELECT sku_id FROM car_highlight WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            print(f"   car_highlight: {'exists' if row else 'empty'}")

            # car_report
            await cur.execute("SELECT has_report FROM car_report WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            print(f"   car_report: {'has_report=' + str(row[0]) if row else 'empty'}")

            # car_financial
            await cur.execute("SELECT sku_id FROM car_financial WHERE sku_id=%s", (sku_id,))
            row = await cur.fetchone()
            print(f"   car_financial: {'exists' if row else 'empty'}")

    await db.close()
    print("\n✅ 端到端测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
