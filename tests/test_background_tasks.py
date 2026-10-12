"""Tests for background task reference tracking and error handling."""

import asyncio
import logging
import pytest

from app.core.tasks import create_background_task, get_active_tasks


@pytest.mark.asyncio
async def test_create_background_task_retains_reference_and_cleans_up():
    completed = False

    async def sample_coro():
        nonlocal completed
        await asyncio.sleep(0.03)
        completed = True

    task = create_background_task(sample_coro(), name="test_sample_task")

    # While task is running, it must be retained in active tasks set
    assert task in get_active_tasks()

    # Wait for completion
    await asyncio.sleep(0.06)

    assert completed is True
    # Once done, it must be automatically discarded via done callback
    assert task not in get_active_tasks()


@pytest.mark.asyncio
async def test_background_task_logs_unhandled_exception(caplog):
    async def failing_coro():
        await asyncio.sleep(0.01)
        raise ValueError("Simulated background error")

    with caplog.at_level(logging.ERROR):
        task = create_background_task(failing_coro(), name="failing_task")
        await asyncio.sleep(0.04)

    assert task not in get_active_tasks()
    assert "Simulated background error" in caplog.text
    assert "failing_task" in caplog.text
