from __future__ import annotations

import importlib
import os
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


AutomationFunc = Callable[[], None]


@dataclass(frozen=True)
class Automation:
    name: str
    func: AutomationFunc
    description: str = ""


_REGISTRY: dict[str, Automation] = {}


def automation(name: str, description: str = "") -> Callable[[AutomationFunc], AutomationFunc]:
    def decorator(func: AutomationFunc) -> AutomationFunc:
        if name in _REGISTRY:
            raise ValueError(f"Automatizace '{name}' uz existuje.")
        _REGISTRY[name] = Automation(name=name, func=func, description=description)
        return func

    return decorator


def get_automation(name: str) -> Automation:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "zadne"
        raise SystemExit(f"Automatizace '{name}' neexistuje. Dostupne: {known}") from exc


def list_automations() -> list[Automation]:
    return sorted(_REGISTRY.values(), key=lambda item: item.name)


def import_task_modules() -> None:
    package_name = "automations.tasks"
    package = importlib.import_module(package_name)

    for module in pkgutil.iter_modules(package.__path__):
        if not module.ispkg:
            importlib.import_module(f"{package_name}.{module.name}")


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value

