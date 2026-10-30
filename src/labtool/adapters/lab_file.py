import yaml
import os
from pathlib import Path
import click
from ..domain import Lab, LabError, Node


APP_NAME = "labtool"

TEMPLATE = """\
# labtool configuration
domain: example.com        # a domain that is Active on Cloudflare
tunnel_name: my-tunnel     # name of the tunnel
nodes:
  - name: node1            # becomes node1.example.com
    ip: 192.168.56.11      # address the tunnel machine can reach
"""


def user_config_path():
    """Per-user config location (differs per OS)."""
    return Path(click.get_app_dir(APP_NAME)) / "lab.yaml"


def resolve_lab_path(explicit=None):
    """Find lab.yaml: -f flag, env var, current dir, then user config dir."""
    if explicit:
        return Path(explicit)

    env = os.environ.get("LABTOOL_FILE")
    if env:
        return Path(env)

    for candidate in (Path("lab.yaml"), user_config_path()):
        if candidate.exists():
            return candidate

    raise LabError(
        "lab.yaml not found. Create one with: labtool config init\n"
        f"(or pass -f PATH, or set LABTOOL_FILE). Searched: ./lab.yaml, {user_config_path()}"
    )


def write_template(path, force=False):
    """Write the template; refuse to overwrite unless force=True."""
    path = Path(path)
    if path.exists() and not force:
        raise LabError(f"{path} already exists (use --force to overwrite).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE)
    return path


def load_lab(path):
    """Read and validate the lab file; raise LabError with a clear message."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise LabError(f"File {path} not found")
    except yaml.YAMLError as e:
        raise LabError(f"{path} is not valid YAML: {e}")

    if not isinstance(raw, dict):
        raise LabError(f"{path} is empty or has the wrong format")

    for key in ("domain", "tunnel_name", "nodes"):
        if key not in raw:
            raise LabError(f"{path}: missing required key '{key}'")

    if not isinstance(raw["nodes"], list) or not raw["nodes"]:
        raise LabError(f"{path}: 'nodes' must be a non-empty list")

    try:
        nodes = tuple(Node(**n) for n in raw["nodes"])
        return Lab(domain=raw["domain"], tunnel_name=raw["tunnel_name"], nodes=nodes)
    except (TypeError, ValueError) as e:
        # TypeError: unknown/missing node field, ValueError: invalid IP, duplicate names
        raise LabError(f"{path}: invalid node definition: {e}")
    