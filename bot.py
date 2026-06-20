import os
import re
import csv
import time
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
)
from telegram.constants import ParseMode

# ====================== TOKEN ======================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8964738276:AAELG92LrYXWD1gDF6LCcXEXDMUUyFOHd9s"

# ====================== CONFIG ======================
UPLOAD_STATE = 1

class Config:
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 200))
    MAX_NUMBERS = int(os.getenv("MAX_NUMBERS", 7000))
    OWNER_ID = int(os.getenv("OWNER_ID", 0))

config = Config()

# ====================== PATHS ======================
BASE_DIR = Path(__file__).parent.resolve()
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

USED_FILE = BASE_DIR / "used_numbers.txt"
BANNED_FILE = BASE_DIR / "banned_numbers.txt"
PERSONAL_FILE = BASE_DIR / "personal_numbers.txt"

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("=== BOT STARTING ===")

# ====================== HELPERS ======================
def is_authorized(user_id: int) -> bool:
    return config.OWNER_ID == 0 or user_id == config.OWNER_ID

def normalize_number(num: str) -> str:
    num = re.sub(r"\D", "", str(num or ""))
    if not num:
        return ""

    if num.startswith("0"):
        num = "62" + num[1:]
    elif num.startswith("8"):
        num = "62" + num

    return num

def is_valid_number(num: str) -> bool:
    return num.isdigit() and 9 <= len(num) <= 15

def load_number_set(path: Path) -> set:
    if not path.exists():
        return set()

    output = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            n = normalize_number(line.strip())
            if is_valid_number(n):
                output.add(n)
    return output

def save_txt(path: Path, rows: List[str]):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))

def save_csv(path: Path, rows: List[str], header="Phone Number"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([header])
        for r in rows:
            writer.writerow([r])

# ====================== FILE PARSER ======================
class FileParser:
    @staticmethod
    def parse(file_path: str, filename: str) -> List[str]:
        ext = os.path.splitext(filename.lower())[1]
        raw_numbers = []

        try:
            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                    raw_numbers = re.findall(r"\+?\d[\d\s\-\(\)]{7,20}\d", text)

            elif ext == ".csv":
                df = pd.read_csv(file_path, header=None, dtype=str, on_bad_lines="skip")
                for col in df.columns:
                    for val in df[col]:
                        if pd.notna(val):
                            raw_numbers.extend(re.findall(r"\+?\d[\d\s\-\(\)]{7,20}\d", str(val)))

            elif ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path, header=None, dtype=str)
                for col in df.columns:
                    for val in df[col]:
                        if pd.notna(val):
                            raw_numbers.extend(re.findall(r"\+?\d[\d\s\-\(\)]{7,20}\d", str(val)))

        except Exception:
            logger.exception("Parse error")
            return []

        seen = set()
        cleaned = []

        for raw in raw_numbers:
            num = normalize_number(raw)
            if is_valid_number(num) and num not in seen:
                seen.add(num)
                cleaned.append(num)

        return cleaned

# ====================== STATS ======================
class Statistics:
    def __init__(self):
        self.total = 0
        self.used = 0
        self.banned = 0
        self.personal = 0
        self.unused = 0
        self.started = time.time()

    def add(self, cat: str):
        self.total += 1
        if cat == "used":
            self.used += 1
        elif cat == "banned":
            self.banned += 1
        elif cat == "personal":
            self.personal += 1
        else:
            self.unused += 1

    def summary(self) -> str:
        unused_pct = (self.unused / self.total * 100) if self.total else 0
        return (
            f"📊 *CHECK RESULT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Used: {self.used}\n"
            f"🔴 Banned: {self.banned}\n"
            f"🟡 Personal: {self.personal}\n"
            f"❌ Unused: {self.unused} ({unused_pct:.1f}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total: {self.total}"
        )

# ====================== CLASSIFIER ======================
def classify_numbers(numbers: List[str]) -> Dict[str, List[str]]:
    used_set = load_number_set(USED_FILE)
    banned_set = load_number_set(BANNED_FILE)
    personal_set = load_number_set(PERSONAL_FILE)

    results = {
        "used": [],
        "banned": [],
        "personal": [],
        "unused": []
    }

    for num in numbers:
        if num in banned_set:
            results["banned"].append(num)
        elif num in personal_set:
            results["personal"].append(num)
        elif num in used_set:
            results["used"].append(num)
        else:
            results["unused"].append(num)

    return results

