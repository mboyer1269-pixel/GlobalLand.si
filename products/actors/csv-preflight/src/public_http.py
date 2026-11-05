"""Public HTTP transport. Kept in each actor so its Apify bundle is standalone.

Validate every DNS answer and connect to the validated sockaddr directly. Never
let a client, proxy, or automatic redirect resolve the destination a second time.
Callers follow redirects explicitly and call request() again for every hop.
"""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urlunsplit


class PublicHTTPError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def resolve(url, allow_private=False):
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise PublicHTTPError('invalid_url', 'URL must not contain whitespace or control characters')
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https'):
            raise PublicHTTPError('invalid_scheme', 'only http(s) URLs are accepted')
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        if not host or '%' in host or parts.username is not None or parts.password is not None:
            raise ValueError('invalid host or credentials')
        host = host.encode('idna').decode('ascii')
    except (ValueError, UnicodeError):
        raise PublicHTTPError('invalid_url', 'invalid URL host, port or credentials') from None
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        raise PublicHTTPError('dns_error', 'host could not be resolved') from None
    if not answers:
        raise PublicHTTPError('dns_error', 'host has no addresses')
    for family, _, _, _, address in answers:
        try:
            ip = ipaddress.ip_address(address[0])
        except ValueError:
            raise PublicHTTPError('blocked_address', 'invalid destination address') from None
        if family not in (socket.AF_INET, socket.AF_INET6) or (not allow_private and (
                not ip.is_global or ip.is_multicast or ip.is_unspecified)):
            raise PublicHTTPError('blocked_address', 'host resolves to a non-public address')
    return parts, host, port, answers


def request(url, method, timeout, read_bytes=0, headers=None, allow_private=False):
    parts, host, port, answers = resolve(url, allow_private)
    # A numeric sockaddr, not socket.create_connection(host), prevents DNS rebinding.
    sock = None
    last_error = None
    for family, kind, proto, _, address in answers:
        try:
            sock = socket.socket(family, kind, proto)
            sock.settimeout(timeout)
            sock.connect(address)
            break
        except OSError as error:
            last_error = error
            if sock is not None:
                sock.close()
            sock = None
    if sock is None:
        raise last_error
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        if parts.scheme == 'https':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        conn.sock = sock
        authority = '[' + host + ']' if ':' in host else host
        if port != (443 if parts.scheme == 'https' else 80):
            authority += ':' + str(port)
        request_headers = dict(headers or {})
        request_headers.update({'Host': authority, 'Accept-Encoding': 'identity', 'Connection': 'close'})
        target = urlunsplit(('', '', parts.path or '/', parts.query, ''))
        conn.request(method, target, headers=request_headers)
        response = conn.getresponse()
        try:
            # Redirects and HTTP errors need no response body; do not drain them.
            body = response.read(read_bytes) if method != 'HEAD' and 200 <= response.status < 300 and read_bytes else b''
            return response.status, response.getheader('Location'), body
        finally:
            response.close()
    finally:
        conn.close()
        sock.close()
