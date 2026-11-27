"""GPU IN AFFITTO (27 nov 2026, Giorgio: "e' quello il futuro, video tipo film a costo basso").
Invece di pagare fal a secondo di video, si affitta una GPU su Modal a secondo di calcolo e si fanno girare noi i modelli aperti:
  - immagini: FLUX.1 schnell (4 passaggi, ~1-2 s l'una su H100)
  - clip animate dall'immagine: LTX-Video 0.9.7 distilled (pochi passaggi, ~10-20 s per 5 s di video 720p su H100, stima da verificare)
Modal: Starter gratuito con 30 $ di calcolo al mese inclusi; H100 ~0,0011 $/s, L40S ~0,00054 $/s.
Segreti GitHub che Giorgio crea lui: MODAL_TOKEN_ID, MODAL_TOKEN_SECRET (da modal.com > Settings > API Tokens).
Uso dal workflow gpu_prova.yml:  modal run strumenti/gpu/modal_video.py --scene '<json>' --uscita libreria_clip/<nome>
NON ancora provato: si prova al primo giro con i token (il workflow stampa tempi e costo stimato di ogni clip)."""
import io, json, os, time

import modal

GPU = os.environ.get('GPU_MODAL', 'H100')
img = (modal.Image.debian_slim(python_version='3.11')
       .apt_install('ffmpeg', 'git')
       .pip_install('torch==2.5.1', 'diffusers>=0.34.0', 'transformers>=4.47', 'accelerate', 'sentencepiece', 'imageio[ffmpeg]', 'pillow',
                    'huggingface_hub[hf_transfer]', 'protobuf')
       .env({'HF_HUB_ENABLE_HF_TRANSFER': '1', 'HF_HOME': '/cache'}))
app = modal.App('ambience-video', image=img)
cache = modal.Volume.from_name('ambience-modelli', create_if_missing=True)   # i modelli si scaricano una volta sola


@app.function(volumes={'/cache': cache}, timeout=3600, cpu=4)
def scarica():
    """scarica i modelli nel volume SENZA GPU (costa pochissimo), cosi' la GPU si paga solo per lavorare"""
    from huggingface_hub import snapshot_download
    t = time.time()
    for r in ('Lightricks/LTX-Video-0.9.7-distilled',):   # 27 nov: FLUX.1 schnell e' a registrazione (gated): le immagini le fa fal (~0,02 $), qui solo l'animazione
        snapshot_download(r, cache_dir='/cache/hub', allow_patterns=['model_index.json', '*/*.json', '*/*.safetensors', '*/*.model', '*/*.txt'])   # solo le cartelle diffusers (i file grandi in radice sono altre versioni: 30+ GB inutili)
        print('scaricato', r, round(time.time() - t), 's', flush=True)
    cache.commit()


@app.cls(gpu=GPU, volumes={'/cache': cache}, timeout=3600, scaledown_window=120)
class Studio:
    @modal.enter()
    def carica(self):
        import torch
        from diffusers import LTXConditionPipeline
        t = time.time()
        self.ltx = LTXConditionPipeline.from_pretrained('Lightricks/LTX-Video-0.9.7-distilled', torch_dtype=torch.bfloat16).to('cuda')
        self.ltx.vae.enable_tiling()
        cache.commit()
        print('modelli caricati in', round(time.time() - t), 's', flush=True)

    @modal.method()
    def scena(self, png, prompt, movimento, secondi=5.0, w=1280, h=704, seed=7):
        """anima un'immagine gia' fatta; ritorna (mp4, tempi)"""
        import torch
        from PIL import Image
        from diffusers.utils import export_to_video
        from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
        g = torch.Generator('cuda').manual_seed(seed)
        im = Image.open(io.BytesIO(png)).convert('RGB').resize((w, h))
        t1 = time.time()
        n = int(secondi * 24) // 8 * 8 + 1   # LTX vuole 8k+1 fotogrammi
        fr = self.ltx(conditions=[LTXVideoCondition(image=im, frame_index=0)], prompt=movimento + '. ' + prompt,
                      negative_prompt='worst quality, inconsistent motion, blurry, jittery, distorted, text, watermark',
                      width=w, height=h, num_frames=n, timesteps=[1000, 993, 987, 981, 975, 909, 725, 0.03], decode_timestep=0.05,
                      decode_noise_scale=0.025, image_cond_noise_scale=0.0, guidance_scale=1.0, guidance_rescale=0.7, generator=g,
                      output_type='pil').frames[0]
        t2 = time.time()
        p = '/tmp/c.mp4'; export_to_video(fr, p, fps=24)
        return open(p, 'rb').read(), {'immagine_s': 0.0, 'clip_s': round(t2 - t1, 1)}


@app.local_entrypoint()
def main(scene: str, uscita: str, stile: str = ''):
    os.makedirs(uscita, exist_ok=True)
    sc = json.loads(scene)
    scarica.remote()
    s_ = Studio()
    prezzo = {'H100': 0.001097, 'A100-80GB': 0.000694, 'L40S': 0.000542}.get(GPU, 0.0011)
    tot = 0.0; righe = []
    for x in sc:
        t = time.time()
        png = open(x['immagine'], 'rb').read()   # immagine gia' fatta (fal) nella libreria
        mp4, tempi = s_.scena.remote(png, (stile + ' ' + x['prompt']).strip(), x.get('movimento') or '', float(x.get('secondi') or 5))
        open(os.path.join(uscita, f"grezzo_{x['id']}.mp4"), 'wb').write(mp4)
        gpu_s = tempi['immagine_s'] + tempi['clip_s']; costo = gpu_s * prezzo; tot += costo
        righe.append(dict(x, **tempi, costo_dollari=round(costo, 4), totale_s=round(time.time() - t, 1)))
        print(x['id'], tempi, f'~{costo:.4f} $', flush=True)
    json.dump({'gpu': GPU, 'scene': righe, 'totale_dollari_gpu': round(tot, 3),
               'nota': 'tempo GPU di calcolo; il primo avvio (download modelli) si paga una volta'}, open(os.path.join(uscita, 'tempi_gpu.json'), 'w'), indent=1)
    print('TOTALE GPU stimato', round(tot, 3), '$ per', len(sc), 'clip')
