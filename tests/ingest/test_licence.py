import pytest

from skeleton.ingest.licence import PERMITTED, apply_gate, detect_licence
from skeleton.ingest.models import IngestCode, IngestError

MIT = """MIT License

Copyright (c) 2024 Someone

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
"""

BSD2 = """BSD 2-Clause License

Copyright (c) 2024, Someone
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
"""

BSD3 = BSD2.replace("2-Clause", "3-Clause") + """
3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.
"""

APACHE = """
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION
"""

GPL = """                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.
"""


@pytest.mark.parametrize(
    "text,expected",
    [(MIT, "MIT"), (BSD2, "BSD-2-Clause"), (BSD3, "BSD-3-Clause"), (APACHE, "Apache-2.0"), (GPL, "unknown")],
)
def test_detect(tmp_path, text, expected):
    (tmp_path / "LICENSE").write_text(text)
    assert detect_licence(tmp_path) == expected


def test_missing_file(tmp_path):
    assert detect_licence(tmp_path) == "unknown"


def test_mixed_case_filename(tmp_path):
    (tmp_path / "Licence.md").write_text("x")
    (tmp_path / "License.txt").write_text(MIT)
    assert detect_licence(tmp_path) == "MIT"


def test_copying_file(tmp_path):
    (tmp_path / "COPYING").write_text(BSD3)
    assert detect_licence(tmp_path) == "BSD-3-Clause"


@pytest.mark.parametrize("lic", sorted(PERMITTED))
def test_gate_permitted(lic):
    assert apply_gate(lic, "retained") is True
    assert apply_gate(lic, "ephemeral") is False


@pytest.mark.parametrize("lic", ["unknown", "GPL-3.0-only"])
def test_gate_retained_rejects(lic):
    with pytest.raises(IngestError) as e:
        apply_gate(lic, "retained")
    assert e.value.code is IngestCode.licence_not_permitted


@pytest.mark.parametrize("lic", ["unknown", "GPL-3.0-only"])
def test_gate_ephemeral_never_raises(lic):
    assert apply_gate(lic, "ephemeral") is False
