# Memory Service Specification

## Overview

A RESTful memory service that provides persistent storage for agents with automatic git versioning. The service exposes a tree-structured filesystem interface backed by markdown files and git commits.

## Technical Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Package Manager**: UV
- **Testing**: pytest + asyncio
- **Code Quality**: pre-commit hooks with ruff and autoflake
- **Version Control**: Git (with GitHub integration)
- **Search**: ripgrep (with grep fallback)

## Core Requirements

### 1. Service Configuration

#### Environment Variables
- `GITHUB_TOKEN` (required for write operations and git push)
- `MEMORY_ROOT` (default: `./memory`)
- `GIT_REMOTE_URL` (required, e.g. `https://github.com/org/memory-repo.git`)
- `SERVICE_PORT` (default: 8000)
- `SERVICE_HOST` (default: 0.0.0.0)

#### Startup Checks
1. Check if `MEMORY_ROOT` directory exists
   - If not, create it
2. Check if `MEMORY_ROOT` contains a git repository
   - If not, clone from `GIT_REMOTE_URL`
   - If yes, verify remote URL matches `GIT_REMOTE_URL`
3. Verify `gh` CLI tool is installed
4. Configure repository for HTTP push using `GITHUB_TOKEN`
5. If `GITHUB_TOKEN` is not set, start in read-only mode
6. Check for ripgrep availability, fallback to grep

#### Initial Setup Behavior
- On first run, the service will clone the repository specified in `GIT_REMOTE_URL` to `MEMORY_ROOT`
- On subsequent runs, if `MEMORY_ROOT` already contains a git repository:
  - Verify the remote URL matches `GIT_REMOTE_URL`
  - If mismatch, fail with error (prevents accidental repository switches)
  - If match, continue using existing repository
- After initial clone, the service becomes the authoritative source - no pulls or merges are performed
- All subsequent operations are local commits followed by pushes to the remote

### 2. Data Model

#### Memory Node
```json
{
  "path": "agents/agent1/context.md",
  "content": "markdown content here",
  "metadata": {
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "size": 1024,
    "sha": "abc123..."
  }
}
```

#### Tree Structure
- Paths use forward slashes (`/`) as delimiters
- All files have `.md` extension
- Directory structure mirrors the logical memory hierarchy

### 3. API Endpoints

#### Authentication
- No authentication required for API endpoints (public access)
- `GITHUB_TOKEN` is used internally for git push operations only
- All endpoints are publicly accessible

#### Core Endpoints

##### GET /health
Health check endpoint
```json
{
  "status": "healthy",
  "read_only": false,
  "git_configured": true,
  "search_backend": "ripgrep"
}
```

##### GET /memory/{path:path}
Read a memory node
- Returns: Memory node JSON or 404
- Headers: `X-Git-SHA` (current commit)

##### PUT /memory/{path:path}
Write/Update a memory node
- Body: `{"content": "markdown content"}`
- Creates parent directories as needed
- Commits with message: `Update {path}`
- Returns: Updated memory node JSON

##### DELETE /memory/{path:path}
Delete a memory node
- Commits with message: `Delete {path}`
- Returns: 204 No Content

##### GET /list
List memory nodes
- Query params:
  - `prefix`: string (filter by path prefix)
  - `delimiter`: string (for hierarchical listing, default none)
  - `recursive`: boolean (default true)
  - `include_content`: boolean (default false)
- Returns: Array of memory nodes

##### POST /batch
Batch update operations
```json
{
  "operations": [
    {"action": "create", "path": "...", "content": "..."},
    {"action": "update", "path": "...", "content": "..."},
    {"action": "delete", "path": "..."}
  ],
  "commit_message": "Batch update"
}
```
- Atomic operation (all or nothing)
- Single commit for all changes

##### GET /search
Search memory content
- Query params:
  - `query`: string (grep pattern)
  - `prefix`: string (search within path prefix)
  - `context_lines`: int (lines around match, default 2)
  - `max_results`: int (default 50)
- Returns: Array of search results with highlighted matches

##### GET /schema
OpenAPI schema endpoint
- Returns: JSON Schema for API

##### GET /commits
List recent commits
- Query params:
  - `limit`: int (default 10)
  - `path`: string (filter by path)
- Returns: Array of commit info

### 4. Git Integration

#### Repository Management
- Service clones from `GIT_REMOTE_URL` on first startup
- After initial clone, service is the sole authoritative writer
- No pulls, fetches, or merges are performed after initial setup
- Service assumes exclusive write access to the repository

#### Commit Strategy
- Every write operation creates a commit
- Batch operations create a single commit
- Commit messages follow pattern: `{action} {path}`
- Author: `Memory Service <memory@service.local>`

#### Push Strategy
- After each successful commit, push to `GIT_REMOTE_URL`
- Push failures should be logged but not fail the write operation
- Implement exponential backoff for retries
- Queue failed pushes for later retry

### 5. Error Handling

#### HTTP Status Codes
- 200: Success
- 201: Created
- 204: No Content (delete success)
- 400: Bad Request
- 403: Forbidden (service in read-only mode, no GITHUB_TOKEN configured)
- 404: Not Found
- 409: Conflict (concurrent modification)
- 500: Internal Server Error

