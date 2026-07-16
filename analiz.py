# --- 1. Teknik Analiz ve Grafik Oluşturma Motoru (Güçlendirilmiş Bağlantı) ---
def analiz_ve_grafik_uret(coin_sembol):
    # Binance bağlantısına sunucu engellerini aşmak için timeout ve ek ayarlar ekliyoruz
    borsa = ccxt.binance({
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    # Kullanıcı boşluklu veya hatalı yazdıysa temizliyoruz
    coin_adi = coin_sembol.strip().replace(" ", "").upper()
    
    # Eğer kullanıcı BTCUSDT yazdıysa doğrudan kabul et, sadece BTC yazdıysa arkasına USDT ekle
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
        
        # Matematiksel Hesaplamalar
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
