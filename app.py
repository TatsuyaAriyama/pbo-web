import os
import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# Config
# =========================
APP_NAME = "Proof by Output"
MIN_CHARS = 60
HISTORY_LIMIT = 50

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
- JSONの外に一切文字を書かない
- tags は上記6タグから最大3つ選ぶ
- score は 0〜100 の整数
- improve_tips は少なくとも1件、最大3件
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
client = OpenAI(api_key=api_key) if api_key else None

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# Utility
# =========================
def count_chars(text: str) -> int:
    return len(text)


def safe_filename(text: str, max_len: int = 40) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = text.strip("_")
    return (text[:max_len] or "topic")


def score_to_rank(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def rank_comment(rank: str) -> str:
    comments = {
        "S": "説明が明確で再現性も高いです。実務で通用するレベル。",
        "A": "十分に明快です。根拠か具体例を1段深めるとSに届きます。",
        "B": "要点は伝わっています。順序と具体性を補強すると伸びます。",
        "C": "方向性は良いです。定義→理由→例の型で組み立てると改善します。",
        "D": "まずは論点を1つに絞り、短く具体的に説明してみましょう。",
    }
    return comments.get(rank, "")


def validate_input(topic: str, explanation: str) -> tuple[bool, str]:
    if not topic:
        return False, "トピック名は必須です。例: TypeScriptのUnion型"

    char_count = count_chars(explanation)
    if char_count < MIN_CHARS:
        remain = MIN_CHARS - char_count
        return (
            False,
            f"説明文は{MIN_CHARS}文字以上必要です（現在{char_count}文字、あと{remain}文字）。\n"
            "ヒント: 『〜とは』『なぜ使うか』『具体例』の3点を書くと到達しやすいです。"
        )

    if not api_key:
        return False, "OPENAI_API_KEY が見つかりません。.env または環境変数を確認してください。"

    return True, ""


def evaluate(topic: str, explanation: str) -> dict:
    """
    モデルの利用可否差分やJSON崩れに強い実装:
    - 利用可能モデルへフォールバック
    - response_format=json_object でJSON強制
    """
    if client is None:
        raise RuntimeError("OpenAI client が初期化されていません。OPENAI_API_KEY を確認してください。")

    user_prompt = f"""
[トピック]
{topic}

[説明文]
{explanation}
"""

    model_candidates = [
        "gpt-4o-mini",
        "gpt-4.1-mini",
    ]

    last_err = None
    for model_name in model_candidates:
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = res.choices[0].message.content
            data = json.loads(content)

            # 最低限の防御（キーがない時でも落ちにくくする）
            data.setdefault("score", 0)
            data.setdefault("strengths", [])
            data.setdefault("tags", [])
            data.setdefault("improve_tips", [])
            data.setdefault("improved_explanation", "")
            data.setdefault("explanation_30sec", "")

            return data
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"AI呼び出しに失敗しました: {last_err}")


