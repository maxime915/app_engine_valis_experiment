# app_engine_valis_experiment

Experiment to integrate [VALIS](https://github.com/MathOnco/valis) (Virtual
Alignment of pathoLogy Image Series) with the new
[Cytomine App Engine](https://doc.uliege.cytomine.org/user-guide/appengine).

This app registers ("aligns") two whole-slide images and warps a geometry
(annotation) from the moving image onto the fixed image, using VALIS as the
registration engine.

## Table of contents

- [Building the app](#building-the-app)
- [Uploading the app to Cytomine](#uploading-the-app-to-cytomine)
- [Using the app in Cytomine](#using-the-app-in-cytomine)
  - [Inputs](#inputs)
  - [Outputs](#outputs)
  - [Tips for best results](#tips-for-best-results)
  - [Troubleshooting](#troubleshooting)

## Building the app

The app is packaged as a zip archive containing a Docker image (tar) and a
`descriptor.yaml`, as required by the App Engine task format.

Building it requires Docker, `make`, `curl` and
[`uv`](https://docs.astral.sh/uv/) (used to validate the descriptor):

```sh
make zip
```

This will:

1. Validate `descriptor.yaml` against the JSON schema referenced by its
   `$schema` field. The schema is downloaded once and cached in `.cache/`
   (delete that folder to fetch it again). Validation is strict: keys that
   the schema does not declare (e.g. a typo such as `cpu` instead of `cpus`)
   are rejected, except `name_short`, used by the Makefile. It also checks that
   `configuration.image.file` matches `/<name_short>-<version>.tar` (both
   read from `descriptor.yaml`). This step alone can be run with
   `make descriptor`.
2. Build the Docker image described by the `Dockerfile`.
3. Save it as `app_engine_valis_exp-<version>.tar`.
4. Produce `app_engine_valis_exp.zip`, ready to be uploaded to Cytomine.
   The archive also contains `logo.png`, which Cytomine displays as the
   task's icon.

> To publish a new task version, bump `version` and `configuration.image.file`
> in `descriptor.yaml` before rebuilding.

## Uploading the app to Cytomine

Once `app_engine_valis_exp.zip` has been built, it must be uploaded to the App
Engine so it becomes available as a task in your Cytomine instance.

Follow the official Cytomine App Engine documentation for how to upload and
run tasks:
<https://doc.uliege.cytomine.org/user-guide/appengine>

> 📷 *Suggested screenshot: the App Engine "upload task" page in Cytomine,
> showing the zip file being selected/uploaded.*

## Using the app in Cytomine

Once uploaded, the task appears as **VALIS experiment** in the list of
available App Engine tasks and can be run against images stored in a
Cytomine project.

> 📷 *Suggested screenshot: the task listed in the App Engine task catalog,
> with its name and version visible.*

### Inputs

| Input | Type | Description |
|---|---|---|
| **Fixed Image** | image | The reference image. It stays unchanged; the moving image is aligned onto it. |
| **Moving Image** | image | The image that will be deformed/aligned to match the fixed image. |
| **Geometry on Moving Image** | geometry | An annotation/geometry (GeoJSON) drawn on the moving image. **Optional**: if omitted, no geometry output is produced. Otherwise it is warped both into the registration space and onto the fixed image (see outputs). |
| **Cropping Mode** | enumeration: `reference`, `all`, `overlap` (default `all`) | Which region of the images is kept/considered for registration. `reference` crops to the fixed image's content, `overlap` keeps only the area common to both images after alignment, `all` keeps the union of both images. **`all` is recommended** in most cases since it avoids losing image content. |
| **Registration Type** | enumeration: `rigid`, `non-rigid`, `micro` (default `non-rigid`) | The registration algorithm to run. `rigid` only estimates translation/rotation/scale. `non-rigid` additionally performs a non-rigid (deformable) registration at low resolution. `micro` performs an additional non-rigid registration pass at high resolution, refining the result of `non-rigid` (it always runs the low-resolution steps first). |
| **Low Resolution** | integer ≥ 100 (default `850`) | The maximum image dimension (in pixels) used while computing the rigid and non-rigid registrations. Larger values give more precise alignment but take longer and use more memory. Must not exceed High Resolution when the latter is given. |
| **High Resolution** | integer ≥ 100 (default `3000`) | The maximum image dimension (in pixels) used for the `micro` registration pass. **Optional**, but required when Registration Type is `micro` (ignored otherwise). When given, must be **greater than or equal to** Low Resolution. |

> 📷 *Suggested screenshot: the task's parameter form in Cytomine, showing
> the image pickers and the enumeration/integer fields described above.*

### Outputs

| Output | Type | Description |
|---|---|---|
| **Deformed Moving Image** | image | The moving image after being warped to align with the fixed image. |
| **Deformed Geometry (Fixed Image)** | geometry | The input geometry mapped onto the (unwarped) fixed image's coordinates, attached to the fixed image. Only produced if a geometry is given. |
| **Deformed Geometry (Registration Space)** | geometry | The input geometry warped into the registration space, i.e. the coordinates of the Deformed Moving Image. With `crop: all`/`overlap` this space is padded/cropped and differs from the fixed image. Only produced if a geometry is given. |
| **VALIS log (out)** | file | Captured standard output from the VALIS registration run. Useful to inspect matching quality/statistics. |
| **VALIS log (err)** | file | Captured standard error from the VALIS registration run. Check this first if a run fails or produces unexpected results. |

> 📷 *Suggested screenshot: the results panel showing the deformed image
> overlayed/compared with the fixed image, and the warped geometry.*
>
> 📷 *Suggested screenshot: viewing the `valis_stdout`/`valis_stderr` output
> files from a completed run.*

### Tips for best results

- Prefer **`crop: all`** unless you specifically need the output cropped to
  the overlapping region — it avoids discarding image content that falls
  outside the fixed image's bounds.
- Start with **`registration_type: non-rigid`** for tissue sections that are
  not perfectly rigid (which is the common case for serial sections); use
  `rigid` only when you know the images are simple translations/rotations of
  each other (e.g. re-scans of the same physical slide).
- Use `micro` only when fine, high-resolution alignment is required (e.g. for
  cell-level analysis) — it is significantly slower since it reprocesses the
  images at a higher **High Resolution**.
- Keep **Low Resolution** modest (e.g. `850`–`1500`) to keep runtimes
  reasonable; increase it only if the alignment quality at lower resolution
  is insufficient.
- **High Resolution** should be set high enough to capture the detail you
  need (e.g. `3000` or more) but drives most of the runtime/memory cost when
  `registration_type: micro` is used.
- Only PNG, JPEG and TIFF image formats are supported as inputs (this is a
  VALIS limitation); the task declares these formats so other images are
  rejected before running.

### Troubleshooting

- If the task fails, always check the **VALIS log (err)** output first — it
  contains the underlying Python/VALIS traceback.
- Registration runtime scales with **Low Resolution**/**High Resolution** and
  image size; if a run times out or runs out of memory, try lowering these
  values.
