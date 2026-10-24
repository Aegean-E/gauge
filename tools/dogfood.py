#!/usr/bin/env python3
"""
Gauge's dogfood runner: use the product as a user does, then attack its input edge.

The golden path renders a sparkline, its ASCII twin, signed bars, a histogram, the JSON summary,
stdin and file sources, width resampling and the demo. The chaos track sends empty and malformed
input, non-finite values, impossible widths and bin counts, conflicting sources, a missing file,
an unknown flag and a legacy pipe encoding. Every child runs in its own process group and is
killed through a context manager; one temporary sandbox holds every file and the project tree is
snapshotted before and after.

Usage: python tools/dogfood.py   (exit 0 pass, 1 fail, 2 cannot run)

PRINCIPLE-015.
"""

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / ".aikit" / "dogfood_last_run.log"
TIMEOUT_SECONDS = 30.0
KILL_TIMEOUT_SECONDS = 10.0
MAX_REPORT_LINES = 15


class Report:
    """Collects step outcomes: the console sees a summary, the log sees everything."""

    def __init__(self) -> None:
        self.lines: List[str] = []
        self.failures: List[str] = []

    def step(self, ok: bool, label: str, detail: str = "") -> bool:
        """Record one step's outcome and hand back whether it passed."""
        mark = "PASS" if ok else "FAIL"
        self.lines.append(f"[{mark}] {label}" + (f" :: {detail}" if detail else ""))
        if not ok:
            self.failures.append(f"{label}: {detail}" if detail else label)
        return ok


