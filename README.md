# Telegram Saved Messages Agent

Este proyecto es un agente MTProto controlado desde el chat "Mensajes guardados" de Telegram. Permite gestionar canales, supergrupos y buscar mensajes mediante comandos sencillos.

## Requisitos
- Python 3.8+
- [Telethon](https://github.com/LonamiWebs/Telethon)

## Instalación

1. **Clona el repositorio y entra en la carpeta:**
   ```bash
   git clone <URL_DEL_REPO>
   cd telegram-agent
   ```

2. **Crea y activa un entorno virtual (venv):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instala las dependencias:**
   ```bash
   pip install telethon
   ```

## Configuración

1. **Obtén tus credenciales de Telegram:**
   - Ve a https://my.telegram.org, inicia sesión y crea una nueva app para obtener `api_id` y `api_hash`.

2. **Exporta las variables de entorno:**
   ```bash
   export TG_API_ID=<tu_api_id>
   export TG_API_HASH=<tu_api_hash>
   # Opcional:
   export TG_SESSION=user.session
   export TG_ALIAS_FILE=aliases.json
   ```

## Ejecución

Con el entorno virtual activado y las variables de entorno configuradas:

```bash
python tg_agent.py
```

La primera vez, se abrirá un prompt para iniciar sesión en Telegram (código por SMS).

## Uso desde Telegram

1. Abre tu chat de "Mensajes guardados" en Telegram.
2. Escribe `/ayuda` para ver la lista de comandos disponibles.

### Comandos principales
- `/canales [filtro]` — Lista canales y supergrupos recientes (puedes filtrar por texto).
- `/setcanal N alias=xxx` — Guarda el canal N de la lista anterior como alias.
- `/aliases` — Lista los alias guardados.
- `/delalias xxx` — Borra un alias.
- `/buscar alias "texto" N` — Busca mensajes en el canal del alias y reenvía los N primeros a guardados.

#### Ejemplo de flujo
1. `/canales kubernetes`
2. `/setcanal 3 alias=k8s`
3. `/buscar k8s "error 500" 5`

---

**¡Listo! Ahora puedes gestionar y buscar mensajes de tus canales desde tus mensajes guardados en Telegram.**
