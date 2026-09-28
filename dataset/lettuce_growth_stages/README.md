# Lettuce growth-stage dataset

Photos of lettuce sorted by growth stage. This is the first dataset for a camera AI model that
classifies the growth stage of the plants seen by the MaixCAM (see the main README, Part 5).

| Stage | Folder | Photos |
|---|---|---|
| Seedling | `seedling/` | 30 |
| Vegetative | `vegetative/` | 29 |
| Matured (ready to harvest) | `matured/` | 29 |
| **Total** | | **88** |

- The folder name is the label. `labels.csv` lists every photo with its stage, format, size and
  original file name.
- Formats: 84 JPEG, 4 AVIF, 2 WEBP. Sizes range from 194×259 to 2976×2232 px. Convert and
  resize (e.g. to 224×224 JPEG) before training; not every tool reads AVIF.
- `vegetative_012.jpg` and `matured_022.jpg` were removed: they were the same photo with two
  different labels.
- The classes are balanced (30 / 29 / 29). Add photos from the Hydro camera itself
  (`data/vision/`) so the model also learns the real rack view.
