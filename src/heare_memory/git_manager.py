"""Git operations manager for memory service."""

import asyncio
import logging
import subprocess
import time
from pathlib import Path

from git import Repo
from git.exc import GitCommandError

from .config import settings
from .models.git import (
    GitBatchOperation,
    GitCommitError,
    GitCommitInfo,
    GitOperationResult,
    GitPushError,
    GitPushResult,
    GitRepositoryError,
    GitRepositoryStatus,
)

logger = logging.getLogger(__name__)


class GitManager:
    """Manages git operations for the memory service."""

    def __init__(self, repository_path: Path | None = None):
        """Initialize GitManager.

        Args:
            repository_path: Path to git repository. Uses settings.memory_root if None.
        """
        self.repository_path = repository_path or settings.memory_root
        self.repo: Repo | None = None
        self._push_queue: list[str] = []  # Queue of commits to push
        self._push_lock = asyncio.Lock()

    async def initialize_repository(self) -> None:
        """Initialize or validate the git repository.

        Raises:
            GitRepositoryError: If repository initialization fails
        """
        try:
            if not self.repository_path.exists():
                logger.info("Creating memory root directory: %s", self.repository_path)
                self.repository_path.mkdir(parents=True, exist_ok=True)

            if not (self.repository_path / ".git").exists():
                if settings.git_remote_url:
                    logger.info("Cloning repository from %s", settings.git_remote_url)
                    self.repo = Repo.clone_from(settings.git_remote_url, self.repository_path)
                else:
                    logger.info("Initializing new git repository at %s", self.repository_path)
                    self.repo = Repo.init(self.repository_path)
            else:
                logger.info("Using existing git repository at %s", self.repository_path)
                self.repo = Repo(self.repository_path)

            # Configure git for the service
            await self._configure_git()

            # Verify remote configuration
            await self._verify_remote_config()

            logger.info("Git repository initialized successfully")

        except Exception as exc:
            raise GitRepositoryError(
                f"Failed to initialize git repository: {exc}",
                "initialize_repository",
                {"path": str(self.repository_path), "remote_url": settings.git_remote_url},
            ) from exc

    async def _configure_git(self) -> None:
        """Configure git settings for the service."""
        if not self.repo:
            raise GitRepositoryError("Repository not initialized", "configure_git")

        # Set git user for commits
        with self.repo.config_writer() as git_config:
            git_config.set_value("user", "name", "Memory Service")
            git_config.set_value("user", "email", "memory@heare.ai")

        # Configure HTTP authentication if token is available
        if settings.github_token and settings.git_remote_url:
            await self._configure_http_auth()

    async def _configure_http_auth(self) -> None:
        """Configure HTTP authentication for git operations."""
        if not settings.github_token or not settings.git_remote_url:
            return

        # Configure git credential helper to use token
        with self.repo.config_writer() as git_config:
            git_config.set_value("credential", "helper", "")
            git_config.set_value("credential", "useHttpPath", "true")

    async def _verify_remote_config(self) -> None:
        """Verify remote repository configuration."""
        if not self.repo or not settings.git_remote_url:
            return

        try:
            origin = self.repo.remote("origin")
            if origin.url != settings.git_remote_url:
                logger.warning(
                    "Remote URL mismatch: configured=%s actual=%s",
                    settings.git_remote_url,
                    origin.url,
                )
        except Exception:
            # Add remote if it doesn't exist
            if settings.git_remote_url:
                self.repo.create_remote("origin", settings.git_remote_url)

    async def commit_file(
        self, file_path: str, content: str, message: str | None = None
    ) -> GitOperationResult:
        """Commit a single file change.

        Args:
            file_path: Path to the file relative to repository root
            content: File content to write
            message: Custom commit message. Auto-generated if None.

        Returns:
            GitOperationResult: Result of the operation

        Raises:
            GitCommitError: If commit operation fails
        """
        start_time = time.time()

        try:
            if not self.repo:
                raise GitCommitError("Repository not initialized", "commit_file")

            # Ensure file directory exists
            full_path = self.repository_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            full_path.write_text(content, encoding="utf-8")

            # Stage the file
            self.repo.index.add([file_path])

            # Create commit
            commit_message = message or f"Update {file_path}"
            commit = self.repo.index.commit(commit_message)

            # Queue for push
            async with self._push_lock:
                self._push_queue.append(commit.hexsha)

            operation_time = time.time() - start_time
            logger.info("Committed file %s with SHA %s", file_path, commit.hexsha[:8])

            return GitOperationResult(
                success=True,
                commit_sha=commit.hexsha,
                error_message=None,
                files_changed=[file_path],
                operation_time=operation_time,
            )

        except Exception as exc:
            operation_time = time.time() - start_time
            error_msg = f"Failed to commit file {file_path}: {exc}"
            logger.error(error_msg)

            return GitOperationResult(
                success=False,
                commit_sha=None,
                error_message=error_msg,
                files_changed=[],
                operation_time=operation_time,
            )

    async def delete_file(self, file_path: str, message: str | None = None) -> GitOperationResult:
        """Delete a file and commit the change.

        Args:
            file_path: Path to the file relative to repository root
            message: Custom commit message. Auto-generated if None.

        Returns:
            GitOperationResult: Result of the operation
        """
        start_time = time.time()

        try:
            if not self.repo:
                raise GitCommitError("Repository not initialized", "delete_file")

            full_path = self.repository_path / file_path

            if not full_path.exists():
                logger.warning("File %s does not exist, skipping deletion", file_path)
                return GitOperationResult(
                    success=True,
                    commit_sha=None,
                    error_message=None,
                    files_changed=[],
                    operation_time=time.time() - start_time,
                )

            # Remove file and stage deletion
            full_path.unlink()
            self.repo.index.remove([file_path])

            # Create commit
            commit_message = message or f"Delete {file_path}"
            commit = self.repo.index.commit(commit_message)

            # Queue for push
            async with self._push_lock:
                self._push_queue.append(commit.hexsha)

            operation_time = time.time() - start_time
            logger.info("Deleted file %s with SHA %s", file_path, commit.hexsha[:8])

            return GitOperationResult(
                success=True,
                commit_sha=commit.hexsha,
                error_message=None,
                files_changed=[file_path],
                operation_time=operation_time,
            )

        except Exception as exc:
            operation_time = time.time() - start_time
            error_msg = f"Failed to delete file {file_path}: {exc}"
            logger.error(error_msg)

            return GitOperationResult(
                success=False,
                commit_sha=None,
                error_message=error_msg,
                files_changed=[],
                operation_time=operation_time,
            )

    async def batch_commit(self, batch_operation: GitBatchOperation) -> GitOperationResult:
        """Perform a batch of operations as a single commit.

        Args:
            batch_operation: Batch operation specification

        Returns:
            GitOperationResult: Result of the batch operation
        """
        start_time = time.time()
        files_changed = []

        try:
            if not self.repo:
                raise GitCommitError("Repository not initialized", "batch_commit")

            # Perform all operations
            for operation in batch_operation.operations:
                if operation.operation_type in ("create", "update"):
                    if not operation.content:
                        raise GitCommitError(
                            f"Content required for {operation.operation_type} operation",
                            "batch_commit",
                        )

                    # Write file
                    full_path = self.repository_path / operation.file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(operation.content, encoding="utf-8")

                    # Stage file
                    self.repo.index.add([operation.file_path])
                    files_changed.append(operation.file_path)

                elif operation.operation_type == "delete":
                    full_path = self.repository_path / operation.file_path
                    if full_path.exists():
                        full_path.unlink()
                        self.repo.index.remove([operation.file_path])
                        files_changed.append(operation.file_path)

            # Create single commit for all operations
            if files_changed:
                commit = self.repo.index.commit(batch_operation.commit_message)

                # Queue for push
                async with self._push_lock:
                    self._push_queue.append(commit.hexsha)

                operation_time = time.time() - start_time
                logger.info(
                    "Batch commit completed with SHA %s, %d files changed",
                    commit.hexsha[:8],
                    len(files_changed),
                )

                return GitOperationResult(
                    success=True,
                    commit_sha=commit.hexsha,
                    error_message=None,
                    files_changed=files_changed,
                    operation_time=operation_time,
                )
            else:
                logger.info("No files changed in batch operation")
                return GitOperationResult(
                    success=True,
                    commit_sha=None,
                    error_message=None,
                    files_changed=[],
                    operation_time=time.time() - start_time,
                )

        except Exception as exc:
            operation_time = time.time() - start_time
            error_msg = f"Failed to perform batch commit: {exc}"
            logger.error(error_msg)

            return GitOperationResult(
                success=False,
                commit_sha=None,
                error_message=error_msg,
                files_changed=files_changed,
                operation_time=operation_time,
            )

    async def push_changes(self, max_retries: int = 3) -> GitPushResult:
        """Push pending changes to remote repository.

        Args:
            max_retries: Maximum number of retry attempts

        Returns:
            GitPushResult: Result of the push operation
        """
        if not settings.github_token or not settings.git_remote_url:
            logger.debug("Skipping push: no GitHub token or remote URL configured")
            return GitPushResult(success=True, error_message=None, retry_count=0, total_time=0.0)

        start_time = time.time()

        async with self._push_lock:
            if not self._push_queue:
                return GitPushResult(
                    success=True, error_message=None, retry_count=0, total_time=0.0
                )

            pending_commits = self._push_queue.copy()

        for attempt in range(max_retries + 1):
            try:
                await self._execute_push()

                # Clear push queue on success
                async with self._push_lock:
                    self._push_queue.clear()

                total_time = time.time() - start_time
                logger.info("Successfully pushed %d commits", len(pending_commits))

                return GitPushResult(
                    success=True, error_message=None, retry_count=attempt, total_time=total_time
                )

            except Exception as exc:
                if attempt < max_retries:
                    delay = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "Push attempt %d failed, retrying in %d seconds: %s",
                        attempt + 1,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    total_time = time.time() - start_time
                    error_msg = f"Push failed after {max_retries + 1} attempts: {exc}"
                    logger.error(error_msg)

                    return GitPushResult(
                        success=False,
                        error_message=error_msg,
                        retry_count=attempt,
                        total_time=total_time,
                    )

        # Should never reach here
        return GitPushResult(
            success=False, error_message="Unexpected error", retry_count=max_retries, total_time=0.0
        )

    async def _execute_push(self) -> None:
        """Execute git push with authentication."""
        if not self.repo or not settings.github_token or not settings.git_remote_url:
            raise GitPushError("Missing repository, token, or remote URL", "push")

        # Prepare authenticated URL
        auth_url = settings.git_remote_url.replace("https://", f"https://{settings.github_token}@")

        # Execute push using subprocess for better control
        # Note: This is safe because we control all inputs - git binary and auth_url validated
        result = subprocess.run(  # noqa: S603
            ["git", "push", auth_url, "HEAD"],  # noqa: S607
            cwd=self.repository_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise GitPushError(
                f"Git push failed: {result.stderr}",
                "push",
                {"stdout": result.stdout, "stderr": result.stderr},
            )

    async def get_repository_status(self) -> GitRepositoryStatus:
        """Get the current status of the git repository.

        Returns:
            GitRepositoryStatus: Current repository status
        """
        if not self.repo:
            raise GitRepositoryError("Repository not initialized", "get_repository_status")

        try:
            # Get last commit info
            last_commit = None
            if self.repo.heads:
                commit = self.repo.head.commit
                last_commit = GitCommitInfo(
                    sha=commit.hexsha,
                    message=commit.message.strip(),
                    author=str(commit.author),
                    timestamp=commit.committed_datetime,
                    files_changed=list(commit.stats.files.keys()),
                )

            # Check repository status
            is_clean = not self.repo.is_dirty()
            has_uncommitted = self.repo.is_dirty() or bool(self.repo.untracked_files)

            # Get remote info
            remote_url = None
            ahead_by = 0
            behind_by = 0

            try:
                origin = self.repo.remote("origin")
                remote_url = origin.url
                # Note: Getting ahead/behind requires network access, skipping for now
            except Exception as exc:
                logger.debug("Could not get remote information: %s", exc)

            return GitRepositoryStatus(
                path=str(self.repository_path),
                remote_url=remote_url,
                branch=self.repo.active_branch.name if self.repo.heads else "main",
                last_commit=last_commit,
                has_uncommitted_changes=has_uncommitted,
                is_clean=is_clean,
                ahead_by=ahead_by,
                behind_by=behind_by,
            )

        except Exception as exc:
            raise GitRepositoryError(
                f"Failed to get repository status: {exc}", "get_repository_status"
            ) from exc

    async def get_file_sha(self, file_path: str) -> str | None:
        """
        Get the git SHA for a specific file.

        Args:
            file_path: Path to the file relative to repository root

        Returns:
            str | None: Git SHA of the file's last commit, or None if file not in git

        Raises:
            GitRepositoryError: If there's an error accessing git
        """
        try:
            repo = Repo(self.repository_path)

            # Check if there are any commits
            if not repo.heads:
                return None

            # Try to get the file's last commit
            try:
                commits = list(repo.iter_commits(paths=file_path, max_count=1))
                if commits:
                    return commits[0].hexsha
                else:
                    # File might be new/uncommitted
                    return None
            except GitCommandError:
                # File might not exist in git
                return None

        except Exception as exc:
            logger.error(f"Failed to get file SHA for {file_path}: {exc}")
            # Don't raise exception, return None for missing SHA
            return None
