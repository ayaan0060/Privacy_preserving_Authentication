# phase3_fusion/tests/test_integration.py
"""
End-to-End Pipeline Test:
Phase 1 Encoder -> Phase 2 Key Derivation -> Phase 3 FiLM -> Template
"""
import pytest
import torch
import numpy as np
import sys, os, hashlib, hmac, struct, math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase1_encoder')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase2_keymgmt')))

from models.film import FiLMGenerator, FiLMFusion
from model.encoder import FingerprintEncoder

def derive_key_vector(seed, domain_tag, user_id, key_version, dim=256):
    info = f"{domain_tag}|{user_id}|{key_version}|FiLM_KeyVector".encode()
    prk = hmac.new(b'\x00'*32, seed, hashlib.sha256).digest()
    okm = bytearray()
    t = b''
    for i in range(1, math.ceil(dim*4/32)+1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm.extend(t)
    okm = bytes(okm[:dim*4])
    vals = struct.unpack(f"<{dim}I", okm)
    return np.array([(v/4294967296.0)*2-1 for v in vals], dtype=np.float32)

def test_full_pipeline_deterministic():
    """
    Same Image + Same Seed + Same Version -> Same Template (Deterministic)
    Different Version -> Different Template (Unlinkable)
    """
    # 1. Setup Encoder
    encoder = FingerprintEncoder(embedding_dim=256, dropout=0.0)
    encoder.eval()
    
    # 2. Setup FiLM
    gen = FiLMGenerator(hidden_dims=[64])
    torch.nn.init.normal_(gen.beta_net[-1].weight, std=0.5)
    gen.eval()
    fusion = FiLMFusion(gen)
    fusion.eval()
    
    # 3. Inputs
    img = torch.randn(1, 1, 96, 96)
    seed = b'user_seed_32_bytes_long_12345678'
    domain_tag = "Test/App/v1"
    user_id = "user_001"
    version = 1
    
    # 4. Run Pipeline
    with torch.no_grad():
        x = encoder(img)
        k_np = derive_key_vector(seed, domain_tag, user_id, version)
        k = torch.from_numpy(k_np).unsqueeze(0)
        t1, _, _ = fusion(x, k)
    
    # 5. Repeat
    k_np2 = derive_key_vector(seed, domain_tag, user_id, version)
    k2 = torch.from_numpy(k_np2).unsqueeze(0)
    with torch.no_grad():
        t2, _, _ = fusion(x, k2)
    
    assert torch.allclose(t1, t2, atol=1e-5), "Pipeline Non-Deterministic!"
    
    # 6. Rotation
    k_np_v2 = derive_key_vector(seed, domain_tag, user_id, version+1)
    k_v2 = torch.from_numpy(k_np_v2).unsqueeze(0)
    with torch.no_grad():
        t_v2, _, _ = fusion(x, k_v2)
    
    sim = torch.nn.functional.cosine_similarity(t1, t_v2).item()
    assert abs(sim) < 0.25, f"Rotation Failed to Unlink: Sim={sim}"
