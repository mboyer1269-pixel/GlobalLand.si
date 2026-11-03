"""Exercise both actor HTTP paths without contacting any external address."""
import importlib.util
import io
import pathlib
import socket
import ssl
import sys
import unittest
from unittest.mock import patch

ACTORS = pathlib.Path(__file__).resolve().parents[1] / 'products/actors'
FEED = b'<rss><channel><title>Feed</title><item><title>One</title></item></channel></rss>'


def load_core(actor):
    name = actor.replace('-', '_') + '_network_test'
    spec = importlib.util.spec_from_file_location(name, ACTORS / actor / 'src/__init__.py',
                                                submodule_search_locations=[str(ACTORS / actor / 'src')])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(name + '.core')


CORES = {actor: load_core(actor) for actor in ('rss-reader', 'link-checker')}


class Wire:
    """Only DNS/socket I/O is faked; URL validation and HTTP parsing run for real."""
    def __init__(self, responses=None):
        self.responses = list(responses or [(200, {}, FEED)])
        self.connected = []
        self.sent = []
        self.closed = 0

    def socket(self, *_args, **_kwargs):
        wire = self
        class Sock:
            def settimeout(self, value): pass
            def setsockopt(self, *args): pass
            def connect(self, address): wire.connected.append(address)
            def sendall(self, value): wire.sent.append(value)
            def close(self): wire.closed += 1
            def makefile(self, *args, **kwargs):
                status, headers, body = wire.responses.pop(0)
                headers = dict(headers, **{'Content-Length': str(len(body))})
                head = 'HTTP/1.1 %d Test\r\n%s\r\n\r\n' % (status, '\r\n'.join(k + ': ' + v for k, v in headers.items()))
                return io.BytesIO(head.encode() + body)
        return Sock()


def addresses(*ips):
    return [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, '', (ip, 80, 0, 0) if ':' in ip else (ip, 80)) for ip in ips]


class ActorNetworkTests(unittest.TestCase):
    def result(self, actor, url):
        core = CORES[actor]
        if actor == 'rss-reader':
            row = core.read_feed(url)[0]
            return row['error_code']
        return core.check_url(url)['error_code']

    def test_private_mixed_metadata_and_multicast_destinations_are_blocked(self):
        for actor in CORES:
            for ips in [('127.0.0.1',), ('10.0.0.1',), ('169.254.169.254',), ('::1',),
                        ('fc00::1',), ('::ffff:127.0.0.1',), ('224.0.0.1',), ('8.8.8.8', '10.0.0.1')]:
                with self.subTest(actor=actor, ips=ips):
                    wire = Wire()
                    with patch.dict('os.environ', {'no_proxy': '*', 'NO_PROXY': '*'}), \
                         patch('socket.getaddrinfo', return_value=addresses(*ips)), patch('socket.socket', wire.socket):
                        self.assertEqual(self.result(actor, 'http://feed.example/rss'), 'blocked_address')
                    self.assertEqual(wire.connected, [])

    def test_connection_uses_the_validated_address_without_second_dns_lookup(self):
        for actor in CORES:
            with self.subTest(actor=actor):
                wire = Wire()
                with patch.dict('os.environ', {'no_proxy': '*', 'NO_PROXY': '*'}), \
                     patch('socket.getaddrinfo', side_effect=[addresses('8.8.8.8'), addresses('127.0.0.1')]) as dns, \
                     patch('socket.socket', wire.socket):
                    self.assertIsNone(self.result(actor, 'http://feed.example/rss?x=1'))
                self.assertEqual(wire.connected, [('8.8.8.8', 80)])
                self.assertEqual(dns.call_count, 1)
                self.assertIn(b'Host: feed.example\r\n', b''.join(wire.sent))
                self.assertGreater(wire.closed, 0)

    def test_redirect_revalidates_destination_and_does_not_connect_to_private_host(self):
        for actor in CORES:
            with self.subTest(actor=actor):
                wire = Wire([(302, {'Location': 'http://internal.example/rss'}, b''), (200, {}, FEED)])
                def resolve(host, *args, **kwargs):
                    return addresses('127.0.0.1' if host == 'internal.example' else '8.8.8.8')
                with patch.dict('os.environ', {'no_proxy': '*', 'NO_PROXY': '*'}), \
                     patch('socket.getaddrinfo', side_effect=resolve), patch('socket.socket', wire.socket):
                    self.assertEqual(self.result(actor, 'http://feed.example/rss'), 'blocked_address')
                self.assertEqual(wire.connected, [('8.8.8.8', 80)])

    def test_https_preserves_certificate_hostname_and_tls_verification(self):
        for actor in CORES:
            with self.subTest(actor=actor):
                wire = Wire()
                context = ssl.create_default_context()
                with patch.dict('os.environ', {'no_proxy': '*', 'NO_PROXY': '*'}), \
                     patch('socket.getaddrinfo', return_value=addresses('8.8.8.8')), patch('socket.socket', wire.socket), \
                     patch('ssl.create_default_context', return_value=context), \
                     patch.object(context, 'wrap_socket', side_effect=lambda sock, **kw: sock) as tls:
                    self.assertIsNone(self.result(actor, 'https://feed.example/rss'))
                self.assertTrue(context.check_hostname)
                self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                self.assertEqual(tls.call_args.kwargs['server_hostname'], 'feed.example')

    def test_unreachable_first_address_falls_back_only_to_validated_answers(self):
        for actor in CORES:
            with self.subTest(actor=actor):
                wire = Wire()
                def create(*args, **kwargs):
                    sock = wire.socket()
                    connect = sock.connect
                    def attempt(address):
                        connect(address)
                        if address[0] == '2606:4700:4700::1111':
                            raise OSError('IPv6 unavailable')
                    sock.connect = attempt
                    return sock
                with patch.dict('os.environ', {'no_proxy': '*', 'NO_PROXY': '*'}), \
                     patch('socket.getaddrinfo', return_value=addresses('2606:4700:4700::1111', '8.8.8.8')) as dns, \
                     patch('socket.socket', create):
                    self.assertIsNone(self.result(actor, 'http://feed.example/rss'))
                self.assertEqual([a[0] for a in wire.connected], ['2606:4700:4700::1111', '8.8.8.8'])
                self.assertEqual(dns.call_count, 1)


if __name__ == '__main__':
    unittest.main()
