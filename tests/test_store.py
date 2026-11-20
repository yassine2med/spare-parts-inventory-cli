import pytest

from sparepartsinv import store
from sparepartsinv.cli import main


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    store.add_part(c, "A", "Part A", 5, 3, "S1")
    store.add_part(c, "B", "Part B", 1, 4)
    return c


def test_add_and_list(conn):
    assert [r["sku"] for r in store.all_parts(conn)] == ["A", "B"]


def test_duplicate_sku(conn):
    with pytest.raises(store.StockError):
        store.add_part(conn, "A", "again", 1, 1)


def test_negative_initial_quantity(conn):
    with pytest.raises(store.StockError):
        store.add_part(conn, "C", "x", -1, 0)


def test_receive_and_issue(conn):
    assert store.move(conn, "A", 5) == 10
    assert store.move(conn, "A", -7) == 3


def test_cannot_issue_more_than_stock(conn):
    with pytest.raises(store.StockError):
        store.move(conn, "B", -2)
    assert store.all_parts(conn)[1]["quantity"] == 1


def test_unknown_part(conn):
    with pytest.raises(store.StockError):
        store.move(conn, "ZZ", 1)


def test_zero_move_rejected(conn):
    with pytest.raises(store.StockError):
        store.move(conn, "A", 0)


def test_low_stock_order(conn):
    store.move(conn, "A", -2, "used")
    assert [r["sku"] for r in store.low_stock(conn)] == ["B", "A"]


def test_history_records_moves(conn):
    store.move(conn, "A", -1, "job 12")
    notes = [r["note"] for r in store.history(conn, "A")]
    assert notes == ["initial stock", "job 12"]


def test_import_csv(tmp_path):
    c = store.connect(":memory:")
    assert store.import_csv(c, "data/parts.csv") == 7


def test_import_bad_row(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("sku,name,quantity,min_qty,location\nX,x,abc,1,\n")
    with pytest.raises(store.StockError):
        store.import_csv(store.connect(":memory:"), str(p))


def test_cli_roundtrip(tmp_path, capsys):
    db = str(tmp_path / "t.db")
    assert main(["--db", db, "add", "Z1", "Widget", "--qty", "4", "--min", "5"]) == 0
    assert main(["--db", db, "low"]) == 0
    assert "Z1" in capsys.readouterr().out
    assert main(["--db", db, "issue", "Z1", "9"]) == 1


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    assert "LED-2X4" in capsys.readouterr().out
