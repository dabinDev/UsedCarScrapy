"""
测试参数页面数据提取
验证 /auto/params-carIds-{car_id} 页面的 __NEXT_DATA__ 结构
"""
import asyncio
import json
import re
from playwright.async_api import async_playwright


async def main():
    car_id = "8626"  # 蒙迪欧 2013款
    url = f"https://www.dongchedi.com/auto/params-carIds-{car_id}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 方法1: page.request.get (当前代码用的方式)
        print("=" * 60)
        print("方法1: page.request.get")
        try:
            resp = await page.request.get(url)
            print(f"  Status: {resp.status}")
            html = await resp.text()
            print(f"  HTML length: {len(html)}")
            match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html)
            if match:
                data = json.loads(match.group(1))
                props = data.get("props", {}).get("pageProps", {})
                print(f"  pageProps keys: {list(props.keys())}")
                # 查找参数相关的key
                for k, v in props.items():
                    if isinstance(v, list):
                        print(f"    {k}: list[{len(v)}]")
                        if v and isinstance(v[0], dict):
                            print(f"      first item keys: {list(v[0].keys())[:5]}")
                    elif isinstance(v, dict):
                        print(f"    {k}: dict keys={list(v.keys())[:5]}")
                    else:
                        print(f"    {k}: {type(v).__name__} = {str(v)[:80]}")
            else:
                print("  ❌ __NEXT_DATA__ not found")
                # 看看HTML里有什么
                print(f"  HTML preview: {html[:500]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        # 方法2: page.goto (浏览器渲染)
        print("\n" + "=" * 60)
        print("方法2: page.goto (浏览器渲染)")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            html = await page.content()
            print(f"  HTML length: {len(html)}")
            match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html)
            if match:
                data = json.loads(match.group(1))
                props = data.get("props", {}).get("pageProps", {})
                print(f"  pageProps keys: {list(props.keys())}")
                for k, v in props.items():
                    if isinstance(v, list):
                        print(f"    {k}: list[{len(v)}]")
                        if v and isinstance(v[0], dict):
                            print(f"      first item keys: {list(v[0].keys())[:5]}")
                            if "list" in v[0]:
                                first_list = v[0]["list"]
                                if isinstance(first_list, list) and first_list:
                                    print(f"      first group list[0] keys: {list(first_list[0].keys())[:5]}")
                    elif isinstance(v, dict):
                        print(f"    {k}: dict keys={list(v.keys())[:5]}")
                    else:
                        print(f"    {k}: {type(v).__name__} = {str(v)[:80]}")

                # 保存完整数据供分析
                with open("test_params_output.json", "w", encoding="utf-8") as f:
                    json.dump(props, f, ensure_ascii=False, indent=2)
                print("\n  ✅ 完整数据已保存到 test_params_output.json")
            else:
                print("  ❌ __NEXT_DATA__ not found")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
