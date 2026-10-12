from datetime import date, datetime
from pathlib import Path
import re

from dateutil.parser import parse as parse_date_value
from openpyxl import load_workbook
from docx import Document

from .project_models import ProjectActivity


def _header_key(value):
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return parse_date_value(str(value), dayfirst=True).date()
    except (TypeError, ValueError, OverflowError):
        return None


def extract_workplan_activities(document):
    """Create draft activity rows from a standard Excel workplan sheet.

    Expected headers are flexible: Activity/Activities/Activity Description,
    optional Activity Code, Start Date, and End Date. Rows are saved as
    unconfirmed until the Project Officer reviews and confirms them.
    """
    extension = Path(document.file.name).suffix.lower()
    if extension in {".docx"}:
        return _extract_docx_activities(document)
    if extension not in {".xlsx", ".xlsm"}:
        return 0

    document.file.open("rb")
    try:
        workbook = load_workbook(document.file, read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        header_index = None
        headers = None
        for index, candidate in enumerate(rows[:15]):
            candidate_keys = {_header_key(value) for value in candidate}
            if candidate_keys.intersection({"activity", "activities", "activity name", "activity description"}) and candidate_keys.intersection({"start date", "start", "activity start"}):
                header_index = index
                headers = candidate
                break
        if headers is None:
            return 0
        keys = {_header_key(value): index for index, value in enumerate(headers)}

        def find_column(candidates):
            for candidate in candidates:
                if candidate in keys:
                    return keys[candidate]
            return None

        code_column = find_column(("activity code", "activity no", "activity number", "code", "no"))
        activity_column = find_column(("activity", "activities", "activity name", "activity description", "description", "task"))
        start_column = find_column(("start date", "start", "activity start"))
        end_column = find_column(("end date", "end", "activity end"))
        if activity_column is None or start_column is None or end_column is None:
            return 0

        created = 0
        for row in rows[header_index + 1:]:
            name = str(row[activity_column] or "").strip()
            code = str(row[code_column] or "").strip() if code_column is not None else ""
            start_date = _date_value(row[start_column])
            end_date = _date_value(row[end_column])
            if not name or not start_date or not end_date or end_date < start_date:
                continue
            ProjectActivity.objects.create(
                workplan=document,
                code=code[:80],
                name=name[:255],
                start_date=start_date,
                end_date=end_date,
            )
            created += 1
        return created
    finally:
        document.file.close()


def _extract_docx_activities(document):
    document.file.open("rb")
    try:
        word_document = Document(document.file)
        table_created = _extract_docx_table_activities(document, word_document)
        if table_created:
            return table_created
        pending = None
        created = 0
        activity_pattern = re.compile(r"^activity(?:\s+code)?\s*[:#-]?\s*([A-Za-z0-9./_-]+)?\s*[:.-]\s*(.+)$", re.IGNORECASE)
        simple_activity_pattern = re.compile(r"^(?:activities?|activity\s+description)\s*[:.-]\s*(.+)$", re.IGNORECASE)
        code_pattern = re.compile(r"^activity\s+code\s*[:.-]\s*(.+)$", re.IGNORECASE)
        date_pattern = re.compile(
            r"start\s*date\s*:\s*([0-9][0-9/.-]*)\s+end\s*date\s*:\s*([0-9][0-9/.-]*)",
            re.IGNORECASE,
        )
        for paragraph in word_document.paragraphs:
            text = " ".join(paragraph.text.split())
            code_match = code_pattern.match(text)
            if code_match and not pending:
                pending = {"code": code_match.group(1).strip(), "name": ""}
                continue
            activity_match = activity_pattern.match(text)
            if activity_match:
                pending = {
                    "code": (activity_match.group(1) or (pending or {}).get("code", "")).strip(),
                    "name": activity_match.group(2).strip(),
                }
                continue
            simple_match = simple_activity_pattern.match(text)
            if simple_match:
                pending = {"code": (pending or {}).get("code", ""), "name": simple_match.group(1).strip()}
                continue
            if pending:
                code_match = code_pattern.match(text)
                if code_match:
                    pending["code"] = code_match.group(1).strip()
                    continue
            if not pending:
                continue
            date_match = date_pattern.search(text)
            if not date_match:
                continue
            start_date = _date_value(date_match.group(1))
            end_date = _date_value(date_match.group(2))
            if start_date and end_date and end_date >= start_date:
                ProjectActivity.objects.create(
                    workplan=document,
                    code=pending["code"][:80],
                    name=pending["name"][:255],
                    start_date=start_date,
                    end_date=end_date,
                )
                created += 1
            pending = None
        return created
    finally:
        document.file.close()


def _extract_docx_table_activities(document, word_document):
    for table in word_document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        if not rows:
            continue
        keys = {_header_key(value): index for index, value in enumerate(rows[0])}

        def find_column(candidates):
            for candidate in candidates:
                if candidate in keys:
                    return keys[candidate]
            return None

        code_column = find_column(("activity code", "activity no", "activity number", "code", "no"))
        activity_column = find_column(("activity", "activities", "activity name", "activity description", "task"))
        start_column = find_column(("start date", "start", "activity start"))
        end_column = find_column(("end date", "end", "activity end"))
        if activity_column is None or start_column is None or end_column is None:
            continue

        created = 0
        for row in rows[1:]:
            if max(activity_column, start_column, end_column) >= len(row):
                continue
            name = row[activity_column].strip()
            start_date = _date_value(row[start_column])
            end_date = _date_value(row[end_column])
            if not name or not start_date or not end_date or end_date < start_date:
                continue
            code = row[code_column].strip() if code_column is not None and code_column < len(row) else ""
            ProjectActivity.objects.create(
                workplan=document,
                code=code[:80],
                name=name[:255],
                start_date=start_date,
                end_date=end_date,
            )
            created += 1
        if created:
            return created
    return 0
