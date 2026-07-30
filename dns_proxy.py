#!/usr/bin/env python3

import argparse
import ipaddress
import select
import socket
import socketserver
import subprocess
import sys
import threading
import time

from atomic_io import atomic_write_text


DNS_SERVER = '1.1.1.1'
MAX_HEADER_BYTES = 16384
RESOLUTION_TTL = 300


class Resolver:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    def resolve(self, hostname):
        now = time.monotonic()
        with self.lock:
            cached = self.cache.get(hostname)
            if cached and cached[1] > now:
                return cached[0]

        result = subprocess.run(
            ['dig', '+short', '@{}'.format(DNS_SERVER), hostname, 'A'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                'DNS fallback failed for {}: {}'.format(hostname, result.stderr.strip())
            )

        addresses = []
        for line in result.stdout.splitlines():
            candidate = line.strip()
            try:
                if ipaddress.ip_address(candidate).version == 4:
                    addresses.append(candidate)
            except ValueError:
                continue
        if not addresses:
            raise RuntimeError('DNS fallback returned no IPv4 address for {}'.format(hostname))

        address = addresses[0]
        with self.lock:
            self.cache[hostname] = (address, now + RESOLUTION_TTL)
        return address


resolver = Resolver()


class ThreadingProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ConnectHandler(socketserver.BaseRequestHandler):
    def read_headers(self):
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = self.request.recv(4096)
            if not chunk:
                raise RuntimeError('client disconnected before sending proxy headers')
            data += chunk
            if len(data) > MAX_HEADER_BYTES:
                raise RuntimeError('proxy request headers are too large')
        return data

    def handle(self):
        remote = None
        try:
            headers = self.read_headers()
            request_line = headers.split(b'\r\n', 1)[0].decode('ascii', errors='strict')
            method, authority, _version = request_line.split(' ', 2)
            if method.upper() != 'CONNECT':
                self.request.sendall(b'HTTP/1.1 405 Method Not Allowed\r\n\r\n')
                return

            hostname, port_text = authority.rsplit(':', 1)
            port = int(port_text)
            if port != 443:
                raise RuntimeError('only HTTPS port 443 is allowed')
            if not hostname or any(
                character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-'
                for character in hostname
            ):
                raise RuntimeError('invalid proxy hostname')

            address = resolver.resolve(hostname)
            remote = socket.create_connection((address, port), timeout=20)
            self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self.request.settimeout(None)
            remote.settimeout(None)

            sockets = [self.request, remote]
            while True:
                readable, _writable, exceptional = select.select(sockets, [], sockets, 60)
                if exceptional or not readable:
                    return
                for source in readable:
                    target = remote if source is self.request else self.request
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    target.sendall(chunk)
        except Exception as error:
            print('DNS proxy connection failed: {}'.format(error), file=sys.stderr)
            try:
                self.request.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            except OSError:
                pass
        finally:
            if remote is not None:
                remote.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port-file', required=True)
    args = parser.parse_args()

    with ThreadingProxy(('127.0.0.1', 0), ConnectHandler) as server:
        port = server.server_address[1]
        atomic_write_text(args.port_file, '{}\n'.format(port), default_mode=0o600)
        print('DNS fallback proxy listening on 127.0.0.1:{}'.format(port), file=sys.stderr)
        server.serve_forever(poll_interval=0.5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
