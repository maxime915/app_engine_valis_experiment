import pathlib
import sys
from contextlib import contextmanager
from io import StringIO

from app_engine_valis_experiment.io_utils import find_inputs
from app_engine_valis_experiment.register import register


@contextmanager
def replace_out_err():
    bkp = sys.stdout, sys.stderr
    o, e = StringIO(), StringIO()
    sys.stdout, sys.stderr = o, e
    try:
        yield o, e
    finally:
        sys.stdout, sys.stderr = bkp


inputs = find_inputs()
with replace_out_err() as (stdout, stderr):
    register(inputs)

pathlib.Path("/outputs/valis_stdout").write_text(stdout.getvalue())
pathlib.Path("/outputs/valis_stderr").write_text(stderr.getvalue())
