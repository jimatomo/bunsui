

"""
Initialization commands for Bunsui CLI.
"""

import click
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box
from rich.prompt import Prompt
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
import json
import yaml
import os
from pathlib import Path
from datetime import datetime
import sys
import tty
import termios

console = Console()


class InteractiveSelector:
    """インタラクティブな選択機能を提供するクラス"""
    
    def __init__(self, console: Console):
        self.console = console
    
    def select_with_autocomplete(self, prompt: str, choices: List[str], default: Optional[str] = None) -> str:
        """予測変換付きの選択機能"""
        self.console.print(f"\n[bold cyan]{prompt}[/bold cyan]")
        self.console.print(f"選択肢: {', '.join(choices)}")
        if default:
            self.console.print(f"デフォルト: [green]{default}[/green]")
        
        while True:
            user_input = Prompt.ask("選択してください", default=default or "")
            
            # 完全一致
            if user_input in choices:
                return user_input
            
            # 部分一致で予測変換
            matches = [choice for choice in choices if choice.lower().startswith(user_input.lower())]
            
            if len(matches) == 1:
                # 1つだけマッチした場合、自動補完
                selected = matches[0]
                self.console.print(f"[green]自動補完: {selected}[/green]")
                return selected
            elif len(matches) > 1:
                # 複数マッチした場合、候補を表示
                self.console.print(f"[yellow]候補: {', '.join(matches)}[/yellow]")
                self.console.print("より具体的に入力してください")
            else:
                # マッチしない場合
                self.console.print(f"[red]無効な選択です。選択肢: {', '.join(choices)}[/red]")
    
    def select_with_radio(self, prompt: str, choices: List[str], descriptions: Optional[List[str]] = None, default: Optional[str] = None) -> str:
        """ラジオボタン形式の選択機能"""
        self.console.print(f"\n[bold cyan]{prompt}[/bold cyan]")
        
        # 選択肢を表示
        for i, choice in enumerate(choices, 1):
            marker = "●" if choice == default else "○"
            color = "green" if choice == default else "white"
            
            if descriptions and i <= len(descriptions):
                self.console.print(f"[{color}]{marker} {i}. {choice}[/{color}] - {descriptions[i-1]}")
            else:
                self.console.print(f"[{color}]{marker} {i}. {choice}[/{color}]")
        
        while True:
            try:
                user_input = Prompt.ask("番号で選択してください", default=str(choices.index(default) + 1) if default else "")
                
                # 数字で選択
                if user_input.isdigit():
                    index = int(user_input) - 1
                    if 0 <= index < len(choices):
                        return choices[index]
                
                # 文字列で選択（部分一致）
                matches = [choice for choice in choices if choice.lower().startswith(user_input.lower())]
                if len(matches) == 1:
                    return matches[0]
                elif len(matches) > 1:
                    self.console.print(f"[yellow]候補: {', '.join(matches)}[/yellow]")
                    continue
                
                self.console.print(f"[red]無効な選択です。1-{len(choices)}の数字または選択肢名を入力してください[/red]")
                
            except (ValueError, IndexError):
                self.console.print(f"[red]無効な入力です。1-{len(choices)}の数字を入力してください[/red]")
    
    def select_with_arrow_keys(self, prompt: str, choices: List[str], descriptions: Optional[List[str]] = None, default: Optional[str] = None) -> str:
        """十字キーで移動するインタラクティブ選択機能"""
        if not choices:
            raise ValueError("選択肢が空です")
        
        # デフォルトインデックスの決定
        default_index = 0
        if default and default in choices:
            default_index = choices.index(default)
        
        current_index = default_index
        
        def create_selection_display() -> str:
            """選択画面の表示を作成"""
            lines = [f"\n[bold cyan]{prompt}[/bold cyan]\n"]
            lines.append("[dim]↑↓キーで移動、Enterで選択、qでキャンセル[/dim]\n")
            
            for i, choice in enumerate(choices):
                # 現在選択中の項目をハイライト
                if i == current_index:
                    marker = "●"
                    color = "green"
                    prefix = "> "
                else:
                    marker = "○"
                    color = "white"
                    prefix = "  "
                
                # 説明文がある場合は追加
                description = ""
                if descriptions and i < len(descriptions):
                    description = f" - {descriptions[i]}"
                
                lines.append(f"[{color}]{prefix}{marker} {choice}{description}[/{color}]")
            
            return "\n".join(lines)
        
        def get_key() -> str:
            """キー入力を取得"""
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # ESC
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':  # [
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A':  # 上矢印
                            return 'UP'
                        elif ch3 == 'B':  # 下矢印
                            return 'DOWN'
                elif ch == '\r' or ch == '\n':  # Enter
                    return 'ENTER'
                elif ch == 'q':  # qキー
                    return 'QUIT'
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        # 初期表示
        self.console.print(create_selection_display())
        
        while True:
            # キー入力を待機
            key = get_key()
            
            if key == 'UP':
                current_index = (current_index - 1) % len(choices)
            elif key == 'DOWN':
                current_index = (current_index + 1) % len(choices)
            elif key == 'ENTER':
                # 選択完了
                self.console.print(f"\n[green]選択: {choices[current_index]}[/green]")
                return choices[current_index]
            elif key == 'QUIT':
                # キャンセル
                self.console.print("\n[yellow]選択がキャンセルされました[/yellow]")
                raise KeyboardInterrupt
            
            # 画面をクリアして再表示
            self.console.clear()
            self.console.print(create_selection_display())


