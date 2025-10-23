# Contributing to COD3S

Thank you for your interest in contributing to COD3S! Please read our [Contributing Guide](../docs/development/contributing.md) for detailed information on how to contribute.

## Quick Start

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## Documentation

To build the documentation locally:

```bash
cd docs
pip install mkdocs mkdocs-material mkdocstrings[python]
mkdocs serve
```

## Code Style

We use Black for code formatting:

```bash
black cod3s/ tests/
```

## Questions?

Feel free to open an issue for questions or discussions.
