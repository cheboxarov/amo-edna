import logging
from fastapi import FastAPI
from presentation.routers.health import router as health_router
from presentation.routers.webhooks import router as webhooks_router, container
from presentation.middleware.logging import log_request_body_middleware
import uvicorn

# Configure logging to show DEBUG for our clients
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("amocrm.amojo").setLevel(logging.DEBUG)
logging.getLogger("edna").setLevel(logging.DEBUG)
logging.getLogger("request_body_logger").setLevel(logging.INFO)

app = FastAPI(title="edna-amocrm-integration")

app.middleware("http")(log_request_body_middleware)

app.include_router(health_router)
app.include_router(webhooks_router)


@app.on_event("startup")
async def startup() -> None:
	await container.amocrm_client.ensure_ready()
	await container.edna_client.ensure_ready()


if __name__ == "__main__":
	uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
