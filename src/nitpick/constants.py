"""Constants."""
import os

import jmespath

PROJECT_OWNER = "andreoliwa"
PROJECT_NAME = "nitpick"
FLAKE8_PREFIX = "NIP"
CACHE_DIR_NAME = ".cache"
TOML_EXTENSION = ".toml"
DOT_NITPICK_TOML = f".nitpick{TOML_EXTENSION}"
NITPICK_STYLE_TOML = f"nitpick-style{TOML_EXTENSION}"
MERGED_STYLE_TOML = f"merged-style{TOML_EXTENSION}"
READ_THE_DOCS_URL = "https://nitpick.rtfd.io/en/latest/"

# Special files
# Python
PYPROJECT_TOML = "pyproject.toml"
SETUP_PY = "setup.py"
SETUP_CFG = "setup.cfg"
REQUIREMENTS_STAR_TXT = "requirements*.txt"
PIPFILE_STAR = "Pipfile*"
ROOT_PYTHON_FILES = ("app.py", "wsgi.py", "autoapp.py")
MANAGE_PY = "manage.py"
TOX_INI = "tox.ini"
PYLINTRC = ".pylintrc"
# Tools
PRE_COMMIT_CONFIG_YAML = ".pre-commit-config.yaml"
EDITOR_CONFIG = ".editorconfig"
# JavaScript
PACKAGE_JSON = "package.json"
# Rust
CARGO_STAR = "Cargo.*"
# Golang
GO_MOD = "go.mod"
GO_SUM = "go.sum"
# All root files
ROOT_FILES = (
    DOT_NITPICK_TOML,
    NITPICK_STYLE_TOML,
    PRE_COMMIT_CONFIG_YAML,
    PYPROJECT_TOML,
    SETUP_PY,
    SETUP_CFG,
    REQUIREMENTS_STAR_TXT,
    PIPFILE_STAR,
    TOX_INI,
    PACKAGE_JSON,
    CARGO_STAR,
    GO_MOD,
    GO_SUM,
) + ROOT_PYTHON_FILES
CONFIG_FILES = (DOT_NITPICK_TOML, PYPROJECT_TOML)

SINGLE_QUOTE = "'"
DOUBLE_QUOTE = '"'

#: Special unique separator for :py:meth:`flatten()` and :py:meth:`unflatten()`,
# to avoid collision with existing key values (e.g. the default dot separator "." can be part of a pyproject.toml key).
SEPARATOR_FLATTEN = "$#@"

#: Special unique separator for :py:meth:`nitpick.generic.quoted_split()`.
SEPARATOR_QUOTED_SPLIT = "#$@"

# Config sections and keys
TOOL_NITPICK = "tool.nitpick"

# JMESPath expressions
TOOL_NITPICK_JMEX = jmespath.compile(TOOL_NITPICK)
NITPICK_STYLES_INCLUDE_JMEX = jmespath.compile("nitpick.styles.include")
NITPICK_MINIMUM_VERSION_JMEX = jmespath.compile("nitpick.minimum_version")

#: Dot/slash is used to indicate a local style file
SLASH = os.path.sep
DOT_SLASH = f".{SLASH}"
