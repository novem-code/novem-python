"""
GraphQL client for novem CLI utility operations.

This module handles GraphQL queries for listing operations (plots, grids, mails, etc.)
while the core data operations remain REST-based.
"""

import json
import re
from typing import Any, Dict, List, Optional

import requests

from ..utils import API_ROOT, get_current_config


def _get_gql_endpoint(api_root: str) -> str:
    """Convert REST API root to GraphQL endpoint by replacing /v1 with /gql."""
    # Remove trailing slash if present, then replace /v1 with /gql
    api_root = api_root.rstrip("/")
    return re.sub(r"/v\d+$", "/gql", api_root)


class NovemGQL:
    """GraphQL client for novem CLI operations."""

    def __init__(self, **kwargs: Any) -> None:
        _, config = get_current_config(**kwargs)
        self._config = config
        self._session = requests.Session()
        self._debug = kwargs.get("debug", False)
        self._gql_debug = kwargs.get("gql_debug", False)

        token = config.get("token")
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})

        api_root = config.get("api_root") or API_ROOT
        self._endpoint = _get_gql_endpoint(api_root)

        if self._debug:
            print(f"GQL endpoint: {self._endpoint}")

    def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return the result."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        if self._debug:
            print(f"GQL query: {query.strip()}")
            if variables:
                print(f"GQL variables: {variables}")

        response = self._session.post(self._endpoint, json=payload)
        response.raise_for_status()
        result = response.json()

        if self._gql_debug:
            print(json.dumps(result, indent=2))
            raise SystemExit(0)

        if "errors" in result:
            raise Exception(f"GraphQL error: {result['errors']}")

        return result.get("data", {})


# GraphQL query for listing plots/grids/mails
LIST_VIS_QUERY = """
query ListVis($author: String, $limit: Int, $offset: Int) {
  plots(author: $author, limit: $limit, offset: $offset) {
    id
    name
    type
    summary
    url
    updated
    public
    shared {
      id
      name
      type
    }
    tags {
      id
      name
      type
    }
  }
}
"""

LIST_GRIDS_QUERY = """
query ListGrids($author: String, $limit: Int, $offset: Int) {
  grids(author: $author, limit: $limit, offset: $offset) {
    id
    name
    type
    summary
    url
    updated
    public
    shared {
      id
      name
      type
    }
    tags {
      id
      name
      type
    }
  }
}
"""

LIST_MAILS_QUERY = """
query ListMails($author: String, $limit: Int, $offset: Int) {
  mails(author: $author, limit: $limit, offset: $offset) {
    id
    name
    type
    summary
    url
    updated
    public
    shared {
      id
      name
      type
    }
    tags {
      id
      name
      type
    }
  }
}
"""

LIST_JOBS_QUERY = """
query ListJobs($author: String, $limit: Int, $offset: Int) {
  jobs(author: $author, limit: $limit, offset: $offset) {
    id
    name
    type
    summary
    url
    updated
    public
    shared {
      id
      name
      type
    }
    tags {
      id
      name
      type
    }
    last_run_status
    run_count
    job_steps
    current_step
    schedule
    triggers
  }
}
"""


LIST_USERS_QUERY = """
query ListUsers($limit: Int, $offset: Int) {
  users(limit: $limit, offset: $offset) {
    username
    name
    type
    bio
    public
    relationship {
      orgs
      groups
      follower
      connected
      following
      ignoring
    }
    social {
      followers
      following
      connections
    }
    plots {
      id
    }
    grids {
      id
    }
    mails {
      id
    }
    docs {
      id
    }
    repos {
      id
    }
    jobs {
      id
    }
  }
}
"""


def _transform_shared(public: bool, shared: List[Dict[str, Any]]) -> List[str]:
    """
    Transform GraphQL shared format to REST format.

    GraphQL: public (bool) + shared ([{id, name, type}])
    REST: ["public", "@", "+", ...]

    The share_fmt function only checks the first character of each item,
    so we just need the prefix: "public" -> P, "@" -> @, "+" -> +
    """
    result: List[str] = []

    if public:
        result.append("public")

    for group in shared:
        group_type = group.get("type", "")

        if group_type == "user_group":
            result.append("@")
        elif group_type == "org_group":
            result.append("+")
        elif group_type == "org":
            result.append("+")

    return result


def _get_markers(tags: List[Dict[str, Any]]) -> str:
    """Return combined fav/like marker string: '*', '+', '*+', or ''."""
    fav = "*" if any(tag.get("id") == "fav" for tag in tags) else ""
    like = "+" if any(tag.get("id") == "like" for tag in tags) else ""
    return fav + like


