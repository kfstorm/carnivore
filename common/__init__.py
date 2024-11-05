import shlex
import subprocess
import sys
import os


def invoke_command(
    command: list[str],
    input: str = None,
    redirect_stderr_to_stdout: bool = False,
    **kwargs,
) -> str:
    # Invoke a command and return the output
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=(subprocess.STDOUT if redirect_stderr_to_stdout else subprocess.PIPE),
        **kwargs,
    )
    stdout, stderr = process.communicate(input=input.encode() if input else None)
    if process.returncode != 0:
        message = (
            f"Subprocess of command {command} failed"
            f" with exit code {process.returncode}."
        )
        if stdout and stderr:
            message += f"\nstderr:\n{stderr.decode()}"
            message += f"\nstdout:\n{stdout.decode()}"
        elif stdout:
            message += f"\n{stdout.decode()}"
        elif stderr:
            message += f"\n{stderr.decode()}"
        raise Exception(message)
    return stdout.decode()


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
