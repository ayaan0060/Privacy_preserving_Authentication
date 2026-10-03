# phase4_he/he/params.py
"""
CKKS Parameter Selection & Justification.

DESIGN REQUIREMENTS:
1. Embedding dimension: 256 (real values in [-1, 1])
2. Operation: Dot product (256 multiplications + 255 additions)
3. Multiplicative depth: 1 (single ciphertext-ciphertext multiply)
   + log2(256) = 8 rotations for sum reduction
4. Precision: ~1e-3 relative error (CKKS native)
5. Security: ≥128-bit classical
"""
from dataclasses import dataclass
from typing import List, Tuple
import tenseal as ts

@dataclass(frozen=True)
class CKKSParams:
    poly_modulus_degree: int
    coeff_mod_bit_sizes: List[int]
    scale_bits: int
    security_level: int
    std_dev: float = 3.2
    
    @property
    def total_coeff_bits(self) -> int:
        return sum(self.coeff_mod_bit_sizes)
    
    @property
    def num_levels(self) -> int:
        return len(self.coeff_mod_bit_sizes) - 1  # Levels = len(chain) - 1
    
    @property
    def max_slots(self) -> int:
        return self.poly_modulus_degree // 2
    
    @property
    def scale(self) -> float:
        return 2.0 ** self.scale_bits


# DEFAULT PARAMETERS (validated for 128-bit security)
DEFAULT_PARAMS = CKKSParams(
    poly_modulus_degree=8192,
    coeff_mod_bit_sizes=[60, 40, 40, 60],
    scale_bits=40,
    security_level=128,
)

# HIGH SECURITY PARAMETERS (192-bit, for future-proofing)
HIGH_SECURITY_PARAMS = CKKSParams(
    poly_modulus_degree=16384,
    coeff_mod_bit_sizes=[60, 40, 40, 40, 60],
    scale_bits=40,
    security_level=192,
)

# MINIMAL PARAMETERS (for testing only — NOT SECURE)
TEST_PARAMS = CKKSParams(
    poly_modulus_degree=4096,
    coeff_mod_bit_sizes=[30, 20, 20, 30],
    scale_bits=20,
    security_level=80,  # INSECURE
)


def create_tenseal_context(params: CKKSParams, 
                           generate_galois_keys: bool = True,
                           generate_relin_keys: bool = True) -> ts.Context:
    """
    Create TenSEAL CKKS context with specified parameters.
    
    Returns context WITH secret key (for client).
    Use `context.make_context_public()` for server context.
    """
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=params.poly_modulus_degree,
        coeff_mod_bit_sizes=params.coeff_mod_bit_sizes,
    )
    
    context.global_scale = 2 ** params.scale_bits
    context.auto_relin = True
    context.auto_rescale = True
    context.auto_mod_switch = True
    
    if generate_galois_keys:
        context.generate_galois_keys()
    if generate_relin_keys:
        context.generate_relin_keys()
    
    return context


def estimate_security(params: CKKSParams) -> dict:
    """
    Estimate security based on Homomorphic Encryption Standard tables.
    Returns dict with classical/quantum bits.
    """
    max_logq_128 = {4096: 109, 8192: 218, 16384: 438, 32768: 881}
    max_logq = max_logq_128.get(params.poly_modulus_degree, 218)
    
    if params.total_coeff_bits <= max_logq:
        estimated = float(params.security_level)
    else:
        ratio = max_logq / params.total_coeff_bits
        estimated = float(int(128 * ratio))
    
    return {
        "classical_bits": estimated,
        "quantum_bits": estimated * 0.5,
        "params": {
            "N": params.poly_modulus_degree,
            "logQ": params.total_coeff_bits,
            "sigma": params.std_dev,
        }
    }


def validate_params(params: CKKSParams) -> Tuple[bool, str]:
    """Validate parameters meet requirements."""
    if params.max_slots < 256:
        return False, f"Insufficient slots: {params.max_slots} < 256"
    
    sec = estimate_security(params)
    if sec["classical_bits"] < 128:
        return False, f"Security {sec['classical_bits']:.1f}-bit < target 128-bit"
    
    if len(params.coeff_mod_bit_sizes) < 4:
        return False, f"Insufficient coeff modulus chain length: need ≥4, got {len(params.coeff_mod_bit_sizes)}"
    
    return True, "OK"


if __name__ == "__main__":
    print("=== CKKS Parameter Validation ===")
    for name, params in [("DEFAULT", DEFAULT_PARAMS), 
                          ("HIGH_SECURITY", HIGH_SECURITY_PARAMS),
                          ("TEST", TEST_PARAMS)]:
        print(f"\n{name}:")
        print(f"  N={params.poly_modulus_degree}, logQ={params.total_coeff_bits}, scale=2^{params.scale_bits}")
        print(f"  Slots={params.max_slots}, Levels={params.num_levels}")
        
        valid, msg = validate_params(params)
        print(f"  Valid: {valid} ({msg})")
        
        sec = estimate_security(params)
        print(f"  Security: {sec['classical_bits']:.1f} classical, ~{sec['quantum_bits']:.1f} quantum")
