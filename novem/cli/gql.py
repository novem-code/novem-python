"""
GraphQL client for novem CLI utility operations.

This module handles GraphQL queries for listing operations (plots, grids, mails, etc.)
while the core data operations remain REST-based.
"""

import datetime
import json
import re
import shutil
import textwrap
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from ..utils import API_ROOT, cl, colors, get_current_config, parse_api_datetime


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
        # Support both old gql_debug and new gql parameter for debug mode
        gql_param = kwargs.get("gql", False)
        self._gql_debug = gql_param is True  # True when --gql with no argument

        token = config.get("token")
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})

        api_root = config.get("api_root") or API_ROOT
        self._endpoint = _get_gql_endpoint(api_root)

        if self._debug:
            print(f"GQL endpoint: {self._endpoint}")

    def run_raw_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return the raw result (for CLI --gql @filename)."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        if self._debug:
            print(f"GQL query: {query.strip()}")
            if variables:
                print(f"GQL variables: {variables}")

        response = self._session.post(self._endpoint, json=payload)
        response.raise_for_status()
        return response.json()

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
    social {
      views
    }
    topics {
      num_comments
      num_likes
      num_dislikes
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
    social {
      views
    }
    topics {
      num_comments
      num_likes
      num_dislikes
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
    social {
      views
    }
    topics {
      num_comments
      num_likes
      num_dislikes
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
    social {
      views
    }
    topics {
      num_comments
      num_likes
      num_dislikes
    }
    last_run_status
    last_run_time
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
        # GraphQL enums may be returned in uppercase, so normalize to lowercase
        group_type = group.get("type", "").lower()

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


def _aggregate_activity(item: Dict[str, Any]) -> Dict[str, int]:
    """Sum topic-level comments, likes, and dislikes for a visualization."""
    topics = item.get("topics", []) or []
    return {
        "_comments": sum(t.get("num_comments", 0) for t in topics) + len(topics),
        "_likes": sum(t.get("num_likes", 0) for t in topics),
        "_dislikes": sum(t.get("num_dislikes", 0) for t in topics),
    }


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
            "_views": (item.get("social") or {}).get("views", 0),
            **_aggregate_activity(item),
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

    Includes job-specific fields: last_run_status, last_run_time, run_count, job_steps,
    current_step, schedule, triggers.
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
            "_views": (item.get("social") or {}).get("views", 0),
            "last_run_status": item.get("last_run_status", ""),
            "last_run_time": item.get("last_run_time", ""),
            "run_count": item.get("run_count", 0),
            "job_steps": item.get("job_steps", 0),
            "current_step": item.get("current_step"),
            "schedule": item.get("schedule", ""),
            "triggers": item.get("triggers", []),
            **_aggregate_activity(item),
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


LIST_ORGS_QUERY = """
query ListOrgs {
  me {
    founder {
      id
      type
      name
      public
      is_open
      enable_subdomain
      groups {
        id
        plots { id author { username } }
        grids { id author { username } }
        mails { id author { username } }
        docs { id author { username } }
        repos { id author { username } }
        jobs { id author { username } }
      }
      founders { username }
      admins { username }
      superusers { username }
      members { username }
      created
    }
    admin {
      id
      type
      name
      public
      is_open
      enable_subdomain
      groups {
        id
        plots { id author { username } }
        grids { id author { username } }
        mails { id author { username } }
        docs { id author { username } }
        repos { id author { username } }
        jobs { id author { username } }
      }
      founders { username }
      admins { username }
      superusers { username }
      members { username }
      created
    }
    superuser {
      id
      type
      name
      public
      is_open
      enable_subdomain
      groups {
        id
        plots { id author { username } }
        grids { id author { username } }
        mails { id author { username } }
        docs { id author { username } }
        repos { id author { username } }
        jobs { id author { username } }
      }
      founders { username }
      admins { username }
      superusers { username }
      members { username }
      created
    }
    member {
      id
      type
      name
      public
      is_open
      enable_subdomain
      groups {
        id
        plots { id author { username } }
        grids { id author { username } }
        mails { id author { username } }
        docs { id author { username } }
        repos { id author { username } }
        jobs { id author { username } }
      }
      founders { username }
      admins { username }
      superusers { username }
      members { username }
      created
    }
  }
}
"""


def _transform_orgs_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform GraphQL org response into flat format for display."""
    me = data.get("me", {}) or {}
    result: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    # Process each role list, highest role first
    role_priority = ["founder", "admin", "superuser", "member"]

    for role in role_priority:
        groups = me.get(role, []) or []
        for group in groups:
            # Only include orgs (not org_groups or user_groups)
            if group.get("type") != "org":
                continue
            # Skip if already seen (user has multiple roles, use highest)
            if group.get("id") in seen_ids:
                continue
            seen_ids.add(group.get("id"))

            # Sum all member types for total member count
            members_count = (
                len(group.get("founders", []) or [])
                + len(group.get("admins", []) or [])
                + len(group.get("superusers", []) or [])
                + len(group.get("members", []) or [])
            )

            # Count vis across all org groups (deduplicated by author/id)
            vis_types = ["plots", "grids", "mails", "docs", "repos", "jobs"]
            vis_counts: Dict[str, Set[str]] = {vt: set() for vt in vis_types}

            org_groups = group.get("groups", []) or []
            for org_group in org_groups:
                for vis_type in vis_types:
                    for vis in org_group.get(vis_type, []) or []:
                        vis_id = vis.get("id", "")
                        author = vis.get("author", {}) or {}
                        author_username = author.get("username", "")
                        if vis_id and author_username:
                            # Use author/id as unique key since IDs are user-scoped
                            vis_counts[vis_type].add(f"{author_username}/{vis_id}")

            transformed = {
                "id": group.get("id", ""),
                "name": group.get("name", "") or "",
                "role": role,
                "public": group.get("public") or False,
                "is_open": group.get("is_open") or False,
                "enable_subdomain": group.get("enable_subdomain") or False,
                "groups_count": len(org_groups),
                "members_count": members_count,
                "plots": len(vis_counts["plots"]),
                "grids": len(vis_counts["grids"]),
                "mails": len(vis_counts["mails"]),
                "docs": len(vis_counts["docs"]),
                "repos": len(vis_counts["repos"]),
                "jobs": len(vis_counts["jobs"]),
                "created": group.get("created", "") or "",
            }
            result.append(transformed)

    return result


def list_orgs_gql(gql: NovemGQL) -> List[Dict[str, Any]]:
    """List user's orgs via GraphQL, returning transformed format."""
    data = gql._query(LIST_ORGS_QUERY)
    return _transform_orgs_response(data)


LIST_ORG_MEMBERS_QUERY = """
query ListOrgMembers($orgId: ID!) {
  groups(id: $orgId, type: org) {
    id
    founders {
      username
      name
      type
      public
      relationship {
        follower
        connected
        following
        ignoring
      }
    }
    admins {
      username
      name
      type
      public
      relationship {
        follower
        connected
        following
        ignoring
      }
    }
    superusers {
      username
      name
      type
      public
      relationship {
        follower
        connected
        following
        ignoring
      }
    }
    members {
      username
      name
      type
      public
      relationship {
        follower
        connected
        following
        ignoring
      }
    }
    invited {
      admins {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      superusers {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      members {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
    }
    groups {
      id
      plots { id author { username } }
      grids { id author { username } }
      mails { id author { username } }
      docs { id author { username } }
      repos { id author { username } }
      jobs { id author { username } }
    }
  }
}
"""


def _transform_org_members_response(data: Dict[str, Any], current_user: str) -> List[Dict[str, Any]]:
    """
    Transform GraphQL org members response for display.

    Extracts members from each role list, deduplicates by highest role,
    and counts vis shared with org groups per user.
    """
    groups_list = data.get("groups", []) or []
    if not groups_list:
        return []

    org = groups_list[0]

    # Role priority: founder > admin > superuser > member
    role_priority = ["founder", "admin", "superuser", "member"]
    role_fields = ["founders", "admins", "superusers", "members"]

    # Build member dict with highest role (deduped)
    members: Dict[str, Dict[str, Any]] = {}
    for role, field in zip(role_priority, role_fields):
        for user in org.get(field, []) or []:
            username = user.get("username", "")
            if username and username not in members:
                relationship = user.get("relationship", {}) or {}
                members[username] = {
                    "username": username,
                    "name": user.get("name", "") or "",
                    "type": user.get("type", "REGULAR"),
                    "public": user.get("public") or False,
                    "role": role,
                    "connected": relationship.get("connected") or False,
                    "follower": relationship.get("follower") or False,
                    "following": relationship.get("following") or False,
                    "ignoring": relationship.get("ignoring") or False,
                    # Initialize vis counts
                    "plots": set(),
                    "grids": set(),
                    "mails": set(),
                    "docs": set(),
                    "repos": set(),
                    "jobs": set(),
                }

    # Process invited users (role with ? suffix)
    invited = org.get("invited", {}) or {}
    invited_role_map = [("admin?", "admins"), ("superuser?", "superusers"), ("member?", "members")]
    for role, field in invited_role_map:
        for user in invited.get(field, []) or []:
            username = user.get("username", "")
            if username and username not in members:
                relationship = user.get("relationship", {}) or {}
                members[username] = {
                    "username": username,
                    "name": user.get("name", "") or "",
                    "type": user.get("type", "REGULAR"),
                    "public": user.get("public") or False,
                    "role": role,
                    "connected": relationship.get("connected") or False,
                    "follower": relationship.get("follower") or False,
                    "following": relationship.get("following") or False,
                    "ignoring": relationship.get("ignoring") or False,
                    # Initialize vis counts
                    "plots": set(),
                    "grids": set(),
                    "mails": set(),
                    "docs": set(),
                    "repos": set(),
                    "jobs": set(),
                }

    # Collect vis IDs per user from org groups
    vis_types = ["plots", "grids", "mails", "docs", "repos", "jobs"]
    org_groups = org.get("groups", []) or []

    for group in org_groups:
        for vis_type in vis_types:
            for vis in group.get(vis_type, []) or []:
                author = vis.get("author", {}) or {}
                author_username = author.get("username", "")
                vis_id = vis.get("id", "")
                if author_username in members and vis_id:
                    members[author_username][vis_type].add(vis_id)

    # Convert sets to counts and return as list
    result = []
    for username, member in members.items():
        member_data = {
            "username": member["username"],
            "name": member["name"],
            "type": member["type"],
            "public": member["public"],
            "role": member["role"],
            "connected": member["connected"],
            "follower": member["follower"],
            "following": member["following"],
            "ignoring": member["ignoring"],
            "plots": len(member["plots"]),
            "grids": len(member["grids"]),
            "mails": len(member["mails"]),
            "docs": len(member["docs"]),
            "repos": len(member["repos"]),
            "jobs": len(member["jobs"]),
            "is_me": username == current_user,
        }
        result.append(member_data)

    return result


def list_org_members_gql(gql: NovemGQL, org_id: str, current_user: str) -> List[Dict[str, Any]]:
    """List org members via GraphQL, returning transformed format with vis counts."""
    variables = {"orgId": org_id}
    data = gql._query(LIST_ORG_MEMBERS_QUERY, variables)
    return _transform_org_members_response(data, current_user)


LIST_ORG_GROUPS_QUERY = """
query ListOrgGroups($orgId: ID!) {
  groups(id: $orgId, type: org) {
    id
    groups {
      id
      name
      public
      is_open
      allow_inbound_mail
      mail_verify_spf
      mail_verify_dkim
      founders { username }
      admins { username }
      superusers { username }
      members { username }
      plots { id author { username } }
      grids { id author { username } }
      mails { id author { username } }
      docs { id author { username } }
      repos { id author { username } }
      jobs { id author { username } }
      created
    }
  }
}
"""


def _transform_org_groups_response(data: Dict[str, Any], current_user: str) -> List[Dict[str, Any]]:
    """Transform GraphQL org groups response for display."""
    groups_list = data.get("groups", []) or []
    if not groups_list:
        return []

    org = groups_list[0]
    org_groups = org.get("groups", []) or []
    result: List[Dict[str, Any]] = []

    for group in org_groups:
        # Sum all member types for total member count
        members_count = (
            len(group.get("founders", []) or [])
            + len(group.get("admins", []) or [])
            + len(group.get("superusers", []) or [])
            + len(group.get("members", []) or [])
        )

        # Determine current user's role in this group
        role = ""
        role_fields = [("founder", "founders"), ("admin", "admins"), ("superuser", "superusers"), ("member", "members")]
        for role_name, field in role_fields:
            users = group.get(field, []) or []
            if any(u.get("username") == current_user for u in users):
                role = role_name
                break

        # Count vis (deduplicated by author/id)
        vis_types = ["plots", "grids", "mails", "docs", "repos", "jobs"]
        vis_counts: Dict[str, Set[str]] = {vt: set() for vt in vis_types}

        for vis_type in vis_types:
            for vis in group.get(vis_type, []) or []:
                vis_id = vis.get("id", "")
                author = vis.get("author", {}) or {}
                author_username = author.get("username", "")
                if vis_id and author_username:
                    vis_counts[vis_type].add(f"{author_username}/{vis_id}")

        transformed = {
            "id": group.get("id", ""),
            "name": group.get("name", "") or "",
            "role": role,
            "public": group.get("public") or False,
            "is_open": group.get("is_open") or False,
            "allow_inbound_mail": group.get("allow_inbound_mail") or False,
            "mail_verify_spf": group.get("mail_verify_spf") or False,
            "mail_verify_dkim": group.get("mail_verify_dkim") or False,
            "members_count": members_count,
            "plots": len(vis_counts["plots"]),
            "grids": len(vis_counts["grids"]),
            "mails": len(vis_counts["mails"]),
            "docs": len(vis_counts["docs"]),
            "repos": len(vis_counts["repos"]),
            "jobs": len(vis_counts["jobs"]),
            "created": group.get("created", "") or "",
        }
        result.append(transformed)

    return result


def list_org_groups_gql(gql: NovemGQL, org_id: str, current_user: str) -> List[Dict[str, Any]]:
    """List org's groups via GraphQL, returning transformed format."""
    variables = {"orgId": org_id}
    data = gql._query(LIST_ORG_GROUPS_QUERY, variables)
    return _transform_org_groups_response(data, current_user)


LIST_ORG_GROUP_MEMBERS_QUERY = """
query ListOrgGroupMembers($orgId: ID!) {
  groups(id: $orgId, type: org) {
    id
    groups {
      id
      name
      founders {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      admins {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      superusers {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      members {
        username
        name
        type
        public
        relationship {
          follower
          connected
          following
          ignoring
        }
      }
      invited {
        admins {
          username
          name
          type
          public
          relationship {
            follower
            connected
            following
            ignoring
          }
        }
        superusers {
          username
          name
          type
          public
          relationship {
            follower
            connected
            following
            ignoring
          }
        }
        members {
          username
          name
          type
          public
          relationship {
            follower
            connected
            following
            ignoring
          }
        }
      }
      plots { id author { username } }
      grids { id author { username } }
      mails { id author { username } }
      docs { id author { username } }
      repos { id author { username } }
      jobs { id author { username } }
    }
  }
}
"""


def _transform_org_group_members_response(
    data: Dict[str, Any], group_id: str, current_user: str
) -> List[Dict[str, Any]]:
    """
    Transform GraphQL org group members response for display.

    Similar to org members but for a specific group, counting vis shared with this group.
    """
    groups_list = data.get("groups", []) or []
    if not groups_list:
        return []

    org = groups_list[0]
    org_groups = org.get("groups", []) or []

    # Find the specific group by ID
    group = None
    for g in org_groups:
        if g.get("id") == group_id:
            group = g
            break

    if not group:
        return []

    # Role priority: founder > admin > superuser > member
    role_priority = ["founder", "admin", "superuser", "member"]
    role_fields = ["founders", "admins", "superusers", "members"]

    # Build member dict with highest role (deduped)
    members: Dict[str, Dict[str, Any]] = {}
    for role, field in zip(role_priority, role_fields):
        for user in group.get(field, []) or []:
            username = user.get("username", "")
            if username and username not in members:
                relationship = user.get("relationship", {}) or {}
                members[username] = {
                    "username": username,
                    "name": user.get("name", "") or "",
                    "type": user.get("type", "REGULAR"),
                    "public": user.get("public") or False,
                    "role": role,
                    "connected": relationship.get("connected") or False,
                    "follower": relationship.get("follower") or False,
                    "following": relationship.get("following") or False,
                    "ignoring": relationship.get("ignoring") or False,
                    # Initialize vis counts as sets for deduplication
                    "plots": set(),
                    "grids": set(),
                    "mails": set(),
                    "docs": set(),
                    "repos": set(),
                    "jobs": set(),
                }

    # Process invited users (role with ? suffix)
    invited = group.get("invited", {}) or {}
    invited_role_map = [("admin?", "admins"), ("superuser?", "superusers"), ("member?", "members")]
    for role, field in invited_role_map:
        for user in invited.get(field, []) or []:
            username = user.get("username", "")
            if username and username not in members:
                relationship = user.get("relationship", {}) or {}
                members[username] = {
                    "username": username,
                    "name": user.get("name", "") or "",
                    "type": user.get("type", "REGULAR"),
                    "public": user.get("public") or False,
                    "role": role,
                    "connected": relationship.get("connected") or False,
                    "follower": relationship.get("follower") or False,
                    "following": relationship.get("following") or False,
                    "ignoring": relationship.get("ignoring") or False,
                    # Initialize vis counts as sets for deduplication
                    "plots": set(),
                    "grids": set(),
                    "mails": set(),
                    "docs": set(),
                    "repos": set(),
                    "jobs": set(),
                }

    # Count vis per user from this group
    vis_types = ["plots", "grids", "mails", "docs", "repos", "jobs"]
    for vis_type in vis_types:
        for vis in group.get(vis_type, []) or []:
            author = vis.get("author", {}) or {}
            author_username = author.get("username", "")
            vis_id = vis.get("id", "")
            if author_username in members and vis_id:
                members[author_username][vis_type].add(f"{author_username}/{vis_id}")

    # Convert sets to counts and return as list
    result = []
    for username, member in members.items():
        member_data = {
            "username": member["username"],
            "name": member["name"],
            "type": member["type"],
            "public": member["public"],
            "role": member["role"],
            "connected": member["connected"],
            "follower": member["follower"],
            "following": member["following"],
            "ignoring": member["ignoring"],
            "plots": len(member["plots"]),
            "grids": len(member["grids"]),
            "mails": len(member["mails"]),
            "docs": len(member["docs"]),
            "repos": len(member["repos"]),
            "jobs": len(member["jobs"]),
            "is_me": username == current_user,
        }
        result.append(member_data)

    return result


def list_org_group_members_gql(gql: NovemGQL, org_id: str, group_id: str, current_user: str) -> List[Dict[str, Any]]:
    """List org group members via GraphQL, returning transformed format with vis counts."""
    variables = {"orgId": org_id}
    data = gql._query(LIST_ORG_GROUP_MEMBERS_QUERY, variables)
    return _transform_org_group_members_response(data, group_id, current_user)


LIST_ORG_GROUP_VIS_QUERY = """
query ListOrgGroupVis($orgId: ID!) {
  groups(id: $orgId, type: org) {
    id
    groups {
      id
      plots {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
      }
      grids {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
      }
      mails {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
      }
      docs {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
      }
      repos {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
      }
      jobs {
        id
        name
        type
        summary
        url
        updated
        public
        shared { id name type }
        tags { id name type }
        author { username }
        last_run_time
      }
    }
  }
}
"""


def _transform_org_group_vis_response(data: Dict[str, Any], group_id: str, vis_type: str) -> List[Dict[str, Any]]:
    """
    Transform GraphQL org group vis response for display.

    Returns vis items of the specified type from the specific group,
    with author/id as the display ID.
    """
    groups_list = data.get("groups", []) or []
    if not groups_list:
        return []

    org = groups_list[0]
    org_groups = org.get("groups", []) or []

    # Find the specific group by ID
    group = None
    for g in org_groups:
        if g.get("id") == group_id:
            group = g
            break

    if not group:
        return []

    # Get vis items of the specified type
    vis_items = group.get(vis_type, []) or []

    # Transform to display format with separate author and id
    result = []
    for item in vis_items:
        author = item.get("author", {}) or {}
        author_username = author.get("username", "")

        transformed = {
            "username": author_username,
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


def list_org_group_vis_gql(gql: NovemGQL, org_id: str, group_id: str, vis_type: str) -> List[Dict[str, Any]]:
    """List vis shared with an org group, returning REST-compatible format."""
    variables = {"orgId": org_id}
    data = gql._query(LIST_ORG_GROUP_VIS_QUERY, variables)
    return _transform_org_group_vis_response(data, group_id, vis_type)


# --- Topics / Comments ---

_COMMENT_FIELDS = """
    comment_id
    slug
    message
    depth
    deleted
    edited
    num_replies
    likes
    dislikes
    my_reaction
    created
    updated
    creator { username }
    mentions { nonce user { username } }
"""


def _build_comment_fragment(depth: int = 4) -> str:
    """Build a nested comment/replies fragment to the given depth."""
    fragment = _COMMENT_FIELDS
    for _ in range(depth):
        fragment = f"""
    {_COMMENT_FIELDS}
    replies {{{fragment}
    }}"""
    return fragment


_TOPICS_QUERY_TPL = """
query GetTopics($id: ID!, $author: String) {{
  me {{ username }}
  {vis_type}(id: $id, author: $author) {{
    vars {{ id value format type threshold }}
    topics {{
      topic_id
      slug
      message
      audience
      status
      num_comments
      likes
      dislikes
      my_reaction
      edited
      created
      updated
      creator {{ username }}
      mentions {{ nonce user {{ username }} }}
      comments {{{comment_fragment}
      }}
    }}
  }}
}}
"""


def _build_topics_query(vis_type: str, depth: int = 3) -> str:
    """Build a topics query for a given vis type (plots, grids, mails, etc.)."""
    comment_fragment = _build_comment_fragment(depth)
    return _TOPICS_QUERY_TPL.format(vis_type=vis_type, comment_fragment=comment_fragment)


def _has_truncated_replies(comments: List[Dict[str, Any]]) -> bool:
    """Check if any comment has num_replies > 0 but empty replies list."""
    for c in comments:
        replies = c.get("replies", []) or []
        if c.get("num_replies", 0) > 0 and not replies:
            return True
        if replies and _has_truncated_replies(replies):
            return True
    return False


def fetch_topics_gql(gql: NovemGQL, vis_type: str, vis_id: str, author: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch topics and comments, deepening the query if threads are truncated."""
    topics, _ = fetch_vde_topics_gql(gql, vis_type, vis_id, author=author)
    return topics


def fetch_vde_topics_gql(
    gql: NovemGQL, vis_type: str, vis_id: str, author: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch topics, comments, and VDE vars. Returns (topics, vars)."""
    topics, vde_vars, _ = _fetch_vde_topics_gql(gql, vis_type, vis_id, author=author)
    return topics, vde_vars


def _fetch_vde_topics_gql(
    gql: NovemGQL, vis_type: str, vis_id: str, author: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Fetch topics, comments, VDE vars, and current username. Returns (topics, vars, username)."""
    variables: Dict[str, Any] = {"id": vis_id}
    if author:
        variables["author"] = author

    depth = 3
    max_depth = 12
    topics: List[Dict[str, Any]] = []
    vde_vars: List[Dict[str, Any]] = []
    username = ""

    while depth <= max_depth:
        query = _build_topics_query(vis_type, depth=depth)
        data = gql._query(query, variables)
        username = (data.get("me") or {}).get("username", "")
        items = data.get(vis_type, [])
        if not items:
            return [], [], username
        topics = items[0].get("topics", [])
        vde_vars = items[0].get("vars", []) or []

        # Check if any topic has truncated comment trees
        truncated = any(_has_truncated_replies(t.get("comments", [])) for t in topics)
        if not truncated:
            break
        depth += 3

    return topics, vde_vars, username


# ---------------------------------------------------------------------------
# Group topics (org groups and user groups)
# ---------------------------------------------------------------------------

_GROUP_TOPICS_QUERY_TPL = """
query GetGroupTopics($name: String!, $type: GroupType!, $parent_group: String) {{
  me {{ username }}
  groups(name: $name, type: $type, parent_group: $parent_group) {{
    topics {{
      topic_id
      slug
      message
      audience
      status
      num_comments
      likes
      dislikes
      my_reaction
      edited
      created
      updated
      creator {{ username }}
      mentions {{ nonce user {{ username }} }}
      comments {{{comment_fragment}
      }}
    }}
  }}
}}
"""


def _build_group_topics_query(depth: int = 3) -> str:
    """Build a topics query for a group."""
    comment_fragment = _build_comment_fragment(depth)
    return _GROUP_TOPICS_QUERY_TPL.format(comment_fragment=comment_fragment)


def fetch_group_topics_gql(gql: NovemGQL, group_name: str, group_type: str, parent: str) -> List[Dict[str, Any]]:
    """Fetch topics and comments for a group. Returns topics list."""
    topics, _ = _fetch_group_topics_gql(gql, group_name, group_type, parent)
    return topics


def _fetch_group_topics_gql(
    gql: NovemGQL, group_name: str, group_type: str, parent: str
) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch topics and comments for a group. Returns (topics, username)."""
    variables: Dict[str, Any] = {
        "name": group_name,
        "type": group_type,
        "parent_group": parent,
    }

    depth = 3
    max_depth = 12
    topics: List[Dict[str, Any]] = []
    username = ""

    while depth <= max_depth:
        query = _build_group_topics_query(depth=depth)
        data = gql._query(query, variables)
        username = (data.get("me") or {}).get("username", "")
        groups = data.get("groups", [])
        if not groups:
            return [], username
        topics = groups[0].get("topics", [])

        truncated = any(_has_truncated_replies(t.get("comments", [])) for t in topics)
        if not truncated:
            break
        depth += 3

    return topics, username


# ---------------------------------------------------------------------------
# Message processing: mentions, VDE variable embeds, and markdown rendering
# ---------------------------------------------------------------------------

_VDE_VAR_RE = re.compile(r"\{(/u/[A-Za-z0-9_.-]+/[pgmdrj]/[A-Za-z0-9_.-]+/v/[A-Za-z0-9_.-]+)\}")
_MENTION_RE = re.compile(r"@(_m[a-f0-9]{16})")

# ANSI attribute codes (use specific on/off to allow nesting)
_ANSI_BOLD_ON = "\033[1m"
_ANSI_BOLD_OFF = "\033[22m"
_ANSI_ITALIC_ON = "\033[3m"
_ANSI_ITALIC_OFF = "\033[23m"
_ANSI_STRIKE_ON = "\033[9m"
_ANSI_STRIKE_OFF = "\033[29m"
_ANSI_UNDERLINE_ON = "\033[4m"
_ANSI_UNDERLINE_OFF = "\033[24m"
_ANSI_DIM_ON = "\033[2m"
_ANSI_DIM_OFF = "\033[22m"
# 256-color backgrounds for pills
_ANSI_BG_GREEN = "\033[48;5;22m"
_ANSI_BG_RED = "\033[48;5;52m"
_ANSI_BG_GRAY = "\033[48;5;236m"
_ANSI_BG_OFF = "\033[49m"
_ANSI_FG_OFF = "\033[39m"

# Inline markdown regex — single pass, mirrors webapp's inlineRe
# Groups: 1=code, 2=bold, 3=strike, 4=italic, 5+6=link text+url,
#         7=mention nonce, 8=superscript, 9=subscript, 10=vde var
_INLINE_RE = re.compile(
    r"`([^`]+)`"  # 1: inline code
    r"|\*\*(.+?)\*\*"  # 2: bold
    r"|~~(.+?)~~"  # 3: strikethrough
    r"|\*(.+?)\*"  # 4: italic
    r"|\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)"  # 5,6: link
    r"|@(_m[a-f0-9]{16})"  # 7: mention
    r"|\^([^^]+?)\^"  # 8: superscript
    r"|~([^~]+?)~"  # 9: subscript
    r"|\{(/u/[A-Za-z0-9_.-]+/[pgmdrj]/[A-Za-z0-9_.-]+/v/[A-Za-z0-9_.-]+)\}"  # 10: vde var
)


def _resolve_mentions(message: str, mentions: Optional[List[Dict[str, Any]]]) -> str:
    """Replace @_m<nonce> placeholders with @username."""
    if not mentions:
        return message
    nonce_map = {}
    for m in mentions:
        nonce = m.get("nonce", "")
        username = (m.get("user") or {}).get("username", "")
        if nonce and username:
            nonce_map[nonce] = username

    def _repl(match: re.Match) -> str:  # type: ignore[type-arg]
        nonce = match.group(1)
        username = nonce_map.get(nonce)
        return f"@{username}" if username else match.group(0)

    return _MENTION_RE.sub(_repl, message)


def _format_var_value(
    value: Optional[str], fmt: Optional[str], var_type: Optional[str], threshold: Optional[str]
) -> str:
    """Format a VDE variable value according to its format string.

    Mirrors the webapp's formatVar.ts logic.
    """
    if value is None:
        return ""

    # Text passthrough
    if fmt == "st" or var_type == "text":
        return value

    # Date passthrough
    if fmt and fmt.startswith("%"):
        return value

    try:
        num = float(value)
    except (ValueError, TypeError):
        return value

    is_percent = bool(fmt and "%" in fmt)
    show_sign = bool(fmt and "+" in fmt)
    use_comma = bool(fmt and "," in fmt)

    # Parse precision from format string
    precision = 0
    if fmt:
        # Money: "$2m" → 2
        money_match = re.match(r"^([$€£])(\d+)m$", fmt)
        if money_match:
            symbol = money_match.group(1)
            precision = int(money_match.group(2))
            display = abs(num)
            formatted = f"{display:.{precision}f}"
            formatted = _comma_group(formatted)
            if num < 0:
                formatted = "\u2212" + formatted
            elif show_sign:
                formatted = "+" + formatted
            return f"{symbol}{formatted}"

        # .Nf or .N%
        prec_match = re.search(r"\.(\d+)", fmt)
        if prec_match:
            precision = int(prec_match.group(1))

    display_num = num * 100 if is_percent else num
    formatted = f"{abs(display_num):.{precision}f}"

    if use_comma:
        formatted = _comma_group(formatted)

    if display_num < 0:
        formatted = "\u2212" + formatted
    elif show_sign and display_num >= 0:
        formatted = "+" + formatted

    if is_percent:
        formatted += "%"

    return formatted


def _comma_group(s: str) -> str:
    """Add thousands separators to a formatted number string."""
    parts = s.split(".")
    digits = parts[0]
    grouped = ""
    for i, ch in enumerate(reversed(digits)):
        if i > 0 and i % 3 == 0:
            grouped = "," + grouped
        grouped = ch + grouped
    parts[0] = grouped
    return ".".join(parts)


def _render_vde_var_ansi(
    value: Optional[str],
    fmt: Optional[str],
    var_type: Optional[str],
    threshold: Optional[str],
) -> str:
    """Render a VDE variable as an ANSI-colored inline pill."""
    formatted = _format_var_value(value, fmt, var_type, threshold)
    if not formatted:
        return ""

    # Direction indicator for relative type — colored pill with triangle
    if var_type == "relative" and value is not None and threshold is not None:
        try:
            val = float(value)
            thresh = float(threshold)
            if val > thresh:
                return f"{_ANSI_BG_GREEN}{cl.OKGREEN} \u25b2 {formatted} {cl.ENDC}"
            elif val < thresh:
                return f"{_ANSI_BG_RED}{cl.FAIL} \u25bc {formatted} {cl.ENDC}"
            else:
                return f"{_ANSI_BG_GRAY}\033[97m \u25b6 {formatted} {cl.ENDC}"
        except (ValueError, TypeError):
            pass

    # Non-relative vars — subtle gray pill
    return f"{_ANSI_BG_GRAY}\033[97m {formatted} {cl.ENDC}"


def _build_var_lookup(
    vde_vars: List[Dict[str, Any]], user: str, vis_type: str, vis_id: str
) -> Dict[str, Dict[str, Any]]:
    """Build a lookup dict from VDE var FQNP path to var data.

    Maps e.g. "/u/alice/p/myplot/v/revenue" -> {"value": "0.15", "format": "+,.1%", ...}
    """
    # Reverse the type map: "plots" -> "p", "grids" -> "g", etc.
    type_to_code = {"plots": "p", "grids": "g", "mails": "m", "docs": "d", "jobs": "j", "repos": "r"}
    code = type_to_code.get(vis_type, "")
    lookup: Dict[str, Dict[str, Any]] = {}
    for v in vde_vars:
        var_id = v.get("id", "")
        if var_id:
            path = f"/u/{user}/{code}/{vis_id}/v/{var_id}"
            lookup[path] = v
    return lookup


_TYPE_CODE_TO_GQL = {"p": "plots", "g": "grids", "m": "mails", "d": "docs", "j": "jobs", "r": "repos"}


def _collect_var_refs(topics: List[Dict[str, Any]]) -> Set[str]:
    """Scan all messages in topics/comments for VDE var FQNP paths."""
    refs: Set[str] = set()

    def _scan(msg: Optional[str]) -> None:
        if msg:
            refs.update(m.group(1) for m in _VDE_VAR_RE.finditer(msg))

    for t in topics:
        _scan(t.get("message"))
        _scan_comments(t.get("comments") or [], refs)
    return refs


def _scan_comments(comments: List[Dict[str, Any]], refs: Set[str]) -> None:
    for c in comments:
        msg = c.get("message")
        if msg:
            refs.update(m.group(1) for m in _VDE_VAR_RE.finditer(msg))
        _scan_comments(c.get("replies") or [], refs)


def _fetch_all_cross_vars(
    session: requests.Session,
    api_root: str,
    var_paths: Set[str],
    existing_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Fetch vars for all referenced VDEs in a single aliased GQL query.

    Groups var paths by VDE, skips VDEs already in existing_lookup,
    builds one GQL query with aliases, returns a full var_path -> var_data lookup.
    """
    # Group by VDE (user/type_code/vis_id), skip paths already resolved
    vde_to_alias: Dict[str, str] = {}  # "user/type_code/vis_id" -> alias
    vde_info: Dict[str, Tuple[str, str, str, str]] = {}  # alias -> (user, vis_type, vis_id, type_code)

    for path in var_paths:
        if existing_lookup and path in existing_lookup:
            continue
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) != 6 or parts[0] != "u" or parts[4] != "v":
            continue
        user, type_code, vis_id = parts[1], parts[2], parts[3]
        vis_type = _TYPE_CODE_TO_GQL.get(type_code)
        if not vis_type:
            continue
        vde_key = f"{user}/{type_code}/{vis_id}"
        if vde_key not in vde_to_alias:
            alias = f"vde_{len(vde_to_alias)}"
            vde_to_alias[vde_key] = alias
            vde_info[alias] = (user, vis_type, vis_id, type_code)

    if not vde_info:
        return {}

    # Build single aliased GQL query
    fragments: List[str] = []
    for alias, (user, vis_type, vis_id, _) in vde_info.items():
        fragments.append(
            f'  {alias}: {vis_type}(id: "{vis_id}", author: "{user}") '
            f"{{ vars {{ id value format type threshold }} }}"
        )
    query = "query {\n" + "\n".join(fragments) + "\n}"

    gql_endpoint = _get_gql_endpoint(api_root)
    try:
        resp = session.post(gql_endpoint, json={"query": query})
        resp.raise_for_status()
        result = resp.json()
        data = result.get("data", {})
    except Exception:
        return {}

    # Build lookup from results
    lookup: Dict[str, Dict[str, Any]] = {}
    for alias, (user, vis_type, vis_id, type_code) in vde_info.items():
        items = data.get(alias)
        if not items:
            continue
        # GQL returns either a list of VDEs or a single VDE object
        vde_obj = items[0] if isinstance(items, list) else items
        for v in vde_obj.get("vars", []) or []:
            var_id = v.get("id", "")
            if var_id:
                fqnp = f"/u/{user}/{type_code}/{vis_id}/v/{var_id}"
                lookup[fqnp] = v

    return lookup


def _render_inline_ansi(
    text: str,
    mention_map: Optional[Dict[str, str]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Render inline markdown elements to ANSI escape codes.

    Handles: bold, italic, strikethrough, inline code, links,
    mentions, superscript, subscript, and VDE variable embeds.
    """
    if not text:
        return text

    parts: List[str] = []
    last_end = 0

    for m in _INLINE_RE.finditer(text):
        # Append plain text before this match
        if m.start() > last_end:
            parts.append(text[last_end : m.start()])

        if m.group(1):  # inline code
            parts.append(f"{_ANSI_BG_GRAY}\033[37m {m.group(1)} {cl.ENDC}")
        elif m.group(2):  # bold
            inner = _render_inline_ansi(m.group(2), mention_map, var_lookup)
            parts.append(f"{_ANSI_BOLD_ON}{inner}{_ANSI_BOLD_OFF}")
        elif m.group(3):  # strikethrough
            inner = _render_inline_ansi(m.group(3), mention_map, var_lookup)
            parts.append(f"{_ANSI_STRIKE_ON}{inner}{_ANSI_STRIKE_OFF}")
        elif m.group(4):  # italic
            inner = _render_inline_ansi(m.group(4), mention_map, var_lookup)
            parts.append(f"{_ANSI_ITALIC_ON}{inner}{_ANSI_ITALIC_OFF}")
        elif m.group(5):  # link [text](url)
            link_text = _render_inline_ansi(m.group(5), mention_map, var_lookup)
            url = m.group(6)
            parts.append(f"{_ANSI_UNDERLINE_ON}{link_text}{_ANSI_UNDERLINE_OFF}")
            parts.append(f" {cl.FGGRAY}({url}){cl.ENDC}")
        elif m.group(7):  # mention @_m<nonce>
            nonce = m.group(7)
            username = (mention_map or {}).get(nonce)
            if username:
                parts.append(f"{cl.OKCYAN}@{username}{cl.ENDC}")
            else:
                parts.append(m.group(0))
        elif m.group(8):  # superscript
            parts.append(m.group(8))
        elif m.group(9):  # subscript
            parts.append(m.group(9))
        elif m.group(10):  # VDE var embed
            path = m.group(10)
            var_data = (var_lookup or {}).get(path)
            if var_data:
                parts.append(
                    _render_vde_var_ansi(
                        var_data.get("value"),
                        var_data.get("format"),
                        var_data.get("type"),
                        var_data.get("threshold"),
                    )
                )
            else:
                parts.append(f"{cl.FGGRAY}{path}{cl.ENDC}")

        last_end = m.end()

    # Trailing text
    if last_end < len(text):
        parts.append(text[last_end:])

    return "".join(parts)


def _build_mention_map(mentions: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, str]]:
    """Build nonce -> username map from mentions list."""
    if not mentions:
        return None
    result: Dict[str, str] = {}
    for m in mentions:
        nonce = m.get("nonce", "")
        username = (m.get("user") or {}).get("username", "")
        if nonce and username:
            result[nonce] = username
    return result or None


def _render_message_lines(
    message: str,
    prefix: str,
    width: int,
    mentions: Optional[List[Dict[str, Any]]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    """Render a message with markdown, mentions, and VDE vars into prefixed lines.

    Handles block-level elements (code blocks, blockquotes, lists, headings, hr)
    and inline elements (bold, italic, code, strikethrough, links, mentions, vars).
    """
    if not message:
        return []

    mention_map = _build_mention_map(mentions)
    indent_width = _visible_len(prefix)
    available = max(20, width - indent_width)
    lines: List[str] = []
    src_lines = message.split("\n")
    i = 0

    while i < len(src_lines):
        line = src_lines[i]

        # --- Fenced code block ---
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(src_lines) and not src_lines[i].startswith("```"):
                code_lines.append(src_lines[i])
                i += 1
            if i < len(src_lines):
                i += 1  # skip closing ```

            # Render code block: gray background, dim language label
            if lang:
                lines.append(f"{prefix}{_ANSI_BG_GRAY}\033[37m {lang} {cl.ENDC}")
            for cl_line in code_lines:
                lines.append(f"{prefix}{_ANSI_BG_GRAY}\033[37m {cl_line:{available - 1}}{cl.ENDC}")
            continue

        # --- Heading ---
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = _render_inline_ansi(heading_match.group(2), mention_map, var_lookup)
            if level <= 2:
                lines.append(f"{prefix}{_ANSI_BOLD_ON}{cl.OKCYAN}{text}{cl.ENDC}")
            else:
                lines.append(f"{prefix}{_ANSI_BOLD_ON}{text}{_ANSI_BOLD_OFF}")
            i += 1
            continue

        # --- Horizontal rule ---
        if re.match(r"^---+\s*$", line):
            rule = "\u2500" * min(available, 40)
            lines.append(f"{prefix}{cl.FGGRAY}{rule}{cl.ENDC}")
            i += 1
            continue

        # --- Blockquote ---
        if line.startswith("> ") or line == ">":
            quote_lines: List[str] = []
            while i < len(src_lines) and (src_lines[i].startswith("> ") or src_lines[i] == ">"):
                quote_lines.append(re.sub(r"^>\s?", "", src_lines[i]))
                i += 1
            quote_prefix = f"{prefix}{cl.FGGRAY}\u2502{cl.ENDC} "
            for ql in quote_lines:
                rendered = _render_inline_ansi(ql, mention_map, var_lookup)
                lines.extend(_wrap_ansi_text(rendered, quote_prefix, width))
            continue

        # --- Unordered list ---
        if re.match(r"^[-*]\s", line):
            while i < len(src_lines) and re.match(r"^[-*]\s", src_lines[i]):
                item_text = src_lines[i][2:]
                rendered = _render_inline_ansi(item_text, mention_map, var_lookup)
                bullet_prefix = f"{prefix}\u2022 "
                cont_prefix = f"{prefix}  "
                wrapped = _wrap_ansi_text(rendered, cont_prefix, width)
                if wrapped:
                    wrapped[0] = (
                        f"{bullet_prefix}{rendered}"
                        if len(wrapped) == 1
                        else bullet_prefix + wrapped[0][len(cont_prefix) :]
                    )
                    lines.extend(wrapped)
                else:
                    lines.append(bullet_prefix)
                i += 1
            continue

        # --- Blank line ---
        if not line.strip():
            lines.append(prefix)
            i += 1
            continue

        # --- Paragraph (default) ---
        rendered = _render_inline_ansi(line, mention_map, var_lookup)
        lines.extend(_wrap_ansi_text(rendered, prefix, width))
        i += 1

    return lines


def _wrap_ansi_text(text: str, prefix: str, width: int) -> List[str]:
    """Wrap ANSI-formatted text to fit within width, prepending prefix.

    Uses _visible_len to handle ANSI escape codes correctly.
    Falls back to textwrap on the plain-text version, then re-applies
    the ANSI codes line by line.
    """
    indent_width = _visible_len(prefix)
    available = max(20, width - indent_width)

    # For short text that fits, just return it directly
    if _visible_len(text) <= available:
        return [f"{prefix}{text}"]

    # Strip ANSI for wrapping, then re-render each wrapped line
    plain = re.sub(r"\033\[[0-9;]*m", "", text)
    wrapped = textwrap.wrap(plain, width=available) or [""]

    # If the text has no ANSI codes, simple case
    if plain == text:
        return [f"{prefix}{wl}" for wl in wrapped]

    # Re-render: for each wrapped plain line, find matching portion in original
    # and extract with ANSI codes intact
    result: List[str] = []
    src_pos = 0
    for wl in wrapped:
        # Find where this wrapped line starts in the plain text
        plain_idx = plain.find(wl, src_pos)
        if plain_idx == -1:
            result.append(f"{prefix}{wl}")
            continue

        # Map plain_idx back to position in ANSI text
        ansi_start = _plain_to_ansi_pos(text, plain_idx)
        ansi_end = _plain_to_ansi_pos(text, plain_idx + len(wl))
        segment = text[ansi_start:ansi_end]
        result.append(f"{prefix}{segment}")
        src_pos = plain_idx + len(wl)

    return result


def _plain_to_ansi_pos(ansi_text: str, plain_pos: int) -> int:
    """Map a position in plain text to position in ANSI-coded text."""
    ansi_re = re.compile(r"\033\[[0-9;]*m")
    plain_count = 0
    i = 0
    while i < len(ansi_text) and plain_count < plain_pos:
        m = ansi_re.match(ansi_text, i)
        if m:
            i = m.end()
        else:
            plain_count += 1
            i += 1
    # Skip any trailing ANSI codes at the boundary
    while i < len(ansi_text):
        m = ansi_re.match(ansi_text, i)
        if m:
            i = m.end()
        else:
            break
    return i


# Keep these for backward compatibility and testing
def _process_message(
    message: str,
    mentions: Optional[List[Dict[str, Any]]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Process a message: resolve mentions and render VDE variable embeds."""
    if not message:
        return message

    mention_map = _build_mention_map(mentions)
    return _render_inline_ansi(message, mention_map, var_lookup)


def _relative_time(dt: datetime.datetime) -> str:
    """Return a human-friendly relative time string."""
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    return dt.strftime("%b %d, %Y")


def _visible_len(s: str) -> int:
    """Return the visible length of a string, ignoring ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _wrap_text(text: str, prefix: str, width: int) -> List[str]:
    """Wrap text to fit within width, prepending prefix to each line."""
    indent_width = _visible_len(prefix)
    available = width - indent_width
    if available < 20:
        available = 20

    result: List[str] = []
    for line in text.splitlines():
        if not line:
            result.append(prefix)
        else:
            wrapped = textwrap.wrap(line, width=available) or [""]
            for wl in wrapped:
                result.append(f"{prefix}{wl}")
    return result


def _get_term_width() -> int:
    """Get terminal width, capped at 120."""
    return min(120, shutil.get_terminal_size().columns)


def _render_comment(
    comment: Dict[str, Any],
    prefix: str,
    connector: str,
    child_prefix: str,
    width: int = 0,
    me: str = "",
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Render a single comment and its replies as a tree."""
    if not width:
        width = _get_term_width()

    lines: List[str] = []

    username = comment.get("creator", {}).get("username", "?")
    message = comment.get("message", "") or ""
    mentions = comment.get("mentions")
    deleted = comment.get("deleted", False)
    edited = comment.get("edited", False)
    created_str = comment.get("created", "")

    # Timestamp
    ts = ""
    dt = parse_api_datetime(created_str)
    if dt:
        ts = _relative_time(dt)

    # Markers
    markers: List[str] = []
    if edited:
        markers.append("edited")
    if deleted:
        markers.append("deleted")
    marker_str = f" {cl.FGGRAY}({', '.join(markers)}){cl.ENDC}" if markers else ""

    # Reactions
    reactions: List[str] = []
    likes = comment.get("likes", 0)
    dislikes = comment.get("dislikes", 0)
    if likes:
        reactions.append(f"+{likes}")
    if dislikes:
        reactions.append(f"-{dislikes}")
    reaction_str = f" {cl.FGGRAY}[{' '.join(reactions)}]{cl.ENDC}" if reactions else ""

    # Header line
    user_color = cl.WARNING if me and username == me else cl.OKCYAN
    header = (
        f"{prefix}{connector}"
        f"{user_color}@{username}{cl.ENDC}"
        f" {cl.FGGRAY}·{cl.ENDC} "
        f"{cl.FGGRAY}{ts}{cl.ENDC}"
        f"{marker_str}{reaction_str}"
    )
    lines.append(header)

    # Message body
    body_prefix = f"{prefix}{child_prefix}"
    if deleted:
        lines.append(f"{body_prefix}{cl.FGGRAY}[deleted]{cl.ENDC}")
    elif message:
        lines.extend(_render_message_lines(message, body_prefix, width, mentions, var_lookup))

    # Replies
    replies = comment.get("replies", []) or []
    for i, reply in enumerate(replies):
        is_last = i == len(replies) - 1
        rc = "└ " if is_last else "├ "
        rp = "  " if is_last else "│ "
        lines.append(
            _render_comment(
                reply,
                f"{prefix}{child_prefix}",
                rc,
                rp,
                width,
                me=me,
                var_lookup=var_lookup,
            )
        )

    return "\n".join(lines)


def render_topics(
    topics: List[Dict[str, Any]],
    me: str = "",
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    session: Optional[requests.Session] = None,
    api_root: str = "",
) -> str:
    """Render a list of topics with their comment trees."""
    colors()

    if not topics:
        return f"{cl.FGGRAY}No topics{cl.ENDC}"

    # Scan messages for cross-VDE var references and batch-fetch in one GQL call
    if session and api_root:
        var_refs = _collect_var_refs(topics)
        if var_refs:
            cross_vars = _fetch_all_cross_vars(session, api_root, var_refs, var_lookup)
            if cross_vars:
                var_lookup = dict(var_lookup or {}, **cross_vars)

    width = _get_term_width()
    parts: List[str] = []

    for topic in topics:
        lines: List[str] = []

        username = topic.get("creator", {}).get("username", "?")
        message = topic.get("message", "") or ""
        mentions = topic.get("mentions")
        audience = topic.get("audience", "")
        status = topic.get("status", "")
        num_comments = topic.get("num_comments", 0)
        edited = topic.get("edited", False)
        created_str = topic.get("created", "")

        # Timestamp
        ts = ""
        dt = parse_api_datetime(created_str)
        if dt:
            ts = _relative_time(dt)

        # Metadata tags
        tags: List[str] = []
        if audience:
            tags.append(audience)
        if status and status != "active":
            tags.append(status)
        tag_str = f" {cl.FGGRAY}({', '.join(tags)}){cl.ENDC}" if tags else ""

        # Reactions
        reactions: List[str] = []
        likes = topic.get("likes", 0)
        dislikes = topic.get("dislikes", 0)
        if likes:
            reactions.append(f"+{likes}")
        if dislikes:
            reactions.append(f"-{dislikes}")
        reaction_str = f" {cl.FGGRAY}[{' '.join(reactions)}]{cl.ENDC}" if reactions else ""

        edited_str = f" {cl.FGGRAY}(edited){cl.ENDC}" if edited else ""

        comment_count = f" {cl.FGGRAY}· {num_comments} comment{'s' if num_comments != 1 else ''}{cl.ENDC}"

        # Topic header
        user_color = cl.WARNING if me and username == me else cl.OKCYAN
        header = (
            f"{cl.BOLD}┌{cl.ENDC} "
            f"{user_color}@{username}{cl.ENDC}"
            f" {cl.FGGRAY}·{cl.ENDC} "
            f"{cl.FGGRAY}{ts}{cl.ENDC}"
            f"{tag_str}{edited_str}{reaction_str}{comment_count}"
        )
        lines.append(header)

        # Topic body
        body_prefix = f"{cl.BOLD}│{cl.ENDC} "
        if message:
            lines.extend(_render_message_lines(message, body_prefix, width, mentions, var_lookup))

        # Comments
        comments = topic.get("comments", []) or []
        for i, comment in enumerate(comments):
            is_last = i == len(comments) - 1
            connector = "├ " if not is_last else "└ "
            child_prefix = "│ " if not is_last else "  "
            lines.append(
                _render_comment(
                    comment,
                    body_prefix,
                    connector,
                    child_prefix,
                    width,
                    me=me,
                    var_lookup=var_lookup,
                )
            )

        if not comments:
            lines.append(f"{cl.BOLD}└{cl.ENDC} {cl.FGGRAY}(no comments){cl.ENDC}")

        # Cap the last line: replace topic-level bold │ with bold └
        topic_text = "\n".join(lines)
        all_lines = topic_text.split("\n")
        bold_pipe = f"{cl.BOLD}│{cl.ENDC}"
        bold_cap = f"{cl.BOLD}└{cl.ENDC}"
        all_lines[-1] = all_lines[-1].replace(bold_pipe, bold_cap, 1)
        parts.append("\n".join(all_lines))

    return "\n\n".join(parts)
