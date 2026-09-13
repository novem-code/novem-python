"""An optional stdin read must not block on a pipe nobody writes to.

Exercised in a subprocess: the behaviour under test is a real blocking read on
a real pipe, which an in-process fake stdin cannot reproduce.
"""

import subprocess
import sys
import time

import pytest

PROBE = "from novem.utils import data_on_stdin; print(repr(data_on_stdin(required={})))"


def spawn(required):
    return subprocess.Popen(
        [sys.executable, "-c", PROBE.format(required)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )


def wait_for_exit(proc, timeout):
    """Poll for exit without touching stdin, so the pipe stays open."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(0.02)
    return False


def test_optional_read_does_not_block_on_an_idle_pipe():
    proc = spawn(False)
    try:
        assert wait_for_exit(proc, 5), "data_on_stdin(required=False) blocked on an open, empty pipe"
        assert proc.stdout.read().strip() == "None"
    finally:
        proc.kill()
        proc.wait()


def test_required_read_still_waits_for_a_slow_producer():
    """A bare -w PATH asked for stdin, so it must wait rather than give up."""
    proc = spawn(True)
    try:
        time.sleep(0.6)
        assert proc.poll() is None, "required read gave up before the producer wrote"
        proc.stdin.write("late data")
        proc.stdin.close()
        assert wait_for_exit(proc, 5)
        assert proc.stdout.read().strip() == "'late data'"
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.parametrize("required", [True, False])
def test_piped_data_is_read_either_way(required):
    proc = spawn(required)
    out, _ = proc.communicate("1: 0 bg red", timeout=10)
    assert out.strip() == "'1: 0 bg red'"


@pytest.mark.parametrize("required", [True, False])
def test_closed_stdin_reads_as_empty(required):
    proc = spawn(required)
    out, _ = proc.communicate("", timeout=10)
    assert out.strip() == "None"
