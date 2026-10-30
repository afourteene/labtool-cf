# labtool

A small CLI that sets up and manages a Cloudflare Tunnel (`cloudflared`) for machines behind NAT, so they can be reached over the internet without opening any ports.

Everything is described in one file, `lab.yaml`. The tool turns it into a tunnel, DNS records and a `cloudflared` `config.yml`.

## Requirements

- Python 3.10+
- A domain managed by Cloudflare (status: Active)
- A Cloudflare account (used once for `labtool login`)
- `cloudflared` (the tool can install it for you: `labtool install`)

## Using your domain with Cloudflare

`labtool` creates DNS records such as `node1.example.com`, so your domain must be managed by Cloudflare (its nameservers must point to Cloudflare). You only do this once per domain.

### Option A: you already own a domain at another registrar

1. Create a free account at [dash.cloudflare.com](https://dash.cloudflare.com).
2. Go to **Domains** and click **Add domain**. Enter your domain (for example `example.com`) and choose the **Free** plan.
3. Cloudflare scans your existing DNS records. Review them and continue. Keep any records you still need (website, mail).
4. Cloudflare shows you two nameservers, for example `xxx.ns.cloudflare.com` and `yyy.ns.cloudflare.com`.
5. Log in to your registrar (where you bought the domain), open the domain's nameserver settings, and replace the current nameservers with the two from Cloudflare.
6. Wait until the domain shows **Active** in the Cloudflare dashboard. This usually takes minutes, but can take up to 24 hours.

Check from the terminal:

```bash
dig +short NS example.com
```

The output should list the two `*.ns.cloudflare.com` servers.

### Option B: buy the domain from Cloudflare

In the dashboard choose **Domains**, then **Buy domain**. A domain bought there is managed by Cloudflare right away; there is nothing to move.

### Authorize labtool for that domain

Run:

```bash
labtool login
```

Open the printed URL, log in, and **select your domain** on the authorization page. Cloudflare saves a `cert.pem` that lets `labtool` create tunnels and DNS records for that domain only. If you own several domains, pick the one set as `domain:` in `lab.yaml`.

### What `labtool init` does to your DNS

For every node in `lab.yaml` it creates a proxied `CNAME` record that points to the tunnel:

| Record | Type | Points to |
|---|---|---|
| `node1.example.com` | CNAME (proxied) | `<TUNNEL_ID>.cfargotunnel.com` |

Notes:

- No server IP is stored in DNS, and no port has to be opened on your machines.
- If a record with the same name already exists, `init` overwrites it. Do not reuse a hostname that serves something else.
- To use a subdomain only for this tool, set `domain: lab.example.com` in `lab.yaml`; nodes then become `node1.lab.example.com`.
- After `labtool delete`, the CNAME records stay in DNS. Remove them in the dashboard under **DNS > Records**.
- The free plan is enough. No payment method is needed for DNS and tunnels.

### Troubleshooting the domain

| Problem | Fix |
|---|---|
| Domain stays **Pending** | Nameservers at the registrar are not changed yet, or have not propagated. Re-check step 5 and wait. |
| `labtool init` cannot create DNS records | The domain is not Active, or you selected a different domain during `labtool login`. Delete `~/.cloudflared/cert.pem` and run `labtool login` again. |
| `node1.example.com` does not resolve | The record is missing. Run `labtool init` again and check the dashboard under **DNS > Records**. |

## Installation

### From PyPI (recommended)

```bash
pipx install labtool-cf
labtool -h
```

`pipx` installs the tool in its own isolated environment, so it does not clash with system Python packages. You can also use `pip install labtool-cf` inside a virtual environment. The package is called `labtool-cf`; the command it installs is `labtool`.

Upgrade with `pipx upgrade labtool-cf`.

### From source (development)

From the project root (the folder containing `pyproject.toml`):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
labtool -h
```

For development (tests):

```bash
pip install pytest
pytest -v
```

You can also run it as a module: `python -m labtool -h`.

## Configuration: `lab.yaml`

```yaml
domain: example.com        # a domain active on Cloudflare
tunnel_name: my-tunnel     # name of the tunnel
nodes:
  - name: node1            # becomes node1.example.com
    ip: 192.168.56.11      # address the tunnel machine can reach
  - name: node2
    ip: 192.168.56.12
```

Each node is exposed as `ssh://<ip>:22` under `<name>.<domain>`.

### Creating the file

The easiest way is to let the tool create a template for you:

```bash
labtool config init          # creates the file in your user config directory
labtool config path          # shows which file will be used
```

Then edit the file it printed (set `domain`, `tunnel_name` and `nodes`). Useful options:

- `labtool config init --local` creates `./lab.yaml` in the current folder instead.
- `labtool config init --force` overwrites an existing file (without it, an existing file is never touched).

User config directory:

| System | Path |
|---|---|
| Linux | `~/.config/labtool/lab.yaml` |
| macOS | `~/Library/Application Support/labtool/lab.yaml` |
| Windows | `%APPDATA%\labtool\lab.yaml` |

### Where the tool looks for the file

The first match wins:

1. The `-f PATH` option
2. The `LABTOOL_FILE` environment variable
3. `./lab.yaml` in the current folder
4. The user config directory (table above)

If none exists, the command stops and tells you to run `labtool config init`.

You can keep one `lab.yaml` per project (use option 3 or `-f`), or one global file for everything (option 4). For scripts and CI, set `LABTOOL_FILE`:

```bash
export LABTOOL_FILE=/path/to/lab.yaml
labtool init
```

## Quick start

```bash
labtool install      # 1. install cloudflared for this OS
labtool config init  # 2. create a template lab.yaml, then edit it
labtool login        # 3. authorize with Cloudflare (creates cert.pem)
labtool init         # 4. create tunnel + DNS records + config.yml
labtool up           # 5. run the tunnel in the background
labtool status       # 6. check it
labtool down         # 7. stop it
```

## How it works

1. **You describe the lab** in `lab.yaml`: a domain, a tunnel name and a list of nodes (name + IP).
2. **`labtool init`** talks to Cloudflare through the `cloudflared` binary. It creates the tunnel (once), adds a DNS record `<node>.<domain>` for every node, and writes a `config.yml` whose `ingress` rules map each hostname to `ssh://<ip>:22`. A last catch-all rule (`http_status:404`) is added automatically, because `cloudflared` requires it.
3. **`labtool up`** starts `cloudflared tunnel run` in the background and remembers its PID. The tunnel connects *outward* to Cloudflare, so no inbound port is opened.
4. **A client** connects to `node1.example.com`. The request reaches Cloudflare, travels through the tunnel to your machine, and is forwarded to the node's IP.
5. **`labtool down`** stops the process; the hostnames stop working until you run `up` again.

```
client ──ssh──► Cloudflare ──► tunnel (cloudflared on your machine) ──► node IP:22
```

## Commands

Every command supports `-h` / `--help`. `labtool -v` prints the version.

| Command | What it does |
|---|---|
| `install` | Installs `cloudflared` (Homebrew on macOS, `.deb` or binary on Linux, `winget` on Windows). Skips if already installed. |
| `login` | Runs `cloudflared tunnel login`. Prints a URL; open it in any browser and click Authorize. Skips if `cert.pem` already exists. |
| `init` | Logs in if needed, creates the tunnel if missing, routes DNS for every node, and writes `~/.cloudflared/config.yml`. This is the only command that creates the tunnel. |
| `up` | Starts `cloudflared tunnel run` in the background. Does nothing if already running. |
| `down` | Stops the running tunnel. |
| `status` | Shows whether the tunnel is running (and its PID). |
| `delete` | Stops and deletes the tunnel from Cloudflare. Asks for confirmation; `-y` skips the prompt. Irreversible. |

| `config init` | Creates a template `lab.yaml` in the user config directory. Options: `--local` (use `./lab.yaml`), `--force` (overwrite). |
| `config path` | Prints the `lab.yaml` that would be used. |

`init`, `up` and `delete` accept `-f, --file PATH` to choose the lab file (see "Where the tool looks for the file" above). The other commands do not read it.

All commands are safe to run more than once (idempotent).

## Files used

| Path | Purpose |
|---|---|
| `~/.cloudflared/cert.pem` | Result of `login`. Admin access to your domain; treat it like a password. |
| `~/.cloudflared/<TUNNEL_ID>.json` | Tunnel credentials, needed on any machine that runs the tunnel. |
| `~/.cloudflared/config.yml` | Generated by `init`. |
| `lab.yaml` | Your configuration (see "Configuration" above). Not stored inside the package. |
| `~/.labtool/tunnel.pid` | PID of the background tunnel. |
| `~/.labtool/tunnel.log` | `cloudflared` output (check here if `up` fails). |

## Connecting to a node

Install `cloudflared` on the client machine, then:

```bash
ssh -i ~/.ssh/id_rsa \
  -o ProxyCommand="cloudflared access ssh --hostname %h" \
  user@node1.example.com
```

## Running the tunnel on another machine

- `cert.pem` is only needed for management commands (`init`, `delete`). Running a tunnel (`up`) needs only `<TUNNEL_ID>.json` and `config.yml`.
- The credentials file exists only on the machine where the tunnel was created. Either copy it to the other machine, or set a different `tunnel_name` in that machine's `lab.yaml` and run `labtool init` there to create a separate tunnel.
- Do not run the same tunnel on two machines at once unless you want traffic split between them. Stop one with `labtool down` (or `Ctrl+C`).
- `init` overwrites existing DNS records, so they will point to the tunnel you just initialised.

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `Cannot determine default origin certificate path` | No `cert.pem`. Run `labtool login`. |
| `Tunnel credentials file ... doesn't exist` | Credentials are missing on this machine. Copy the `.json`, or create a tunnel here. |
| `cloudflared exited immediately` | Check `~/.labtool/tunnel.log` (bad config or missing credentials). |
| `You have an existing certificate ... which login would overwrite` | You are already logged in. Nothing to do. |
| `lab.yaml not found` | No file in any searched location. Run `labtool config init`, or pass `-f PATH`. |
| `... is empty or has the wrong format` / `missing required key` | The file is empty or incomplete. It needs `domain`, `tunnel_name` and a non-empty `nodes` list. |
| `No module named labtool.cli` | `cli.py` must be in `src/labtool/`; then run `pip install -e .` again. |

`Ctrl+C` cancels any command cleanly (exit code 130).

## Project layout

```
labtool/
├── pyproject.toml
├── lab.yaml
├── src/labtool/
│   ├── cli.py            # click commands only (wiring)
│   ├── ui.py             # colored output
│   ├── services.py       # use cases: init, up, down, delete, ...
│   ├── domain.py         # models and pure rules, no I/O
│   ├── config_builder.py # pure function: Lab -> tunnel config
│   ├── ports.py          # interfaces
│   └── adapters/         # cloudflared, process runner, system, lab file
└── tests/                # run with pytest, using fakes (no Cloudflare needed)
```

Dependencies point inward: `cli -> services -> domain`, and adapters implement the interfaces in `ports`. Services never import `click` or `subprocess`, which is why they can be tested with fakes.

## Security notes

- Never commit `cert.pem`, `<TUNNEL_ID>.json`, SSH private keys, or tokens. Add them to `.gitignore` (`venv/`, `.labtool/`, `*.json`, `ssh-keys/`).
- Use key-only SSH on the nodes (`PasswordAuthentication no`).
- A tunnel hostname is public while the tunnel runs. Stop it with `labtool down` when you are not using it.