# MusicIA 2.0

Versão pronta para teste com ACE-Step.

## Teste mais simples
Abra `frontend/index.html` em um navegador moderno. O botão **Criar música** tenta conectar diretamente à API Gradio do Space `fffiloni/ACE-Step-API`.

## Modo servidor
Também existe o backend FastAPI em `backend/app.py`.

```bash
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

O ACE-Step 1.5 é um modelo open-source com suporte a geração de música e API/Gradio. O Space público pode ficar ocupado ou dormir; isso não é garantia de disponibilidade 24/7.
