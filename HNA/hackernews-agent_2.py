import os
from dotenv import load_dotenv
import json
import requests
import time
from datetime import datetime, timedelta
import logging
from anthropic import Anthropic, RateLimitError, APIError

# Configurazione di logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hackernews_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HackerNewsAgent")

load_dotenv()  # Carica le variabili da .env

# Configurazione delle credenziali API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    logger.warning("API key non trovata come variabile d'ambiente.")
    exit(1)

# Inizializzazione del client Anthropic
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Configurazione dei modelli
MODEL = "claude-3-7-sonnet-20250219"  # Utilizziamo Sonnet per un buon equilibrio tra capacità e costo
MAX_TOKENS = 4000

class HackerNewsAPI:
    """Classe per interagire con l'API di Hacker News"""
    
    def __init__(self):
        self.top_stories_endpoint = "https://hacker-news.firebaseio.com/v0/topstories.json"
        self.new_stories_endpoint = "https://hacker-news.firebaseio.com/v0/newstories.json"
        self.item_endpoint = "https://hacker-news.firebaseio.com/v0/item/{}.json"
    
    def get_top_stories(self, limit=50):
        """Recupera gli ID delle top stories"""
        try:
            response = requests.get(self.top_stories_endpoint, timeout=10)
            response.raise_for_status()
            return response.json()[:limit]
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore nel recupero delle top stories: {str(e)}")
            return []
    
    def get_new_stories(self, limit=50):
        """Recupera gli ID delle nuove stories"""
        try:
            response = requests.get(self.new_stories_endpoint, timeout=10)
            response.raise_for_status()
            return response.json()[:limit]
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore nel recupero delle new stories: {str(e)}")
            return []
    
    def get_item_details(self, item_id):
        """Recupera i dettagli di un item specifico"""
        try:
            response = requests.get(self.item_endpoint.format(item_id), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore nel recupero dell'item {item_id}: {str(e)}")
            return None

class HackerNewsAgent:
    """Agente per recuperare, riassumere e tradurre notizie da Hacker News"""
    
    def __init__(self):
        self.api = HackerNewsAPI()
        self.stories = []
    
    def fetch_hackernews_stories(self, hours=24, limit=10):
        """
        Recupera le storie principali da HackerNews delle ultime ore specificate
        
        Args:
            hours (int): Numero di ore nel passato da cui recuperare le notizie
            limit (int): Numero massimo di notizie da recuperare
            
        Returns:
            str: Storie formattate per il prompt
        """
        logger.info(f"Recupero delle storie delle ultime {hours} ore (max {limit})...")
        
        # Ottiene gli ID delle top stories
        story_ids = self.api.get_top_stories(50)  # Prendiamo più storie per filtrare quelle recenti e rilevanti
        if not story_ids:
            logger.warning("Nessuna storia trovata")
            return "Nessuna storia trovata su Hacker News."
        
        cutoff_time = int((datetime.now() - timedelta(hours=hours)).timestamp())
        recent_stories = []
        
        for story_id in story_ids:
            story = self.api.get_item_details(story_id)
            
            # Verifica che sia una storia valida e recente
            if (story and 
                'type' in story and story['type'] == 'story' and
                'time' in story and story['time'] >= cutoff_time and
                'title' in story and 
                'dead' not in story and 'deleted' not in story):
                
                # Aggiungiamo un controllo per il punteggio, prioritizzando storie con maggior engagement
                if 'score' in story and story['score'] > 5:  # Filtriamo storie con punteggio molto basso
                    recent_stories.append(story)
            
            # Piccola pausa per non sovraccaricare l'API
            time.sleep(0.1)
            
            # Se abbiamo raggiunto il limite desiderato, usciamo dal ciclo
            if len(recent_stories) >= limit:
                break
        
        # Ordiniamo le storie per punteggio decrescente
        recent_stories.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Prendiamo solo le top N storie
        recent_stories = recent_stories[:limit]
        
        logger.info(f"Recuperate {len(recent_stories)} storie recenti")
        self.stories = recent_stories
        return self.format_stories_for_prompt()
    
    def format_stories_for_prompt(self):
        """Formatta le storie per l'utilizzo nei prompt di Claude"""
        if not self.stories:
            return "Nessuna storia disponibile."
        
        formatted_stories = []
        
        for idx, story in enumerate(self.stories, 1):
            # Estrai i dati rilevanti con controllo dell'esistenza delle chiavi
            title = story.get('title', 'No Title')
            url = story.get('url', '')
            # Se non c'è URL, usa il link diretto a HN
            if not url:
                url = f"https://news.ycombinator.com/item?id={story.get('id', '')}"
                
            score = story.get('score', 0)
            by = story.get('by', 'anonymous')
            timestamp = story.get('time', 0)
            
            # Converti il timestamp in data leggibile
            date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # Aggiungi i commenti se disponibili
            comments_count = story.get('descendants', 0)
            comments_url = f"https://news.ycombinator.com/item?id={story.get('id', '')}"
            
            # Aggiungiamo anche il testo della storia se disponibile
            text = story.get('text', '')
            
            # Formatta la storia
            formatted_story = f"""
            Articolo #{idx}:
            Titolo: {title}
            URL: {url}
            Punteggio: {score}
            Autore: {by}
            Data: {date}
            Commenti: {comments_count} ({comments_url})
            """
            
            # Aggiungi il testo solo se presente
            if text:
                formatted_story += f"Testo: {text}\n"
            
            formatted_stories.append(formatted_story)
        
        return "\n".join(formatted_stories)
    
    def _handle_rate_limit(self, func, *args, **kwargs):
        """Gestisce il rate limiting con retry"""
        max_retries = 3
        retry_delay = 5  # secondi
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit raggiunto, nuovo tentativo in {retry_delay} secondi...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Backoff esponenziale
                else:
                    logger.error(f"Rate limit persistente dopo {max_retries} tentativi.")
                    raise
            except APIError as e:
                logger.error(f"Errore API: {str(e)}")
                raise
    
    def summarize_stories(self):
        """
        Crea riassunti accattivanti delle storie recuperate utilizzando Claude
        
        Returns:
            str: Storie riassunte in modo accattivante
        """
        if not self.stories:
            logger.warning("Nessuna storia da riassumere")
            return "Nessuna storia da riassumere."
        
        logger.info("Creazione di riassunti accattivanti delle storie...")
        
        # Prepara i dati per il prompt
        formatted_stories = self.format_stories_for_prompt()
        
        # Crea il prompt per Claude
        system_prompt = """
        Sei un esperto di tecnologia e informatica con esperienza nella creazione di contenuti editoriali accattivanti.
        Il tuo compito è creare riassunti coinvolgenti delle principali notizie da Hacker News.
        
        Per ogni articolo:
        1. Crea un riassunto conciso ma informativo (2-4 frasi) che catturi l'essenza dell'articolo
        2. Usa un tono vivace e coinvolgente, come quello di un blogger tecnologico di alto livello
        3. Includi i dettagli più importanti e il motivo per cui questa notizia è rilevante
        4. Evita espressioni generiche come "un articolo interessante" - sii specifico sul valore della notizia
        5. Mantieni il titolo originale dell'articolo come intestazione
        6. Includi l'URL alla fine di ogni riassunto tra parentesi
        7. Non inventare informazioni o dettagli non presenti nel titolo
        
        Formatta l'output come segue per ogni notizia:
        
        ## [Titolo originale]
        
        [Riassunto accattivante di 2-4 frasi]
        
        ([URL])
        
        ---
        
        Non creare categorizzazioni o raggruppamenti - elenca semplicemente le notizie in ordine di rilevanza.
        """
        
        try:
            # Chiama Claude per riassumere le storie
            response = self._handle_rate_limit(
                client.messages.create,
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user", 
                        "content": f"Ecco le notizie da riassumere in modo accattivante:\n\n{formatted_stories}"
                    }
                ]
            )
            
            summarized_stories = ""
            for content in response.content:
                if content.type == "text":
                    summarized_stories += content.text
            
            logger.info("Storie riassunte con successo")
            return summarized_stories
            
        except Exception as e:
            logger.error(f"Errore durante la creazione dei riassunti: {str(e)}")
            return f"Errore durante la creazione dei riassunti: {str(e)}"
    
    def translate_to_italian(self, summarized_stories):
        """
        Traduce i riassunti delle storie in italiano utilizzando Claude
        
        Args:
            summarized_stories (str): Riassunti delle storie da tradurre
            
        Returns:
            str: Riassunti tradotti in italiano
        """
        if not summarized_stories or summarized_stories.startswith("Errore") or summarized_stories == "Nessuna storia da riassumere.":
            logger.warning("Nessun riassunto da tradurre")
            return "Nessun riassunto da tradurre."
        
        logger.info("Traduzione dei riassunti in italiano...")
        
        # Crea il prompt per Claude
        system_prompt = """
        Sei un traduttore esperto dall'inglese all'italiano, specializzato in tecnologia e informatica.
        Il tuo compito è tradurre i riassunti delle notizie di Hacker News in italiano, mantenendo lo stile accattivante e coinvolgente.
        
        Traduci:
        1. I titoli degli articoli
        2. I riassunti mantenendo il tono vivace e coinvolgente
        3. NON tradurre gli URL
        
        Mantieni la stessa struttura del formato:
        
        ## [Titolo tradotto in italiano]
        
        [Riassunto tradotto in italiano]
        
        ([URL originale])
        
        ---
        
        Usa un linguaggio naturale e fluido in italiano, adattando eventuali termini tecnici secondo le convenzioni italiane,
        ma mantieni i nomi propri, i nomi di aziende, prodotti e tecnologie nella loro forma originale quando appropriato.
        """
        
        try:
            # Chiama Claude per tradurre i riassunti
            response = self._handle_rate_limit(
                client.messages.create,
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user", 
                        "content": f"Traduci questi riassunti in italiano:\n\n{summarized_stories}"
                    }
                ]
            )
            
            translated_stories = ""
            for content in response.content:
                if content.type == "text":
                    translated_stories += content.text
            
            logger.info("Riassunti tradotti con successo")
            return translated_stories
            
        except Exception as e:
            logger.error(f"Errore durante la traduzione dei riassunti: {str(e)}")
            return f"Errore durante la traduzione dei riassunti: {str(e)}"
    
    def run_pipeline(self, hours=24, limit=10):
        """
        Esegue l'intero pipeline: recupera, riassume e traduce le storie
        
        Args:
            hours (int): Numero di ore nel passato da cui recuperare le notizie
            limit (int): Numero massimo di notizie da recuperare (max 10)
            
        Returns:
            dict: Risultati dell'intero processo con storie originali, riassunte e tradotte
        """
        # Limitiamo il numero massimo di storie a 10 come richiesto
        if limit > 10:
            limit = 10
            logger.info("Limite impostato a 10 storie come da specifica")
            
        logger.info(f"Avvio del pipeline HackerNews Agent con limite di {limit} storie delle ultime {hours} ore")
        
        # Fase 1: Recupero delle storie
        raw_stories = self.fetch_hackernews_stories(hours, limit)
        if raw_stories == "Nessuna storia trovata su Hacker News.":
            logger.warning("Pipeline terminato: nessuna storia trovata")
            return {
                "status": "completed_with_warnings",
                "message": "Nessuna storia trovata su Hacker News",
                "raw_stories": None,
                "summarized_stories": None,
                "translated_stories": None
            }
        
        # Fase 2: Creazione dei riassunti accattivanti
        summarized_stories = self.summarize_stories()
        if summarized_stories.startswith("Errore"):
            logger.error("Pipeline terminato con errori durante la creazione dei riassunti")
            return {
                "status": "error",
                "message": summarized_stories,
                "raw_stories": raw_stories,
                "summarized_stories": None,
                "translated_stories": None
            }
        
        # Fase 3: Traduzione dei riassunti
        translated_stories = self.translate_to_italian(summarized_stories)
        if translated_stories.startswith("Errore"):
            logger.error("Pipeline terminato con errori durante la traduzione")
            return {
                "status": "error",
                "message": translated_stories,
                "raw_stories": raw_stories,
                "summarized_stories": summarized_stories,
                "translated_stories": None
            }
        
        logger.info("Pipeline completato con successo")
        return {
            "status": "success",
            "message": "Pipeline completato con successo",
            "raw_stories": raw_stories,
            "summarized_stories": summarized_stories,
            "translated_stories": translated_stories
        }
        
    def save_to_file(self, translated_stories, filename=None):
        """
        Salva le storie tradotte su un file
        
        Args:
            translated_stories (str): Storie tradotte da salvare
            filename (str, optional): Nome del file. Se None, usa la data corrente
            
        Returns:
            str: Path del file salvato
        """
        if not filename:
            current_date = datetime.now().strftime("%Y-%m-%d")
            filename = f"hackernews_daily_{current_date}.md"
            
        logger.info(f"Salvataggio delle storie tradotte su {filename}")
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                # Aggiungi un'intestazione al file
                header = f"# HackerNews Daily - {datetime.now().strftime('%d %B %Y')}\n\n"
                f.write(header)
                f.write(translated_stories)
                
            logger.info(f"Storie salvate con successo su {filename}")
            return filename
        except Exception as e:
            logger.error(f"Errore durante il salvataggio del file: {str(e)}")
            return None


def main():
    """Funzione principale che esegue l'intero processo"""
    try:
        logger.info("Avvio di HackerNews Agent")
        
        # Parametri configurabili
        hours = 24  # Numero di ore nel passato
        limit = 10  # Numero massimo di storie (imposto a 10 come da richiesta)
        
        # Crea l'agente e esegui il pipeline
        agent = HackerNewsAgent()
        result = agent.run_pipeline(hours, limit)
        
        if result["status"] == "success":
            # Salva le storie tradotte su file
            filename = agent.save_to_file(result["translated_stories"])
            if filename:
                logger.info(f"Processo completato con successo. Risultati salvati in {filename}")
                print(f"Processo completato con successo. Risultati salvati in {filename}")
            else:
                logger.warning("Processo completato ma non è stato possibile salvare i risultati")
                print("Processo completato ma non è stato possibile salvare i risultati")
        else:
            logger.error(f"Processo terminato con stato: {result['status']}. Messaggio: {result['message']}")
            print(f"Errore: {result['message']}")
            
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione: {str(e)}")
        print(f"Errore durante l'esecuzione: {str(e)}")


if __name__ == "__main__":
    main()