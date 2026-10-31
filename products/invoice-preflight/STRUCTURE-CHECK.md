# Local CSV structure check

Run: python3 products/invoice-preflight/csv_structure_check.py products/invoice-preflight/sample.csv

Checks comma-separated UTF-8 CSV syntax, blank or duplicate headers and inconsistent record widths. Runs locally using the Python standard library. Multiline quoted fields and UTF-8 BOM are supported.

This is a generic structural check. It does not validate invoice amounts, tax, customer mappings, required platform fields or successful import into Manager or any accounting platform. Passing does not establish import compatibility. No payment or revenue has been verified.
