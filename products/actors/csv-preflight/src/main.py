import asyncio
from apify import Actor
from .core import check_text, read_csv

async def main():
    async with Actor:
        inp = await Actor.get_input() or {}
        delim = (inp.get("delimiter") or ",")[:1]
        req = inp.get("requiredColumns") or []
        sources = [("text", t) for t in ([inp["csvText"]] if inp.get("csvText") else [])]
        sources += [("url", u) for u in (inp.get("csvUrls") or [])]
        if not sources:
            await Actor.fail(status_message="Provide csvText or csvUrls")
            return
        for kind, value in sources:
            checker = read_csv if kind == 'url' else check_text
            item = await asyncio.to_thread(checker, value, delim, req)
            await Actor.push_data(item)
            if item['error'] is None:
                await Actor.charge(event_name='file-checked')
