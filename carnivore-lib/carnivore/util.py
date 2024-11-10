import atexit
import json
import shlex
import subprocess
import logging
import asyncio


def kill_child(proc: subprocess.Popen):
    try:
        proc.kill()
    except Exception:
        pass


async def invoke_command(
    command: list[str],
    input: str = None,
    no_stderr_warning: bool = False,
    **kwargs,
) -> str:
    # Invoke a command and return the output
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    atexit.register(kill_child, process)
    stdout, stderr = await process.communicate(input=input.encode() if input else None)
    if process.returncode != 0:
        message = (
            f"Subprocess of command {command} failed"
            f" with exit code {process.returncode}."
        )
        if stderr:
            message += f" stderr: {stderr.decode().strip()}"
        if stdout:
            message += f" stdout: {stdout.decode().strip()}"
        raise Exception(message)
    if not no_stderr_warning and stderr:
        logging.warning(
            f"Subprocess of command {command} succeeded"
            f" with stderr: {stderr.decode().strip()}"
        )
    return stdout.decode().strip()


async def post_process(carnivore_output: dict, post_process_command: str) -> dict:
    carnivore_output_json = json.dumps(carnivore_output)
    post_process_command = shlex.split(post_process_command)
    output = await invoke_command(post_process_command, input=carnivore_output_json)
    return output
