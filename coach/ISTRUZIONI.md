# COACH AUTOMATICO DEI CANALI — istruzioni per Claude (attività programmata ogni 3 giorni)

Obiettivo di Giorgio: lui sceglie SOLO quali canali aprire e i parametri da rispettare; il coach migliora i canali da solo
finché i parametri sono rispettati, senza buttare il lavoro fatto. Rispondi e scrivi sempre in ITALIANO.

## Regole fisse (decise con Giorgio il 30 ott 2026)
- Vale solo per i canali con `coach_auto = SI` in Channel Configs.
- Parametri (colonne di Channel Configs, default tra parentesi): `coach_obiettivo_ctr` (3,5), `coach_obiettivo_ret30` (65),
  `coach_obiettivo_ret60` (50), `coach_finestra_video` (3), `coach_min_impression` (1000), `coach_budget_video`
  (costo massimo per video in $ ≈ €, voce ElevenLabs esclusa perche' e' un abbonamento).
- ATTENZIONE: la colonna `budget_video` (senza coach_) e' un'impostazione del motore video_storia (euro di disegni: 0 = solo Pexels,
  NO = senza tetto): e' una LEVA che il coach puo' cambiare nella ricetta, non il budget del coach.
- Il costo reale di ogni video lo scrivono i workflow in `coach/costi/<slug>.tsv` (prove escluse dal calcolo).
- La DURATA la decide Giorgio nel foglio (`durata_min_minuti`, `durata_max_minuti`): il coach non la cambia mai.
- Il calcolo lo fa `coach/coach_calcola.py` (gratis). Ordine fisso delle leve: COSTO (se il costo medio degli ultimi video supera
  coach_budget_video) -> CTR -> retention 30 s -> retention 60 s.
- UNA modifica alla volta per canale e per controllo. Ogni modifica = nuova VERSIONE nella ricetta del canale
  (`coach/canali/<slug>/ricetta.json`): numero, data `dal`, cosa, leva, parametri, risultati, decisione.
- I parametri della versione attiva valgono SOPRA la riga di Channel Configs (li legge il motore). Il foglio non si tocca.
- Mai superare `coach_budget_video`. Preferire SEMPRE le modifiche a costo zero: meno costa un video, più canali si aprono.
- Restare SEMPRE nello stile del competitor del canale (campo `stile_base` della ricetta) e nel suo tratto distintivo:
  si cambiano dettagli dentro quello stile, mai lo stile intero.
- Titolo: resta copiato/tradotto dal competitor (regola di Giorgio). Durata: sempre tra durata_min_minuti e durata_max_minuti.
- Per scrivere su Channel Configs si usa SOLO il workflow "Modifica Channel Configs (con lucchetti)" (coach/foglio_configs.py).
  LUCCHETTI di Giorgio, mai da aggirare: la riga KAO PSICOLOGIA non si tocca; le colonne videos_per_day (canale acceso/spento)
  e publish_schedule_days non si toccano; i suoi parametri (coach_*, durata_min_minuti, durata_max_minuti) non si cambiano.
  Le modifiche del coach restano nella ricetta: sul foglio si scrive solo se Giorgio lo chiede.
- Mai cambiare un canale STABILE se i parametri tengono. Se scende sotto: tornare alla versione `migliore`.
- Non lanciare video veri: li lancia l'orchestratore. Le prove brevi (circa 1 minuto) sono permesse.
- Non toccare canali senza `coach_auto = SI`, non cambiare impostazioni di n8n, non spendere fuori da `budget_video`.

