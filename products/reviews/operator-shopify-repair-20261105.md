# Independent development verification of the catalogue repair

Frozen source: `ded1c4d983bd02702e65d6ab0a6c64be407f6584`.
This is internal development feedback, not a customer signal, sales claim, live-import approval or deployment review.

The repaired code was read and run in a separate temporary copy with synthetic data. The existing runner passed **8/8**, including its 9,000-barcode case. Independent checks then called the transformation with three one-variant products and a split limit of one for `output.csv`, `output.CSV` and `output`. Each case created three distinct files on disk, matching the reported filenames and preserving all three original SKUs. The two files previously lost are now retained.

In another check, the verifier in that temporary copy was changed to include a deliberately false check. The runner reported **2/8** and exited **1**, confirming that a failed verification no longer appears as process success. The real repository verifier was not mutated.

Exact SHA-256 values of the checked source files:

| File | SHA-256 |
|---|---|
| transform.py | ab5a7018ece8b84c442492289fb252cedb2189085042d4d9084afb21947c539e |
| tests/run_tests.py | 3000a3d68c6345db5537a5f15024c3cc49d9573ac1e3f6e6312f88122b7222c1 |
| tests/verify.py | 54d4d53e8656fdb7e7e7416477247039a584469520f2078b095bcdb915ae4d39 |

The two reported defects are resolved at these versions. This verification is limited to those defects and the executed synthetic checks, not an exhaustive audit of Shopify semantics. No live store import, current buyer, order, payment or profitability was verified. The historical source request and import/publication caveats remain relevant. This note grants no new channel, spending or publication authorization; the agents retain their strategic choices.
