"""The DNS resolver used by every domain-ownership check (custom hosting domain, e-mail sending domain, DKIM publication).

By default the machine's own resolver configuration is used. `CUSTOM_DOMAIN_DNS_NAMESERVERS` ("1.1.1.1,8.8.8.8" or "127.0.0.1:5353") pins the
checks to chosen nameservers instead: useful to avoid a stale local cache after a customer changed a record, to use a resolver that is reachable from a
locked-down network, and to exercise the real DNS protocol against a local test server."""

import dns.asyncresolver

from api.config import settings


def parse_nameservers(value: str) -> tuple[list[str], dict[str, int]]:
    """"host[:port]" items separated by commas -> (hosts, {host: port}) in the form dnspython expects. An IPv6 literal must be bracketed: "[::1]:5353"."""
    hosts: list[str] = []
    ports: dict[str, int] = {}
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        host, port = item, None
        if item.startswith("["):
            host, _, rest = item[1:].partition("]")
            port = rest.lstrip(":") or None
        elif item.count(":") == 1:
            host, port = item.split(":")
        hosts.append(host)
        if port:
            ports[host] = int(port)
    return hosts, ports


def make_txt_resolver() -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    resolver.lifetime = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    hosts, ports = parse_nameservers(settings.CUSTOM_DOMAIN_DNS_NAMESERVERS)
    if hosts:
        resolver.nameservers = hosts
        resolver.nameserver_ports = ports
    return resolver
