"""
Persona 300개 t-SNE 시각화
- personas_300.json 로드
- Qwen3-0.6B-Embed로 임베딩 (배치 32)
- t-SNE 2D 투영: Big Five 5축 × 직업군 총 6 패널
- results/figures/persona_tsne_300.png 저장
- results/embeddings/persona_embeddings_300.npy 저장
"""
import sys
sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")

import json
import pathlib
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm

_KO_FONT_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
]
_ko_font = None
for _p in _KO_FONT_PATHS:
    if pathlib.Path(_p).exists():
        fm.fontManager.addfont(_p)
        _ko_font = fm.FontProperties(fname=_p).get_name()
        break
if _ko_font:
    matplotlib.rcParams["font.family"] = _ko_font

from sklearn.manifold import TSNE
from transformers import AutoTokenizer, AutoModel

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DATA_PATH = pathlib.Path("/home/swim/Documents/Projects/co-spec/data/personas/personas_300.json")
OUT_DIR = pathlib.Path("/home/swim/Documents/Projects/co-spec/results/figures")
EMB_DIR = pathlib.Path("/home/swim/Documents/Projects/co-spec/results/embeddings")
OUT_DIR.mkdir(parents=True, exist_ok=True)
EMB_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 32

OCC_GROUPS = {
    "지식/연구직": ["SW연구원", "대학원생", "데이터과학자", "대학교수", "번역가"],
    "창작/예술직": ["작가", "그래픽디자이너"],
    "비즈니스직":  ["마케터", "영업사원", "기업임원", "공무원", "HR매니저", "건설감독", "회계사"],
    "케어/교육직": ["간호사", "초등교사"],
    "신체/기술직": ["개인트레이너", "운동선수", "요리사"],
    "기타":        ["창업자"],
}
OCC_COLOR = {
    "지식/연구직": "#8e44ad",
    "창작/예술직": "#e74c3c",
    "비즈니스직":  "#27ae60",
    "케어/교육직": "#2980b9",
    "신체/기술직": "#e67e22",
    "기타":        "#7f8c8d",
}
OCC_TO_GROUP = {occ: grp for grp, occs in OCC_GROUPS.items() for occ in occs}


def last_token_pool(last_hidden_state, attention_mask):
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_state[:, -1]
    seq_len = attention_mask.sum(dim=1) - 1
    return last_hidden_state[
        torch.arange(last_hidden_state.shape[0], device=last_hidden_state.device), seq_len
    ]


