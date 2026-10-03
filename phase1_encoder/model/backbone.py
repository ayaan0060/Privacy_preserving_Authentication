# phase1_encoder/model/backbone.py
"""
ResNet18-style backbone for fingerprint embedding.
- No pretrained weights (fingerprint domain is too different from ImageNet)
- Modified stem: 1 input channel, no maxpool (small 96x96 input)
- Output: 512-d feature map before pooling
"""
import torch
import torch.nn as nn
from typing import List

class BasicBlock(nn.Module):
    expansion = 1
    
    def __init__(self, in_planes: int, planes: int, stride: int = 1, downsample: nn.Module | None = None):
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            identity = self.downsample(x)
        out += identity
        out = self.relu(out)
        return out


class ResNetBackbone(nn.Module):
    def __init__(
        self,
        block: type[BasicBlock] = BasicBlock,
        layers: List[int] = [2, 2, 2, 2],  # ResNet18
        in_channels: int = 1,
        base_width: int = 64,
    ):
        super().__init__()
        self.in_planes = base_width
        
        # Modified stem for 1-channel, small input
        self.conv1 = nn.Conv2d(in_channels, base_width, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(base_width)
        self.relu = nn.ReLU(inplace=True)
        # NO maxpool — 96x96 -> 96x96 after conv1
        
        self.layer1 = self._make_layer(block, base_width, layers[0], stride=1)
        self.layer2 = self._make_layer(block, base_width * 2, layers[1], stride=2)  # 48x48
        self.layer3 = self._make_layer(block, base_width * 4, layers[2], stride=2)  # 24x24
        self.layer4 = self._make_layer(block, base_width * 8, layers[3], stride=2)  # 12x12
        
        # Final feature dim
        self.out_channels = base_width * 8 * block.expansion  # 512 for ResNet18
        
        # Weight initialization
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
    
    def _make_layer(self, block, planes: int, blocks: int, stride: int) -> nn.Sequential:
        downsample = None
        if stride != 1 or self.in_planes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.in_planes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = [block(self.in_planes, planes, stride, downsample)]
        self.in_planes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.in_planes, planes))
        return nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        
        return x  # (B, 512, H/8, W/8) e.g., (B, 512, 12, 12) for 96x96 input


def resnet18_backbone(in_channels: int = 1) -> ResNetBackbone:
    return ResNetBackbone(BasicBlock, [2, 2, 2, 2], in_channels=in_channels)
