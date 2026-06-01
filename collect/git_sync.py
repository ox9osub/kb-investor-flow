"""data 브랜치 worktree에서 add/commit/push 수행.

멱등성: 'nothing to commit' 케이스는 정상 종료.
"""
import subprocess
from pathlib import Path


def commit_and_push(repo_dir: Path, relpath: "str | list[str]", message: str) -> None:
    paths = [relpath] if isinstance(relpath, str) else list(relpath)
    _run(["git", "add", *paths], cwd=repo_dir)

    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if commit.returncode != 0:
        combined = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in combined or "no changes added" in combined:
            return
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    _run(["git", "push", "origin", "HEAD"], cwd=repo_dir)


def _run(args: list[str], cwd: Path) -> None:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"git command failed ({' '.join(args)}): {res.stderr.strip()}"
        )
