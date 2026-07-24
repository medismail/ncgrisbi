from __future__ import annotations

from ncgrisbi.completion_history import prefer_current_account_history


def test_current_account_history_replaces_cross_account_fallback() -> None:
    snapshot = {
        "a": ["1", "Current"],
        "T": [
            [
                "10", "07/10/2026", None, "-10.00", "4", "1", "2", "3",
                "Older local", None, 0, None, None, "0", None, None,
                0, None, "0",
            ],
            [
                "11", "07/11/2026", None, "-20.00", "4", "5", "6", "7",
                "Newest local", "REF", 0, "V", "B", "0", "12", None,
                4, "2", "8",
            ],
        ],
        "H": [
            ["4", "2", "999.00", "9", "9", "9", "Wrong account", None, None, None, None],
            ["5", "2", "15.00", "0", "0", "2", "Fallback only", None, None, None, None],
        ],
    }

    result = prefer_current_account_history(snapshot)
    rows = {row[0]: row for row in result["H"]}

    assert rows["4"] == [
        "4", "1", "-20.00", "5", "6", "7", "Newest local", "REF", "V", "B", "2", "8"
    ]
    assert rows["5"][1] == "2"
    assert rows["5"][6] == "Fallback only"


def test_split_children_do_not_become_completion_source() -> None:
    snapshot = {
        "a": ["1", "Current"],
        "T": [[
            "20", "07/12/2026", None, "-30.00", "6", "1", "1", "1",
            "Split child", None, 0, None, None, "0", None, "19",
            2, None, "0",
        ]],
        "H": [["6", "2", "40.00", "0", "0", "2", "Fallback", None, None, None, None]],
    }

    result = prefer_current_account_history(snapshot)
    assert result["H"][0][1] == "2"
    assert result["H"][0][6] == "Fallback"
