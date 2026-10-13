"""Single outbound boundary. DNS is validated then pinned to the socket destination."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .models import digest, now

USER_AGENT = 'AviScope/0.1 (+https://builderr.ai/challenges/signalpost)'
RESTRICTED = ('linkedin.com', 'facebook.com', 'instagram.com', 'indeed.com', 'glassdoor.com', 'google.com', 'bing.com', 'youtube.com', 'x.com', 'twitter.com')


class PolicyError(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def safe_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url) or '\\' in url:
        raise PolicyError('Malformed URL')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise PolicyError('Only credential-free HTTP(S) URLs are allowed')
    if parsed.port not in (None, 80, 443):
        raise PolicyError('Nonstandard destination port')
    host = parsed.hostname.rstrip('.').encode('idna').decode('ascii').lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '%' in host:
        raise PolicyError('Internal hostname')
    for key in ('token=', 'api_key=', 'apikey=', 'password=', 'secret=', 'access_token='):
        if key in parsed.query.lower():
            raise PolicyError('Credential-bearing URL')
    return urlunsplit((parsed.scheme, host if ':' not in host else '[' + host + ']', parsed.path or '/', parsed.query, ''))


def public_addresses(host: str, port: int) -> list[str]:
    addresses = list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses:
        raise PolicyError('No DNS addresses')
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global or ip.is_multicast or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo)):
            raise PolicyError('Nonpublic or transition destination')
    return addresses


@dataclass
class Budget:
    max_requests: int = 2000
    max_seconds: float = 2600
    max_cost: float = 10
    max_bytes: int = 8_000_000_000
    started: float = field(default_factory=time.monotonic)
    requests: int = 0
    bytes: int = 0
    retries: int = 0
    redirects: int = 0
    cache_hits: int = 0
    cost: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def remaining_seconds(self):
        return max(0, self.max_seconds - (time.monotonic() - self.started))

    def reserve(self, worst_case_cost=0.0):
        with self.lock:
            if self.requests >= self.max_requests or self.remaining_seconds() <= 1 or self.bytes >= self.max_bytes or self.cost + worst_case_cost > self.max_cost:
                raise BudgetExceeded('Batch request, deadline, byte or cost limit reached')
            self.requests += 1
            self.cost += worst_case_cost

    def record_bytes(self, size):
        with self.lock:
            self.bytes += size
            if self.bytes > self.max_bytes:
                raise BudgetExceeded('Batch byte ceiling reached')

    def metrics(self):
        return {'requests': self.requests, 'bytes': self.bytes, 'retries': self.retries, 'redirects': self.redirects, 'cache_hits': self.cache_hits, 'third_party_cost_usd': self.cost, 'runtime_seconds': round(time.monotonic() - self.started, 3)}


def redact_personal(value):
    if isinstance(value, dict):
        return {k: redact_personal(v) for k, v in value.items() if k.lower() not in ('fodselsdato', 'fødselsdato', 'fodselsnummer', 'fødselsnummer', 'personnummer')}
    if isinstance(value, list):
        return [redact_personal(x) for x in value]
    return value


class Broker:
    def __init__(self, root: Path, budget: Budget, source_policy: dict | None = None, transport=None):
        self.root = Path(root)
        (self.root / 'evidence').mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.policy = source_policy or {'domains': {}}
        self.transport = transport or self._request
        self.lock = threading.RLock()
        self.host_next = {}
        self.failures = {}
        self.robots = {}
        self.cache = {}
        self.events = []

    def permitted(self, url, source_class):
        host = urlsplit(url).hostname
        if source_class == 'official_registry':
            if host != 'data.brreg.no':
                raise PolicyError('Official source must be data.brreg.no')
        else:
            if any(host == x or host.endswith('.' + x) for x in RESTRICTED):
                raise PolicyError('Restricted platform: licensed route not enabled')
            entry = self.policy.get('domains', {}).get(host, {})
            if entry and (entry.get('access_allowed') is False or entry.get('retention_allowed') is False):
                raise PolicyError('Source rights explicitly disabled for this domain')

    def _request(self, url, timeout, max_bytes):
        parsed = urlsplit(url)
        port = 443 if parsed.scheme == 'https' else 80
        addresses = public_addresses(parsed.hostname, port)
        # Connect to the already validated IP; do not resolve hostname a second time.
        sock = socket.create_connection((addresses[0], port), timeout=timeout)
        try:
            if parsed.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
            connection = http.client.HTTPConnection(parsed.hostname, port, timeout=timeout)
            connection.sock = sock
            connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={'User-Agent': USER_AGENT, 'Accept': 'application/json,text/html,application/pdf,text/plain;q=0.8', 'Accept-Encoding': 'identity', 'Connection': 'close'})
            response = connection.getresponse()
            chunks = []
            total = 0
            until = time.monotonic() + timeout
            while True:
                if time.monotonic() >= until or self.budget.remaining_seconds() <= 0:
                    raise TimeoutError('Response deadline reached')
                if response.isclosed():
                    break
                chunk = response.read(min(65536, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                self.budget.record_bytes(len(chunk))
                if total > max_bytes:
                    raise PolicyError('Response exceeds maximum size')
                chunks.append(chunk)
            return response.status, dict(response.getheaders()), b''.join(chunks)
        finally:
            sock.close()

    def _throttle(self, host, interval):
        with self.lock:
            current = time.monotonic()
            slot = max(current, self.host_next.get(host, 0))
            self.host_next[host] = slot + interval
        delay = slot - current
        if delay >= self.budget.remaining_seconds() - 1:
            raise BudgetExceeded('No time for host throttle')
        if delay > 0:
            time.sleep(delay)

    def fetch(self, url: str, source_class='official_registry', *, use_cache=True, check_robots=True) -> tuple[dict, bytes]:
        url = safe_url(url)
        self.permitted(url, source_class)
        if source_class != 'official_registry' and check_robots:
            self._robots_allowed(url)
        with self.lock:
            if use_cache and url in self.cache:
                self.budget.cache_hits += 1
                return self.cache[url]
        requested = url
        chain = []
        for redirect in range(5):
            url = safe_url(url)
            self.permitted(url, source_class)
            if source_class != 'official_registry' and check_robots and url != requested:
                self._robots_allowed(url)
            host = urlsplit(url).hostname
            if self.failures.get(host, 0) >= 12:
                raise PolicyError('Host circuit breaker open after repeated failures')
            for attempt in range(2):
                interval = 2.1 if '/aarsregnskap/kopi/' in url else .18 if source_class == 'official_registry' else 1.0
                self._throttle(host, interval)
                self.budget.reserve()
                with self.lock:
                    with (self.root / 'requests.jsonl').open('a', encoding='utf-8') as journal:
                        journal.write(json.dumps({'url': url, 'reserved_at': now(), 'source_class': source_class}) + '\n')
                        journal.flush()
                started = time.monotonic()
                status, headers, body = 0, {}, b''
                error = None
                try:
                    status, headers, body = self.transport(url, min(12, self.budget.remaining_seconds()), 2_000_000)
                except (OSError, ValueError, http.client.HTTPException) as exc:
                    error = type(exc).__name__ + ': ' + str(exc)[:160]
                finally:
                    event = {'url': url, 'status': status, 'retrieved_at': now(), 'elapsed_ms': round((time.monotonic()-started)*1000), 'bytes': len(body), 'error': error}
                    with self.lock:
                        self.events.append(event)
                if status not in (0, 429, 500, 502, 503, 504) or attempt == 1:
                    break
                with self.lock:
                    self.budget.retries += 1
                retry_after = headers.get('Retry-After', headers.get('retry-after', '1'))
                delay = min(10, max(1, int(retry_after))) if str(retry_after).isdigit() else 1
                if delay >= self.budget.remaining_seconds():
                    raise BudgetExceeded('Retry would exceed deadline')
                time.sleep(delay)
            if status in (301, 302, 303, 307, 308):
                location = headers.get('Location') or headers.get('location')
                if not location:
                    raise PolicyError('Redirect lacks Location')
                chain.append({'url': url, 'status': status})
                with self.lock:
                    self.budget.redirects += 1
                url = urljoin(url, location)
                continue
            with self.lock:
                self.failures[host] = self.failures.get(host, 0) + 1 if status in (0, 429, 500, 502, 503, 504) else 0
            sha = hashlib.sha256(body).hexdigest()
            retained = body
            transformed = False
            if source_class == 'official_registry' and body:
                try:
                    parsed_body = json.loads(body)
                    filtered = redact_personal(parsed_body)
                    if filtered != parsed_body:
                        retained = json.dumps(filtered, ensure_ascii=False, separators=(',', ':')).encode()
                        transformed = True
                except (ValueError, UnicodeError):
                    pass
            stored_hash = hashlib.sha256(retained).hexdigest()
            path = Path('evidence') / (stored_hash + '.bin')
            with self.lock:
                if not (self.root / path).exists():
                    (self.root / path).write_bytes(retained)
            snapshot = {'id': 'sn-' + digest([url, sha, event['retrieved_at']])[:24], 'requested_url': requested, 'final_url': url, 'redirect_chain': chain, 'status': status, 'content_type': headers.get('Content-Type', headers.get('content-type', '')), 'retrieved_at': event['retrieved_at'], 'content_sha256': sha, 'retained_sha256': stored_hash, 'privacy_redacted': transformed, 'path': path.as_posix(), 'source_class': source_class, 'retention': 'permitted_open_data' if source_class == 'official_registry' else 'company_owned_public_source', 'error': error}
            result = snapshot, retained
            with self.lock:
                if use_cache and status == 200:
                    self.cache[requested] = result
            return result
        raise PolicyError('Redirect limit reached')

    def _robots_allowed(self, url):
        parsed = urlsplit(url)
        origin = parsed.scheme + '://' + parsed.netloc
        with self.lock:
            parser = self.robots.get(origin)
        if parser is None:
            snap, body = self.fetch(origin + '/robots.txt', 'company_owned', check_robots=False)
            if snap['status'] == 404:
                parser = RobotFileParser(); parser.parse([])
            elif snap['status'] == 200:
                parser = RobotFileParser(); parser.parse(body.decode('utf-8', 'replace').splitlines())
            else:
                raise PolicyError('Robots permission unavailable')
            with self.lock:
                self.robots[origin] = parser
        if not parser.can_fetch(USER_AGENT, url):
            raise PolicyError('Blocked by robots.txt')
        delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*')
        if delay:
            self._throttle(parsed.hostname, max(1.0, float(delay)))
