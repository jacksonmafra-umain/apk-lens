from __future__ import annotations

import pytest

from apk_lens import __version__
from apk_lens.cli import build_parser, main


def test_version_flag_reports_the_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_bare_invocation_prints_help_and_succeeds(capsys):
    assert main([]) == 0
    assert "apk-lens" in capsys.readouterr().out


def test_parser_builds_without_registered_commands():
    # The command registry is populated by each stage module; an empty registry
    # must still yield a usable parser.
    assert build_parser().prog == "apk-lens"
