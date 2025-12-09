#!/usr/bin/env python3
"""Table search functionality."""

from PyQt6.QtWidgets import QLineEdit, QTableWidget


class TableSearch:
    """Search functionality for QTableWidget."""

    def __init__(self, table: QTableWidget, search_box: QLineEdit):
        self.table = table
        self.search_box = search_box
        self.search_box.textChanged.connect(self.filter_table)

    def filter_table(self, search_text: str):
        """Filter table rows based on search text."""
        search_lower = search_text.lower()

        for row in range(self.table.rowCount()):
            match = False

            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_lower in item.text().lower():
                    match = True
                    break

            self.table.setRowHidden(row, not match)


def add_search_to_table(table: QTableWidget, search_box: QLineEdit):
    """Add search capability to table."""
    return TableSearch(table, search_box)
