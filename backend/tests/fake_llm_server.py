import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_bad_keys: set[str] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    env_bad = os.environ.get("FAKE_LLM_BAD_KEYS", "")
    if env_bad:
        _bad_keys.update(k for k in env_bad.split(",") if k)
    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    model: str
    messages: list


class ControlBody(BaseModel):
    keys: list[str] = []


@app.post("/__control__/bad_keys")
async def set_bad_keys(body: ControlBody):
    _bad_keys.clear()
    _bad_keys.update(body.keys)
    return {"ok": True, "bad_keys": list(_bad_keys)}


@app.post("/{path:path}")
async def chat_completions(_path: str, request: Request):
    auth = request.headers.get("authorization", "")
    key = auth.removeprefix("Bearer ").strip()
    if not key:
        return JSONResponse({"error": "missing api key"}, status_code=401)

    model_hint = ""
    try:
        body = await request.json()
        model_hint = body.get("model", "")
    except Exception:  # noqa: BLE001
        pass

    if key in _bad_keys:
        return JSONResponse(
            {
                "error": "simulated auth failure",
                "key_preview": key[:12],
                "requested_model": model_hint,
            },
            status_code=401,
        )

    return JSONResponse(
        {
            "id": "fake-cmpl",
            "object": "chat.completion",
            "created": 1234567890,
            "model": model_hint or "unknown",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"ok:{key[:12]}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
