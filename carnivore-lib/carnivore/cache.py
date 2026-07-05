import hashlib
import json
import os
import pickle


CACHE_SCHEMA_VERSION = 1


def _generate_key(func_name: str, args: tuple, kwargs: dict) -> str:
    key_data = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "func_name": func_name,
        "args": args,
        "kwargs": kwargs,
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def _get_cache_file_path(cache_dir: str, key: str) -> str:
    return os.path.join(cache_dir, f"{key}.pickle")


def _read_disk_cache(cache_dir: str, key: str):
    cache_file_path = _get_cache_file_path(cache_dir, key)
    if not os.path.exists(cache_file_path):
        return None
    with open(cache_file_path, "rb") as cache_file:
        return pickle.load(cache_file)


def _write_disk_cache(cache_dir: str, key: str, value):
    os.makedirs(cache_dir, exist_ok=True)
    cache_file_path = _get_cache_file_path(cache_dir, key)
    temporary_file_path = f"{cache_file_path}.tmp"
    with open(temporary_file_path, "wb") as cache_file:
        pickle.dump(value, cache_file)
    os.replace(temporary_file_path, cache_file_path)


def cached():
    def decorator(func):
        async def wrapper(*args, **kwargs):
            (func_this, *other_args) = args
            key = _generate_key(func.__name__, other_args, kwargs)
            value = func_this.cache_store.get(key)
            if value is None:
                cache_dir = os.environ.get("CARNIVORE_CACHE_DIR")
                if os.environ.get("CARNIVORE_CACHE") != "0" and cache_dir:
                    value = _read_disk_cache(cache_dir, key)
            if value is None:
                try:
                    value = await func(*args, **kwargs)
                except Exception as e:
                    value = e
                func_this.cache_store[key] = value
                cache_dir = os.environ.get("CARNIVORE_CACHE_DIR")
                if (
                    os.environ.get("CARNIVORE_CACHE") != "0"
                    and cache_dir
                    and not isinstance(value, Exception)
                ):
                    _write_disk_cache(cache_dir, key, value)
            if isinstance(value, Exception):
                raise value
            return value

        return wrapper

    return decorator
