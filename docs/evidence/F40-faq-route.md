# F40 FAQ route evidence status

Status: blocked; no implementation or response-contract tests authorized.

The candidate design records `help.php:18-23,26-32,51-73` as source evidence for GET category and POST query-search branches, and `.htaccess:72-73` as route mapping only. It explicitly states that no retained HTTP response capture exists and the FAQ schema is unverified (`docs/roadmap/F31-F45-candidate-design.md`, evidence register and F40 row).

Required gates still open:
- Retained response capture: absent. Status, headers, cookies, body markers and exact response shapes are not established.
- FAQ schema owner and approved field mapping: absent; FAQ fields remain UNKNOWN.
- Owner scope approval and independent review: not recorded.

The routes `/help/{id}` and `/help/faqsearch` are source-indicated request shapes, not captured contracts. This record does not infer a schema, fabricate a capture, or authorize implementation. Revisit only after the missing capture and ownership decisions are retained and reviewed.
