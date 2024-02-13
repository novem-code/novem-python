from inspect import Parameter, signature
from typing import Any, Dict, List, Optional

from .plot import Plot


class NovemEmailSection(object):
    _type = "base"
    _subtype = "double"

    def __init__(self) -> None:
        """Novem e-mail sections add additional features to your e-mail."""

        self._params: List[str] = []
        self._kwparams: List[str] = []
        self._cparams: List[str] = []

        self._body: str = ""

    def get_markdown(self) -> str:
        """
        Returns novem e-mail markdown for this section
        """

        return ""


class NovemEmailSectionApi(NovemEmailSection):
    def __init__(
        self,
        locs: Dict[str, Any],
        params: Any,
        /,
        **kwargs: str,
    ) -> None:
        """Novem e-mail sections add additional features to your e-mail."""

        super().__init__()

        # get our arguments
        # args = signature(VisSection.__init__).parameters

        # construct all our keyword arguments
        for k, p in params.items():
            if p.kind != Parameter.POSITIONAL_OR_KEYWORD:
                continue

            v = locs[k]

            # #find out if k is string, bool or list
            if p.annotation is str or p.annotation is Optional[str]:
                # This is a string argument, if value is not None add it
                if v:
                    ts = f"{k.replace('_',' ')}: {v}"
                    self._kwparams.append(ts)

            elif p.annotation is bool:
                if v:
                    ts = f"{k.replace('_',' ')}: true"
                    self._kwparams.append(ts)

            elif p.annotation is List[str]:
                print("Treat as list of str")

        self._process_common_params(**kwargs)

        return None

    # let's parse and populate our default arguments according to
    # https://novem.no/docs/mail/sections/overview#common-parameters
    def _process_common_params(self, **kwargs: str) -> None:
        """
        Process the e-mail section parameters common to all novem mail
        #sections.
        * Padding
        * Margin
        * Borders
        * Colors

        We'll do some minor sanity checking here so we can report problems to
        the user, but ultimately the server side will verify the correctness
        of all parameters.
        """

        # valid direction list
        vdl = ["l", "r", "b", "t", "x", "y", "a"]
        valid_param_map = {
            "padding": ["multi", "dirsize"],
            "p": ["multi", "dirsize"],
            "margin": ["multi", "dirsize"],
            "m": ["multi", "dirsize"],
            "border": ["multi", "dirsize", "color"],
            "borders": ["multi", "dirsize", "color"],
            "b": ["multi", "dirsize", "color"],
            "foreground": ["color"],
            "fg": ["color"],
            "background": ["color"],
            "bg": ["color"],
        }

        vk = valid_param_map.keys()
        for k in kwargs.keys():

            # must be a common param
            if k not in vk:
                continue

            v = kwargs[k]

            # the content of the param must be a string or a list of strings
            if not (isinstance(v, str) or (isinstance(v, list) and not sum([1 for x in v if not isinstance(x, str)]))):

                # consider exception
                print((f'WARN: Section parameter "{k}" must be a string or ' "a list of strings"))

            # get some meta data about our param
            vp = valid_param_map[k]

            if "multi" not in vp and isinstance(v, list):
                # consider exception
                print(f'WARN: Section parameter "{k}" does not support lists')

            vs: List[str] = []
            # convert everything to a  list
            if isinstance(v, str):
                vs = [v]
            else:
                vs = v

            args = []
            # iterate over our v and construct our options
            for v in vs:
                if "dirsize" in vp:
                    splt = v.split(" ")
                    ds = splt[0]
                    dd = ds[0]  # direction
                    dz = 1
                    clr = ""
                    if dd not in vdl:
                        print(f'WARN: valid direction option for "{k}" ' f'is one of {",".join(vdl)}')
                    if len(ds) > 1:
                        try:
                            dz = int(ds[1])
                        except ValueError:
                            print(f'WARN: valid size option for "{k}" ' "is between 0 and 5")

                        if dz > 5 or dz < 0:
                            print(f'WARN: valid size option for "{k}" ' "is between 0 and 5")

                    if len(splt) > 1 and "color" in vp:
                        cls = splt[1:]
                        if len(cls) > 2:
                            print("WARN: a maximum of two colors can " f'be supplied for "{k}"')
                            cls = cls[:2]

                        # validate colors?
                        clr = f' {" ".join(cls)}'
                        # COLOR

                    args.append(f"{dd}{dz}{clr}")

                elif "color" in vp:
                    # only colors
                    cls = v.split(" ")
                    if len(cls) > 2:
                        print("WARN: a maximum of two colors can " f'be supplied for "{k}"')
                        cls = cls[:2]

                        # validate colors?
                    clr = f'{" ".join(cls)}'
                    args.append(f"{clr}")

            if len(args) == 1:
                self._cparams.append(f"{k}: {args[0]}")
            else:
                self._cparams.append(f'{k}: [{", ".join(args)}]')

    def get_markdown(self) -> str:
        """
        Returns novem e-mail markdown for this section
        """

        ot = f"{{{{ {self._type}"

        plist = self._params + self._kwparams + self._cparams

        # Add section controleld params first
        for p in plist:
            if not len(p):
                continue

            ot = f"{ot}\n  {p}"

        if len(plist):
            ot = f"{ot}\n"
        else:
            ot = f"{ot} "

        ot = f"{ot}}}}}"

        if self._subtype == "double":
            ot = f"{ot}\n{self._body}\n"
            ot = f"{ot}{{{{ /{self._type} }}}}"

        return ot

    def ispct(self, value: Optional[str]) -> Optional[str]:
        """
        Novem standard pct value check
        """
        if value:
            try:
                ww = int(str(value).replace("%", ""))
                value = f"{ww:d}%"
            except ValueError:
                value = "100%"

            return value

        return "100%"

    def isinval(self, value: Optional[str], default: Optional[str], opts: List[str]) -> Optional[str]:
        """
        Novem value in options check
        """
        if value:
            # verify alignment is in valid
            value = value.strip().lower()
            if value not in opts:
                # TODO: Raise exception for invalid value
                value = default
            return value

        return default


