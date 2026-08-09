import hashlib
import json
import os
import sys
import uuid
from functools import wraps
from pathlib import Path

from .models import SUPPORTED_FORMATS


CACHE_SCHEMA_VERSION = 1


def _generate_key(func_name: str, args: tuple, kwargs: dict, namespace=None) -> str:
    key_data = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "namespace": namespace,
        "func_name": func_name,
        "args": args,
        "kwargs": kwargs,
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def _cache_enabled() -> bool:
    return os.environ.get("CARNIVORE_CACHE") == "1"


def _cache_dir() -> Path:
    configured = os.environ.get("CARNIVORE_CACHE_DIR")
    if configured:
        return Path(configured)
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "carnivore"


def _cache_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def _trace_cache_hit() -> None:
    if os.environ.get("CARNIVORE_CACHE_TRACE") == "1":
        print("cache_hit", file=sys.stderr)


def _payload_checksum(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_fetch_result(key: str, result_type):
    """Read a validated result, treating every cache problem as a miss."""
    if not _cache_enabled():
        return None
    try:
        with _cache_path(key).open("r", encoding="utf-8") as cache_file:
            envelope = json.load(cache_file)
        if envelope.get("schema_version") != CACHE_SCHEMA_VERSION:
            return None
        payload = envelope.get("payload")
        if not isinstance(payload, dict) or envelope.get("key") != key:
            return None
        if envelope.get("payload_sha256") != _payload_checksum(payload):
            return None
        if payload.get("format") not in SUPPORTED_FORMATS or not isinstance(
            payload.get("content"), str
        ):
            return None
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            return None
        result = result_type(
            format=payload["format"], content=payload["content"], metadata=metadata
        )
        _trace_cache_hit()
        return result
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def write_fetch_result(key: str, result) -> None:
    """Atomically persist a result; cache failures must not affect fetching."""
    if not _cache_enabled():
        return
    temporary_file = None
    try:
        payload = {
            "format": result.format,
            "content": result.content,
            "metadata": result.metadata,
        }
        envelope = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "key": key,
            "payload": payload,
            "payload_sha256": _payload_checksum(payload),
        }
        cache_file = _cache_path(key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = cache_file.with_name(
            f".{cache_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        with temporary_file.open("w", encoding="utf-8") as output:
            json.dump(envelope, output, ensure_ascii=False, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_file, cache_file)
    except (OSError, TypeError, ValueError):
        if temporary_file is not None:
            try:
                temporary_file.unlink()
            except OSError:
                pass


def cached():
    """Keep the pre-contract decorator in memory without reading pickle data."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            func_this, *other_args = args
            key = _generate_key(
                func.__name__,
                tuple(other_args),
                kwargs,
                func_this.get_cache_namespace()
                if hasattr(func_this, "get_cache_namespace")
                else None,
            )
            if key not in func_this.cache_store:
                func_this.cache_store[key] = await func(*args, **kwargs)
            return func_this.cache_store[key]

        return wrapper

    return decorator