#### Error Response Format
```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

### 6. Performance Considerations

- Use async file operations
- Implement caching for frequently accessed paths
- Batch git operations where possible
- Stream large file responses
- Connection pooling for git operations

### 7. Security

- Validate all path inputs (prevent directory traversal)
- Sanitize file content (prevent XSS in markdown)
- Rate limiting on write operations
- Audit logging for all mutations
- CORS configuration

## Task Breakdown

### Phase 1: Core Infrastructure (Week 1)

#### 1.1 Project Setup
- [ ] Initialize UV project structure
- [ ] Configure pyproject.toml with dependencies
- [ ] Setup pre-commit hooks (ruff, autoflake)
- [ ] Create basic FastAPI application structure
- [ ] Setup pytest with asyncio fixtures

#### 1.2 Configuration & Startup
- [ ] Create configuration module with pydantic settings
- [ ] Implement startup checks (gh cli, git repo, ripgrep)
- [ ] Create read-only mode logic
- [ ] Setup logging configuration
- [ ] Implement health check endpoint

#### 1.3 Git Integration Foundation
- [ ] Create git wrapper module using GitPython or subprocess
- [ ] Implement commit creation logic
- [ ] Setup HTTP push configuration verification
- [ ] Create commit message templates
- [ ] Handle git errors gracefully

### Phase 2: Core CRUD Operations (Week 1-2)

#### 2.1 File System Operations
- [ ] Create async file read/write utilities
- [ ] Implement path validation and sanitization
- [ ] Create directory creation logic
- [ ] Setup markdown file handling

#### 2.2 Basic Endpoints
- [ ] Implement GET /memory/{path} endpoint
- [ ] Implement PUT /memory/{path} endpoint
- [ ] Implement DELETE /memory/{path} endpoint
- [ ] Add authentication middleware
- [ ] Create error handling middleware

#### 2.3 Testing Foundation
- [ ] Create test fixtures for git repo
- [ ] Write tests for CRUD operations
- [ ] Add integration tests for git commits
- [ ] Setup test coverage reporting

### Phase 3: Advanced Features (Week 2)

#### 3.1 List and Search
- [ ] Implement GET /list endpoint with filtering
- [ ] Add delimiter support for hierarchical listing
- [ ] Create ripgrep wrapper with grep fallback
- [ ] Implement GET /search endpoint
- [ ] Add search result highlighting

#### 3.2 Batch Operations
- [ ] Design batch operation schema
- [ ] Implement POST /batch endpoint
- [ ] Add transaction/rollback logic
- [ ] Create batch validation logic
- [ ] Write comprehensive batch tests

#### 3.3 Metadata and History
- [ ] Add file metadata to responses
- [ ] Implement GET /commits endpoint
- [ ] Add commit filtering by path
- [ ] Create commit info serialization

### Phase 4: Production Features (Week 3)

#### 4.1 Performance Optimization
- [ ] Implement response caching
- [ ] Add ETag support
- [ ] Create connection pooling for git
- [ ] Optimize file streaming for large files
- [ ] Add performance benchmarks

#### 4.2 Observability
- [ ] Add structured logging
- [ ] Implement metrics collection
- [ ] Create audit log for mutations
- [ ] Add request tracing
- [ ] Setup error tracking

#### 4.3 Documentation & Client Support
- [ ] Generate OpenAPI schema
- [ ] Implement GET /schema endpoint
- [ ] Create API documentation
- [ ] Write usage examples
- [ ] Create client generation guide

### Phase 5: Deployment & Operations (Week 3-4)

#### 5.1 Packaging
- [ ] Create Docker image
- [ ] Setup UV build configuration
- [ ] Create installation script for ripgrep
- [ ] Add platform detection logic
- [ ] Create deployment documentation

#### 5.2 Operations
- [ ] Add graceful shutdown handling
- [ ] Implement backup/restore procedures
- [ ] Create monitoring dashboards
- [ ] Setup CI/CD pipeline
- [ ] Write operations runbook

#### 5.3 Security Hardening
- [ ] Implement rate limiting
- [ ] Add CORS configuration
- [ ] Create security headers middleware
- [ ] Add input validation schemas
- [ ] Perform security audit

## Testing Strategy

### Unit Tests
- Path validation logic
- Git operations
- File system operations
- Search functionality

### Integration Tests
- Full CRUD cycle with git commits
- Batch operations
- Search across multiple files
- Authentication flows

### End-to-End Tests
- Complete user workflows
- Error scenarios
- Performance under load
- Concurrent operations

## Deployment Considerations

### Container Deployment
```dockerfile
FROM python:3.11-slim
# Install git, ripgrep, gh cli
# Copy application
# Run with UV
```

### Environment Configuration
All configuration via environment variables (12-factor app style):

```bash
# Required
export GIT_REMOTE_URL="https://github.com/org/agent-memory.git"
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# Optional with defaults
export MEMORY_ROOT="/var/lib/memory"  # default: ./memory
export SERVICE_PORT="8000"             # default: 8000
export SERVICE_HOST="0.0.0.0"          # default: 0.0.0.0
```

### Deployment Checklist
1. Ensure persistent volume mounted at `MEMORY_ROOT`
2. Set `GIT_REMOTE_URL` to target repository
3. Configure `GITHUB_TOKEN` with repo write permissions
4. Service will clone on first start, then manage repository independently

### Monitoring
- Health checks every 30s
- Git repository size monitoring
- API response time metrics
- Error rate alerting
- Push failure monitoring

## Success Criteria

1. All CRUD operations work with git commits
2. Search functionality performs well on large repositories
3. Batch operations are atomic
4. API is self-documenting via schema endpoint
5. Service handles concurrent requests safely
6. Read-only mode works without GITHUB_TOKEN
7. All operations are auditable via git history

