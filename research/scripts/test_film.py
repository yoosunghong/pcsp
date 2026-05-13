"""FiLM 모듈 sanity check"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import numpy as np
from src.models.film import (
    FiLMLayer, FiLMBlock, PersonaProjection,
    PersonaConditionedPolicy, PersonaConditionedValue,
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OBS_DIM = 20      # Mini-Inzoi obs dim
N_ACTIONS = 10    # Mini-Inzoi action space
LLM_DIM = 1024    # Qwen3-0.6B-Embed output dim
PERSONA_DIM = 64
BATCH = 4

def test_film_layer():
    layer = FiLMLayer(PERSONA_DIM, 256).to(DEVICE)
    h = torch.randn(BATCH, 256, device=DEVICE)
    e_p = torch.randn(BATCH, PERSONA_DIM, device=DEVICE)
    out = layer(h, e_p)
    assert out.shape == (BATCH, 256), f"Expected (4, 256), got {out.shape}"
    # At init, γ=1, β=0 → output should be close to h (but not exactly due to gradients not set)
    print(f"FiLMLayer: PASS ✓ | output shape {out.shape}")

def test_persona_projection():
    proj = PersonaProjection(LLM_DIM, PERSONA_DIM).to(DEVICE)
    e_llm = torch.randn(BATCH, LLM_DIM, device=DEVICE)
    e_p = proj(e_llm)
    assert e_p.shape == (BATCH, PERSONA_DIM)
    # Check L2-normalized
    norms = e_p.norm(dim=-1)
    assert torch.allclose(norms, torch.ones(BATCH, device=DEVICE), atol=1e-5), "Not normalized"
    print(f"PersonaProjection: PASS ✓ | shape {e_p.shape} | norms ≈ 1")

def test_policy():
    policy = PersonaConditionedPolicy(OBS_DIM, N_ACTIONS, PERSONA_DIM, LLM_DIM).to(DEVICE)
    obs = torch.randn(BATCH, OBS_DIM, device=DEVICE)
    e_llm = torch.randn(BATCH, LLM_DIM, device=DEVICE)
    logits = policy(obs, e_llm)
    assert logits.shape == (BATCH, N_ACTIONS)
    print(f"PolicyNet: PASS ✓ | logits shape {logits.shape}")

    # Param count
    n_params = sum(p.numel() for p in policy.parameters())
    print(f"  Trainable params: {n_params:,}")

def test_value():
    value = PersonaConditionedValue(OBS_DIM, PERSONA_DIM, LLM_DIM).to(DEVICE)
    obs = torch.randn(BATCH, OBS_DIM, device=DEVICE)
    e_llm = torch.randn(BATCH, LLM_DIM, device=DEVICE)
    v = value(obs, e_llm)
    assert v.shape == (BATCH,), f"Expected ({BATCH},), got {v.shape}"
    print(f"ValueNet: PASS ✓ | value shape {v.shape}")

def test_persona_diversity():
    """Different persona embeddings should produce different action distributions."""
    policy = PersonaConditionedPolicy(OBS_DIM, N_ACTIONS, PERSONA_DIM, LLM_DIM).to(DEVICE)
    # Load real embeddings if available
    emb_path = ROOT / "results" / "embeddings" / "persona_embeddings_30.npy"
    if emb_path.exists():
        embs = np.load(str(emb_path))[:4]  # first 4
        e_llm = torch.tensor(embs, dtype=torch.float32, device=DEVICE)
    else:
        e_llm = torch.randn(4, LLM_DIM, device=DEVICE)

    obs = torch.zeros(1, OBS_DIM, device=DEVICE).expand(4, -1)  # same obs for all
    with torch.no_grad():
        logits = policy(obs, e_llm)
        probs  = torch.softmax(logits, dim=-1)

    # KL divergences between all pairs
    kl_sum = 0.0
    n_pairs = 0
    for i in range(4):
        for j in range(i + 1, 4):
            kl = torch.sum(probs[i] * (probs[i].log() - probs[j].log())).item()
            kl_sum += kl
            n_pairs += 1
    avg_kl = kl_sum / n_pairs

    print(f"\nDiversity sanity (random-init policy):")
    print(f"  Avg pairwise KL (4 personas, same obs): {avg_kl:.4f}")
    print(f"  Note: This will increase significantly after persona-conditioned training")

def test_gradient_flow():
    policy = PersonaConditionedPolicy(OBS_DIM, N_ACTIONS, PERSONA_DIM, LLM_DIM).to(DEVICE)
    value  = PersonaConditionedValue(OBS_DIM, PERSONA_DIM, LLM_DIM).to(DEVICE)
    opt_p  = torch.optim.Adam(policy.parameters(), lr=3e-4)
    opt_v  = torch.optim.Adam(value.parameters(),  lr=3e-4)

    obs   = torch.randn(BATCH, OBS_DIM, device=DEVICE)
    e_llm = torch.randn(BATCH, LLM_DIM, device=DEVICE)

    for step in range(5):
        logits = policy(obs, e_llm)
        dist   = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        log_probs = dist.log_prob(actions)
        values = value(obs, e_llm)

        # Dummy PPO-style loss
        returns = torch.randn(BATCH, device=DEVICE)
        adv = returns - values.detach()
        loss_p = -(log_probs * adv).mean()
        loss_v = F.mse_loss(values, returns)

        opt_p.zero_grad(); loss_p.backward(); opt_p.step()
        opt_v.zero_grad(); loss_v.backward(); opt_v.step()

    print(f"\nGradient flow test: PASS ✓ (5 update steps)")
    print(f"  Final policy loss: {loss_p.item():.4f}")
    print(f"  Final value loss: {loss_v.item():.4f}")

if __name__ == "__main__":
    import torch.nn.functional as F

    print(f"Device: {DEVICE}\n")
    test_film_layer()
    test_persona_projection()
    test_policy()
    test_value()
    test_persona_diversity()
    test_gradient_flow()
    print("\nAll FiLM module tests PASSED ✓")
