import logging
from fastapi import Request

logger = logging.getLogger("request_body_logger")


async def log_request_body_middleware(request: Request, call_next):
    body = await request.body()
    if body:
        logger.info(f"Request Body: {body.decode('utf-8', errors='ignore')}")

    async def receive():
        return {"type": "http.request", "body": body}

    new_request = Request(request.scope, receive)
    response = await call_next(new_request)
    return response