def _transform_vis_response(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform GraphQL visualization response to match REST format.

    Transforms:
    - url -> uri
    - public + shared -> shared (list of strings)
    - tags -> is_fav (bool)
    """
    result = []
    for item in items:
        transformed = {
            "id": item.get("id", ""),
            "name": item.get("name", "") or "",
            "type": item.get("type", ""),
            "summary": item.get("summary"),
            "uri": item.get("url", ""),
            "updated": item.get("updated", ""),
            "shared": _transform_shared(item.get("public", False), item.get("shared", [])),
            "fav": _get_markers(item.get("tags", [])),
        }
        result.append(transformed)
    return result


def list_plots_gql(gql: NovemGQL, author: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List plots via GraphQL, returning REST-compatible format."""
    variables: Dict[str, Any] = {}
    if author:
        variables["author"] = author
    if limit:
        variables["limit"] = limit

    data = gql._query(LIST_VIS_QUERY, variables)
    plots = data.get("plots", [])
    return _transform_vis_response(plots)


def list_grids_gql(gql: NovemGQL, author: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List grids via GraphQL, returning REST-compatible format."""
    variables: Dict[str, Any] = {}
    if author:
        variables["author"] = author
    if limit:
        variables["limit"] = limit

    data = gql._query(LIST_GRIDS_QUERY, variables)
    grids = data.get("grids", [])
    return _transform_vis_response(grids)


def list_mails_gql(gql: NovemGQL, author: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List mails via GraphQL, returning REST-compatible format."""
    variables: Dict[str, Any] = {}
    if author:
        variables["author"] = author
    if limit:
        variables["limit"] = limit

    data = gql._query(LIST_MAILS_QUERY, variables)
    mails = data.get("mails", [])
    return _transform_vis_response(mails)


def _transform_jobs_response(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform GraphQL jobs response for job listing.

    Includes job-specific fields: last_run_status, run_count, job_steps, current_step, schedule, triggers.
    """
    result = []
    for item in items:
        transformed = {
            "id": item.get("id", ""),
            "name": item.get("name", "") or "",
            "type": item.get("type", ""),
            "summary": item.get("summary"),
            "uri": item.get("url", ""),
            "updated": item.get("updated", ""),
            "shared": _transform_shared(item.get("public", False), item.get("shared", [])),
            "fav": _get_markers(item.get("tags", [])),
            "last_run_status": item.get("last_run_status", ""),
            "run_count": item.get("run_count", 0),
            "job_steps": item.get("job_steps", 0),
            "current_step": item.get("current_step"),
            "schedule": item.get("schedule", ""),
            "triggers": item.get("triggers", []),
        }
        result.append(transformed)
    return result


def list_jobs_gql(gql: NovemGQL, author: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List jobs via GraphQL, returning REST-compatible format."""
    variables: Dict[str, Any] = {}
    if author:
        variables["author"] = author
    if limit:
        variables["limit"] = limit

    data = gql._query(LIST_JOBS_QUERY, variables)
    jobs = data.get("jobs", [])
    return _transform_jobs_response(jobs)


def _transform_users_response(users: List[Dict[str, Any]], me_type: str) -> List[Dict[str, Any]]:
    """
    Transform GraphQL users response for user listing.

    Includes user fields: username, name, type, bio, relationship, social, and content counts.
    """
    result = []
    for user in users:
        relationship = user.get("relationship", {}) or {}
        social = user.get("social", {}) or {}

        transformed = {
            "username": user.get("username", ""),
            "name": user.get("name", "") or "",
            "type": user.get("type", ""),
            "bio": user.get("bio", "") or "",
            "public": user.get("public", False),
            # Relationship fields
            "connected": relationship.get("connected", False),
            "follower": relationship.get("follower", False),
            "following": relationship.get("following", False),
            "ignoring": relationship.get("ignoring", False),
            "orgs": relationship.get("orgs", 0) or 0,
            "groups": relationship.get("groups", 0) or 0,
            # Social fields
            "social_connections": social.get("connections", 0) or 0,
            "social_followers": social.get("followers", 0) or 0,
            "social_following": social.get("following", 0) or 0,
            # Content counts
            "plots": len(user.get("plots", []) or []),
            "grids": len(user.get("grids", []) or []),
            "mails": len(user.get("mails", []) or []),
            "docs": len(user.get("docs", []) or []),
            "repos": len(user.get("repos", []) or []),
            "jobs": len(user.get("jobs", []) or []),
            # Verified status (VERIFIED or NOVEM type)
            "verified": user.get("type", "") in ["VERIFIED", "NOVEM", "SYSTEM"],
        }
        result.append(transformed)
    return result


def list_users_gql(gql: NovemGQL, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List all users via GraphQL, returning transformed format."""
    variables: Dict[str, Any] = {}
    if limit:
        variables["limit"] = limit

    data = gql._query(LIST_USERS_QUERY, variables if variables else None)
    users = data.get("users", [])
    return _transform_users_response(users, "")
