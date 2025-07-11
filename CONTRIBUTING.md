# Contributing to bunsui

bunsuiプロジェクトへの貢献をありがとうございます！このドキュメントでは、プロジェクトへの貢献方法について説明します。

## 開発環境のセットアップ

### 前提条件

- Python 3.8以上
- Git
- Docker（統合テスト用）

### セットアップ手順

1. リポジトリをクローン
```bash
git clone https://github.com/your-org/bunsui.git
cd bunsui
```

2. 仮想環境を作成
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# または
venv\Scripts\activate  # Windows
```

3. 依存関係をインストール
```bash
pip install -e .[dev]
```

4. 開発用ツールをインストール
```bash
pip install pre-commit
pre-commit install
```

## 開発ワークフロー

### 1. ブランチ戦略

- `main`: 本番リリース用ブランチ
- `develop`: 開発用ブランチ
- `feature/*`: 新機能開発用ブランチ
- `bugfix/*`: バグ修正用ブランチ
- `hotfix/*`: 緊急修正用ブランチ

### 2. 開発手順

1. 新しいブランチを作成
```bash
git checkout -b feature/your-feature-name
```

2. 変更を実装

3. テストを実行
```bash
pytest
pytest --cov=bunsui
```

4. コード品質チェック
```bash
flake8 src/ tests/
black src/ tests/
isort src/ tests/
mypy src/
```

5. コミット
```bash
git add .
git commit -m "feat: add new feature"
```

6. プッシュ
```bash
git push origin feature/your-feature-name
```

7. プルリクエストを作成

### 3. コミットメッセージ規約

[Conventional Commits](https://www.conventionalcommits.org/)に従います：

- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメントのみの変更
- `style`: コードの意味に影響しない変更（空白、フォーマット等）
- `refactor`: バグ修正や機能追加ではないコードの変更
- `test`: テストの追加や修正
- `chore`: ビルドプロセスや補助ツールの変更

例：
```
feat: add pipeline validation feature
fix: resolve authentication token issue
docs: update installation guide
```

## テスト

### テストの実行

```bash
# 全テストを実行
pytest

# カバレッジ付きで実行
pytest --cov=bunsui --cov-report=html

# 特定のテストファイルを実行
pytest tests/unit/test_pipeline.py

# 統合テストを実行
pytest tests/integration/

# E2Eテストを実行
pytest tests/e2e/
```

### テストカバレッジ

- 目標: 90%以上
- 新機能は必ずテストを作成
- バグ修正時は回帰テストを追加

## コード品質

### リンター

- **flake8**: PEP8準拠のチェック
- **black**: コードフォーマット
- **isort**: import文の整理
- **mypy**: 型チェック

### セキュリティ

- **bandit**: セキュリティ脆弱性の検出
- **safety**: 依存関係の脆弱性チェック

## ドキュメント

### ドキュメントの更新

1. コード変更時は関連するドキュメントも更新
2. API変更時は必ずドキュメントを更新
3. 新機能追加時は使用例を追加

### ドキュメントのビルド

```bash
cd docs
make html
```

## リリースプロセス

### リリース手順

1. バージョン番号を決定（Semantic Versioning）
2. CHANGELOG.mdを更新
3. リリーススクリプトを実行
```bash
./scripts/release.sh 1.0.0
```

### リリースチェックリスト

- [ ] 全テストが通る
- [ ] コード品質チェックが通る
- [ ] セキュリティスキャンが通る
- [ ] ドキュメントが最新
- [ ] CHANGELOGが更新済み
- [ ] バージョン番号が正しい

## 問題報告

### バグ報告

1. GitHub Issuesでバグを報告
2. 再現手順を詳細に記載
3. 環境情報を記載（OS、Pythonバージョン等）
4. エラーログを添付

### 機能要求

1. GitHub Issuesで機能要求を報告
2. ユースケースを明確に説明
3. 期待する動作を記載

## コミュニティ

### 行動規範

- 建設的なフィードバックを提供
- 他者の貢献を尊重
- プロフェッショナルな態度を保つ

### サポート

- GitHub Issues: バグ報告・機能要求
- GitHub Discussions: 質問・議論
- ドキュメント: 使用方法・APIリファレンス

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。貢献する際は、このライセンスに同意したものとみなされます。

---

ご質問やご提案がございましたら、お気軽にGitHub Issuesでお知らせください。 