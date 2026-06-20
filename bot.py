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
    maimport os
import re
import asyncio
import logging
import csv
import io
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)
from telegram.constants import ParseMode

# ====================== YOUR BOT TOKEN ======================
BOT_TOKEN = "8964738276:AAELG92LrYXWD1gDF6LCcXEXDMUUyFOHd9s"

# ====================== CONFIG ======================
class Config:
    BATCH_SIZE = 8
    DELAY = 4.2
    MAX_NUMBERS = 7000
    TIMEOUT = 28

config = Config()

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
logger.info("=== ULTIMATE WHATSAPP 4-CATEGORY CHECKER v4.0 STARTED ===")

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# ====================== CLASSES ======================
class Statistics:
    def __init__(self):
        self.total = 0
        self.used = 0
        self.banned = 0
        self.personal = 0
        self.unused = 0
        self.start_time = time.time()

    def add(self, cat: str):
        self.total += 1
        if cat == "used": self.used += 1
        elif cat == "banned": self.banned += 1
        elif cat == "personal": self.personal += 1
        else: self.unused += 1

    def summary(self):
        unused_pct = (self.unused / self.total * 100) if self.total > 0 else 0
        return (
            f"📊 **CHECKING RESULT**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Used Accounts     : {self.used}\n"
            f"🔴 Banned Accounts   : {self.banned}\n"
            f"🟡 Personal Accounts : {self.personal}\n"
            f"❌ **Clean Unused**   : {self.unused} ({unused_pct:.1f}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Numbers Checked: {self.total}"
        )

class FileParser:
    @staticmethod
    def extract_numbers(file_path: str, filename: str) -> List[str]:
        ext = os.path.splitext(filename.lower())[1]
        raw_numbers = []
        try:
            if ext == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_numbers = re.findall(r'\b\d{9,15}\b', f.read())
            elif ext == '.csv':
                df = pd.read_csv(file_path, header=None, dtype=str)
                for col in df.columns:
                    for cell in df[col]:
                        if pd.notna(cell):
                            raw_numbers.extend(re.findall(r'\b\d{9,15}\b', str(cell)))
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, header=None, dtype=str)
                for col in df.columns:
                    for cell in df[col]:
                        if pd.notna(cell):
                            raw_numbers.extend(re.findall(r'\b\d{9,15}\b', str(cell)))
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        # Clean and remove duplicates
        seen = set()
        cleaned = []
        for num in raw_numbers:
            clean_num = re.sub(r'\D', '', num)
            if len(clean_num) >= 10 and clean_num not in seen:
                seen.add(clean_num)
                cleaned.append(clean_num)
        return cleaned

class ResultExporter:
    @staticmethod
    def save(results: Dict[str, List[str]], timestamp: str):
        for category, numbers in results.items():
            if numbers:
                with open(f"{category.upper()}_{timestamp}.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(numbers))
        
        with open(f"FULL_REPORT_{timestamp}.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Number", "Category", "Checked_At"])
            for cat, nums in results.items():
                for num in nums:
                    writer.writerow([num, cat.upper(), timestamp])
        logger.info(f"Results saved with timestamp: {timestamp}")

# ====================== CORE CHECKER ======================
async def check_numbers_batch(numbers: List[str]) -> List[tuple]:
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
            return [tuple(x.strip().split(":", 1)) for x in data.split("|") if ":" in x]
        return [(num, "unused") for num in numbers]
    except Exception as e:
        logger.error(f"Node.js Error: {e}")
        return [(num, "unused") for num in numbers]

