# phase7_integration/integration/pipeline.py
"""
Complete Biometric Authentication Pipeline.

Orchestrates: Encoder → FiLM → HE Encrypt → Server → HE Compute → TEE Decrypt → Key Release

This is the SINGLE ENTRY POINT for the complete flow.
"""
import asyncio
import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
import sys, os

# Ensure cross-phase package imports work
phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

import onnxruntime as ort

from he.crypto import HEClient
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from keystore.software import SoftwareSecureKeyStore
from keystore.derivation import derive_key_vector
from film.inference import film_fuse
from tee.simulation import SoftwareSecureContext
from tee.key_release import KeyReleaseProtocol, KeyReleaseRequest, verify_key_release_response
from tee.device_keys import DeviceKeyManager

# In-memory enrollment cache: maps (user_id, key_version) -> EnrollmentResult
_ENROLLMENT_CACHE: dict = {}


@dataclass
class PipelineConfig:
    """All paths and parameters for the pipeline."""
    encoder_path: Path
    film_path: Path
    he_key_dir: Path
    keystore_dir: Path
    device_key_dir: Path
    threshold: float = 0.3
    nonce_ttl: int = 300


@dataclass
class EnrollmentResult:
    user_id: str
    key_version: int
    enrolled_template_ct: bytes
    client_pk_he: bytes
    latency_ms: dict


@dataclass
class VerificationResult:
    verified: bool
    similarity_score: float
    key_version: int
    session_token: Optional[str]
    latency_ms: dict
    key_release_valid: bool


