Terminal 1
redis-server --bind 127.0.0.1 --port 6379

terminal 2
celery -A app.celery_app worker --loglevel=info --pool=solo

terminal 3
uvicorn app.main:app --reload