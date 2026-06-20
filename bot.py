import os
import re
import asyncio
import logging
import csv
import io
import json
import tempfile
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)
from telegram.constants import ParseMode

# ====================== CONFIG ======================
class ConfigManager:
    def __init__(self):
        self.BATCH_SIZE = int(os.getenv("BATCH_SIZE", 8))
        self.DELAY = float(os.getenv("DELAY", 4.5))
        self.MAX_NUMBERS = int(os.getenv("MAX_NUMBERS", 8000))
        self.TIMEOUT = int(os.getenv("TIMEOUT", 28))
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.OWNER_ID = int(os.getenv("OWNER_ID", 0))
        
    def is_owner(self, user_id: int) -> bool:
        return self.OWNER_ID == 0 or user_id == self.OWNER_ID

config = ConfigManager()

if not config.TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required!")

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler("whatsapp_checker.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("=== ULTIMATE WHATSAPP CHECKER v3.0 STARTED ===")

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# ====================== CLASSES ======================
class Statistics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.total = 0
        self.used = 0
        self.banned = 0
        self.personal = 0
        self.unused = 0
        self.start_time = time.time()

    def add(self, category: str):
        self.total += 1
        if category == "used": self.used += 1
        elif category == "banned": self.banned += 1
        elif category == "personal": self.personal += 1
        else: self.unused += 1

    def get_summary(self) -> str:
        if self.total == 0: return "No data"
        unused_pct = (self.unused / self.total * 100)
        return (
            f"📊 **STATISTICS**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Used: {self.used}\n"
            f"🔴 Banned: {self.banned}\n"
            f"🟡 Personal: {self.personal}\n"
            f"❌ **Unused (Best for New WA):** {self.unused} ({unused_pct:.1f}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total: {self.total}"
        )

class FileParser:
    @staticmethod
    def parse(file_path: str, filename: str) -> List[str]:
        ext = os.path.splitext(filename.lower())[1]
        numbers = []
        try:
            if ext == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    numbers = re.findall(r'\b\d{9,15}\b', f.read())
            elif ext == '.csv':
                df = pd.read_csv(file_path, header=None, dtype=str)
                for col in df.columns:
                    for val in df[col]:
                        if pd.notna(val):
                            numbers.extend(re.findall(r'\b\d{9,15}\b', str(val)))
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, header=None, dtype=str)
                for col in df.columns:
                    for val in df[col]:
                        if pd.notna(val):
                            numbers.extend(re.findall(r'\b\d{9,15}\b', str(val)))
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        seen = set()
        cleaned = []
        for n in numbers:
            clean = re.sub(r'\D', '', str(n))
            if len(clean) >= 10 and clean not in seen:
                seen.add(clean)
                cleaned.append(clean)
        return cleaned

class ResultExporter:
    @staticmethod
    def export(results: Dict[str, List[str]], timestamp: str):
        base = f"WA_Check_{timestamp}"
        for cat, nums in results.items():
            if nums:
                with open(f"{cat.upper()}_{base}.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(nums))
        
        with open(f"FULL_REPORT_{base}.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Number", "Category", "Checked_At"])
            for cat, nums in results.items():
                for num in nums:
                    writer.writerow([num, cat.upper(), timestamp])

class ProgressManager:
    def __init__(self, total: int, message):
        self.total = total
        self.processed = 0
        self.message = message
        self.start = time.time()

    async def update(self, batch_size: int, stats: Statistics):
        self.processed += batch_size
        percent = (self.processed / self.total) * 100
        elapsed = time.time() - self.start
        eta = ((self.total - self.processed) / (self.processed / elapsed)) if elapsed > 0 else 0

        text = (
            f"🔄 **WhatsApp Number Checker**\n\n"
            f"Progress: {self.processed}/{self.total} ({percent:.1f}%)\n"
            f"Time: {elapsed/60:.1f} min | ETA: {eta/60:.1f} min\n\n"
            f"{stats.get_summary()}"
        )
        try:
            await self.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        except:
            pass