# ====================== EXPORTER ======================
class ResultExporter:
    @staticmethod
    def export(results: Dict[str, List[str]], timestamp: str) -> Dict[str, str]:
        export_paths = {}

        for cat, nums in results.items():
            txt_path = TEMP_DIR / f"{cat.upper()}_{timestamp}.txt"
            csv_path = TEMP_DIR / f"{cat.upper()}_{timestamp}.csv"

            save_txt(txt_path, nums)
            save_csv(csv_path, nums)

            export_paths[f"{cat}_txt"] = str(txt_path)
            export_paths[f"{cat}_csv"] = str(csv_path)

        full_csv = TEMP_DIR / f"FULL_REPORT_{timestamp}.csv"
        with open(full_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Number", "Category", "Checked_At"])
            for cat, nums in results.items():
                for num in nums:
                    writer.writerow([num, cat.upper(), timestamp])

        export_paths["full_csv"] = str(full_csv)
        return export_paths

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    keyboard = [
        [InlineKeyboardButton("📤 Upload File (TXT/CSV/XLSX)", callback_data="upload")]
    ]

    await update.message.reply_text(
        "🔥 *ULTIMATE NUMBER CLASSIFIER BOT*\n\n"
        "Categories:\n"
        "✅ Used\n"
        "🔴 Banned\n"
        "🟡 Personal\n"
        "❌ Unused\n\n"
        "Tap below to upload your file.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📤 Send your file now.\n\n"
        "Supported:\n"
        "• TXT\n"
        "• CSV\n"
        "• XLSX / XLS\n\n"
        f"Max numbers: {config.MAX_NUMBERS}"
    )
    return UPLOAD_STATE

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END

    document = update.message.document
    if not document:
        await update.message.reply_text("❌ No document found.")
        return ConversationHandler.END

    msg = await update.message.reply_text("📥 Downloading and processing file...")

    try:
        ext = os.path.splitext(document.file_name)[1].lower()
        if ext not in [".txt", ".csv", ".xlsx", ".xls"]:
            await msg.edit_text("❌ Unsupported file type.")
            return ConversationHandler.END

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tg_file = await document.get_file()
            await tg_file.download_to_drive(tmp.name)
            temp_path = tmp.name

        numbers = FileParser.parse(temp_path, document.file_name)

        try:
            os.unlink(temp_path)
        except:
            pass

        if not numbers:
            await msg.edit_text("❌ No valid numbers found in file.")
            return ConversationHandler.END

        if len(numbers) > config.MAX_NUMBERS:
            numbers = numbers[:config.MAX_NUMBERS]

        await msg.edit_text(f"🚀 Started checking *{len(numbers)}* numbers...", parse_mode=ParseMode.MARKDOWN)

        all_results = classify_numbers(numbers)
        stats = Statistics()
        results = {
            "used": [],
            "banned": [],
            "personal": [],
            "unused": []
        }

        processed = 0
        for cat in ["used", "banned", "personal", "unused"]:
            for num in all_results[cat]:
                results[cat].append(num)
                stats.add(cat)
                processed += 1

                if processed % config.BATCH_SIZE == 0 or processed == len(numbers):
                    await msg.edit_text(
                        f"🔄 *Checking in progress...*\n\n"
                        f"{stats.summary()}\n\n"
                        f"Processed: {processed}/{len(numbers)}",
                        parse_mode=ParseMode.MARKDOWN
                    )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = ResultExporter.export(results, timestamp)

        context.user_data["results"] = results
        context.user_data["timestamp"] = timestamp
        context.user_data["files"] = files

        keyboard = [
            [InlineKeyboardButton("❌ Download UNUSED", callback_data="download_unused_txt")],
            [InlineKeyboardButton("✅ Download USED", callback_data="download_used_txt")],
            [InlineKeyboardButton("🔴 Download BANNED", callback_data="download_banned_txt")],
            [InlineKeyboardButton("🟡 Download PERSONAL", callback_data="download_personal_txt")],
            [InlineKeyboardButton("📄 Download FULL CSV REPORT", callback_data="download_full_csv")]
        ]

        await msg.edit_text(
            f"✅ *CHECK COMPLETE!*\n\n{stats.summary()}\n\nDownload your result files below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.exception("handle_upload error")
        await msg.edit_text(f"❌ Error: {str(e)}")

    return ConversationHandler.END

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    files = context.user_data.get("files", {})
    data = query.data

    mapping = {
        "download_used_txt": "used_txt",
        "download_banned_txt": "banned_txt",
        "download_personal_txt": "personal_txt",
        "download_unused_txt": "unused_txt",
        "download_full_csv": "full_csv",
    }

    key = mapping.get(data)
    if not key or key not in files:
        await query.message.reply_text("❌ File not found.")
        return

    path = files[key]
    if not os.path.exists(path):
        await query.message.reply_text("❌ Saved file missing.")
        return

    with open(path, "rb") as f:
        await query.message.reply_document(
            document=f,
            filename=os.path.basename(path),
            caption=f"📁 {os.path.basename(path)}"
        )

# ====================== MAIN ======================
def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is missing")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_callback, pattern="^upload$")],
        states={
            UPLOAD_STATE: [MessageHandler(filters.Document.ALL, handle_upload)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_handler, pattern="^download_"))

    logger.info("Bot started successfully")
    print("🚀 Bot started successfully. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
