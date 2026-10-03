# phase3_fusion/scripts/train_film.py
import os, sys, yaml, logging
import torch
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint, LearningRateMonitor, Callback
from pytorch_lightning.loggers import TensorBoardLogger
from torch.utils.data import DataLoader

# Path Setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase1_encoder')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'phase2_keymgmt')))

from src.data.fusion_dataset import FusionDataset
from src.engine.trainer import FusionTrainer
from src.models.film import FiLMGenerator

# Phase 1 Imports
from phase1_encoder.src.data.transforms import get_val_transforms, extract_roi_fixed_center
from phase1_encoder.src.models.backbone import FingerprintEncoder
from phase1_encoder.src.config import load_config as load_p1_config
from phase2_keymgmt.src.config import load_config as load_p2_config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class IncrementVersionCallback(Callback):
    """Calls dataset.increment_key_versions() every epoch."""
    def on_train_epoch_start(self, trainer, pl_module):
        if hasattr(trainer.train_dataloader, 'dataset'):
            ds = trainer.train_dataloader.dataset
            if hasattr(ds, 'increment_key_versions'):
                ds.increment_key_versions()
                log.info(f"Epoch {trainer.current_epoch}: Incremented Key Versions for all users.")

def load_config(path): 
    with open(path, 'r') as f: return yaml.safe_load(f)

def main():
    config = load_config("config.yaml")
    p1_config = load_p1_config(config['paths']['phase1_config'])
    p2_config = load_p2_config(config['paths']['phase2_config'])
    
    pl.seed_everything(config['project']['seed'], workers=True)
    device = torch.device(config['project']['device'])
    
    # 1. Load Phase 1 Encoder
    encoder = FingerprintEncoder(
        embedding_dim=p1_config['model']['embedding_dim'],
        pretrained=False, dropout=0.0
    ).to(device)
    ckpt = torch.load(config['paths']['phase1_encoder_ckpt'], map_location=device)
    enc_state = {k.replace('encoder.', ''): v for k, v in ckpt['state_dict'].items() if k.startswith('encoder.')}
    encoder.load_state_dict(enc_state)
    encoder.eval()
    
    # 2. Transforms
    val_tf = get_val_transforms(p1_config['preprocessing']['img_size'], 
                                p1_config['preprocessing']['clahe_clip_limit'],
                                p1_config['preprocessing']['clahe_tile_grid'])
    
    # 3. Datasets
    train_ds = FusionDataset(encoder, p1_config['paths']['soco_root'], 
                             p2_config, val_tf, extract_roi_fixed_center, split="train")
    val_ds = FusionDataset(encoder, p1_config['paths']['soco_root'],
                           p2_config, val_tf, extract_roi_fixed_center, split="val")
    
    train_loader = DataLoader(train_ds, batch_size=config['training']['batch_size'], 
                              shuffle=True, num_workers=config['training']['num_workers'], pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=config['training']['batch_size'], 
                            shuffle=False, num_workers=4)
    
    num_classes = len(train_ds.user_to_idx)
    log.info(f"Training Identities: {num_classes}")
    
    # 4. Model
    model = FusionTrainer(config, num_classes, config['paths']['phase1_encoder_ckpt'], p1_config)
    
    # 5. Trainer
    ckpt_dir = os.path.join(config['paths']['output_dir'], 'checkpoints')
    os.makedirs(ckpt_dir, exist_ok=True)
    
    callbacks = [
        ModelCheckpoint(dirpath=ckpt_dir, monitor='val/loss_arc', mode='min', save_top_k=3, filename='film-epoch={epoch}-val_loss={val/loss_arc:.4f}'),
        LearningRateMonitor(),
        IncrementVersionCallback()
    ]
    
    trainer = pl.Trainer(
        max_epochs=config['training']['epochs'],
        accelerator=config['project']['device'], devices=1,
        precision='16-mixed' if config['training']['amp'] else 32,
        callbacks=callbacks, logger=TensorBoardLogger(config['paths']['log_dir'], name="film"),
        gradient_clip_val=1.0
    )
    
    trainer.fit(model, train_loader, val_loader)
    log.info(f"Best FiLM Model: {trainer.checkpoint_callback.best_model_path}")

if __name__ == "__main__":
    main()
