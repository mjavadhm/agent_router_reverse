import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import (
    CLINE_USER_AGENT,
    HOST,
    PORT,
    STAINLESS_LANG,
    STAINLESS_RUNTIME,
    UPSTREAM_URL,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agentrouter-proxy")

# Global HTTP client
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    # Extended timeouts for large LLM completions
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=60.0)
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
    logger.info("=" * 60)
    logger.info("AgentRouter Reverse Proxy Started")
    logger.info(f"Local Server:    http://{HOST}:{PORT}")
    logger.info(f"Target Upstream: {UPSTREAM_URL}")
    logger.info(f"Spoofed Agent:   {CLINE_USER_AGENT}")
    logger.info("=" * 60)
    yield
    await http_client.aclose()
    logger.info("Reverse Proxy stopped.")


app = FastAPI(title="AgentRouter Cline Proxy", lifespan=lifespan)

# Allow all CORS requests for web-based frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hop-by-hop headers to exclude when proxying
EXCLUDE_HEADERS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "user-agent",
    "x-stainless-lang",
    "x-stainless-runtime",
}


@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": "AgentRouter Reverse Proxy",
        "upstream": UPSTREAM_URL,
        "spoofed_headers": {
            "User-Agent": CLINE_USER_AGENT,
            "X-Stainless-Lang": STAINLESS_LANG,
            "X-Stainless-Runtime": STAINLESS_RUNTIME,
        },
    }


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_handler(request: Request, full_path: str):
    start_time = time.time()
    method = request.method
    query_params = request.query_params
    target_url = f"{UPSTREAM_URL}/{full_path}"

    body = await request.body()

    # Extract model and stream info for informative console logging
    model_name = "unknown"
    is_stream = False
    if body and request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                model_name = payload.get("model", "unknown")
                is_stream = bool(payload.get("stream", False))
        except Exception:
            pass

    # Build forward headers
    forward_headers = {}
    for header, value in request.headers.items():
        header_lower = header.lower()
        if header_lower not in EXCLUDE_HEADERS:
            forward_headers[header] = value

    # Impersonate Cline headers
    forward_headers["User-Agent"] = CLINE_USER_AGENT
    forward_headers["X-Stainless-Lang"] = STAINLESS_LANG
    forward_headers["X-Stainless-Runtime"] = STAINLESS_RUNTIME

    # If stream requested, ensure Accept header is event-stream
    if is_stream:
        forward_headers["Accept"] = "text/event-stream"

    auth_preview = "Present" if "authorization" in forward_headers or "Authorization" in forward_headers else "None"

    logger.info(
        f"Incoming: {method} /{full_path} | Model: {model_name} | Stream: {is_stream} | Auth: {auth_preview}"
    )

    try:
        # Build outbound request
        upstream_req = http_client.build_request(
            method=method,
            url=target_url,
            params=query_params,
            headers=forward_headers,
            content=body,
        )

        response = await http_client.send(upstream_req, stream=True)
        status_code = response.status_code
        content_type = response.headers.get("content-type", "")

        # Check if upstream returned SSE stream
        if "text/event-stream" in content_type:
            logger.info(
                f"Streaming response initiated for /{full_path} (Status: {status_code})"
            )

            async def stream_generator():
                try:
                    async for chunk in response.aiter_raw():
                        yield chunk
                finally:
                    await response.aclose()
                    elapsed = time.time() - start_time
                    logger.info(
                        f"Stream completed for /{full_path} in {elapsed:.2f}s (Status: {status_code})"
                    )

            # Pass-through streaming response with anti-buffering headers
            return StreamingResponse(
                stream_generator(),
                status_code=status_code,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Standard non-streaming response
        content = await response.aread()
        await response.aclose()
        elapsed = time.time() - start_time

        if status_code >= 400:
            logger.warning(
                f"Upstream returned error {status_code} in {elapsed:.2f}s for /{full_path}: {content[:150].decode('utf-8', errors='ignore')}"
            )
        else:
            logger.info(
                f"Success {status_code} for /{full_path} in {elapsed:.2f}s"
            )

        # Forward response headers (excluding hop-by-hop)
        resp_headers = {}
        for k, v in response.headers.items():
            if k.lower() not in {"transfer-encoding", "connection", "content-encoding", "content-length"}:
                resp_headers[k] = v

        return Response(
            content=content,
            status_code=status_code,
            headers=resp_headers,
            media_type=content_type or "application/json",
        )

    except httpx.RequestError as exc:
        elapsed = time.time() - start_time
        logger.error(f"Upstream request failed after {elapsed:.2f}s: {exc}")
        return Response(
            content=json.dumps(
                {"error": {"message": f"Proxy upstream error: {str(exc)}", "type": "proxy_error"}}
            ),
            status_code=502,
            media_type="application/json",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
