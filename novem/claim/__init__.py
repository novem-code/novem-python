class Claim:
    id: str

    def __init__(self, id: str) -> None:
        self.id = id

    def get_share_string(self) -> str:
        """get our share string"""
        return f"{self.id}"

    def __str__(self) -> str:
        """Return a string representation of roles"""
        return self.get_share_string()
