"""pyproject.toml tests."""
from flake8_nitpick import PyProjectTomlChecker
from tests.helpers import ProjectMock


def test_missing_pyproject_toml(request):
    """Suggest poetry init when pyproject.toml does not exist."""
    assert ProjectMock(request, pyproject_toml=False).lint().errors == {
        f"NIP201 {PyProjectTomlChecker.file_name} does not exist. Run 'poetry init' to create one."
    }