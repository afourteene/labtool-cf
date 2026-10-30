import pytest

from labtool.adapters import lab_file
from labtool.adapters.lab_file import (
    TEMPLATE,
    load_lab,
    resolve_lab_path,
    write_template,
)
from labtool.domain import LabError

VALID = """\
domain: example.com
tunnel_name: t
nodes:
  - name: a
    ip: 10.0.0.1
  - name: b
    ip: 10.0.0.2
"""


def write(path, text):
    path.write_text(text)
    return path




def test_load_valid_file(tmp_path):
    lab = load_lab(write(tmp_path / "lab.yaml", VALID))
    assert lab.domain == "example.com"
    assert lab.tunnel_name == "t"
    assert [n.name for n in lab.nodes] == ["a", "b"]
    assert lab.nodes[0].ip == "10.0.0.1"


def test_load_missing_file(tmp_path):
    with pytest.raises(LabError, match="not found"):
        load_lab(tmp_path / "nope.yaml")


def test_load_empty_file(tmp_path):
    with pytest.raises(LabError, match="empty or has the wrong format"):
        load_lab(write(tmp_path / "lab.yaml", ""))


def test_load_comment_only_file(tmp_path):
    with pytest.raises(LabError, match="empty or has the wrong format"):
        load_lab(write(tmp_path / "lab.yaml", "# nothing here\n"))


def test_load_yaml_that_is_a_list(tmp_path):
    with pytest.raises(LabError, match="wrong format"):
        load_lab(write(tmp_path / "lab.yaml", "- a\n- b\n"))


def test_load_invalid_yaml(tmp_path):
    with pytest.raises(LabError, match="not valid YAML"):
        load_lab(write(tmp_path / "lab.yaml", "domain: [\n"))


@pytest.mark.parametrize("key", ["domain", "tunnel_name", "nodes"])
def test_load_missing_required_key(tmp_path, key):
    lines = [l for l in VALID.splitlines() if not l.startswith(key)]
    text = "\n".join(lines) if key != "nodes" else "domain: example.com\ntunnel_name: t\n"
    with pytest.raises(LabError, match=f"missing required key '{key}'"):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_empty_nodes_list(tmp_path):
    text = "domain: example.com\ntunnel_name: t\nnodes: []\n"
    with pytest.raises(LabError, match="non-empty list"):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_nodes_not_a_list(tmp_path):
    text = "domain: example.com\ntunnel_name: t\nnodes: node1\n"
    with pytest.raises(LabError, match="non-empty list"):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_invalid_ip(tmp_path):
    text = VALID.replace("10.0.0.2", "192.168.56.999")
    with pytest.raises(LabError, match="invalid node definition"):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_duplicate_node_names(tmp_path):
    text = VALID.replace("name: b", "name: a")
    with pytest.raises(LabError):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_node_with_unknown_field(tmp_path):
    text = VALID.replace("ip: 10.0.0.1", "ip: 10.0.0.1\n    color: red")
    with pytest.raises(LabError, match="invalid node definition"):
        load_lab(write(tmp_path / "lab.yaml", text))


def test_load_node_missing_ip(tmp_path):
    text = "domain: example.com\ntunnel_name: t\nnodes:\n  - name: a\n"
    with pytest.raises(LabError, match="invalid node definition"):
        load_lab(write(tmp_path / "lab.yaml", text))




@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated world: empty cwd, empty user config dir, no LABTOOL_FILE."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    user_file = tmp_path / "userdir" / "lab.yaml"

    monkeypatch.chdir(cwd)
    monkeypatch.delenv("LABTOOL_FILE", raising=False)
    monkeypatch.setattr(lab_file, "user_config_path", lambda: user_file)
    return {"cwd": cwd, "user_file": user_file, "tmp": tmp_path}


def test_resolve_explicit_path_wins(env, monkeypatch):
    monkeypatch.setenv("LABTOOL_FILE", str(env["tmp"] / "from_env.yaml"))
    write(env["cwd"] / "lab.yaml", VALID)
    assert resolve_lab_path("explicit.yaml").name == "explicit.yaml"


def test_resolve_env_beats_current_dir(env, monkeypatch):
    write(env["cwd"] / "lab.yaml", VALID)
    monkeypatch.setenv("LABTOOL_FILE", str(env["tmp"] / "from_env.yaml"))
    assert resolve_lab_path().name == "from_env.yaml"


def test_resolve_current_dir_beats_user_config(env):
    write(env["cwd"] / "lab.yaml", VALID)
    env["user_file"].parent.mkdir()
    write(env["user_file"], VALID)
    assert str(resolve_lab_path()) == "lab.yaml"


def test_resolve_falls_back_to_user_config(env):
    env["user_file"].parent.mkdir()
    write(env["user_file"], VALID)
    assert resolve_lab_path() == env["user_file"]


def test_resolve_nothing_found_gives_helpful_error(env):
    with pytest.raises(LabError) as exc:
        resolve_lab_path()
    message = str(exc.value)
    assert "labtool config init" in message
    assert str(env["user_file"]) in message



def test_template_creates_file_and_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "dir" / "lab.yaml"
    result = write_template(target)
    assert result == target
    assert target.read_text() == TEMPLATE


def test_template_refuses_to_overwrite(tmp_path):
    target = write(tmp_path / "lab.yaml", "keep me")
    with pytest.raises(LabError, match="already exists"):
        write_template(target)
    assert target.read_text() == "keep me"


def test_template_force_overwrites(tmp_path):
    target = write(tmp_path / "lab.yaml", "old")
    write_template(target, force=True)
    assert target.read_text() == TEMPLATE


def test_template_is_a_valid_lab_file(tmp_path):
    """The generated template must load without errors."""
    target = write_template(tmp_path / "lab.yaml")
    lab = load_lab(target)
    assert lab.domain == "example.com"
    assert len(lab.nodes) >= 1