from __future__ import annotations

import typer
import uvicorn

from .agent import TreasuryAgent
from .api.app import create_app

app = typer.Typer(help="ZeroClose treasury controls")


@app.command()
def serve(org_id: str, host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(create_app(TreasuryAgent(org_id)), host=host, port=port)


@app.command()
def status(org_id: str) -> None:
    typer.echo(TreasuryAgent(org_id).status())


if __name__ == "__main__":
    app()
