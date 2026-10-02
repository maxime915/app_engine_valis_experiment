import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from valis import registration

from .io_utils import InputData, get_io_dirs

# FIX: otherwise PIL refuses to open certain large image files
Image.MAX_IMAGE_PIXELS = 15 * 16 * (1024 * 1024 * 1024 // 4 // 3)


@contextmanager
def _step(logger: logging.Logger, message: str):
    "log the start, end (or failure) and duration of a step"
    logger.info("%s...", message)
    start = time.perf_counter()
    try:
        yield
    except BaseException:
        logger.error("%s failed after %.1fs", message, time.perf_counter() - start)
        raise
    logger.info("%s done in %.1fs", message, time.perf_counter() - start)


def _read_int(path: str) -> int | None:
    try:
        with open(path, encoding="utf8") as f:
            raw = f.read().strip()
        return None if raw == "max" else int(raw)
    except (OSError, ValueError):
        return None


def _available_memory() -> tuple[int | None, int | None]:
    "return (host available bytes, container limit bytes), when known"
    host = None
    try:
        with open("/proc/meminfo", encoding="utf8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    host = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    limit = _read_int("/sys/fs/cgroup/memory.max")  # cgroup v2
    if limit is None:
        limit = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")  # v1
    if limit is not None and limit >= 1 << 60:  # "unlimited" sentinel
        limit = None
    return host, limit


def _cpu_count() -> tuple[int, int | None]:
    "return (cores usable by this process, cgroup cpu quota in cores)"
    usable = len(os.sched_getaffinity(0))
    quota = None
    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="utf8") as f:
            q, period = f.read().split()
        if q != "max":
            quota = int(q) / int(period)
    except (OSError, ValueError):
        pass
    return usable, quota


def _gib(n: int | None) -> str:
    return "unknown" if n is None else f"{n / 1024**3:.2f} GiB"


def _log_environment(logger: logging.Logger):
    usable, quota = _cpu_count()
    logger.info(
        "CPU cores: %d usable (%s total)%s",
        usable,
        os.cpu_count(),
        "" if quota is None else f", cgroup quota {quota:.2f} cores",
    )
    host, limit = _available_memory()
    logger.info(
        "memory: %s available on host, container limit: %s",
        _gib(host),
        "none" if limit is None else _gib(limit),
    )
    try:
        import torch

        if torch.cuda.is_available():
            names = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
            logger.info("GPU found: %s", ", ".join(names))
        else:
            logger.info("no GPU found (CUDA unavailable), running on CPU")
    except ImportError:
        logger.info("GPU status unknown: torch is not installed")
    except Exception as e:
        logger.warning("could not query GPU: %r", e)


def _name_with_ext(path: Path):
    "return a name with an appropriate extension for an image file"
    with Image.open(path) as img:
        match img.format:
            case "PNG":
                return path.with_suffix(".png").name
            case "JPEG":
                return path.with_suffix(".jpeg").name
            case "TIFF":
                return path.with_suffix(".tiff").name
        raise ValueError(f"{img.format=!r} is not supported")


def _write_geometry(path: Path, warped: dict):
    "map back from the VALIS feature collection to a single GeoJSON geometry"
    with open(path, "x", encoding="utf8") as out_geom_f:
        json.dump(warped["features"][0]["geometry"], out_geom_f)


def _warp_geometry(
    data: InputData,
    work_dir: Path,
    o_dir: Path,
    moving_slide: registration.Slide,
    fixed_slide: registration.Slide,
):
    assert data.geometry_moving is not None
    with open(data.geometry_moving, "r", encoding="utf8") as s_geom_f:
        s_geom_d = json.load(s_geom_f)

    # VALIS expects a feature collection rather than a bare geometry
    dup_geo = work_dir / "tmp-geo.json"
    with open(dup_geo, "x", encoding="utf8") as dup_geo_f:
        json.dump({"type": "INVALID", "features": [{"geometry": s_geom_d}]}, dup_geo_f)

    # registration space: matches the deformed moving image
    _write_geometry(
        o_dir / "deformed_geometry_registration",
        moving_slide.warp_geojson(str(dup_geo)),
    )

    # coordinate space of the (unwarped) fixed image
    _write_geometry(
        o_dir / "deformed_geometry_fixed",
        moving_slide.warp_geojson_from_to(
            str(dup_geo),
            fixed_slide,
            non_rigid=data.registration_type != "rigid",
        ),
    )


def register(data: InputData, logger: logging.Logger):
    total_start = time.perf_counter()
    logger.info("starting registration (%s)", data.registration_type)
    _log_environment(logger)
    logger.info(
        "found 2 images (fixed: %.1f MiB, moving: %.1f MiB) and %d geometr%s",
        data.fixed_image.stat().st_size / 1024**2,
        data.moving_image.stat().st_size / 1024**2,
        0 if data.geometry_moving is None else 1,
        "ies" if data.geometry_moving is None else "y",
    )
    logger.info(
        "parameters: crop=%s max_proc_size=%d micro_max_proc_size=%s",
        data.crop,
        data.max_proc_size,
        data.micro_max_proc_size,
    )

    with _step(logger, "starting the JVM"):
        registration.init_jvm()
    _, o_dir = get_io_dirs()

    # copy everything in a new temporary directory
    with TemporaryDirectory() as tmpdir_:
        work_dir = Path(tmpdir_)
        tmp_src = work_dir / "slides"
        tmp_src.mkdir()

        tmp_dst = work_dir / "outputs"
        tmp_dst.mkdir()

        # NOTE Valis doesn't play well with files without extensions
        #   since only PNG/JPEG/TIFF are supported right now, we can rename them

        # image copy for valis
        fixed_name = _name_with_ext(data.fixed_image)
        moving_name = _name_with_ext(data.moving_image)
        shutil.copy(data.fixed_image, tmp_src / fixed_name)
        shutil.copy(data.moving_image, tmp_src / moving_name)

        # start valis with default options
        registrar = registration.Valis(
            src_dir=str(tmp_src),
            dst_dir=str(tmp_dst),
            name="main",  # useless -> each container will only see one job
            reference_img_f=fixed_name,
            align_to_reference=True,
            crop=data.crop,
            max_image_dim_px=data.max_proc_size,
            max_processed_image_dim_px=data.max_proc_size,
            max_non_rigid_registration_dim_px=data.max_proc_size,
            non_rigid_registrar_cls=(
                None
                if data.registration_type == "rigid"
                else registration.DEFAULT_NON_RIGID_CLASS
            ),  # type: ignore
        )
        if not hasattr(registrar, "rigid_reg_kwargs"):
            registrar.rigid_reg_kwargs = {}
        if not hasattr(registrar, "non_rigid_reg_kwargs"):
            registrar.non_rigid_reg_kwargs = {}
        stages = (
            "rigid" if data.registration_type == "rigid" else "rigid + non-rigid"
        )
        with _step(logger, f"performing {stages} registration"):
            _ = registrar.register()

        if data.registration_type == "micro":
            assert data.micro_max_proc_size is not None
            with _step(logger, "performing micro registration"):
                registrar.register_micro(
                    max_non_rigid_registration_dim_px=data.micro_max_proc_size
                )

        moving_slide: registration.Slide = registrar.get_slide(moving_name)  # type:ignore
        fixed_slide: registration.Slide = registrar.get_slide(fixed_name)  # type:ignore

        if data.geometry_moving is not None:
            with _step(logger, "warping the geometry"):
                _warp_geometry(data, work_dir, o_dir, moving_slide, fixed_slide)

        # warp image
        deformed = tmp_dst / "deformed_moving.ome.tiff"
        with _step(logger, "warping and saving the moving image"):
            moving_slide.warp_and_save_slide(str(deformed))

        shutil.copy(deformed, o_dir / "deformed_moving")
        logger.info("output image size: %.1f MiB", deformed.stat().st_size / 1024**2)

    registration.kill_jvm()
    logger.info("registration finished in %.1fs", time.perf_counter() - total_start)
