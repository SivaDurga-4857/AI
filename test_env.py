from dotenv import load_dotenv
import os
print(load_dotenv(dotenv_path=".env"))
print(os.getenv("GEMINI_API_KEY"))