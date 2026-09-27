import os
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from gradio_client import Client


# ============================================================
# MUSICIA 2.0
# Backend
# ============================================================

app = FastAPI(
    title="MusicIA API",
    version="2.0"
)


# ============================================================
# DIRETÓRIOS
# ============================================================

AUDIO_DIR = Path(tempfile.gettempdir()) / "musicia_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# ACE-STEP
# ============================================================

SPACE = "ACE-Step/Ace-Step-v1.5"

print("==========================================", flush=True)
print("MUSICIA - CONECTANDO AO ACE-STEP", flush=True)
print("SPACE:", SPACE, flush=True)
print("==========================================", flush=True)

HF_TOKEN = os.environ.get("HF_TOKEN")

if not HF_TOKEN:
    raise RuntimeError(
        "HF_TOKEN não configurado no Render."
    )

client = Client(
    SPACE,
    token=HF_TOKEN,
    verbose=True
)


# ============================================================
# MODELO DA REQUISIÇÃO
# ============================================================

class GenerateRequest(BaseModel):
    idea: str
    style: str = "Sertanejo"
    mood: str = "Motivacional"
    voice: str = "Masculina"

    # Duração solicitada pelo usuário
    # Valores permitidos: 10, 15, 30 ou 60 segundos
    duration: int = 10


# ============================================================
# UTILITÁRIOS
# ============================================================

def safe_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    try:
        return str(value)
    except Exception:
        return ""


def is_url(value: Any) -> bool:
    return (
        isinstance(value, str)
        and (
            value.startswith("http://")
            or value.startswith("https://")
        )
    )


def is_file(value: Any) -> bool:
    return (
        isinstance(value, str)
        and os.path.isfile(value)
    )


# ============================================================
# PROCURA ÁUDIO NO RESULTADO
# ============================================================

def extract_audio(result):
    """
    Procura recursivamente um arquivo ou URL de áudio
    dentro do resultado devolvido pelo Gradio.
    """

    if result is None:
        return None

    if isinstance(result, str):

        if is_url(result):
            return result

        if is_file(result):
            return result

        return None

    if isinstance(result, dict):

        priority_keys = [
            "audio",
            "audio_url",
            "url",
            "path",
            "filepath",
            "file",
            "name",
            "value"
        ]

        for key in priority_keys:

            if key in result:

                found = extract_audio(
                    result[key]
                )

                if found:
                    return found

        for value in result.values():

            found = extract_audio(value)

            if found:
                return found

        return None

    if isinstance(result, (list, tuple)):

        for value in result:

            found = extract_audio(value)

            if found:
                return found

        return None

    for attr in [
        "path",
        "url",
        "name",
        "filepath"
    ]:

        try:

            value = getattr(
                result,
                attr,
                None
            )

            found = extract_audio(value)

            if found:
                return found

        except Exception:
            pass

    try:

        if hasattr(result, "__dict__"):

            found = extract_audio(
                vars(result)
            )

            if found:
                return found

    except Exception:
        pass

    return None


# ============================================================
# CRIA PROMPT
# ============================================================

def create_prompt(request: GenerateRequest) -> str:

    voice_map = {
        "Masculina": "male vocal",
        "Feminina": "female vocal",
        "Dueto": "male and female duet",
        "Instrumental": "instrumental, no vocals"
    }

    voice = voice_map.get(
        request.voice,
        request.voice
    )

    return (
        f"{request.style} brasileiro, "
        f"{request.mood.lower()}, "
        f"{voice}, "
        "música em português do Brasil, "
        "produção musical moderna, "
        "melodia marcante, "
        "estrutura profissional, "
        "refrão forte e emocionante. "
        f"Tema principal: {request.idea}"
    )


# ============================================================
# LETRA
# ============================================================

