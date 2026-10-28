# Motore di produzione (tutti i canali "stile PRODUCTION")

Un solo programma per tutti i canali che prima passavano dal PRODUCTION di n8n (oggi KAO PSICOLOGIA e Agora of Sages).
Lo lancia n8n ("MULTICHANNEL - GitHub Video") con il workflow `.github/workflows/video_produzione.yml`.

## Dove sta cosa
| Cosa | Dove |
|---|---|
| Programma | `motore/motore.js` |
| Logica e prompt del PRODUCTION (copiati 1:1 da n8n) | `motore/produzione.json` |
| Copertina "di sempre" (pagina HTML -> immagine) | `motore/html_png.py` |
| Copioni di riferimento di ogni canale | `esempi_copioni/<nome-canale>/*.txt` (es. `esempi_copioni/kao-psicologia`) |
| Workflow GitHub (uno per tutti) | `.github/workflows/video_produzione.yml` |
| Impostazioni di ogni canale | riga del canale in Channel Configs |

## Aggiungere un canale
1. Channel Configs, riga del canale: `github_workflow` = `video_produzione.yml`, `chiave_youtube` = nome del secret YouTube (es. `YT_REFRESH_TOKEN_NOMECANALE`), `render_engine` = `github_completo`.
2. GitHub, Settings > Secrets > Actions: il secret YouTube del canale con quel nome.
3. `esempi_copioni/<nome-canale>/`: i copioni di riferimento (.txt). Il nome della cartella e' il channel_id in minuscolo con i trattini
   (es. "Agora of Sages" -> `agora-of-sages`).

Nessun file di programma nuovo: il canale si distingue solo dalla sua riga in Channel Configs
(render_workflow sceglie il montaggio: kao_render.yml = formato KAO, filosofo.yml o vuoto = formato filosofo; copertina_github = SI usa copertine_cinema_kao.py).
