# HackerNews Agent

Un sistema automatizzato che recupera, riassume e traduce in italiano le principali notizie da Hacker News utilizzando Claude AI. L'agente genera un digest giornaliero di notizie tech, alimentato dal modello Claude-3 Sonnet di Anthropic.

## Panoramica

HackerNews Agent è una pipeline Python che:

1. Recupera le notizie più rilevanti dalle API di Hacker News nelle ultime 24 ore
2. Genera riassunti coinvolgenti utilizzando l'AI
3. Traduce i contenuti in italiano
4. Salva il risultato in un file Markdown formattato

## Architettura del Sistema

Il sistema è strutturato in tre componenti principali che operano in sequenza:

1. **Raccolta Dati**
   - Utilizza le API ufficiali di Hacker News per recuperare le ultime notizie
   - Filtra le storie in base a età e punteggio
   - Implementa gestione degli errori e rate limiting

2. **Elaborazione e Organizzazione**
   - Un primo modello LLM analizza e organizza le notizie
   - Genera riassunti coinvolgenti mantenendo il contesto originale
   - Applica formattazione consistente

3. **Traduzione**
   - Un secondo modello LLM traduce i contenuti in italiano
   - Mantiene la terminologia tecnica appropriata
   - Preserva la struttura del documento

## Caratteristiche

- Recupero automatico delle migliori storie da HackerNews
- Filtraggio intelligente basato su età e punteggio
- Riassunti AI-powered che mantengono il contesto originale
- Traduzione professionale in italiano
- Output in Markdown con formattazione consistente
- Gestione errori e logging robusto
- Protezione rate limiting per le chiamate API

## Requisiti

```
python >= 3.7
anthropic
python-dotenv
requests
```

## Installazione

1. Clona questa repository
2. Installa le dipendenze:
```bash
pip install anthropic python-dotenv requests
```
3. Crea un file .env nella root del progetto con la tua chiave API Anthropic:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Utilizzo

Esegui lo script:

```bash
python hackernews-agent_2.py
```

Lo script:
- Recupera fino a 10 notizie principali delle ultime 24 ore
- Genera riassunti utilizzando Claude-3 Sonnet
- Traduce i contenuti in italiano
- Salva i risultati in `hackernews_daily_YYYY-MM-DD.md`

## Configurazione

Parametri principali nello script:

- `hours`: Finestra temporale per il recupero notizie (default: 24)
- `limit`: Numero massimo di notizie da processare (default: 10)
- `MODEL`: Versione del modello Claude utilizzata (default: claude-3-7-sonnet-20250219)
- `MAX_TOKENS`: Limite token per risposte AI (default: 4000)

## Formato Output

Il file Markdown generato segue questa struttura:

```markdown
# HackerNews Daily - [Data Corrente]

## [Titolo Tradotto]

[Riassunto in italiano della notizia]

(URL Originale)

---
```

## Logging

Lo script registra tutte le operazioni su:
- Output console
- File hackernews_agent.log

## Gestione Errori

Lo script include gestione completa degli errori per:
- Rate limit API con backoff esponenziale
- Problemi di connessione rete
- Risposte API non valide
- Operazioni su file system

## Licenza

MIT

## Contribuire

Pull request sono benvenute. Per modifiche maggiori, apri prima una issue per discutere i cambiamenti proposti.

## Ringraziamenti

- [HackerNews API](https://github.com/HackerNews/API)
- [Anthropic's Claude](https://www.anthropic.com/claude)
