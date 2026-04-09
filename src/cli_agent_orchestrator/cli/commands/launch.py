"""Launch command for CLI Agent Orchestrator CLI."""

import os
import subprocess

import click
import requests

from cli_agent_orchestrator.constants import DEFAULT_PROVIDER, PROVIDERS, SERVER_HOST, SERVER_PORT

# Providers that require workspace folder access
PROVIDERS_REQUIRING_WORKSPACE_ACCESS = {
    "claude_code",
    "codex",
    "copilot_cli",
    "gemini_cli",
    "kimi_cli",
    "kiro_cli",
}


@click.command()
@click.option("--agents", required=False, help="Agent profile to launch")
@click.option("--team", "team_name", help="Team to launch (bounded context)")
@click.option("--session-name", help="Name of the session (default: auto-generated)")
@click.option("--headless", is_flag=True, help="Launch in detached mode")
@click.option(
    "--provider", default=None, help=f"Provider to use (default: {DEFAULT_PROVIDER})"
)
@click.option(
    "--allowed-tools",
    multiple=True,
    help="Override allowedTools (CAO format: execute_bash, fs_read, @cao-mcp-server). Repeatable.",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Skip confirmation prompt (restrictions still enforced).",
)
@click.option(
    "--yolo",
    is_flag=True,
    help="[DANGEROUS] Unrestricted tool access AND skip confirmation prompts. "
    "Agent can execute ANY command including aws, rm, curl.",
)
def launch(agents, team_name, session_name, headless, provider, allowed_tools, auto_approve, yolo):
    """Launch cao session with specified agent profile."""
    try:
        # Resolve team — interactive picker if neither --agents nor --team provided
        team = None
        if team_name:
            from cli_agent_orchestrator.services.team_service import load_team

            team = load_team(team_name)
        elif not agents:
            team = _pick_team()

        # Apply team defaults
        if team:
            if not agents:
                agents = team.agents[0] if team.agents else "code_supervisor"
            if not provider:
                provider = team.provider or DEFAULT_PROVIDER
            if not session_name:
                session_name = team.name

        # Final defaults
        if not agents:
            raise click.ClickException("Either --agents or --team is required")
        if not provider:
            provider = DEFAULT_PROVIDER

        # Validate provider
        if provider not in PROVIDERS:
            raise click.ClickException(
                f"Invalid provider '{provider}'. Available providers: {', '.join(PROVIDERS)}"
            )
        working_directory = os.path.realpath(os.getcwd())

        # Team overrides working directory
        if team and team.resolved_home and team.resolved_home.is_dir():
            working_directory = str(team.resolved_home)

        # Resolve allowedTools: --yolo > --allowed-tools CLI > profile/role defaults
        from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile
        from cli_agent_orchestrator.utils.tool_mapping import (
            format_tool_summary,
            resolve_allowed_tools,
        )

        resolved_allowed_tools = None
        no_role_set = False
        resolved_role = None
        if yolo:
            resolved_allowed_tools = ["*"]
        elif allowed_tools:
            resolved_allowed_tools = list(allowed_tools)
        else:
            # Load profile to get role-based defaults
            try:
                profile = load_agent_profile(agents)
                mcp_server_names = list(profile.mcpServers.keys()) if profile.mcpServers else None
                no_role_set = not profile.role and not profile.allowedTools
                resolved_role = profile.role
                resolved_allowed_tools = resolve_allowed_tools(
                    profile.allowedTools, profile.role, mcp_server_names
                )
            except (FileNotFoundError, RuntimeError):
                # Profile not found — use developer defaults (backward compatible)
                no_role_set = True
                resolved_allowed_tools = resolve_allowed_tools(None, None, None)

        # Confirmation / warning prompts
        if provider in PROVIDERS_REQUIRING_WORKSPACE_ACCESS:
            if yolo:
                # --yolo: warn but don't block
                click.echo(click.style("\n[WARNING] --yolo mode enabled", fg="yellow", bold=True))
                click.echo(
                    f"  Agent '{agents}' launching UNRESTRICTED on {provider}.\n"
                    f"  Agent can execute ANY command (aws, rm, curl, read credentials).\n"
                    f"  Directory: {working_directory}\n"
                )
            else:
                # Normal launch: show tool summary and confirm
                tool_summary = format_tool_summary(resolved_allowed_tools)
                role_display = (
                    resolved_role if resolved_role else "(not set — using developer defaults)"
                )

                click.echo(
                    f"\nAgent '{agents}' launching on {provider}:\n"
                    f"  Role:      {role_display}\n"
                    f"  Allowed:   {tool_summary}\n"
                    f"  Directory: {working_directory}\n"
                )
                if no_role_set:
                    click.echo(
                        "  Note: No role or allowedTools set — defaulting to 'developer'.\n"
                        "  Add 'role' or 'allowedTools' to your agent profile to control tool access.\n"
                        "  Docs: https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/tool-restrictions.md\n"
                    )
                click.echo(
                    "  To skip this prompt next time, relaunch with --auto-approve\n"
                    "  To remove all restrictions, relaunch with --yolo\n"
                )
                if not auto_approve and not click.confirm("Proceed?", default=True):
                    raise click.ClickException("Launch cancelled by user")

        # Call API to create session
        url = f"http://{SERVER_HOST}:{SERVER_PORT}/sessions"
        params = {
            "provider": provider,
            "agent_profile": agents,
            "working_directory": working_directory,
        }
        if session_name:
            params["session_name"] = session_name
        if resolved_allowed_tools:
            # Pass as comma-separated string for query param
            params["allowed_tools"] = ",".join(resolved_allowed_tools)
        if team:
            params["team"] = team.name

        response = requests.post(url, params=params)
        response.raise_for_status()

        terminal = response.json()

        team_label = f" [team: {team.name}]" if team else ""
        click.echo(f"Session created: {terminal['session_name']}{team_label}")
        click.echo(f"Terminal created: {terminal['name']}")

        # Attach to tmux session unless headless
        if not headless:
            subprocess.run(["tmux", "attach-session", "-t", terminal["session_name"]])

    except requests.exceptions.RequestException as e:
        raise click.ClickException(f"Failed to connect to cao-server: {str(e)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))


def _pick_team():
    """Interactive team picker. Returns Team or None."""
    from cli_agent_orchestrator.services.team_service import list_teams

    teams = list_teams()
    if not teams:
        return None

    click.echo("\nSelect a team:")
    for i, t in enumerate(teams, 1):
        home = t.home or "(cwd)"
        display = t.display_name or t.name
        click.echo(f"  {i}. {t.name:<20} — {display} ({home})")
    click.echo(f"  {len(teams) + 1}. (none)             — Launch without a team")

    choice = click.prompt(
        f"\nTeam [1-{len(teams) + 1}]",
        type=click.IntRange(1, len(teams) + 1),
        default=len(teams) + 1,
    )

    if choice <= len(teams):
        return teams[choice - 1]
    return None