def save_record(topic: str, explanation: str, result: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = safe_filename(topic)
    path = OUTPUT_DIR / f"{ts}_{name}.json"

    score = result.get("score")
    rank = score_to_rank(score) if isinstance(score, int) else None

    payload = {
        "app": APP_NAME,
        "created_at": datetime.now().isoformat(),
        "topic": topic,
        "explanation": explanation,
        "char_count": count_chars(explanation),
        "score": score,
        "rank": rank,
        "result": result,
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return path


def load_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    files = sorted(OUTPUT_DIR.glob("*.json"), reverse=True)[:limit]
    records = []
    for p in files:
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # 旧データ互換
            if "score" not in data:
                data["score"] = data.get("result", {}).get("score")
            if "rank" not in data and isinstance(data.get("score"), int):
                data["rank"] = score_to_rank(data["score"])

            data["_file"] = str(p)
            records.append(data)
        except Exception:
            continue
    return records


def find_previous_same_topic_score(topic: str, current_created_at: str | None = None) -> int | None:
    """
    同一トピックの直近過去スコアを返す。
    current_created_at がある場合は、それより前の記録のみを対象にする。
    """
    records = load_history(limit=500)
    same_topic = [r for r in records if r.get("topic") == topic and isinstance(r.get("score"), int)]

    if current_created_at:
        same_topic = [r for r in same_topic if (r.get("created_at", "") < current_created_at)]

    if not same_topic:
        return None

    # load_historyは新しい順なので先頭が直近
    return same_topic[0].get("score")


def render_diagnosis_result(result: dict, topic: str | None = None, created_at: str | None = None):
    st.subheader("診断結果")

    score = result.get("score", None)
    if isinstance(score, int):
        rank = score_to_rank(score)

        delta_text = "比較対象なし"
        if topic:
            prev = find_previous_same_topic_score(topic=topic, current_created_at=created_at)
            if isinstance(prev, int):
                diff = score - prev
                sign = "+" if diff >= 0 else ""
                delta_text = f"{sign}{diff}（前回 {prev}）"

        c1, c2, c3 = st.columns(3)
        c1.metric("スコア", f"{score} / 100")
        c2.metric("ランク", rank)
        c3.metric("前回比（同一トピック）", delta_text)
        st.caption(rank_comment(rank))
    else:
        st.metric("スコア", "N/A")

    strengths = result.get("strengths", [])
    if strengths:
        st.markdown("### 良い点")
        for s in strengths:
            st.markdown(f"- {s}")

    tags = result.get("tags", [])
    if tags:
        st.markdown("### 検知タグ")
        for t in tags:
            st.markdown(f"- **{t.get('name', '')}**：{t.get('description', '')}")
            advice = t.get("advice", "")
            if advice:
                st.markdown(f"  - 改善: {advice}")

    tips = result.get("improve_tips", [])
    if tips:
        st.markdown("### 改善提案")
        for tip in tips:
            st.markdown(f"- {tip}")

    st.markdown("### 改善版説明")
    st.write(result.get("improved_explanation", ""))

    st.markdown("### 30秒説明")
    st.write(result.get("explanation_30sec", ""))


# =========================
# UI
# =========================
st.set_page_config(page_title=APP_NAME, page_icon="🧠", layout="centered")
st.title(APP_NAME)
st.caption("理解は、アウトプットで証明する。")

mode = st.sidebar.radio("メニュー", ["診断", "履歴"], index=0)

if mode == "診断":
    topic = st.text_input("トピック名", placeholder="例: TypeScriptのUnion型 / HTTP 404と500の違い")
    explanation = st.text_area(
        "説明文（60文字以上）",
        placeholder="ここに自分の説明を書いてください。",
        height=220,
    )

    chars = count_chars(explanation)
    status = "✅ OK" if chars >= MIN_CHARS else "⚠️ まだ不足"
    st.write(f"文字数: **{chars}** / 最低 **{MIN_CHARS}**  ({status})")

    if st.button("診断する", type="primary"):
        ok, msg = validate_input(topic, explanation)
        if not ok:
            st.warning(msg)
        else:
            try:
                with st.spinner("診断中..."):
                    result = evaluate(topic, explanation)

                # 診断直後表示用に現在時刻を渡す（過去比較フィルタ用）
                current_created_at = datetime.now().isoformat()
                render_diagnosis_result(result, topic=topic, created_at=current_created_at)

                save_path = save_record(topic, explanation, result)
                st.success(f"結果を保存しました: {save_path}")

            except json.JSONDecodeError as e:
                st.error(f"AI応答のJSON解析に失敗しました: {e}")
            except Exception as e:
                st.error(f"エラーが発生しました: {type(e).__name__}: {e}")

else:
    st.subheader("診断履歴")
    records = load_history(limit=HISTORY_LIMIT)

    if not records:
        st.info("まだ履歴がありません。診断を実行するとここに表示されます。")
    else:
        for i, rec in enumerate(records, start=1):
            topic = rec.get("topic", "(no topic)")
            created = rec.get("created_at", "")
            score = rec.get("score", rec.get("result", {}).get("score", "N/A"))
            rank = rec.get("rank", score_to_rank(score) if isinstance(score, int) else "-")
            char_count = rec.get("char_count", 0)

            with st.expander(f"{i}. {topic} | rank: {rank} | score: {score} | {created}"):
                st.write(f"文字数: {char_count}")
                st.write(f"ファイル: {rec.get('_file', '')}")

                st.markdown("**入力説明文**")
                st.write(rec.get("explanation", ""))

                st.markdown("**診断結果**")
                render_diagnosis_result(
                    rec.get("result", {}),
                    topic=rec.get("topic"),
                    created_at=rec.get("created_at"),
                )