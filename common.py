import json
import asyncio
from functools import partial
from typing import Any, Callable, TypeVar, Coroutine
from contextlib import asynccontextmanager


T = TypeVar('T')


async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    loop = asyncio.get_running_loop()
    partial_func = partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, partial_func)


@asynccontextmanager
async def async_lock():
    lock = asyncio.Lock()
    async with lock:
        yield


class AsyncTaskPool:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def run(self, coro: Coroutine) -> Any:
        async with self.semaphore:
            return await coro


def safe_json_loads(data: str) -> dict:
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)