## Passi a ogni controllo
1. `cd` nel repository ambience (gggweb23-gif/ambience), `git pull`.
2. Scarica Channel Configs (Google Drive, id `1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0`) come xlsx
   (download_file_content con exportMimeType `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
   decodifica base64 in un file). Elenca i canali con `coach_auto = SI`.
3. Per ogni canale: scarica come xlsx il suo file di produzione (colonna `scout_production_sheet_id`) e lancia
   `python3 coach/coach_calcola.py <configs.xlsx> <produzione.xlsx> "<channel_id>"`.
4. Decidi in base a `stato`:
   - `ATTESA` (meno di N video con 72 ore nella versione attiva): non cambiare nulla.
   - `OK`: scrivi i risultati nella versione attiva. Se anche il controllo precedente era OK -> `stato` = `stabile`,
     `migliore` = versione attiva. Nessuna modifica.
   - `LEVA_COSTO`: riporta il costo sotto `coach_budget_video` restando nello stile (es. meno disegni e piu' riuso di ogni
     disegno, misto Pexels, modelli piu' economici per i controlli). Prima una prova breve, poi la nuova versione.
   - `LEVA_CTR` / `LEVA_RET30` / `LEVA_RET60`:
     a. Scrivi i risultati nella versione attiva e confrontali con la versione `migliore` (se esiste).
        Se la versione attiva è PEGGIORE della migliore sulla stessa leva -> torna alla migliore (nuova versione con i suoi parametri).
     b. Altrimenti crea la versione successiva cambiando UNA sola cosa della leva indicata (catalogo sotto),
        scegliendo la modifica più probabile guardando i dati (video migliori del canale vs peggiori, copertine del competitor).
     c. Se la modifica è visiva, fai prima una prova breve (es. workflow "Prova breve motore statua + karaoke") e guarda il risultato.
     d. Aggiorna `ricetta.json` (`versione_attiva`, nuova voce in `versioni`, una riga in `registro`), commit e push.
5. Manda a Giorgio un messaggio BREVE (notifica): per ogni canale stato, misure (CTR, ret 30 s, ret 60 s sui video della finestra),
   cosa hai cambiato e perché, spesa delle prove. Niente altro.

## Catalogo delle leve (parametri che il motore legge già)
I nomi nei `parametri` della ricetta devono essere quelli che il MOTORE legge dal payload (controlla nel codice: per esempio
video_storia.py legge `voce`, `max_minuti`... oltre ai nomi delle colonne). Motore di ogni canale: colonna `render_workflow` /
`github_workflow` (video_storia.yml -> video_storia.py, video_mappe.yml -> video_mappe.py, video_produzione.yml -> motore/motore.js).

Motore video_storia.py (Faces of Rome = channel_id Roma Senza Filtri, Storia in Minuti): `budget_video` (euro di disegni;
0 = solo Pexels), `quota_cartoni` (% cartone), `ritmo` (secondi per immagine nei primi 10 s / 10-30 s / dopo), `secondi_per_immagine`,
`sfondi_max`, `max_spesa_immagini`, `copertina_stile` (foto, primo_piano...), `copertina_copia`, `cornice`, `linea_tempo`, musica.
Motore video_mappe.py (Rich Borders = channel_id Main Street Atlas): `copertina_stile`, `tema_colori`, `font_titoli`, `font_testi`,
`angoli_tondi`, `voce_stabilita`, `voce_stile`, `voice_speed`, `musica_cartella`, `musica_ritmo`.

Motore "github" (Agora of Sages: motore.js + copertina_statua.py + render_filosofo.py):
- CTR (copertina): `copertina_istruzioni` (testo libero per il piano della copertina: formula delle scritte, es. "comando
  di 2 parole + verdetto", "usa sempre YOU"), `statua_scena` (sola | antagonisti), `statua_gesti` (indici ammessi 0-7,
  vedi GESTI in copertina_statua.py), `statua_aspetto` (descrizione in inglese di capelli/barba), `copertina_regola` (SI/NO),
  `thumbnail_firma_testo`. Il verde #39FF14 è il tratto distintivo: non si cambia.
- Retention 30 s (gancio): `narrative_angle` (istruzioni al copione sull'apertura: andare subito al punto, promessa forte,
  domanda diretta allo spettatore), `language_register`.
- Retention 60 s e oltre (ritmo/video): `render_style` (JSON: `dimensione_testo`, `caratteri_riga`, `righe_max`, `effetto`
  cenere|nessuno), `musica_volume`, `voice_id` (solo voci già approvate da Giorgio: David `ppLqTilh7rH7fbUVlXsf`).
Se una leva necessaria NON esiste nel motore, puoi aggiungerla nel codice SOLO se è parametrica (colonna o chiave della ricetta),
non cambia nulla per gli altri canali, e la provi con una prova breve prima del push. Altrimenti scrivila nel messaggio come proposta.
