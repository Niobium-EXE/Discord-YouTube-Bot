import os
from dotenv import load_dotenv

# Load .env when running locally.
# Railway will supply environment variables directly.
load_dotenv()

# ---------------------------------------------------------
# Discord
# ---------------------------------------------------------
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
BOT_STATUS = os.getenv("BOT_STATUS", "Watching YouTube")

# ---------------------------------------------------------
# YouTube
# ---------------------------------------------------------
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# ---------------------------------------------------------
# Internal API
# ---------------------------------------------------------
API_SECRET = os.getenv("API_SECRET", "")

# ---------------------------------------------------------
# Storage
# ---------------------------------------------------------
LOCAL_DATA_DIR = os.getenv("LOCAL_DATA_DIR", "data")

# These support both our custom names and common
# Railway/AWS-style variable names.

S3_ENDPOINT = (os.getenv("S3_ENDPOINT") or os.getenv("ENDPOINT") or os.getenv("AWS_ENDPOINT_URL"))
S3_ACCESS_KEY = (os.getenv("S3_ACCESS_KEY") or os.getenv("ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"))
S3_SECRET_KEY = (os.getenv("S3_SECRET_KEY") or os.getenv("SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"))
S3_BUCKET = (os.getenv("S3_BUCKET") or os.getenv("BUCKET") or os.getenv("AWS_S3_BUCKET_NAME"))
S3_REGION = (os.getenv("S3_REGION") or os.getenv("REGION") or os.getenv("AWS_DEFAULT_REGION") or "auto")
S3_URL_STYLE = os.getenv("S3_URL_STYLE", "virtual")

def bucket_is_configured() -> bool:
    """
    Returns True when enough information exists
    to connect to the Railway bucket.
    """
    return all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET])