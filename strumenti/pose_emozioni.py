#!/usr/bin/env python3
"""23 nov (Giorgio, copertine notizie): il volto del personaggio noto e' il gancio: grande, intero e con un'EMOZIONE CHIARA
in linea con la notizia, senza cadere nella caricatura. Crea una volta sola le pose-emozione dei personaggi piu' usati
(0,08 $ l'una, poi restano in caricature/<chi>/<emozione>.png e si riusano gratis). Approvato da Giorgio (circa 1 $ una tantum).
Env: CHI (es. "putin,trump,zelensky"; vuoto = tutti), FAL_KEY, ANTHROPIC_API_KEY"""
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATURALE = ('Emotion clearly readable at thumbnail size but natural and believable, a real expression of this person, NOT exaggerated, '
            'not grotesque, not a meme face. Standing, arms relaxed or one natural gesture. ')
EMOZIONI = {
    'putin': {'teso': 'tense and worried: brows drawn together, lips pressed, eyes narrowed with concern',
              'arrabbiato': 'cold anger: furrowed brow, hard stare straight at the viewer, jaw clenched',
              'compiaciuto': 'smug and confident: a slight satisfied half smile, chin a little up'},
    'trump': {'compiaciuto': 'smug and pleased: confident satisfied grin, eyebrows slightly raised',
              'arrabbiato': 'angry: frowning, mouth tight, intense stare, pointing one finger forward',
              'preoccupato': 'worried and serious: frown, eyes looking aside with concern, mouth closed',
              'sorpreso': 'shocked: eyebrows raised high, eyes wide, mouth slightly open'},
    'zelensky': {'determinato': 'determined: firm serious look straight at the viewer, jaw set',
                 'preoccupato': 'worried: concerned frown, tired serious eyes',
                 'arrabbiato': 'angry and defiant: furrowed brow, intense stare'},
}
COMMONS = {'putin': 'File:Vladimir Putin in KGB uniform.jpg', 'trump': 'File:Donald Trump official portrait.jpg', 'zelensky': 'File:Volodymyr Zelenskyy in 2022.jpg'}
CHI = {'putin': 'Vladimir Putin, President of Russia, in a dark suit', 'trump': 'Donald Trump, President of the United States, in a dark suit and red tie',
       'zelensky': 'Volodymyr Zelensky, President of Ukraine, in his olive-green military-style shirt'}
scelti = [x.strip() for x in (os.environ.get('CHI') or '').split(',') if x.strip()] or list(EMOZIONI)
N = {'nome': 'pose_emozioni', 'budget_dollari': 0.09 * sum(len(EMOZIONI[c]) for c in scelti) + 0.2,
     'personaggi': {c: {'chi': CHI[c], 'commons': COMMONS[c], 'pose': {e: NATURALE + d for e, d in EMOZIONI[c].items()}} for c in scelti}}
f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False); json.dump(N, f); f.close()
os.environ['NOTIZIA'] = f.name
sys.path.insert(0, ROOT)
import video_notizie as V
for c in scelti:
    for e in EMOZIONI[c]:
        print(c, e, '->', V.posa(c, e), flush=True)
