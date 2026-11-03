"""Run a real Actor wrapper with local SDK input, datasets and test charging.

Only the remote feed/link socket is replaced; no Apify account or billable call.
Invoked separately per Actor so SDK singleton services cannot leak across runs.
"""
import argparse
import asyncio
import importlib
import json
import pathlib
import socket
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from apify import Actor, Configuration
from test_actor_network import Wire, addresses, FEED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actor', choices=['rss-reader', 'link-checker'], required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1] / 'products/actors' / args.actor
    sys.path.insert(0, str(root))
    wrapper = importlib.import_module('src.main')
    transport = importlib.import_module('src.public_http')
    good = 'http://fixture.example/rss'
    bad = 'file:///blocked'
    is_rss = args.actor == 'rss-reader'
    input_value = {'feedUrls': [good, good, bad], 'maxItems': 1} if is_rss else {'urls': [good, good, bad]}
    event = 'item-parsed' if is_rss else 'link-checked'
    wire = Wire([(200, {}, FEED)])
    socket_api = SimpleNamespace(AF_INET=socket.AF_INET, AF_INET6=socket.AF_INET6,
                                 SOCK_STREAM=socket.SOCK_STREAM, IPPROTO_TCP=socket.IPPROTO_TCP,
                                 getaddrinfo=lambda *a, **kw: addresses('8.8.8.8'), socket=wire.socket)
    with tempfile.TemporaryDirectory() as directory:
        storage = pathlib.Path(directory)
        inputs = storage / 'key_value_stores/default'
        inputs.mkdir(parents=True)
        (inputs / 'INPUT.json').write_text(json.dumps(input_value))
        wrapper.Actor = Actor(configuration=Configuration(storage_dir=directory, is_at_home=False,
                              test_pay_per_event=True, purge_on_start=False), exit_process=False)
        with patch.object(transport, 'socket', socket_api):
            asyncio.run(wrapper.main())
        def rows(dataset):
            return [json.loads(p.read_text()) for p in (storage / 'datasets' / dataset).glob('*.json')
                    if not p.name.startswith('__') and 'metadata' not in p.name]
        data = rows('default')
        # The SDK also logs its synthetic dataset-item event in local PPE mode.
        charges = [r for r in rows('charging-log') if r['event_name'] != 'apify-default-dataset-item']
        assert len(data) == 2, data
        assert sum(r.get('error_code') is None for r in data) == 1, data
        assert len(charges) == 1, charges
        assert charges[0]['event_name'] == event and charges[0]['charged_count'] == 1, charges
        assert len(wire.connected) == 1, wire.connected
        print('%s: real SDK input, 2 output rows, 1 test charge (%s), no real billing' % (args.actor, event))


if __name__ == '__main__':
    main()
