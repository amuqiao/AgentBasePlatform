"""
Application entry point.
Usage: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging

from src.main import app  # noqa: F401


if __name__ == "__main__":
    import uvicorn

    host = "0.0.0.0"
    port = 8000
    docs_url = "/docs"
    logging.getLogger(__name__).info("Swagger UI docs: http://127.0.0.1:%s%s", port, docs_url)
    uvicorn.run("main:app", host=host, port=port, reload=True)
