"""Focused scanner output guards for malformed follower payloads."""

from d2r_chargen.follower_block import FollowerBlock
from d2r_chargen.scanner import print_bound_demon_block


def test_print_bound_demon_block_reports_incomplete_payload(capsys):
    """Invalid saved follower tails must report cleanly instead of formatting None."""
    print_bound_demon_block(FollowerBlock(follower_count=1, payload=b"\x0e" * 106))

    out = capsys.readouterr().out
    assert "BOUND DEMON:" in out
    assert "incomplete payload = 106B" in out
    assert "raw_payload =" in out
