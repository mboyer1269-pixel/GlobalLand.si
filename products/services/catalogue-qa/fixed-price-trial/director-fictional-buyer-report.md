# Catalogue QA report for a fictional buyer

Autonomous AI agents prepared this example using fictional data. The verifier ran on 20 variant records against the documented column subset. The comparison control passed. The modified output failed the identifier preservation and variant image mapping checks.

| SKU | CSV data record after the header | Field | Expected | Observed |
| --- | ---: | --- | --- | --- |
| SYN-B-BL-XXL | 20 | Barcode | `0000000000020` | `0000000000000` |
| SYN-B-BL-XXL | 20 | Variant image URL | `https://example.com/img/SYN-B-Blue-1.jpg` | `https://example.invalid/fictional-variant.png` |

The verifier reports grouped checks. The record and field locations come from a separate comparison by SKU. The row-location control in TASK-179585316100 found the same two changes at data record 1 after reordering. Before importing, restore the expected values in the produced CSV and rerun the verifier. No Shopify import was run. Preservation and image mapping require produced rows. An input-only request is limited to input validation.

## Private scope decision

Keep this as a candidate for the provisional CAD 60 quote only for the documented input and report scope. The test establishes technical coverage for these controls. Total preparation, review, revision and administrative effort remains unknown. At a hypothetical CAD 60 per hour, the gross price covers at most 60 all-in minutes before unknown deductions. Measure that effort on the next authorized rehearsal or delivery before treating CAD 60 as economically validated.
