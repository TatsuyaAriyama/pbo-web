import os
import re
import json
import sys
import locale
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# =========================
# UTF-8対策（日本語入力・出力）
# =========================
try:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    pass
# =========================
# Config
# =========================
APP_NAME = "Proof by Output"
MIN_CHARS = 60

TAGS = [
    {"name": "論点", "description": "何について話しているかが曖昧"},
    {"name": "根拠", "description": "なぜそう言えるかの理由が不足"},
    {"name": "具体", "description": "具体例やケースが不足"},
    {"name": "手順", "description": "説明の順序や進め方が不明瞭"},
    {"name": "留意", "description": "注意点・制約・例外条件が不足"},
    {"name": "用語", "description": "専門用語の説明が不足"},
]

TAG_TEXT = "\n".join([f"- {t['name']}：{t['description']}" for t in TAGS])

SYSTEM_PROMPT = f"""
あなたは学習内容の説明文を診断するコーチです。
ユーザーの説明文を評価し、つまずきタグを返します。

# つまずきタグ定義
{TAG_TEXT}

# 出力ルール
- 必ず日本語
- 必ずJSONのみ（前置き・補足文は禁止）
- tags は上記6タグから最大3つ選ぶ
- score は 0〜100 の整数
- improve_tips は短く具体的に3件以内
- improved_explanation は200〜320文字
- explanation_30sec は80〜140文字

# JSONスキーマ
{{
  "score": 0,
  "strengths": ["..."],
  "tags": [
    {{
      "name": "論点",
      "description": "何について話しているかが曖昧",
      "advice": "改善方法を1文"
    }}
  ],
  "improve_tips": ["..."],
  "improved_explanation": "...",
  "explanation_30sec": "..."
}}
"""
# =========================
# Setup
# =========================
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY が見つかりません。.env を確認してください。")

client = OpenAI(api_key=api_key)
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def count_chars(text: str) -> int:
    # 改行や空白込みでカウント
    return len(text)


def safe_filename(text: str, max_len: int = 40) -> str:
    """
    保存ファイル名を安全なASCIIへ寄せる
    例:
      "githubについて" -> "github"
      "TypeScript Union型" -> "typescript_union"
      （英数が無ければ topic）
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = text.strip("_")
    return (text[:max_len] or "topic")


def input_multiline(prompt: str) -> str:
    print(prompt)
    print("入力後、空行で終了（Enterを2回）")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def validate_input(topic: str, explanation: str) -> tuple[bool, str]:
    if not topic:
        return False, "トピック名は必須です。"
    char_count = count_chars(explanation)
    if char_count < MIN_CHARS:
        remain = MIN_CHARS - char_count
        return False, f"説明文は{MIN_CHARS}文字以上必要です（現在{char_count}文字、あと{remain}文字）。"
    return True, ""


def evaluate(topic: str, explanation: str) -> dict:
    user_prompt = f"""