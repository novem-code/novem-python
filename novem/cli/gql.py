"""
GraphQL client for novem CLI utility operations.

This module handles GraphQL queries for listing operations (plots, grids, mails, etc.)
while the core data operations remain REST-based.
"""

import json
import re
from typing import Any, Dict, List, Optional, Set

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
