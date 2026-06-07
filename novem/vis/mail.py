from __future__ import annotations

from typing import Any, List, Optional, Union

from novem.exceptions import Novem404
from novem.vis import NovemVisAPI

from .mail_sections import NovemEmailSection, PreviewSection


class Mail(NovemVisAPI):
    """A novem e-mail, addressed by name.

    Content and delivery fields (``content``, ``to``, ``cc``, ``bcc``,
    ``subject``, ``status``, …) may be passed to the constructor or set as
    attributes; changes are written live. Note that setting ``status`` can
    send the e-mail, so it is always applied last. Connection options are
    resolved from the arguments, ``novem.config``, the environment, or the
    config file — see the README.
    """

    _content_props = (
        "name",
        "description",
        "summary",
        "content",
        "status",
        "to",
        "cc",
        "bcc",
        "subject",
        "theme",
        "size",
        "template",
        "reply_to",
    )
    # content first (writes body), status last (can send the e-mail)
    _content_deferred = ("content", "status")

    def __init__(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = None,
        to: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        theme: Optional[str] = None,
        size: Optional[str] = None,
        template: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        :id mail name, duplicate entry will update the mail

        :to  TO recipients
        :cc  CC recipients
        :bcc BCC recipients
        :subject subject line

        Connection options and behaviour flags are accepted via **kwargs and
        resolved by the super chain. Unknown extras are warned and ignored.
        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            kwargs["user"] = cand[0]

        self.id = id

        self._vispath = "mails"
        self._type = "mail"

        super().__init__(**kwargs)

        self._section_updated: bool = False

        self._preview: Optional[NovemEmailSection] = None

        self._sections: List[NovemEmailSection] = []

        self._parse_kwargs(
            name=name,
            description=description,
            summary=summary,
            content=content,
            status=status,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            theme=theme,
            size=size,
            template=template,
            reply_to=reply_to,
            **kwargs,
        )

    def __call__(self, content: Any, **kwargs: Any) -> Any:
        """
        Set's the content of the mail

        The parameter either needs to be a text string
        of CSV formatted text or an object with a to_csv
        function.
        """

        raw_str: str = str(content)

        # setting the content object will invoke a server write
        self.content = raw_str

        # also update our varibales
        self._parse_kwargs(**kwargs)

        # return the original object so users can chain the contentframe
        return content

    # we'll implement generic properties common across all plots here
    def _produce_content(self) -> str:
        """
        Produce a valid novem e-mail markdown file
        from the supplied options
        """

        # construct our markdown
        ctnt = ""

        if self._preview:
            ctnt = self._preview.get_markdown()

        if len(self._sections):
            ctnt += "\n\n" + "\n\n".join([s.get_markdown() for s in self._sections])

        return ctnt

    def add_section(self, section: NovemEmailSection) -> Mail:
        """
        Add section to e-mail

        :section NovemEmailSection to add
        """

        if not isinstance(section, NovemEmailSection):
            # throw?
            print("You must supply a valid NovemEmailSection")

        if isinstance(section, PreviewSection):
            # update our preview section
            self._preview = section
            self._section_updated = True
        else:
            # append the section to our section list
            self._sections.append(section)
            self._section_updated = True

        return self
        # verify that

    def render(self) -> None:
        """
        Write e-mail to server
        """
        if self._section_updated:
            ctnt = self._produce_content()
            self.api_write("/content", ctnt)
            # update after api_write in case of exception
            self._section_updated = False

        return None

    def send(self) -> None:
        """
        Send e-mail to recipients
        """
        # check if there are any recipients registered
        try:
            to = self.to
        except Novem404:
            to = ""

        try:
            cc = self.cc
        except Novem404:
            cc = ""

        try:
            bcc = self.bcc
        except Novem404:
            bcc = ""

        reps = f"{to}\n{cc}\n{bcc}".split("\n")
        reps = [x for x in reps if x != ""]

        if len(reps) == 0:
            # print("No recipients registered, e-mail won't be sent")
            return None

        self.render()
        return self.api_write("/status", "sending")

    def _send(self) -> None:
        return self.api_write("/status", "sending")

    def test(self) -> None:
        """
        Create a test e-mail
        """
        # no need to check for recipients,

        self.render()
        return self.api_write("/status", "testing")

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
    # Important attributes that cause render and sending
    ###

    @property
    def content(self) -> str:
        return self.api_read("/content")

    @content.setter
    def content(self, value: str) -> None:
        return self.api_write("/content", value)

    @property
    def status(self) -> str:
        return self.api_read("/status")

    @status.setter
    def status(self, value: str) -> None:
        return self.api_write("/status", value)

    ###
    # Recipients
    ###

    # recipients to string
    def _r2s(self, rcpts: List[str]) -> str:
        return "\n".join(rcpts)

    # recipients to list
    def _r2l(self, rcpts: str) -> List[str]:
        return rcpts.split("\n")

    @property
    def to(self) -> str:
        return self.api_read("/recipients/to")

    @to.setter
    def to(self, value: Union[str, List[str]]) -> None:
        if value is None:
            return
        if isinstance(value, list):
            value = self._r2s(value)
        elif isinstance(value, str):
            value = "\n".join(value.split(","))
        return self.api_write("/recipients/to", value)

    @property
    def cc(self) -> str:
        return self.api_read("/recipients/cc")

    @cc.setter
    def cc(self, value: Union[str, List[str]]) -> None:
        if value is None:
            return
        if isinstance(value, list):
            value = self._r2s(value)
        elif isinstance(value, str):
            value = "\n".join(value.split(","))
        return self.api_write("/recipients/cc", value)

    @property
    def bcc(self) -> str:
        return self.api_read("/recipients/bcc")

    @bcc.setter
    def bcc(self, value: Union[str, List[str]]) -> None:
        if value is None:
            return
        if isinstance(value, list):
            value = self._r2s(value)
        elif isinstance(value, str):
            value = "\n".join(value.split(","))
        return self.api_write("/recipients/bcc", value)

    ###
    # Config
    ###

    @property
    def subject(self) -> str:
        return self.api_read("/config/subject")

    @subject.setter
    def subject(self, value: str) -> None:
        if not value:
            return
        return self.api_write("/config/subject", value)

    @property
    def theme(self) -> str:
        return self.api_read("/config/theme")

    @theme.setter
    def theme(self, value: str) -> None:
        return self.api_write("/config/theme", value)

    @property
    def size(self) -> str:
        return self.api_read("/config/size")

    @size.setter
    def size(self, value: str) -> None:
        return self.api_write("/config/size", value)

    @property
    def template(self) -> str:
        return self.api_read("/config/template")

    @template.setter
    def template(self, value: str) -> None:
        return self.api_write("/config/template", value)

    @property
    def reply_to(self) -> str:
        return self.api_read("/config/reply_to")

    @reply_to.setter
    def reply_to(self, value: str) -> None:
        return self.api_write("/config/reply_to", value)
