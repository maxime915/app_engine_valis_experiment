import json
import shutil
from pathlib import Path
from PIL import Image
from tempfile import TemporaryDirectory

from valis import registration

from .io_utils import InputData, get_io_dirs


# FIX: otherwise PIL refuses to open certain large image files
Image.MAX_IMAGE_PIXELS = 15 * 16 * int(1024 * 1024 * 1024 // 4 // 3)


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
        shutil.copy(data.fixed_image, tmp_src / _name_with_ext(data.fixed_image))
        shutil.copy(data.moving_image, tmp_src / _name_with_ext(data.moving_image))

        # start valis with default options
        registrar = registration.Valis(
            src_dir=str(tmp_src),
            dst_dir=str(tmp_dst),
            name="main",  # useless -> each container will only see one job
            reference_img_f=data.fixed_image.name,
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
            registrar.register_micro(max_non_rigid_registration_dim_px=data.micro_max_proc_size)

        moving_slide: registration.Slide = registrar.get_slide(
            data.moving_image.name
        )  # type:ignore

        with open(data.geometry_moving, "r", encoding="utf8") as s_geom_f:
            s_geom_d = json.load(s_geom_f)

        # VALIS expects a different format for GEOJSON
        dup_geo = work_dir / "tmp-geo.json"
        with open(dup_geo, "x", encoding="utf8") as dup_geo_f:
            json.dump(
                {"type": "INVALID", "features": [{"geometry": s_geom_d}]}, dup_geo_f
            )

        geom_data = moving_slide.warp_geojson(dup_geo)

        # map back to the original GEOJSON format
        geom_data = geom_data["features"][0]["geometry"]

        # dump the warped geometry
        with open(o_dir / "deformed_geometry", "x", encoding="utf8") as out_geom_f:
            json.dump(geom_data, out_geom_f)

        # warp image
        deformed = tmp_dst / "deformed_moving.ome.tiff"
        moving_slide.warp_and_save_slide(str(deformed))

        shutil.copy(deformed, o_dir / "deformed_moving")

    registration.kill_jvm()