# ====================== NODE.JS CHECKER ======================
async def check_batch(numbers: List[str]) -> List[Tuple[str, str]]:
    if not numbers:
        return []
    try:
        process = await asyncio.create_subprocess_exec(
            'node', 'checker.js', ','.join(numbers),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate(timeout=90)
        output = stdout.decode('utf-8', errors='ignore').strip()

        if "CHECK_RESULT:" in output:
            data = output.split("CHECK_RESULT:")[1]
            return [tuple(item.split(":", 1)) for item in data.split("|") if ":" in item]
        return [(n, "unused") for n in numbers]
    except Exception as e:
        logger.error(f"Checker error: {e}")
        return [(n, "unused") for n in numbers]

# ====================== MAIN BOT ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📤 Upload File (TXT/CSV/XLSX)", callback_data="upload")]]
    await update.message.reply_text(
        "🔥 **ULTIMATE WhatsApp Number Classifier**\n\n"
        "Detects 4 categories accurately:\n"
        "✅ Used • 🔴 Banned • 🟡 Personal • ❌ Unused\n\n"
        "Upload your number list now!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📤 Send your number file now (TXT, CSV or Excel):")
    return 1

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    msg = await update.message.reply_text("📥 Processing file...")

    try:
        ext = os.path.splitext(document.file_name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file = await document.get_file()
            await file.download_to_drive(tmp.name)
            path = tmp.name

        numbers = FileParser.parse(path, document.file_name)
        os.unlink(path)

        if not numbers:
            await msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        if len(numbers) > config.MAX_NUMBERS:
            numbers = numbers[:config.MAX_NUMBERS]

        stats = Statistics()
        progress = ProgressManager(len(numbers), msg)
        results = {"used": [], "banned": [], "personal": [], "unused": []}

        for i in range(0, len(numbers), config.BATCH_SIZE):
            batch = numbers[i:i+config.BATCH_SIZE]
            batch_results = await check_batch(batch)
            
            for num, status in batch_results:
                status = status.lower()
                if status in results:
                    results[status].append(num)
                    stats.add(status)
                else:
                    results["unused"].append(num)
                    stats.add("unused")
            
            await progress.update(len(batch), stats)
            await asyncio.sleep(config.DELAY)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ResultExporter.export(results, timestamp)

        final_text = f"✅ **CHECK COMPLETE!**\n\n{stats.get_summary()}\n\nDownload below:"

        keyboard = [
            [InlineKeyboardButton("❌ UNUSED (Best for New WA)", callback_data=f"dl_unused_{timestamp}")],
            [InlineKeyboardButton("✅ Used", callback_data=f"dl_used_{timestamp}"),
             InlineKeyboardButton("🔴 Banned", callback_data=f"dl_banned_{timestamp}")],
            [InlineKeyboardButton("🟡 Personal", callback_data=f"dl_personal_{timestamp}")]
        ]

        context.user_data['results'] = results
        context.user_data['ts'] = timestamp

        await msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.exception("Upload error")
        await msg.edit_text(f"❌ Error: {str(e)}")
    return ConversationHandler.END

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    results = context.user_data.get('results', {})
    ts = context.user_data.get('ts', 'result')

    if "unused" in data:
        content = "\n".join(results.get("unused", []))
        caption = "❌ CLEAN UNUSED NUMBERS\nBest for creating new WhatsApp accounts"
        fname = f"UNUSED_BEST_{ts}.txt"
    elif "used" in data:
        content = "\n".join(results.get("used", []))
        caption = "✅ Used Numbers"
        fname = f"USED_{ts}.txt"
    elif "banned" in data:
        content = "\n".join(results.get("banned", []))
        caption = "🔴 Banned Numbers"
        fname = f"BANNED_{ts}.txt"
    elif "personal" in data:
        content = "\n".join(results.get("personal", []))
        caption = "🟡 Personal/Restricted Numbers"
        fname = f"PERSONAL_{ts}.txt"
    else:
        return

    await query.message.reply_document(
        document=io.BytesIO(content.encode('utf-8')),
        filename=fname,
        caption=caption
    )

def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_callback, pattern="^upload$")],
        states={1: [MessageHandler(filters.Document.ALL, handle_upload)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_handler, pattern="^dl_"))

    logger.info("Bot started successfully on Railway")
    print("🚀 Ultimate WhatsApp Checker Bot is Running on Railway!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
