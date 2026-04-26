# Moje automatizace

Lehky zaklad pro osobni automatizace v Pythonu. Projekt je pripraveny tak, aby slo jednoduse pridavat nove ulohy, spoustet je rucne a pozdeji je napojit na cron, launchd, GitHub Actions nebo jinou planovaci sluzbu.

## Rychly start

```bash
python3 run.py list
python3 run.py run hello
```

Pokud automatizace potrebuje tajne hodnoty nebo osobni nastaveni, zkopiruj priklad:

```bash
cp .env.example .env
```

Soubor `.env` je ignorovany Gitem.

## Struktura

```text
.
├── automations/
│   ├── core.py            # registr a pomocne funkce
│   └── tasks/             # jednotlive automatizace
├── run.py                 # prikazova radka
├── .env.example           # priklad konfigurace
└── pyproject.toml         # metadata projektu
```

## Pridani nove automatizace

1. Vytvor novy soubor v `automations/tasks/`, treba `backup.py`.
2. Zaregistruj ulohu pres dekorator `@automation`.
3. Spust ji prikazem `python3 run.py run nazev-ulohy`.

Priklad:

```python
from automations.core import automation


@automation("backup", description="Provede zalohu dulezitych souboru")
def run() -> None:
    print("Zalohuju...")
```

## Priklady spousteni

Vypis dostupnych uloh:

```bash
python3 run.py list
```

Spusteni jedne ulohy:

```bash
python3 run.py run hello
```

Spusteni s nactenim `.env` souboru:

```bash
python3 run.py --env-file .env run hello
```

## Tydenni audit eidas.tools

Automatizace `eidas-weekly-audit` vytvori Markdown report s prioritnimi tipy pro zlepseni `https://eidas.tools`. Agent je nastaveny jako expert na pravni systemy, legal ops produktivitu, EU/eIDAS a pravni research workflow.

Lokalni spusteni:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
cp .env.example .env
python3 run.py --env-file .env run eidas-weekly-audit
```

V `.env` musi byt nastaveno:

```bash
OPENAI_API_KEY=sk-...
```

Pokud `eidas.tools` ukazuje password obrazovku, nastav v `.env` jeste:

```bash
EIDAS_AUDIT_PASSWORD=tvoje_heslo
```

Report se ulozi do `reports/eidas-tools/YYYY-MM-DD.md`.

Poznamka: `eidas.tools` je SPA aplikace, proto je pro plnohodnotny lokalni audit potreba nainstalovany Playwright pro renderovani stranky. GitHub Actions workflow to dela automaticky.

### GitHub Actions

Workflow `.github/workflows/eidas-weekly-audit.yml` bezi kazde pondeli v 06:00 UTC, tedy rano pro Europe/Luxembourg, a commitne novy report do repozitare.

V GitHub repozitari nastav secret:

```text
OPENAI_API_KEY
```
