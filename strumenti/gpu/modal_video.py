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


@app.cls(gpu=GPU, volumes={'/cache': cache}, timeout=3600, scaledown_window=120)
class Studio:
    @modal.enter()
    def carica(self):
        import torch
        from diffusers import FluxPipeline, LTXConditionPipeline
        t = time.time()
        self.flux = FluxPipeline.from_pretrained('black-forest-labs/FLUX.1-schnell', torch_dtype=torch.bfloat16).to('cuda')
        self.ltx = LTXConditionPipeline.from_pretrained('Lightricks/LTX-Video-0.9.7-distilled', torch_dtype=torch.bfloat16).to('cuda')
        self.ltx.vae.enable_tiling()
        cache.commit()
        print('modelli caricati in', round(time.time() - t), 's', flush=True)

    @modal.method()
    def scena(self, prompt, movimento, secondi=5.0, w=1280, h=720, seed=7):
        """un'immagine e la sua clip animata; ritorna (png, mp4, tempi)"""
        import torch
        from diffusers.utils import export_to_video
        g = torch.Generator('cuda').manual_seed(seed)
        t0 = time.time()
        im = self.flux(prompt, width=1344, height=768, num_inference_steps=4, guidance_scale=0.0, generator=g).images[0].resize((w, h))
        t1 = time.time()
        n = int(secondi * 24) // 8 * 8 + 1   # LTX vuole 8k+1 fotogrammi
        fr = self.ltx(image=im, prompt=movimento + '. ' + prompt, negative_prompt='worst quality, inconsistent motion, blurry, jittery, distorted',
                      width=w, height=h, num_frames=n, timesteps=[1000, 993, 987, 981, 975, 909, 725, 0.03], decode_timestep=0.05,
                      decode_noise_scale=0.025, image_cond_noise_scale=0.0, guidance_scale=1.0, guidance_rescale=0.7, generator=g,
                      output_type='pil').frames[0]
        t2 = time.time()
        p = '/tmp/c.mp4'; export_to_video(fr, p, fps=24)
        b = io.BytesIO(); im.save(b, 'PNG')
        return b.getvalue(), open(p, 'rb').read(), {'immagine_s': round(t1 - t0, 1), 'clip_s': round(t2 - t1, 1)}


@app.local_entrypoint()
def main(scene: str, uscita: str, stile: str = ''):
    os.makedirs(uscita, exist_ok=True)
    sc = json.loads(scene); s_ = Studio()
    prezzo = {'H100': 0.001097, 'A100-80GB': 0.000694, 'L40S': 0.000542}.get(GPU, 0.0011)
    tot = 0.0; righe = []
    for x in sc:
        t = time.time()
        png, mp4, tempi = s_.scena.remote((stile + ' ' + x['prompt']).strip(), x.get('movimento') or '', float(x.get('secondi') or 5))
        open(os.path.join(uscita, f"immagine_{x['id']}.png"), 'wb').write(png)
        open(os.path.join(uscita, f"grezzo_{x['id']}.mp4"), 'wb').write(mp4)
        gpu_s = tempi['immagine_s'] + tempi['clip_s']; costo = gpu_s * prezzo; tot += costo
        righe.append(dict(x, **tempi, costo_dollari=round(costo, 4), totale_s=round(time.time() - t, 1)))
        print(x['id'], tempi, f'~{costo:.4f} $', flush=True)
    json.dump({'gpu': GPU, 'scene': righe, 'totale_dollari_gpu': round(tot, 3),
               'nota': 'tempo GPU di calcolo; il primo avvio (download modelli) si paga una volta'}, open(os.path.join(uscita, 'tempi_gpu.json'), 'w'), indent=1)
    print('TOTALE GPU stimato', round(tot, 3), '$ per', len(sc), 'clip')
