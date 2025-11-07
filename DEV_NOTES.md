# COD3S Development Notes

This file contains all the necessary commands and scripts to develop the COD3S project.

## Environment Setup

### Installing development dependencies
```bash
# Install uv if not already done
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install development dependencies
uv sync --upgrade
```

### Virtual environment activation
```bash
# Activate the virtual environment created by uv
source .venv/bin/activate
```

## Development

### Testing
```bash
# Run all tests
pytest

# Run tests with more verbosity
pytest -v

# Run slow tests only
pytest --runslow

# Run a specific test
pytest tests/test_file.py::test_function_name
```

## Documentation

### MkDocs development server
```bash
# Start the development server
mkdocs serve

# Server accessible at http://127.0.0.1:8000
```

### Documentation building
```bash
# Build static documentation
mkdocs build

# Build and deploy to GitHub Pages
mkdocs gh-deploy
```

## Building and distribution

### Package building
```bash
# Build the package
python -m build

# Check the built package
twine check dist/*
```

### Local development installation
```bash
# Editable installation
pip install -e .
```

## Project scripts

### Main script
```bash
# Run a COD3S study
run-cod3s-study --help
```

## Useful commands

### Cleanup
```bash
# Clean Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete

# Clean build files
rm -rf build/ dist/ *.egg-info/
```

### Configuration verification
```bash
# Check project configuration
python -c "import cod3s; print(cod3s.__version__)"
```

## Recommended development workflow

1. **Before starting**:
   ```bash
   uv sync
   source .venv/bin/activate
   ```

2. **During development**:
   ```bash
   # Automatic formatting
   black .
   isort .
   
   # Tests
   pytest
   
   # Documentation
   mkdocs serve
   ```

3. **Before committing**:
   ```bash
   # Complete checks
   flake8 .
   mypy cod3s/
   pytest
   ```
