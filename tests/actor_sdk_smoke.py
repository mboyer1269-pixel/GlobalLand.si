"""Run a real Actor wrapper with local SDK input, datasets and test charging.

Only remote sockets and the domain bootstrap endpoint are replaced; no Apify
account or billable call. RDAP and CSV responses are synthetic local fixtures.
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
from contextlib import ExitStack
from unittest.mock import patch

from apify import Actor, Configuration
from test_actor_network import Wire, addresses, fixture_body, ACTOR_NAMES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actor', choices=ACTOR_NAMES, required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1] / 'products/actors' / args.actor
    sys.path.insert(0, str(root))
    wrapper = importlib.import_module('src.main')
    transport = importlib.import_module('src.public_http')
    good = 'http://fixture.example/rss'
    bad = 'file:///blocked'
    domain = args.actor == 'domain-availability'
    csv = args.actor == 'csv-preflight'
    input_value, event = {
        'rss-reader': ({'feedUrls': [good, good, bad], 'maxItems': 1}, 'item-parsed'),
        'link-checker': ({'urls': [good, good, bad]}, 'link-checked'),
        'domain-availability': ({'domains': ['example.com', 'EXAMPLE.COM', 'free.com', 'limited.com', 'bad domain']}, 'domain-checked'),
        'csv-preflight': ({'csvText': 'x' * (10 * 1024 * 1024 + 1),
                           'csvUrls': [good, bad, 'http://fixture.example/redirect', 'http://fixture.example/large']}, 'file-checked'),
    }[args.actor]
    responses = [(200, {}, fixture_body(args.actor))]
    if domain:
        responses += [(404, {}, b'{}'), (429, {}, b'{}')]
    if csv:
        responses += [(302, {'Location': 'http://internal.example/file.csv'}, b''),
                      (200, {}, b'x' * (10 * 1024 * 1024 + 1))]
    wire = Wire(responses)
    socket_api = SimpleNamespace(AF_INET=socket.AF_INET, AF_INET6=socket.AF_INET6,
                                 SOCK_STREAM=socket.SOCK_STREAM, IPPROTO_TCP=socket.IPPROTO_TCP,
                                 getaddrinfo=lambda host, *a, **kw: addresses('127.0.0.1' if host == 'internal.example' else '8.8.8.8'), socket=wire.socket)
    with tempfile.TemporaryDirectory() as directory:
        storage = pathlib.Path(directory)
        inputs = storage / 'key_value_stores/default'
        inputs.mkdir(parents=True)
        (inputs / 'INPUT.json').write_text(json.dumps(input_value))
        wrapper.Actor = Actor(configuration=Configuration(storage_dir=directory, is_at_home=False,
                              test_pay_per_event=True, purge_on_start=False), exit_process=False)
        with ExitStack() as patches:
            patches.enter_context(patch.object(transport, 'socket', socket_api))
            if domain:
                patches.enter_context(patch.object(wrapper, 'load_bootstrap', return_value={'com': 'http://fixture.example/'}))
            asyncio.run(wrapper.main())
        def rows(dataset):
            return [json.loads(p.read_text()) for p in sorted((storage / 'datasets' / dataset).glob('*.json'))
                    if not p.name.startswith('__') and 'metadata' not in p.name]
        data = rows('default')
        # The SDK also logs its synthetic dataset-item event in local PPE mode.
        charges = [r for r in rows('charging-log') if r['event_name'] != 'apify-default-dataset-item']
        assert len(data) == (4 if domain else 5 if csv else 2), data
        assert sum(r.get('error_code') is None for r in data) == (2 if domain else 1), data
        assert len(charges) == (2 if domain else 1), charges
        assert all(r['event_name'] == event and r['charged_count'] == 1 for r in charges), charges
        assert len(wire.connected) == (3 if domain or csv else 1), wire.connected
        if domain:
            assert [r['available'] for r in data] == [False, True, None, None], data
        if csv:
            assert data[1]['headers'] == ['A', 'B'] and data[1]['data_rows'] == 1, data
            assert [r['error_code'] for r in data] == ['too_large', None, 'invalid_scheme', 'blocked_address', 'too_large'], data
            assert all(ip == '8.8.8.8' for ip, _ in wire.connected), wire.connected
        print('%s: real SDK input, %d output rows, %d test charges (%s), no real billing' %
              (args.actor, len(data), len(charges), event))


if __name__ == '__main__':
    main()
