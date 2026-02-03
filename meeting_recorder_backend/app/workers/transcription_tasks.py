from app.celery_app import celery_app
from app.services.transcription import transcribe_audio
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="app.workers.transcription_tasks.transcribe_audio_task")
def transcribe_audio_task(self, processed_path: str):
    try:
        logger.info(f"Starting transcription for {processed_path}")
        transcript = transcribe_audio(processed_path)
        print("====transcription result===")
        print(transcript)

        logger.info(f"Transcription completed for {processed_path}")

        return {
            "status": "success",
            "transcript": transcript
            }
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'exc_message': str(e)}
        )
        raise