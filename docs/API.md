# API reference

`datacraft.run(source: Path, destination: Path, config: dict | None = None) -> dict[str, int]`

Validates configuration before reading data. Returns read, accepted, rejected, filtered and written counts. Output is replaced only after successful processing and fsync. Destination and source must differ. `PipelineError` identifies invalid configurations, rows or file structure; IO exceptions remain normal `OSError` subclasses.

`schema`: column names mapped to `{type: str|int|decimal, required: bool, min: number, max: number}`. Missing optional fields become null. Numeric values must be finite and have no more than 1000 source characters or an exponent magnitude above 1000. Integer conversion rejects fractional values. Bounds require an int or decimal schema and the minimum cannot exceed the maximum.

`filters`: all rules are ANDed. `{field, op, value}` supports eq, ne, contains, gt, ge, lt and le. Comparisons use Decimal for ordering; contains uses case-sensitive text. Ordering filter values must be numeric and are checked before source IO. Field names and operators must be strings.

`aggregate`: `{group_by: [field, ...], sum: [field, ...]}` emits one row per group with `count` and the summed fields. SQLite stores grouping state on disk. Keys are sorted type-tagged serialized tuples. Decimal group keys normalize equivalent representations (0.10 and 0.100 share a group), while numeric values and lookalike strings remain distinct. Sum values export as strings to preserve exact decimal digits. Field names must be distinct and cannot be `count`.

`on_error`: fail (default) or skip. Skip covers row schema/filter validation only, logs row number and reason, and increments rejected. Malformed source files, missing aggregate fields and export defects always fail. Empty CSV output is a zero-byte file because no header is inferred.

JSON and JSONL fractional numbers are decoded directly as Decimal, avoiding binary float rounding, and export as strings even without schema rules. Integer JSON numbers retain their integer representation. The CLI also reads fractional configuration values as Decimal.

CSV/JSONL/XLSX are streamed. JSON arrays are loaded into memory; use JSONL for large inputs. CSV output requires uniform columns and prefixes an apostrophe before values beginning with =, +, - or @ to neutralize common spreadsheet formulas. This also affects negative decimal strings; use JSON/JSONL for lossless interchange. XLSX reads the active sheet and cached formula values; this tool does not recalculate Excel formulas.
