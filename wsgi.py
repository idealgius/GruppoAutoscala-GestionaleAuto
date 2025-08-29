from app import app

# L'oggetto 'app' viene esportato per Gunicorn/Render
# Non serve il blocco if __name__ == "__main__"
# Gunicorn gestisce host e porta automaticamente tramite la variabile $PORT
