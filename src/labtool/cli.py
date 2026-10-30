import click
import sys
from pathlib import Path
from labtool.adapters import system
from labtool.services import install_cloudflared
from importlib.metadata import version
from labtool.adapters.cloudflared import CloudflaredGateway, YamlConfigStore
from labtool.adapters.lab_file import load_lab
from labtool.adapters.runner import ProcessRunner
from labtool.domain import LabError
from labtool.services import (
    delete_tunnel,
    down_tunnel,
    ensure_login,
    init_tunnel,
    tunnel_status,
    up_tunnel,
)
from . import ui
from .adapters.lab_file import load_lab, resolve_lab_path, user_config_path, write_template





CONTEXT = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT)
@click.version_option(version("labtool-cf"), "-v", "--version", prog_name="labtool-cf")
def cli():
    """labtool: manage a Cloudflare tunnel for your lab nodes.

    \b
    Typical flow:
      labtool install    install cloudflared
      labtool login      authorize with Cloudflare
      labtool init       create tunnel, DNS and config.yml
      labtool up         run the tunnel in the background
      labtool status     check whether it is running
      labtool down       stop it
    """
    
    
@cli.command(context_settings=CONTEXT)
@click.option("-f", "--file", default=None, show_default=True)
def init(file):
    """Create the tunnel, DNS records and config.yml."""
    lab = load_lab(resolve_lab_path(file))
    init_tunnel(lab, CloudflaredGateway(), YamlConfigStore(), log=ui.smart_log)


@cli.command(context_settings=CONTEXT)
def install():
    """Install cloudflared on this system."""
    install_cloudflared(system.detect_platform, system.is_installed,
                        system.run_commands, log=ui.smart_log)          

@cli.command(context_settings=CONTEXT)
def status():
    """Show whether the tunnel is running."""
    state = tunnel_status(ProcessRunner())
    if state.running:
        ui.success(f"Running (PID {state.pid})")
    else:
        ui.warn("Stopped")


@cli.command(context_settings=CONTEXT)
@click.option("-f", "--file", default=None, show_default=True)
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
def delete(file, yes):
    """Delete the tunnel from Cloudflare (irreversible)."""
    lab = load_lab(resolve_lab_path(file))
    if not yes:
        click.confirm(
            click.style(f"Delete tunnel '{lab.tunnel_name}'?", fg="red", bold=True),
            abort=True,
        )
    delete_tunnel(lab, CloudflaredGateway(), ProcessRunner(), log=ui.smart_log)
    
@cli.command(context_settings=CONTEXT)
@click.option("-f", "--file", default=None, show_default=True,
              help="Path to the lab definition file.")
def up(file):
    """Run the tunnel in the background."""
    lab = load_lab(resolve_lab_path(file))
    up_tunnel(lab, CloudflaredGateway(), ProcessRunner(), log=ui.smart_log)


@cli.command(context_settings=CONTEXT)
def down():
    """Stop the running tunnel."""
    down_tunnel(ProcessRunner(), log=ui.smart_log)


@cli.command(context_settings=CONTEXT)
def login():
    """Log in to Cloudflare (creates cert.pem)."""
    ensure_login(CloudflaredGateway(), log=ui.smart_log)
    
    
    
@cli.group(context_settings=CONTEXT)
def config():
    """Manage the lab.yaml configuration file."""


@config.command("init", context_settings=CONTEXT)
@click.option("--local", is_flag=True, help="Create ./lab.yaml instead of the user config dir.")
@click.option("--force", is_flag=True, help="Overwrite an existing file.")
def config_init(local, force):
    """Create a template lab.yaml and show where it is."""
    path = Path("lab.yaml") if local else user_config_path()
    write_template(path, force)
    ui.success(f"Created {path}")
    ui.info("Edit it (domain, tunnel_name, nodes), then run: labtool init")


@config.command("path", context_settings=CONTEXT)
def config_path():
    """Print the config file that would be used."""
    click.echo(resolve_lab_path())

    
    
    
def main():
    """Entry point: turn errors and Ctrl+C into clean, colored messages."""
    try:
        cli(standalone_mode=False)
    except click.exceptions.Abort:
        ui.warn("Cancelled.")
        sys.exit(130)                     # 130 = conventional exit code for Ctrl+C
    except KeyboardInterrupt:
        ui.warn("Cancelled (Ctrl+C).")
        sys.exit(130)
    except click.ClickException as e:
        ui.error(e.format_message())
        sys.exit(e.exit_code)
    except click.exceptions.Exit as e:
        sys.exit(e.exit_code)
    except LabError as e:
        ui.error(str(e))
        sys.exit(1)