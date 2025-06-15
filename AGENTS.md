# Heare Memory Global Service - Agent Development Guide

## Project Overview

The Heare Memory Global Service implements the "global" tier of a three-tier memory architecture designed for multi-agent environments. This service provides persistent, git-backed storage for cross-project concepts and knowledge that should be accessible by multiple agent instances.

### Memory Architecture Context

This project focuses exclusively on **global memory** within a three-tier system:

- **Session**: Task-specific, may not persist beyond session (handled by agent harnesses)
- **Project**: Curated by humans/agents, project-specific (AGENTS.md concept, stored with projects)
- **Global**: Cross-project concepts, multi-agent accessible, **this service**

## Core Principles

### 1. Git-Native Storage
- All memory operations backed by git commits for full audit trail
- Every write creates a commit with proper attribution
- Push operations with retry logic and conflict resolution
- Repository serves as single source of truth

### 2. RESTful Interface
- Clean HTTP API following OpenAPI specifications
- Consistent error responses with structured format
- Proper HTTP status codes and headers
- Self-documenting via `/docs` and `/schema` endpoints

### 3. Autonomous Operation
- Service starts with comprehensive validation of dependencies
- Graceful degradation to read-only mode when appropriate
- External tool detection with helpful error messages
- No human intervention required for normal operations

### 4. Multi-Agent Safety
- Atomic operations prevent corruption during concurrent access
- Read-only mode when authentication unavailable
- Path validation prevents directory traversal attacks
- Consistent behavior across different agent instances

## Development Standards

### Code Quality
- **Testing**: Comprehensive test coverage with pytest and asyncio
- **Linting**: Ruff for code quality and formatting
- **Pre-commit**: Automated quality checks on every commit
- **Type Safety**: Full type hints with mypy validation
- **Documentation**: Docstrings for all public interfaces

### Architecture Patterns
- **Async First**: All I/O operations use async/await
- **Dependency Injection**: Configuration via environment variables
- **Error Handling**: Structured exceptions with context
- **Separation of Concerns**: Clear module boundaries and responsibilities

### Git Workflow
- **Feature Branches**: Develop features in isolated branches
- **Atomic Commits**: Each commit represents a complete, working change
- **Descriptive Messages**: Commit messages explain both what and why
- **Pre-commit Hooks**: Automated quality checks prevent broken commits

## Project Structure

```
src/heare_memory/
├── main.py                  # FastAPI app and lifecycle management
├── config.py                # Environment configuration with pydantic
├── startup.py               # Service initialization and validation
├── git_manager.py           # Git operations and repository management
├── external_tools.py        # External tool detection and validation
├── state.py                 # Global application state management
├── routers/
│   ├── health.py            # Health check and status reporting
│   ├── memory.py            # Memory CRUD operations
│   └── schema.py            # OpenAPI schema endpoint
├── middleware/
│   └── error_handler.py     # Consistent error response formatting
└── models/
    ├── git.py               # Git operation data models
    └── memory.py            # Memory node data models
```

## API Design

### Core Endpoints
- `GET /health` - Service health and configuration status
- `GET /memory/{path}` - Retrieve memory node content
- `PUT /memory/{path}` - Create or update memory node
- `DELETE /memory/{path}` - Remove memory node
- `GET /memory/` - List memory nodes with filtering
- `POST /batch` - Atomic batch operations
- `GET /search` - Content search across memory

### Data Model
- **Memory Nodes**: Markdown files with metadata
- **Path Structure**: Forward-slash delimited, `.md` extension
- **Metadata**: Created/updated timestamps, size, git SHA
- **Batch Operations**: Multiple operations in single git commit

## Configuration

### Required Environment Variables
```bash
# Git repository for memory storage
GIT_REMOTE_URL="https://github.com/org/memory-repo.git"

# GitHub token for write operations (optional, enables write mode)
GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

### Optional Configuration
```bash
# Local storage path (default: ./memory)
MEMORY_ROOT="/var/lib/memory"

# Service network configuration
SERVICE_HOST="0.0.0.0"  # default
SERVICE_PORT="8000"     # default

# Logging level (default: INFO)
LOG_LEVEL="DEBUG"
```

## Development Workflow

### Setting Up Development Environment
```bash
# Clone repository
git clone https://github.com/heare-io/heare-memory.git
cd heare-memory

