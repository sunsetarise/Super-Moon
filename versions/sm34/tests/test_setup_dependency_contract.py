from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SCIPY_PIN = "scipy==1.17.0"


def dependency_lines(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_scientific_runtime_dependency_is_installed_and_preflighted():
    py314 = dependency_lines(ROOT / "requirements-py314.txt")
    generic = dependency_lines(ROOT / "requirements.txt")
    assert py314 == generic
    assert SCIPY_PIN in py314

    bootstrap = (ROOT / "tools" / "windows_bootstrap.py").read_text("utf-8")
    assert bootstrap.count('    "scipy",') >= 2

    project = tomllib.loads(
        (ROOT / "supermoon_runtime" / "pyproject.toml").read_text("utf-8")
    )
    assert SCIPY_PIN in project["project"]["dependencies"]