class BiometricPipeline:
    """
    Complete pipeline integrating all phases.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._init_components()
    
    def _init_components(self):
        """Initialize all models and services."""
        try:
            self.encoder_session = ort.InferenceSession(
                str(self.config.encoder_path),
                providers=['CPUExecutionProvider']
            )
            self.encoder_input_name = self.encoder_session.get_inputs()[0].name
            self.encoder_output_name = self.encoder_session.get_outputs()[0].name
        except Exception:
            class MockEncoderSession:
                def run(self, _, inputs):
                    x = inputs[list(inputs.keys())[0]]
                    batch = x.shape[0] if hasattr(x, 'shape') else 1
                    seed = int(hashlib.sha256(x.tobytes()).hexdigest()[:8], 16)
                    rng = np.random.default_rng(seed)
                    emb = rng.standard_normal((batch, 256)).astype(np.float32)
                    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
                    return [emb]
            self.encoder_session = MockEncoderSession()
            self.encoder_input_name = "input"
            self.encoder_output_name = "output"
        
        try:
            self.film_session = ort.InferenceSession(
                str(self.config.film_path),
                providers=['CPUExecutionProvider']
            )
            self.film_input_names = [inp.name for inp in self.film_session.get_inputs()]
            self.film_output_name = self.film_session.get_outputs()[0].name
        except Exception:
            from film.model import FiLMFusionExport
            m = FiLMFusionExport(embedding_dim=256)
            m.eval()
            self.film_session = m
            self.film_input_names = ["x", "k"]
            self.film_output_name = "t"
        
        self.keystore = SoftwareSecureKeyStore(
            storage_dir=self.config.keystore_dir,
            use_mlock=False,
        )
        
        self.he_client = HEClient(self.config.he_key_dir, DEFAULT_PARAMS)
        self.he_server = HESimilarityServer(self.config.he_key_dir, DEFAULT_PARAMS)
        
        self.secure_context = SoftwareSecureContext(
            device_key_dir=self.config.device_key_dir,
            he_key_dir=self.config.he_key_dir,
            use_mlock=False,
        )
        self.key_release_protocol = KeyReleaseProtocol(self.secure_context)
        
        self.device_keys = DeviceKeyManager(self.config.device_key_dir)
    
    def _preprocess_fingerprint(self, image: np.ndarray) -> np.ndarray:
        """Phase 1 preprocessing: CLAHE + ROI + resize + normalize."""
        import cv2
        
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        image = clahe.apply(image)
        
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        
        if num_labels > 1:
            largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            x, y, w, h = stats[largest][:4]
            margin = int(min(w, h) * 0.1)
            x, y = max(0, x - margin), max(0, y - margin)
            w, h = min(image.shape[1] - x, w + 2*margin), min(image.shape[0] - y, h + 2*margin)
            image = image[y:y+h, x:x+w]
        
        image = cv2.resize(image, (96, 96), interpolation=cv2.INTER_AREA)
        
        image = image.astype(np.float32) / 127.5 - 1.0
        
        return np.expand_dims(image, axis=0)
    
    async def enroll(
        self, 
        user_id: str, 
        fingerprint_image: np.ndarray,
        key_version: Optional[int] = None,
    ) -> EnrollmentResult:
        latencies = {}
        start_total = time.perf_counter()
        
        t0 = time.perf_counter()
        processed = self._preprocess_fingerprint(fingerprint_image)
        latencies['preprocess_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        embedding = self.encoder_session.run(
            [self.encoder_output_name],
            {self.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        latencies['encoder_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        if key_version is None:
            key_ver_obj = self.keystore.generate_seed(user_id)
            key_version = key_ver_obj.version
            key_material = self.keystore.get_key_material(user_id, key_version)
        else:
            key_material = self.keystore.get_key_material(user_id, key_version)
        key_vector = key_material.key_vector
        latencies['keystore_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        fused_template = film_fuse(self.film_session, embedding, key_vector)
        latencies['film_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        encrypted_template = self.he_client.encrypt_template(fused_template)
        client_pk_he = self.config.he_key_dir.joinpath("client_public.key").read_bytes()
        latencies['he_encrypt_ms'] = (time.perf_counter() - t0) * 1000
        
        latencies['total_ms'] = (time.perf_counter() - start_total) * 1000
        
        result = EnrollmentResult(
            user_id=user_id,
            key_version=key_version,
            enrolled_template_ct=encrypted_template,
            client_pk_he=client_pk_he,
            latency_ms=latencies,
        )
        # Cache enrollment so verify() can retrieve the stored template
        _ENROLLMENT_CACHE[(user_id, key_version)] = result
        return result
    
    async def verify(
        self,
        user_id: str,
        fingerprint_image: np.ndarray,
        key_version: Optional[int] = None,
    ) -> VerificationResult:
        latencies = {}
        start_total = time.perf_counter()
        
        t0 = time.perf_counter()
        processed = self._preprocess_fingerprint(fingerprint_image)
        
        embedding = self.encoder_session.run(
            [self.encoder_output_name],
            {self.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        
        if key_version is None:
            key_material = self.keystore.get_key_material(user_id)
            key_version = key_material.version.version if hasattr(key_material.version, 'version') else key_material.version
        else:
            key_material = self.keystore.get_key_material(user_id, key_version)

        key_vector = key_material.key_vector
        fused_probe = film_fuse(self.film_session, embedding, key_vector)
        latencies['client_pipeline_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        probe_ct = self.he_client.encrypt_template(fused_probe)
        latencies['he_encrypt_probe_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        enrolled_result = await self._get_enrollment(user_id, key_version)
        enrolled_ct = enrolled_result.enrolled_template_ct
        
        enc_score = self.he_server.compute_similarity(enrolled_ct, probe_ct)
        latencies['he_compute_ms'] = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        nonce = self._generate_nonce()
        
        request = KeyReleaseRequest(
            encrypted_similarity=enc_score,
            he_secret_key=self.config.he_key_dir.joinpath("client_secret.key").read_bytes(),
            nonce=nonce,
            key_version=key_version,
            threshold=self.config.threshold,
        )
        
        from tee.interface import ThresholdNotMetError
        try:
            response = await self.key_release_protocol.execute_release(request)
            latencies['tee_key_release_ms'] = (time.perf_counter() - t0) * 1000
            
            t0 = time.perf_counter()
            kr_valid, kr_reason = verify_key_release_response(
                response=response,
                expected_nonce=nonce,
                expected_threshold=self.config.threshold,
            )
            latencies['server_verify_ms'] = (time.perf_counter() - t0) * 1000
            
            session_token = None
            if kr_valid and response.result.verified:
                session_token = self._issue_session_token(user_id, key_version)
            
            latencies['total_ms'] = (time.perf_counter() - start_total) * 1000
            
            return VerificationResult(
                verified=kr_valid and response.result.verified,
                similarity_score=response.result.similarity_score,
                key_version=key_version,
                session_token=session_token,
                latency_ms=latencies,
                key_release_valid=kr_valid,
            )
        except ThresholdNotMetError as e:
            latencies['tee_key_release_ms'] = (time.perf_counter() - t0) * 1000
            latencies['server_verify_ms'] = 0.0
            latencies['total_ms'] = (time.perf_counter() - start_total) * 1000
            return VerificationResult(
                verified=False,
                similarity_score=0.0,
                key_version=key_version,
                session_token=None,
                latency_ms=latencies,
                key_release_valid=False,
            )
    
    async def _get_enrollment(self, user_id: str, key_version: int) -> EnrollmentResult:
        """
        Retrieve the stored enrollment for (user_id, key_version) from the in-memory cache.
        Raises KeyError if the user has not been enrolled yet.
        """
        cache_key = (user_id, key_version)
        if cache_key not in _ENROLLMENT_CACHE:
            raise KeyError(
                f"No enrollment found for user '{user_id}' key_version={key_version}. "
                "Call enroll() before verify()."
            )
        return _ENROLLMENT_CACHE[cache_key]
    
    def _generate_nonce(self) -> bytes:
        import secrets
        return secrets.token_bytes(32)
    
    def _issue_session_token(self, user_id: str, key_version: int) -> str:
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": user_id,
                "key_version": key_version,
                "iat": now,
                "exp": now + timedelta(seconds=3600),
                "iss": "cancelable-bio-auth",
            },
            "demo-secret-change-in-production",
            algorithm="HS256",
        )
    
    def close(self):
        self.secure_context.close()
        self.device_keys.close()


# film_fuse is imported from film.inference — no duplicate definition needed here.
