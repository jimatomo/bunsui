#!/bin/bash

# Bunsui Code Check Script
# コード修正後の動作確認前チェックを自動化

set -e  # エラーが発生したら即座に終了

# 色付き出力のための関数
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "\033[34m[INFO]\033[0m $message"
            ;;
        "SUCCESS")
            echo -e "\033[32m[SUCCESS]\033[0m $message"
            ;;
        "WARNING")
            echo -e "\033[33m[WARNING]\033[0m $message"
            ;;
        "ERROR")
            echo -e "\033[31m[ERROR]\033[0m $message"
            ;;
    esac
}

# ヘルプ表示
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help         このヘルプを表示"
    echo "  -f, --format       コードフォーマットのみ実行"
    echo "  -l, --lint         リントチェックのみ実行"
    echo "  -t, --type-check   型チェックのみ実行"
    echo "  -u, --test         テストのみ実行"
    echo "  -a, --all          すべてのチェックを実行（デフォルト）"
    echo "  -q, --quick        クイックチェック（フォーマット + リント + 型チェック）"
    echo "  -v, --verbose      詳細出力"
    echo ""
    echo "Examples:"
    echo "  $0                 # すべてのチェックを実行"
    echo "  $0 --quick         # クイックチェック"
    echo "  $0 --format        # フォーマットのみ"
}

# 変数初期化
VERBOSE=false
RUN_FORMAT=false
RUN_LINT=false
RUN_TYPE_CHECK=false
RUN_TEST=false
RUN_ALL=true

# コマンドライン引数の解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -f|--format)
            RUN_FORMAT=true
            RUN_ALL=false
            shift
            ;;
        -l|--lint)
            RUN_LINT=true
            RUN_ALL=false
            shift
            ;;
        -t|--type-check)
            RUN_TYPE_CHECK=true
            RUN_ALL=false
            shift
            ;;
        -u|--test)
            RUN_TEST=true
            RUN_ALL=false
            shift
            ;;
        -a|--all)
            RUN_ALL=true
            shift
            ;;
        -q|--quick)
            RUN_FORMAT=true
            RUN_LINT=true
            RUN_TYPE_CHECK=true
            RUN_ALL=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# プロジェクトルートディレクトリの確認
if [[ ! -f "pyproject.toml" ]]; then
    print_status "ERROR" "pyproject.tomlが見つかりません。プロジェクトルートディレクトリで実行してください。"
    exit 1
fi

print_status "INFO" "Bunsui Code Check を開始します..."

# 開始時間を記録
START_TIME=$(date +%s)

# コードフォーマット
if [[ "$RUN_ALL" == true || "$RUN_FORMAT" == true ]]; then
    print_status "INFO" "コードフォーマットを実行中..."
    if make format; then
        print_status "SUCCESS" "コードフォーマットが完了しました"
    else
        print_status "ERROR" "コードフォーマットでエラーが発生しました"
        exit 1
    fi
fi

# リントチェック
if [[ "$RUN_ALL" == true || "$RUN_LINT" == true ]]; then
    print_status "INFO" "リントチェックを実行中..."
    if make lint; then
        print_status "SUCCESS" "リントチェックが完了しました"
    else
        print_status "ERROR" "リントチェックでエラーが発生しました"
        exit 1
    fi
fi

# 型チェック
if [[ "$RUN_ALL" == true || "$RUN_TYPE_CHECK" == true ]]; then
    print_status "INFO" "型チェックを実行中..."
    if make type-check; then
        print_status "SUCCESS" "型チェックが完了しました"
    else
        print_status "ERROR" "型チェックでエラーが発生しました"
        exit 1
    fi
fi

# テスト実行
if [[ "$RUN_ALL" == true || "$RUN_TEST" == true ]]; then
    print_status "INFO" "テストを実行中..."
    if make test-cov; then
        print_status "SUCCESS" "テストが完了しました"
    else
        print_status "ERROR" "テストでエラーが発生しました"
        exit 1
    fi
fi

# 終了時間を計算
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

print_status "SUCCESS" "すべてのチェックが完了しました！"
print_status "INFO" "実行時間: ${DURATION}秒"

# 詳細出力が有効な場合、追加情報を表示
if [[ "$VERBOSE" == true ]]; then
    echo ""
    print_status "INFO" "詳細情報:"
    echo "  - プロジェクト: $(grep '^name =' pyproject.toml | cut -d'"' -f2)"
    echo "  - バージョン: $(grep '^version =' pyproject.toml | cut -d'"' -f2)"
    echo "  - Python要件: $(grep '^requires-python =' pyproject.toml | cut -d'"' -f2)"
fi

print_status "INFO" "動作確認の準備が整いました！" 