def create_lyrics(request: GenerateRequest) -> str:

    if request.voice == "Instrumental":
        return ""

    idea = request.idea.strip()

    return f"""
[Verso 1]
{idea}
Eu já caí, mas levantei
Mesmo sofrendo, eu continuei
A vida tentou me derrubar
Mas eu nasci pra conquistar

[Pré-Refrão]
Cada batalha me fez mais forte
Eu não dependo apenas da sorte
Se existe um caminho pra seguir
Eu vou lutar até conseguir

[Refrão]
Eu não vou desistir
Enquanto houver força em mim
Eu vou lutar, eu vou seguir
Até chegar ao meu fim

Se a vida fechar uma porta
Eu vou procurar outra saída
Porque quem acredita no sonho
Nunca abandona a própria vida

[Verso 2]
Já passei por dias difíceis
Já pensei em parar
Mas dentro do meu peito
Ainda existe vontade de lutar

[Pré-Refrão]
Eu sei que ainda vai chegar
O dia que eu vou vencer
Enquanto existir esperança
Eu não vou deixar de crer

[Refrão]
Eu não vou desistir
Enquanto houver força em mim
Eu vou lutar, eu vou seguir
Até chegar ao meu fim

[Final]
Eu posso cair
Eu posso sofrer
Mas enquanto eu respirar
Eu vou lutar pra vencer
"""


# ============================================================
# OBTÉM INFORMAÇÕES DO ENDPOINT
# ============================================================

def get_generation_api():

    print(
        "Consultando API real do ACE-Step...",
        flush=True
    )

    info = client.view_api(
        return_format="dict"
    )

    print(
        "========== API DO ACE-STEP ==========",
        flush=True
    )

    try:
        print(
            json.dumps(
                info,
                ensure_ascii=False,
                indent=2,
                default=str
            ),
            flush=True
        )
    except Exception:
        print(
            repr(info),
            flush=True
        )

    print(
        "======================================",
        flush=True
    )

    endpoints = {}

    if isinstance(info, dict):

        endpoints = info.get(
            "named_endpoints",
            {}
        )

    endpoint = (
        endpoints.get(
            "/generation_wrapper"
        )
    )

    if endpoint is None:

        for name, data in endpoints.items():

            if (
                "generation" in name.lower()
                or "wrapper" in name.lower()
            ):

                endpoint = data

                print(
                    f"Endpoint encontrado: {name}",
                    flush=True
                )

                return name, endpoint

    if endpoint is None:

        raise RuntimeError(
            "O endpoint /generation_wrapper "
            "não foi encontrado no ACE-Step."
        )

    return "/generation_wrapper", endpoint


# ============================================================
# PEGA NOME DO PARÂMETRO
# ============================================================

def parameter_name(parameter, index):

    if not isinstance(parameter, dict):
        return f"param_{index + 1}"

    for key in [
        "parameter_name",
        "name",
        "label"
    ]:

        value = parameter.get(key)

        if isinstance(value, str):
            return value

    return f"param_{index + 1}"


# ============================================================
# PEGA VALOR PADRÃO
# ============================================================

def parameter_default(parameter):

    if not isinstance(parameter, dict):
        return None, False

    for key in [
        "parameter_default",
        "default",
        "example_input"
    ]:

        if key in parameter:

            value = parameter.get(key)

            if value is not None:
                return value, True

    if parameter.get(
        "parameter_has_default"
    ):

        if "parameter_default" in parameter:

            return (
                parameter.get(
                    "parameter_default"
                ),
                True
            )

    return None, False


# ============================================================
# INFERÊNCIA DE VALOR
# ============================================================