def embed_all(texts, tokenizer, model):
    all_embs = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        enc = tokenizer(
            batch, padding=True, truncation=True, max_length=128, return_tensors="pt"
        ).to(DEVICE)
        with torch.no_grad():
            out = model(**enc)
        emb = last_token_pool(out.last_hidden_state, enc["attention_mask"])
        emb = torch.nn.functional.normalize(emb, p=2, dim=1)
        all_embs.append(emb.cpu().numpy())
        if (i // BATCH_SIZE + 1) % 5 == 0:
            done = min(i + BATCH_SIZE, len(texts))
            print(f"  {done}/{len(texts)} 완료")
    return np.vstack(all_embs)


def _scatter(ax, coords, colors, markers, s=60):
    for (x, y), c, m in zip(coords, colors, markers):
        ax.scatter(x, y, c=c, marker=m, s=s, edgecolors="black", linewidths=0.3, zorder=3, alpha=0.85)


def main():
    print(f"Loading {DATA_PATH}...")
    records = json.loads(DATA_PATH.read_text())
    print(f"  총 {len(records)}개 (train={sum(r['split']=='train' for r in records)}, test={sum(r['split']=='test' for r in records)})")

    texts = [r["text"] for r in records]
    splits = [r["split"] for r in records]
    occupations = [r["occupation"] for r in records]
    bf = {dim: [r["big_five"][dim] for r in records] for dim in "ENAOC"}

    # ── 임베딩 ──────────────────────────────────────────────────────────────
    emb_cache = EMB_DIR / "persona_embeddings_300.npy"
    if emb_cache.exists():
        print(f"캐시에서 임베딩 로드: {emb_cache}")
        embeddings = np.load(str(emb_cache))
    else:
        print(f"Embedding {len(texts)} personas with {MODEL_ID}...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModel.from_pretrained(MODEL_ID, dtype=torch.float16, trust_remote_code=True).to(DEVICE)
        model.eval()
        embeddings = embed_all(texts, tokenizer, model)
        np.save(str(emb_cache), embeddings)
        print(f"Embeddings saved → {emb_cache}")

    # cosine similarity matrix
    sim_matrix = embeddings @ embeddings.T
    np.save(str(OUT_DIR / "persona_sim_matrix_300.npy"), sim_matrix)

    # ── t-SNE ────────────────────────────────────────────────────────────────
    print("Running t-SNE (perplexity=30, n_iter=2000)...")
    tsne = TSNE(n_components=2, perplexity=30, random_state=42, n_iter=2000, n_jobs=-1)
    coords = tsne.fit_transform(embeddings)

    # 마커: train=o, test=^
    markers = ["^" if s == "test" else "o" for s in splits]

    # ── 시각화 (2행 3열) ─────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 3, figsize=(21, 14))

    COLOR_MAP = {"high": "#e74c3c", "mid": "#f39c12", "low": "#3498db"}
    DIM_NAMES = {"E": "Extraversion", "N": "Neuroticism", "A": "Agreeableness",
                 "C": "Conscientiousness", "O": "Openness"}

    for idx, dim in enumerate("ENAOC"):
        ax = axes[idx // 3][idx % 3]
        colors = [COLOR_MAP[v] for v in bf[dim]]
        _scatter(ax, coords, colors, markers)
        patches = [mpatches.Patch(color=v, label=k) for k, v in COLOR_MAP.items()]
        patches.append(mpatches.Patch(color="white", label="○ train  △ test", ec="black"))
        ax.legend(handles=patches, fontsize=8, loc="upper left")
        ax.set_title(f"Big Five — {DIM_NAMES[dim]} ({dim})", fontsize=11, fontweight="bold")
        ax.set_xlabel("t-SNE dim 1", fontsize=8)
        ax.set_ylabel("t-SNE dim 2", fontsize=8)
        ax.grid(True, alpha=0.25)

    # 직업군 패널 (2행 3열 마지막)
    ax = axes[1][2]
    occ_colors = [OCC_COLOR[OCC_TO_GROUP.get(o, "기타")] for o in occupations]
    _scatter(ax, coords, occ_colors, markers)

    # 직업 레이블: 각 직업별 중심점에만 표시
    from collections import defaultdict
    occ_coords = defaultdict(list)
    for (x, y), occ in zip(coords, occupations):
        occ_coords[occ].append((x, y))
    for occ, pts in occ_coords.items():
        cx, cy = np.mean(pts, axis=0)
        ax.annotate(occ, (cx, cy), fontsize=6.5, ha="center", va="bottom",
                    fontweight="bold", alpha=0.9)

    patches2 = [mpatches.Patch(color=v, label=k) for k, v in OCC_COLOR.items()]
    ax.legend(handles=patches2, fontsize=8, loc="upper left")
    ax.set_title("Occupation Groups", fontsize=11, fontweight="bold")
    ax.set_xlabel("t-SNE dim 1", fontsize=8)
    ax.set_ylabel("t-SNE dim 2", fontsize=8)
    ax.grid(True, alpha=0.25)

    plt.suptitle(
        f"Qwen3-Embedding-0.6B: 300 Persona Embeddings (t-SNE, perplexity=30)",
        fontsize=13, y=1.01
    )
    plt.tight_layout()
    out_path = OUT_DIR / "persona_tsne_300.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved → {out_path}")

    # ── 유사도 인사이트 ───────────────────────────────────────────────────────
    print("\n── Cosine Similarity Insights ──")
    for dim in "ENAOC":
        idx_high = [i for i, v in enumerate(bf[dim]) if v == "high"]
        idx_low  = [i for i, v in enumerate(bf[dim]) if v == "low"]
        if idx_high and idx_low:
            intra = np.mean([sim_matrix[i, j] for i in idx_high for j in idx_high if i < j])
            cross = np.mean([sim_matrix[i, j] for i in idx_high for j in idx_low])
            print(f"  {DIM_NAMES[dim]:20s}  intra-high={intra:.4f}  high-vs-low={cross:.4f}  Δ={intra-cross:.4f}")


if __name__ == "__main__":
    main()
