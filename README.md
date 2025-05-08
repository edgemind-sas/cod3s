# COD3S: COmplex Dynamic Stochastic System Simulation library

COD3S aims to provide tools for building generic component libraries to model complex industrial systems for simulation and assessment. The framework provides a generic formalism to describe components and systems, along with tools to translate system descriptions into other frameworks like PyCATSHOO to perform quantitative analyses.

## Key Features

- Generic component and system modeling formalism
- Tools for translating system descriptions to simulation frameworks
- Support for PyCATSHOO integration for quantitative analyses
- Framework for building reusable component libraries

## Code Style Guide
- Types: Use type hints with Pydantic>=2 framework 
- Imports: Stdlib first, then third-party, then local imports
- Naming: Classes=PascalCase, functions/vars=snake_case, constants=UPPERCASE
- Formatting: Use black formatter, 4-space indentation
- Error handling: Specific exceptions with descriptive messages, logged via COD3SLogger
- Docstrings: Multi-line format with parameter descriptions
- Testing: Use pytest, test files named test_*.py, fixtures in conftest.py

## Testing

```bash
# Run all tests
pytest

# Run a specific test
pytest tests/test_file.py::test_function_name

# Run slow tests
pytest --runslow
```
