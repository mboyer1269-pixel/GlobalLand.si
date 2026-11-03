import asyncio
from apify import Actor
from .core import read_feed

MAX_FEEDS = 100


async def main():
    async with Actor:
        inp = await Actor.get_input() or {}
        urls = [u.strip() for u in (inp.get("feedUrls") or []) if isinstance(u, str) and u.strip()]
        try:
            max_items = int(inp.get("maxItems") or 50)
        except (TypeError, ValueError):
            max_items = 50
        max_items = max(1, min(max_items, 1000))
        if not urls:
            await Actor.fail(status_message="Provide at least one public feed URL in feedUrls")
            return
        urls = list(dict.fromkeys(urls))[:MAX_FEEDS]
        for url in urls:
            rows = await asyncio.to_thread(read_feed, url, max_items)
            for row in rows:
                await Actor.push_data(row)
                if row["row_type"] == "item":
                    await Actor.charge(event_name="item-parsed")
