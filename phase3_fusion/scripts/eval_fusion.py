# phase3_fusion/scripts/eval_fusion.py
import argparse, yaml, torch, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase1_encoder')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase2_keymgmt')))

from src.engine.trainer import FusionTrainer
from src.engine.evaluator import evaluate_verification, evaluate_unlinkability
from src.data.fusion_dataset import FusionDataset
from phase1_encoder.src.data.transforms import get_val_transforms, extract_roi_fixed_center
from phase1_encoder.src.models.backbone import FingerprintEncoder
from phase1_encoder.src.config import load_config as load_p1_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ckpt', required=True, help='FiLM Checkpoint (.ckpt)')
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()
    
    config = yaml.safe_load(open(args.config))
    p1_config = load_p1_config(config['paths']['phase1_config'])
    p2_config = yaml.safe_load(open(config['paths']['phase2_config']))
    
    device = torch.device(config['project']['device'])
    
    # Load Encoder for Dataset
    encoder = FingerprintEncoder(embedding_dim=p1_config['model']['embedding_dim'], pretrained=False, dropout=0.0).to(device)
    p1_ckpt = torch.load(config['paths']['phase1_encoder_ckpt'], map_location=device)
    enc_state = {k.replace('encoder.', ''): v for k, v in p1_ckpt['state_dict'].items() if k.startswith('encoder.')}
    encoder.load_state_dict(enc_state)
    encoder.eval()
    
    val_tf = get_val_transforms(p1_config['preprocessing']['img_size'], p1_config['preprocessing']['clahe_clip_limit'], p1_config['preprocessing']['clahe_tile_grid'])
    
    # Load FiLM Trainer
    model = FusionTrainer.load_from_checkpoint(
        args.ckpt, config=config, num_train_classes=1, 
        encoder_ckpt_path=config['paths']['phase1_encoder_ckpt'], phase1_config=p1_config
    )
    model.eval().to(device)
    
    # --- UNLINKABILITY TEST (Synthetic) ---
    print("\n=== UNLINKABILITY TEST ===")
    with torch.no_grad():
        sims = []
        for _ in range(1000):
            x = torch.randn(1, 256, device=device)
            x = torch.nn.functional.normalize(x, dim=1)
            k1 = (torch.rand(1, 256, device=device) * 2 - 1)
            k2 = (torch.rand(1, 256, device=device) * 2 - 1)
            t1 = model.fusion(x, k1)[0]
            t2 = model.fusion(x, k2)[0]
            sims.append(torch.nn.functional.cosine_similarity(t1, t2).item())
        
        sims = torch.tensor(sims)
        print(f"Mean CosSim: {sims.mean():.6f} (Target ~0.0)")
        print(f"Std CosSim:  {sims.std():.6f} (Target ~0.0625)")
        print(f"Max |Sim|:   {sims.abs().max():.6f}")
        assert sims.abs().max() < 0.3, "UNLINKABILITY FAILED"
        print("✅ Unlinkability PASSED")
    
    print("\n=== VERIFICATION TEST ===")
    print("Run Phase 1 evaluate.py logic with Encoder + FiLM fusion layer.")

if __name__ == "__main__":
    main()
