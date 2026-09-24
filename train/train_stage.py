"""Train the lettuce growth-stage model (stage also gives size).

    Seedling = Small = 1,  Vegetative = Medium = 2,  Matured = Large = 3

Runs 5-fold cross-validation for two models on dataset/lettuce_224/:
    A  classifier  - picks one of 3 stages (cross-entropy)
    B  regression  - outputs a number 1..3, rounded to a stage (MSE)
Both start from MobileNetV3-Small pretrained on ImageNet. Reports train vs test
accuracy, MAE, MSE, RMSE and MAPE (on the 1/2/3 stage number) against two
baselines, then trains the better model on all photos and exports it to ONNX.

Run:  .venv/bin/python train/train_stage.py
Out:  models/stage.onnx, stage_labels.json, stage_report.md,
      stage_training.png, stage_predictions.csv
"""
import csv
import json
import os
import random
import time

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold
from torchvision import models, transforms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "dataset", "lettuce_224")
OUT = os.path.join(ROOT, "models")

STAGES = ["seedling", "vegetative", "matured"]
SIZES = ["small", "medium", "large"]
FOLDS, EPOCHS, BATCH, SEED = 5, 30, 8, 42
LR_HEAD, LR_BODY = 1e-3, 1e-4

MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
train_tf = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.6, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(20),
    transforms.ColorJitter(0.2, 0.2, 0.1, 0.02),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])
