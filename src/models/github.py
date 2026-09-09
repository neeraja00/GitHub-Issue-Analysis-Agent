"""GitHub data models and representations."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """User representation in GitHub."""
    login: str
    id: Optional[int] = None
    html_url: Optional[str] = None


class GitHubLabel(BaseModel):
    """Label associated with an issue."""
    name: str
    color: Optional[str] = "ededed"
    description: Optional[str] = None


class GitHubComment(BaseModel):
    """Comment on an issue."""
    id: int
    author: str
    body: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class GitHubIssue(BaseModel):
    """Full GitHub Issue representation."""
    number: int
    title: str
    body: Optional[str] = ""
    state: str = "open"
    author: str
    labels: List[str] = Field(default_factory=list)
    comments_count: int = 0
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    html_url: str = ""
    is_pull_request: bool = False
    comments: List[GitHubComment] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Returns consolidated title and body text for analysis."""
        return f"{self.title}\n\n{self.body or ''}".strip()


class RepositoryMetadata(BaseModel):
    """Summary metadata of a GitHub repository."""
    owner: str
    repo: str
    full_name: str
    description: Optional[str] = None
    open_issues_count: int = 0
    stargazers_count: int = 0
    default_branch: str = "main"
    html_url: str = ""
