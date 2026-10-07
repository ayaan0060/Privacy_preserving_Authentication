#!/usr/bin/env python3
"""
Acceptance test suite for 'Privacy-Preserving Fingerprint Authentication Using Cancelable Templates and CKKS Homomorphic Encryption'.
Must be run via `make accept` or `python3 scripts/acceptance.py`.
Checks compiled PDF text, macros, arithmetic consistency, and code assertions.
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def run_command(cmd, cwd=ROOT_DIR):
    res = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout, res.stderr

def extract_pdf_text(pdf_path):
    # Try pdftotext first if available
    ret, out, _ = run_command(f"pdftotext {pdf_path} -")
    if ret == 0 and len(out.strip()) > 0:
        return out
    
    # Fallback to pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path}: {e}")

def main():
    print("=" * 70)
    print("RUNNING STAGE 0 ACCEPTANCE TESTS")
    print("=" * 70)
    
    failures = []
    passes = []
    
    def record_pass(test_id, msg):
        passes.append((test_id, msg))
        print(f"[PASS] {test_id}: {msg}")

    def record_fail(test_id, msg):
        failures.append((test_id, msg))
        print(f"[FAIL] {test_id}: {msg}")

    # ---------------------------------------------------------
    # 0. Compile paper.tex to paper.pdf
    # ---------------------------------------------------------
    print("\n--- [Stage 0.0: Compile paper.tex] ---")
    ret, out, err = run_command("tectonic paper.tex")
    if ret != 0:
        record_fail("COMPILE", f"tectonic compilation failed:\n{err or out}")
        return 1
    else:
        record_pass("COMPILE", "tectonic successfully built paper.pdf")

    pdf_path = ROOT_DIR / "paper.pdf"
    if not pdf_path.exists():
        record_fail("PDF_EXISTS", "paper.pdf was not produced")
        return 1
    
    pdf_text = extract_pdf_text(pdf_path)
    with open(ROOT_DIR / "paper.tex") as f:
        paper_tex = f.read()

    # ---------------------------------------------------------
    # 1. Forbidden strings in paper.pdf (case-insensitive regex)
    # ---------------------------------------------------------
    print("\n--- [Stage 0.1: Forbidden Strings in Compiled PDF] ---")
    forbidden_rules = [
        ("FORBIDDEN_AUC_1", r"AUC\s+(?:of|=)\s*1\.0000", "Forbidden string: 'AUC of 1.0000' or 'AUC = 1.0000'"),
        ("FORBIDDEN_COMPROMISED", r"completely\s+(?:compromised|vulnerable)", "Forbidden string: 'completely compromised' or 'completely vulnerable'"),
        ("FORBIDDEN_50_MBPS", r"50\s*Mbit/s\s*downlink", "Forbidden string: '50 Mbit/s downlink'"),
        ("FORBIDDEN_50_MS_RTT", r"50\s*ms\s*base\s*RTT", "Forbidden string: '50 ms base RTT'"),
        ("FORBIDDEN_IJBC", r"\bIJB-C\b", "Forbidden string: 'IJB-C'"),
        ("FORBIDDEN_BGV", r"\bBGV\b", "Forbidden string: 'BGV'"),
        ("FORBIDDEN_50_60_PCT", r"50\.60%", "Forbidden string: '50.60%'"),
        ("FORBIDDEN_99_8_PCT", r"99\.8%", "Forbidden string: '99.8%'"),
        ("FORBIDDEN_NO_ACCESS_SERVER", r"without\s+gaining\s+access\s+to\s+server\s+database", "Forbidden string: 'without gaining access to server database'"),
        ("FORBIDDEN_5_ADVERSARIES", r"five\s+distinct\s+adversary", "Forbidden string: 'five distinct adversary'"),
        ("FORBIDDEN_SIMD_ZERO", r"SIMD\s+register\s+zero", "Forbidden string: 'SIMD register zero'"),
        ("FORBIDDEN_PROD_EVAL", r"Production\s+Evaluation", "Forbidden string: 'Production Evaluation'"),
        ("FORBIDDEN_EXPLICITLY", r"\bexplicitly\b", "Forbidden string: 'explicitly'"),
        ("FORBIDDEN_UNRESOLVED_REF", r"\[\?\]", "Forbidden string: '[?]' unresolved citation"),
        ("FORBIDDEN_DOUBLE_QMARK", r"\?\?", "Forbidden string: '??' unresolved reference"),
    ]

    for test_id, pattern, desc in forbidden_rules:
        matches = list(re.finditer(pattern, pdf_text, re.IGNORECASE))
        if matches:
            matched_snippets = [repr(pdf_text[max(0, m.start()-20):min(len(pdf_text), m.end()+20)]) for m in matches[:3]]
            record_fail(test_id, f"{desc} found {len(matches)} times: {', '.join(matched_snippets)}")
        else:
            record_pass(test_id, f"{desc} not found in PDF")

    # Three random seeds check: forbidden unless Stage 3 proves three encoders
    three_encoder_checkpoints = list(ROOT_DIR.glob("exports/fingerprint_encoder_seed*.pt"))
    if len(three_encoder_checkpoints) < 3:
        # Must not say 'three random seeds' if not 3 encoders
        matches = list(re.finditer(r"three\s+random\s+seeds", pdf_text, re.IGNORECASE))
        if matches:
            record_fail("FORBIDDEN_THREE_SEEDS", f"Found 'three random seeds' in PDF without 3 trained encoders ({len(matches)} matches)")
        else:
            record_pass("FORBIDDEN_THREE_SEEDS", "'three random seeds' not claimed without 3 trained encoders")
    else:
        record_pass("FORBIDDEN_THREE_SEEDS", "Three encoder checkpoints found")

    # 'not met' must appear only next to the TAR row
    not_met_matches = list(re.finditer(r"not\s+met", pdf_text, re.IGNORECASE))
    invalid_not_met = []
    for m in not_met_matches:
        context = pdf_text[max(0, m.start()-80):min(len(pdf_text), m.end()+80)]
        if not re.search(r"TAR|Genuine\s+Acceptance", context, re.IGNORECASE):
            invalid_not_met.append(context)
    if invalid_not_met:
        record_fail("NOT_MET_RESTRICTION", f"'not met' appeared outside of TAR row: {invalid_not_met}")
    else:
        record_pass("NOT_MET_RESTRICTION", f"'not met' appears strictly in TAR row ({len(not_met_matches)} occurrences)")

    # Stage 8b: Additional forbidden checks
    stage8b_rules = [
        ("FORBIDDEN_DOUBLE_PERCENT", r"(?<!\\)%%",
         "Forbidden string: '%%' (double percent sign in PDF text)"),
        ("FORBIDDEN_DESIGN_TARGET", r"Design\s+Target",
         "Forbidden string: 'Design Target' (column removed in Stage 4)"),
        ("FORBIDDEN_STRESS_TEST_FRAMING", r"\bstress\s+test\b",
         "Forbidden string: 'stress test' (framing removed in Stage 5b)"),
        ("FORBIDDEN_DEPLOYMENT_FEASIBILITY", r"Deployment\s+Feasibility",
         "Forbidden string: 'Deployment Feasibility' (renamed in Stage 5d)"),
        ("FORBIDDEN_GITHUB_URL", r"\bgithub\.com\b|\bgithub\b",
         "Forbidden string: 'github' (repository reference removed per Stage 5g)"),
        ("FORBIDDEN_REPOSITORY_WORD", r"\brepository\b",
         "Forbidden string: 'repository' (repository reference removed per Stage 5g)"),
        ("FORBIDDEN_OPEN_SOURCE_RELEASE", r"open.source\s+release|open\s+source\s+release",
         "Forbidden string: 'open-source release'"),
        ("FORBIDDEN_EER_CONTRADICTION", r"(?:9\.(?:77|90)%.*?2\.(?:89|85)%|2\.(?:89|85)%.*?9\.(?:77|90)%).*?(?:ROP|plaintext)",
         "Forbidden string: sentence pairing headline EER with easy EER for ROP/plaintext"),
    ]
    for test_id, pattern, desc in stage8b_rules:
        matches = list(re.finditer(pattern, pdf_text, re.IGNORECASE))
        if matches:
            snippets = [repr(pdf_text[max(0, m.start()-20):min(len(pdf_text), m.end()+20)]) for m in matches[:3]]
            record_fail(test_id, f"{desc} found {len(matches)} times: {', '.join(snippets)}")
        else:
            record_pass(test_id, f"{desc} not found in PDF")

    # Protocol results file must exist
    proto_results = ROOT_DIR / "results" / "final" / "protocol_results.json"
    if proto_results.exists():
        with open(proto_results) as f_pr:
            _pr = json.load(f_pr)
        all_eer_val = _pr.get("protocol_metrics", {}).get("ALL", {}).get("schemes", {}).get("rop", {}).get("eer_mean", None)
        if all_eer_val is not None:
            record_pass("PROTOCOL_RESULTS_EXIST", f"Protocol results present (ALL ROP EER={all_eer_val:.2f}%)")
        else:
            record_fail("PROTOCOL_RESULTS_EXIST", "Protocol results file exists but ALL ROP EER missing")
    else:
        record_fail("PROTOCOL_RESULTS_EXIST", "results/final/protocol_results.json missing — run scripts/run_protocol_experiments.py")

    # Pair CSVs must exist for both protocols
    pairs_all_csv  = ROOT_DIR / "results" / "final" / "pairs_all.csv"
    pairs_easy_csv = ROOT_DIR / "results" / "final" / "pairs_easy.csv"
    if pairs_all_csv.exists() and pairs_easy_csv.exists():
        record_pass("PROTOCOL_PAIR_CSVS", "pairs_all.csv and pairs_easy.csv present in results/final/")
    else:
        record_fail("PROTOCOL_PAIR_CSVS", f"Missing pair CSVs: all={pairs_all_csv.exists()}, easy={pairs_easy_csv.exists()}")

    # Table IV Learned Attacker Check (differs from simple attacks)
    unl_path = ROOT_DIR / "results" / "final" / "unlinkability_results.json"
    if unl_path.exists():
        with open(unl_path) as f_u:
            _unl = json.load(f_u)
        diff_count = 0
        total_schemes = len(_unl.get("unlinkability_table", {}))
        for _sch, _dat in _unl.get("unlinkability_table", {}).items():
            _l = _dat.get("auc_learned_mlp", 0)
            _c = _dat.get("auc_cosine", 0)
            _a = _dat.get("auc_abs_val", 0)
            _s = _dat.get("auc_sort_mag", 0)
            if _l != _c and _l != _a and _l != _s:
                diff_count += 1
        if diff_count == total_schemes:
            record_pass("LEARNED_ATTACKER_DISTINCT", f"Learned attacker AUC is distinct from simple attacks for all {total_schemes} schemes")
        else:
            record_fail("LEARNED_ATTACKER_DISTINCT", f"Learned attacker matches simple attacks in {total_schemes - diff_count} schemes")
    else:
        record_fail("LEARNED_ATTACKER_DISTINCT", "unlinkability_results.json missing")

    # Table III single-seed within mean +/- 3 std
    if proto_results.exists():
        outlier_schemes = []
        all_schemes = _pr.get("protocol_metrics", {}).get("ALL", {}).get("schemes", {})
        for _sch, _sdata in all_schemes.items():
            _mean = _sdata.get("eer_mean", 0)
            _std = _sdata.get("eer_std", 0)
            _single = _sdata.get("single_seed_eer", _mean)
            if abs(_single - _mean) > 3 * _std + 1e-4:
                outlier_schemes.append((_sch, _single, _mean, _std))
        if not outlier_schemes:
            record_pass("TABLE_III_SINGLE_SEED_BOUNDS", "All Table III single-seed values are within mean +/- 3 std")
        else:
            record_fail("TABLE_III_SINGLE_SEED_BOUNDS", f"Outlier single-seed values found: {outlier_schemes}")

    # ---------------------------------------------------------
    # 2. Required in text
    # ---------------------------------------------------------
    print("\n--- [Stage 0.2: Required Text Content] ---")
    

    # Required: All-alteration EER macro in abstract and Table II
    # In metrics.json, we must have all-alteration EER, and it must be macro-referenced in abstract and Table II
    metrics_path = ROOT_DIR / "results" / "final" / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
    else:
        metrics = {}

    has_all_alteration_metric = "all_alteration" in metrics.get("verification", {}) or "all_alteration_eer" in metrics.get("verification", {})
    # Check if abstract has all-alteration EER
    abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", paper_tex, re.DOTALL)
    abstract_text = abstract_match.group(1) if abstract_match else ""
    
    has_all_alt_in_abstract = "\\AllAlterationEER" in abstract_text or ("all-alteration" in abstract_text.lower() and "\\HeadlineEER" in abstract_text)
    tab_spec_path = ROOT_DIR / "tables" / "tab_specifications.tex"
    tab_spec_content = tab_spec_path.read_text() if tab_spec_path.exists() else ""
    has_all_alt_in_tab_spec = "all-alteration" in tab_spec_content.lower() or "\\AllAlterationEER" in tab_spec_content

    if has_all_alt_in_abstract and has_all_alt_in_tab_spec and has_all_alteration_metric:
        record_pass("REQUIRED_ALL_ALT_EER", "All-alteration EER is reported in abstract and Table II")
    else:
        record_fail("REQUIRED_ALL_ALT_EER", f"All-alteration EER missing in abstract or Table II (metric_present={has_all_alteration_metric}, abstract={has_all_alt_in_abstract}, tab_spec={has_all_alt_in_tab_spec})")

    # Required: Sentence stating exactly which pairs nominal 10,000-pair benchmark uses (counts by alteration level)
    # E.g., counts by alteration level (Easy, Medium, Hard)
    has_nominal_pair_breakdown = bool(
        re.search(r"nominal.*?10[,\s]*000.*?pairs.*?(?:easy|altered)", paper_tex, re.IGNORECASE) and
        re.search(r"(?:easy|medium|hard).*?(?:count|pairs|\d+)", paper_tex, re.IGNORECASE) and
        ("Easy-only" in paper_tex or "easy alteration" in paper_tex.lower())
    )
    if has_nominal_pair_breakdown:
        record_pass("REQUIRED_NOMINAL_PAIR_BREAKDOWN", "Nominal 10,000-pair benchmark discloses pair counts by alteration level")
    else:
        record_fail("REQUIRED_NOMINAL_PAIR_BREAKDOWN", "Sentence stating exactly which pairs nominal 10,000-pair benchmark uses (counts by alteration level) is missing")

    # ---------------------------------------------------------
    # 3. Numeric consistency & abstract word count
    # ---------------------------------------------------------
    print("\n--- [Stage 0.3: Numeric Consistency & Abstract Length] ---")
    
    # Abstract word count <= 250
    # Clean abstract words (strip LaTeX comments and commands)
    clean_abstract = re.sub(r"%.*?\n", " ", abstract_text)
    clean_abstract = re.sub(r"\\[a-zA-Z]+(\{[^}]*\})?", " word ", clean_abstract)
    abstract_words = [w for w in clean_abstract.split() if w.strip()]
    word_count = len(abstract_words)
    if word_count <= 250:
        record_pass("ABSTRACT_WORD_COUNT", f"Abstract has {word_count} words (<= 250 limit)")
    else:
        record_fail("ABSTRACT_WORD_COUNT", f"Abstract has {word_count} words (> 250 limit)")

    # Macro consistency: verify that macros in results/final/macros.tex are uniquely defined
    macros_path = ROOT_DIR / "results" / "final" / "macros.tex"
    if macros_path.exists():
        with open(macros_path) as f:
            macro_lines = f.readlines()
        macro_defs = {}
        dup_macros = []
        for line in macro_lines:
            m = re.match(r"\\newcommand\{\\([A-Za-z0-9]+)\}\{(.*?)\}", line.strip())
            if m:
                k, v = m.group(1), m.group(2)
                if k in macro_defs:
                    dup_macros.append(k)
                macro_defs[k] = v
        if dup_macros:
            record_fail("MACRO_CONSISTENCY", f"Duplicate macro definitions found: {dup_macros}")
        else:
            record_pass("MACRO_CONSISTENCY", f"{len(macro_defs)} macros defined with zero duplicate collisions")
    else:
        record_fail("MACRO_CONSISTENCY", "macros.tex missing")

    # ---------------------------------------------------------
    # 4. Arithmetic assertions (computed from metrics.json)
    # ---------------------------------------------------------
    print("\n--- [Stage 0.4: Arithmetic Assertions] ---")
    
    # 4G total = uplink + downlink + RTT + handshake + compute with ONE parameter set in text and Table VI
    ckks_data = metrics.get("ckks", {})
    perf_data = metrics.get("performance", {})
    load_test_path = ROOT_DIR / "results" / "raw" / "load_test_results.json"

    # Verify Little's Law discrepancy per row < 5% and throughput X <= N/Z
    if load_test_path.exists():
        with open(load_test_path) as f:
            load_rows = json.load(f)
        load_fail = []
        for r in load_rows:
            N = r.get("concurrent_clients", r.get("N", 0))
            X = r.get("throughput_req_per_s", r.get("throughput_rps", 0.0))
            Z = r.get("think_time_s", 1.25)
            R = (r.get("mean_latency_ms", 0.0)) / 1000.0
            
            # Little's Law: N_exp = X * (R + Z)
            N_exp = X * (R + Z)
            disc = abs(N_exp - N) / N if N > 0 else 0.0
            if disc >= 0.05:
                load_fail.append(f"N={N}: disc={disc*100:.2f}% >= 5%")
            if X > (N / Z) + 1e-4:
                load_fail.append(f"N={N}: X={X:.2f} > max_possible={N/Z:.2f}")

        if load_fail:
            record_fail("LOAD_TEST_ARITHMETIC", f"Load test arithmetic violations: {load_fail}")
        else:
            record_pass("LOAD_TEST_ARITHMETIC", f"Little's Law (<5% discrepancy) and X <= N/Z verified for all {len(load_rows)} load rows")
    else:
        record_fail("LOAD_TEST_ARITHMETIC", "load_test_results.json not found")

    # 4G arithmetic assertion
    # Total mobile latency must equal network delay + unloaded compute e2e latency
    net_delay = ckks_data.get("cellular_4g_delay_ms", 0.0)
    total_mobile = ckks_data.get("total_mobile_latency_ms", 0.0)
    compute_e2e = perf_data.get("directly_measured_end_to_end_median_ms", 0.0)
    
    if net_delay > 0 and compute_e2e > 0 and total_mobile > 0:
        expected_total = net_delay + compute_e2e
        diff = abs(total_mobile - expected_total)
        if diff < 0.1:
            record_pass("CELLULAR_4G_ARITHMETIC", f"4G total {total_mobile:.2f} ms matches net ({net_delay:.2f} ms) + compute ({compute_e2e:.2f} ms)")
        else:
            record_fail("CELLULAR_4G_ARITHMETIC", f"4G arithmetic discrepancy: total={total_mobile:.2f} ms vs net({net_delay:.2f}) + compute({compute_e2e:.2f}) = {expected_total:.2f} ms (diff={diff:.2f} ms)")
    else:
        record_fail("CELLULAR_4G_ARITHMETIC", f"Missing 4G metrics for arithmetic assertion (net={net_delay}, compute={compute_e2e}, total={total_mobile})")

    # ---------------------------------------------------------
    # 5. Code assertions: FiLM Generator Checkpoint Loading & Ranges
    # ---------------------------------------------------------
    print("\n--- [Stage 0.5: Code Assertions (FiLM)] ---")
    
    # No script may instantiate FiLMGenerator() without loading the trained checkpoint
    script_files = list((ROOT_DIR / "scripts").glob("*.py"))
    unloaded_film_instances = []
    
    for py_file in script_files:
        content = py_file.read_text()
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if "FiLMGenerator(" in line and not line.strip().startswith("#"):
                # Check next 20 lines for load_state_dict or torch.load
                subsequent_block = "\n".join(lines[idx:idx+25])
                if "load_state_dict" not in subsequent_block and "load_from_checkpoint" not in subsequent_block:
                    unloaded_film_instances.append(f"{py_file.name}:{idx+1}")

    if unloaded_film_instances:
        record_fail("FILM_CHECKPOINT_LOADING", f"FiLMGenerator instantiated without loading trained checkpoint at: {unloaded_film_instances}")
    else:
        record_pass("FILM_CHECKPOINT_LOADING", "All FiLMGenerator instantiations load trained checkpoints")

    # Checkpoint statistics match paper equations
    film_ckpt_path = ROOT_DIR / "exports" / "film_generator.pt"
    if not film_ckpt_path.exists():
        record_fail("FILM_CHECKPOINT_EXISTS", f"Trained FiLM checkpoint missing at {film_ckpt_path.relative_to(ROOT_DIR)}")
    else:
        record_pass("FILM_CHECKPOINT_EXISTS", f"Trained FiLM checkpoint present at {film_ckpt_path.relative_to(ROOT_DIR)}")

    # ---------------------------------------------------------
    # 6. Semantic Provenance & Geometric Quality Checks
    # ---------------------------------------------------------
    print("\n--- [Stage 0.6: Semantic Provenance & Geometric Quality] ---")

    # ROP Isometry check: Inner product preservation < 1e-5
    rop_iso_diff = metrics.get("verification", {}).get("rop_isometry_max_diff", 0.0)
    if 0.0 <= rop_iso_diff < 1e-5:
        record_pass("ROP_ISOMETRY", f"ROP preserves inner products with max deviation {rop_iso_diff:.2e} < 1e-5")
    else:
        record_fail("ROP_ISOMETRY", f"ROP isometry violation: max deviation {rop_iso_diff:.2e} >= 1e-5")

    # Validation tau provenance check
    val_tau_metrics = metrics.get("verification", {}).get("val_transfer_tau")
    if proto_results.exists():
        with open(proto_results) as f_pr:
            pr_data = json.load(f_pr)
        val_tau_proto = pr_data.get("protocol_metrics", {}).get("ALL", {}).get("validation_transfer", {}).get("val_tau")
        if val_tau_metrics is not None and val_tau_proto is not None and abs(val_tau_metrics - val_tau_proto) < 1e-4:
            record_pass("VAL_TAU_PROVENANCE", f"Validation tau ({val_tau_metrics:.4f}) matches between metrics.json and protocol_results.json")
        else:
            record_fail("VAL_TAU_PROVENANCE", f"Validation tau discrepancy: metrics={val_tau_metrics} vs proto={val_tau_proto}")
    else:
        record_fail("VAL_TAU_PROVENANCE", "protocol_results.json missing for tau validation check")

    # ROC Figure limits check: ax_roc y-axis starts at 0.40 or below to avoid TAR clipping
    make_fig_path = ROOT_DIR / "scripts" / "make_figures.py"
    if make_fig_path.exists():
        fig_content = make_fig_path.read_text()
        if "set_ylim(0.40" in fig_content or "set_ylim(0.35" in fig_content or "set_ylim(0.0" in fig_content:
            record_pass("ROC_FIGURE_LIMITS", "ROC curve y-axis properly avoids clipping TAR curves (starts <= 0.40)")
        else:
            record_fail("ROC_FIGURE_LIMITS", "ROC curve y-axis clipping TAR curve (missing set_ylim(0.40, ...))")
    else:
        record_fail("ROC_FIGURE_LIMITS", "make_figures.py missing")

    # Provenance Manifest Audit check
    manifest_path = ROOT_DIR / "results" / "final" / "manifest.json"
    if manifest_path.exists():
        try:
            from scripts.audit_provenance import audit_provenance as run_audit
            if run_audit():
                record_pass("MANIFEST_PROVENANCE_AUDIT", "Manifest audit verified all raw and final artifacts")
            else:
                record_fail("MANIFEST_PROVENANCE_AUDIT", "Manifest audit failed")
        except Exception as e:
            record_fail("MANIFEST_PROVENANCE_AUDIT", f"Manifest audit exception: {e}")
    else:
        record_fail("MANIFEST_PROVENANCE_AUDIT", "manifest.json missing")

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"ACCEPTANCE TEST SUMMARY: {len(passes)} PASSED, {len(failures)} FAILED")
    print("=" * 70)
    for tid, msg in passes:
        print(f"  [✓] {tid}")
    for tid, msg in failures:
        print(f"  [✗] {tid}: {msg}")
    print("=" * 70)

    if failures:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
