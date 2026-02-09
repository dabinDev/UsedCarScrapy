"""验证参数采集修复是否正确"""
import asyncio
import json
from dongchedi_api import DongchediAPI


async def main():
    api = DongchediAPI(headless=True)
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 测试详情采集（含参数页）
        sku_id = "21794373"  # 之前失败的一个
        print(f"采集详情: sku_id={sku_id}")
        detail = await api.fetch_car_detail(page, sku_id)

        if not detail:
            print("❌ 详情采集失败")
            await browser.close()
            return

        print(f"✅ 详情采集成功")
        print(f"  title: {detail.get('title')}")
        print(f"  sh_price: {detail.get('sh_price')}")
        print(f"  include_tax_price: {detail.get('include_tax_price')}")
        print(f"  detail_params_url: {detail.get('detail_params_url')}")

        dp = detail.get("detail_params")
        dpr = detail.get("detail_params_raw")
        print(f"  detail_params: {'None' if dp is None else f'{len(dp)} groups'}")
        print(f"  detail_params_raw: {'None' if dpr is None else f'keys={list(dpr.keys())}'}")

        if dp:
            for g in dp[:3]:
                print(f"\n  === {g['group']} ({len(g['params'])} params) ===")
                for param in g["params"][:5]:
                    print(f"    {param['name']}: {param['value']}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
