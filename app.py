import json
import os

from datetime import datetime
from pathlib import Path

import streamlit as st
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


#Information about the Agent hosted in Microsoft Azure Foundry
DEFAULT_PROJECT_ENDPOINT = (
    "https://ricardo286malaga-9265-resource.services.ai.azure.com/"
    "api/projects/ricardo286malaga-9265"
)
DEFAULT_AGENT_NAME = "FirstFoundry"
DEFAULT_AGENT_VERSION = "3"

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", DEFAULT_PROJECT_ENDPOINT)
AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", DEFAULT_AGENT_NAME)
AGENT_VERSION = os.getenv("FOUNDRY_AGENT_VERSION", DEFAULT_AGENT_VERSION)




def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest parent containing Database or .venv."""
    current = (start or Path.cwd()).resolve()

    for candidate in (current, *current.parents):
        if (candidate / "Database").is_dir() or (candidate / ".venv").is_dir():
            return candidate

    return current


PROJECT_ROOT = find_project_root()
DATABASE_DIR = PROJECT_ROOT / "Database"
REGISTRY_PATH = DATABASE_DIR / "conversations.json"


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"conversations": {}}

    with REGISTRY_PATH.open("r", encoding="utf-8") as file:
        registry = json.load(file)

    if not isinstance(registry.get("conversations"), dict):
        raise ValueError("Invalid registry: 'conversations' must be an object.")

    return registry


def save_registry(registry: dict) -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    with REGISTRY_PATH.open("w", encoding="utf-8") as file:
        json.dump(registry, file, ensure_ascii=False, indent=4)
        file.write("\n")


def list_registered_conversations() -> list[dict]:
    rows = [
        {"conversation_id": conversation_id, **metadata}
        for conversation_id, metadata
        in load_registry()["conversations"].items()
    ]
    return sorted(
        rows,
        key=lambda row: row.get("updated_at", ""),
        reverse=True,
    )


def register_conversation(conversation_id: str, title: str) -> None:
    registry = load_registry()
    timestamp = current_timestamp()
    registry["conversations"][conversation_id] = {
        "title": title.strip(),
        "agent_name": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_response_id": None,
    }
    save_registry(registry)


def update_last_response(conversation_id: str, response_id: str) -> None:
    registry = load_registry()
    metadata = registry["conversations"].get(conversation_id)

    if metadata is None:
        raise KeyError(f"Conversation {conversation_id!r} is not registered.")

    metadata["updated_at"] = current_timestamp()
    metadata["last_response_id"] = response_id
    save_registry(registry)


@st.cache_resource
def get_clients():
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
    )
    return project_client, project_client.get_openai_client()


def create_conversation(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Escribe un título para la conversación.")

    titles = {
        row.get("title", "").strip().casefold()
        for row in list_registered_conversations()
    }
    if normalized_title.casefold() in titles:
        raise ValueError("Ya existe una conversación con ese título.")

    _, openai_client = get_clients()
    conversation = openai_client.conversations.create()
    register_conversation(conversation.id, normalized_title)
    return conversation.id


def extract_text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        return str(content.get("text", ""))

    text = getattr(content, "text", None)
    return text if isinstance(text, str) else ""


def load_messages(conversation_id: str) -> list[dict[str, str]]:
    _, openai_client = get_clients()
    page = openai_client.conversations.items.list(
        conversation_id=conversation_id,
        order="asc",
        limit=100,
    )
    messages = []

    for item in page.data:
        if getattr(item, "type", None) != "message":
            continue

        role = getattr(item, "role", None)
        if role not in {"user", "assistant"}:
            continue

        parts = [
            extract_text_from_content(content)
            for content in getattr(item, "content", [])
        ]
        text = "\n".join(part for part in parts if part).strip()

        if text:
            messages.append({"role": role, "content": text})

    return messages


def send_message(conversation_id: str, message: str) -> str:
    _, openai_client = get_clients()

    openai_client.conversations.items.create(
        conversation_id=conversation_id,
        items=[{"type": "message", "role": "user", "content": message}],
    )

    response = openai_client.responses.create(
        conversation=conversation_id,
        extra_body={
            "agent_reference": {
                "name": AGENT_NAME,
                "version": AGENT_VERSION,
                "type": "agent_reference",
            }
        },
    )
    update_last_response(conversation_id, response.id)
    return response.output_text


st.set_page_config(
    page_title="FirstFoundry Conversations",
    page_icon="💬",
    layout="wide",
)

st.title("FirstFoundry")
st.caption("Conversaciones persistentes de Microsoft Foundry")

try:
    conversations = list_registered_conversations()
except (OSError, json.JSONDecodeError, ValueError) as error:
    st.error(f"No se pudo leer {REGISTRY_PATH}: {error}")
    st.stop()

with st.sidebar:
    st.header("Conversaciones")

    with st.form("new_conversation_form", clear_on_submit=True):
        new_title = st.text_input("Título de la conversación")
        create_pressed = st.form_submit_button(
            "Nueva conversación",
            use_container_width=True,
        )

    if create_pressed:
        try:
            new_conversation_id = create_conversation(new_title)
        except Exception as error:
            st.error(f"No se pudo crear la conversación: {error}")
        else:
            st.session_state.selected_conversation_id = new_conversation_id
            st.rerun()

    if conversations:
        conversation_by_id = {
            row["conversation_id"]: row for row in conversations
        }
        conversation_ids = list(conversation_by_id)
        selected_id = st.session_state.get(
            "selected_conversation_id",
            conversation_ids[0],
        )
        if selected_id not in conversation_by_id:
            selected_id = conversation_ids[0]

        selected_id = st.selectbox(
            "Historial",
            options=conversation_ids,
            index=conversation_ids.index(selected_id),
            format_func=lambda conversation_id: conversation_by_id[conversation_id]["title"],
        )
        st.session_state.selected_conversation_id = selected_id

        selected_metadata = conversation_by_id[selected_id]
        st.caption(f"Agente: {selected_metadata['agent_name']} v{selected_metadata['agent_version']}")
        st.caption(f"Actualizada: {selected_metadata['updated_at']}")
    else:
        selected_id = None
        st.info("Crea la primera conversación para comenzar.")

if selected_id is None:
    st.info("Usa la barra lateral para crear una conversación.")
    st.stop()

selected_title = next(
    row["title"]
    for row in conversations
    if row["conversation_id"] == selected_id
)
st.subheader(selected_title)

try:
    messages = load_messages(selected_id)
except Exception as error:
    st.error(
        "No se pudo recuperar el historial desde Foundry. "
        "Comprueba que has ejecutado `az login` y que la conversación existe.\n\n"
        f"Detalle: {error}"
    )
    st.stop()

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Escribe un mensaje para FirstFoundry")

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("FirstFoundry está respondiendo..."):
            try:
                answer = send_message(selected_id, prompt)
            except Exception as error:
                st.error(f"No se pudo obtener la respuesta: {error}")
            else:
                st.markdown(answer)
                st.rerun()
