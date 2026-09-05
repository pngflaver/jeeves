import logging
import re
import sys
import asyncio
from datetime import datetime, timezone
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
import time
from services.persona_service import persona_service
from services.flight_service import flight_service
from services.profile_service import profile_service
from services.movie_service import movie_service
from services.kpi_service import kpi_service
from services.places_service import places_service
from services.nrl_service import nrl_service, NRL_VALIDATION_SYSTEM_PROMPT
from services.quality_service import quality_service
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

def track_kpi_command(name: str):
    """Decorator to measure and record command execution in KPIService."""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            t0 = time.time()
            user_id = update.effective_user.id if update.effective_user else None
            success = True
            try:
                return await func(update, context)
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - t0) * 1000.0
                kpi_service.record_command(name, user_id=user_id, success=success, duration_ms=duration_ms)
        return wrapper
    return decorator

# ==========================================
# Informational & General Commands
# ==========================================

@track_kpi_command("start")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    bot_user = await context.bot.get_me()
    welcome_text = (
        f"👋 Hi! I am your Technical AI assistant & Network Diagnostics bot.\n\n"
        f"🤖 **Technical & AI Knowledge (Web Search + HW/SW Lifecycle):**\n"
        f"• `/ask <question>` — Ask technical, CLI, CVE, hardware, or software questions\n"
        f"• `/movie <title>` — Look up Movie ID (`{{id}}` with `tt` prefix or TMDB ID)\n"
        f"• `/tv <title> [s] [e]` — Look up TV Show (`{{id}}`, `{{season}}`, `{{episode}}`)\n"
        f"• `/flight <from> <to>` — Search flight routes & operating airlines (e.g. `/flight POM BNE`)\n"
        f"• `/place <name>` — Look up local business, operating hours, phone & map\n"
        f"• `/nrl [team/query]` — Verified NRL news, ladder standings, and player/team stats\n"
        f"• `/sync_nrl` — Admin sync of NRL teams, squads, ladder & weekly briefing\n"
        f"• `@{bot_user.username} <question>` — Mention in group chats\n"
        f"• `/hardware` — View tracked hardware inventory list\n"
        f"• `/software` — View tracked software & OS version list\n\n"
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

@track_kpi_command("help")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    bot_user = await context.bot.get_me()
    help_text = (
        f"📖 **Command Reference:**\n\n"
        f"🧠 **AI, Places & Media Knowledge:**\n"
        f"• `/ask <prompt>` — Ask hardware/software EOL, CLI configs, CVEs, or general IT questions\n"
        f"• `/nrl [team/query]` — Verified NRL news, ladder standings, and player/team stats\n"
        f"• `/sync_nrl` — Admin sync of NRL teams, squads, ladder & weekly briefing\n"
        f"• `/place <name>` — Look up local business, operating hours & phone (e.g. `/place CPL Vision City`)\n"
        f"• `/movie <title>` — Extract movie parameters (`{{id}}` from IMDb/TMDB)\n"
        f"• `/tv <title> [s] [e]` — Extract TV show parameters (`{{id}}`, `{{season}}`, `{{episode}}`)\n"
        f"• `/flight <orig> <dest>` — Flight schedules & operating airlines (e.g. `/flight POM BNE`)\n"
        f"• `@{bot_user.username} <prompt>` — Mention in group chats\n"
        f"• `/hardware` — List tracked hardware devices from `{config.HARDWARE_CONFIG_FILE}`\n"
        f"• `/software` — List tracked software/OS versions from `{config.SOFTWARE_CONFIG_FILE}`\n"
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

@track_kpi_command("movie")
async def movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /movie and /movies lookup command extracting {id}."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    title = " ".join(context.args).strip()
    if not title:
        await update.effective_message.reply_text(
            "Usage: `/movie <title>` (e.g. `/movie Inception` or `/movie Interstellar 2014`)\n"
            "Returns `{id}` parameter from IMDb / TheMovieDB.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    movie_data = await movie_service.lookup_movie(title)
    if not movie_data or not (movie_data.get("imdb_id") or movie_data.get("tmdb_id")):
        await update.effective_message.reply_text(
            f"❌ Could not find movie or IMDb/TMDB ID for: `{title}`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    formatted_card = movie_service.format_movie_card(movie_data)
    await update.effective_message.reply_text(
        formatted_card,
        parse_mode=constants.ParseMode.MARKDOWN
    )

@track_kpi_command("tv")
async def tv_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tv and /series lookup command extracting {id}, {season}, and {episode}."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    raw_query = " ".join(context.args).strip()
    if not raw_query:
        await update.effective_message.reply_text(
            "Usage:\n"
            "• `/tv <title> <season> <episode>` (e.g. `/tv Breaking Bad 2 5`)\n"
            "• `/tv <title> s02e05` (e.g. `/tv The Boys s03e02`)\n"
            "• `/tv <title>` (defaults to season 1, episode 1)\n\n"
            "Returns `{id}`, `{season}`, and `{episode}` parameters.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    tv_data, season, episode = await movie_service.lookup_tv(raw_query)
    if not tv_data or not (tv_data.get("imdb_id") or tv_data.get("tmdb_id")):
        await update.effective_message.reply_text(
            f"❌ Could not find TV series or IMDb/TMDB ID for: `{raw_query}`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    formatted_card = movie_service.format_tv_card(tv_data, season, episode)
    await update.effective_message.reply_text(
        formatted_card,
        parse_mode=constants.ParseMode.MARKDOWN
    )

@track_kpi_command("hardware")
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

@track_kpi_command("software")
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

@track_kpi_command("sync_hardware")
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

@track_kpi_command("sync_software")
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

@track_kpi_command("model")
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

@track_kpi_command("flight")
async def flight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /flight <origin> <destination> command."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text(
            "✈️ **Flight Lookup Usage:**\n"
            "• `/flight POM BNE` — Port Moresby to Brisbane\n"
            "• `/flight POM SYD` — Port Moresby to Sydney\n"
            "• `/flight POM CNS` — Port Moresby to Cairns\n"
            "• `/flight Port Moresby to Singapore`\n\n"
            "Provides operating airlines, direct schedules, flight times, and live booking/tracking links.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    flight_query = f"flights from {query}" if "to" in query or len(context.args) >= 2 else f"flight {query}"
    await process_and_reply(update, context, flight_query)

@track_kpi_command("place")
async def place_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Look up local business, operating hours, phone, and address via OpenStreetMap & web."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text(
            "📍 **Local Place & Business Lookup Usage:**\n"
            "• `/place CPL Medical Center Vision City`\n"
            "• `/place Airways Hotel Port Moresby`\n"
            "• `/place Daikoku Restaurant`\n"
            "• `/place Brian Bell Plaza Boroko`\n\n"
            "Retrieves verified operating hours, phone, address, and map links without Google API keys.",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    place_data = await places_service.lookup_place(query)
    card = places_service.format_place_card(place_data)
    await update.effective_message.reply_text(card, parse_mode=constants.ParseMode.MARKDOWN)

@track_kpi_command("nrl")
async def nrl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nrl command for verified rugby league updates."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    query = " ".join(context.args).strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    if not query:
        # Return priority pre-compiled briefing (Broncos, QLD Maroons, PNG Chiefs)
        briefing = await nrl_service.get_priority_briefing()
        header = (
            "🏉 **NRL Intelligence & Priority Briefing**\n"
            "*(Verified via official NRL, QRL, ABC, and PNG news)*\n\n"
        )
        footer = "\n\n💡 *Tip: Query specific topics, e.g.* `/nrl reece walsh` *or* `/nrl png chiefs`."
        full_text = header + briefing + footer
        rec_id = quality_service.log_interaction(
            command="nrl",
            user=update.effective_user,
            query="[Priority Briefing]",
            response=full_text,
            sources=None
        )
        reply_markup = None
        if rec_id:
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ])
        try:
            await update.effective_message.reply_text(
                full_text,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as md_err:
            logger.warning(f"Markdown formatting failed in /nrl ({md_err}), sending as plain text.")
            await update.effective_message.reply_text(
                full_text,
                reply_markup=reply_markup
            )
    else:
        q_clean = query.strip().lower()

        # 1. Full NRL Ladder query
        if q_clean in ["ladder", "standings", "table", "nrl ladder", "nrl standings", "the ladder"]:
            ans = nrl_service.format_full_ladder()
            rec_id = quality_service.log_interaction(
                command="nrl",
                user=update.effective_user,
                query=query,
                response=ans,
                sources=None
            )
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ]) if rec_id else None
            await update.effective_message.reply_text(ans, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=reply_markup)
            return

        # 2. Team-specific inquiries (e.g. "/nrl broncos stats", "/nrl storm record", "/nrl dolphins")
        team_match = nrl_service.find_team_in_registry(query)
        player_match = nrl_service.find_player_in_registry(query)

        if team_match and not player_match and (nrl_service.is_stats_query(query) or len(query.split()) <= 3):
            ans = nrl_service.format_team_stats_card(team_match[1])
            rec_id = quality_service.log_interaction(
                command="nrl",
                user=update.effective_user,
                query=query,
                response=ans,
                sources=None
            )
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ]) if rec_id else None
            try:
                await update.effective_message.reply_text(
                    ans,
                    parse_mode=constants.ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            except Exception as md_err:
                logger.warning(f"Markdown formatting failed in /nrl team card ({md_err}), sending as plain text.")
                await update.effective_message.reply_text(ans, reply_markup=reply_markup)
            return

        # 3. Check if query is asking for player stats and matches multiple candidates or has moderate confidence
        if nrl_service.is_player_query(query):
            candidates = nrl_service.suggest_players(query, max_candidates=4)
            if candidates:
                top_key, top_data, top_score = candidates[0]
                is_ambiguous = (
                    len(candidates) > 1
                    and candidates[1][2] >= 0.80
                    and abs(top_score - candidates[1][2]) < 0.15
                )
                is_moderate_confidence = (0.75 <= top_score < 0.85)

                if is_ambiguous or is_moderate_confidence:
                    clean_name = nrl_service.extract_clean_player_name(query)
                    prompt_text = (
                        f"❓ I found multiple potential player matches for *'{clean_name}'*.\n"
                        f"Please select the player you intended:"
                    )
                    buttons = []
                    for p_key, p_data, score in candidates[:4]:
                        fn = p_data.get("full_name", p_key)
                        pos = p_data.get("position", "")
                        club = p_data.get("current_club", "NRL")
                        btn_label = f"🏉 {fn} — {pos} ({club})" if pos else f"🏉 {fn} ({club})"
                        buttons.append([InlineKeyboardButton(btn_label, callback_data=f"nrl_p:{p_key}")])

                    quality_service.log_interaction(
                        command="nrl",
                        user=update.effective_user,
                        query=query,
                        response=f"[Disambiguation Buttons Presented for '{clean_name}']",
                        sources=None
                    )
                    await update.effective_message.reply_text(
                        prompt_text,
                        parse_mode=constants.ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    return

        # 4. Check if query is asking for a specific player who needs on-demand compilation
        if nrl_service.is_player_query(query):
            matched_player = nrl_service.find_player_in_registry(query)
            if matched_player:
                p_key, p_data = matched_player
                has_stats = "season_stats_2026" in p_data or "career_stats" in p_data
                if not has_stats:
                    p_name = p_data.get("full_name", p_key.replace("_", " ").title())
                    interim_msg = await update.effective_message.reply_text(
                        f"⏳ *Retrieving official 2026 match & career stats for {p_name}...*\n"
                        f"_Please wait a few seconds while records are compiled._",
                        parse_mode=constants.ParseMode.MARKDOWN
                    )
                    ans = await nrl_service.query_specific_nrl(query)
                    rec_id = quality_service.log_interaction(
                        command="nrl",
                        user=update.effective_user,
                        query=query,
                        response=ans,
                        sources=None
                    )
                    reply_markup = None
                    if rec_id:
                        reply_markup = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                                InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                            ]
                        ])
                    try:
                        await interim_msg.edit_text(
                            ans,
                            parse_mode=constants.ParseMode.MARKDOWN,
                            reply_markup=reply_markup
                        )
                    except Exception as md_err:
                        logger.warning(f"Markdown formatting failed in edited /nrl ({md_err}), sending as plain text.")
                        await interim_msg.edit_text(
                            ans,
                            reply_markup=reply_markup
                        )
                    return

        # 5. Live accredited search or single high-confidence stats card
        ans = await nrl_service.query_specific_nrl(query)
        rec_id = quality_service.log_interaction(
            command="nrl",
            user=update.effective_user,
            query=query,
            response=ans,
            sources=None
        )
        reply_markup = None
        if rec_id:
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ])
        try:
            await update.effective_message.reply_text(
                ans,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as md_err:
            logger.warning(f"Markdown formatting failed in /nrl ({md_err}), sending as plain text.")
            await update.effective_message.reply_text(
                ans,
                reply_markup=reply_markup
            )

@track_kpi_command("sync_nrl")
async def sync_nrl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sync_nrl command for manual administrative synchronization of NRL rosters, ladders & briefing."""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return

    status_msg = await update.effective_message.reply_text("🔄 Initiating NRL round finalization & registry sync...")
    try:
        res = await nrl_service.sync_weekly_round_finalization()
        report = (
            f"🏉 **NRL Weekly Round & Registry Synchronization**\n"
            f"• **Status:** Successfully synchronized\n"
            f"• **Active Teams Loaded:** {res['teams_count']} (17 NRL Clubs + PNG Chiefs)\n"
            f"• **Active Players Registered:** {res['players_count']}\n"
            f"• **Season Phase:** {res['season_phase']}\n"
            f"• **Priority Briefing:** Refreshed with latest accredited sources\n"
            f"• **Timestamp:** {res['timestamp']}\n\n"
            f"✅ *All records grounded and verified.*"
        )
        quality_service.log_interaction(
            command="sync_nrl",
            user=update.effective_user,
            query="/sync_nrl",
            response=report,
            sources=None
        )
        await status_msg.edit_text(report, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error executing /sync_nrl: {e}")
        await status_msg.edit_text(f"❌ Error executing NRL synchronization: {e}")

# ==========================================
# Network Diagnostic Commands
# ==========================================

@track_kpi_command("ping")
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

@track_kpi_command("traceroute")
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

@track_kpi_command("dns")
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

@track_kpi_command("nmap")
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

@track_kpi_command("whois")
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

@track_kpi_command("http")
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

@track_kpi_command("ssl")
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

@track_kpi_command("ipinfo")
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

@track_kpi_command("ask")
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

    user = update.effective_user
    user_str = f"@{user.username} ({user.full_name}, ID: {user.id})" if user else f"User in chat {chat_id}"
    logger.info(f"[{user_str}] in chat {chat_id} asked AI: '{prompt[:100]}...'")

    # Record interaction & update user behavioral profile
    if user:
        try:
            profile_service.record_interaction(user, chat_id, prompt)
        except Exception as prof_err:
            logger.error(f"Error recording user profile interaction: {prof_err}")

    t_ai_start = time.time()
    ai_success = True
    try:
        search_results = None
        wiki_info = None

        is_tech = True
        custom_sys_prompt = None

        # 1. Check for Flight & Travel inquiries
        if flight_service.is_flight_query(prompt):
            is_tech = False
            logger.info(f"Identified flight schedule inquiry from chat {chat_id}: '{prompt}'")
            has_flight, search_results = await flight_service.get_flight_context(prompt)
        # 2. Check for NRL Rugby League inquiries
        elif nrl_service.is_nrl_query(prompt):
            is_tech = False
            custom_sys_prompt = NRL_VALIDATION_SYSTEM_PROMPT
            logger.info(f"Identified NRL rugby league inquiry from chat {chat_id}: '{prompt}'")
            search_results = await nrl_service.fetch_accredited_search(prompt)
        else:
            # 3. Check for Flavius VIP or Personal Identity inquiries
            persona_intent = persona_service.classify_persona_intent(prompt)
            if persona_intent == "FLAVIUS_VIP":
                is_tech = False
                logger.info(f"Identified Flavius VIP inquiry from chat {chat_id}: '{prompt}'")
                search_results = [persona_service.get_flavius_context()]
            elif persona_intent == "PERSONAL_IDENTITY":
                is_tech = False
                logger.info(f"Identified personal identity query from chat {chat_id}: '{prompt}'")
                # Try Wikipedia search for public figures (e.g. Alan Turing, Linus Torvalds)
                wiki_info = await search_wikipedia(prompt)
            else:
                # 4. Analyze technical vs general intent & fetch targeted info
                intent, search_results = await technical_service.get_technical_context(prompt)
                is_tech = (intent != "GENERAL_WEB")
                if search_results:
                    logger.info(f"Retrieved {len(search_results)} search sources for intent '{intent}' (is_tech={is_tech})")
                elif intent == "GENERAL_WEB":
                    # Fallback to Wikipedia only for general web queries when search yielded nothing
                    wiki_info = await search_wikipedia(prompt)
                    if wiki_info:
                        logger.info(f"Found Wikipedia reference: '{wiki_info['title']}' ({wiki_info['url']})")

        response_text = await llm.generate_response(
            prompt,
            context_messages=context_msgs,
            wiki_info=wiki_info,
            search_results=search_results,
            is_technical=is_tech,
            custom_system_prompt=custom_sys_prompt
        )

        rec_id = quality_service.log_interaction(
            command="ask",
            user=user,
            query=prompt,
            response=response_text,
            sources=search_results
        )
        reply_markup = None
        if rec_id:
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ])

        try:
            await message.reply_text(
                response_text,
                reply_to_message_id=message.message_id,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as md_err:
            logger.warning(f"Markdown formatting failed ({md_err}), sending as plain text.")
            await message.reply_text(
                response_text,
                reply_to_message_id=message.message_id,
                reply_markup=reply_markup
            )
    except Exception as ai_err:
        ai_success = False
        raise ai_err
    finally:
        stop_typing_event.set()
        typing_task.cancel()
        ai_duration_ms = (time.time() - t_ai_start) * 1000.0
        kpi_service.record_ai_query(
            user_id=user.id if user else None,
            prompt=prompt,
            duration_ms=ai_duration_ms,
            success=ai_success
        )

# ==========================================
# Quality Feedback Callback
# ==========================================

async def quality_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle thumbs up/down quality feedback button presses."""
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    if data == "none":
        await query.answer()
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[0] == "qf":
        verdict, rec_id = parts[1], parts[2]
        quality_service.record_user_verdict(rec_id, verdict)
        label = "Feedback: 👍 Accurate" if verdict == "yes" else "Feedback: 👎 Flagged for review"
        try:
            await query.answer("Thank you for your feedback!")
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="none")]])
            )
        except Exception as e:
            logger.warning(f"Failed to update quality feedback markup: {e}")

