# Lettuce dataset, 224×224 JPEG (ready for training)

All 41 photos from [`../lettuce_growth_stages/`](../lettuce_growth_stages/) converted to
**224×224 JPEG** (quality 95): rotated upright, centre-cropped to a square, then resized.
The originals are left untouched.

Each growth stage also gives the plant size:

| Stage | Size | Folder | Photos |
|---|---|---|---|
| Seedling | Small | `seedling/` | 18 |
| Vegetative | Medium | `vegetative/` | 6 |
| Matured | Large | `matured/` | 17 |

`labels.csv` has columns `file, stage, size, source` (`source` is the original file).
Because size follows stage, one model trained on these folders predicts both.
