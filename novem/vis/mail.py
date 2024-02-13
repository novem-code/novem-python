from __future__ import annotations

from typing import Any, List, Optional, Union

from novem.exceptions import Novem404
from novem.vis import NovemVisAPI

from .mail_sections import NovemEmailSection, PreviewSection


class Mail(NovemVisAPI):
    """
    Novem mail class
    """

    def __init__(self, id: str, **kwargs: Any) -> None:
        """
        :id mail name, duplicate entry will update the mail

        :to  TO recipients
        :cc  CC recipients
        :bcc BCC recipients
        :subject subject line
        """

        # if we have an @ name we will override id and user
        if id[0] == "@":
            cand = id[1:].split("~")
            id = cand[1]
            uname = cand[0]
            kwargs["user"] = uname

        self.id = id

        self._vispath = "mails"
        self._type = "mail"

        super().__init__(**kwargs)

        self._section_updated: bool = False

        self._preview: Optional[NovemEmailSection] = None

        self._sections: List[NovemEmailSection] = []

        self._parse_kwargs(**kwargs)

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

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        # exclude content as it needs to be run last
        props = [x for x in dir(self) if x[0] != "_" and x not in ["content", "read", "delete", "write", "status"]]

        do_content = False
        do_status = False
        for k, v in kwargs.items():
            if k == "content":
                do_content = True

            if k == "status":
                do_status = True

            if k not in props:
                continue

            # print(f"{k} :: {v}")
            # set our value
            setattr(self, k, v)

        if do_content:
            content = kwargs["content"]
            setattr(self, "content", content)

        # status can send e-mail, so it's the very last thing to be updated
        if do_status:
            status = kwargs["status"]
            setattr(self, "status", status)

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

    @property
    def log(self) -> str:
        return self.api_read("/log").strip()

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
        if not value:
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
        if not value:
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
        if not value:
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
