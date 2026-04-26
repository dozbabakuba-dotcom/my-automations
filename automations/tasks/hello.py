from __future__ import annotations

import os

from automations.core import automation


@automation("hello", description="Ukazkova automatizace pro overeni, ze projekt funguje")
def run() -> None:
    greeting = os.getenv("AUTOMATION_GREETING", "Ahoj")
    print(f"{greeting}, automatizace je pripravena.")

