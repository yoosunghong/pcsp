"""
Persona 임베딩 t-SNE 시각화
- Qwen3-0.6B-Embed로 30개 persona 텍스트 임베딩
- t-SNE 2D 투영 + Big Five 주축(E/I)별 색상 표시
- results/figures/persona_tsne.png 저장
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

# Korean font setup
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

from src.data.persona_generator import save_dataset

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT_DIR = pathlib.Path("/home/swim/Documents/Projects/co-spec/results/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def last_token_pool(last_hidden_state, attention_mask):
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_state[:, -1]
    seq_len = attention_mask.sum(dim=1) - 1
    return last_hidden_state[torch.arange(last_hidden_state.shape[0], device=last_hidden_state.device), seq_len]


def embed(texts: list[str], tokenizer, model) -> np.ndarray:
    enc = tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        out = model(**enc)
    emb = last_token_pool(out.last_hidden_state, enc["attention_mask"])
    emb = torch.nn.functional.normalize(emb, p=2, dim=1)
    return emb.cpu().numpy()


def main():
    # 데이터셋 생성 및 로드
    records = save_dataset()
    texts = [r["text"] for r in records]
    big_five_e = [r["big_five"]["E"] for r in records]  # high/mid/low
    occupations = [r["occupation"] for r in records]
    splits = [r["split"] for r in records]
    ids = [r["id"] for r in records]

    # 임베딩
    print(f"Embedding {len(texts)} personas with {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL_ID, dtype=torch.float16, trust_remote_code=True).to(DEVICE)
    model.eval()

    embeddings = embed(texts, tokenizer, model)
    print(f"Embedding shape: {embeddings.shape}")

    # cosine similarity matrix
    sim_matrix = embeddings @ embeddings.T
    np.save(str(OUT_DIR / "persona_sim_matrix.npy"), sim_matrix)

    # t-SNE
    print("Running t-SNE...")
    tsne = TSNE(n_components=2, perplexity=8, random_state=42, n_iter=2000)
    coords = tsne.fit_transform(embeddings)

    # 시각화
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # ── Plot 1: Extroversion axis ──────────────────────────────────────────
    ax = axes[0]
    color_map = {"high": "#e74c3c", "mid": "#f39c12", "low": "#3498db"}
    colors = [color_map[e] for e in big_five_e]

    for i, (x, y) in enumerate(coords):
        c = color_map[big_five_e[i]]
        marker = "^" if splits[i] == "test" else "o"
        ax.scatter(x, y, c=c, marker=marker, s=120, edgecolors="black", linewidths=0.5, zorder=3)
        ax.annotate(f"#{ids[i]}", (x, y), textcoords="offset points",
                    xytext=(5, 3), fontsize=7, alpha=0.8)

    patches = [mpatches.Patch(color=v, label=f"Extroversion: {k}") for k, v in color_map.items()]
    patches.append(mpatches.Patch(color="white", label="○ train  △ test", ec="black"))
    ax.legend(handles=patches, fontsize=9, loc="upper left")
    ax.set_title("Persona t-SNE: Extroversion Axis", fontsize=13, fontweight="bold")
    ax.set_xlabel("t-SNE dim 1"); ax.set_ylabel("t-SNE dim 2")
    ax.grid(True, alpha=0.3)

    # ── Plot 2: Occupation cluster ────────────────────────────────────────
    ax = axes[1]
    occ_groups = {
        "지식/연구직": ["SW연구원", "대학원생", "데이터과학자", "대학교수", "번역가", "편집자"],
        "창작/예술직": ["배우", "작가", "그래픽디자이너", "유튜버", "여행블로거"],
        "비즈니스직":  ["마케터", "영업사원", "기업임원", "공무원", "은행원", "HR매니저", "중간관리자", "건설감독", "회계사"],
        "케어/교육직": ["간호사", "초등교사", "사회복지사"],
        "신체/기술직": ["개인트레이너", "운동선수", "요리사", "시니어엔지니어", "프리랜서개발자"],
        "기타":        ["창업자", "은퇴자"],
    }
    occ_color = {
        "지식/연구직": "#8e44ad", "창작/예술직": "#e74c3c",
        "비즈니스직":  "#27ae60", "케어/교육직": "#2980b9",
        "신체/기술직": "#e67e22", "기타":        "#7f8c8d",
    }
    occ_to_group = {occ: grp for grp, occs in occ_groups.items() for occ in occs}

    for i, (x, y) in enumerate(coords):
        grp = occ_to_group.get(occupations[i], "기타")
        c = occ_color[grp]
        marker = "^" if splits[i] == "test" else "o"
        ax.scatter(x, y, c=c, marker=marker, s=120, edgecolors="black", linewidths=0.5, zorder=3)
        ax.annotate(occupations[i], (x, y), textcoords="offset points",
                    xytext=(5, 3), fontsize=6.5, alpha=0.85)

    patches2 = [mpatches.Patch(color=v, label=k) for k, v in occ_color.items()]
    ax.legend(handles=patches2, fontsize=9, loc="upper left")
    ax.set_title("Persona t-SNE: Occupation Groups", fontsize=13, fontweight="bold")
    ax.set_xlabel("t-SNE dim 1"); ax.set_ylabel("t-SNE dim 2")
    ax.grid(True, alpha=0.3)

    plt.suptitle("Qwen3-Embedding-0.6B: 30 Persona Embeddings", fontsize=14, y=1.02)
    plt.tight_layout()
    out_path = OUT_DIR / "persona_tsne.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")

    # 임베딩 유사도 인사이트
    print("\n── Cosine Similarity Insights ──")
    labels = [f"#{r['id']} {r['occupation']}" for r in records]
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if records[i]["big_five"]["E"] == records[j]["big_five"]["E"] == "high":
                print(f"  Extrovert pair [{labels[i]}, {labels[j]}]: sim={sim_matrix[i,j]:.4f}")
                break

    # Save embeddings
    emb_dir = OUT_DIR.parent / "embeddings"
    emb_dir.mkdir(parents=True, exist_ok=True)
    np.save(str(emb_dir / "persona_embeddings_30.npy"), embeddings)
    print(f"Embeddings saved to results/embeddings/persona_embeddings_30.npy")


if __name__ == "__main__":
    main()
