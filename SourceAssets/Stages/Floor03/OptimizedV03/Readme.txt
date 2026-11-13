Floor03 OptimizedV03 — furniture geometry candidate
2026-11-13

Created from the actual SurveyV02/EscapeFromKD_Floor03_v02.blend.
The original source and FBX files were not changed.
Original source SHA256:
2f423416a9b0910777621ee70681fb18a634e2ec88163e7c2633b04745002e3b

Only Chairs and Laptops were changed. Other ten categories were checked for
unchanged vertex/UV/material/transform data. All furniture positions, scales,
rotations and material assignments are preserved.

Chairs:
- Main classroom and instructor: 41 chairs, 7620 -> 3810 triangles per chair.
- Closed CAD classroom: 72 chairs, 7620 -> 1904 triangles per chair.
- Closed adjacent classroom: 60 sled chairs, 1344 -> 672 triangles per chair.
- Whole FBX category: 941700 -> 333618 triangles (64.6% reduction).
- Measured bidirectional sampled surface error:
  main <= 0.568 mm; CAD <= 2.524 mm; adjacent <= 0.512 mm.
  This measures vertices and polygon centers, not a mathematical bound over
  every point of the surface.

Laptops:
- Only the bevels on 62 thin keyboard/touchpad boxes were removed.
- Box bounds, 3D thickness and planar UV mapping are retained.
- Screen, body, hinge and camera meshes are unchanged.
- Whole FBX category: 156492 -> 31500 triangles (79.9% reduction).
- Measured sampled surface error <= 0.341 mm.

Files:
EscapeFromKD_Floor03_v03.blend
Export/SM_F03V03_Chairs.fbx
Export/SM_F03V03_Laptops.fbx
optimization_report.json
validation_report.json
Previews/Chair_Main_Comparison.png
Previews/Laptop_Comparison.png

The FBX files were imported back into Blender. Triangle counts and UV layers
matched; maximum coordinate/bounds difference was below 0.002 mm.
Near-camera CPU comparison renders were visually reviewed. The main chair
silhouette, back, seat, base, ribbed support and casters remain present.
The laptop display/body/keyboard silhouette remains intact.
The CAD chair has measured geometry validation; it was not separately rendered.

UE integration:
Import the two FBX meshes as separate new assets, reusing existing materials.
Do not import new textures or materials.
Preserve the current Nanite and collision settings.
Chairs material slot order:
  KD_F03_BlackPlastic, KD_F03_DarkRubber, KD_F03_SilverMetal
Laptops material slot order:
  KD_F03_BlackPlastic, KD_F03_DarkRubber,
  KD_F03_LaptopKeyboard, KD_F03_LaptopScreen
Blender roundtrip reports .001/.002 material suffixes because originals were
already loaded in the validation scene; the exported FBX slot names are unchanged.
UE import, frame-time comparison and final adoption are performed separately.

Rebuild:
Blender 5.3 background mode: --python build_optimized_furniture.py
Validate and render with CPU: --python validate_optimized_furniture.py
The build reads SurveyV02 and writes only OptimizedV03.
The validator does not save or alter the blend file.

Performance scope:
This is a geometry reduction candidate, not a promise of a corresponding FPS
increase. GPU profiling found Nanite visibility/base-pass costs much smaller
than the total frame time. Lighting/rendering improvements remain the primary
performance work.

Handoff checkpoint (2026-11-13):
No UE import or mesh replacement was performed. Work stopped at the user's request.
Later CPU analysis found a large GameThread Animation cost. The first next-session
step is a PIE-only enemy per-poly collision A/B, before further GPU changes.
See Documentation/Handoff_20261113/EscapeFromKD_Handoff_20261113.txt.
The validator resolves both FBX files from this folder's Export directory, so
historical absolute paths recorded in the JSON do not control the FBX import.

