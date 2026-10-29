#!/usr/bin/env python3
"""Dump the local LIMS database views to an Excel workbook and CSV files."""

import argparse
import csv
import datetime
import os
import sqlite3
import sys

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE, Cell
from openpyxl.workbook.views import BookView
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

import limsDB

# Views to dump, in sheet order. The "v_" prefix is dropped from the
# sheet and CSV names.
VIEWS = ["v_requests", "v_request_samples", "v_samples", "v_fastqs"]

# Excel row limit, including the header row
EXCEL_MAX_ROWS = 1048576


def read_view(conn: sqlite3.Connection, view: str) -> tuple[list[str], list[tuple]]:
    """Read all rows of a view.

    Args:
        conn: Open database connection.
        view: View name.

    Returns:
        Tuple of (column names, rows).
    """
    cur = conn.execute(f"SELECT * FROM {view}")
    return [d[0] for d in cur.description], cur.fetchall()


def write_csv(path: str, columns: list[str], rows: list[tuple]) -> None:
    """Write a table to a CSV file. NULL values are written as empty fields.

    Args:
        path: Output CSV path.
        columns: Column names.
        rows: Table rows.
    """
    with open(path, "w", newline="") as fp:
        writer = csv.writer(fp, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def excel_value(
    ws: WriteOnlyWorksheet, value: str | int | float | None
) -> str | int | float | Cell | None:
    """Prepare a value for a write-only sheet.

    Strings have characters that are illegal in XLSX removed, and
    strings starting with "=" are kept as text, not formulas.

    Args:
        ws: Write-only worksheet the value goes into.
        value: Value from the database.

    Returns:
        The value, or a text cell for text that starts with "=".
    """
    if not isinstance(value, str):
        return value
    value = ILLEGAL_CHARACTERS_RE.sub("", value)
    if value.startswith("="):
        cell = WriteOnlyCell(ws, value)
        cell.data_type = "s"
        return cell
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with db and out attributes.
    """
    parser = argparse.ArgumentParser(
        description="Dump the views of the local LIMS database to an Excel "
        "workbook with one sheet per view and to one CSV file per view.",
        epilog="Output files: <OUT>_<YYMMDD>.xlsx and "
        "<OUT>_<YYMMDD>_<view>.csv, with today's date and views "
        "requests, request_samples, samples, fastqs",
    )
    parser.add_argument(
        "-d",
        "--db",
        default=limsDB.get_db_path(),
        help="database path (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=os.path.join("lims", "limsDB"),
        help="output path prefix (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Dump each view to a sheet of <OUT>_<YYMMDD>.xlsx and to a CSV file.

    The CSV files are <OUT>_<YYMMDD>_<view>.csv, with today's date.
    """
    args = parse_args()

    if not os.path.isfile(args.db):
        print(f"Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    out = f"{args.out}_{datetime.date.today():%y%m%d}"

    conn = limsDB.connect(args.db)
    wb = Workbook(write_only=True)
    for view in VIEWS:
        name = view.removeprefix("v_")
        columns, rows = read_view(conn, view)

        csv_file = f"{out}_{name}.csv"
        write_csv(csv_file, columns, rows)
        print(f"{name}: {len(rows)} rows -> {csv_file}")

        if len(rows) + 1 > EXCEL_MAX_ROWS:
            print(
                f"WARNING: {name} has too many rows for Excel; "
                "sheet left out of the workbook",
                file=sys.stderr,
            )
            continue
        ws = wb.create_sheet(name)
        ws.freeze_panes = "A2"
        ws.append(columns)
        for row in rows:
            ws.append([excel_value(ws, v) for v in row])
    conn.close()

    xlsx_file = f"{out}.xlsx"
    wb.views = [
        BookView(xWindow=4000, yWindow=3000, windowWidth=32000, windowHeight=20000)
    ]
    wb.save(xlsx_file)
    print(f"Workbook -> {xlsx_file}")


if __name__ == "__main__":
    main()
