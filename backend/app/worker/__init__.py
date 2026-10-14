"""Background worker: polls the eval_runs table for queued runs and executes them."""

import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.llm.base import LLMProvider
from app.observability import QUEUE_AGE, QUEUE_DEPTH
from app.repositories import Repo
from app.services.executor import execute_run

log = logging.getLogger(__name__)


async def run_once(
    maker: async_sessionmaker[AsyncSession], provider: LLMProvider, settings: Settings
) -> int | None:
    """Claim and execute one queued run. Returns its id, or None if the queue is empty."""
    async with maker() as s:
        repo = Repo(s)
        QUEUE_AGE.set(await repo.oldest_queued_age_seconds())
        QUEUE_DEPTH.set((await repo.count_runs_by_status()).get("queued", 0))
        run = await repo.claim_next_run()
        run_id = run.id if run else None
    if run_id is None:
        return None
    log.info("claimed run", extra={"run_id": run_id})
    await execute_run(maker, run_id, provider, settings)
    return run_id


async def drain(
    maker: async_sessionmaker[AsyncSession], provider: LLMProvider, settings: Settings
) -> list[int]:
    """Process queued runs until none are left. Used by tests and the seed script."""
    done: list[int] = []
    while (run_id := await run_once(maker, provider, settings)) is not None:
        done.append(run_id)
    return done


async def serve(
    maker: async_sessionmaker[AsyncSession], provider: LLMProvider, settings: Settings
) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows event loop
            pass
    log.info("worker started", extra={"status": "ready"})
    while not stop.is_set():
        try:
            claimed = await run_once(maker, provider, settings)
        except Exception:
            log.exception("worker loop error")
            claimed = None
        if claimed is None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
    log.info("worker stopped")
