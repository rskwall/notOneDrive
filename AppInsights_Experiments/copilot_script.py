import subprocess
import sys

def run_command(command: str) -> None:
    """Run a shell command and print its output in real time."""
    print(f"Running: {command}\n")
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"Command exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    # Change this command to whatever you want to run
    run_command('copilot -p "run copilot_task.json"')