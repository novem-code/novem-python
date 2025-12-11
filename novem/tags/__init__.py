import json
from typing import TYPE_CHECKING, Iterator, List, Union

from novem.exceptions import Novem404

if TYPE_CHECKING:
    from ..api_ref import NovemAPI

# Valid system tags
VALID_TAGS = {"fav", "like", "ignore", "wip", "archived"}


def is_valid_tag(tag: str) -> bool:
    """
    Check if a tag is valid.

    Valid tags are:
    - One of: fav, like, ignore, wip, archived
    - Any string starting with + (user tag)
    """
    if not tag:
        return False
    return tag in VALID_TAGS or tag.startswith("+")


class NovemTags:
    """
    Novem tags

    Novem tags are exposed at:
      f"{api._api_root}{tag_path}/tags"

    Valid tags are: fav, like, ignore, wip, archived, or any tag starting with + (user tag)
    """

    def __init__(self, api: "NovemAPI", tag_path: str) -> None:
        """Initialize the Tags object"""
        self.api: "NovemAPI" = api
        self.tag_path = tag_path

    def get(self) -> List[str]:
        """
        Get list of all tags currently active
        """
        try:
            path = f"{self.tag_path}/tags"
            s = self.api.read(path)
            tags_data = json.loads(s)
            tags = sorted([x["name"] for x in tags_data])
        except Novem404:
            tags = []

        return tags

    def set(self, tag: Union[str, List[str]]) -> None:
        """
        Replace all tags with the new set

        Args:
            tag: A string or a list of strings. Invalid tags are silently ignored.
        """
        # Convert to a list of tag strings
        if isinstance(tag, str):
            tags = [tag] if tag and is_valid_tag(tag) else []
        else:
            # Filter to only valid tags
            tags = [t for t in tag if t and is_valid_tag(t)]

        # If the list was non-empty but all items were invalid,
        # don't change the existing tags
        if isinstance(tag, list) and tag and not tags:
            return

        existing = self.get()
        to_remove = set(existing) - set(tags)
        to_add = set(tags) - set(existing)

        # Delete tags to remove
        for t in filter(None, to_remove):
            path = f"{self.tag_path}/tags/{t}"
            self.api.delete(path)

        # Add new tags
        for t in filter(None, to_add):
            path = f"{self.tag_path}/tags/{t}"
            self.api.create(path)

    def __iadd__(self, tag: str) -> "NovemTags":
        """
        Add a new tag to the collection

        Args:
            tag: A string tag. Invalid tags are silently ignored.
        """
        if tag and is_valid_tag(tag) and tag not in self.get():
            path = f"{self.tag_path}/tags/{tag}"
            self.api.create(path)
        return self

    def __isub__(self, tag: str) -> "NovemTags":
        """
        Remove a tag from the collection

        Args:
            tag: A string tag to remove.
        """
        if tag and tag in self.get():
            path = f"{self.tag_path}/tags/{tag}"
            self.api.delete(path)
        return self

    def __eq__(self, other: object) -> bool:
        """
        Check if the tags are equal to the given object

        Supports comparison with:
        - List of strings
        """
        if isinstance(other, list):
            other_tags = []
            for item in other:
                if isinstance(item, str):
                    other_tags.append(item)
                else:
                    # If we get something we don't understand, return False
                    return False

            # Compare the string representations
            return set(self.get()) == set(other_tags)
        return NotImplemented

    def __str__(self) -> str:
        """
        Return a string representation of tags
        """
        tags = self.get()
        if tags:
            return "\n".join(tags)
        else:
            return ""

    def __len__(self) -> int:
        """Return the number of tags"""
        tags = self.get()
        return len(tags) if tags else 0

    def __iter__(self) -> Iterator[str]:
        """Allow iteration over tags"""
        return iter(self.get())

    def __getitem__(self, index: Union[int, slice]) -> Union[str, List[str]]:
        """Allow indexing into tags"""
        return self.get()[index]

    def __contains__(self, tag: str) -> bool:
        """Check if a tag is in the collection"""
        return tag in self.get()
