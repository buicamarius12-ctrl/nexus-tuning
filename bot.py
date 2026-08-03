import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# Importăm baza de date și views (dacă există în proiectul tău)
try:
    from database import init_db, start_pontaj_user, stop_pontaj_user, get_ore_user, reset_all_pontaje
except ImportError:
    pass

# --- 1. SERVER WEB PENTRU KEEP-ALIVE PE RENDER ---
app = Flask('')

@app.route('/')
def home():
    return 'Botul Nexus Tuning este online 24/7!'

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Pornim serverul Flask pe un fir de execuție secundar
threading.Thread(target=run_flask, daemon=True).start()

# --- 2. CONFIGURARE BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- 3. DEFINIRE VIEW PENTRU BUTOANE (CU DEFER ANTERIOR) ---
class PontajView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Intra In Tura", style=discord.ButtonStyle.green, custom_id="intra_tura_btn")
    async def intra_tura(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Confirmăm instant interacțiunea ca să nu dea eroare "nu a răspuns la timp"
        await interaction.response.defer(ephemeral=True)
        try:
            # Apelăm funcția din baza de date
            start_pontaj_user(interaction.user.id)
            await interaction.followup.send("🟢 **Ai intrat în tură cu succes!** Spor la treabă!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ **Eroare:** {e}", ephemeral=True)

    @discord.ui.button(label="Iesi Din Tura", style=discord.ButtonStyle.red, custom_id="iesi_tura_btn")
    async def iesi_tura(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            ore, minute = stop_pontaj_user(interaction.user.id)
            if ore is not None:
                await interaction.followup.send(f"🔴 **Ai ieșit din tură!** Ai lucrat **{ore}h și {minute}m**.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Nu erai înregistrat ca fiind în tură!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ **Eroare:** {e}", ephemeral=True)

    @discord.ui.button(label="Vezi Orele Tale", style=discord.ButtonStyle.blurple, custom_id="vezi_ore_btn")
    async def vezi_ore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            total_ore, total_minute = get_ore_user(interaction.user.id)
            await interaction.followup.send(f"📊 **Total ore lucrate:** {total_ore}h și {total_minute}m.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"📊 **Total ore lucrate:** 0h și 0m.", ephemeral=True)

# --- 4. EVENIMENT LA PORNIRE ---
@bot.event
async def on_ready():
    # Inițializăm baza de date la pornire
    try:
        init_db()
    except Exception:
        pass
    
    # Sincronizăm comenzile slash (/)
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sincronizat cu succes {len(synced)} comenzi slash!")
    except Exception as e:
        print(f"❌ Eroare la sincronizarea comenzilor: {e}")

    print(f"🤖 Botul este online și conectat ca {bot.user}!")

# --- 5. COMENZI SLASH ---
@bot.tree.command(name="setup_pontaj", description="Trmite panoul principal pentru pontaj mecanici")
async def setup_pontaj(interaction: discord.Interaction):
    # Răspundem instant Discord-ului ca să nu apară "Aplicația nu a răspuns"
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="🛠️ Nexus Tuning — Pontaj Mecanici",
        description=(
            "Bine ai venit în tura ta la **Nexus Tuning**! 🏎️💨\n\n"
            "Folosește butoanele de mai jos pentru a-ți gestiona timpul petrecut în atelier:\n\n"
            "🟢 **Intră în tură** — Pornește ceasul când intri în atelier.\n"
            "🔴 **Ieși din tură** — Oprește pontajul la finalul programului.\n"
            "📊 **Vezi orele tale** — Verifică totalul de ore lucrate la Tuning."
        ),
        color=discord.Color.teal()
    )
    embed.set_footer(text="Nexus Tuning • Keep tuning, keep driving! 🛠️")
    
    # Trimitem mesajul public cu panoul
    await interaction.channel.send(embed=embed, view=PontajView())
    await interaction.followup.send("Panoul de pontaj a fost trimis cu succes pe canal!", ephemeral=True)

# --- 6. PORNIRE BOT ---
TOKEN = os.environ.get('DISCORD_TOKEN')

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ EROARE CRITICĂ: Variabila DISCORD_TOKEN nu a fost găsită în Render!")
