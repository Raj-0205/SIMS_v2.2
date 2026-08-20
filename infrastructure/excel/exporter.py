# infrastructure/excel/exporter.py

from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

__all__ = ["ExcelExporter"]


class ExcelExporter:
    """
    Exports structured data into Excel-compatible CSV and Spreadsheet formats.
    Complies with UTF-8 encoding standards with BOM for seamless Microsoft Excel loading.
    """

    @staticmethod
    def export_to_csv(
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        output_path: Path | str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """
        Writes data to a UTF-8 with BOM CSV file for direct Excel compatibility.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, mode="w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)

            # Metadata header comments if provided
            if metadata:
                for k, v in metadata.items():
                    writer.writerow([f"# {k}: {v}"])
                writer.writerow([])  # blank separator line

            writer.writerow(headers)
            for row in rows:
                writer.writerow([str(cell) if cell is not None else "" for cell in row])

        return path
