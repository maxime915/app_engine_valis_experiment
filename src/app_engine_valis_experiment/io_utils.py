import pathlib
from typing import Literal

import pydantic


class InputData(pydantic.BaseModel):
    fixed_image: pathlib.Path
    moving_image: pathlib.Path
    geometry_moving: pathlib.Path | None = None
    crop: Literal["reference", "all", "overlap"]
    registration_type: Literal["rigid", "non-rigid", "micro"]
    max_proc_size: int = pydantic.Field(ge=100)
    micro_max_proc_size: int | None = pydantic.Field(default=None, ge=100)

    @pydantic.model_validator(mode="after")
    def check_fields(self):
        proc, micro = self.max_proc_size, self.micro_max_proc_size
        if self.registration_type == "micro" and micro is None:
            raise ValueError("micro_max_proc_size is required for micro registration")
        if micro is not None and proc > micro:
            raise ValueError(
                f"max_proc_size={proc} should not be higher "
                f"than micro_max_proc_size={micro}"
            )
        return self


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


def read_optional_parameter(input_dir: pathlib.Path, key: str):
    if not (input_dir / key).is_file():
        return None
    return read_parameter(input_dir, key)


def find_inputs():
    dir_i, _ = get_io_dirs()

    fixed_image = dir_i / "fixed_image"
    _expect(fixed_image, "file")
    moving_image = dir_i / "moving_image"
    _expect(moving_image, "file")
    geometry_moving = dir_i / "geometry_moving"
    if not geometry_moving.is_file():
        geometry_moving = None

    micro_max_proc_size = read_optional_parameter(dir_i, "micro_max_proc_size")

    return InputData(
        fixed_image=fixed_image,
        moving_image=moving_image,
        geometry_moving=geometry_moving,
        crop=read_parameter(dir_i, "crop"),  # type: ignore
        registration_type=read_parameter(dir_i, "registration_type"),  # type: ignore
        max_proc_size=int(read_parameter(dir_i, "max_proc_size")),
        micro_max_proc_size=(
            None if not micro_max_proc_size else int(micro_max_proc_size)
        ),
    )