class VisSection(NovemEmailSectionApi):
    def __init__(
        self,
        vis: Plot,
        /,
        width: Optional[str] = "100%",
        align: Optional[str] = "center",
        include_caption: bool = True,
        include_title: bool = False,
        include_link: bool = False,
        override_title: str = None,
        override_caption: str = None,
        **kwargs: str,
    ) -> None:
        """Add a novem visual to your e-mail.

        :param vis: A handle to a :class:`novem.Plot` object referencing the
            visual you want to embed.
        :type vis: class:`novem.Plot`
        :param width: The width of the visual in the e-mail, defaults to 100%.
        :type width: str, optional
        :param align: Should the visual be aligned left, right or center.
        :type align: str, optional
        :param include_caption: Include the caption? Default true
        :type include_caption: bool, optional
        :param include_title: Include the title? Default false
        :type include_title: bool, optional
        :param include_link: Include a link to the web representation? Default
            false
        :type include_link: bool, optional
        :param override_caption: Override the caption with a string of your
            choice, leave out or set to None to ignore.
        :type override_caption: str, optional
        :param override_title: Override the title with a string of your
            choice, leave out or set to None to ignore.
        :type override_title: str, optional
        """
        # set our type
        self._type = "vis"
        self._subtype = "double"

        # verify our input variables, update them with default values
        width = self.ispct(width)
        align = self.isinval(align, "left", ["left", "right", "center"])

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # add param for our mandatory section
        vsn = vis.shortname.strip()
        vsn = f"ref: {vsn}"
        self._params.append(vsn)


