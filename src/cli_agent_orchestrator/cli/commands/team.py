"""Team commands for CLI Agent Orchestrator."""

import click

from cli_agent_orchestrator.services import team_service


@click.group()
def team():
    """Manage teams (bounded context sessions)."""


@team.command()
@click.argument("file_path", type=click.Path(exists=True))
def add(file_path):
    """Add a team from a markdown file."""
    try:
        t = team_service.add_team(file_path)
        click.echo(f"Team '{t.name}' added successfully")
        if t.display_name:
            click.echo(f"  Display name: {t.display_name}")
        if t.home:
            click.echo(f"  Home: {t.home}")
        if t.agents:
            click.echo(f"  Agents: {', '.join(t.agents)}")
    except Exception as e:
        raise click.ClickException(str(e))


@team.command("list")
def list_teams():
    """List all teams."""
    teams = team_service.list_teams()
    if not teams:
        click.echo("No teams configured. Add one with: cao team add <file>")
        return

    click.echo(f"{'Name':<20} {'Display Name':<25} {'Home':<40} {'Agents':<20}")
    click.echo("-" * 105)
    for t in teams:
        home = t.home or "(cwd)"
        agents = ", ".join(t.agents) if t.agents else "-"
        display = t.display_name or ""
        click.echo(f"{t.name:<20} {display:<25} {home:<40} {agents:<20}")


@team.command()
@click.argument("name")
def show(name):
    """Show team details."""
    try:
        t = team_service.load_team(name)
        click.echo(f"Name:         {t.name}")
        click.echo(f"Display name: {t.display_name or '(none)'}")
        click.echo(f"Home:         {t.home or '(cwd)'}")
        click.echo(f"Agents:       {', '.join(t.agents)}")
        click.echo(f"Provider:     {t.provider or '(default)'}")
        click.echo(f"Steering:     {len(t.steering)} doc(s)")
        for s in t.steering:
            click.echo(f"  - {s}")
        if t.env:
            click.echo(f"Env vars:     {len(t.env)}")
            for k, v in t.env.items():
                click.echo(f"  {k}={v}")
        if t.context:
            click.echo(f"\nContext:\n{t.context[:500]}")
    except FileNotFoundError:
        raise click.ClickException(f"Team '{name}' not found")


@team.command()
@click.argument("name")
def remove(name):
    """Remove a team."""
    try:
        team_service.remove_team(name)
        click.echo(f"Team '{name}' removed")
    except FileNotFoundError:
        raise click.ClickException(f"Team '{name}' not found")
