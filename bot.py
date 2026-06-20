import os
import re
import asyncio
import logging
import csv
import io
import tempfile
import time
from datetime import datetime
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
BATCH_SIZE = 8
DELAY_BETWEEN_BATCH = 4.3
MAX_NUMBERS = 7000

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
logger.info("=== ULTIMATE WHATSAPP CHECKER v4.1 (Fixed) STARTED ===")

# ====================== CLASSES ======================
class Statistics:
    def __init__(self):
        self.total = 0
        self.used = 0
        self.banned = 0
        self.personal = 0
        self.unused = 0

    def add(self, category: str):
        self.total += 1
        if category == "used":
            self.used += 1
        elif category == "banned":
            self.banned += 1
        elif category == "personal":
            self.personal += 1
        else:
            self.unused += 1

    def get_summary(self) -> str:
        if self.total == 0:
            return "No data processed yet."
        unused_pct = (self.unused / self.total * 100)
        return (
            f"📊 **CHECK RESULT**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Used       : {self.used}\n"
            f"🔴 Banned     : {self.banned}\n"
            f"🟡 Personal   : {self.personal}\n"
            f"❌ **Unused (Best)** : {self.unused} ({unused_pct:.1f}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Checked : {self.total}"
        )

class FileParser:
    @staticmethod
    def extract_numbers(file_path: str, filename: str) -> List[str]:
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

# ====================== NODE.JS CHECKER ======================
async def check_batch(numbers: List[str]) -> List[tuple]:
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
            data = output.split("CHECK_RESULT:")[1].strip()
            return [tuple(item.split(":", 1)) for item in data.split("|") if ":" in item]
        logger.warning("No CHECK_RESULT found, returning all as unused")
        return [(n, "unused") for n in numbers]
    except Exception as e:
        logger.error(f"Node.js Error: {e}")
        return [(n, "unused") for n in numbers]

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📤 Upload Number File", callback_data="upload")]]
    await update.message.reply_text(
        "🔥 **ULTIMATE WhatsApp Number Classifier Bot**\n\n"
        "✅ Used Accounts\n"
        "🔴 Banned Accounts\n"
        "🟡 Personal/Restricted\n"
        "❌ **Unused (Best for New Account)**\n\n"
        "Upload your number list (TXT, CSV or Excel)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📤 এখন আপনার নম্বরের ফাইল পাঠান (TXT / CSV / XLSX):")
    return 1

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    status_msg = await update.message.reply_text("📥 ফাইল ডাউনলোড হচ্ছে...")

    try:
        ext = os.path.splitext(document.file_name)[1].lower()
        if ext not in ['.txt', '.csv', '.xlsx', '.xls']:
            await status_msg.edit_text("❌ শুধুমাত্র TXT, CSV, XLSX ফাইল সমর্থিত।")
            return ConversationHandler.END

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file = await document.get_file()
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        numbers = FileParser.extract_numbers(tmp_path, document.file_name)
        os.unlink(tmp_path)

        if not numbers:
            await status_msg.edit_text("❌ কোনো বৈধ নম্বর পাওয়া যায়নি!")
            return ConversationHandler.END

        if len(numbers) > MAX_NUMBERS:
            numbers = numbers[:MAX_NUMBERS]

        stats = Statistics()
        results = {"used": [], "banned": [], "personal": [], "unused": []}

        await status_msg.edit_text(f"🚀 **{len(numbers)}টি নম্বর চেক শুরু হচ্ছে...**")

        for i in range(0, len(numbers), BATCH_SIZE):
            batch = numbers[i:i + BATCH_SIZE]
            batch_results = await check_batch(batch)

            for number, status in batch_results:
                status = status.lower()
                if status in results:
                    results[status].append(number)
                    stats.add(status)
                else:
                    results["unused"].append(number)
                    stats.add("unused")

            if i % 12 == 0 or i + BATCH_SIZE >= len(numbers):
                await status_msg.edit_text(
                    f"🔄 **চেক চলছে...**\n\n{stats.get_summary()}\n\n"
                    f"প্রগ্রেস: {min(i + BATCH_SIZE, len(numbers))}/{len(numbers)}",
                    parse_mode=ParseMode.MARKDOWN
                )

            await asyncio.sleep(DELAY_BETWEEN_BATCH)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for cat, nums in results.items():
            if nums:
                with open(f"{cat.upper()}_{timestamp}.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(nums))

        final_text = (
            f"✅ **চেকিং সম্পূর্ণ হয়েছে!**\n\n"
            f"{stats.get_summary()}\n\n"
            f"**নিচের বাটনে ক্লিক করে ফাইল ডাউনলোড করুন**\n"
            f"`UNUSED` = নতুন WhatsApp অ্যাকাউন্ট তৈরির জন্য সবচেয়ে ভালো"
        )

        keyboard = [
            [InlineKeyboardButton("❌ UNUSED (Best)", callback_data=f"dl_unused_{timestamp}")],
            [InlineKeyboardButton("✅ Used", callback_data=f"dl_used_{timestamp}"),
             InlineKeyboardButton("🔴 Banned", callback_data=f"dl_banned_{timestamp}")],
            [InlineKeyboardButton("🟡 Personal", callback_data=f"dl_personal_{timestamp}")]
        ]

        context.user_data['results'] = results
        context.user_data['timestamp'] = timestamp

        await status_msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.exception("Error in process_file")
        await status_msg.edit_text(f"❌ সিস্টেম এরর: {str(e)}")
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
    logger.info("Bot starting with hardcoded token...")
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_callback, pattern="^upload$")],
        states={1: [MessageHandler(filters.Document.ALL, process_file)]},
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_"))

    logger.info("Bot is now running successfully!")
    print("🚀 Bot Started Successfully! Send /start in your bot.")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
