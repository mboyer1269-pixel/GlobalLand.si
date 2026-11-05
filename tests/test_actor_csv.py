"""CSV transport limits run on synthetic sockets, never on private resources."""
import unittest
from unittest.mock import patch

from test_actor_network import CORES, Wire, addresses

core = CORES['csv-preflight']


class CSVTransportTests(unittest.TestCase):
    def test_bad_csv_options_produce_a_file_error_instead_of_aborting_the_actor(self):
        for options in [('', []), (',', [42])]:
            with self.subTest(options=options):
                row = core.check_text('A,B\n1,2', *options)
                self.assertEqual(row['error_code'], 'invalid_input')
                self.assertEqual(row['headers'], [])

    def test_pasted_multibyte_text_is_limited_by_utf8_bytes(self):
        row = core.check_text('\u00e9' * (5 * 1024 * 1024 + 1))
        self.assertEqual(row['error_code'], 'too_large')
        self.assertEqual(row['headers'], [])

    def test_download_stops_at_limit_plus_one_instead_of_buffering_entire_body(self):
        reads = []
        import io
        real_bytes_io = io.BytesIO
        class Body(real_bytes_io):
            def read(self, size=-1):
                reads.append(size)
                if size < 0:
                    raise AssertionError('unbounded response read')
                return super().read(size)
        wire = Wire([(200, {}, b'A\n' + b'x' * (10 * 1024 * 1024 + 100))])
        with patch('socket.getaddrinfo', return_value=addresses('8.8.8.8')), \
             patch('socket.socket', wire.socket), patch('test_actor_network.io.BytesIO', Body):
            row = core.read_csv('http://fixture.example/large.csv')
        self.assertEqual(row['error_code'], 'too_large')
        self.assertEqual(reads, [10 * 1024 * 1024 + 1])
        self.assertGreater(wire.closed, 0)

    def test_redirect_loop_has_a_finite_request_limit(self):
        wire = Wire([(302, {'Location': '/next-%d.csv' % n}, b'') for n in range(8)])
        with patch('socket.getaddrinfo', return_value=addresses('8.8.8.8')), patch('socket.socket', wire.socket):
            row = core.read_csv('http://fixture.example/start.csv')
        self.assertEqual(row['error_code'], 'too_many_redirects')
        self.assertLessEqual(len(wire.connected), 6)

    def test_invalid_encoding_and_http_error_do_not_return_csv_content(self):
        for response, expected in [((200, {}, b'\xff'), 'invalid_encoding'), ((403, {}, b'SECRET'), 'http_error')]:
            with self.subTest(expected=expected):
                wire = Wire([response])
                with patch('socket.getaddrinfo', return_value=addresses('8.8.8.8')), patch('socket.socket', wire.socket):
                    row = core.read_csv('http://fixture.example/file.csv')
                self.assertEqual(row['error_code'], expected)
                self.assertEqual(row['headers'], [])


if __name__ == '__main__':
    unittest.main()
