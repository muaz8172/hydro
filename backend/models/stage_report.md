# Lettuce growth-stage model: training report

Dataset: `dataset/lettuce_224/`, 41 photos (seedling 18, vegetative 6, matured 17). Stage number for MAE/MSE/MAPE: Small = 1, Medium = 2, Large = 3.

Method: 5-fold stratified cross-validation, MobileNetV3-Small (ImageNet pretrained), 30 epochs, augmentation, class-weighted loss. Test scores use each photo once, predicted by a model that never saw it.

## Results

| Model | Train acc | Test acc | Test MAE | Test MSE | Test RMSE | Test MAPE |
|---|---|---|---|---|---|---|
| Always Small (baseline) | 44% | 44% | 0.98 | 1.80 | 1.34 | 35% |
| Always Medium (baseline) | 15% | 15% | 0.85 | 0.85 | 0.92 | 58% |
| A: Classifier **(chosen)** | 100% | 90% | 0.10 | 0.10 | 0.31 | 6% |
| B: Regression | 98% | 63% | 0.37 | 0.37 | 0.60 | 24% |

Train acc is the mean over folds on each fold's own training photos. MAPE divides by the true stage number, so a miss on a seedling (1) counts 100% but the same miss on a matured plant (3) counts 33%; read MAE instead.

Test accuracy per fold: A: Classifier 89%, 88%, 100%, 88%, 88%; B: Regression 100%, 38%, 50%, 62%, 62%

## A: Classifier: per stage (test)

| Actual \ Predicted | Small | Medium | Large | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Seedling (Small) | 17 | 1 | 0 | 85% | 94% | 0.89 |
| Vegetative (Medium) | 3 | 3 | 0 | 75% | 50% | 0.60 |
| Matured (Large) | 0 | 0 | 17 | 100% | 100% | 1.00 |

## B: Regression: per stage (test)

| Actual \ Predicted | Small | Medium | Large | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Seedling (Small) | 12 | 6 | 0 | 92% | 67% | 0.77 |
| Vegetative (Medium) | 1 | 2 | 3 | 15% | 33% | 0.21 |
| Matured (Large) | 0 | 5 | 12 | 80% | 71% | 0.75 |

## Pass criteria (chosen model)

| Check | Result | Value |
|---|---|---|
| Test accuracy >= 80% | PASS | 90% |
| Test MAE < 0.3 | PASS | 0.10 |
| Vegetative recall > 50% | FAIL | 50% |
| Beats both baselines on MAE | PASS |  |

Train vs test accuracy gap: 10% (acceptable).

## Exported model

`backend/models/stage.onnx` (A: Classifier, trained on all 41 photos), 6.1 MB, 19 ms per photo on this Raspberry Pi 5 (ONNX Runtime, CPU).

Loss curves: `backend/models/stage_training.png`. Per-photo predictions: `backend/models/stage_predictions.csv`.
