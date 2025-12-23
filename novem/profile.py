from typing import Any

from novem.api_ref import NovemAPI


class Profile(NovemAPI):
    """
    Novem user profile class

    Manage your profile settings including name, bio, timezone, and visibility.

    Example usage:
        # Use default profile from config
        me = Profile()
        me.name = "My Name"
        me.bio = "A short bio"
        me.public = True

        # Use specific profile from config
        other = Profile(profile="my-other-user")

        # Use token directly
        new = Profile(token="nbt-XXXXa251")
    """

    _base_path = "admin/profile"
    _debug: bool = False

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize a Profile instance.

        :param profile: Profile name from config file to use
        :param token: Direct token string to authenticate with
        :param api_root: Override the API root URL
        :param config_path: Override the config file path
        """
        # Map 'profile' to 'config_profile' for user convenience
        if "profile" in kwargs and "config_profile" not in kwargs:
            kwargs["config_profile"] = kwargs.pop("profile")

        if "debug" in kwargs and kwargs["debug"]:
            self._debug = True

        super().__init__(**kwargs)

        self._parse_kwargs(**kwargs)

    def _parse_kwargs(self, **kwargs: Any) -> None:
        """Parse kwargs and set any valid properties."""
        super()._parse_kwargs(**kwargs)

        # Get list of settable properties (exclude private, methods, and read-only)
        props = [
            x
            for x in dir(self)
            if x[0] != "_" and x not in ["url", "read", "delete", "write", "create", "create_token"]
        ]

        for k, v in kwargs.items():
            if k not in props:
                continue
            setattr(self, k, v)

    def _read(self, prop: str) -> str:
        """Read a profile property from the API."""
        path = f"{self._base_path}/{prop}"

        if self._debug:
            print(f"GET: {self._api_root}{path}")

        return self.read(path)

    def _write(self, prop: str, value: str) -> None:
        """Write a profile property to the API."""
        path = f"{self._base_path}/{prop}"

        if self._debug:
            print(f"POST: {self._api_root}{path}")

        self.write(path, value)

    @property
    def name(self) -> str:
        """Get/set the profile display name."""
        return self._read("name").strip()

    @name.setter
    def name(self, value: str) -> None:
        self._write("name", value)

    @property
    def bio(self) -> str:
        """Get/set the profile bio."""
        return self._read("bio")

    @bio.setter
    def bio(self, value: str) -> None:
        self._write("bio", value)

    @property
    def timezone(self) -> str:
        """Get/set the profile timezone (e.g., 'Europe/Oslo')."""
        return self._read("timezone").strip()

    @timezone.setter
    def timezone(self, value: str) -> None:
        self._write("timezone", value)

    @property
    def public(self) -> bool:
        """Get/set whether the profile is publicly visible."""
        val = self._read("public").strip().lower()
        return val in ("yes", "true", "1")

    @public.setter
    def public(self, value: bool) -> None:
        self._write("public", "yes" if value else "no")

    @property
    def url(self) -> str:
        """Get the profile URL (read-only)."""
        return self._read("url").strip()