# グローバルなセレクターインスタンス
selector = InteractiveSelector(console)


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.pass_context
def init(ctx: click.Context):
    """Bunsuiの初期化を実行。インタラクティブに設定を行い、既存設定がある場合は確認します。"""
    
    # メインの初期化処理
    _handle_main_setup(ctx)


def _handle_main_setup(ctx: click.Context):
    """メインの初期化処理"""
    # 設定ディレクトリの決定（デフォルト: ~/.bunsui）
    base_config_dir = Path.home() / '.bunsui'
    
    console.print(Panel.fit(
        "[bold blue]Bunsui 初期化ウィザード[/bold blue]\n"
        f"モード: インタラクティブ\n"
        f"設定ディレクトリ: {base_config_dir}",
        title="🚀 Bunsui Setup"
    ))
    
    # 既存設定のチェック（force=Falseで確認）
    if _check_existing_setup(base_config_dir):
        if not Confirm.ask("既存の設定が見つかりました。続行しますか？"):
            console.print("[yellow]初期化がキャンセルされました[/yellow]")
            return
    
    # モード別の初期化実行
    _setup_interactive(ctx, base_config_dir)
    
    console.print(Panel.fit(
        "[bold green]✅ 初期化が完了しました！[/bold green]\n\n"
        "次のステップ:\n"
        "1. チュートリアルを実行: [bold]cd tutorial && bunsui pipeline create --file simple_pipeline.yaml --dry-run[/bold]\n"
        "2. ヘルプを確認: [bold]bunsui --help[/bold]\n"
        "3. 設定を確認: [bold]bunsui config list[/bold]\n"
        "4. 診断を実行: [bold]bunsui doctor[/bold]",
        title="🎉 セットアップ完了"
    ))


def _check_existing_setup(config_dir: Path) -> bool:
    """既存のセットアップをチェック"""
    return (config_dir / 'config' / 'config.yaml').exists()


def _setup_interactive(ctx: click.Context, config_dir: Path):
    """インタラクティブセットアップ"""
    console.print("[bold cyan]インタラクティブセットアップを開始します[/bold cyan]")
    
    # 用途を選択（ラジオボタン形式）
    purposes = ["learning", "development", "production"]
    descriptions = [
        "学習・実験用（オフラインモード）",
        "開発用（AWS開発環境）", 
        "本番環境用（AWS本番環境）"
    ]
    
    purpose = selector.select_with_arrow_keys(
        "Bunsuiの用途を選択してください",
        purposes,
        descriptions,
        default="learning"
    )
    
    if purpose == "learning":
        _setup_offline(ctx, config_dir)
    elif purpose == "development":
        # AWS設定の詳細選択
        _setup_aws_interactive(ctx, config_dir, is_production=False)
    else:  # production
        _setup_aws_interactive(ctx, config_dir, is_production=True)


