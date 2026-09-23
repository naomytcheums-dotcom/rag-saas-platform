# Reverse proxy + HTTPS (optional)

Real, opt-in Nginx + Let's Encrypt (Certbot) setup for the self-hosted
stack (`docker-compose.selfhosted.yml`). Off by default — skip this
entirely if you're already behind your own proxy or load balancer.

## 1. Prerequisites

- A real domain name pointing (A/AAAA record) at this host's public IP.
- Ports 80 and 443 open and free on this host.
- `DOMAIN_NAME=your-domain.example.com` set in `.env`.

## 2. First-time certificate issuance

Nginx needs a certificate to start with `ssl_certificate` pointing at a
real file, and Certbot's webroot challenge needs Nginx already serving
`/.well-known/acme-challenge/` — so the very first certificate is
issued with a **temporary, HTTP-only** Nginx config, then the real one
(HTTPS + security headers, `nginx/templates/default.conf.template`)
takes over:

```bash
# 1. Start only Nginx, temporarily, on plain HTTP.
docker compose -f docker-compose.selfhosted.yml --profile proxy up -d nginx

# 2. Issue the real certificate via the webroot Certbot already has mounted.
docker compose -f docker-compose.selfhosted.yml --profile proxy run --rm certbot \
  certonly --webroot -w /var/www/certbot -d "$DOMAIN_NAME" \
  --email you@example.com --agree-tos --no-eff-email

# 3. Restart Nginx so it picks up the now-real certificate, and start
#    the renewal loop.
docker compose -f docker-compose.selfhosted.yml --profile proxy up -d
```

## 3. Renewal

The `certbot` service's own entrypoint runs `certbot renew` every 12
hours in a loop — a real no-op unless a certificate is within its own
renewal window (Let's Encrypt's own recommendation). Nothing else to
schedule.

## 4. Verifying

```bash
curl -I http://your-domain.example.com/      # -> 301 to https://
curl -I https://your-domain.example.com/     # -> 200, real Strict-Transport-Security header
```
