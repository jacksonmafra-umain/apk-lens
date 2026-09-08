from __future__ import annotations

import pytest

from apk_lens import domains


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("api.example.com", "example.com"),
        ("example.com", "example.com"),
        ("a.b.c.example.co.uk", "example.co.uk"),
        ("cdn.example.com.br", "example.com.br"),
        ("deep.sub.example.io", "example.io"),
        # Each tenant under a hosting suffix is a different party.
        ("tenant.s3.amazonaws.com", "tenant.s3.amazonaws.com"),
        ("app.appspot.com", "app.appspot.com"),
        # Unknown suffix: fall back to the last two labels.
        ("host.example.zzunknown", "example.zzunknown"),
    ],
)
def test_registrable_domain(host, expected):
    assert domains.registrable_domain(host) == expected


@pytest.mark.parametrize(
    "candidate",
    ["api.example.com", "a.co.uk", "cdn.example.io", "weird-host.tk"],
)
def test_real_hostnames_are_accepted(candidate):
    assert domains.is_hostname(candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        "android.view.View",       # a class name
        "config.properties",       # a file name
        "some_host.com",           # underscores are not legal in hostnames
        "localhost",               # no dot
        "",
        "example.zzunknown",       # TLD the catalog does not know
    ],
)
def test_things_that_only_look_like_hostnames_are_rejected(candidate):
    assert not domains.is_hostname(candidate)


def test_a_rejected_candidate_can_still_be_recognised_as_hostname_shaped():
    # This is what lets the census *count* what it skipped instead of hiding it.
    assert domains.looks_like_hostname("example.zzunknown")
    assert not domains.has_known_tld("example.zzunknown")


def test_labels_of_drops_the_public_suffix():
    assert domains.labels_of("api.myapp.example.com") == ["api", "myapp", "example"]
