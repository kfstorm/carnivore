import hashlib
import json


def _generate_key(func_name: str, args: tuple, kwargs: dict) -> str:
    key_data = {"func_name": func_name, "args": args, "kwargs": kwargs}
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached():
    def decorator(func):
        async def wrapper(*args, **kwargs):
            (func_this, *other_args) = args
            key = _generate_key(func.__name__, other_args, kwargs)
            value = func_this.cache_store.get(key)
            if value is None:
                try:
                    value = await func(*args, **kwargs)
                except Exception as e:
                    value = e
                func_this.cache_store[key] = value
            if isinstance(value, Exception):
                raise value
            return value

        return wrapper

    return decorator
