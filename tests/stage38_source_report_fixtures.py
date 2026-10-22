"""New-wire synthetic authorship only, never an adapter for private failed jobs."""
from copy import deepcopy

from app.core.report_pipeline import object_hash
from app.core.source_report import REF_NAMES, freeze_source_directory
from stage38_report_fixtures import report_case


def source_case(count=2, *, bulk=False, texts=None):
    legacy, bank, texts = report_case(count, bulk=bulk, texts=texts)
    binding = dict(account_id="synthetic-author", project_id="synthetic-book", source_version="version-one",
                   source_revision=1, source_hash=object_hash(texts))
    directory = freeze_source_directory(binding, bank, texts)
    reverse = {source: short for short, source in directory["entries"].items()}
    mapping = {row["id"]: reverse[row["source_id"]] for row in legacy["evidence"]}
    def visit(value):
        if isinstance(value, dict):
            return {REF_NAMES.get(key, key): ([mapping[ref] for ref in item] if key in REF_NAMES else visit(item))
                    for key, item in value.items() if key != "evidence"}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    return visit(deepcopy(legacy)), bank, texts, {**binding, "source_directory": directory}


def capacity_draft(draft, entries, count=137):
    """Citation-volume stress only, not a claim of realistic narrative quality."""
    from app.core.source_report import SOURCE_REF_NAMES
    used = set()
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in SOURCE_REF_NAMES:
                    used.update(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(draft)
    result = deepcopy(draft)
    first = min(result["chapter_numbers"])
    extra = [key for key in entries if key.startswith(f"C{first}P") and key not in used][:count - len(used)]
    if count < len(used) or len(used) + len(extra) != count:
        raise AssertionError("Synthetic capacity source is insufficient")
    for offset in range(0, len(extra), 12):
        claim = deepcopy(result["characters"][0]["identity"])
        claim.update(source_ids=extra[offset:offset + 12], title="核对记录")
        result["characters"][0]["insights"].append(claim)
    return result
