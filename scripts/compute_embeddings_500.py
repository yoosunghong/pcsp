"""
Phase 7: Qwen3-Embedding-0.6B 임베딩 계산 (500 personas)

실행:
  conda run -n paper python scripts/compute_embeddings_500.py

출력: results/embeddings/persona_embeddings_500.npy  (500, 1024) float16
"""
import sys, json, pathlib
from pathlib import Path

sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

ROOT     = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "personas" / "personas_500.json"
EMB_DIR  = ROOT / "results" / "embeddings"
OUT_PATH = EMB_DIR / "persona_embeddings_500.npy"
EMB_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ID   = "Qwen/Qwen3-Embedding-0.6B"
BATCH_SIZE = 32
MAX_LENGTH = 128


def load_model():
    print(f"Loading {MODEL_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model     = AutoModel.from_pretrained(MODEL_ID, torch_dtype=torch.float16,
                                          trust_remote_code=True).cuda()
    model.eval()
    return tokenizer, model


def encode_batch(texts: list[str], tokenizer, model) -> np.ndarray:
    enc = tokenizer(texts, return_tensors="pt", truncation=True,
                    max_length=MAX_LENGTH, padding=True).to("cuda")
    with torch.no_grad():
        out = model(**enc)
    # last-token pooling + L2 normalize
    embs = out.last_hidden_state[:, -1, :]
    embs = torch.nn.functional.normalize(embs, dim=-1)
    return embs.cpu().float().numpy()


def main():
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run generate_personas_500.py first.")
        sys.exit(1)

    personas = json.loads(DATA_PATH.read_text())
    personas.sort(key=lambda p: p["id"])
    texts    = [p["text"] for p in personas]
    print(f"Encoding {len(texts)} personas ...")

    tokenizer, model = load_model()
    all_embs = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch   = texts[start:start + BATCH_SIZE]
        embs    = encode_batch(batch, tokenizer, model)
        all_embs.append(embs)
        print(f"  {min(start + BATCH_SIZE, len(texts)):3d}/{len(texts)}")

    embeddings = np.concatenate(all_embs, axis=0).astype(np.float16)
    np.save(OUT_PATH, embeddings)
    print(f"\nSaved {embeddings.shape} float16 embeddings → {OUT_PATH}")
    print(f"VRAM used: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
