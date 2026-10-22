import io
import json
import logging
import pandas as pd
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# লগিং কনফিগারেশন
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# আপনার প্রদত্ত বটের টোকেন
BOT_TOKEN = "8862995521:AAFKJIP91fc9y7zkbv4zJvCfBd6AAUZlBW0"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 স্বাগতম! আমি OTP Matching Bot।\n\n"
        "📌 ধাপ ১: আপনার মূল অ্যাকাউন্ট ডেটা ফাইলটি পাঠান (.json বা .xlsx ফাইল)।"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name.lower()
    file_bytes = await file.download_as_bytearray()

    # ধাপ ১: মূল ফাইল রিসিভ ও রিড করা
    if "accounts_dict" not in context.user_data:
        try:
            accounts_dict = {}

            if file_name.endswith(".json"):
                data = json.loads(file_bytes.decode("utf-8"))
                for row in data:
                    num = str(row.get("email_or_phone", "")).strip()
                    pwd = str(row.get("password", "")).strip()
                    if num:
                        accounts_dict[num] = pwd

            elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
                df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
                phone_col, pwd_col = None, None

                for c in df.columns:
                    c_low = str(c).lower()
                    if any(key in c_low for key in ["phone", "email_or_phone", "number"]):
                        phone_col = c
                    elif any(key in c_low for key in ["password", "pass"]):
                        pwd_col = c

                if not phone_col or not pwd_col:
                    await update.message.reply_text("❌ ফাইলে ফোন নম্বর বা পাসওয়ার্ড কলাম খুঁজে পাওয়া যায়নি।")
                    return

                for _, row in df.iterrows():
                    num = str(row[phone_col]).strip()
                    pwd = str(row[pwd_col]).strip()
                    if num and num != "nan":
                        accounts_dict[num] = pwd
            else:
                await update.message.reply_text("❌ অনুগ্রহ করে .json অথবা .xlsx ফাইল আপলোড করুন।")
                return

            context.user_data["accounts_dict"] = accounts_dict
            await update.message.reply_text(
                f"✅ সফলভাবে {len(accounts_dict)} টি অ্যাকাউন্ট লোড হয়েছে!\n\n"
                "📌 ধাপ ২: এবার ওটিপি লিস্ট সরাসরি মেসেজে পেস্ট করুন অথবা `.txt` ফাইল পাঠান (ফরম্যাট: `number|otp`)।"
            )
            return

        except Exception as e:
            await update.message.reply_text(f"❌ ফাইল রিড করতে সমস্যা হয়েছে: {str(e)}")
            return

    # ধাপ ২: ওটিপি টেক্সট ফাইল পাঠালে
    if file_name.endswith(".txt"):
        otp_text = file_bytes.decode("utf-8", errors="ignore")
        await process_otp(otp_text, update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "accounts_dict" not in context.user_data:
        await update.message.reply_text("⚠️ প্রথমে মূল অ্যাকাউন্ট ফাইলটি (.json / .xlsx) আপলোড করুন।")
        return

    await process_otp(update.message.text, update, context)


async def process_otp(otp_text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts_dict = context.user_data.get("accounts_dict", {})
    lines = otp_text.strip().split("\n")

    otp_dict = {}
    for line in lines:
        if "|" in line:
            parts = line.strip().split("|", 1)
            otp_dict[parts[0].strip()] = parts[1].strip()

    if not otp_dict:
        await update.message.reply_text("❌ ওটিপির সঠিক ফরম্যাট পাওয়া যায়নি (ফরম্যাট হতে হবে: `number|otp`)।")
        return

    # Number|PASSWORD|OTP ফরম্যাটে ম্যাচিং
    matched_lines = []
    for num, otp in otp_dict.items():
        if num in accounts_dict:
            pwd = accounts_dict[num]
            matched_lines.append(f"{num}|{pwd}|{otp}")

    if not matched_lines:
        await update.message.reply_text(
            f"⚠️ চেক করা হয়েছে {len(otp_dict)} টি ওটিপি, কিন্তু আগের কোনো অ্যাকাউন্টের সাথে নম্বর মিলেনি।"
        )
        return

    # Text ফাইল তৈরি (In-memory)
    txt_content = "\n".join(matched_lines)
    output = io.BytesIO(txt_content.encode("utf-8"))
    output.seek(0)

    # ইউজারকে .txt ফাইল পাঠানো
    await update.message.reply_document(
        document=output,
        filename="matched_accounts.txt",
        caption=(
            f"🎉 ম্যাচ সম্পন্ন হয়েছে!\n\n"
            f"🔹 ইনপুট ওটিপি: {len(otp_dict)} টি\n"
            f"🔹 ম্যাচ হয়েছে: {len(matched_lines)} টি"
        )
    )

    context.user_data.clear()
    await update.message.reply_text("🔄 নতুন ডেটা প্রসেস করতে আবার নতুন অ্যাকাউন্ট ফাইল দিন।")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot চালু হয়েছে! টেলিগ্রামে গিয়ে মেসেজ দিন...")
    app.run_polling()


if __name__ == "__main__":
    main()