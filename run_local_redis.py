"""Local dev-only stand-in for a real Redis server, used because this
sandboxed machine cannot run Docker Desktop or WSL2 (both fail with
virtualization errors -- confirmed directly, not assumed). fakeredis's
TcpFakeServer speaks the real RESP protocol over a real TCP socket on
localhost:6379, so the app's own real redis.asyncio client connects to
it exactly as it would a real Redis server -- not a mock substituted
into the app's own code. Not for production use; a real deployment
runs real Redis (see docker-compose.selfhosted.yml)."""

from fakeredis import TcpFakeServer

if __name__ == "__main__":
    server_address = ("127.0.0.1", 6379)
    server = TcpFakeServer(server_address, server_type="redis")
    print(f"fake Redis TCP server listening on {server_address}")
    server.serve_forever()
