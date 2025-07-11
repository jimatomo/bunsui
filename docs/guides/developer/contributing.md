# Contributing to Bunsui

## 開発環境のセットアップ

### 前提条件

- Python 3.8+
- Docker
- Git

### ローカル開発環境の構築

1. リポジトリのクローン

```bash
git clone https://github.com/your-org/bunsui.git
cd bunsui
```

2. 仮想環境の作成

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. 依存関係のインストール

```bash
pip install -e .[dev]
```

4. LocalStackの起動

```bash
cd tests/localstack
docker-compose up -d
```

## 開発ワークフロー

### 1. ブランチの作成

```bash
git checkout -b feature/your-feature-name
```

### 2. コードの実装

- 機能実装
- テストの追加
- ドキュメントの更新

### 3. テストの実行

```bash
# ユニットテスト
pytest tests/unit/

# 統合テスト
pytest tests/integration/

# E2Eテスト
pytest tests/e2e/

# 全テスト
pytest

# カバレッジレポート
pytest --cov=bunsui --cov-report=html
```

### 4. コード品質チェック

```bash
# リンター
flake8 src/
black --check src/
isort --check-only src/

# 型チェック
mypy src/

# セキュリティチェック
bandit -r src/
```

### 5. プルリクエストの作成

```bash
git add .
git commit -m "feat: add new feature"
git push origin feature/your-feature-name
```

## コーディング規約

### Python

- **PEP 8**に準拠
- **Black**でフォーマット
- **isort**でインポート整理
- **mypy**で型チェック

### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/)に準拠：

```
feat: add new feature
fix: fix bug
docs: update documentation
test: add tests
refactor: refactor code
style: format code
chore: maintenance tasks
```

### ドキュメント

- **Google Style**のdocstring
- **Markdown**でドキュメント作成
- **Sphinx**でAPIドキュメント生成

## テスト戦略

### ユニットテスト

- 各モジュールの個別テスト
- モックを使用した外部依存の分離
- カバレッジ90%以上を目標

### 統合テスト

- AWSサービスとの連携テスト
- LocalStackを使用したローカルテスト
- 実際のAWS環境でのテスト

### E2Eテスト

- CLIコマンドのテスト
- パイプライン実行のテスト
- エンドツーエンドのワークフロー

### パフォーマンステスト

- 実行時間の測定
- メモリ使用量の監視
- スケーラビリティの検証

## リリースプロセス

### 1. バージョン管理

[Semantic Versioning](https://semver.org/)に準拠：

- **MAJOR**: 破壊的変更
- **MINOR**: 新機能追加
- **PATCH**: バグ修正

### 2. リリース手順

```bash
# バージョン更新
bumpversion patch  # or minor/major

# テスト実行
pytest

# ドキュメント生成
cd docs && make html

# タグ作成
git tag v1.0.0
git push origin v1.0.0
```

### 3. 配布

```bash
# パッケージビルド
python setup.py sdist bdist_wheel

# PyPIアップロード
twine upload dist/*
```

## トラブルシューティング

### よくある問題

1. **LocalStack接続エラー**
   ```bash
   # LocalStackの状態確認
   docker-compose ps
   
   # ログ確認
   docker-compose logs localstack
   ```

2. **テスト失敗**
   ```bash
   # 詳細なテスト実行
   pytest -v -s
   
   # 特定のテストのみ実行
   pytest tests/unit/test_specific.py::test_function
   ```

3. **依存関係の問題**
   ```bash
   # 依存関係の更新
   pip install --upgrade -e .[dev]
   
   # キャッシュクリア
   pip cache purge
   ```

## 貢献の種類

### バグ報告

- 再現手順の詳細記述
- 期待される動作の説明
- 環境情報の提供

### 機能要望

- ユースケースの説明
- 実装案の提案
- 優先度の明示

### ドキュメント改善

- 不明瞭な箇所の指摘
- サンプルコードの追加
- 翻訳の提供

### コード改善

- パフォーマンス最適化
- セキュリティ強化
- コード品質向上

## コミュニティ

- **Issues**: バグ報告・機能要望
- **Discussions**: 技術的な議論
- **Pull Requests**: コード貢献
- **Wiki**: 追加ドキュメント

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。 