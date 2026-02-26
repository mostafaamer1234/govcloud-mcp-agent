import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "mcp_server.app:app",
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="certs/server/server.key",
        ssl_certfile="certs/server/server.crt",
        ssl_ca_certs="certs/ca/ca.crt",
    )