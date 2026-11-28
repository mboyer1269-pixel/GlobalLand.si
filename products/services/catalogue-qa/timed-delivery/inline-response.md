Catalogue QA report for a fictional buyer

Autonomous AI agents prepared this report. I checked 20 produced variant records against the documented CSV column subset. The verifier flagged identifier preservation and variant image mapping. A separate comparison by SKU located these changes.

- SYN-B-BL-XXL, data record 20 after the header, Barcodes. Expected 0000000000020. Found 0000000000000.
- SYN-B-BL-XXL, data record 20 after the header, Variant image URL. Expected https://example.com/img/SYN-B-Blue-1.jpg. Found https://example.invalid/fictional-variant.png.

Restore those values in the produced CSV and rerun the check before import. Shopify import was outside the scope of this check. Preservation and image mapping require produced rows. Source rows alone support input validation.
