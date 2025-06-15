# Heare Memory Global Service

A RESTful memory service that provides persistent storage for agents with automatic git versioning. The service exposes a tree-structured filesystem interface backed by markdown files and git commits.

## Overview

The Heare Memory Global Service implements the "global" tier of a three-tier memory architecture:
- **Session**: Task-specific, may not persist beyond session
- **Project**: Curated by humans/agents, project-specific  
- **Global**: Cross-project concepts, multi-agent accessible, implicit interaction model

This service provides:
- RESTful API for memory node CRUD operations
- Git-backed storage with full audit trail
- Search capabilities across memory content
- Batch operations for efficient updates
- Authentication and read-only mode support

## Quick Start

### Requirements

- Python 3.12+
- UV package manager
- Git
- GitHub CLI (`gh`) for git operations (optional, for push functionality)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/heare-ai/heare-memory.git
cd heare-memory
```

2. Install dependencies:
```bash
uv sync
```

3. Run the service:
```bash
uv run heare-memory
```

The service will be available at `http://localhost:8000`.

### Development

1. Install development dependencies:
```bash
uv sync --dev
```

2. Set up pre-commit hooks:
```bash
uv run pre-commit install
```

3. Run tests:
```bash
uv run pytest
```

4. Run the service in development mode:
```bash
uv run python -m heare_memory.main
```

## Configuration

The service is configured via environment variables:

- `GITHUB_TOKEN` (required for write operations and git push)
- `MEMORY_ROOT` (default: `./memory`)
- `GIT_REMOTE_URL` (required, e.g. `https://github.com/org/memory-repo.git`)
- `SERVICE_PORT` (default: 8000)
- `SERVICE_HOST` (default: 0.0.0.0)

## API Documentation

Once running, visit:
- API documentation: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Development Status

This project is currently in active development. See the [implementation plan](docs/IMPLEMENTATION_PLAN.md) for detailed progress and roadmap.

## Contributing

This project uses:
- **Package Manager**: UV
- **Code Quality**: Ruff, autoflake, pre-commit hooks
- **Testing**: pytest with asyncio support
- **Web Framework**: FastAPI
- **Git Integration**: GitPython

Please ensure all tests pass and code quality checks are met before submitting pull requests.

## License

MIT License - see LICENSE file for details.