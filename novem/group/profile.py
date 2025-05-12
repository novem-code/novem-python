from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from novem.group import NovemGroupAPI


class GroupOptions(object):
    def __init__(self, api: "NovemGroupAPI") -> None:
        """Initialize organization options with API reference"""
        self.api: "NovemGroupAPI" = api

    def set(self, profile: Dict[str, Any]) -> None:
        """
        Set profile options
        """

        props = [x for x in dir(self) if x not in ["api", "set"] and x[0] != "_"]

        for k in profile.keys():
            if k not in props:
                continue
            v = profile[k]
            setattr(self, k, v)

    @property
    def is_open(self) -> bool:
        res = self.api.api_read("/profile/options/is_open")
        if res.lower() == "yes":
            return True
        return False

    @is_open.setter
    def is_open(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/is_open", val)

    @property
    def show_description(self) -> bool:
        res = self.api.api_read("/profile/options/show_description")
        if res.lower() == "yes":
            return True
        return False

    @show_description.setter
    def show_description(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/show_description", val)

    @property
    def show_members(self) -> bool:
        res = self.api.api_read("/profile/options/show_members")
        if res.lower() == "yes":
            return True
        return False

    @show_members.setter
    def show_members(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/show_members", val)

    @property
    def show_profile(self) -> bool:
        res = self.api.api_read("/profile/options/show_profile")
        if res.lower() == "yes":
            return True
        return False

    @show_profile.setter
    def show_profile(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/show_profile", val)


class OrgOptions(GroupOptions):
    @property
    def enable_subdomain(self) -> bool:
        res = self.api.api_read("/profile/options/enable_subdomain")

        if res.lower() == "yes":
            return True
        return False

    @enable_subdomain.setter
    def enable_subdomain(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/enable_subdomain", val)


class OrgGroupOptions(GroupOptions):
    @property
    def allow_inbound_mail(self) -> bool:
        res = self.api.api_read("/profile/options/allow_inbound_mail")

        if res.lower() == "yes":
            return True
        return False

    @allow_inbound_mail.setter
    def allow_inbound_mail(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/allow_inbound_mail", val)

    @property
    def mail_verify_dkim(self) -> bool:
        res = self.api.api_read("/profile/options/mail_verify_dkim")

        if res.lower() == "yes":
            return True
        return False

    @mail_verify_dkim.setter
    def mail_verify_dkim(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/mail_verify_dkim", val)

    @property
    def mail_verify_spf(self) -> bool:
        res = self.api.api_read("/profile/options/mail_verify_spf")

        if res.lower() == "yes":
            return True
        return False

    @mail_verify_spf.setter
    def mail_verify_spf(self, value: bool) -> None:
        val = value and "yes" or "no"
        return self.api.api_write("/profile/options/mail_verify_spf", val)


class NovemGroupProfile(object):
    """
    Novem group profile
    """

    options: GroupOptions

    def __init__(self, api: "NovemGroupAPI", type: str = "group") -> None:
        """ """
        self.api: "NovemGroupAPI" = api

        if type == "org":
            self.options = OrgOptions(api)
        elif type == "org_group":
            self.options = OrgGroupOptions(api)

    def set(self, profile: Dict[str, Any]) -> None:
        """
        Set profile options
        """

        props = [x for x in dir(self) if x in ["name", "description", "options"]]

        for k in profile.keys():
            if k not in props:
                continue

            v = profile[k]
            if k == "options":
                self.options.set(profile[k])
            else:
                setattr(self, k, v)

    @property
    def name(self) -> str:
        return self.api.api_read("/profile/name")

    @name.setter
    def name(self, value: str) -> None:
        return self.api.api_write("/profile/name", value)

    @property
    def description(self) -> str:
        return self.api.api_read("/profile/description")

    @description.setter
    def description(self, value: str) -> None:
        return self.api.api_write("/profile/description", value)
