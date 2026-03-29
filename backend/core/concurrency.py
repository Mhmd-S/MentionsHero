"""Shared concurrency controls for job processing."""

import asyncio

MAX_CONCURRENT_JOBS = 10
MAX_CONCURRENT_AUTO = 3

job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
auto_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUTO)
