#!/bin/bash

# bunsui Release Script
# 使用方法: ./scripts/release.sh <version>

set -e

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 引数チェック
if [ $# -eq 0 ]; then
    log_error "バージョン番号を指定してください"
    echo "使用方法: $0 <version>"
    echo "例: $0 1.0.0"
    exit 1
fi

VERSION=$1

# バージョン形式チェック
if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "バージョン番号は semver 形式である必要があります (例: 1.0.0)"
    exit 1
fi

log_info "bunsui v$VERSION のリリースを開始します"

# 現在のブランチチェック
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    log_warning "現在のブランチは '$CURRENT_BRANCH' です。mainブランチで実行することを推奨します。"
    read -p "続行しますか? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "リリースをキャンセルしました"
        exit 1
    fi
fi

# 作業ディレクトリの変更をチェック
if [ -n "$(git status --porcelain)" ]; then
    log_error "作業ディレクトリに未コミットの変更があります"
    git status --short
    exit 1
fi

# 最新の変更を取得
log_info "最新の変更を取得中..."
git fetch origin
git pull origin main

# テストの実行
log_info "テストを実行中..."
python -m pytest --cov=bunsui --cov-report=term-missing

# コード品質チェック
log_info "コード品質チェックを実行中..."
flake8 src/ tests/
black --check src/ tests/
isort --check-only src/ tests/
mypy src/

# セキュリティチェック
log_info "セキュリティチェックを実行中..."
safety check
bandit -r src/

# バージョン更新
log_info "バージョンを $VERSION に更新中..."
python -c "
import re
with open('pyproject.toml', 'r') as f:
    content = f.read()
content = re.sub(r'version = \"[^\"]+\"', 'version = \"$VERSION\"', content)
with open('pyproject.toml', 'w') as f:
    f.write(content)
"

# CHANGELOGの更新
log_info "CHANGELOGを更新中..."
if [ ! -f "CHANGELOG.md" ]; then
    cat > CHANGELOG.md << EOF
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [$VERSION] - $(date +%Y-%m-%d)

### Added
- Initial release

### Changed

### Deprecated

### Removed

### Fixed

### Security

EOF
else
    # 既存のCHANGELOGに新しいバージョンを追加
    sed -i "s/## \[Unreleased\]/## [$VERSION] - $(date +%Y-%m-%d)\n\n### Added\n- \n\n### Changed\n\n### Deprecated\n\n### Removed\n\n### Fixed\n\n### Security\n\n## [Unreleased]/" CHANGELOG.md
fi

# 変更をコミット
log_info "変更をコミット中..."
git add pyproject.toml CHANGELOG.md
git commit -m "Bump version to $VERSION"

# タグを作成
log_info "タグ v$VERSION を作成中..."
git tag -a "v$VERSION" -m "Release version $VERSION"

# パッケージをビルド
log_info "パッケージをビルド中..."
python -m build

# ビルド結果をチェック
log_info "ビルド結果をチェック中..."
twine check dist/*

# リモートにプッシュ
log_info "リモートにプッシュ中..."
git push origin main
git push origin "v$VERSION"

log_success "リリース v$VERSION が完了しました！"
log_info "以下の手順でリリースを確認してください："
echo "1. GitHub Actions の実行状況を確認: https://github.com/your-org/bunsui/actions"
echo "2. リリースページを確認: https://github.com/your-org/bunsui/releases"
echo "3. PyPI への公開を確認: https://pypi.org/project/bunsui/"

# リリースノートの表示
log_info "リリースノート:"
echo "---"
git log --oneline $(git describe --tags --abbrev=0 HEAD^)..HEAD
echo "---" 