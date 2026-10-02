import logging
import os
import pathlib
import sys
import traceback
from contextlib import contextmanager


@contextmanager
def replace_out_err(out_path: pathlib.Path, err_path: pathlib.Path):
    "redirect fd 1/2 (Python, native and JVM output alike) to the given files"
    sys.stdout.flush()
    sys.stderr.flush()
    bkp_out, bkp_err = os.dup(1), os.dup(2)
    with open(out_path, "wb") as o, open(err_path, "wb") as e:
        os.dup2(o.fileno(), 1)
        os.dup2(e.fileno(), 2)
        try:
            yield
        except BaseException:
            traceback.print_exc()
            raise
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(bkp_out, 1)
            os.dup2(bkp_err, 2)
            os.close(bkp_out)
            os.close(bkp_err)

def make_logger(stream) -> logging.Logger:
    logger = logging.getLogger("valis_app")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    return logger


# keep a handle on the real stderr before fd 2 is redirected to a file
true_stderr = os.fdopen(os.dup(2), "w", buffering=1, encoding="utf8")
logger = make_logger(true_stderr)

with replace_out_err(
    pathlib.Path("/outputs/valis_stdout"), pathlib.Path("/outputs/valis_stderr")
):
    from app_engine_valis_experiment.io_utils import find_inputs
    from app_engine_valis_experiment.register import register

    register(find_inputs(), logger)
