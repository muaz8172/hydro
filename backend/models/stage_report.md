# Lettuce growth-stage model: training report

Dataset: `dataset/lettuce_224/`, 88 photos (seedling 30, vegetative 29, matured 29). Stage number for MAE/MSE/MAPE: Small = 1, Medium = 2, Large = 3.

Method: 5-fold stratified cross-validation, MobileNetV3-Small (ImageNet pretrained), 30 epochs, augmentation, class-weighted loss. Test scores use each photo once, predicted by a model that never saw it.

## Results

| Model | Train acc | Test acc | Test MAE | Test MSE | Test RMSE | Test MAPE |
|---|---|---|---|---|---|---|
| Always Small (baseline) | 34% | 34% | 0.99 | 1.65 | 1.28 | 38% |
| Always Medium (baseline) | 33% | 33% | 0.67 | 0.67 | 0.82 | 45% |
| A: Classifier **(chosen)** | 100% | 86% | 0.16 | 0.20 | 0.45 | 7% |
| B: Regression | 98% | 76% | 0.24 | 0.24 | 0.49 | 12% |

Train acc is the mean over folds on each fold's own training photos. MAPE divides by the true stage number, so a miss on a seedling (1) counts 100% but the same miss on a matured plant (3) counts 33%; read MAE instead.

Test accuracy per fold: A: Classifier 100%, 72%, 83%, 76%, 100%; B: Regression 78%, 78%, 78%, 59%, 88%

## A: Classifier: per stage (test)

| Actual \ Predicted | Small | Medium | Large | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Seedling (Small) | 29 | 1 | 0 | 85% | 97% | 0.91 |
| Vegetative (Medium) | 3 | 23 | 3 | 85% | 79% | 0.82 |
| Matured (Large) | 2 | 3 | 24 | 89% | 83% | 0.86 |

## B: Regression: per stage (test)

| Actual \ Predicted | Small | Medium | Large | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Seedling (Small) | 25 | 5 | 0 | 89% | 83% | 0.86 |
| Vegetative (Medium) | 3 | 25 | 1 | 60% | 86% | 0.70 |
| Matured (Large) | 0 | 12 | 17 | 94% | 59% | 0.72 |

## Pass criteria (chosen model)

| Check | Result | Value |
|---|---|---|
| Test accuracy >= 80% | PASS | 86% |
| Test MAE < 0.3 | PASS | 0.16 |
| Vegetative recall >= 70% | PASS | 79% |
| Beats both baselines on MAE | PASS |  |

Train vs test accuracy gap: 13% (acceptable).

## Exported model

`backend/models/stage.onnx` (A: Classifier, trained on all 88 photos), 6.1 MB, 10 ms per photo on this Raspberry Pi 5 (ONNX Runtime, CPU).

Loss curves: `backend/models/stage_training.png`. Per-photo predictions: `backend/models/stage_predictions.csv`.
