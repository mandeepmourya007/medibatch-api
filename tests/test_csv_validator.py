import pytest

from app.csv_validator import validate_csv


def test_valid_csv():
    # Excel BOM, mixed-case header, quoted comma, blank line, optional phone.
    content = '﻿Name,Address,Phone\nGeneral,"1 Main St, Block B",555\n\nCity,2 Park Ave,\n'.encode()

    hospitals, errors = validate_csv(content)

    assert errors == []
    assert [(h.name, h.address, h.phone) for h in hospitals] == [("General", "1 Main St, Block B", "555"), ("City", "2 Park Ave", None)]


def test_missing_fields_are_reported_per_row():
    hospitals, errors = validate_csv(b"name,address\n,1 Main St\nGeneral,\n")

    assert hospitals == []
    assert [(e["row"], e["field"]) for e in errors] == [(1, "name"), (2, "address")]


@pytest.mark.parametrize(
    "content",
    [
        b"",
        "name,address\nCaf\xe9,1 St\n".encode("latin-1"),
        b"name,name,address\nA,B,C\n",
        b"name,address,postcode\nA,B,1\n",
        b"name,phone\nA,1\n",
        b"name,address\n",
        ("name,address\n" + "H,St\n" * 21).encode(),
    ],
    ids=["empty", "not utf-8", "duplicate column", "unknown column", "missing column", "no hospitals", "over 20"],
)
def test_bad_files_are_rejected(content):
    hospitals, errors = validate_csv(content)

    assert hospitals == [] and len(errors) == 1
