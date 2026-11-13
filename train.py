"""Train the move predictor on data.npz produced by prepare_data.py.

Usage:  python train.py --data data.npz --epochs 5
"""
import argparse
import time

import numpy as np
import torch
import torch.nn.functional as F

from model import MovePredictor


def accuracy(model, X, y, device, bs=1024):
    model.eval()
    top1 = top3 = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            xb = torch.from_numpy(X[i:i + bs]).float().to(device)
            yb = torch.from_numpy(y[i:i + bs].astype(np.int64)).to(device)
            top = model(xb).topk(3, dim=1).indices
            top1 += (top[:, 0] == yb).sum().item()
            top3 += (top == yb[:, None]).any(dim=1).sum().item()
    return top1 / len(X), top3 / len(X)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.npz")
    ap.add_argument("--out", default="model.pt")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--channels", type=int, default=64)
    ap.add_argument("--blocks", type=int, default=4)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device)

    data = np.load(args.data)
    X, y = data["X"], data["y"]
    idx = np.random.default_rng(0).permutation(len(X))
    split = int(len(X) * 0.95)
    tr, va = idx[:split], idx[split:]
    Xtr, ytr, Xva, yva = X[tr], y[tr], X[va], y[va]

    model = MovePredictor(args.channels, args.blocks).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(
        opt, T_max=args.epochs * (len(Xtr) // args.batch_size + 1))

    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = np.random.permutation(len(Xtr))
        total = 0.0
        nb = (len(perm) + args.batch_size - 1) // args.batch_size
        t0 = time.time()
        for bi, i in enumerate(range(0, len(perm), args.batch_size), 1):
            b = perm[i:i + args.batch_size]
            xb = torch.from_numpy(Xtr[b]).float().to(device)
            yb = torch.from_numpy(ytr[b].astype(np.int64)).to(device)
            loss = F.cross_entropy(model(xb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item() * len(b)
            if bi % 50 == 0 or bi == nb:
                done = min(i + args.batch_size, len(perm))
                rate = done / max(time.time() - t0, 1e-9)
                eta = (len(perm) - done) / rate / 60
                print(f"epoch {epoch} [{done}/{len(perm)}] loss {total / done:.3f} "
                      f"({rate:.0f} pos/s, ETA {eta:.0f} min)", flush=True)
        t1, t3 = accuracy(model, Xva, yva, device)
        print(f"epoch {epoch}: loss {total / len(Xtr):.3f} | val top-1 {t1:.1%} top-3 {t3:.1%}")
        torch.save({"state": model.state_dict(),
                    "channels": args.channels, "blocks": args.blocks}, args.out)

    print("saved", args.out)


if __name__ == "__main__":
    main()
