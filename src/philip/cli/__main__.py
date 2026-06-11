"""Philip CLI — rub standalone adapter."""

import contextlib
import io
import sys
import warnings

# Suppress SyntaxWarnings from third-party packages (jieba on Python 3.14)
if not sys.warnoptions:
    warnings.filterwarnings("ignore", category=SyntaxWarning)

# Pre-import jieba silently (suppresses "Building prefix dict" logger output)
import logging
logging.getLogger("jieba").setLevel(logging.WARNING)
import jieba  # noqa: F401
jieba.setLogLevel(logging.WARNING)

from rub.standalone import standalone_cli

from philip.cli.adapter import PhilipAdapter

app = standalone_cli(PhilipAdapter(), name="philip", default_url="philip://local")