def fallback_value(parameter, index):

    if not isinstance(parameter, dict):
        return None

    name = (
        parameter_name(
            parameter,
            index
        )
        .lower()
    )

    component = safe_text(
        parameter.get(
            "component",
            ""
        )
    ).lower()

    ptype = safe_text(
        parameter.get(
            "type",
            ""
        )
    ).lower()

    description = safe_text(
        parameter.get(
            "description",
            ""
        )
    ).lower()

    text = (
        name
        + " "
        + component
        + " "
        + ptype
        + " "
        + description
    )

    if (
        "list" in ptype
        or "checkboxgroup" in component
    ):
        return []

    if (
        "bool" in ptype
        or "checkbox" in component
    ):
        return False

    if (
        "int" in ptype
        or "integer" in ptype
        or "number" in component
    ):

        if "batch" in text:
            return 1

        if "step" in text:
            return 8

        if "index" in text:
            return 0

        return 0

    if (
        "float" in ptype
        or "slider" in component
    ):

        if (
            "scale" in text
            or "strength" in text
        ):
            return 1.0

        if "temperature" in text:
            return 0.85

        if "top_p" in text:
            return 0.9

        return 0.0

    if "state" in component:
        return {}

    if (
        "audio" in text
        or "file" in component
    ):
        return None

    return ""


# ============================================================
# MONTA ARGUMENTOS DINAMICAMENTE
# ============================================================

def build_generation_kwargs(
    request: GenerateRequest
):

    endpoint_name, endpoint = (
        get_generation_api()
    )

    parameters = []

    if isinstance(endpoint, dict):

        parameters = endpoint.get(
            "parameters",
            []
        )

    if not parameters:

        raise RuntimeError(
            "O ACE-Step não informou os "
            "parâmetros do generation_wrapper."
        )

    prompt = create_prompt(request)
    lyrics = create_lyrics(request)

    kwargs = {}

    print(
        "========== MONTANDO PARÂMETROS ==========",
        flush=True
    )

    for index, parameter in enumerate(
        parameters
    ):

        name = parameter_name(
            parameter,
            index
        )

        default, has_default = (
            parameter_default(
                parameter
            )
        )

        if has_default:
            value = default
        else:
            value = fallback_value(
                parameter,
                index
            )

        lower = name.lower()

        # ----------------------------------------------------
        # CAMPOS PRINCIPAIS
        # ----------------------------------------------------

        if (
            lower
            in [
                "simple_query_input",
                "query",
                "prompt"
            ]
        ):
            value = prompt

        elif (
            "simple_vocal_language"
            in lower
        ):
            value = "pt"

        elif (
            lower
            in [
                "caption",
                "simple_caption"
            ]
        ):
            value = prompt

        elif lower == "lyrics":
            value = lyrics

        elif lower == "vocal_language":
            value = "pt"

        # ----------------------------------------------------
        # FORMATO / TAREFA
        # ----------------------------------------------------

        elif lower == "task_type":
            value = "text2music"

        elif lower == "audio_format":
            value = "mp3"

        # ----------------------------------------------------
        # DURAÇÃO
        # ----------------------------------------------------
        # Diferentes versões do ACE-Step podem chamar
        # esse parâmetro por nomes diferentes.
        #
        # O valor escolhido pelo usuário é enviado aqui.
        # Permitidos: 10, 15, 30 e 60 segundos.
        # ----------------------------------------------------

        elif (
            "audio_duration" in lower
            or lower in [
                "duration",
                "target_duration",
                "audio_length"
            ]
        ):

            value = int(request.duration)

        # ----------------------------------------------------
        # MODELO
        # ----------------------------------------------------

        elif lower == "selected_model":
            value = "acestep-v15-turbo"

        elif lower == "generation_mode":
            value = "simple"

        # ----------------------------------------------------
        # CONFIGURAÇÕES SEGURAS
        # ----------------------------------------------------

        if (
            isinstance(value, bool)
            and (
                "scale" in lower
                or "strength" in lower
                or "temperature" in lower
                or "duration" in lower
                or "bpm" in lower
                or "step" in lower
                or "shift" in lower
            )
        ):

            value = fallback_value(
                parameter,
                index
            )

        kwargs[name] = value

        print(
            f"[{index}] {name} = {repr(value)}",
            flush=True
        )

    print(
        "==========================================",
        flush=True
    )

    print(
        "TOTAL KWARGS:",
        len(kwargs),
        flush=True
    )

    return endpoint_name, kwargs


# ============================================================
# GERAÇÃO
# ============================================================

