#!/usr/bin/env python3
"""Table pagination for large datasets."""

from PyQt6.QtWidgets import QWidget, QPushButton, QLabel, QHBoxLayout


class TablePaginator(QWidget):
    """Pagination widget for tables."""

    def __init__(self, table, page_size: int = 100):
        super().__init__()
        self.table = table
        self.page_size = page_size
        self.current_page = 0
        self.total_rows = 0
        self.all_data = []

        self._setup_ui()

    def _setup_ui(self):
        """Setup pagination controls."""
        layout = QHBoxLayout()

        self.prev_btn = QPushButton("Previous")
        self.next_btn = QPushButton("Next")
        self.page_label = QLabel("Page 1 of 1")

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)

        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_btn)

        self.setLayout(layout)

    def set_data(self, data: list):
        """Set data and display first page."""
        self.all_data = data
        self.total_rows = len(data)
        self.current_page = 0
        self.update_display()

    def update_display(self):
        """Update table with current page."""
        start = self.current_page * self.page_size
        end = min(start + self.page_size, self.total_rows)
        page_data = self.all_data[start:end]

        # Update table (implementation depends on table structure)
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")

        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(end < self.total_rows)

    def next_page(self):
        """Go to next page."""
        if (self.current_page + 1) * self.page_size < self.total_rows:
            self.current_page += 1
            self.update_display()

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_display()
