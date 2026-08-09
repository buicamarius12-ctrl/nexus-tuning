# --- SERVER WEB FLASK ---
app = Flask(__name__)

@app.route('/', methods=['GET', 'HEAD', 'POST'])
def home():
    return 'Botul Nexus Tuning este online!', 200

def run_flask():
    # Render alocă un port dinamic prin variabila PORT
    port = int(os.environ.get('PORT', 10000))
    try:
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    except Exception as e:
        print(f"❌ Eroare la pornirea Flask: {e}")

# Pornește Flask pe un thread separat înainte de bot
threading.Thread(target=run_flask, daemon=True).start()

# --- PORNIRE BOT DISCORD ---
TOKEN = os.environ.get('DISCORD_TOKEN')

if not TOKEN:
    print("❌ EROARE CRITICĂ: Variabila 'DISCORD_TOKEN' nu există în Render -> Environment!")
else:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ EROARE LA CONECTARE BOT DISCORD: {e}")
