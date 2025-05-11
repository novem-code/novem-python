from novem import Claim


def test_claim():
    claim_string = "test_string"
    c = Claim(claim_string)
    assert str(c) == claim_string
    assert c.get_share_string() == claim_string
