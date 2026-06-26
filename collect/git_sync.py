"""data 브랜치 worktree에서 add/commit/push 수행.

멱등성: 'nothing to commit' 케이스는 정상 종료.
인증 실패시 대화형 프롬프트(브라우저 팝업/credential manager)가 떠서
다음 분 수집을 막지 않도록 GIT_TERMINAL_PROMPT=0 강제.
"""
import os
import subprocess
from pathlib import Path


def _git_env() -> dict:
    """대화형 인증 프롬프트 차단 — 401이면 즉시 실패하고 다음 사이클로."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"  # Git Credential Manager (Windows)
    return env


def commit_and_push(repo_dir: Path, relpath: "str | list[str]", message: str) -> None:
    paths = [relpath] if isinstance(relpath, str) else list(relpath)
    _run(["git", "add", *paths], cwd=repo_dir)

    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_dir, capture_output=True, text=True, env=_git_env(),
    )
    if commit.returncode != 0:
        combined = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in combined or "no changes added" in combined:
            return
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    _run(["git", "push", "origin", "HEAD"], cwd=repo_dir)


def _run(args: list[str], cwd: Path) -> None:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=_git_env())
    if res.returncode != 0:
        raise RuntimeError(
            f"git command failed ({' '.join(args)}): {res.stderr.strip()}"
        )
