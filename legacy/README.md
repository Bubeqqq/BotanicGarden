# Legacy

Files no longer used by the project, kept for reference.
The `.gdignore` file makes Godot skip this folder: nothing here is imported or exported.
To use a file again, move it back into the project and remove it from here.

| File | Original location | Notes |
|---|---|---|
| `compute/compute_example.glsl` | `Scripts/ComputeShaders/` | Early compute shader example |
| `render/voxel_material.gdshader` | `Scripts/Render/` | Pre-DDA voxel material; replaced by `simulation/render/dda_render.gdshader` (see commented code in `WorldRender.SetupMaterial`) |
| `menu/icon.svg` | `Menu/` | Duplicate of the root `icon.svg`, not referenced anywhere |
