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
## Quick Run
```bash
python -m streamlit run web_app.py
$EOF

## Roadmap
- [ ] Topic-specific previous-score comparison
- [ ] Team login support
- [ ] Dashboard for tag trends
- Usage: Enter topic + 60+ chars, then click 診断する.
cat >> README.md << 'EOF'

## FAQ

- Q. 何文字から診断できますか？
  - A. 60文字以上です。
- Q. 結果はどこに保存されますか？
  - A. `outputs/*.json` に保存されます。
EOF

git add README.md
git commit -m "docs: add FAQ section"
git push
cat >> README.md << 'EOF'

## Usage Tips

- 「定義 / なぜ使うか / 具体例」の3点を書くと精度が上がります。
- 1トピックを繰り返し説明して、改善版との差分を見るのがおすすめです。
EOF

git add README.md
git commit -m "docs: add usage tips"
git push
cat >> README.md << 'EOF'

## Version

- v0.1.0: Streamlit UI + AI診断 + 履歴保存
EOF

git add README.md
git commit -m "docs: add version note"
git push
cat >> README.md << 'EOF'

## Changelog
EOF

git add README.md
git commit -m "docs: add changelog header"
git push
echo "- 2026-02-15: improved README structure." >> README.md

git add README.md
git commit -m "docs: add changelog entry for README"
git push
cat >> README.md << 'EOF'

## Notes
EOF

git add README.md
git commit -m "docs: add notes header"
git push
echo "- Keep commits small and meaningful." >> README.md

git add README.md
git commit -m "docs: add workflow note"
git push
echo "- Next: deploy to Render and share internal URL." >> README.md

git add README.md
git commit -m "docs: add next action note"
git push## Changelog
