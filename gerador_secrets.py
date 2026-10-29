"""Gera o bloco TOML para colar em Settings > Secrets no Streamlit Cloud.
Uso local: python generate_secrets.py
Não commite a saída nem o .json.
"""
import json
from pathlib import Path

src = Path(__file__).parent / "financeiro-b0c58-firebase-adminsdk-fbsvc-04f0310bd8.json"
data = json.loads(src.read_text(encoding="utf-8"))

# Escapa para TOML em linha única: \n vira \\n, " vira \"
def esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

print("[firebase_service_account]")
for k in ["type", "project_id", "private_key_id", "private_key", "client_email",
          "client_id", "auth_uri", "token_uri",
          "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"]:
    print(f'{k} = "{esc(str(data.get(k, "")))}"')
