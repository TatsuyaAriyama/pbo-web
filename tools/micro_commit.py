#!/usr/bin/env python3
"""
micro_commit.py
- Small, meaningful commits helper for Git repositories.
- Goal: keep each commit around 3-10 changed lines (configurable).

Usage:
  python tools/micro_commit.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# ===== Config =====
MIN_LINES = 3
MAX_LINES = 10


@dataclass
class Hunk:
    file_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    body: List[str]

    @property
    def added(self) -> int:
        return sum(1 for ln in self.body if ln.startswith("+") and not ln.startswith("+++"))

    @property
    def removed(self) -> int:
        return sum(1 for ln in self.body if ln.startswith("-") and not ln.startswith("---"))

    @property
    def changed(self) -> int:
        return self.added + self.removed


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def ensure_git_repo() -> None:
    try:
        run(["git", "rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError:
        print("❌ Gitリポジトリ内で実行してください。")
        sys.exit(1)


def get_current_branch() -> str:
    p = run(["git", "branch", "--show-current"])
    return p.stdout.strip()


def parse_unified_diff(diff_text: str) -> List[Hunk]:
    hunks: List[Hunk] = []
    current_file = ""
    lines = diff_text.splitlines()

    hunk_header_re = re.compile(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            # e.g. diff --git a/path b/path
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3]
                current_file = b_path[2:] if b_path.startswith("b/") else b_path
            i += 1
            continue

        m = hunk_header_re.match(line)
        if m:
            old_start = int(m.group(1))
            old_count = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_count = int(m.group(4) or "1")

            body: List[str] = []
            i += 1
            while i < len(lines):
                if lines[i].startswith("diff --git ") or hunk_header_re.match(lines[i]):
                    break
                body.append(lines[i])
                i += 1

            hunks.append(
                Hunk(
                    file_path=current_file,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    body=body,
                )
            )
            continue

        i += 1

    return hunks


def get_working_diff() -> str:
    # --unified=3 keeps hunks readable
    p = run(["git", "diff", "--unified=3"], check=True)
    return p.stdout


def show_hunk_preview(h: Hunk, max_lines: int = 24) -> str:
    preview_lines = h.body[:max_lines]
    suffix = "\n... (truncated) ..." if len(h.body) > max_lines else ""
    header = (
        f"file: {h.file_path}\n"
        f"@@ -{h.old_start},{h.old_count} +{h.new_start},{h.new_count} @@\n"
        f"changed: +{h.added} / -{h.removed} / total={h.changed}\n"
    )
    return header + "\n".join(preview_lines) + suffix


def stage_file_patch_interactive(file_path: str) -> None:
    # Delegate exact hunk selection to git's safe interactive patch mode.
    # User can split hunks with 's', stage with 'y', skip with 'n'.
    print(f"\n🧩 {file_path} のパッチ選択を開始します")
    print("   ヒント: y=stage / n=skip / s=split / q=quit\n")
    # Using subprocess.call to allow interactive tty behavior
    code = subprocess.call(["git", "add", "-p", "--", file_path])
    if code != 0:
        print(f"⚠️ git add -p が中断されました（code={code}）")


def get_staged_numstat() -> List[Tuple[int, int, str]]:
    p = run(["git", "diff", "--cached", "--numstat"])
    rows = []
    for line in p.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) != 3:
            continue
        add_s, del_s, path = cols
        try:
            adds = int(add_s)
            dels = int(del_s)
        except ValueError:
            continue
        rows.append((adds, dels, path))
    return rows


def staged_total_changed() -> int:
    return sum(a + d for a, d, _ in get_staged_numstat())


def has_staged_changes() -> bool:
    p = run(["git", "diff", "--cached", "--name-only"])
    return bool(p.stdout.strip())


def commit_and_push() -> None:
    msg = input("\n📝 コミットメッセージを入力してください: ").strip()
    if not msg:
        print("❌ メッセージが空です。中止します。")
        return

    run(["git", "commit", "-m", msg], check=True)
    branch = get_current_branch() or "main"
    run(["git", "push", "-u", "origin", branch], check=True)
    print(f"✅ push 完了: origin/{branch}")


def main() -> None:
    ensure_git_repo()

    diff_text = get_working_diff()
    if not diff_text.strip():
        print("✅ 変更がありません。")
        return

    hunks = parse_unified_diff(diff_text)
    if not hunks:
        print("ℹ️ 差分解析対象の hunk が見つかりませんでした。")
        return

    print(f"\n検出 hunk 数: {len(hunks)}")
    print(f"推奨: 1コミット {MIN_LINES}〜{MAX_LINES} 行前後\n")

    # Group by file for practical interactive staging
    files = sorted({h.file_path for h in hunks if h.file_path})
    for f in files:
        fhunks = [h for h in hunks if h.file_path == f]
        total = sum(h.changed for h in fhunks)
        mark = "✅" if MIN_LINES <= total <= MAX_LINES else "⚪"
        print(f"{mark} {f} (hunks={len(fhunks)}, approx changed={total})")

    print("\n--- プレビュー（先頭）---")
    for idx, h in enumerate(hunks[:5], start=1):
        print(f"\n[{idx}]")
        print(show_hunk_preview(h))

    print("\n次にファイルごとに `git add -p` を開きます。")
    print("小さな変更（目安3〜10行）だけ `y` でステージしてください。")

    for f in files:
        stage_file_patch_interactive(f)

    if not has_staged_changes():
        print("\nℹ️ ステージされた変更がありません。終了します。")
        return

    total = staged_total_changed()
    print(f"\n📊 ステージ済み変更行数(追加+削除): {total}")
    if total < MIN_LINES or total > MAX_LINES:
        print(f"⚠️ 目安({MIN_LINES}〜{MAX_LINES})から外れています。")
        ans = input("このままコミットしますか？ [y/N]: ").strip().lower()
        if ans != "y":
            print("中止しました。`git restore --staged .` で再調整できます。")
            return

    print("\nステージ内容:")
    for a, d, pth in get_staged_numstat():
        print(f"  - {pth}: +{a} -{d}")

    commit_and_push()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() if e.stderr else str(e)
        print(f"❌ コマンド実行エラー: {err}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n中断しました。")
        sys.exit(130)