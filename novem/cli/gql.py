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
    variables: Dict[str, Any] = {"id": vis_id}
    if author:
        variables["author"] = author

    depth = 3
    max_depth = 12
    topics: List[Dict[str, Any]] = []
    vde_vars: List[Dict[str, Any]] = []

    while depth <= max_depth:
        query = _build_topics_query(vis_type, depth=depth)
        data = gql._query(query, variables)
        items = data.get(vis_type, [])
        if not items:
            return [], []
        topics = items[0].get("topics", [])
        vde_vars = items[0].get("vars", []) or []

        # Check if any topic has truncated comment trees
        truncated = any(_has_truncated_replies(t.get("comments", [])) for t in topics)
        if not truncated:
            break
        depth += 3

    return topics, vde_vars


# ---------------------------------------------------------------------------
# Message processing: mentions + VDE variable embeds
# ---------------------------------------------------------------------------

_VDE_VAR_RE = re.compile(r"\{(/u/[A-Za-z0-9_.-]+/[pgmdrj]/[A-Za-z0-9_.-]+/v/[A-Za-z0-9_.-]+)\}")
_MENTION_RE = re.compile(r"@(_m[a-f0-9]{16})")


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

    # Direction indicator for relative type
    if var_type == "relative" and value is not None and threshold is not None:
        try:
            val = float(value)
            thresh = float(threshold)
            if val > thresh:
                return f"{cl.OKGREEN}\u25b2 {formatted}{cl.ENDC}"
            elif val < thresh:
                return f"{cl.FAIL}\u25bc {formatted}{cl.ENDC}"
        except (ValueError, TypeError):
            pass

    return formatted


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
            path = f"/u/{user}/p/{vis_id}/v/{var_id}" if code == "p" else f"/u/{user}/{code}/{vis_id}/v/{var_id}"
            lookup[path] = v
    return lookup


def _process_message(
    message: str,
    mentions: Optional[List[Dict[str, Any]]] = None,
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Process a message: resolve mentions and render VDE variable embeds."""
    if not message:
        return message

    # Resolve mentions
    message = _resolve_mentions(message, mentions)

    # Render VDE variable embeds
    if var_lookup:

        def _var_repl(match: re.Match) -> str:  # type: ignore[type-arg]
            path = match.group(1)
            var_data = var_lookup.get(path)
            if var_data:
                return _render_vde_var_ansi(
                    var_data.get("value"),
                    var_data.get("format"),
                    var_data.get("type"),
                    var_data.get("threshold"),
                )
            # Unknown var — show path without braces
            return path

        message = _VDE_VAR_RE.sub(_var_repl, message)

    return message


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
        message = _process_message(message, mentions, var_lookup)
        lines.extend(_wrap_text(message, body_prefix, width))

    # Replies
    replies = comment.get("replies", []) or []
    for i, reply in enumerate(replies):
        is_last = i == len(replies) - 1
        rc = "└ " if is_last else "├ "
        rp = "  " if is_last else "│ "
        lines.append(_render_comment(reply, f"{prefix}{child_prefix}", rc, rp, width, me=me, var_lookup=var_lookup))

    return "\n".join(lines)


def render_topics(
    topics: List[Dict[str, Any]],
    me: str = "",
    var_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Render a list of topics with their comment trees."""
    colors()

    if not topics:
        return f"{cl.FGGRAY}No topics{cl.ENDC}"

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
            message = _process_message(message, mentions, var_lookup)
            lines.extend(_wrap_text(message, body_prefix, width))

        # Comments
        comments = topic.get("comments", []) or []
        for i, comment in enumerate(comments):
            is_last = i == len(comments) - 1
            connector = "├ " if not is_last else "└ "
            child_prefix = "│ " if not is_last else "  "
            lines.append(
                _render_comment(comment, body_prefix, connector, child_prefix, width, me=me, var_lookup=var_lookup)
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
