# phase3_fusion/scripts/export_fusion.py
import argparse, yaml, torch, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase1_encoder')))

from src.models.combined import CombinedFusionModel, EncoderWrapper
from src.models.film import FiLMGenerator, FiLMFusion
from src.engine.trainer import FusionTrainer
from phase1_encoder.src.config import load_config as load_p1_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ckpt', required=True)
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--out_dir', default='exports/phase3')
    args = parser.parse_args()
    
    config = yaml.safe_load(open(args.config))
    p1_config = load_p1_config(config['paths']['phase1_config'])
    os.makedirs(args.out_dir, exist_ok=True)
    
    # Load FiLM Trainer
    model = FusionTrainer.load_from_checkpoint(
        args.ckpt, config=config, num_train_classes=1,
        encoder_ckpt_path=config['paths']['phase1_encoder_ckpt'], phase1_config=p1_config
    )
    model.eval()
    
    # Build Combined Model
    encoder_wrapper = EncoderWrapper(config['paths']['phase1_encoder_ckpt'], p1_config)
    combined = CombinedFusionModel(encoder_wrapper, model.fusion)
    
    # Export
    combined.export_onnx_separate(
        onnx_encoder_path=os.path.join(args.out_dir, "encoder.onnx"),
        onnx_film_path=os.path.join(args.out_dir, "film_generator.onnx"),
        onnx_combined_path=os.path.join(args.out_dir, "fusion_combined.onnx"),
        config=config
    )
    
    print(f"\n✅ Exports saved to {args.out_dir}")
    print("  - encoder.onnx: Image -> Embedding (Phase 1)")
    print("  - film_generator.onnx: Key k -> Gamma, Beta")
    print("  - fusion_combined.onnx: Image, Key k -> Template t (CLIENT SIDE)")

if __name__ == "__main__":
    main()