# ====================== TELEGRAM HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📤 Upload Number File", callback_data="upload")]]
    await update.message.reply_text(
        "🔥 **ULTIMATE WHATSAPP NUMBER CLASSIFIER**\n\n"
        "This bot will classify numbers into 4 categories:\n"
        "✅ **Used** - Active WhatsApp Account\n"
        "🔴 **Banned** - Permanently Banned\n"
        "🟡 **Personal** - Messenger Warning / Restricted\n"
        "❌ **Unused** - Clean (Best for New Account Creation)\n\n"
        "Upload your TXT, CSV or Excel file now!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def upload_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📤 **Please send your file**\n\n"
        "Supported: `.txt`, `.csv`, `.xlsx`, `.xls`\n"
        "Maximum 7000 numbers per file."
    )
    return 1

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    status_msg = await update.message.reply_text("📥 Downloading file...")

    try:
        ext = os.path.splitext(document.file_name)[1].lower()
        if ext not in ['.txt', '.csv', '.xlsx', '.xls']:
            await status_msg.edit_text("❌ Only TXT, CSV, XLSX files are supported!")
            return ConversationHandler.END

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file = await document.get_file()
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        numbers = FileParser.extract_numbers(tmp_path, document.file_name)
        os.unlink(tmp_path)

        if not numbers:
            await status_msg.edit_text("❌ No valid phone numbers found in file!")
            return ConversationHandler.END

        if len(numbers) > config.MAX_NUMBERS:
            numbers = numbers[:config.MAX_NUMBERS]
            await status_msg.edit_text(f"⚠️ Only first {config.MAX_NUMBERS} numbers will be checked.")

        stats = Statistics()
        results = {"used": [], "banned": [], "personal": [], "unused": []}

        await status_msg.edit_text(f"🚀 Starting check for **{len(numbers)}** numbers...\nPlease wait.")

        for i in range(0, len(numbers), config.BATCH_SIZE):
            batch = numbers[i:i + config.BATCH_SIZE]
            batch_results = await check_numbers_batch(batch)

            for number, status in batch_results:
                status = status.lower()
                if status in results:
                    results[status].append(number)
                    stats.add(status)
                else:
                    results["unused"].append(number)
                    stats.add("unused")

            if i % 16 == 0 or i + config.BATCH_SIZE >= len(numbers):
                await status_msg.edit_text(
                    f"🔄 **Checking in Progress...**\n\n{stats.summary()}\n\n"
                    f"Processed: {min(i + config.BATCH_SIZE, len(numbers))}/{len(numbers)}",
                    parse_mode=ParseMode.MARKDOWN
                )

            await asyncio.sleep(config.DELAY)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ResultExporter.save(results, timestamp)

        final_text = (
            f"✅ **CHECKING COMPLETED SUCCESSFULLY!**\n\n"
            f"{stats.summary()}\n\n"
            f"**Download your results below:**\n"
            f"`UNUSED` = Best numbers for creating new WhatsApp accounts."
        )

        keyboard = [
            [InlineKeyboardButton("❌ Download UNUSED (Best)", callback_data=f"download_unused_{timestamp}")],
            [InlineKeyboardButton("✅ Used", callback_data=f"download_used_{timestamp}"),
             InlineKeyboardButton("🔴 Banned", callback_data=f"download_banned_{timestamp}")],
            [InlineKeyboardButton("🟡 Personal", callback_data=f"download_personal_{timestamp}")]
        ]

        context.user_data['results'] = results
        context.user_data['timestamp'] = timestamp

        await status_msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.exception("Error in file processing")
        await status_msg.edit_text(f"❌ System Error: {str(e)}")
    return ConversationHandler.END

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    results = context.user_data.get('results', {})
    ts = context.user_data.get('timestamp', 'result')

    if "unused" in data:
        content = "\n".join(results.get("unused", []))
        caption = "❌ CLEAN UNUSED NUMBERS\nBest for creating new WhatsApp accounts"
        filename = f"UNUSED_BEST_{ts}.txt"
    elif "used" in data:
        content = "\n".join(results.get("used", []))
        caption = "✅ Used Numbers"
        filename = f"USED_{ts}.txt"
    elif "banned" in data:
        content = "\n".join(results.get("banned", []))
        caption = "🔴 Banned Numbers"
        filename = f"BANNED_{ts}.txt"
    elif "personal" in data:
        content = "\n".join(results.get("personal", []))
        caption = "🟡 Personal/Restricted Numbers"
        filename = f"PERSONAL_{ts}.txt"
    else:
        return

    await query.message.reply_document(
        document=io.BytesIO(content.encode('utf-8')),
        filename=filename,
        caption=caption
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_button, pattern="^upload$")],
        states={1: [MessageHandler(filters.Document.ALL, process_file)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download_"))

    logger.info("Bot is running on Railway with your token")
    print("🚀 Bot Started Successfully! (Token Loaded)")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()in()
