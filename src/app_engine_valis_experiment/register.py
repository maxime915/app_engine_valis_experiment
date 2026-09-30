import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from valis import registration

from .io_utils import InputData, get_io_dirs

# FIX: otherwise PIL refuses to open certain large image files
Image.MAX_IMAGE_PIXELS = 15 * 16 * (1024 * 1024 * 1024 // 4 // 3)


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


def register(data: InputData):
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
        _ = registrar.register()

        if data.registration_type == "micro":
            assert data.micro_max_proc_size is not None
            registrar.register_micro(
                max_non_rigid_registration_dim_px=data.micro_max_proc_size
            )

        moving_slide: registration.Slide = registrar.get_slide(moving_name)  # type:ignore
        fixed_slide: registration.Slide = registrar.get_slide(fixed_name)  # type:ignore

        if data.geometry_moving is not None:
            _warp_geometry(data, work_dir, o_dir, moving_slide, fixed_slide)

        # warp image
        deformed = tmp_dst / "deformed_moving.ome.tiff"
        moving_slide.warp_and_save_slide(str(deformed))

        shutil.copy(deformed, o_dir / "deformed_moving")

    registration.kill_jvm()