# Install dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Start development server
uv run python -m heare_memory.main
```

### Making Changes
1. **Create feature branch**: `git checkout -b feature/description`
2. **Write tests first**: Define expected behavior with tests
3. **Implement feature**: Write minimal code to pass tests
4. **Run quality checks**: `uv run pytest && uv run ruff check`
5. **Commit changes**: Descriptive commit messages
6. **Push and review**: Create PR for review

### Testing Strategy
- **Unit tests**: Individual component functionality
- **Integration tests**: Cross-component interactions
- **End-to-end tests**: Full API workflow validation
- **Mocking**: External dependencies (git, filesystem)

## Current Implementation Status

### ✅ Completed (Phase 1 - Infrastructure)
- **Project Setup**: Complete UV package management with all dependencies
- **FastAPI Application**: Modular router structure with health, memory, schema endpoints
- **Git Integration**: Full GitManager with commit, push, batch operations, retry logic
- **Startup Validation**: Comprehensive external tool checking (git, gh CLI, ripgrep/grep)
- **Configuration**: Pydantic settings with environment variables and read-only mode
- **Error Handling**: Structured error responses and comprehensive logging
- **Testing**: 26 passing tests across git operations, startup checks, and API structure
- **Code Quality**: Pre-commit hooks with ruff, autoflake, and formatting automation

### 🔄 Ready for Implementation (Phase 2 - Core Operations)
- **Memory CRUD Endpoints**: Router stubs exist, need file operations integration
- **Async File Operations**: Need module for safe markdown file read/write/delete
- **Search Integration**: Ripgrep/grep backends detected, need endpoint implementation
- **Batch Operations**: Models and git support ready, need endpoint implementation

### 📋 Future Phases
- **Semantic Search**: Content analysis and intelligent retrieval
- **Implicit Observation**: Background memory synthesis from interactions
- **Performance**: Caching, optimization, and scaling considerations

## Critical Implementation Notes

### Issue Tracking Integration
- Uses Linear/Plane for issue management
- 7 major issues completed in Phase 1 (HEARE-2 through HEARE-10)
- Issues can be queried, updated, and commented on during development
- Next high-priority issues: HEARE-5, HEARE-11, HEARE-12, HEARE-13, HEARE-14, HEARE-15

### Git Workflow Established
- Work directly on `main` branch (no feature branches for this project)
- All commits include comprehensive messages with context
- Pre-commit hooks enforce code quality automatically
- Test coverage tracking without enforcement threshold

### Key Architecture Decisions
- **GitManager**: Centralized git operations with async interface and error handling
- **State Management**: Global state in `state.py` to avoid circular imports
- **Startup Sequence**: Comprehensive validation before service accepts requests
- **Configuration**: Environment-driven with sensible defaults and validation
- **Error Philosophy**: Structured responses with actionable error messages

### Testing Philosophy
- Infrastructure code has 66% coverage (appropriate for foundational systems)
- Core business logic (git operations, tool checking) has 77-94% coverage
- Integration tests verify full workflows, unit tests cover individual components
- Temporary directories used for git operations to avoid side effects

### Memory Storage Patterns
- All memory nodes are `.md` files with forward-slash path structure
- Metadata included in responses (timestamps, size, git SHA)
- Directory structure created automatically as needed
- Git commits provide full audit trail of all changes

## Agent Interaction Patterns

### Explicit Memory Operations
Agents interact with global memory through deliberate API calls:
```python
# Read memory node
response = await http_client.get("/memory/concepts/python-patterns.md")

# Write memory node
await http_client.put("/memory/learnings/user-preferences.md",
                     json={"content": "# User Preferences\n\n..."})

# Search memory
results = await http_client.get("/search?query=authentication&prefix=concepts")
```

### Future: Implicit Memory Integration
Planned implicit interaction model:
1. Agent passes conversation context to memory service
2. Service performs semantic search across all memory
3. Relevant memories surfaced as "brings to mind" context
4. Agent maintains rolling context of relevant memories

### Memory Organization Patterns
- **Concepts**: `/concepts/` - General knowledge and patterns
- **Projects**: `/projects/` - Project-specific learnings
- **Users**: `/users/` - User preferences and context
- **Procedures**: `/procedures/` - Step-by-step processes
- **Learnings**: `/learnings/` - Derived insights and patterns

## Troubleshooting

### Common Issues
- **Startup failures**: Check git installation and repository access
- **Read-only mode**: Verify GITHUB_TOKEN configuration
- **Permission errors**: Ensure MEMORY_ROOT is writable
- **Tool detection**: Install git, optionally gh CLI and ripgrep

### Debugging
- **Health endpoint**: `/health` shows configuration and tool status
- **Logs**: Structured logging with configurable levels
- **Git status**: Check repository state and remote configuration
- **Test mode**: Run with temporary directories for isolation

## Contributing

### Code Review Checklist
- [ ] Tests pass and cover new functionality
- [ ] Code follows project style (ruff, type hints)
- [ ] Commit messages are descriptive
- [ ] Documentation updated for API changes
- [ ] Error handling includes helpful messages
- [ ] Git operations are atomic and safe

### Release Process
1. **Version bump**: Update version in `pyproject.toml`
2. **Documentation**: Update README and API docs
3. **Testing**: Full test suite on multiple environments
4. **Tagging**: Create git tag with release notes
5. **Deployment**: Container build and deployment automation

This project represents the foundational layer for persistent, multi-agent memory systems. Every design decision should consider scalability, reliability, and ease of agent integration.
