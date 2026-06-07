from __future__ import annotations

from typing import Any, List, Optional

from novem.vis import NovemVisAPI

from .doc_sections import FrontmatterSection, NovemDocSection


class Doc(NovemVisAPI):
    """A novem document, addressed by name.

    Content properties (``content``, ``title``, ``theme``, ``type``, ``toc``,
    …) may be passed to the constructor or set as attributes; changes are
    written live. Connection options are resolved from the arguments,
    ``novem.config``, the environment, or the config file — see the README.
    """

    _content_props = ("name", "description", "summary", "content", "theme", "type", "title", "toc")
    _content_deferred = ("content",)

    def __init__(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        content: Optional[str] = None,
        theme: Optional[str] = None,
        type: Optional[str] = None,
        title: Optional[str] = None,
        toc: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        :id doc name, duplicate entry will update the doc

        Connection options and behaviour flags are accepted via **kwargs and
        resolved by the super chain. Unknown extras are warned and ignored.
        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            kwargs["user"] = cand[0]

        self.id = id

        self._vispath = "docs"
        self._type = "doc"

        super().__init__(**kwargs)

        self._section_updated: bool = False

        self._frontmatter: Optional[FrontmatterSection] = None

        self._sections: List[NovemDocSection] = []

        self._parse_kwargs(
            name=name,
            description=description,
            summary=summary,
            content=content,
            theme=theme,
            type=type,
            title=title,
            toc=toc,
            **kwargs,
        )

    def __call__(self, content: Any, **kwargs: Any) -> Any:
        """
        Set's the content of the doc

        The parameter either needs to be a text string
        or a file-like object with a read() method.
        """

        if hasattr(content, "read"):
            content = content.read()

        raw_str: str = str(content)

        # setting the content object will invoke a server write
        self.content = raw_str

        # also update our variables
        self._parse_kwargs(**kwargs)

        # return the original object so users can chain
        return content

    # --- Sections ---

    def add_section(self, section: NovemDocSection) -> Doc:
        """
        Add section to document

        :section NovemDocSection to add
        """

        if isinstance(section, FrontmatterSection):
            self._frontmatter = section
            self._section_updated = True
        else:
            self._sections.append(section)
            self._section_updated = True

        return self

    def _produce_content(self) -> str:
        """
        Produce a valid novem document markdown file
        from the supplied options
        """

        parts = []

        if self._frontmatter:
            parts.append(self._frontmatter.get_markdown())

        for section in self._sections:
            parts.append(section.get_markdown())

        return "\n\n".join(parts)

    def render(self) -> None:
        """
        Write document to server
        """
        if self._section_updated:
            ctnt = self._produce_content()
            self.api_write("/content", ctnt)
            # update after api_write in case of exception
            self._section_updated = False

        return None

    # --- Metadata properties ---

    @property
    def name(self) -> str:
        return self.api_read("/name").strip()

    @name.setter
    def name(self, value: str) -> None:
        return self.api_write("/name", value)

    @property
    def description(self) -> str:
        return self.api_read("/description")

    @description.setter
    def description(self, value: str) -> None:
        return self.api_write("/description", value)

    @property
    def summary(self) -> str:
        return self.api_read("/summary")

    @summary.setter
    def summary(self, value: str) -> None:
        return self.api_write("/summary", value)

    @property
    def url(self) -> str:
        return self.api_read("/url").strip()

    @property
    def shortname(self) -> str:
        return self.api_read("/shortname").strip()

    ###
    # Important attributes that cause render
    ###

    @property
    def content(self) -> str:
        return self.api_read("/content")

    @content.setter
    def content(self, value: str) -> None:
        return self.api_write("/content", value)

    ###
    # Config
    ###

    @property
    def theme(self) -> str:
        return self.api_read("/config/theme")

    @theme.setter
    def theme(self, value: str) -> None:
        return self.api_write("/config/theme", value)

    @property
    def type(self) -> str:
        return self.api_read("/config/type")

    @type.setter
    def type(self, value: str) -> None:
        return self.api_write("/config/type", value)

    @property
    def title(self) -> str:
        return self.api_read("/config/title")

    @title.setter
    def title(self, value: str) -> None:
        return self.api_write("/config/title", value)

    @property
    def toc(self) -> str:
        return self.api_read("/config/toc")

    @toc.setter
    def toc(self, value: str) -> None:
        return self.api_write("/config/toc", value)
