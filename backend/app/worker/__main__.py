"""`python -m app.worker`: run the background worker with a Prometheus endpoint on :9101."""

from prometheus_client import start_http_server

from app.config import get_settings
from app.db import make_engine, make_sessionmaker, run_async
from app.llm import build_provider
from app.observability import setup_logging, setup_tracing
from app.worker import serve


async def main() -> None:
    settings = get_settings()
    setup_logging(settings)
    setup_tracing(settings, "evalops-worker")
    start_http_server(9101)
    engine = make_engine(settings)
    try:
        await serve(make_sessionmaker(engine), build_provider(settings), settings)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    run_async(main())
