#!/usr/bin/env python3
"""
Bunsui Code Check Script (Python Version)
コード修正後の動作確認前チェックを自動化
"""

import argparse
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import List, Dict, Any


class ColorOutput:
    """色付き出力のためのクラス"""
    
    @staticmethod
    def info(message: str) -> None:
        print(f"\033[34m[INFO]\033[0m {message}")
    
    @staticmethod
    def success(message: str) -> None:
        print(f"\033[32m[SUCCESS]\033[0m {message}")
    
    @staticmethod
    def warning(message: str) -> None:
        print(f"\033[33m[WARNING]\033[0m {message}")
    
    @staticmethod
    def error(message: str) -> None:
        print(f"\033[31m[ERROR]\033[0m {message}")


class CodeChecker:
    """コードチェックを実行するクラス"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path.cwd()
        self.start_time = None
        
    def check_project_root(self) -> bool:
        """プロジェクトルートディレクトリかどうかを確認"""
        pyproject_toml = self.project_root / "pyproject.toml"
        if not pyproject_toml.exists():
            ColorOutput.error("pyproject.tomlが見つかりません。プロジェクトルートディレクトリで実行してください。")
            return False
        return True
    
    def run_command(self, command: List[str], description: str) -> bool:
        """コマンドを実行し、結果を返す"""
        ColorOutput.info(f"{description}を実行中...")
        
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=not self.verbose,
                text=True,
                cwd=self.project_root
            )
            ColorOutput.success(f"{description}が完了しました")
            return True
        except subprocess.CalledProcessError as e:
            ColorOutput.error(f"{description}でエラーが発生しました")
            if self.verbose and e.stderr:
                print(f"エラー詳細: {e.stderr}")
            return False
    
    def run_format(self) -> bool:
        """コードフォーマットを実行"""
        return self.run_command(["make", "format"], "コードフォーマット")
    
    def run_lint(self) -> bool:
        """リントチェックを実行"""
        return self.run_command(["make", "lint"], "リントチェック")
    
    def run_type_check(self) -> bool:
        """型チェックを実行"""
        return self.run_command(["make", "type-check"], "型チェック")
    
    def run_test(self) -> bool:
        """テストを実行"""
        return self.run_command(["make", "test-cov"], "テスト")
    
    def get_project_info(self) -> Dict[str, str]:
        """プロジェクト情報を取得"""
        pyproject_toml = self.project_root / "pyproject.toml"
        info = {}
        
        try:
            with open(pyproject_toml, 'r') as f:
                content = f.read()
                
            for line in content.split('\n'):
                if line.startswith('name ='):
                    info['name'] = line.split('"')[1]
                elif line.startswith('version ='):
                    info['version'] = line.split('"')[1]
                elif line.startswith('requires-python ='):
                    info['python_requires'] = line.split('"')[1]
                    
        except Exception as e:
            ColorOutput.warning(f"プロジェクト情報の取得に失敗: {e}")
            
        return info
    
    def run_checks(self, checks: List[str]) -> bool:
        """指定されたチェックを実行"""
        self.start_time = time.time()
        
        ColorOutput.info("Bunsui Code Check を開始します...")
        
        # プロジェクトルートの確認
        if not self.check_project_root():
            return False
        
        # チェックの実行
        check_functions = {
            'format': self.run_format,
            'lint': self.run_lint,
            'type-check': self.run_type_check,
            'test': self.run_test,
        }
        
        for check in checks:
            if check in check_functions:
                if not check_functions[check]():
                    return False
            else:
                ColorOutput.error(f"不明なチェック: {check}")
                return False
        
        # 実行時間の計算
        duration = int(time.time() - self.start_time)
        ColorOutput.success("すべてのチェックが完了しました！")
        ColorOutput.info(f"実行時間: {duration}秒")
        
        # 詳細情報の表示
        if self.verbose:
            info = self.get_project_info()
            if info:
                print()
                ColorOutput.info("詳細情報:")
                for key, value in info.items():
                    print(f"  - {key}: {value}")
        
        ColorOutput.info("動作確認の準備が整いました！")
        return True


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Bunsui Code Check Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                 # すべてのチェックを実行
  %(prog)s --quick         # クイックチェック
  %(prog)s --format        # フォーマットのみ
  %(prog)s --verbose       # 詳細出力付き
        """
    )
    
    parser.add_argument(
        '-f', '--format',
        action='store_true',
        help='コードフォーマットのみ実行'
    )
    parser.add_argument(
        '-l', '--lint',
        action='store_true',
        help='リントチェックのみ実行'
    )
    parser.add_argument(
        '-t', '--type-check',
        action='store_true',
        help='型チェックのみ実行'
    )
    parser.add_argument(
        '-u', '--test',
        action='store_true',
        help='テストのみ実行'
    )
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='すべてのチェックを実行（デフォルト）'
    )
    parser.add_argument(
        '-q', '--quick',
        action='store_true',
        help='クイックチェック（フォーマット + リント + 型チェック）'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='詳細出力'
    )
    
    args = parser.parse_args()
    
    # 実行するチェックを決定
    checks = []
    
    if args.quick:
        checks = ['format', 'lint', 'type-check']
    elif args.format:
        checks = ['format']
    elif args.lint:
        checks = ['lint']
    elif args.type_check:
        checks = ['type-check']
    elif args.test:
        checks = ['test']
    elif args.all or not any([args.format, args.lint, args.type_check, args.test, args.quick]):
        checks = ['format', 'lint', 'type-check', 'test']
    
    # チェックの実行
    checker = CodeChecker(verbose=args.verbose)
    success = checker.run_checks(checks)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 