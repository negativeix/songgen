import os
from dotenv import load_dotenv

load_dotenv()

print("GOOGLE_CLIENT_ID:", os.environ.get('GOOGLE_CLIENT_ID'))
print("GOOGLE_CLIENT_SECRET:", os.environ.get('GOOGLE_CLIENT_SECRET'))