import asyncio


async def invoke_command(
    command: list[str],
    input: str | None = None,
    max_output_bytes: int | None = None,
    **kwargs,
) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,
    )
    try:
        stdout, _ = await process.communicate(
            input.encode("utf-8") if input is not None else None
        )
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise

    if max_output_bytes is not None and len(stdout) > max_output_bytes:
        raise RuntimeError("Subprocess output exceeded the configured limit")
    if process.returncode != 0:
        raise RuntimeError("Subprocess failed")
    return stdout.decode("utf-8").strip()
