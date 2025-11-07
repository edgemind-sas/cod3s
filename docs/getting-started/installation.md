# Installation

This guide will help you install COD3S for end users.

## Requirements

COD3S requires Python 3.9 or higher (up to Python 3.11). Make sure you have a compatible Python version installed:

```bash
python --version
```

## Installation

### Install from GitHub

Since COD3S is not yet published on PyPI, install it directly from the GitHub repository:

```bash
pip install git+https://github.com/edgemind-sas/cod3s.git
```

### Using a Virtual Environment (Recommended)

It's recommended to install COD3S in a virtual environment to avoid dependency conflicts:

```bash
# Create a virtual environment
python -m venv cod3s-env

# Activate the virtual environment
source cod3s-env/bin/activate  # On Windows: cod3s-env\Scripts\activate

# Install COD3S
pip install git+https://github.com/edgemind-sas/cod3s.git
```

## Verify Installation

After installation, verify that COD3S is properly installed:

```python
import cod3s
print(cod3s.__version__)
```

You should see the version number printed without any errors.

## Dependencies

COD3S automatically installs the following dependencies:

- **pandas** (2.2.2): Data manipulation and analysis
- **pydantic** (2.11.9): Data validation using Python type hints
- **plotly** (6.3.0): Interactive plotting library
- **PyYAML** (6.0.2): YAML parser and emitter
- **colored** (1.4.4): Terminal string styling
- **tqdm** (4.67.1): Progress bars
- **lxml** (5.3.0): XML and HTML processing
- **xlsxwriter** (3.0.9): Excel file creation
- **kaleido** (1.1.0): Static image export for Plotly
- **semver** (3.0.4): Semantic versioning

## Optional Dependencies

### PyCATSHOO Integration

For simulation capabilities, you'll need PyCATSHOO. Please refer to the PyCATSHOO documentation for installation instructions, as it may require additional system dependencies.

## Platform Support

- **Linux**: Fully supported and tested
- **Windows**: Should work, but some simulation dependencies may require additional setup
- **macOS**: Should work, consider using conda or homebrew for system dependencies if needed

## Troubleshooting

### Common Issues

**Import Error**: Make sure you're using the correct Python environment and that all dependencies are installed.

**Version Conflicts**: Use a virtual environment to isolate COD3S dependencies:

```bash
python -m venv cod3s-env
source cod3s-env/bin/activate  # On Windows: cod3s-env\Scripts\activate
pip install git+https://github.com/edgemind-sas/cod3s.git
```

**Network Issues**: If you have trouble accessing GitHub, check your network connection and proxy settings.

### Getting Help

If you encounter installation issues:

1. Check the [GitHub Issues](https://github.com/edgemind-sas/cod3s/issues) for similar problems
2. Create a new issue with details about your system and the error message
3. Include your Python version, operating system, and the full error traceback

## Upgrading

To upgrade to the latest version of COD3S:

```bash
pip install --upgrade git+https://github.com/edgemind-sas/cod3s.git
```

## Next Steps

Once COD3S is installed, you can:

- Follow the [Quick Start Guide](quickstart.md) to create your first model
- Read about [Core Concepts](concepts.md) to understand the framework
- Explore the [Tutorials](../tutorials/basic-component.md) for hands-on examples
