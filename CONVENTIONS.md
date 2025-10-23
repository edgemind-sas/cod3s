# Coding Conventions

## General conventions
### Python Style
- Use 4 spaces for indentation
- Maximum line length of 88 characters (Black formatter standard)
- Use docstrings for all classes and methods
- Include type hints for function parameters and return values
- Use pydantic >= 2.7 style everytime it is possible to design classes
- Use snake_case for variables and function names
- Use CamelCase for class names

### Import Order
- Standard library imports first
- Third-party library imports second
- Local application imports last
- Within each group, imports should be alphabetized

### Documentation
- All public methods and classes should have docstrings
- Use triple quotes for docstrings
- Include parameter descriptions in docstrings
- Use english for code documentation and git repo commit

### Error Handling
- Use specific exception types rather than generic exceptions
- Include descriptive error messages

## Testing

- Test files should be named test_*.py
- Use pytest for testing

```bash
# Run all tests
pytest tests/

# Run a specific test
pytest tests/test_file.py::test_function_name

# Run slow tests
pytest --runslow tests/
```