def terminate_tree(process: subprocess.Popen) -> None:
    """Kill a child and everything it started, on Windows and POSIX alike."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=KILL_TIMEOUT_SECONDS)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=KILL_TIMEOUT_SECONDS)


@contextlib.contextmanager
def supervised(command: List[str], box: Path, env: Dict[str, str], use_stdin: bool):
    """Run one child with captured output and a guaranteed process-tree teardown."""
    if os.name == "nt":
        creation = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        creation = {"start_new_session": True}
    options = dict(
        stdin=subprocess.PIPE if use_stdin else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(box),
        env=env,
        **creation,
    )
    process = subprocess.Popen(command, **options)  # hygiene: allow RAII teardown below
    try:
        yield process
    finally:
        terminate_tree(process)


def run_cli(box: Path, *args: str, stdin_text: Optional[str] = None,
            extra_env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    """Run `python -m gauge ARGS` in the sandbox and return (exit code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing if existing else "")
    if extra_env:
        env.update(extra_env)
    command = [sys.executable, "-m", "gauge", *args]
    try:
        with supervised(command, box, env, use_stdin=stdin_text is not None) as process:
            try:
                out, err = process.communicate(input=stdin_text, timeout=TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                return 124, "", f"timed out after {TIMEOUT_SECONDS:.0f}s"
        return process.returncode, out, err
    except OSError as exc:
        return 127, "", str(exc)


def fingerprint() -> str:
    """The project's tracked and untracked state, so a run that dirties it fails."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return result.stdout


def golden_path(box: Path, report: Report) -> None:
    """Every reading surface and every source, once, in the sandbox."""
    code, out, _ = run_cli(box, "spark", *[str(n) for n in range(8)])
    report.step(code == 0 and "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588" in out,
                "spark renders the eight levels", f"exit {code}")

    code, out, _ = run_cli(box, "spark", "1", "2", "3", "--ascii")
    report.step(code == 0 and out.isascii() and bool(out.strip()),
                "the ascii twin stays ascii", f"exit {code}")

    code, out, _ = run_cli(box, "stats", "2", "3", "5", "8", "--json")
    try:
        summary = json.loads(out)
        ok = code == 0 and summary["count"] == 4 and summary["median"] == 4.0
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "stats emits the documented json object", f"exit {code}")

    code, out, _ = run_cli(box, "stats", "--json", stdin_text="1, 2\n3 4\n")
    try:
        ok = code == 0 and json.loads(out)["count"] == 4
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "stdin lines reach the summary", f"exit {code}")

    values_file = box / "values.txt"
    values_file.write_text("4 5 6\n", encoding="utf-8")
    code, out, _ = run_cli(box, "stats", "--file", str(values_file), "--json")
    try:
        ok = code == 0 and json.loads(out)["max"] == 6.0
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "a file reaches the summary", f"exit {code}")

    code, out, _ = run_cli(box, "bars", "-4", "0", "6", "--width", "21", "--ascii")
    lines = out.splitlines()
    report.step(code == 0 and len(lines) == 3 and all("|" in line for line in lines),
                "signed bars keep a zero axis", f"exit {code}, {len(lines)} rows")

    code, out, _ = run_cli(box, "hist", "1", "2", "2", "3", "3", "3",
                           "--bins", "3", "--width", "12", "--ascii")
    lines = out.splitlines()
    report.step(code == 0 and len(lines) == 3 and all("[" in line for line in lines)
                and "#" in out,
                "hist bins the series into aligned rows", f"exit {code}, {len(lines)} rows")

    code, out, _ = run_cli(box, "box", "1", "2", "3", "4", "5", "--width", "20", "--ascii")
    report.step(code == 0 and "[" in out and "]" in out and "med:" in out,
                "box renders horizontal ruler and 5-number summary", f"exit {code}")

    code, out, _ = run_cli(box, "stats", "-f", "2", "-d", ",", "--json",
                           stdin_text="a,10,x\nb,20,y\nc,30,z\n")
    try:
        ok = code == 0 and json.loads(out)["mean"] == 20.0
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "field and delimiter extraction parses delimited table", f"exit {code}")

    code, out, _ = run_cli(box, "stats", "10", "20", "30", "--percentiles", "50,90", "--json")
    try:
        data = json.loads(out)
        ok = code == 0 and "percentiles" in data and data["percentiles"]["50"] == 20.0
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "extended percentiles are reported in json", f"exit {code}")

    code, out, _ = run_cli(box, "spark", "--width", "20",
                           stdin_text=" ".join(str(n) for n in range(100)))
    report.step(code == 0 and len(out.strip()) == 20,
                "a long series resamples to the requested width", f"exit {code}")

    code, out, _ = run_cli(box, "demo")
    report.step(code == 0 and "gauge demo" in out and "median" in out,
                "the demo shows both surfaces", f"exit {code}")

    code, out, _ = run_cli(box, "stats", "1e308", "-1e308", "--json")
    try:
        ok = code == 0 and json.loads(out)["stdev"] == 1e308
    except (ValueError, KeyError):
        ok = False
    report.step(ok, "extreme finite values stay finite", f"exit {code}")


def chaos(box: Path, report: Report) -> None:
    """Empty, malformed and hostile input, plus a legacy output encoding."""
    code, _, err = run_cli(box, "stats", stdin_text="")
    report.step(code == 2 and "Why:" in err and "Fix:" in err,
                "empty input is refused with the triad", f"exit {code}")

    code, _, err = run_cli(box, "stats", "1", "oops")
    report.step(code == 2 and "not a number" in err,
                "a non-numeric token is named", f"exit {code}")

    code, _, err = run_cli(box, "spark", "1", "nan")
    report.step(code == 2 and "finite" in err,
                "a non-finite value is refused", f"exit {code}")

    code, _, err = run_cli(box, "bars", "1", "2", "--width", "1")
    report.step(code == 2 and "--width" in err,
                "an impossible width is refused", f"exit {code}")

    code, _, err = run_cli(box, "hist", "1", "2", "--bins", "0")
    report.step(code == 2 and "--bins" in err,
                "an impossible bin count is refused", f"exit {code}")

    code, _, err = run_cli(box, "box", "1", "2", "--width", "3")
    report.step(code == 2 and "--width" in err,
                "a narrow box width is refused", f"exit {code}")

    code, _, err = run_cli(box, "stats", "-f", "0", "1", "2")
    report.step(code == 2 and "--field" in err,
                "an impossible field index is refused", f"exit {code}")

    code, _, err = run_cli(box, "stats", "-d", "", "1", "2")
    report.step(code == 2 and "--delimiter" in err,
                "an empty delimiter is refused", f"exit {code}")

    code, _, err = run_cli(box, "stats", "--percentiles", "0,50", "1", "2")
    report.step(code == 2 and "percentile" in err,
                "an out-of-range percentile is refused", f"exit {code}")

    code, _, err = run_cli(box, "stats", "--file", str(box / "missing.txt"))
    report.step(code == 1 and "cannot read" in err and "Fix:" in err,
                "a missing file is a runtime error", f"exit {code}")

    code, _, err = run_cli(box, "spark", "1", "--file", "values.txt")
    report.step(code == 2 and "both positional" in err,
                "two input sources are refused", f"exit {code}")

    code, _, err = run_cli(box, "stats", "1e308", "1e308")
    report.step(code == 2 and "sum exceeds" in err and "Fix:" in err,
                "an unrepresentable sum is refused", f"exit {code}")

    code, _, _ = run_cli(box, "stats", "1", "2", "--width", "5")
    report.step(code == 2, "an unknown flag is refused", f"exit {code}")

    code, out, _ = run_cli(box, "spark", "1", "2", "3",
                           extra_env={"PYTHONIOENCODING": "cp1254"})
    report.step(code == 0 and out.isascii(),
                "a legacy pipe encoding falls back to ascii", f"exit {code}")


def main() -> int:
    """Run both tracks in one sandbox and print at most 15 lines."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        before = fingerprint()
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"GAUGE DOGFOOD: cannot start ({exc}).")
        print("Why: the runner proves the project tree is untouched, which needs a git work tree.")
        print("Fix: run it inside the project's repository with git on PATH.")
        return 2
    report = Report()
    with tempfile.TemporaryDirectory(prefix="gauge-dogfood-") as box_name:
        box = Path(box_name)
        with open(LOG_PATH, "w", encoding="utf-8") as log:
            log.write(f"sandbox={box}\n")
            golden_path(box, report)
            chaos(box, report)
            log.write("\n".join(report.lines) + "\n")
    try:
        untouched = fingerprint() == before
    except (OSError, subprocess.SubprocessError, RuntimeError):
        untouched = False
    report.step(untouched, "the run left the project tree untouched")

    passed = len(report.lines) - len(report.failures)
    print(f"GAUGE DOGFOOD (PRINCIPLE-015): {passed}/{len(report.lines)} steps passed")
    for failure in report.failures[:MAX_REPORT_LINES - 4]:
        print(f"  [FAIL] {failure}")
    print(f"  full log: {LOG_PATH.relative_to(ROOT).as_posix()}")
    if report.failures:
        print("  Why: the product must work and refuse bad input before it ships.")
        print("  Fix: read the log, fix the failing step, then rerun this command.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
