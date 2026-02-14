# Proof by Output

理解は、アウトプットで証明する。  
説明文（60文字以上）を入力すると、診断タグ・改善提案・30秒説明を返すCLIツールです。

## Features
- 60文字以上の説明文チェック
- 診断タグ（論点 / 根拠 / 具体 / 手順 / 留意 / 用語）
- 改善版説明と30秒説明を生成
- 結果を `outputs/*.json` に保存

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt