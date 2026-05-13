"""
Smoke test: Qwen3-0.6B-Embedding
목표: 배치 100 persona 텍스트 임베딩 < 500ms on RTX 6000 Ada
"""
import time
import pathlib
import torch
from transformers import AutoTokenizer, AutoModel

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def last_token_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    # Qwen3-Embedding uses last-token pooling
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_state[:, -1]
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_state.shape[0]
    return last_hidden_state[torch.arange(batch_size, device=last_hidden_state.device), sequence_lengths]


def load_model():
    print(f"Loading {MODEL_ID} on {DEVICE}...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL_ID, torch_dtype=torch.float16, trust_remote_code=True).to(DEVICE)
    model.eval()
    print(f"Model loaded in {time.time() - t0:.2f}s")
    return tokenizer, model


def embed_batch(texts: list[str], tokenizer, model, max_length: int = 128) -> torch.Tensor:
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    ).to(DEVICE)
    with torch.no_grad():
        outputs = model(**encoded)
    embeddings = last_token_pool(outputs.last_hidden_state, encoded["attention_mask"])
    return torch.nn.functional.normalize(embeddings, p=2, dim=1)


PERSONA_SAMPLES = [
    "외향적이고 새로운 경험을 즐기는 25세 마케터, 운동을 좋아하고 사람들과 어울리기 좋아함",
    "내성적이고 신중한 35세 연구원, 독서와 혼자만의 시간 선호, 조용한 환경에서 집중력 높음",
    "성실하고 가족 중심적인 42세 부모, 정해진 루틴을 중시하며 안정을 추구함",
    "창의적이고 즉흥적인 28세 예술가, 자유로운 일정과 실험적인 시도를 즐김",
    "경쟁적이고 목표 지향적인 32세 영업사원, 성과를 중시하고 끊임없이 도전함",
    "친절하고 공감능력이 뛰어난 29세 간호사, 타인 돌봄을 우선시하고 감정적 지원 제공",
    "논리적이고 분석적인 38세 데이터 과학자, 데이터 기반 의사결정을 선호하고 세부사항에 집중",
    "모험적이고 위험을 즐기는 24세 여행 블로거, 새로운 문화와 경험 탐색을 좋아함",
    "조직적이고 체계적인 45세 프로젝트 매니저, 계획과 일정 관리를 중시하고 팀워크 강조",
    "호기심 많고 학습을 즐기는 31세 교사, 지식 공유와 타인의 성장을 보람으로 여김",
]

# 배치 100개: 10개 × 10회 반복
BATCH_100 = PERSONA_SAMPLES * 10


def main():
    tokenizer, model = load_model()

    gpu_mem_before = torch.cuda.memory_allocated(DEVICE) / 1024**2 if DEVICE == "cuda" else 0
    print(f"GPU memory (model loaded): {gpu_mem_before:.0f} MB")

    # Warm-up
    _ = embed_batch(PERSONA_SAMPLES[:2], tokenizer, model)
    if DEVICE == "cuda":
        torch.cuda.synchronize()

    # 배치 100 타이밍 (5회 평균)
    times = []
    for _ in range(5):
        if DEVICE == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        embs = embed_batch(BATCH_100, tokenizer, model)
        if DEVICE == "cuda":
            torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)

    avg_ms = sum(times) / len(times)
    print(f"\n=== Smoke Test Results ===")
    print(f"Batch size: {len(BATCH_100)}")
    print(f"Embedding dim: {embs.shape[1]}")
    print(f"Avg latency (5 runs): {avg_ms:.1f} ms")
    print(f"Min / Max: {min(times):.1f} / {max(times):.1f} ms")
    print(f"Target: < 500 ms → {'PASS ✓' if avg_ms < 500 else 'FAIL ✗'}")

    # 배치 1 (단일 NPC 추론 비용)
    t0 = time.perf_counter()
    _ = embed_batch(PERSONA_SAMPLES[:1], tokenizer, model)
    if DEVICE == "cuda":
        torch.cuda.synchronize()
    single_ms = (time.perf_counter() - t0) * 1000
    print(f"\nSingle persona embed: {single_ms:.1f} ms (1회성, 게임 NPC spawn 시)")

    # cosine similarity 검증
    embs_10 = embed_batch(PERSONA_SAMPLES, tokenizer, model)
    sim_matrix = (embs_10 @ embs_10.T).cpu()
    print(f"\nCosine sim (외향 마케터 vs 내성 연구원): {sim_matrix[0, 1]:.4f}")
    print(f"Cosine sim (외향 마케터 vs 경쟁 영업사원): {sim_matrix[0, 4]:.4f}")
    print(f"Expected: 마케터-영업사원 sim > 마케터-연구원 sim")

    # 결과 저장
    import json
    out = {
        "model": MODEL_ID,
        "device": DEVICE,
        "batch_100_avg_ms": round(avg_ms, 2),
        "batch_100_min_ms": round(min(times), 2),
        "batch_100_max_ms": round(max(times), 2),
        "single_ms": round(single_ms, 2),
        "embedding_dim": int(embs.shape[1]),
        "pass": avg_ms < 500,
    }
    out_path = ROOT / "results" / "smoke_test_result.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