def generate_music(
    request: GenerateRequest
):

    endpoint_name, kwargs = (
        build_generation_kwargs(
            request
        )
    )

    print(
        "==========================================",
        flush=True
    )

    print(
        "INICIANDO GERAÇÃO",
        flush=True
    )

    print(
        "DURAÇÃO:",
        request.duration,
        "segundos",
        flush=True
    )

    print(
        "ENDPOINT:",
        endpoint_name,
        flush=True
    )

    print(
        "IDEIA:",
        request.idea,
        flush=True
    )

    print(
        "ESTILO:",
        request.style,
        flush=True
    )

    print(
        "CLIMA:",
        request.mood,
        flush=True
    )

    print(
        "VOZ:",
        request.voice,
        flush=True
    )

    print(
        "==========================================",
        flush=True
    )

    try:

        result = client.predict(
            api_name=endpoint_name,
            **kwargs
        )

        print(
            "========== RESULTADO ==========",
            flush=True
        )

        print(
            repr(result),
            flush=True
        )

        print(
            "================================",
            flush=True
        )

        audio = extract_audio(
            result
        )

        if not audio:

            raise RuntimeError(
                "O ACE-Step respondeu, "
                "mas não retornou áudio."
            )

        return audio

    except Exception as error:

        print(
            "==========================================",
            flush=True
        )

        print(
            "ERRO ACE-STEP:",
            repr(error),
            flush=True
        )

        print(
            "==========================================",
            flush=True
        )

        raise


# ============================================================
# FRONTEND
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    frontend = (
        Path(__file__).parent
        / "frontend"
        / "index.html"
    )

    if frontend.exists():

        return frontend.read_text(
            encoding="utf-8"
        )

    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width,initial-scale=1">
        <title>MusicIA</title>
    </head>

    <body>

        <h1>🎵 MusicIA</h1>

        <p>
            Frontend não encontrado.
        </p>

    </body>
    </html>
    """


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "ok": True,
        "service": "MusicIA",
        "version": "2.0",
        "engine": "ACE-Step v1.5",
        "durations": [
            10,
            15,
            30,
            60
        ]
    }


# ============================================================
# API DE GERAÇÃO
# ============================================================

@app.post("/api/generate")
def generate(
    request: GenerateRequest
):

    if not request.idea.strip():

        raise HTTPException(
            status_code=400,
            detail="Digite uma ideia para a música."
        )

    # --------------------------------------------------------
    # VALIDAÇÃO DA DURAÇÃO
    # --------------------------------------------------------

    if request.duration not in [
        10,
        15,
        30,
        60
    ]:

        raise HTTPException(
            status_code=400,
            detail=(
                "Duração inválida. "
                "Escolha 10, 15, 30 ou 60 segundos."
            )
        )

    try:

        audio = generate_music(
            request
        )

        if is_url(audio):

            return {
                "ok": True,
                "audio": audio,
                "duration": request.duration
            }

        if is_file(audio):

            extension = (
                Path(audio).suffix
                or ".mp3"
            )

            destination = (
                AUDIO_DIR
                / f"{uuid.uuid4().hex}{extension}"
            )

            shutil.copy2(
                audio,
                destination
            )

            media_type = "audio/mpeg"

            if extension.lower() == ".wav":
                media_type = "audio/wav"

            elif extension.lower() == ".ogg":
                media_type = "audio/ogg"

            return FileResponse(
                destination,
                media_type=media_type,
                filename=(
                    "musicia"
                    + extension
                )
            )

        raise RuntimeError(
            "O áudio foi gerado, "
            "mas não foi possível localizar "
            "o arquivo retornado."
        )

    except HTTPException:
        raise

    except Exception as error:

        print(
            "==========================================",
            flush=True
        )

        print(
            "ERRO FINAL:",
            repr(error),
            flush=True
        )

        print(
            "==========================================",
            flush=True
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"{type(error).__name__}: "
                f"{error}"
            )
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
)
