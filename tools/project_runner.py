"""
The "real agent" feature from the spec: "open my project, install
dependencies if missing, start the server, tell me if it's running."

Security note: the LLM only ever supplies a PROJECT PATH. Every actual
command run here (npm install, npm start, pip install, python app.py) is
chosen by fixed logic based on what manifest files are found in that path
— never a string the LLM composes. This keeps the "no arbitrary shell
execution from the model" rule intact even though this tool does run real
subprocess commands.

Honesty about verification: we can't reliably know an arbitrary dev
server actually "works" (that would need knowing its port, framework,
health-check endpoint, etc). What we CAN honestly verify is: did the
process survive past its own crash window, and if not, why. That's what
"verify" means here — stated plainly rather than pretending to a
guarantee we don't have.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from config.settings import settings
from core.errors import JarvisError
from core.logging_setup import log

# Tracks background dev-server processes we've started, keyed by resolved
# project path, so `stop_project` can find and terminate them later.
_RUNNING_PROJECTS: dict[str, subprocess.Popen] = {}

STARTUP_GRACE_PERIOD_S = 4  # how long we wait to see if the server crashes immediately
INSTALL_TIMEOUT_S = 300  # dependency installs can legitimately take a few minutes


def _detect_project_type(project_dir: Path) -> str:
    if (project_dir / "package.json").exists():
        return "node"
    if (project_dir / "requirements.txt").exists() or (project_dir / "pyproject.toml").exists():
        return "python"
    raise JarvisError(
        "I don't see a package.json or requirements.txt in that folder — "
        "I don't know how to start this project."
    )


def _deps_missing(project_dir: Path, project_type: str) -> bool:
    if project_type == "node":
        return not (project_dir / "node_modules").exists()
    # Python: no single universal marker. Treat presence of a local venv or
    # already-satisfied imports as "installed enough" — otherwise we'd
    # reinstall on every single start, which the spec explicitly says to avoid.
    return not (project_dir / ".venv").exists() and not (project_dir / "venv").exists()


async def _run_and_wait(cmd: list[str], cwd: Path, timeout_s: int) -> tuple[int, str]:
    """Run a command to completion (e.g. an install step) and return
    (exit_code, combined_output_tail)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise JarvisError(f"Installing dependencies timed out after {timeout_s} seconds.")
    output = stdout.decode(errors="replace")
    tail = "\n".join(output.strip().splitlines()[-15:])
    return proc.returncode, tail


def _pick_node_start_script(project_dir: Path) -> list[str]:
    package_json = project_dir / "package.json"
    try:
        data = json.loads(package_json.read_text())
    except Exception as exc:
        raise JarvisError("I couldn't read package.json.", technical_detail=str(exc))
    scripts = data.get("scripts", {})
    for candidate in ("dev", "start"):
        if candidate in scripts:
            return ["npm", "run", candidate]
    raise JarvisError("This project's package.json doesn't have a 'dev' or 'start' script.")


def _pick_python_entrypoint(project_dir: Path) -> list[str]:
    for candidate in ("manage.py", "app.py", "main.py", "run.py"):
        if (project_dir / candidate).exists():
            return ["python", candidate]
    raise JarvisError(
        "I couldn't find a common entry point (app.py, main.py, run.py, manage.py) in this project."
    )


async def start_project(path: str) -> str:
    project_dir = Path(path).expanduser().resolve()
    if not project_dir.is_dir():
        raise JarvisError("That project folder doesn't exist.")

    key = str(project_dir)
    if key in _RUNNING_PROJECTS and _RUNNING_PROJECTS[key].returncode is None:
        return f"{project_dir.name} is already running."

    project_type = _detect_project_type(project_dir)
    log.info("Project '%s' detected as %s", project_dir, project_type)

    if _deps_missing(project_dir, project_type):
        log.info("Dependencies missing for '%s', installing...", project_dir)
        install_cmd = ["npm", "install"] if project_type == "node" else ["pip", "install", "-r", "requirements.txt"]
        try:
            code, tail = await _run_and_wait(install_cmd, project_dir, INSTALL_TIMEOUT_S)
        except FileNotFoundError:
            tool = install_cmd[0]
            raise JarvisError(f"I couldn't run '{tool}' — is it installed and on PATH?")
        if code != 0:
            log.warning("Dependency install failed for '%s':\n%s", project_dir, tail)
            raise JarvisError(f"Installing dependencies failed. Last output: {tail[-300:]}")
        log.info("Dependencies installed for '%s'", project_dir)

    start_cmd = _pick_node_start_script(project_dir) if project_type == "node" else _pick_python_entrypoint(project_dir)

    try:
        proc = await asyncio.create_subprocess_exec(
            *start_cmd, cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        raise JarvisError(f"I couldn't run '{start_cmd[0]}' — is it installed and on PATH?")

    _RUNNING_PROJECTS[key] = proc

    # Honest verification: wait a short grace period and see if it's still
    # alive. We are NOT claiming the server is fully up and serving
    # requests — only that it didn't immediately crash.
    try:
        await asyncio.wait_for(proc.wait(), timeout=STARTUP_GRACE_PERIOD_S)
    except asyncio.TimeoutError:
        # Still running after the grace period — good sign.
        return f"Started {project_dir.name}. It's still running after {STARTUP_GRACE_PERIOD_S} seconds with no crash."

    # It exited within the grace period — that's a real failure, report why.
    output = ""
    if proc.stdout:
        try:
            raw = await proc.stdout.read()
            output = raw.decode(errors="replace")
        except Exception:
            pass
    tail = "\n".join(output.strip().splitlines()[-10:])
    _RUNNING_PROJECTS.pop(key, None)
    raise JarvisError(
        f"{project_dir.name} exited immediately with code {proc.returncode}. "
        f"Last output: {tail[-300:] if tail else '(no output captured)'}"
    )


async def stop_project(path: str) -> str:
    project_dir = Path(path).expanduser().resolve()
    key = str(project_dir)
    proc = _RUNNING_PROJECTS.get(key)
    if proc is None or proc.returncode is not None:
        raise JarvisError(f"{project_dir.name} doesn't appear to be running.")
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
    _RUNNING_PROJECTS.pop(key, None)
    return f"Stopped {project_dir.name}."
