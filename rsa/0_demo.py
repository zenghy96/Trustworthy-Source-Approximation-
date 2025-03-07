import os
from diffusers import DDPMScheduler
import numpy as np
import torch
from torchvision import transforms as T
import sys
from dataclasses import dataclass
from tqdm import tqdm
from PIL import Image
sys.path.append('.')

# ## diffusion
from diffusion.controlnet.models.UNet2DModel import UNet2DModel
from diffusion.controlnet.models.controlnet import ControlNetModel
from diffusion.controlnet.models.pipeline_controlnet import DDPMControlNetPipeline
from dataset.condition_dataset import ConditionGenerator
from utils import *


@dataclass
class Config:
    data_dir = 'data/VS/T2'
    split = 'demo'
    output_dir = 'outputs/demo'
    unet_ckpt_dir = 'checkpoints/vs_ddpm'
    controlnet_ckpt_dir = 'checkpoints/vs_controlnet'

    r0, r1, n = 30, 80, 3
    r_steps = np.linspace(float(r0), float(r1), int(n))
    run_num = 3
    num_inference_steps = 50
    seed = 0
    device = 1


if __name__ == "__main__":
    # torch.set_num_threads(1)
    config = Config()
    os.makedirs(config.output_dir, exist_ok=True)
    device = torch.device(f"cuda:{config.device}")
    set_seed(config.seed)
    
    # diffusion model
    noise_scheduler = DDPMScheduler.from_pretrained(config.unet_ckpt_dir, subfolder='scheduler')
    unet = UNet2DModel.from_pretrained(config.unet_ckpt_dir, subfolder='unet')
    controlnet = ControlNetModel.from_pretrained(config.controlnet_ckpt_dir, subfolder='controlnet')
    unet.to(device)
    controlnet.to(device)
    pipeline = DDPMControlNetPipeline(
        contronet=controlnet,
        unet=unet,
        scheduler=noise_scheduler,
        use_bar=False
    )

    # data
    r_steps = config.r_steps
    print(f'steps: {r_steps}')
    n_steps = len(r_steps)
    condition_generator = ConditionGenerator(
        data_dir=config.data_dir,
        split=config.split,
        resolution=unet.sample_size,
        r_steps=r_steps,
        run_num=config.run_num,
    )

    # sample
    for image, conditions, img_id, mask_true in tqdm(condition_generator):
        conditions = conditions.to(device)
        samples = pipeline(
            conditions,
            num_inference_steps=config.num_inference_steps,
            generator=torch.manual_seed(0),
            output_type='pil',
        )[0]
        
        # save to show
        image = (image * 255).round().astype("uint8")
        image = Image.fromarray(image, mode="L")
        image.save(f'{config.output_dir}/{img_id}.png')
        mask_true = (mask_true * 255).round().astype("uint8")
        mask_true = Image.fromarray(mask_true, mode="L")
        mask_true.save(f'{config.output_dir}/{img_id}_mask_true.png')

        for i in range(n_steps):
            cond = conditions[i*config.run_num].cpu().numpy()
            cond = (cond * 255).round().astype("uint8")
            cond = Image.fromarray(cond.squeeze(), mode="L")
            cond.save(f'{config.output_dir}/{img_id}_cond_{i}.png')
            for j in range(config.run_num):
                sample = samples[i*config.run_num+j]
                sample.save(f'{config.output_dir}/{img_id}_sample_{i}_{j}.png')

    
