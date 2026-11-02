import httpx
from apify import Actor
from .core import check

MAX_BYTES = 10 * 1024 * 1024

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
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            for kind, value in sources:
                item = {"source": "pasted_text" if kind == "text" else value}
                try:
                    if kind == "url":
                        r = await client.get(value)
                        r.raise_for_status()
                        if len(r.content) > MAX_BYTES:
                            raise ValueError("file larger than 10 MiB")
                        text = r.content.decode("utf-8")
                    else:
                        text = value
                    item.update(check(text, delim, req))
                    item["error"] = None
                except Exception as exc:
                    item.update({"ok": False, "issues": [], "data_rows": 0, "columns": 0, "headers": [], "had_bom": False, "error": str(exc)[:300]})
                await Actor.push_data(item)
                if item["error"] is None:
                    await Actor.charge(event_name="file-checked")
