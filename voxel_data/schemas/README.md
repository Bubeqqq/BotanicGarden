# Voxel parameter schemas

One file per voxel type (`type_<id>_<name>.json`). Each one says what the 8 parameters `s0..s7` in `voxel_data.json` mean for voxels of that type. These files are the reference for the field meanings: the shader includes point here, and the block editor (`_python/BlocksAndRulesDefinitions.py`) reads them to label fields, show hints and check references.

When you change a rule in `simulation/compute/*.glslinc`, update the matching schema too.

## Format

```jsonc
{
  "type": 2,                         // voxel type id (index >> 11)
  "name": "Plants",
  "shader": "simulation/compute/flower.glslinc",
  "description": "...",
  "variant_field": "s0",             // optional: field whose value picks a variant
  "fields": { "s1": { ... } },       // fields that mean the same in every variant
  "variants": {                      // optional, keyed by the variant field's value
    "0": { "name": "Seed", "description": "...", "fields": { "s2": { ... } } }
  }
}
```

A field not listed for a voxel is unused.

Field keys:

| Key | Meaning |
|---|---|
| `label` | Name shown in the editor |
| `short` | Short name for narrow table headers |
| `kind` | `variant`, `index`, `speed`, `limit`, `flag`, `species` or `number` (see below) |
| `description` | What the shader does with it |
| `default` | Value the shader uses when the field is 0 (`speed` and `limit`) |
| `zero` | What 0 means, when it isn't "use the default" |
| `scale` | `speed` only: chance per step = value × scale |
| `target` | `index` only: `{ "type": 2, "variant": 1 }`, what the referenced voxel should be (`variant` may also be a list) |
| `read` | `false` if the shader currently ignores the field |
| `max` | Largest value the shaders can handle, when lower than 65535 (e.g. species id: 2047) |

Kinds:

- `variant`: picks the variant (for plants, the plant part).
- `index`: points at another voxel index. 0 = none, so the transition never happens.
- `speed`: chance per simulation step (50 steps per second), value × `scale`. 0 = use `default`.
- `limit`: count or distance. 0 = use `default` (or what `zero` says).
- `flag`: 0 = off, anything else = on.
- `species`: id shared by all parts of one species, different for every species (`Analysis.glsl` groups plant counts by it; 0 = not recorded).
- `number`: plain number.
