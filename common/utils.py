import shlex
import subprocess
import sys
import os
import logging


def invoke_command(
    command: list[str],
    input: str = None,
    no_stderr_warning: bool = False,
    **kwargs,
) -> str:
    # Invoke a command and return the output
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    stdout, stderr = process.communicate(input=input.encode() if input else None)
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


def process(url: str, post_process_command: str) -> dict:
    carnivore_output = invoke_command(
        [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "../carnivore/app/main.py"),
            "--url",
            url,
        ]
    )
    post_process_command = shlex.split(post_process_command)
    output = invoke_command(post_process_command, input=carnivore_output)
    return output
