"""Hypothesis profile registration.

Imported by tests/conftest.py for its side effect of registering profiles.
Lives as a standalone module (not inline in conftest.py) so that sync.sh's
heredoc overwrite of the public conftest.py does not silently discard the
registrations.

Profiles:
    dev  — fast default suite (max_examples=20, derandomize=True)
    deep — manual local opt-in for thorough runs (max_examples=2000, deadline=None)

Selection:
    HYPOTHESIS_PROFILE=deep pytest tests/test_property_roundtrip.py
"""
from hypothesis import settings, HealthCheck

settings.register_profile(
    "dev",
    max_examples=20,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "deep",
    max_examples=2000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