async def nrl_player_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle player selection from disambiguation / typo suggestion buttons."""
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    if data.startswith("nrl_p:"):
        p_key = data.split(":", 1)[1]
        player_data = nrl_service.player_registry.get("players", {}).get(p_key)
        if not player_data:
            match = nrl_service.find_player_in_registry(p_key)
            if match:
                player_data = match[1]
        if not player_data:
            await query.answer("Player record not found.")
            return

        has_stats = "season_stats_2026" in player_data or "career_stats" in player_data
        if not has_stats:
            p_name = player_data.get("full_name", p_key.replace("_", " ").title())
            try:
                await query.answer()
                await query.edit_message_text(
                    f"⏳ *Retrieving official 2026 match & career stats for {p_name}...*\n"
                    f"_Please wait a few seconds while records are compiled._",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning(f"Failed to send interim edit in button callback: {e}")

            resolved = await nrl_service.resolve_or_cache_player(p_key, force_fetch=True)
            if resolved:
                player_data = resolved

        card = nrl_service.format_player_stats_card(player_data)
        rec_id = quality_service.log_interaction(
            command="nrl",
            user=update.effective_user,
            query=f"[Selected Player] {player_data.get('full_name')}",
            response=card,
            sources=None
        )
        reply_markup = None
        if rec_id:
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 Yes", callback_data=f"qf:yes:{rec_id}"),
                    InlineKeyboardButton("👎 No", callback_data=f"qf:no:{rec_id}")
                ]
            ])
        try:
            await query.answer()
            await query.edit_message_text(
                card,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as md_err:
            logger.warning(f"Markdown formatting failed in player select callback ({md_err}), sending plain text.")
            await query.edit_message_text(
                card,
                reply_markup=reply_markup
            )

async def post_init(application: Application) -> None:
    """Run background scheduled tasks after bot startup."""
    async def _daily_worker():
        while True:
            try:
                await asyncio.sleep(86400)  # Every 24 hours
                logger.info("Triggering automated daily user profile assessment...")
                profile_service.assess_all_users()
                logger.info("Automated daily user profile assessment completed.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily user assessment worker: {e}")

    async def _kpi_heartbeat():
        while True:
            try:
                await asyncio.sleep(60)  # Refresh metrics every 60s
                kpi_service.export_kpi_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in KPI heartbeat worker: {e}")

    async def _nrl_worker():
        # Hourly background refresh of verified priority NRL briefing
        await asyncio.sleep(10)  # Initial wait on startup
        while True:
            try:
                logger.info("Triggering scheduled NRL priority briefing sync...")
                await nrl_service.refresh_priority_briefing()
                logger.info("NRL priority briefing sync completed.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in NRL background sync worker: {e}")
            await asyncio.sleep(3600)  # Every 1 hour

    async def _nrl_weekly_worker():
        # Monday automated weekly round finalization sync
        last_sync_date = None
        while True:
            try:
                now = datetime.now(timezone.utc)
                today_str = now.strftime("%Y-%m-%d")
                if now.weekday() == 0 and last_sync_date != today_str:
                    logger.info("Monday detected: triggering automated NRL weekly round finalization sync...")
                    await nrl_service.sync_weekly_round_finalization()
                    last_sync_date = today_str
                    logger.info("Automated Monday NRL sync completed successfully.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in NRL weekly sync worker: {e}")
            await asyncio.sleep(3600)  # Check every hour

    asyncio.create_task(_daily_worker())
    asyncio.create_task(_kpi_heartbeat())
    asyncio.create_task(_nrl_worker())
    asyncio.create_task(_nrl_weekly_worker())

def main() -> None:
    """Start the bot."""
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("ERROR: TELEGRAM_BOT_TOKEN is not set in .env!")
        sys.exit(1)

    # Initial export of KPI files
    kpi_service.export_kpi_files()

    logger.info("Initializing Telegram Bot Application...")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Informational & AI Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler(["nrl", "rugby"], nrl_command))
    app.add_handler(CommandHandler(["sync_nrl", "syncnrl"], sync_nrl_command))
    app.add_handler(CommandHandler(["movie", "movies", "imdb", "tmdb"], movie_command))
    app.add_handler(CommandHandler(["tv", "series"], tv_command))
    app.add_handler(CommandHandler(["flight", "flights"], flight_command))
    app.add_handler(CommandHandler(["place", "places", "venue", "locate"], place_command))
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

    # Quality Feedback Callback Handler
    app.add_handler(CallbackQueryHandler(quality_feedback_callback, pattern=r"^(qf:|none)"))

    # NRL Player Disambiguation Callback Handler
    app.add_handler(CallbackQueryHandler(nrl_player_select_callback, pattern=r"^nrl_p:"))

    # General Chat / Mention Message Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Bot started! Using LLM model: {config.OLLAMA_MODEL} with User Profiling & Live Diagnostic Tools")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