class CalloutSection(NovemEmailSectionApi):
    def __init__(
        self,
        markdown: str,
        /,
        type: Optional[str] = "info",
        desc: Optional[str] = None,
        cborder: str = None,
        **kwargs: str,
    ) -> None:
        """Add a novem visual to your e-mail.

        :param markdown: A markdown string that will be rendered inside the
            callout.
        :type vis: str

        :param type: The type of the callout, one of str:`warn`, str:`info`
            str:`err`, str:`ok`. Default is info
        :type type: str, optional

        :param desc: Short descriptive string that will show up before the
            callout.
        :type desc: str, optional

        :param cborder: Optional callout border type, one of str:`solid`,
            str:`dashed`. Set it to none and use the common border options for
            more control
        :type cborder: str, optional

        """
        # set our type
        self._type = "callout"
        self._subtype = "double"

        # verify our input variables, update them with default values
        type = self.isinval(
            type,
            "info",
            [
                "info",
                "warn",
                "err",
                "ok",
                "warning",
                "error",
                "alert",
                "success",
            ],
        )

        cborder = self.isinval(cborder, None, ["dashed", "solid"])

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # add our body
        self._body = markdown


class PreviewSection(NovemEmailSectionApi):
    def __init__(
        self,
        markdown: str,
        /,
        **kwargs: str,
    ) -> None:
        """Add preview text to your mail.

        :param markdown: A markdown string that will be rendered to preview.
        :type vis: str
        """
        # set our type
        self._type = "preview"
        self._subtype = "double"

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # add our body
        self._body = markdown


class ParagraphSection(NovemEmailSectionApi):
    def __init__(
        self,
        markdown: str,
        /,
        font_size: str = "m",
        font_style: str = "r",
        **kwargs: str,
    ) -> None:
        """Add preview text to your mail.

        :param markdown: A markdown string that will be rendered to preview.
        :type vis: str
        """
        # set our type
        self._type = "paragraph"
        self._subtype = "double"

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # add our body
        self._body = markdown


class AuthorSection(NovemEmailSectionApi):
    def __init__(
        self,
        username: str,
        /,
        include_bio: bool = True,
        include_pciture: bool = True,
        override_bio: Optional[str] = None,
        **kwargs: str,
    ) -> None:
        """Add preview text to your mail.

        :param markdown: A markdown string that will be rendered to preview.
        :type vis: str
        """
        # set our type
        self._type = "author"
        self._subtype = "double"

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # strip @s from username
        username = username.lower().replace("@", "")

        # add param for our mandatory section
        vsn = f"username: {username}"
        self._params.append(vsn)


class AttachmentSection(NovemEmailSectionApi):
    def __init__(
        self,
        ref: Plot,  # add grid and doc later
        /,
        format: str = "pdf",  # output format
        name: Optional[str] = None,  # optional name
        **kwargs: str,
    ) -> None:
        """Add a novem visual to your e-mail.

        :param ref: A handle to a :class:`novem.Plot` object referencing the
            visual you want to embed.
        :type ref: class:`novem.Plot`
        """
        # set our type
        self._type = "attachment"
        self._subtype = "double"

        # snapshot local variables
        locs = locals()

        # invoke super for param generations
        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        # add param for our mandatory section
        vsn = ref.shortname.strip()
        vsn = f"ref: {vsn}"
        self._params.append(vsn)


class NovemEmailSectionUtil(NovemEmailSection):
    def __init__(self) -> None:
        super().__init__()

    def get_markdown(self) -> str:
        """
        Returns novem e-mail markdown for this section
        """

        return self._body


class MarkdownSection(NovemEmailSectionUtil):
    def __init__(self, markdown: str) -> None:
        """Add markdown to your document

        :param markdown: A markdown string to add
        :type markdown: str
        """
        # invoke super for param generations
        super().__init__()

        # add our body
        self._body = markdown


class CodeSection(NovemEmailSectionUtil):
    def __init__(self, code: str, lang: str = "") -> None:
        """Add syntax highlighted code

        :param code: code text
        :type code: str
        :param lang: language
        :type lang: str
        """
        # invoke super for param generations
        super().__init__()

        # add our body
        self._body = f"""```{lang}\n{code}\n```"""


# TODO: Mail only section
# Code
# TODO: Mail only section
# Code