def _setup_aws_interactive(ctx: click.Context, config_dir: Path, is_production: bool):
    """AWS設定のインタラクティブセットアップ"""
    console.print(f"[bold blue]AWS {'本番' if is_production else '開発'}環境の設定[/bold blue]")
    
    # デフォルト値の設定
    default_region = "us-east-1"
    default_profile = "production" if is_production else ""
    
    aws_region = Prompt.ask("AWS リージョンを入力", default=default_region)
    
    # AWSプロファイル選択
    if is_production:
        aws_profile = Prompt.ask("AWS プロファイル名", default=default_profile)
    else:
        aws_profile = Prompt.ask("AWS プロファイル名（オプション）", default=default_profile)
    
    if is_production:
        _setup_production(ctx, config_dir, aws_region, aws_profile)
    else:
        _setup_aws(ctx, config_dir, aws_region, aws_profile or None)


def _setup_offline(ctx: click.Context, config_dir: Path):
    """オフラインモードセットアップ"""
    console.print("[yellow]オフラインモードでセットアップします[/yellow]")
    
    # ディレクトリ作成
    _create_directories(config_dir)
    
    # 基本設定作成
    config_data = {
        'mode': 'offline',
        'version': '1.0.0',
        'created_at': datetime.utcnow().isoformat(),
        'directories': {
            'data': str(config_dir / 'data'),
            'cache': str(config_dir / 'cache'),
            'logs': str(config_dir / 'logs')
        },
        'defaults': {
            'timeout_seconds': 3600,
            'max_concurrent_jobs': 5,
            'output_format': 'table'
        }
    }
    
    _save_config(config_dir, config_data)
    _setup_sample_files(config_dir)
    
    console.print("[green]✓ オフラインモードの設定が完了しました[/green]")


def _setup_aws(ctx: click.Context, config_dir: Path, region: Optional[str], 
               profile: Optional[str]):
    """AWS開発モードセットアップ"""
    console.print("[blue]AWS開発モードでセットアップします[/blue]")
    
    # ディレクトリ作成
    _create_directories(config_dir)
    
    # AWS設定の検証
    if not _validate_aws_credentials(region, profile):
        console.print("[red]AWS認証情報が見つかりません。先にAWS CLIを設定してください[/red]")
        console.print("[yellow]オフラインモードで続行します[/yellow]")
        _setup_offline(ctx, config_dir)
        return
    
    # AWSリソースの自動作成
    created_resources = None
    if Confirm.ask("AWSリソース（DynamoDBテーブル、S3バケット）を自動で作成しますか？"):
        created_resources = _create_aws_resources(region, profile, is_production=False)
    
    # AWS設定作成
    config_data = {
        'mode': 'aws_development',
        'version': '1.0.0',
        'created_at': datetime.utcnow().isoformat(),
        'aws': {
            'region': region or 'us-east-1',
            'profile': profile,
            'dynamodb_table_prefix': 'bunsui-dev',
            's3_bucket_prefix': 'bunsui-dev',
        },
        'directories': {
            'data': str(config_dir / 'data'),
            'cache': str(config_dir / 'cache'),
            'logs': str(config_dir / 'logs')
        },
        'defaults': {
            'timeout_seconds': 3600,
            'max_concurrent_jobs': 5,
            'output_format': 'table'
        }
    }
    
    # 作成されたリソース情報を設定に追加
    if created_resources:
        # YAML互換性のため、確実に文字列キーと値を使用
        config_data['aws']['created_resources'] = {
            'tables': {str(k): str(v) for k, v in created_resources['tables'].items()},
            'buckets': {str(k): str(v) for k, v in created_resources['buckets'].items()},
            'random_suffix': str(created_resources['random_suffix'])
        }
    
    _save_config(config_dir, config_data)
    _setup_sample_files(config_dir)
    
    console.print("[green]✓ AWS開発モードの設定が完了しました[/green]")
    
    # 作成されたリソース情報を表示
    if created_resources:
        console.print("\n[bold cyan]作成されたAWSリソース:[/bold cyan]")
        
        if created_resources['tables']:
            console.print("[dim]📊 DynamoDBテーブル:[/dim]")
            for table_name, full_name in created_resources['tables'].items():
                console.print(f"  - {full_name}")
        
        if created_resources['buckets']:
            console.print("[dim]🪣 S3バケット:[/dim]")
            for bucket_type, bucket_name in created_resources['buckets'].items():
                console.print(f"  - {bucket_name}")
        
        if created_resources['random_suffix']:
            console.print(f"[dim]🔑 ランダムサフィックス: {created_resources['random_suffix']}[/dim]")
        
        # 失敗したリソースがある場合の警告
        expected_tables = 3
        expected_buckets = 3
        actual_tables = len(created_resources['tables'])
        actual_buckets = len(created_resources['buckets'])
        
        if actual_tables < expected_tables or actual_buckets < expected_buckets:
            console.print(f"\n[yellow]⚠ 一部のリソースの作成に失敗しました[/yellow]")
            console.print(f"[dim]  テーブル: {actual_tables}/{expected_tables}[/dim]")
            console.print(f"[dim]  バケット: {actual_buckets}/{expected_buckets}[/dim]")
            console.print("[yellow]  手動でリソースを作成するか、再度セットアップを実行してください[/yellow]")
    else:
        console.print("[yellow]注意: DynamoDBテーブルとS3バケットは手動で作成する必要があります[/yellow]")


