import pathlib
from typing import Literal

import pydantic


class InputData(pydantic.BaseModel):
    fixed_image: pathlib.Path
    moving_image: pathlib.Path
    geometry_moving: pathlib.Path
    crop: Literal["reference", "all", "overlap"]
    registration_type: Literal["rigid", "non-rigid", "micro"]
    max_proc_size: int  # 850
    micro_max_proc_size: int  # 3000

    @pydantic.root_validator(pre=True)
    def check_fields(cls, values):
        proc, micro = values.get("max_proc_size"), values.get("micro_max_proc_size")
        if proc < 100:
            raise ValueError(f"max_proc_size={proc} < 100")
        if micro < 100:
            raise ValueError(f"micro_max_proc_size={micro} < 100")

        if proc > micro:
            raise ValueError(
                f"max_proc_size={proc} should not be higher "
                f"than micro_max_proc_size={micro}"
            )
        return values


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


def read_parameter(input_dir: pathlib.Path, key: str):
    with open(input_dir / key, "r", encoding="utf8") as param_file:
        return param_file.read().strip()


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

    return InputData(
        fixed_image=fixed_image,
        moving_image=moving_image,
        geometry_moving=geometry_moving,
        crop=read_parameter(dir_i, "crop"),  # type: ignore
        registration_type=read_parameter(dir_i, "registration_type"),  # type: ignore
        max_proc_size=int(read_parameter(dir_i, "max_proc_size")),
        micro_max_proc_size=int(read_parameter(dir_i, "micro_max_proc_size")),
    )
