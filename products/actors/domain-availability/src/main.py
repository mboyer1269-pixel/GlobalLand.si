import asyncio
from apify import Actor
from .core import check_domains, normalize_domains, load_bootstrap, is_billable


def _int(v, default, lo, hi):
    try:
        v = int(v if v is not None else default)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(v, hi))


async def main():
    async with Actor:
        inp = await Actor.get_input() or {}
        items = normalize_domains(inp.get('domains'))
        if not items:
            await Actor.fail(status_message='Provide at least one domain name in domains')
            return
        timeout = _int(inp.get('timeoutSecs'), 15, 1, 60)
        mapping = load_bootstrap()
        rows = await asyncio.to_thread(check_domains, items, mapping, timeout)
        for row in rows:
            await Actor.push_data(row)
            if is_billable(row):
                await Actor.charge(event_name='domain-checked')
