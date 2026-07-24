from __future__ import annotations

from types import MappingProxyType

from .base import FormatProfile, SupportLevel

ATTRIBUTE_ORDER = MappingProxyType(
    {
        "Transaction": (
            "Ac", "Nb", "Id", "Dt", "Dv", "Cu", "Am", "Exb", "Exr", "Exf",
            "Pa", "Ca", "Sca", "Br", "No", "Pn", "Pc", "Ma", "Ar", "Au",
            "Re", "Fi", "Bu", "Sbu", "Vo", "Ba", "Trt", "Mo",
        ),
        "Party": ("Nb", "Na", "Txt", "Search", "IgnCase", "UseRegex"),
        "Category": ("Nb", "Na", "Kd"),
        "Sub_category": ("Nbc", "Nb", "Na"),
    }
)

RECORD_DEFAULTS = MappingProxyType(
    {
        "Transaction": MappingProxyType(
            {
                "Ac": "0",
                "Nb": "0",
                "Id": "(null)",
                "Dt": "(null)",
                "Dv": "(null)",
                "Cu": "0",
                "Am": "0.00",
                "Exb": "0",
                "Exr": "0.00",
                "Exf": "0.00",
                "Pa": "0",
                "Ca": "0",
                "Sca": "0",
                "Br": "0",
                "No": "(null)",
                "Pn": "0",
                "Pc": "(null)",
                "Ma": "0",
                "Ar": "0",
                "Au": "0",
                "Re": "0",
                "Fi": "0",
                "Bu": "0",
                "Sbu": "0",
                "Vo": "(null)",
                "Ba": "(null)",
                "Trt": "0",
                "Mo": "0",
            }
        ),
        "Party": MappingProxyType(
            {
                "Nb": "0",
                "Na": "",
                "Txt": "(null)",
                "Search": "(null)",
                "IgnCase": "0",
                "UseRegex": "0",
            }
        ),
        "Category": MappingProxyType({"Nb": "0", "Na": "", "Kd": "0"}),
        "Sub_category": MappingProxyType({"Nbc": "0", "Nb": "0", "Na": ""}),
    }
)

PROFILE = FormatProfile(
    file_version="1.2.1",
    application_target="Grisbi 1.2.2",
    support_level=SupportLevel.READ_WRITE,
    section_groups=(
        ("General",),
        ("RGBA",),
        ("Print",),
        ("Currency",),
        ("Account",),
        ("Payment",),
        ("Transaction",),
        ("Scheduled",),
        ("Party",),
        ("Category", "Sub_category"),
        ("Budgetary", "Sub_budgetary"),
        ("Currency_link",),
        ("Bank",),
        ("Financial_year",),
        ("Archive",),
        ("Reconcile",),
        ("Import_rule",),
        ("Partial_balance",),
        ("Bet",),
        ("Report",),
    ),
    attribute_order=ATTRIBUTE_ORDER,
    record_defaults=RECORD_DEFAULTS,
    capabilities=frozenset(
        {
            "read-accounts",
            "read-transactions",
            "patch-mark",
            "update-normal-transaction",
            "create-normal-transaction",
            "delete-normal-transaction",
            "edit-transfer",
            "create-party",
            "create-category",
        }
    ),
)