def _setup_production(ctx: click.Context, config_dir: Path, region: Optional[str], 
                     profile: Optional[str]):
    """本番モードセットアップ"""
    console.print("[red]本番モードでセットアップします[/red]")
    
    if not Confirm.ask("本番環境での使用は高度な設定が必要です。続行しますか？"):
        console.print("[yellow]セットアップがキャンセルされました[/yellow]")
        return
    
    # ディレクトリ作成
    _create_directories(config_dir)
    
    # AWSリソースの自動作成（本番環境）
    created_resources = None
    if Confirm.ask("本番環境のAWSリソース（DynamoDBテーブル、S3バケット）を自動で作成しますか？"):
        created_resources = _create_aws_resources(region, profile, is_production=True)
    
    # 本番設定作成
    config_data = {
        'mode': 'production',
        'version': '1.0.0',
        'created_at': datetime.utcnow().isoformat(),
        'aws': {
            'region': region or 'us-east-1',
            'profile': profile or 'production',
            'dynamodb_table_prefix': 'bunsui-prod',
            's3_bucket_prefix': 'bunsui-prod',
        },
        'directories': {
            'data': str(config_dir / 'data'),
            'cache': str(config_dir / 'cache'),
            'logs': str(config_dir / 'logs')
        },
        'defaults': {
            'timeout_seconds': 7200,
            'max_concurrent_jobs': 10,
            'output_format': 'json'
        },
        'security': {
            'enable_audit_logs': True,
            'require_confirmation': True
        }
    }
    
    # 作成されたリソース情報を設定に追加
    if created_resources:
        # YAML互換性のため、確実に文字列キーと値を使用
        config_data['aws']['created_resources'] = {
            'tables': {str(k): str(v) for k, v in created_resources['tables'].items()},
            'buckets': {str(k): str(v) for k, v in created_resources['buckets'].items()},
            'random_suffix': str(created_resources['random_suffix'])
        }
    
    _save_config(config_dir, config_data)
    
    console.print("[green]✓ 本番モードの設定が完了しました[/green]")
    
    # 作成されたリソース情報を表示
    if created_resources:
        console.print("\n[bold cyan]作成されたAWSリソース:[/bold cyan]")
        
        if created_resources['tables']:
            console.print("[dim]📊 DynamoDBテーブル:[/dim]")
            for table_name, full_name in created_resources['tables'].items():
                console.print(f"  - {full_name}")
        
        if created_resources['buckets']:
            console.print("[dim]🪣 S3バケット:[/dim]")
            for bucket_type, bucket_name in created_resources['buckets'].items():
                console.print(f"  - {bucket_name}")
        
        if created_resources['random_suffix']:
            console.print(f"[dim]🔑 ランダムサフィックス: {created_resources['random_suffix']}[/dim]")
        
        # 失敗したリソースがある場合の警告
        expected_tables = 3
        expected_buckets = 3
        actual_tables = len(created_resources['tables'])
        actual_buckets = len(created_resources['buckets'])
        
        if actual_tables < expected_tables or actual_buckets < expected_buckets:
            console.print(f"\n[yellow]⚠ 一部のリソースの作成に失敗しました[/yellow]")
            console.print(f"[dim]  テーブル: {actual_tables}/{expected_tables}[/dim]")
            console.print(f"[dim]  バケット: {actual_buckets}/{expected_buckets}[/dim]")
            console.print("[yellow]  手動でリソースを作成するか、再度セットアップを実行してください[/yellow]")
        
        console.print("[red]重要: 本番環境のIAM設定を確認してください[/red]")
    else:
        console.print("[red]重要: 本番環境のAWSリソースとIAM設定を確認してください[/red]")


