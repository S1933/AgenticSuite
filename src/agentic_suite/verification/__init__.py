"""Check types: pure functions that evaluate the 3 closed check types.

These functions do not perform I/O. The runtime layer is responsible for
loading context, artifacts, and resolving command_ref before calling
them. This separation is what allows them to be unit-tested with no
external state.
"""

from __future__ import annotations