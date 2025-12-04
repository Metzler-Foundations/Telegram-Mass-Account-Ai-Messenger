# Contributing to Telegram Automation Platform

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a professional, respectful environment.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Understanding of asyncio and PyQt6
- Familiarity with Telegram API

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio flake8 black mypy

# Run tests
pytest tests/
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `security/` - Security fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation changes

### 2. Make Changes

- Write clean, documented code
- Follow PEP 8 style guide
- Add type hints to function signatures
- Include docstrings for all public methods
- Write tests for new functionality

### 3. Test Your Changes

```bash
# Run unit tests
pytest tests/

# Run linter
flake8 .

# Run type checker
mypy .

# Check code formatting
black --check .
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: Add your feature description"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `security:` - Security fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Style Guidelines

### Python Style

- Follow PEP 8
- Maximum line length: 100 characters
- Use type hints
- Use descriptive variable names
- Add docstrings (Google style)

Example:

```python
def validate_phone_number(phone: str, normalize: bool = True) -> str:
    """
    Validate and normalize phone number.
    
    Args:
        phone: Phone number string
        normalize: Whether to normalize format
        
    Returns:
        Normalized phone number
        
    Raises:
        ValidationError: If phone number is invalid
    """
    # Implementation...
```

### Async/Await

- Use async/await for I/O operations
- Properly handle task cancellation
- Use semaphores for concurrency control
- Always cleanup resources

### Error Handling

- Use specific exception types
- Provide helpful error messages
- Log errors appropriately
- Don't swallow exceptions

## Testing Guidelines

### Writing Tests

- Test file: `tests/test_<module>.py`
- Test function: `test_<functionality>()`
- Use fixtures for common setup
- Mock external dependencies
- Aim for 80%+ coverage

Example:

```python
import pytest
from utils.input_validation import validate_phone

def test_validate_phone_number_valid():
    """Test phone number validation with valid input."""
    result = validate_phone("+1234567890")
    assert result == "+1234567890"

def test_validate_phone_number_invalid():
    """Test phone number validation with invalid input."""
    with pytest.raises(ValidationError):
        validate_phone("invalid")
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_validation.py

# With coverage
pytest --cov=. --cov-report=html

# Verbose mode
pytest -v
```

## Pull Request Process

### Before Submitting

- [ ] All tests pass
- [ ] Code is formatted (black)
- [ ] No linter errors (flake8)
- [ ] Type hints added (mypy clean)
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Security considerations reviewed

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Security fix
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass
- [ ] Code formatted
- [ ] Documentation updated
- [ ] Changelog updated
```

### Review Process

1. Automated checks run (linter, tests)
2. Code review by maintainer
3. Security review (if applicable)
4. Approval and merge

## Security Vulnerability Reporting

**DO NOT** open public issues for security vulnerabilities.

Instead, email: security@example.com

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 48 hours.

## Documentation

### Code Documentation

- Add docstrings to all public methods
- Include examples in docstrings
- Document complex algorithms
- Add inline comments for clarity

### Project Documentation

Update relevant documentation when adding features:
- README.md - Overview and quick start
- API docs - API reference
- User guides - Usage instructions

## Questions?

- Open an issue for questions
- Join our Discord (link TBD)
- Email: support@example.com

Thank you for contributing!





