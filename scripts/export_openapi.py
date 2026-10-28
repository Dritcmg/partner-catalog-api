"""Export a contract using a temporary database and an ephemeral, unprinted key."""

import json
import secrets
import tempfile
from pathlib import Path

from partner_catalog.config import Settings
from partner_catalog.main import create_app

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    settings = Settings(
        api_key=secrets.token_urlsafe(32), database_url=f"sqlite:///{Path(folder) / 'openapi.db'}"
    )
    app = create_app(settings)
    schema = app.openapi()
    app.state.engine.dispose()
(root / "docs").mkdir(exist_ok=True)
(root / "docs" / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
print("OpenAPI contract exported to docs/openapi.json")
