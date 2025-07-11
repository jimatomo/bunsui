# Bunsui Code Check Scripts

コード修正後の動作確認前チェックを自動化するスクリプト群です。

## 概要

これらのスクリプトは、コードを修正した後に動作確認を行う前に、以下のチェックを自動的に実行します：

- **コードフォーマット** (black, isort)
- **リントチェック** (flake8)
- **型チェック** (mypy)
- **テスト実行** (pytest)

## 利用可能なスクリプト

### 1. Bash スクリプト (`check-code.sh`)

```bash
# 基本的な使用方法
./scripts/check-code.sh

# オプション付き
./scripts/check-code.sh --quick    # クイックチェック（テストなし）
./scripts/check-code.sh --format   # フォーマットのみ
./scripts/check-code.sh --verbose  # 詳細出力付き
```

### 2. Python スクリプト (`check_code.py`)

```bash
# 基本的な使用方法
python scripts/check_code.py

# オプション付き
python scripts/check_code.py --quick    # クイックチェック（テストなし）
python scripts/check_code.py --format   # フォーマットのみ
python scripts/check_code.py --verbose  # 詳細出力付き
```

### 3. Makefile ターゲット

```bash
# 包括的なチェック（フォーマット + リント + 型チェック + テスト）
make check-code

# クイックチェック（フォーマット + リント + 型チェック）
make check-quick
```

## オプション一覧

| オプション | 説明 |
|-----------|------|
| `--all` | すべてのチェックを実行（デフォルト） |
| `--quick` | クイックチェック（フォーマット + リント + 型チェック） |
| `--format` | コードフォーマットのみ実行 |
| `--lint` | リントチェックのみ実行 |
| `--type-check` | 型チェックのみ実行 |
| `--test` | テストのみ実行 |
| `--verbose` | 詳細出力 |
| `--help` | ヘルプを表示 |

## 推奨ワークフロー

### 1. 開発中のクイックチェック

```bash
# コード修正後、すぐにチェック
make check-quick
# または
./scripts/check-code.sh --quick
```

### 2. コミット前の包括的チェック

```bash
# すべてのチェックを実行
make check-code
# または
./scripts/check-code.sh --all
```

### 3. 特定の問題のみチェック

```bash
# 型エラーのみ確認
./scripts/check-code.sh --type-check

# コードスタイルのみ確認
./scripts/check-code.sh --lint
```

## 出力例

```
[INFO] Bunsui Code Check を開始します...
[INFO] コードフォーマットを実行中...
[SUCCESS] コードフォーマットが完了しました
[INFO] リントチェックを実行中...
[SUCCESS] リントチェックが完了しました
[INFO] 型チェックを実行中...
[SUCCESS] 型チェックが完了しました
[INFO] テストを実行中...
[SUCCESS] テストが完了しました
[SUCCESS] すべてのチェックが完了しました！
[INFO] 実行時間: 45秒
[INFO] 動作確認の準備が整いました！
```

## エラーハンドリング

- エラーが発生した場合、スクリプトは即座に終了します
- 詳細出力モード（`--verbose`）では、エラーの詳細情報も表示されます
- 各チェックは独立して実行され、一つでも失敗すると全体が失敗します

## 注意事項

- プロジェクトルートディレクトリ（`pyproject.toml`がある場所）で実行してください
- 開発環境のセットアップ（`make install-dev`）が完了している必要があります
- スクリプトは既存のMakefileターゲットを利用しているため、Makefileが正しく設定されている必要があります

## トラブルシューティング

### よくある問題

1. **権限エラー**
   ```bash
   chmod +x scripts/check-code.sh
   chmod +x scripts/check_code.py
   ```

2. **依存関係エラー**
   ```bash
   make install-dev
   ```

3. **プロジェクトルートエラー**
   - `pyproject.toml`があるディレクトリで実行してください

4. **Makefileターゲットエラー**
   - Makefileが正しく設定されているか確認してください
   - `make help`で利用可能なターゲットを確認してください 