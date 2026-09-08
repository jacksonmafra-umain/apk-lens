from __future__ import annotations

import pytest

from apk_lens import prompts
from apk_lens.cli import main
from apk_lens.errors import ApkLensError

EXPECTED = {
    "00-run-full-analysis",
    "01-permissions",
    "02-network-map",
    "03-data-collection",
    "04-third-party-sdks",
    "05-native-and-opacity",
    "06-mitigation",
    "07-red-team-your-findings",
    "08-plain-language-summary",
}


def test_the_library_is_complete():
    assert set(prompts.names()) == EXPECTED


def test_every_prompt_carries_the_standing_rules():
    """Self-contained when pasted, defined once so ten copies cannot drift."""
    for name in prompts.names():
        expanded = prompts.load(name)
        assert "Never confuse capability with behaviour" in expanded
        assert "Report absences" in expanded
        assert prompts.RULES_MARKER not in expanded


def test_every_prompt_names_a_command_or_an_evidence_file():
    for name in prompts.names():
        text = prompts.load(name)
        assert "apk-lens" in text or "results.json" in text, name


def test_prompts_can_be_selected_by_number_or_by_word():
    assert prompts.resolve("02") == "02-network-map"
    assert prompts.resolve("2") == "02-network-map"
    assert prompts.resolve("mitigation") == "06-mitigation"
    assert prompts.resolve("06-mitigation") == "06-mitigation"


def test_an_unknown_prompt_says_how_to_list_them():
    with pytest.raises(ApkLensError, match="no prompt matches"):
        prompts.resolve("nonsense")


def test_an_ambiguous_query_asks_for_the_full_name():
    with pytest.raises(ApkLensError, match="matches several prompts"):
        prompts.resolve("a")


def test_the_rules_file_is_not_offered_as_a_prompt():
    assert prompts.RULES_FILE.removesuffix(".md") not in prompts.names()
    assert "README" not in prompts.names()


def test_the_full_analysis_prompt_covers_the_whole_workflow():
    text = prompts.load("00")
    assert "apk-lens doctor" in text
    assert "apk-lens analyze" in text
    assert "--depth full" in text
    assert "--category" in text
    assert "09-coverage-and-limits.md" in text
    assert "07-red-team-your-findings.md" in text


def test_the_red_team_prompt_asks_for_withdrawals_not_just_confidence():
    text = prompts.load("07")
    assert "withdrew" in text
    assert "would overturn it" in text


def test_the_plain_language_prompt_forbids_intent_words():
    text = prompts.load("08")
    assert "Do not use the word spyware" in text


def test_the_rules_forbid_the_sentence_the_prompts_exist_to_prevent():
    text = prompts.rules()
    assert 'never "the app sends X"' in text
    assert "A claim you cannot cite is" in text


def test_prompts_command_lists_them(capsys):
    assert main(["prompts"]) == 0
    out = capsys.readouterr().out
    assert "00-run-full-analysis" in out


def test_prompts_command_prints_one_expanded(capsys):
    assert main(["prompts", "03"]) == 0
    out = capsys.readouterr().out
    assert "Data collection" in out
    assert "Cite the evidence" in out