test_tf = transforms.Compose([transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load():
    rows = list(csv.DictReader(open(os.path.join(DATA, "labels.csv"))))
    imgs = [Image.open(os.path.join(DATA, r["file"])).convert("RGB") for r in rows]
    y = np.array([STAGES.index(r["stage"]) for r in rows])
    return rows, imgs, y


def build(kind):
    net = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    net.classifier[3] = nn.Linear(net.classifier[3].in_features, 3 if kind == "A" else 1)
    return net


def class_weights(y):
    counts = np.bincount(y, minlength=3)
    return torch.tensor(len(y) / (3 * counts), dtype=torch.float32)


def loss_fn(kind, out, target, w):
    if kind == "A":
        return nn.functional.cross_entropy(out, target, weight=w)
    stage_num = target.float() + 1                        # 1, 2, 3
    per = (out.squeeze(1) - stage_num) ** 2
    return (per * w[target]).sum() / w[target].sum()


def predict(kind, net, imgs):
    """Return (stage index 0..2, raw stage number 1..3) for each image."""
    net.eval()
    with torch.no_grad():
        out = net(torch.stack([test_tf(i) for i in imgs]))
    if kind == "A":
        return out.argmax(1).numpy(), None
    raw = out.squeeze(1).numpy()
    return np.clip(np.rint(raw), 1, 3).astype(int) - 1, raw


def eval_loss(kind, net, imgs, y, w):
    net.eval()
    with torch.no_grad():
        out = net(torch.stack([test_tf(i) for i in imgs]))
        return loss_fn(kind, out, torch.tensor(y), w).item()


def train(kind, imgs, y, test_imgs=None, test_y=None):
    """Train one model. Returns the net and per-epoch (train loss, test loss)."""
    net = build(kind)
    head = list(net.classifier.parameters())
    head_ids = {id(p) for p in head}
    body = [p for p in net.parameters() if id(p) not in head_ids]
    opt = torch.optim.AdamW([{"params": body, "lr": LR_BODY},
                             {"params": head, "lr": LR_HEAD}], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
    w = class_weights(y)
    hist = []
    for _ in range(EPOCHS):
        net.train()
        order = np.random.permutation(len(imgs))
        losses = []
        for s in range(0, len(order) - BATCH + 1, BATCH):  # drop last partial batch (BatchNorm)
            idx = order[s:s + BATCH]
            x = torch.stack([train_tf(imgs[i]) for i in idx])
            loss = loss_fn(kind, net(x), torch.tensor(y[idx]), w)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(loss.item())
        sched.step()
        test_loss = eval_loss(kind, net, test_imgs, test_y, w) if test_imgs else None
        hist.append((float(np.mean(losses)), test_loss))
    return net, hist


def metrics(y, pred):
    """Accuracy plus MAE/MSE/RMSE/MAPE on the stage number 1/2/3."""
    t, p = y + 1, pred + 1
    err = p - t
    return {
        "acc": float(np.mean(err == 0)),
        "mae": float(np.mean(np.abs(err))),
        "mse": float(np.mean(err ** 2)),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape": float(np.mean(np.abs(err) / t) * 100),
    }


def cross_validate(kind, imgs, y):
    skf = StratifiedKFold(FOLDS, shuffle=True, random_state=SEED)
    oof = np.zeros(len(y), dtype=int)
    oof_raw = np.zeros(len(y))
    folds, hists = [], []
    for f, (tr, te) in enumerate(skf.split(np.zeros(len(y)), y)):
        seed_all(SEED + f)
        t0 = time.time()
        tr_imgs, te_imgs = [imgs[i] for i in tr], [imgs[i] for i in te]
        net, hist = train(kind, tr_imgs, y[tr], te_imgs, y[te])
        p_tr, _ = predict(kind, net, tr_imgs)
        p_te, raw = predict(kind, net, te_imgs)
        oof[te] = p_te
        if raw is not None:
            oof_raw[te] = raw
        m_tr, m_te = metrics(y[tr], p_tr), metrics(y[te], p_te)
        folds.append((m_tr, m_te))
        hists.append(hist)
        print(f"  {kind} fold {f + 1}: train acc {m_tr['acc']:.0%}  test acc {m_te['acc']:.0%}"
              f"  test MAE {m_te['mae']:.2f}  ({time.time() - t0:.0f}s)", flush=True)
    return oof, (oof_raw if kind == "B" else None), folds, hists


def plot(hists_by_kind, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    names = {"A": "A: classifier (cross-entropy)", "B": "B: regression (MSE)"}
    for ax, (kind, hists) in zip(axes, hists_by_kind.items()):
        h = np.array(hists, dtype=float)                   # folds x epochs x 2
        ep = np.arange(1, h.shape[1] + 1)
        for j, (label, col) in enumerate([("train", "#2a7ab9"), ("test", "#d9822b")]):
            mean, sd = h[:, :, j].mean(0), h[:, :, j].std(0)
            ax.plot(ep, mean, color=col, label=f"{label} loss (mean of {FOLDS} folds)")
            ax.fill_between(ep, mean - sd, mean + sd, color=col, alpha=0.15)
        ax.set_title(names[kind])
        ax.set_xlabel("epoch")
        ax.set_ylabel("loss")
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)


def export(kind, net):
    net.eval()
    path = os.path.join(OUT, "stage.onnx")
    torch.onnx.export(net, torch.zeros(1, 3, 224, 224), path, input_names=["image"],
                      output_names=["out"], dynamic_axes={"image": {0: "n"}, "out": {0: "n"}},
                      opset_version=17, dynamo=False)
    json.dump({"kind": "classifier" if kind == "A" else "regression", "stages": STAGES,
               "sizes": SIZES, "input": [1, 3, 224, 224], "mean": MEAN, "std": STD},
              open(os.path.join(OUT, "stage_labels.json"), "w"), indent=2)
    return path


def time_onnx(path, img):
    import onnxruntime as ort
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    x = test_tf(img).unsqueeze(0).numpy()
    for _ in range(5):
        sess.run(None, {"image": x})
    t0 = time.time()
    for _ in range(50):
        sess.run(None, {"image": x})
    return (time.time() - t0) / 50 * 1000


def main():
    os.makedirs(OUT, exist_ok=True)
    torch.set_num_threads(4)
    rows, imgs, y = load()
    print(f"{len(y)} photos: " + ", ".join(f"{s} {n}" for s, n in zip(STAGES, np.bincount(y))))

    results, hists, oofs, raws = {}, {}, {}, {}
    for kind in ["A", "B"]:
        print(f"Model {kind}: {FOLDS}-fold cross-validation, {EPOCHS} epochs")
        oofs[kind], raws[kind], folds, hists[kind] = cross_validate(kind, imgs, y)
        results[kind] = {
            "train": {k: np.mean([f[0][k] for f in folds]) for k in folds[0][0]},
            "test": metrics(y, oofs[kind]),
            "fold_test_acc": [f[1]["acc"] for f in folds],
        }

    # Pick the model with lower test MAE; accuracy breaks ties
    best = min("AB", key=lambda k: (results[k]["test"]["mae"], -results[k]["test"]["acc"]))

    print(f"Training final model {best} on all {len(y)} photos")
    seed_all(SEED)
    net, _ = train(best, imgs, y)
    onnx_path = export(best, net)
    ms = time_onnx(onnx_path, imgs[0])
    mb = os.path.getsize(onnx_path) / 1e6

    plot(hists, os.path.join(OUT, "stage_training.png"))
    with open(os.path.join(OUT, "stage_predictions.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "true_stage", "A_pred", "B_pred", "B_raw"])
        for i, r in enumerate(rows):
            w.writerow([r["file"], STAGES[y[i]], STAGES[oofs["A"][i]], STAGES[oofs["B"][i]],
                        f"{raws['B'][i]:.2f}"])

    write_report(y, results, oofs, best, ms, mb)
    print(open(os.path.join(OUT, "stage_report.md")).read())


def write_report(y, results, oofs, best, ms, mb):
    n = len(y)
    base = {"Always Small": np.zeros(n, dtype=int), "Always Medium": np.ones(n, dtype=int)}
    names = {"A": "A: Classifier", "B": "B: Regression"}
    L = []
    L.append("# Lettuce growth-stage model: training report\n")
    L.append(f"Dataset: `dataset/lettuce_224/`, {n} photos "
             f"({', '.join(f'{s} {c}' for s, c in zip(STAGES, np.bincount(y)))}). "
             f"Stage number for MAE/MSE/MAPE: Small = 1, Medium = 2, Large = 3.\n")
    L.append(f"Method: {FOLDS}-fold stratified cross-validation, MobileNetV3-Small (ImageNet "
             f"pretrained), {EPOCHS} epochs, augmentation, class-weighted loss. Test scores use "
             f"each photo once, predicted by a model that never saw it.\n")
    L.append("## Results\n")
    L.append("| Model | Train acc | Test acc | Test MAE | Test MSE | Test RMSE | Test MAPE |")
    L.append("|---|---|---|---|---|---|---|")
    for name, pred in base.items():
        m = metrics(y, pred)
        L.append(f"| {name} (baseline) | {m['acc']:.0%} | {m['acc']:.0%} | {m['mae']:.2f} | "
                 f"{m['mse']:.2f} | {m['rmse']:.2f} | {m['mape']:.0f}% |")
    for k in "AB":
        tr, te = results[k]["train"], results[k]["test"]
        mark = " **(chosen)**" if k == best else ""
        L.append(f"| {names[k]}{mark} | {tr['acc']:.0%} | {te['acc']:.0%} | {te['mae']:.2f} | "
                 f"{te['mse']:.2f} | {te['rmse']:.2f} | {te['mape']:.0f}% |")
    L.append("\nTrain acc is the mean over folds on each fold's own training photos. "
             "MAPE divides by the true stage number, so a miss on a seedling (1) counts 100% "
             "but the same miss on a matured plant (3) counts 33%; read MAE instead.\n")
    L.append("Test accuracy per fold: " + "; ".join(
        f"{names[k]} " + ", ".join(f"{a:.0%}" for a in results[k]["fold_test_acc"]) for k in "AB")
        + "\n")

    for k in "AB":
        cm = confusion_matrix(y, oofs[k], labels=[0, 1, 2])
        p, r, f1, _ = precision_recall_fscore_support(y, oofs[k], labels=[0, 1, 2], zero_division=0)
        L.append(f"## {names[k]}: per stage (test)\n")
        L.append("| Actual \\ Predicted | Small | Medium | Large | Precision | Recall | F1 |")
        L.append("|---|---|---|---|---|---|---|")
        for i, s in enumerate(STAGES):
            L.append(f"| {s.title()} ({SIZES[i].title()}) | {cm[i, 0]} | {cm[i, 1]} | {cm[i, 2]} | "
                     f"{p[i]:.0%} | {r[i]:.0%} | {f1[i]:.2f} |")
        L.append("")

    te = results[best]["test"]
    rec = precision_recall_fscore_support(y, oofs[best], labels=[0, 1, 2], zero_division=0)[1]
    beats = te["mae"] < min(metrics(y, b)["mae"] for b in base.values())
    checks = [("Test accuracy >= 80%", te["acc"] >= 0.8, f"{te['acc']:.0%}"),
              ("Test MAE < 0.3", te["mae"] < 0.3, f"{te['mae']:.2f}"),
              ("Vegetative recall > 50%", rec[1] > 0.5, f"{rec[1]:.0%}"),
              ("Beats both baselines on MAE", beats, "")]
    L.append("## Pass criteria (chosen model)\n")
    L.append("| Check | Result | Value |")
    L.append("|---|---|---|")
    for c, ok, v in checks:
        L.append(f"| {c} | {'PASS' if ok else 'FAIL'} | {v} |")
    gap = results[best]["train"]["acc"] - te["acc"]
    L.append(f"\nTrain vs test accuracy gap: {gap:.0%} "
             f"({'large: the model memorises its training photos' if gap > 0.2 else 'acceptable'}).\n")
    L.append("## Exported model\n")
    L.append(f"`models/stage.onnx` ({names[best]}, trained on all {n} photos), {mb:.1f} MB, "
             f"{ms:.0f} ms per photo on this Raspberry Pi 5 (ONNX Runtime, CPU).\n")
    L.append("Loss curves: `models/stage_training.png`. Per-photo predictions: "
             "`models/stage_predictions.csv`.\n")
    open(os.path.join(OUT, "stage_report.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
