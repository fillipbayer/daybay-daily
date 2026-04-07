"""
DayBay Daily — Integração com Microsoft Calendar (Graph API)
Usa MSAL com Device Code Flow — simples, sem servidor de callback
"""

import os
import json
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_CACHE_FILE = Path(__file__).parent.parent / "data" / ".ms_token_cache.json"

SCOPES = ["Calendars.Read", "Tasks.Read", "offline_access"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_msal_app():
    """Cria o app MSAL com cache persistente."""
    try:
        import msal
        client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")

        if not client_id:
            return None, None

        cache = msal.SerializableTokenCache()
        if TOKEN_CACHE_FILE.exists():
            cache.deserialize(TOKEN_CACHE_FILE.read_text())

        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            token_cache=cache,
        )
        return app, cache
    except ImportError:
        logger.warning("msal não instalado")
        return None, None


def _save_cache(cache):
    """Persiste o token cache em disco."""
    if cache and cache.has_state_changed:
        TOKEN_CACHE_FILE.parent.mkdir(exist_ok=True)
        TOKEN_CACHE_FILE.write_text(cache.serialize())


def get_device_code_flow_url() -> Optional[Dict]:
    """
    Inicia o Device Code Flow.
    Retorna dicionário com 'user_code', 'verification_uri' e 'message' para exibir ao usuário.
    """
    app, cache = _get_msal_app()
    if not app:
        return None

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "error" in flow:
        logger.error(f"Erro no Device Code Flow: {flow}")
        return None

    _save_cache(cache)
    # Salva o flow para uso posterior
    flow_file = Path(__file__).parent.parent / "data" / ".ms_device_flow.json"
    flow_file.write_text(json.dumps(flow))

    return {
        "user_code": flow.get("user_code"),
        "verification_uri": flow.get("verification_uri"),
        "message": flow.get("message"),
        "expires_in": flow.get("expires_in", 900),
    }


def complete_device_code_flow() -> bool:
    """Tenta completar o Device Code Flow após o usuário ter feito login."""
    app, cache = _get_msal_app()
    if not app:
        return False

    flow_file = Path(__file__).parent.parent / "data" / ".ms_device_flow.json"
    if not flow_file.exists():
        return False

    flow = json.loads(flow_file.read_text())
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        _save_cache(cache)
        flow_file.unlink(missing_ok=True)
        logger.info("✅ Microsoft autenticado com sucesso!")
        return True

    logger.warning(f"Autenticação pendente: {result.get('error_description', '')}")
    return False


def _get_access_token() -> Optional[str]:
    """Obtém token de acesso válido do cache."""
    app, cache = _get_msal_app()
    if not app:
        return None

    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
    _save_cache(cache)

    if result and "access_token" in result:
        return result["access_token"]
    return None


async def get_todays_events(target_date: Optional[date] = None) -> List[Dict]:
    """Busca eventos do calendário Microsoft para o dia especificado."""
    token = _get_access_token()
    if not token:
        logger.info("Microsoft Calendar não autenticado — pulando")
        return []

    if target_date is None:
        target_date = date.today()

    # Intervalo do dia (UTC-aware)
    start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_BASE}/me/calendarView",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "startDateTime": start_str,
                    "endDateTime": end_str,
                    "$select": "subject,start,end,location,isOnlineMeeting,onlineMeetingUrl,bodyPreview",
                    "$orderby": "start/dateTime",
                    "$top": "20",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            events = []
            for item in data.get("value", []):
                start_dt = item["start"]["dateTime"][:16].replace("T", " ")
                end_dt = item["end"]["dateTime"][:16].replace("T", " ")
                events.append({
                    "subject": item.get("subject", "Sem título"),
                    "start": start_dt,
                    "end": end_dt,
                    "location": item.get("location", {}).get("displayName", ""),
                    "is_online": item.get("isOnlineMeeting", False),
                    "meeting_url": item.get("onlineMeetingUrl", ""),
                    "preview": item.get("bodyPreview", "")[:150],
                })
            return events
    except Exception as e:
        logger.error(f"Erro ao buscar calendário: {e}")
        return []


async def get_tasks() -> List[Dict]:
    """Busca tarefas pendentes do Microsoft To Do."""
    token = _get_access_token()
    if not token:
        return []

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Busca as listas de tarefas
            lists_resp = await client.get(
                f"{GRAPH_BASE}/me/todo/lists",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            lists_resp.raise_for_status()
            lists_data = lists_resp.json()

            tasks = []
            for task_list in lists_data.get("value", [])[:3]:  # primeiras 3 listas
                list_id = task_list["id"]
                tasks_resp = await client.get(
                    f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "$filter": "status ne 'completed'",
                        "$top": "10",
                        "$select": "title,importance,dueDateTime,status",
                    },
                    timeout=10.0,
                )
                tasks_resp.raise_for_status()
                tasks_data = tasks_resp.json()

                for task in tasks_data.get("value", []):
                    due = None
                    if task.get("dueDateTime"):
                        due = task["dueDateTime"]["dateTime"][:10]
                    tasks.append({
                        "title": task.get("title", ""),
                        "importance": task.get("importance", "normal"),
                        "due_date": due,
                        "list_name": task_list.get("displayName", ""),
                    })
            return tasks
    except Exception as e:
        logger.error(f"Erro ao buscar tarefas: {e}")
        return []


def is_authenticated() -> bool:
    """Verifica se há autenticação Microsoft ativa."""
    return _get_access_token() is not None
