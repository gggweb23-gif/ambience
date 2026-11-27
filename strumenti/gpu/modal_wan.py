"""GPU IN AFFITTO - motore WAN 2.2 (27 nov 2026). LTX su Modal costava poco ma quasi non animava (scartato):
qui Wan 2.2 image-to-video A14B (lo stesso modello che su fal si muove bene) in 720p, con le LoRA Lightning a 4 passaggi
(veloce: pochi secondi di GPU per clip invece di minuti). Immagini di partenza: gia' fatte (fal), passate come file.
Uso: modal run strumenti/gpu/modal_wan.py --scene '<json con immagine>' --uscita libreria_clip/<nome>"""
import io, json, os, time

import modal

GPU = os.environ.get('GPU_MODAL', 'H100')
REPO = 'Wan-AI/Wan2.2-I2V-A14B-Diffusers'
LORA = 'lightx2v/Wan2.2-Distill-Loras'   # 27 nov: i nomi dei file cambiano con le versioni: si scelgono leggendo l'elenco del repository


def lora_file(tipo):
    from huggingface_hub import HfApi
    fs = sorted(f for f in HfApi().list_repo_files(LORA) if f.endswith('.safetensors') and 'i2v' in f.lower()
                and f'{tipo}_noise' in f.lower() and '4step' in f.lower())
    if not fs:
        raise RuntimeError('LoRA ' + tipo + ' non trovata in ' + LORA)
    return fs[-1]
img = (modal.Image.debian_slim(python_version='3.11')
       .apt_install('ffmpeg', 'git')
       .pip_install('torch==2.7.1', 'diffusers>=0.35.1', 'transformers>=4.51', 'accelerate', 'peft', 'sentencepiece', 'ftfy',
                    'imageio[ffmpeg]', 'pillow', 'huggingface_hub[hf_transfer]', 'protobuf')
       .env({'HF_HUB_ENABLE_HF_TRANSFER': '1', 'HF_HOME': '/cache'}))
app = modal.App('ambience-wan', image=img)
cache = modal.Volume.from_name('ambience-modelli', create_if_missing=True)


@app.function(volumes={'/cache': cache}, timeout=3600, cpu=8, memory=16384)
def scarica():
    """modelli nel volume senza GPU (costa pochissimo), una volta sola"""
    from huggingface_hub import hf_hub_download, snapshot_download
    t = time.time()
    snapshot_download(REPO, cache_dir='/cache/hub', allow_patterns=['model_index.json', '*/*.json', '*/*.safetensors', '*/*.model', '*/*.txt', '*/spiece*', '*/tokenizer*'])
    print('scaricato', REPO, round(time.time() - t), 's', flush=True)
    for tipo in ('high', 'low'):
        w = lora_file(tipo); hf_hub_download(LORA, w, cache_dir='/cache/hub'); print('LoRA', w, flush=True)
    print('scaricate LoRA', round(time.time() - t), 's', flush=True)
    cache.commit()


@app.cls(gpu=GPU, volumes={'/cache': cache}, timeout=1800, scaledown_window=60, max_containers=1, retries=0, memory=98304)
class Studio:
    @modal.enter()
    def carica(self):
        import torch
        from diffusers import WanImageToVideoPipeline
        t = time.time()
        p = WanImageToVideoPipeline.from_pretrained(REPO, torch_dtype=torch.bfloat16, cache_dir='/cache/hub')
        p.load_lora_weights(LORA, weight_name=lora_file('high'), adapter_name='lightning', cache_dir='/cache/hub')
        p.load_lora_weights(LORA, weight_name=lora_file('low'), adapter_name='lightning_2', load_into_transformer_2=True, cache_dir='/cache/hub')
        p.set_adapters(['lightning', 'lightning_2'], adapter_weights=[1.0, 1.0])
        p.enable_model_cpu_offload()   # 2 trasformatori da 14B + testo: si alternano sulla GPU (80 GB)
        self.p = p
        print('modelli caricati in', round(time.time() - t), 's', flush=True)

    @modal.method()
    def scena(self, png, prompt, movimento, secondi=5.0, w=1280, h=720, seed=7):
        import torch
        from PIL import Image
        from diffusers.utils import export_to_video
        im = Image.open(io.BytesIO(png)).convert('RGB').resize((w, h))
        n = int(secondi * 16) // 4 * 4 + 1   # Wan: 16 fotogrammi al secondo, 4k+1 fotogrammi
        t1 = time.time()
        fr = self.p(image=im, prompt=movimento + '. ' + prompt, height=h, width=w, num_frames=n, num_inference_steps=4,
                    guidance_scale=1.0, guidance_scale_2=1.0, generator=torch.Generator('cuda').manual_seed(seed),
                    negative_prompt='static, still image, frozen, blurry, low quality, deformed, text, watermark').frames[0]
        t2 = time.time()
        p_ = '/tmp/c.mp4'; export_to_video(fr, p_, fps=16)
        return open(p_, 'rb').read(), {'immagine_s': 0.0, 'clip_s': round(t2 - t1, 1)}


@app.local_entrypoint()
def main(scene: str, uscita: str, stile: str = ''):
    os.makedirs(uscita, exist_ok=True)
    sc = json.loads(scene)
    scarica.remote()
    s_ = Studio()
    prezzo = {'H100': 0.001097, 'A100-80GB': 0.000694, 'L40S': 0.000542}.get(GPU, 0.0011)
    tot = 0.0; righe = []
    for x in sc:
        png = open(x['immagine'], 'rb').read()
        mp4, tempi = s_.scena.remote(png, (stile + ' ' + x['prompt']).strip(), x.get('movimento') or '', float(x.get('secondi') or 5))
        open(os.path.join(uscita, f"wan_{x['id']}.mp4"), 'wb').write(mp4)
        costo = tempi['clip_s'] * prezzo; tot += costo
        righe.append(dict(x, **tempi, costo_dollari=round(costo, 4)))
        print(x['id'], tempi, f'~{costo:.4f} $', flush=True)
    json.dump({'gpu': GPU, 'motore': 'wan2.2-i2v-a14b + lightning 4 passi', 'scene': righe, 'totale_dollari_gpu': round(tot, 3)},
              open(os.path.join(uscita, 'tempi_gpu_wan.json'), 'w'), indent=1)
    print('TOTALE GPU stimato', round(tot, 3), '$ per', len(sc), 'clip')
