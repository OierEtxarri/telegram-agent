import os
import re
import json
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

from telethon import TelegramClient, events
from telethon.tl.types import Channel, InputPeerChannel


@dataclass
class AliasEntry:
    type: str              # "InputPeerChannel"
    channel_id: int
    access_hash: int
    title: str = ""


class SavedMessagesAgent:
    """
    Agente MTProto controlado desde 'Mensajes guardados' (chat 'me').
    Comandos:
      /ayuda
      /canales [filtro]
      /setcanal N alias=xxx
      /aliases
      /delalias xxx
      /buscar alias "texto" N
    """

    RE_CANALES = re.compile(r"^/canales(?:\s+(.+))?$", re.IGNORECASE)
    RE_SETCANAL = re.compile(r"^/setcanal\s+(\d+)\s+alias=([A-Za-z0-9_]{1,32})\s*$", re.IGNORECASE)
    RE_BUSCAR = re.compile(r'^/buscar\s+([A-Za-z0-9_]{1,32})\s+"(.+?)"\s+(\d+)\s*$', re.IGNORECASE)
    RE_DELALIAS = re.compile(r"^/delalias\s+([A-Za-z0-9_]{1,32})\s*$", re.IGNORECASE)

    def __init__(self, api_id: int, api_hash: str, session_name: str = "user.session", alias_file: str = "aliases.json"):
        self.client = TelegramClient(session_name, api_id, api_hash)  # .session local [web:79]
        self.alias_file = alias_file
        self.last_list: Dict[int, Channel] = {}  # índice -> entidad (temporal, para /setcanal)

        # handler principal: todo llega por aquí
        self.client.add_event_handler(self._on_saved_message, events.NewMessage(chats="me"))  # [web:23]

    # ---------- Persistencia de alias ----------
    def _load_aliases(self) -> Dict[str, AliasEntry]:
        try:
            with open(self.alias_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return {}

        out: Dict[str, AliasEntry] = {}
        for k, v in raw.items():
            out[k] = AliasEntry(
                type=v["type"],
                channel_id=int(v["channel_id"]),
                access_hash=int(v["access_hash"]),
                title=v.get("title", "") or "",
            )
        return out

    def _save_aliases(self, aliases: Dict[str, AliasEntry]) -> None:
        raw: Dict[str, Any] = {}
        for k, v in aliases.items():
            raw[k] = {
                "type": v.type,
                "channel_id": int(v.channel_id),
                "access_hash": int(v.access_hash),
                "title": v.title,
            }
        with open(self.alias_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

    # ---------- Comandos ----------
    async def _cmd_ayuda(self, event):
        await event.respond(
            "Comandos:\n"
            "/canales [filtro]  -> Lista canales+supergrupos recientes (filtro 'contiene').\n"
            "/setcanal N alias=xxx -> Guarda el elemento N como alias.\n"
            "/aliases -> Lista aliases guardados.\n"
            "/delalias xxx -> Borra un alias.\n"
            '/buscar alias "texto" N -> Busca y reenvía N resultados a guardados.\n'
            "\n"
            "Ejemplo:\n"
            "/canales kubernetes\n"
            "/setcanal 3 alias=k8s\n"
            '/buscar k8s "error 500" 5\n'
        )

    async def _cmd_canales(self, event, filtro_raw: Optional[str]):
        filtro = (filtro_raw or "").strip().lower()

        # get_dialogs devuelve recientes primero; no se ordena para mantener recencia. [web:33]
        dialogs = await self.client.get_dialogs(limit=400)  # [web:33]

        self.last_list.clear()
        items: List[Tuple[Channel, str]] = []

        for d in dialogs:
            ent = d.entity
            if not isinstance(ent, Channel):
                continue

            is_broadcast = bool(getattr(ent, "broadcast", False))
            is_supergroup = bool(getattr(ent, "megagroup", False))  # supergrupo [web:44]
            if not (is_broadcast or is_supergroup):
                continue

            title = (getattr(ent, "title", "") or "")
            username = (getattr(ent, "username", "") or "")
            haystack = f"{title} {username}".lower()

            # filtro "contiene"
            if filtro and (filtro not in haystack):
                continue

            kind = "canal" if is_broadcast else "supergrupo"
            items.append((ent, kind))

        if not items:
            await event.respond("Sin resultados. Prueba otro filtro o usa /canales sin filtro.")
            return

        lines = []
        for i, (ent, kind) in enumerate(items[:40], start=1):
            self.last_list[i] = ent
            title = getattr(ent, "title", "(sin título)")
            cid = getattr(ent, "id", None)
            lines.append(f"{i}. [{kind}] {title} (id={cid})")

        await event.respond("Elige con /setcanal N alias=xxx\n\n" + "\n".join(lines))

    async def _cmd_setcanal(self, event, idx: int, alias: str):
        ent = self.last_list.get(idx)
        if not ent:
            await event.respond("Índice inválido o lista caducada. Ejecuta /canales de nuevo.")
            return

        # Convierte entidad a InputPeer* (incluye access_hash) para robustez. [web:33]
        inp = await self.client.get_input_entity(ent)  # [web:33][web:16]
        if not isinstance(inp, InputPeerChannel):
            await event.respond(f"Este chat no es InputPeerChannel (tipo={type(inp).__name__}).")
            return

        aliases = self._load_aliases()
        aliases[alias] = AliasEntry(
            type="InputPeerChannel",
            channel_id=int(inp.channel_id),
            access_hash=int(inp.access_hash),
            title=getattr(ent, "title", "") or "",
        )
        self._save_aliases(aliases)

        await event.respond(f"Guardado alias '{alias}' -> {aliases[alias].title} (channel_id={inp.channel_id}).")

    async def _cmd_aliases(self, event):
        aliases = self._load_aliases()
        if not aliases:
            await event.respond("No hay aliases. Usa /canales y /setcanal.")
            return

        lines = []
        for name, entry in sorted(aliases.items(), key=lambda x: x[0].lower()):
            lines.append(f"- {name}: {entry.title} (channel_id={entry.channel_id})")
        await event.respond("Aliases:\n" + "\n".join(lines))

    async def _cmd_delalias(self, event, alias: str):
        aliases = self._load_aliases()
        if alias not in aliases:
            await event.respond("Ese alias no existe.")
            return
        deleted = aliases.pop(alias)
        self._save_aliases(aliases)
        await event.respond(f"Alias '{alias}' borrado (era: {deleted.title}).")

    async def _cmd_buscar(self, event, alias: str, query: str, limit: int):
        aliases = self._load_aliases()
        info = aliases.get(alias)
        if not info:
            await event.respond(f"No existe el alias '{alias}'. Usa /aliases o crea uno con /setcanal.")
            return
        if info.type != "InputPeerChannel":
            await event.respond("Alias no soportado (no es InputPeerChannel).")
            return

        if limit < 1:
            await event.respond("N debe ser >= 1.")
            return
        limit = min(limit, 50)  # evita spamear guardados

        peer = InputPeerChannel(channel_id=info.channel_id, access_hash=info.access_hash)

        await event.respond(f"Buscando en '{info.title}'… (max {limit})")

        count = 0
        async for msg in self.client.iter_messages(peer, search=query, limit=limit):
            # Reenvía el mensaje exacto a guardados. [web:83]
            await self.client.forward_messages("me", msg, from_peer=peer)  # [web:83]
            count += 1

        await event.respond(f"Listo: reenviados {count} mensajes a guardados.")

    # ---------- Router ----------
    async def _on_saved_message(self, event):
        text = (event.raw_text or "").strip()

        if text.lower() in ("/ayuda", "/help", "/start"):
            await self._cmd_ayuda(event)
            return

        m = self.RE_CANALES.match(text)
        if m:
            await self._cmd_canales(event, m.group(1))
            return

        m = self.RE_SETCANAL.match(text)
        if m:
            await self._cmd_setcanal(event, int(m.group(1)), m.group(2))
            return

        if text.lower() == "/aliases":
            await self._cmd_aliases(event)
            return

        m = self.RE_DELALIAS.match(text)
        if m:
            await self._cmd_delalias(event, m.group(1))
            return

        m = self.RE_BUSCAR.match(text)
        if m:
            await self._cmd_buscar(event, m.group(1), m.group(2), int(m.group(3)))
            return

        # Si no es comando, no responde para no “ensuciar” guardados.

    # ---------- Lifecycle ----------
    async def run(self):
        # client.start() hace login si es necesario y reutiliza .session si ya existe. [web:76]
        await self.client.start()  # [web:76]
        await self.client.send_message("me", "Agente listo. Escribe /ayuda para ver comandos.")  # “me” [web:76]
        await self.client.run_until_disconnected()


async def main():
    # Qué debes hacer aquí:
    # 1) Exportar TG_API_ID y TG_API_HASH (obtenidos de my.telegram.org).
    # 2) (Opcional) TG_SESSION y TG_ALIAS_FILE.
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    session_name = os.environ.get("TG_SESSION", "user.session")
    alias_file = os.environ.get("TG_ALIAS_FILE", "aliases.json")

    agent = SavedMessagesAgent(api_id, api_hash, session_name=session_name, alias_file=alias_file)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
