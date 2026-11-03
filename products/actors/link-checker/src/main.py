import asyncio
from apify import Actor
from .core import check_urls, normalize_urls, is_billable


def _int(v, default, lo, hi):
    try:
        v = int(v if v is not None else default)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(v, hi))


async def main():
    async with Actor:
        inp = await Actor.get_input() or {}
        urls = normalize_urls(inp.get("urls"))
        if not urls:
            await Actor.fail(status_message="Provide at least one public http(s) URL in urls")
            return
        timeout = _int(inp.get("timeoutSecs"), 15, 1, 60)
        max_redirects = _int(inp.get("maxRedirects"), 10, 0, 20)
        rows = await asyncio.to_thread(check_urls, urls, 8, 0.5, timeout=timeout, max_redirects=max_redirects)
        for row in rows:
            await Actor.push_data(row)
            if is_billable(row):
                await Actor.charge(event_name="link-checked")
