import logging
import re
import sys
import asyncio
from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import config
from services.llm_engine import LLMEngine
from services.wiki_service import search_wikipedia
from services.search_service import search_web, search_hardware_lifecycle
from services.hardware_service import hardware_service
from services.software_service import software_service
from services.technical_service import technical_service
from services.persona_service import persona_service
from services import network_tools

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("telegram_llm_bot")

llm = LLMEngine()

def is_chat_allowed(chat_id: int) -> bool:
    """Check if the chat is authorized when whitelist is active."""
    if not config.ALLOWED_CHAT_IDS:
        return True
    return chat_id in config.ALLOWED_CHAT_IDS

# ==========================================
# Informational & General Commands
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    bot_user = await context.bot.get_me()
    welcome_text = (
        f"👋 Hi! I am your Technical AI assistant & Network Diagnostics bot.\n\n"
        f"🤖 **Technical & AI Knowledge (Web Search + HW/SW Lifecycle):**\n"
        f"• `/ask <question>` — Ask technical, CLI, CVE, hardware, or software questions\n"
        f"• `@{bot_user.username} <question>` — Mention in group chats\n"
        f"• `/hardware` — View tracked hardware inventory list\n"
        f"• `/software` — View tracked software & OS version list\n"
        f"• `/sync_hardware` — Sync EOL data for tracked hardware\n"
        f"• `/sync_software` — Sync lifecycle data for tracked software\n\n"
        f"🛠️ **Live Network Diagnostics:**\n"
        f"• `/ping <host>` — Test host latency (4 packets)\n"
        f"• `/traceroute <host>` — Trace network route hops\n"
        f"• `/dns <host> [type]` — DNS lookup (A, MX, TXT, etc.)\n"
        f"• `/nmap <host>` — Fast scan of common ports\n"
        f"• `/whois <domain>` — Domain registration & WHOIS info\n"
        f"• `/http <url>` — HTTP status, headers & redirect chain\n"
        f"• `/ssl <host>` — SSL certificate & expiry inspection\n"
        f"• `/ipinfo <ip/host>` — Geolocation & ASN information\n\n"
        f"Type `/help` for full command details."
    )
    await update.effective_message.reply_text(welcome_text, parse_mode=constants.ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    bot_user = await context.bot.get_me()
    help_text = (
        f"📖 **Command Reference:**\n\n"
        f"🧠 **AI & Technical Knowledge:**\n"
        f"• `/ask <prompt>` — Ask hardware/software EOL, CLI configs, CVEs, or general IT questions\n"
        f"• `@{bot_user.username} <prompt>` — Mention in group chats\n"
        f"• `/hardware` — List tracked hardware devices from `{config.HARDWARE_CONFIG_FILE}`\n"
        f"• `/software` — List tracked software/OS versions from `{config.SOFTWARE_CONFIG_FILE}`\n"
        f"• `/sync_hardware` — Fetch and refresh EOL/lifecycle cache for tracked hardware\n"
        f"• `/sync_software` — Fetch and refresh lifecycle cache for tracked software\n"
        f"• `/model` — Show active local LLM model\n\n"
        f"🌐 **Network Diagnostics:**\n"
        f"• `/ping <host>` — Example: `/ping 1.1.1.1`\n"
        f"• `/traceroute <host>` — Example: `/traceroute 8.8.8.8`\n"
        f"• `/dns <host> [A|AAAA|MX|TXT|NS]` — Example: `/dns google.com MX`\n"
        f"• `/nmap <host>` — Example: `/nmap scanme.nmap.org`\n"
        f"• `/whois <domain>` — Example: `/whois github.com`\n"
        f"• `/http <url>` — Example: `/http https://telegram.org`\n"
        f"• `/ssl <host>` — Example: `/ssl google.com`\n"
        f"• `/ipinfo <ip/host>` — Example: `/ipinfo 8.8.8.8`"
    )
    await update.effective_message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

async def hardware_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List tracked hardware devices in hardware.txt and their cache status."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    devices = hardware_service.get_tracked_devices()
    if not devices:
        await update.effective_message.reply_text(
            f"No devices currently tracked in `{config.HARDWARE_CONFIG_FILE}`. Add devices to start tracking!",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    lines = [f"📋 **Tracked Hardware Inventory (`{config.HARDWARE_CONFIG_FILE}`):**\n"]
    for dev in devices:
        cached = hardware_service.get_cached_info(dev)
        status_icon = "🟢 Cached" if cached else "⚪ Pending Search"
        lines.append(f"• **{dev}** — {status_icon}")

    lines.append(f"\n💡 *Tip: Run `/sync_hardware` to pre-fetch EOL & lifecycle data for all devices.*")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=constants.ParseMode.MARKDOWN)

async def software_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List tracked software and OS versions in software.txt and their cache status."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    software_list = software_service.get_tracked_software()
    if not software_list:
        await update.effective_message.reply_text(
            f"No software currently tracked in `{config.SOFTWARE_CONFIG_FILE}`. Add software to start tracking!",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    lines = [f"💻 **Tracked Software & OS Inventory (`{config.SOFTWARE_CONFIG_FILE}`):**\n"]
    for sw in software_list:
        cached = software_service.get_cached_info(sw)
        status_icon = "🟢 Cached" if cached else "⚪ Pending Search"
        lines.append(f"• **{sw}** — {status_icon}")

    lines.append(f"\n💡 *Tip: Run `/sync_software` to pre-fetch lifecycle and upgrade data for all software.*")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=constants.ParseMode.MARKDOWN)

async def sync_hardware_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger on-demand background sync of all hardware listed in hardware.txt."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    devices = hardware_service.get_tracked_devices()
    if not devices:
        await update.effective_message.reply_text(f"No devices found in `{config.HARDWARE_CONFIG_FILE}` to sync.", parse_mode=constants.ParseMode.MARKDOWN)
        return

    msg = await update.effective_message.reply_text(f"🔄 **Syncing hardware inventory...**\nSearching and caching EOL data for {len(devices)} devices in background.", parse_mode=constants.ParseMode.MARKDOWN)

    # Run sync in background task
    async def _do_sync():
        stats = await hardware_service.sync_all()
        try:
            await msg.edit_text(
                f"✅ **Hardware Sync Complete!**\n\n"
                f"• Total Devices: `{stats['total']}`\n"
                f"• Successfully Synced: `{stats['synced']}`\n"
                f"• Failed/No Results: `{stats['failed']}`\n\n"
                f"Cached data saved to `{config.HARDWARE_CACHE_FILE}`.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error updating sync status message: {e}")

    asyncio.create_task(_do_sync())

async def sync_software_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger on-demand background sync of all software listed in software.txt."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    software_list = software_service.get_tracked_software()
    if not software_list:
        await update.effective_message.reply_text(f"No software found in `{config.SOFTWARE_CONFIG_FILE}` to sync.", parse_mode=constants.ParseMode.MARKDOWN)
        return

    msg = await update.effective_message.reply_text(f"🔄 **Syncing software inventory...**\nSearching and caching lifecycle data for {len(software_list)} software entries in background.", parse_mode=constants.ParseMode.MARKDOWN)

    # Run sync in background task
    async def _do_sync():
        stats = await software_service.sync_all()
        try:
            await msg.edit_text(
                f"✅ **Software Sync Complete!**\n\n"
                f"• Total Software Entries: `{stats['total']}`\n"
                f"• Successfully Synced: `{stats['synced']}`\n"
                f"• Failed/No Results: `{stats['failed']}`\n\n"
                f"Cached data saved to `{config.SOFTWARE_CACHE_FILE}`.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error updating software sync status message: {e}")

    asyncio.create_task(_do_sync())

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active and available models."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    available = await llm.list_available_models()
    models_str = "\n".join([f"• `{m}`" for m in available])
    msg = (
        f"🧠 **Current Active Model:** `{config.OLLAMA_MODEL}`\n\n"
        f"**Installed Models on Server:**\n{models_str}\n\n"
        f"Host: `{config.OLLAMA_HOST}`"
    )
    await update.effective_message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

# ==========================================
# Network Diagnostic Commands
# ==========================================

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live ping."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/ping <host>` (e.g. `/ping 1.1.1.1`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_ping(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live traceroute."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/traceroute <host>` (e.g. `/traceroute 8.8.8.8`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_traceroute(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def dns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live DNS lookup."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: `/dns <host> [record_type]` (e.g. `/dns google.com MX`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    target = context.args[0].strip()
    rec_type = context.args[1].strip() if len(context.args) > 1 else "A"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_dns(target, rec_type)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live nmap scan on common ports."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/nmap <host>` (e.g. `/nmap scanme.nmap.org`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_nmap(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live whois lookup."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/whois <domain>` (e.g. `/whois github.com`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_whois(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def http_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live HTTP header / latency check."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/http <url>` (e.g. `/http https://telegram.org`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_http(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def ssl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live SSL certificate check."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/ssl <host>` (e.g. `/ssl google.com`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_ssl(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

async def ipinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run live IP geolocation / ASN check."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    target = " ".join(context.args).strip()
    if not target:
        await update.effective_message.reply_text("Usage: `/ipinfo <ip/host>` (e.g. `/ipinfo 8.8.8.8`)", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    result = await network_tools.run_ipinfo(target)
    await update.effective_message.reply_text(result, parse_mode=constants.ParseMode.MARKDOWN)

# ==========================================
# General AI & Mention Handling
# ==========================================

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask general knowledge command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text("Please provide a question. Example:\n`/ask What is relativity?`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await process_and_reply(update, context, query)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle normal incoming messages (DMs, mentions, replies in groups)."""
    if not update.effective_message or not update.effective_message.text:
        return

    chat = update.effective_chat
    if not chat or not is_chat_allowed(chat.id):
        return

    message = update.effective_message
    text = message.text.strip()
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username.lower() if bot_user.username else ""

    is_private = chat.type == constants.ChatType.PRIVATE
    is_reply_to_bot = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot_user.id
    )
    is_mentioned = f"@{bot_username}" in text.lower() if bot_username else False

    # In groups, only respond if mentioned or replied to
    if not is_private and not is_reply_to_bot and not is_mentioned:
        return

    # Clean mention tag from prompt
    clean_prompt = text
    if bot_username:
        clean_prompt = re.sub(rf"@{bot_username}\b", "", clean_prompt, flags=re.IGNORECASE).strip()

    if not clean_prompt and is_reply_to_bot:
        clean_prompt = "Explain or respond to the replied message."

    if not clean_prompt:
        return

    context_msgs = []
    if is_reply_to_bot and message.reply_to_message and message.reply_to_message.text:
        context_msgs.append({"role": "assistant", "content": message.reply_to_message.text})

# Pattern to detect mentions of Drake (the artist / aliases)
DRAKE_PATTERN = re.compile(r"\b(drake|champagnepapi|aubrey\s+graham)\b", re.IGNORECASE)

def check_drake_query(prompt: str) -> bool:
    """Check if the user prompt contains mentions of Drake."""
    return bool(DRAKE_PATTERN.search(prompt))

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, context_msgs=None) -> None:
    """Send typing indicator, analyze technical intent/make/model, search/cache specs, and call LLM."""
    chat_id = update.effective_chat.id
    message = update.effective_message

    # Intercept queries regarding Drake immediately
    if check_drake_query(prompt):
        logger.info(f"Intercepted Drake query from chat {chat_id}: '{prompt}'")
        await message.reply_text(
            "Drake is gay... like the person asking this question.",
            reply_to_message_id=message.message_id
        )
        return

async def _keep_typing(bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Continuously send typing action to Telegram while LLM is generating."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

async def process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, context_msgs=None) -> None:
    """Send typing indicator, analyze technical intent/make/model, search/cache specs, and call LLM."""
    chat_id = update.effective_chat.id
    message = update.effective_message

    # Intercept queries regarding Drake immediately
    if check_drake_query(prompt):
        logger.info(f"Intercepted Drake query from chat {chat_id}: '{prompt}'")
        await message.reply_text(
            "Drake is gay... like the person asking this question.",
            reply_to_message_id=message.message_id
        )
        return

    stop_typing_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id, stop_typing_event))

    logger.info(f"User in chat {chat_id} asked AI: '{prompt[:60]}...'")

    try:
        search_results = None
        wiki_info = None

        # 1. Check for Flavius VIP or Personal Identity inquiries
        persona_intent = persona_service.classify_persona_intent(prompt)
        if persona_intent == "FLAVIUS_VIP":
            logger.info(f"Identified Flavius VIP inquiry from chat {chat_id}: '{prompt}'")
            search_results = [persona_service.get_flavius_context()]
        elif persona_intent == "PERSONAL_IDENTITY":
            logger.info(f"Identified personal identity query from chat {chat_id}: '{prompt}'")
            # Try Wikipedia search for public figures (e.g. Alan Turing, Linus Torvalds)
            wiki_info = await search_wikipedia(prompt)
        else:
            # 2. Analyze technical intent (CVE, CLI Config, Specs/EOL, General) & fetch/cache targeted info
            intent, search_results = await technical_service.get_technical_context(prompt)
            if search_results:
                logger.info(f"Retrieved {len(search_results)} technical search sources for intent '{intent}'")
            else:
                # Fallback to Wikipedia if web search yielded nothing
                wiki_info = await search_wikipedia(prompt)
                if wiki_info:
                    logger.info(f"Found Wikipedia reference: '{wiki_info['title']}' ({wiki_info['url']})")

        response_text = await llm.generate_response(
            prompt,
            context_messages=context_msgs,
            wiki_info=wiki_info,
            search_results=search_results
        )

        try:
            await message.reply_text(
                response_text,
                reply_to_message_id=message.message_id,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except Exception as md_err:
            logger.warning(f"Markdown formatting failed ({md_err}), sending as plain text.")
            await message.reply_text(
                response_text,
                reply_to_message_id=message.message_id
            )
    finally:
        stop_typing_event.set()
        typing_task.cancel()

def main() -> None:
    """Start the bot."""
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("ERROR: TELEGRAM_BOT_TOKEN is not set in .env!")
        sys.exit(1)

    logger.info("Initializing Telegram Bot Application...")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Informational & AI Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("hardware", hardware_command))
    app.add_handler(CommandHandler(["sync_hardware", "synchardware"], sync_hardware_command))
    app.add_handler(CommandHandler("software", software_command))
    app.add_handler(CommandHandler(["sync_software", "syncsoftware"], sync_software_command))

    # Network Diagnostic Handlers
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler(["traceroute", "trace"], traceroute_command))
    app.add_handler(CommandHandler(["dns", "dig"], dns_command))
    app.add_handler(CommandHandler(["nmap", "portscan"], nmap_command))
    app.add_handler(CommandHandler("whois", whois_command))
    app.add_handler(CommandHandler(["http", "curl"], http_command))
    app.add_handler(CommandHandler(["ssl", "cert"], ssl_command))
    app.add_handler(CommandHandler(["ipinfo", "ip"], ipinfo_command))

    # General Chat / Mention Message Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Bot started! Using LLM model: {config.OLLAMA_MODEL} with Live Web Search & Network Tools")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

