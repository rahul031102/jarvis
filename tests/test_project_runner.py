"""
Tests project_runner.py's decision logic (project-type detection, deps-
missing detection, start-script picking) directly, and the async
start/stop flow with subprocess creation mocked out — no real npm/pip/
node process is spawned, but the actual control flow (install-if-missing,
crash detection within the grace window, process bookkeeping for
stop_project) is exercised for real.
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.errors import JarvisError
from tools import project_runner


def make_node_project(tmp_path, scripts=None, with_node_modules=False):
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "package.json").write_text(json.dumps({"scripts": scripts or {"start": "node index.js"}}))
    if with_node_modules:
        (project / "node_modules").mkdir()
    return project


def make_python_project(tmp_path, entrypoint="app.py", with_venv=False):
    project = tmp_path / "pyapp"
    project.mkdir()
    (project / "requirements.txt").write_text("flask\n")
    (project / entrypoint).touch()
    if with_venv:
        (project / ".venv").mkdir()
    return project


# ---------- pure decision-logic tests (no mocking needed) ----------

def test_detect_node_project(tmp_path):
    project = make_node_project(tmp_path)
    assert project_runner._detect_project_type(project) == "node"


def test_detect_python_project(tmp_path):
    project = make_python_project(tmp_path)
    assert project_runner._detect_project_type(project) == "python"


def test_detect_unknown_project_raises(tmp_path):
    project = tmp_path / "mystery"
    project.mkdir()
    with pytest.raises(JarvisError):
        project_runner._detect_project_type(project)


def test_deps_missing_true_when_no_node_modules(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=False)
    assert project_runner._deps_missing(project, "node") is True


def test_deps_missing_false_when_node_modules_present(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=True)
    assert project_runner._deps_missing(project, "node") is False


def test_pick_node_start_script_prefers_dev_over_start(tmp_path):
    project = make_node_project(tmp_path, scripts={"start": "node index.js", "dev": "nodemon index.js"})
    assert project_runner._pick_node_start_script(project) == ["npm", "run", "dev"]


def test_pick_node_start_script_falls_back_to_start(tmp_path):
    project = make_node_project(tmp_path, scripts={"start": "node index.js"})
    assert project_runner._pick_node_start_script(project) == ["npm", "run", "start"]


def test_pick_node_start_script_raises_if_neither_present(tmp_path):
    project = make_node_project(tmp_path, scripts={"test": "jest"})
    with pytest.raises(JarvisError):
        project_runner._pick_node_start_script(project)


def test_pick_python_entrypoint_prefers_manage_py(tmp_path):
    project = make_python_project(tmp_path, entrypoint="manage.py")
    assert project_runner._pick_python_entrypoint(project) == ["python", "manage.py"]


def test_pick_python_entrypoint_raises_if_none_found(tmp_path):
    project = tmp_path / "empty_py"
    project.mkdir()
    (project / "requirements.txt").write_text("flask\n")
    with pytest.raises(JarvisError):
        project_runner._pick_python_entrypoint(project)


# ---------- async flow tests (subprocess creation mocked) ----------

class FakeProcess:
    """Stands in for asyncio.subprocess.Process."""
    def __init__(self, returncode_after_wait=None, stdout_data=b""):
        self.returncode = None
        self._returncode_after_wait = returncode_after_wait
        self.stdout = MagicMock()
        self.stdout.read = AsyncMock(return_value=stdout_data)
        self.terminate = MagicMock()
        self.kill = MagicMock()

    async def wait(self):
        if self._returncode_after_wait is None:
            # Simulate "still running" — the test's asyncio.wait_for will time out.
            await asyncio.sleep(10)
        self.returncode = self._returncode_after_wait
        return self.returncode


@pytest.mark.asyncio
async def test_start_project_success_when_deps_present(tmp_path, monkeypatch):
    monkeypatch.setattr(project_runner, "STARTUP_GRACE_PERIOD_S", 0.05)
    project = make_node_project(tmp_path, with_node_modules=True)
    long_running = FakeProcess(returncode_after_wait=None)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=long_running)):
        result = await project_runner.start_project(str(project))

    assert "Started" in result
    assert "still running" in result
    # Cleanup so other tests don't see this process as already-running.
    project_runner._RUNNING_PROJECTS.pop(str(project.resolve()), None)


@pytest.mark.asyncio
async def test_start_project_reports_immediate_crash(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=True)
    crashed = FakeProcess(returncode_after_wait=1, stdout_data=b"Error: address already in use")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=crashed)):
        with pytest.raises(JarvisError) as excinfo:
            await project_runner.start_project(str(project))

    assert "exited immediately" in str(excinfo.value)
    assert "address already in use" in str(excinfo.value)
    # Must not be left in the running-processes table since it crashed.
    assert str(project.resolve()) not in project_runner._RUNNING_PROJECTS


@pytest.mark.asyncio
async def test_start_project_installs_deps_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(project_runner, "STARTUP_GRACE_PERIOD_S", 0.05)
    project = make_node_project(tmp_path, with_node_modules=False)
    install_proc = AsyncMock()
    install_proc.communicate = MagicMock(side_effect=lambda: asyncio.ensure_future(asyncio.to_thread(lambda: (b"added 42 packages", None))))
    install_proc.returncode = 0

    server_proc = FakeProcess(returncode_after_wait=None)

    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        if args[0] == "npm" and "install" in args:
            return install_proc
        return server_proc

    with patch("asyncio.create_subprocess_exec", new=fake_create_subprocess_exec):
        result = await project_runner.start_project(str(project))

    assert any(c[:2] == ("npm", "install") for c in calls)
    assert "Started" in result
    project_runner._RUNNING_PROJECTS.pop(str(project.resolve()), None)


@pytest.mark.asyncio
async def test_start_project_reports_install_failure(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=False)
    install_proc = AsyncMock()
    install_proc.communicate = MagicMock(side_effect=lambda: asyncio.ensure_future(asyncio.to_thread(lambda: (b"npm ERR! network timeout", None))))
    install_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=install_proc)):
        with pytest.raises(JarvisError) as excinfo:
            await project_runner.start_project(str(project))

    assert "Installing dependencies failed" in str(excinfo.value)
    # Must NOT have attempted to start a server after a failed install.
    assert str(project.resolve()) not in project_runner._RUNNING_PROJECTS


@pytest.mark.asyncio
async def test_start_project_missing_folder_raises(tmp_path):
    with pytest.raises(JarvisError):
        await project_runner.start_project(str(tmp_path / "does_not_exist"))


@pytest.mark.asyncio
async def test_stop_project_terminates_tracked_process(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=True)
    key = str(project.resolve())
    proc = FakeProcess(returncode_after_wait=0)
    project_runner._RUNNING_PROJECTS[key] = proc

    result = await project_runner.stop_project(str(project))

    assert "Stopped" in result
    assert proc.terminate.called
    assert key not in project_runner._RUNNING_PROJECTS


@pytest.mark.asyncio
async def test_stop_project_not_running_raises(tmp_path):
    project = make_node_project(tmp_path, with_node_modules=True)
    with pytest.raises(JarvisError):
        await project_runner.stop_project(str(project))
