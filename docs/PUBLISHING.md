# Publishing to PyPI

This document outlines the process for publishing Bunsui to PyPI.

## Prerequisites

1. **PyPI Account**: Create accounts on both [PyPI](https://pypi.org/) and [Test PyPI](https://test.pypi.org/)
2. **API Tokens**: Generate API tokens for both PyPI and Test PyPI
3. **Development Environment**: Set up development environment with required tools

## Setup

### 1. Install Development Dependencies

```bash
make install-dev
```

Or manually:

```bash
pip install -e ".[dev]"
```

### 2. Configure PyPI Credentials

Create a `~/.pypirc` file:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
```

**Note**: Replace `pypi-your-api-token-here` and `pypi-your-test-api-token-here` with your actual API tokens.

### 3. API Token Setup

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/token/)
2. Create a new API token with appropriate scope
3. Copy the token (it starts with `pypi-`)
4. Repeat for [Test PyPI](https://test.pypi.org/manage/account/token/)

## Release Process

### 1. Pre-release Checks

Run quality checks:

```bash
make check-all
```

This runs:
- Code formatting check (`black --check`)
- Import sorting check (`isort --check-only`)
- Linting (`flake8`)
- Type checking (`mypy`)
- Tests (`pytest`)

### 2. Version Bump

Update the version number:

```bash
make bump-version VERSION=x.y.z
```

This will:
- Update `pyproject.toml` with the new version
- Update `CHANGELOG.md` with release date
- Create a git commit and tag

### 3. Build Distribution

Build the distribution packages:

```bash
make build
```

This creates:
- Source distribution (`.tar.gz`)
- Wheel distribution (`.whl`)

### 4. Check Distribution

Verify the distribution packages:

```bash
make check-dist
```

### 5. Test Upload (Recommended)

Upload to Test PyPI first:

```bash
make upload-test
```

Test the installation:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ bunsui
```

### 6. Production Upload

If Test PyPI upload works correctly:

```bash
make upload
```

## Manual Process

If you prefer manual steps:

### 1. Clean Previous Builds

```bash
rm -rf build/ dist/ *.egg-info/
```

### 2. Build

```bash
python -m build
```

### 3. Check

```bash
python -m twine check dist/*
```

### 4. Upload to Test PyPI

```bash
python -m twine upload --repository testpypi dist/*
```

### 5. Upload to PyPI

```bash
python -m twine upload dist/*
```

## Continuous Integration

For automated releases, consider setting up GitHub Actions:

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify API tokens are correct
   - Check `.pypirc` configuration
   - Ensure token has appropriate permissions

2. **Package Already Exists**:
   - PyPI doesn't allow overwriting existing versions
   - Bump the version number and try again

3. **Invalid Distribution**:
   - Run `make check-dist` to identify issues
   - Ensure all required files are included in `MANIFEST.in`

4. **Import Errors After Installation**:
   - Check package structure matches `pyproject.toml` configuration
   - Verify entry points are correctly defined

### Verification

After publishing, verify the package:

1. Check the [PyPI page](https://pypi.org/project/bunsui/)
2. Install in a clean environment:
   ```bash
   pip install bunsui
   bunsui --version
   ```

## Security Best Practices

1. **Never commit API tokens** to version control
2. **Use API tokens** instead of passwords
3. **Limit token scope** to specific projects when possible
4. **Rotate tokens regularly**
5. **Use environment variables** or secure credential storage in CI/CD

## Version Strategy

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

Examples:
- `0.1.0` - Initial alpha release
- `0.2.0` - New features added
- `0.2.1` - Bug fixes
- `1.0.0` - First stable release 