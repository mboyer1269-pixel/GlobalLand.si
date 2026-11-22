import csv
import json
import sys
from collections import defaultdict

with open(sys.argv[1], encoding="utf-8", newline="") as stream:
    rows = csv.DictReader(stream)
    if rows.fieldnames != ["expected_family", "offer_id", "item_group_id"]:
        sys.exit(2)
    groups = defaultdict(set)
    for row in rows:
        family, offer, group = (row[key] for key in rows.fieldnames)
        if None in row or not all(value and value.strip() for value in (family, offer, group)):
            sys.exit(2)
        groups[family].add(group)
    if not groups:
        sys.exit(2)
conflicts = {family: sorted(ids) for family, ids in groups.items() if len(ids) > 1}
print(json.dumps({"conflicting_families": conflicts}, sort_keys=True))
sys.exit(int(bool(conflicts)))
