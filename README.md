# Bunsui

OSS TUI Data Pipeline Management Tool

## Overview

Bunsuiは、AWSサービスと統合されたデータパイプライン管理ツールです。直感的なTUI（Terminal User Interface）を通じて、複雑なデータパイプラインの構築、実行、監視を行うことができます。

## Features

- **Visual Pipeline Builder**: TUIを使用したビジュアルなパイプライン構築
- **AWS Integration**: Step Functions、Lambda、ECS、DynamoDB、S3との統合
- **Real-time Monitoring**: パイプライン実行状況のリアルタイム監視
- **Session Management**: パイプライン実行セッションの管理とチェックポイント機能
- **Error Handling**: 包括的なエラーハンドリングとリカバリー機能

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│       TUI       │    │   Core Models   │    │  AWS Services   │
│                 │    │                 │    │                 │
│  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │
│  │ Pipeline  │  │◄──►│  │ Session   │  │◄──►│  │ DynamoDB  │  │
│  │ Builder   │  │    │  │ Manager   │  │    │  │           │  │
│  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │
│                 │    │                 │    │                 │
│  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │
│  │ Monitor   │  │◄──►│  │ Pipeline  │  │◄──►│  │    S3     │  │
│  │ Dashboard │  │    │  │ DAG       │  │    │  │           │  │
│  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- AWS CLI configured
- AWS credentials

### Install from PyPI

```bash
pip install bunsui
```

### Install from source

```bash
git clone https://github.com/bunsui/bunsui.git
cd bunsui
pip install -e .
```

### Development setup

```bash
git clone https://github.com/bunsui/bunsui.git
cd bunsui
make install-dev
# or manually:
# pip install -e ".[dev]"
# pre-commit install
```

## Usage

### Basic Pipeline Creation

```bash
# Create a new pipeline
bunsui create pipeline my-data-pipeline

# Run pipeline
bunsui run my-data-pipeline

# Monitor running pipelines
bunsui monitor
```

### TUI Interface

Launch the TUI interface:

```bash
bunsui tui
```

## Project Structure

```
src/bunsui/                 # Main package (src layout for PyPI)
├── core/                   # Core business logic
│   ├── models/             # Data models
│   ├── session/            # Session management
│   ├── pipeline/           # Pipeline management
│   └── storage/            # Storage interfaces
├── aws/                    # AWS service integrations
│   ├── dynamodb/           # DynamoDB client
│   ├── s3/                 # S3 client
│   └── stepfunctions/      # Step Functions client
├── tui/                    # Terminal UI components
└── cli/                    # Command-line interface
tests/                      # Test suite
docs/                       # Documentation
examples/                   # Usage examples
```

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Or manually:
pytest
pytest --cov=src/bunsui
```

### Code Quality

```bash
# Format code
make format

# Check formatting
make format-check

# Run linting
make lint

# Type checking
make type-check

# Run all checks
make check-all
```

### Building and Publishing

```bash
# Build distribution packages
make build

# Check distribution
make check-dist

# Upload to Test PyPI
make upload-test

# Upload to PyPI
make upload
```

For detailed publishing instructions, see [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Development Status

This project is currently in active development. See the [development notes](dev_note/) for current progress and roadmap.
