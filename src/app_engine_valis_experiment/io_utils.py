import pathlib
from dataclasses import dataclass
from typing import Literal


@dataclass
class InputData:
    fixed_image: pathlib.Path
    moving_image: pathlib.Path
    geometry_moving: pathlib.Path


def _expect(path: pathlib.Path, kind: Literal["dir", "file", "any"]):
    if not path.exists():
        raise ValueError(f"{path=} does not exist")

    if kind == "file":
        if not path.is_file():
            raise ValueError(f"expected a file at {path=}")
        return

    if kind == "dir":
        if not path.is_dir():
            raise ValueError(f"expected a dir at {path=}")
        return

    if kind != "any":  # safeguard
        raise ValueError(f"{kind=!r} is invalid")


def get_io_dirs():
    dir_i = pathlib.Path("/inputs")
    dir_o = pathlib.Path("/outputs")

    _expect(dir_i, "dir")
    _expect(dir_o, "dir")

    return dir_i, dir_o


def find_inputs():
    dir_i, _ = get_io_dirs()

    # TODO
    #   - extension was removed, but only png, jpeg and tiff are present
    # for now, hope that VALIS will guess it right...

    fixed_image = dir_i / "fixed_image"
    _expect(fixed_image, "file")
    moving_image = dir_i / "moving_image"
    _expect(moving_image, "file")
    geometry_moving = dir_i / "geometry_moving"
    _expect(geometry_moving, "file")

    return InputData(fixed_image, moving_image, geometry_moving)
