import os
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
BOT_STATUS = os.getenv("BOT_STATUS", "Watching YouTube")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
API_SECRET = os.getenv("API_SECRET", "")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "")