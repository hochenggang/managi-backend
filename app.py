import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse

from setting import get_server_config, config as app_config
from routers import router
from common import safe_json_loads


def get_resource_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(redoc_url=None, docs_url=None, openapi_url=None, lifespan=lifespan)

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def get_index():
    html_path = get_resource_path("index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Index file not found</h1>", status_code=404)


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    try:
        response: Response = await call_next(request)
    except Exception as e:
        response = JSONResponse({"error": str(e)}, status_code=500)

    response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"

    return response


@app.options("/{path:path}")
async def options_handler(path: str):
    return Response(status_code=204)


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Managi Backend.")
    parser.add_argument("-p", "--port", type=int, default=None, help="Port to run the application on.")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to.")
    args = parser.parse_args()

    server_config = get_server_config()
    port = args.port or server_config.port
    host = args.host or server_config.host

    print(f"Server start at: {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=server_config.log_level,
        access_log=server_config.access_log,
    )
