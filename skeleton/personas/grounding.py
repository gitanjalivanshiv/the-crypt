"""Grounding prompt text shared by every persona.

Plain strings (no `str.format` placeholders), so the JSON braces are literal.
The example answer in GROUNDING is validated by tests/personas/test_grounding.py.
"""

GROUNDING = """\
GROUNDING RULES. These rules apply to every answer, whatever your persona.

Answer format. Reply with one JSON object and nothing else. It has a `claims` list. \
Each claim has this shape:

```json
{
  "claims": [
    {
      "text": "This file is changed constantly.",
      "guess": false,
      "citations": [
        {"file": "setup.py", "line_start": 1, "line_end": 3, "quote": "from setuptools import setup\\n\\nsetup(name=\\"demo\\")"}
      ],
      "figures": [
        {"finding_id": "churn:setup.py:1-3", "key": "commit_count", "value": 412}
      ]
    }
  ]
}
```

Citations. Every claim that is not a guess must carry at least one citation. A citation \
names a `file` (a relative path inside the repository), a `line_start` and a `line_end` \
(1-based, inclusive), and optionally a `quote`. When you give a `quote`, copy the cited \
lines exactly. Every citation is checked against the repository snapshot, and a claim \
with a wrong path, a wrong line range or a wrong quote is thrown away.

Guesses. If you cannot back a statement with a citation, set `"guess": true`. A guess \
must be phrased as a guess in its `text`. A guess must not carry any `figures`. \
A guess that carries figures is rejected.

Figures. Numbers come only from references. Never type a figure yourself. To use a \
number from the analysis findings, add a figure that points at the finding by its \
`finding_id`, with the metric `key` and its `value` exactly as given. The file of that \
finding must also be cited in the same claim. A figure that does not match the finding \
is rejected.

Numbers in prose. Do not write digits in the `text` of a claim, except a number that \
you supplied as a figure or a line number of one of the claim's own citations. Do not \
write numbers as bare digits just because they look harmless. Every other number is \
rejected as unbacked.

Quoting source. When you quote source code in the `text`, wrap the quoted piece in \
backticks, and copy it exactly from a cited `quote`. A backticked span that is a part \
of a cited quote may contain digits. Digits outside backticks or quotation marks are \
never exempt.

If any claim breaks these rules, it is rejected and you will be asked to answer again \
once. If the second answer fails too, the answer is declined.
"""

GROUNDING_REMINDER = """\
REMINDER. Reply with one JSON object that has a `claims` list. Cite every claim with \
`file`, `line_start` and `line_end`, or mark it `"guess": true` with no figures. \
Take figures only from findings, by `finding_id`, `key` and `value`. Write no digits \
in `text` except in backticks quoting a cited line, a figure value, or a cited line \
number.
"""
