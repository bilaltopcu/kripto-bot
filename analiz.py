import os
# --- 🖥️ HEADLESS SERVER İÇİN GRAFİK MOTORU AYARI ---
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt

import ccxt
import pandas as pd
import asyncio
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# === 🔑 BOT TOKENINIZI BURAYA YAZIN ===
TELEGRAM_TOKEN = "8979697311:AAHAT1x9N9DbWUq9mvnzIqvajmpob0KOVRk"

# Aktif alarmları hafızada tutmak için bir sözlük
ALARMLAR = {}

# --- 🛰️ RENDER'IN BOTU UYUTMAMASI İÇİN WEB SUNUCUSU ---
class CanliTutucuServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("Bot aktif ve 7/24 calisiyor!", "utf-8"))

def web_sunucu_baslat():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), CanliTutucuServer)
    print(f"🛰️ Canlı tutucu web sunucusu {port} portunda başlatıldı.")
    server.serve_forever()

# --- 🧪 SAF PANDAS İLE İNDİKATÖR HESAPLAMA ---
def rsi_hesapla(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd_hesapla(series, fast=12, slow=26, signal=9):
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

# --- 1. Teknik Analiz ve Grafik Oluşturma Motoru ---
def analiz_ve_grafik_uret(coin_sembol):
    borsa = ccxt.binance({
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    coin_adi = coin_sembol.strip().replace(" ", "").upper()
    
    if coin_adi.endswith("USDT"):
        sembol = f"{coin_adi[:-4]}/USDT"
    else:
        sembol = f"{coin_adi}/USDT"
    
    try:
        borsa.load_markets()
        if sembol not in borsa.markets:
            print(f"❌ {sembol} Binance borsasında bulunamadı.")
            return None
            
        ticker = borsa.fetch_ticker(sembol)
        anlik_fiyat = ticker['last']
        hacim_24s = ticker['quoteVolume']
        fiyat_degisim = ticker['percentage']
        
        limit_mum = 250
        mumlar = borsa.fetch_ohlcv(sembol, timeframe='4h', limit=limit_mum)
        df = pd.DataFrame(mumlar, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        df['RSI'] = rsi_hesapla(df['close'], period=14)
        df['MACD'], df['MACD_Sinyal'] = macd_hesapla(df['close'])
        
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['STD20'] = df['close'].rolling(window=20).std()
        df['BB_Ust'] = df['MA20'] + (df['STD20'] * 2)
        df['BB_Alt'] = df['MA20'] - (df['STD20'] * 2)
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        df_grafik = df.iloc[-100:]
        
        # --- 📈 Grafik Çizimi ---
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [2, 1]})
        
        fig.patch.set_facecolor('#121212')
        ax1.set_facecolor('#121212')
        ax2.set_facecolor('#121212')
        
        ax1.plot(df_grafik['datetime'], df_grafik['close'], label='Fiyat', color='#00F5D4', linewidth=2)
        ax1.plot(df_grafik['datetime'], df_grafik['BB_Ust'], label='Bollinger Üst', color='#FF007F', linestyle='--', alpha=0.7)
        ax1.plot(df_grafik['datetime'], df_grafik['BB_Alt'], label='Bollinger Alt', color='#00B4D8', linestyle='--', alpha=0.7)
        ax1.fill_between(df_grafik['datetime'], df_grafik['BB_Alt'], df_grafik['BB_Ust'], color='#00B4D8', alpha=0.05)
        ax1.set_title(f"{sembol} - Canlı Teknik Grafik (4 Saatlik)", fontsize=14, color='white', weight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.1)
        ax1.tick_params(colors='white')
        
        ax2.plot(df_grafik['datetime'], df_grafik['RSI'], label='RSI (14)', color='#FFB703', linewidth=1.5)
        ax2.axhline(70, color='#FF007F', linestyle=':', alpha=0.8, label='Aşırı Alım (70)')
        ax2.axhline(30, color='#00B4D8', linestyle=':', alpha=0.8, label='Aşırı Satım (30)')
        ax2.fill_between(df_grafik['datetime'], 30, 70, color='#8338EC', alpha=0.05)
        ax2.set_ylim(10, 90)
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.1)
        ax2.tick_params(colors='white')
        
        plt.tight_layout()
        
        gorsel_yolu = io.BytesIO()
        plt.savefig(gorsel_yolu, format='png', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        gorsel_yolu.seek(0)
        plt.close(fig)
        
        return {
            "sembol": sembol,
            "anlik_fiyat": anlik_fiyat,
            "hacim_24s": hacim_24s,
            "fiyat_degisim": fiyat_degisim,
            "df": df,
            "grafik_bytes": gorsel_yolu
        }
    except Exception as e:
        print(f"⚠️ Binance Bağlantı Hatası: {e}")
        return None

# --- 2. Telegram Başlangıç ve Akıllı Mesaj Yakalayıcı ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *Kripto Yapay Zeka Karar Merkezine Hoş Geldiniz!*\n\n"
        "İstediğiniz coinin adını yazın, analizi ve grafiği hazırlayayım.\n"
        "Raporun altındaki butonla anında alarm da kurabilirsiniz!"
    )

async def metin_yakalayici(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = update.message.text.strip()
    if mesaj.startswith('/'):
        return

    bekleyen_coin = context.user_data.get('alarm_bekleyen_coin')
    
    if bekleyen_coin:
        try:
            temiz_fiyat_metni = mesaj.replace('.', '').replace(',', '') if ('.' in mesaj and ',' in mesaj or len(mesaj.split('.')) > 2) else mesaj.replace(',', '.')
            
            if '.' in mesaj and len(mesaj.split('.')[1]) == 3 and float(temiz_fiyat_metni) >= 1000:
                hedef_fiyat = float(temiz_fiyat_metni)
            else:
                hedef_fiyat = float(mesaj.replace(',', '.'))
                
            chat_id = update.effective_chat.id
            
            borsa = ccxt.binance()
            ticker = borsa.fetch_ticker(f"{bekleyen_coin.upper()}/USDT")
            guncel_fiyat = ticker['last']
            
            direction = "above" if hedef_fiyat > guncel_fiyat else "below"
            
            if bekleyen_coin not in ALARMLAR:
                ALARMLAR[bekleyen_coin] = []
                
            ALARMLAR[bekleyen_coin].append({
                "chat_id": chat_id,
                "target_price": hedef_fiyat,
                "direction": direction
            })
            
            await update.message.reply_text(f"*{mesaj}* için alarm oluşturuldu.")
            context.user_data.pop('alarm_bekleyen_coin', None)
            return
        except ValueError:
            await update.message.reply_text("⚠️ Lütfen sadece sayısal bir fiyat yazın!")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Bir Hata Oluştu: {e}")
            context.user_data.pop('alarm_bekleyen_coin', None)
            return

    coin_adi = mesaj.upper()
    veriler = analiz_ve_grafik_uret(coin_adi)
    if not veriler:
        await update.message.reply_text(f"❌ {coin_adi} için canlı veri alınamadı. Kodunun doğru olduğundan emin olun.")
        return
        
    context.user_data['secilen_coin'] = coin_adi
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 SPOT STRATEJİ", callback_data='spot'),
            InlineKeyboardButton("🟡 KALDIRAÇLI (FUTURES)", callback_data='futures')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📊 *{veriler['sembol']}* verileri ve canlı grafiği hazırlandı.\n"
        "Lütfen planladığınız işlem türünü seçin:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# --- 3. Karar Verme ve Rapor Gönderme Alanı ---
async def buton_tıklama_kontrolu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    islem_tipi = query.data
    coin_adi = context.user_data.get('secilen_coin')
    
    if islem_tipi == 'alarm_istegi':
        context.user_data['alarm_bekleyen_coin'] = coin_adi
        await query.message.reply_text(
            f"🔔 *{coin_adi.upper()} Fiyat Takibi*\n\n"
            f"Lütfen takip etmek istediğiniz hedef fiyatı doğrudan mesaj olarak yazıp gönderin:"
        )
        return
        
    if not coin_adi:
        await query.edit_message_text("⚠️ Oturum zaman aşımı. Lütfen coin adını tekrar yazın.")
        return
        
    await query.edit_message_text(f"⏳ {coin_adi} için derin teknik hesaplamalar yapılıyor...")
    
    veriler = analiz_ve_grafik_uret(coin_adi)
    if not veriler:
        await query.edit_message_text("❌ Kritik borsa hatası.")
        return
        
    df = veriler['df']
    anlik_fiyat = veriler['anlik_fiyat']
    guncel_rsi = df['RSI'].iloc[-1]
    destek_seviyesi = df['BB_Alt'].iloc[-1]
    direnc_seviyesi = df['BB_Ust'].iloc[-1]
    guncel_sma200 = df['SMA_200'].iloc[-1]
    
    ortak_analiz = (
        f"📊 *{veriler['sembol']} ANALİZ RAPORU*\n"
        f"----------------------------------------\n"
        f"💰 *Fiyat:* ${anlik_fiyat:.6f} | %{veriler['fiyat_degisim']:+.2f}\n"
        f"📉 *RSI (14):* {guncel_rsi:.2f}\n"
        f"🛡️ *Dinamik Destek:* ${destek_seviyesi:.6f}\n"
        f"🚀 *Dinamik Direnç:* ${direnc_seviyesi:.6f}\n"
        f"----------------------------------------\n"
    )
    
    if islem_tipi == 'spot':
        kisa_vade = "🟢 ALIŞ" if guncel_rsi < 40 else "🔴 SATIŞ" if guncel_rsi > 65 else "🟡 BEKLE"
        orta_vade = "🟢 ALIŞ" if anlik_fiyat <= destek_seviyesi * 1.02 else "🔴 SATIŞ" if anlik_fiyat >= direnc_seviyesi * 0.98 else "🟡 BEKLE"
        
        if pd.isna(guncel_sma200) or guncel_sma200 is None:
            uzun_vade = "🟡 BEKLE (Yetersiz Geçmiş Veri)"
        else:
            uzun_vade = "🟢 ALIŞ (Yükseliş Trendi)" if anlik_fiyat > guncel_sma200 else "🔴 SATIŞ (Baskı Var)"
        
        sl = anlik_fiyat * 0.95
        tp1 = anlik_fiyat * 1.08
        tp2 = anlik_fiyat * 1.15
        
        rapor = (
            f"{ortak_analiz}"
            f"⏱️ *Kısa Vade (1-3 G):* {kisa_vade}\n"
            f"📅 *Orta Vade (1-3 H):* {orta_vade}\n"
            f"⏳ *Uzun Vade (1-3 Ay):* {uzun_vade}\n\n"
            f"🎯 *ÖNERİLEN SPOT YATIRIM SEVİYELERİ:*\n"
            f"🟢 *Giriş Bölgesi:* Market fiyatından kademeli\n"
            f"🚨 *Stop-Loss (SL):* ${sl:.6f} (-5%)\n"
            f"🎯 *Hedef 1 (TP1):* ${tp1:.6f} (+8%)\n"
            f"🎯 *Hedef 2 (TP2):* ${tp2:.6f} (+15%)\n"
            f"----------------------------------------\n"
            f"⚠️ _Spot piyasada sabır her zaman kazandırır._"
        )
    else:
        if guncel_rsi < 35:
            yon = "🟢 LONG (Aşırı Satım & Tepki Beklentisi)"
            sl = anlik_fiyat * 0.98
            tp = anlik_fiyat * 1.05
            strateji = "Desteğe yakın bölgeden giriş."
        elif guncel_rsi > 65:
            yon = "🔴 SHORT (Aşırı Alım & Reddedilme)"
            sl = anlik_fiyat * 1.02
            tp = anlik_fiyat * 0.95
            strateji = "Dirençten sekme beklentisiyle giriş."
        else:
            yon = "🟡 NÖTR (Güvenli Alan Yok, İşlem Açmayın)"
            sl, tp = 0, 0
            strateji = "Sinyal oluşması bekleniyor."
            
        rapor = (
            f"{ortak_analiz}"
            f"🎯 *ÖNERİLEN KALDIRAÇ YÖNÜ:*\n"
            f"👉 *{yon}*\n\n"
            f"📝 *Strateji:* {strateji}\n"
        )
        if yon != "🟡 NÖTR (Güvenli Alan Yok, İşlem Açmayın)":
            rapor += (
                f"🚨 *Önerilen Stop-Loss (SL):* ${sl:.6f} (%2)\n"
                f"🎯 *Önerilen Kar Al (TP):* ${tp:.6f} (%5)\n"
            )
        rapor += (
            f"----------------------------------------\n"
            f"⚠️ *FUTURES RISK UYARISI:* Kaldıraçlı işlemler çok yüksek risk barındırır. "
            f"Düşük kaldıraç (3x-5x) kullanılması şiddetle önerilir."
        )
        
    alarm_keyboard = [
        [InlineKeyboardButton("🔔 BU COIN İÇİN ALARM KUR", callback_data='alarm_istegi')]
    ]
    reply_markup = InlineKeyboardMarkup(alarm_keyboard)
    
    await query.message.reply_photo(photo=veriler['grafik_bytes'], caption=rapor, reply_markup=reply_markup, parse_mode="Markdown")

# --- 3. Arka Plan Alarm İzleme Motoru ---
async def alarm_kontrol_dongusu(app: Application):
    borsa = ccxt.binance()
    while True:
        try:
            for coin in list(ALARMLAR.keys()):
                if not ALARMLAR[coin]:
                    continue
                    
                ticker = borsa.fetch_ticker(f"{coin.upper()}/USDT")
                guncel_fiyat = ticker['last']
                
                for alarm in ALARMLAR[coin][:]:
                    tetiklendi = False
                    if alarm['direction'] == 'above' and guncel_fiyat >= alarm['target_price']:
                        tetiklendi = True
                    elif alarm['direction'] == 'below' and guncel_fiyat <= alarm['target_price']:
                        tetiklendi = True
                        
                    if tetiklendi:
                        mesaj = f"🚨 *ALARM TETİKLENDİ!* \n\n🔔 {coin.upper()} fiyatı tam olarak beklentiniz olan *${alarm['target_price']}* seviyesine ulaştı! \n💰 Canlı fiyat: *${guncel_fiyat}*"
                        await app.bot.send_message(chat_id=alarm['chat_id'], text=mesaj, parse_mode="Markdown")
                        ALARMLAR[coin].remove(alarm)
            
        except Exception as e:
            print(f"Alarm döngüsü hatası: {e}")
        await asyncio.sleep(10)

# --- 🚀 ASYNCIO ARKA PLAN GÖREVLERİNİN BAŞLATILMASI ---
async def post_init(app: Application):
    # Arka plandaki alarm kontrol döngüsünü tamamen asenkron olarak güvenli başlatıyoruz
    asyncio.create_task(alarm_kontrol_dongusu(app))

# --- 🏁 ANA BAŞLANGIÇ NOKTASI (MAIN) ---
def main():
    # Web sunucusunu ayrı bir kanalda ayağa kaldırıyoruz (Render canlı tutsun diye)
    web_thread = threading.Thread(target=web_sunucu_baslat, daemon=True)
    web_thread.start()

    print("🤖 Akıllı Karar Destek Botu Ayaklanıyor... Tüm sistemler aktif!")
    
    # asyncio çakışmalarını tamamen ezen modern "Application" yapısı
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, metin_yakalayici))
    app.add_handler(CallbackQueryHandler(buton_tıklama_kontrolu))
    
    # run_polling() fonksiyonu artık kendi içinde event loop'u güvenle yönetir
    app.run_polling()

if __name__ == "__main__":
    main()
