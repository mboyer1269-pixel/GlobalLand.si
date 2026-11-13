Executed: Node v22.23.4, Python 3.11.2. Checks 63/63.

| input | category | JS new Date | JS naive app | JS repaired | Py fromisoformat | Py repaired |
|---|---|---|---|---|---|---|
| `2026-02-30T12:00:00Z` | calendar | 2026-03-02T12:00:00Z | 2026-03-02T12:00:00Z | reject | ValueError: day is out of range for mont | reject |
| `2026-04-31T12:00:00Z` | calendar | 2026-05-01T12:00:00Z | 2026-05-01T12:00:00Z | reject | ValueError: day is out of range for mont | reject |
| `2027-02-29T12:00:00Z` | calendar | 2027-03-01T12:00:00Z | 2027-03-01T12:00:00Z | reject | ValueError: day is out of range for mont | reject |
| `2100-02-29T12:00:00Z` | calendar | 2100-03-01T12:00:00Z | 2100-03-01T12:00:00Z | reject | ValueError: day is out of range for mont | reject |
| `2026-13-01T12:00:00Z` | calendar | Invalid Date | 2027-01-01T12:00:00Z | reject | ValueError: month must be in 1..12 | reject |
| `2026-00-10T12:00:00Z` | calendar | Invalid Date | 2025-12-10T12:00:00Z | reject | ValueError: month must be in 1..12 | reject |
| `2026-12-00T12:00:00Z` | calendar | Invalid Date | 2026-11-30T12:00:00Z | reject | ValueError: day is out of range for mont | reject |
| `2026-12-07T25:00:00Z` | hour | Invalid Date | 2026-12-08T01:00:00Z | reject | ValueError: hour must be in 0..23 | reject |
| `2026-12-07T24:00:00Z` | hour | 2026-12-08T00:00:00Z | 2026-12-08T00:00:00Z | reject | ValueError: hour must be in 0..23 | reject |
| `2026-12-07T12:60:00Z` | minute | Invalid Date | 2026-12-07T13:00:00Z | reject | ValueError: minute must be in 0..59 | reject |
| `2026-12-07T12:00:60Z` | second | Invalid Date | 2026-12-07T12:01:00Z | reject | ValueError: second must be in 0..59 | reject |
| `2026-12-07T12:00:00+24:00` | offset | Invalid Date | 2026-12-06T12:00:00Z | reject | ValueError: offset must be a timedelta s | reject |
| `2026-12-07T12:00:00+05:60` | offset | Invalid Date | 2026-12-07T06:00:00Z | reject | 2026-12-07T06:00:00Z | reject |
| `2028-02-29T12:00:00Z` | valid | 2028-02-29T12:00:00Z | 2028-02-29T12:00:00Z | 2028-02-29T12:00:00Z | 2028-02-29T12:00:00Z | 2028-02-29T12:00:00Z |
| `2000-02-29T12:00:00Z` | valid | 2000-02-29T12:00:00Z | 2000-02-29T12:00:00Z | 2000-02-29T12:00:00Z | 2000-02-29T12:00:00Z | 2000-02-29T12:00:00Z |
| `2026-12-31T23:59:59Z` | valid | 2026-12-31T23:59:59Z | 2026-12-31T23:59:59Z | 2026-12-31T23:59:59Z | 2026-12-31T23:59:59Z | 2026-12-31T23:59:59Z |
| `2026-12-07T12:00:00-05:00` | valid-offset | 2026-12-07T17:00:00Z | 2026-12-07T17:00:00Z | 2026-12-07T17:00:00Z | 2026-12-07T17:00:00Z | 2026-12-07T17:00:00Z |
| `2026-12-07T12:00:00+05:30` | valid-offset | 2026-12-07T06:30:00Z | 2026-12-07T06:30:00Z | 2026-12-07T06:30:00Z | 2026-12-07T06:30:00Z | 2026-12-07T06:30:00Z |
| `2026-12-07T12:00:00+23:59` | valid-offset | 2026-12-06T12:01:00Z | 2026-12-06T12:01:00Z | 2026-12-06T12:01:00Z | 2026-12-06T12:01:00Z | 2026-12-06T12:01:00Z |
| `2026-12-31T23:30:00-01:00` | valid-offset | 2027-01-01T00:30:00Z | 2027-01-01T00:30:00Z | 2027-01-01T00:30:00Z | 2027-01-01T00:30:00Z | 2027-01-01T00:30:00Z |
| `2026-04-30T00:00:00+00:00` | valid-offset | 2026-04-30T00:00:00Z | 2026-04-30T00:00:00Z | 2026-04-30T00:00:00Z | 2026-04-30T00:00:00Z | 2026-04-30T00:00:00Z |
