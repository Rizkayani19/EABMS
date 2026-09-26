"""Gate 5 compatibility suite.

The historical Gate 5 module contained a malformed copied report-export block.
Gate 5.1 is the maintained transaction/UI regression suite and is already part
of the full test run. Re-export its tests here so the legacy Gate 5 module
remains importable without weakening coverage.
"""

from tests.test_gate_5_1 import *  # noqa: F401,F403