def _create_directories(config_dir: Path):
    """必要なディレクトリを作成"""
    directories = [
        config_dir / 'config',
        config_dir / 'data',
        config_dir / 'cache', 
        config_dir / 'logs'
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[dim]📁 {dir_path}[/dim]")


def _save_config(config_dir: Path, config_data: dict):
    """設定ファイルを保存"""
    config_file = config_dir / 'config' / 'config.yaml'
    


    # YAML互換性のため、Pythonオブジェクトを文字列に変換
    def convert_for_yaml(obj):
        """YAML互換性のためオブジェクトを変換"""
        if hasattr(obj, 'value'):
            return obj.value
        elif hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool, type(None))):
            return {k: convert_for_yaml(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {str(k): convert_for_yaml(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_for_yaml(item) for item in obj]
        elif hasattr(obj, '__class__') and obj.__class__.__module__ != 'builtins':
            # カスタムクラスや列挙型の場合、文字列表現を返す
            return str(obj)
        else:
            return obj
    
    # 設定データをYAML互換に変換
    yaml_safe_data = convert_for_yaml(config_data)
    
    with open(config_file, 'w') as f:
        yaml.dump(yaml_safe_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    console.print(f"[green]✓ 設定ファイルを保存しました: {config_file}[/green]")


def _setup_sample_files(config_dir: Path):
    """サンプルファイルをセットアップ"""
    samples_dir = config_dir / 'samples'
    samples_dir.mkdir(exist_ok=True)
    
    _create_sample_files(samples_dir)
    console.print(f"[green]✓ サンプルファイルを配置しました: {samples_dir}[/green]")


def _create_sample_files(target_dir: Path):
    """サンプルファイルを作成"""
    
    # Simple pipeline sample
    simple_pipeline = {
        'name': 'シンプルデータ処理パイプライン',
        'description': '基本的なデータ処理を行うシンプルなパイプライン',
        'version': '1.0.0',
        'timeout_seconds': 3600,
        'max_concurrent_jobs': 5,
        'tags': {
            'environment': 'tutorial',
            'level': 'beginner'
        },
        'metadata': {
            'created_by': 'bunsui-init',
            'purpose': '学習用サンプル'
        },
        'jobs': [
            {
                'job_id': 'hello-world',
                'name': 'Hello World ジョブ',
                'description': '最初のサンプルジョブ',
                'operations': [
                    {
                        'operation_id': 'hello-world-lambda',
                        'name': 'Hello World Lambda',
                        'config': {
                            'operation_type': 'lambda',
                            'resource_arn': 'arn:aws:lambda:us-east-1:123456789012:function:hello-world-function',
                            'timeout_seconds': 300,
                            'parameters': {
                                'message': 'Hello from Bunsui!'
                            }
                        }
                    }
                ],
                'dependencies': []
            },
            {
                'job_id': 'process-data',
                'name': 'データ処理ジョブ',
                'description': '簡単なデータ処理を実行',
                'operations': [
                    {
                        'operation_id': 'process-data-lambda',
                        'name': 'Process Data Lambda',
                        'config': {
                            'operation_type': 'lambda',
                            'resource_arn': 'arn:aws:lambda:us-east-1:123456789012:function:process-data-function',
                            'timeout_seconds': 600,
                            'parameters': {
                                'input_file': 'sample.txt',
                                'output_file': 'result.txt'
                            }
                        }
                    }
                ],
                'dependencies': ['hello-world']
            }
        ]
    }
    
    # ETL pipeline sample
    etl_pipeline = {
        'name': 'サンプルETLパイプライン',
        'description': 'CSVファイルからデータを読み取り、変換してS3に保存するサンプルパイプライン',
        'version': '1.0.0',
        'timeout_seconds': 3600,
        'max_concurrent_jobs': 3,
        'tags': {
            'environment': 'tutorial',
            'pipeline_type': 'etl',
            'team': 'data-engineering'
        },
        'metadata': {
            'created_by': 'bunsui-init',
            'purpose': 'ETL学習用サンプル'
        },
        'jobs': [
            {
                'job_id': 'extract-job',
                'name': 'データ抽出',
                'description': 'S3からCSVファイルを読み取る',
                'operations': [
                    {
                        'operation_id': 'extract-csv',
                        'name': 'Extract CSV from S3',
                        'config': {
                            'operation_type': 'lambda',
                            'resource_arn': 'arn:aws:lambda:ap-northeast-1:123456789012:function:extract-csv-function',
                            'timeout_seconds': 300,
                            'parameters': {
                                'input_bucket': 'sample-input-bucket',
                                'input_key': 'data/input.csv'
                            }
                        }
                    }
                ],
                'dependencies': []
            },
            {
                'job_id': 'transform-job',
                'name': 'データ変換',
                'description': 'データのクレンジングと変換を実行',
                'operations': [
                    {
                        'operation_id': 'transform-data',
                        'name': 'Transform Data',
                        'config': {
                            'operation_type': 'lambda',
                            'resource_arn': 'arn:aws:lambda:ap-northeast-1:123456789012:function:transform-data-function',
                            'timeout_seconds': 900,
                            'parameters': {
                                'transformation_rules': {
                                    'convert_to_uppercase': True,
                                    'remove_duplicates': True,
                                    'validate_schema': True
                                }
                            }
                        }
                    }
                ],
                'dependencies': ['extract-job']
            },
            {
                'job_id': 'load-job',
                'name': 'データロード',
                'description': '変換されたデータをS3に保存',
                'operations': [
                    {
                        'operation_id': 'load-to-s3',
                        'name': 'Load to S3',
                        'config': {
                            'operation_type': 'lambda',
                            'resource_arn': 'arn:aws:lambda:ap-northeast-1:123456789012:function:load-to-s3-function',
                            'timeout_seconds': 600,
                            'parameters': {
                                'output_bucket': 'sample-output-bucket',
                                'output_key': 'data/output.parquet',
                                'format': 'parquet'
                            }
                        }
                    }
                ],
                'dependencies': ['transform-job']
            }
        ]
    }
    
    # ファイルを保存
    with open(target_dir / 'simple_pipeline.yaml', 'w') as f:
        yaml.dump(simple_pipeline, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    with open(target_dir / 'sample_pipeline.yaml', 'w') as f:
        yaml.dump(etl_pipeline, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    # README作成
    readme_content = """# Bunsui サンプルファイル

このディレクトリには、Bunsuiの学習と実験用のサンプルパイプライン定義が含まれています。

## ファイル一覧

- `simple_pipeline.yaml` - 基本的なデータ処理パイプライン
- `sample_pipeline.yaml` - ETLパイプラインの例

## 使用方法

```bash
# パイプライン定義を検証
bunsui pipeline create --file simple_pipeline.yaml --dry-run

# パイプラインを作成（AWS環境が必要）
bunsui pipeline create --file simple_pipeline.yaml --name "My Pipeline"
```

## 注意事項

- サンプルファイル内のAWSリソース（Lambda関数、S3バケットなど）は架空のものです
- 実際の使用には実在するAWSリソースを指定してください
- まずはドライラン（--dry-run）でパイプライン定義を検証することをお勧めします
"""
    
    with open(target_dir / 'README.md', 'w') as f:
        f.write(readme_content)


def _validate_aws_credentials(region: Optional[str], profile: Optional[str]) -> bool:
    """AWS認証情報を検証"""
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ProfileNotFound
        
        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            session = boto3.Session()
        
        # STSを使用して認証情報をテスト
        sts = session.client('sts', region_name=region or 'us-east-1')
        sts.get_caller_identity()
        return True
        
    except (NoCredentialsError, ProfileNotFound):
        return False
    except Exception:
        return False


def _create_aws_resources(region: Optional[str], profile: Optional[str], is_production: bool):
    """AWSリソースを自動作成"""
    try:
        import boto3
        import uuid
        from bunsui.aws.dynamodb.client import DynamoDBClient
        from bunsui.aws.s3.client import S3Client
        from bunsui.aws.dynamodb.schemas import TableName
        
        # AWSクライアントの初期化
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region or 'us-east-1')
        else:
            session = boto3.Session(region_name=region or 'us-east-1')
        
        prefix = 'bunsui-prod' if is_production else 'bunsui-dev'
        region_name = region or 'us-east-1'
        
        # S3バケット名の衝突を防ぐためのランダム文字列を生成
        random_suffix = str(uuid.uuid4())[:8]  # 8文字のランダム文字列
        
        console.print(f"[cyan]AWSリソースを作成中... (リージョン: {region_name})[/cyan]")
        
        # DynamoDBテーブルの作成（冗長なbunsuiを除去）
        console.print("[dim]📊 DynamoDBテーブルを作成中...[/dim]")
        dynamodb_client = DynamoDBClient(region_name)
        
        # テーブル名のマッピング（冗長なbunsuiを除去）
        table_name_mapping = {
            TableName.SESSIONS: "sessions",
            TableName.JOB_HISTORY: "job-history", 
            TableName.PIPELINES: "pipelines"
        }
        
        created_tables = {}
        for table_name in [TableName.SESSIONS, TableName.JOB_HISTORY, TableName.PIPELINES]:
            try:
                # 冗長なbunsuiを除去したテーブル名
                simple_name = table_name_mapping[table_name]
                full_table_name = f"{prefix}-{simple_name}"
                # 文字列キーを使用してYAML互換にする（table_name.valueではなく、実際のテーブル名を使用）
                table_key = f"{prefix}-{simple_name}"
                created_tables[table_key] = full_table_name
                
                console.print(f"[dim]  - {full_table_name}[/dim]")
                dynamodb_client.create_table(table_name)
                console.print(f"[green]  ✓ {full_table_name} を作成しました[/green]")
            except Exception as e:
                if "already exists" in str(e).lower():
                    console.print(f"[yellow]  ⚠ {full_table_name} は既に存在します[/yellow]")
                else:
                    console.print(f"[red]  ✗ {full_table_name} の作成に失敗: {str(e)}[/red]")
        
        # S3バケットの作成（ランダム文字列付き）
        console.print("[dim]🪣 S3バケットを作成中...[/dim]")
        s3_client = S3Client(region_name)
        
        bucket_types = ["data", "logs", "reports"]
        created_buckets = {}
        
        for bucket_type in bucket_types:
            try:
                # ランダム文字列付きのバケット名
                bucket_name = f"{prefix}-{bucket_type}-{random_suffix}"
                
                console.print(f"[dim]  - {bucket_name}[/dim]")
                s3_client.create_bucket(bucket_name, region_name)
                created_buckets[bucket_type] = bucket_name
                console.print(f"[green]  ✓ {bucket_name} を作成しました[/green]")
            except Exception as e:
                if "already exists" in str(e).lower() or "already owned by you" in str(e).lower():
                    console.print(f"[yellow]  ⚠ {bucket_name} は既に存在します[/yellow]")
                    created_buckets[bucket_type] = bucket_name
                else:
                    console.print(f"[red]  ✗ {bucket_name} の作成に失敗: {str(e)}[/red]")
                    # エラーが発生した場合は、そのバケットをスキップ
                    continue
        
        # 作成結果の確認
        success_count = len(created_tables) + len(created_buckets)
        total_count = 3 + 3  # テーブル3つ + バケット3つ
        
        if success_count == total_count:
            console.print("[green]✓ AWSリソースの作成が完了しました[/green]")
        elif success_count > 0:
            console.print(f"[yellow]⚠ AWSリソースの作成が部分的に完了しました ({success_count}/{total_count})[/yellow]")
        else:
            console.print("[red]✗ AWSリソースの作成に失敗しました[/red]")
            return None
        
        # 作成されたリソース名を返す
        return {
            'tables': created_tables,
            'buckets': created_buckets,
            'random_suffix': random_suffix
        }
        
    except ImportError:
        console.print("[red]boto3がインストールされていません。AWSリソースの自動作成をスキップします[/red]")
        return None
    except Exception as e:
        console.print(f"[red]AWSリソースの作成中にエラーが発生しました: {str(e)}[/red]")
        console.print("[yellow]手動でリソースを作成してください[/yellow]")
        return None 