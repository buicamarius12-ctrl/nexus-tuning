import os
import threading
from datetime import datetime
from flask import Flask
import discord
from discord.ext import commands

# --- 1. BAZĂ DE DATE SIMPLĂ ÎN MEMORIE PENTRU PONTAJ ---
active_shifts = {}  # {user_id: start_time}
user_hours = {}     # {user_id: total_seconds}

def start_pontaj_user(user_id):
    if user_id in active_shifts:
        raise Exception("Ești deja în tură! Ieși mai întâi din tura curentă.")
    active_shifts[user_id] = datetime.now()

def stop_pontaj_user(user_id):
    if user_id not in active_shifts:
        return None, None
    
    start_time = active_shifts.pop(user_id)
    duration = datetime.now() - start_time
    seconds_worked = int(duration.total_seconds())
    
    user_hours[user_id] = user_hours.get(user_id, 0) + seconds_worked
    
    hours = seconds_worked // 3600
    minutes = (seconds_worked % 3600) // 60
    return hours, minutes

def get_ore_user(user_id):
    total_seconds = user_hours.get(user_id, 0)
    
    if user_id in active_shifts:
        current_duration = datetime.now() - active_shifts[user_id]
        total_seconds += int(current_duration.total_seconds())
        
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes

def reset_all_pontaje():
    active_shifts.clear()
    user_hours.clear()

# --- 2. SERVER WEB PENTRU KEEP-ALIVE PE RENDER ---
app = Flask('')

@app.route('/')
def home():
    return 'Botul Nexus Tuning este online 24/7!'

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- 3. CONFIGURARE BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- 4. PANOU CU BUTOANE ---
class PontajView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Intra In Tura", style=discord.ButtonStyle.green, custom_id="intra_tura_btn")
    async def intra_tura(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            start_pontaj_user(interaction.user.id)
            await interaction.followup.send("🟢 **Ai intrat în tură cu succes!** Spor la treabă!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ **Notificare:** {e}", ephemeral=True)

    @discord.ui.button(label="Iesi Din Tura", style=discord.ButtonStyle.red, custom_id="iesi_tura_btn")
    async def iesi_tura(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            ore, minute = stop_pontaj_user(interaction.user.id)
            if ore is not None:
                await interaction.followup.send(f"🔴 **Ai ieșit din tură!** Ai lucrat **{ore}h și {minute}m** în această tură.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Nu ești înregistrat ca fiind în tură!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ **Notificare:** {e}", ephemeral=True)

    @discord.ui.button(label="Vezi Orele Tale", style=discord.ButtonStyle.blurple, custom_id="vezi_ore_btn")
    async def vezi_ore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        total_ore, total_minute = get_ore_user(interaction.user.id)
        await interaction.followup.send(f"📊 **Total ore lucrate:** {total_ore}h și {total_minute}m.", ephemeral=True)

# --- 5. EVENIMENT LA PORNIRE ---
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sincronizat cu succes {len(synced)} comenzi slash!")
    except Exception as e:
        print(f"❌ Eroare la sincronizare: {e}")

    print(f"🤖 Botul este online și conectat ca {bot.user}!")

# --- 6. COMENZI SLASH ---

@bot.tree.command(name="setup_pontaj", description="Trimite panoul principal pentru pontaj mecanici")
async def setup_pontaj(interaction: discord.Interaction):
    await interaction.response.defer()
    
    embed = discord.Embed(
        title="🛠️ Nexus Tuning — Pontaj Mecanici",
        description=(
            "Bine ai venit în tura ta la **Nexus Tuning**! 🏎️💨\n\n"
            "Folosește butoanele de mai jos pentru a-ți gestiona timpul petrecut în atelier:\n\n"
            "🟢 **Intră în tură** — Pornește ceasul când intri în atelier.\n"
            "🔴 **Ieși din tură** — Oprește pontajul la finalul programului.\n"
            "📊 **Vezi orele tale** — Verifică totalul de ore lucrate."
        ),
        color=discord.Color.teal()
    )
    embed.set_footer(text="Nexus Tuning • Keep tuning, keep driving! 🛠️")
    
    await interaction.followup.send(embed=embed, view=PontajView())

@bot.tree.command(name="pontaje", description="Trimite lista cu pontajele tuturor mecanicilor în mesaj privat (DM)")
async def pontaje(interaction: discord.Interaction):
    # Preluăm comanda doar pentru cel care a executat-o (ephemeral)
    await interaction.response.defer(ephemeral=True)
    
    all_users = set(user_hours.keys()).union(set(active_shifts.keys()))
    
    if not all_users:
        await interaction.followup.send("📋 **Nu există niciun pontaj înregistrat momentan!**", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Lista Pontaje — Nexus Tuning",
        description="Mai jos regăsești situația tuturor mecanicilor:",
        color=discord.Color.gold()
    )

    lista_text = ""
    for user_id in all_users:
        ore, minute = get_ore_user(user_id)
        status = "🟢 în tură" if user_id in active_shifts else "🔴 Off"
        lista_text += f"• <@{user_id}> [{status}] — **{ore}h {minute}m**\n"

    embed.add_field(name="Mecanici Pontați", value=lista_text, inline=False)
    embed.set_footer(text="Nexus Tuning • Raport generat automat")

    try:
        # Încercăm să trimitem în DM (mesaj privat)
        await interaction.user.send(embed=embed)
        await interaction.followup.send("📩 **Lista de pontaje ți-a fost trimisă în mesaj privat (DM)!**", ephemeral=True)
    except discord.Forbidden:
        # În caz că utilizatorul are mesajele private închise
        await interaction.followup.send("⚠️ Nu am putut să-ți trimit mesaj privat. Verifică dacă ai opțiunea 'Allow Direct Messages' activată pe server!", ephemeral=True)

@bot.tree.command(name="stop_pontaj_user", description="Oprește forțat tura unui mecanic")
async def stop_pontaj_user_cmd(interaction: discord.Interaction, user: discord.Member, salveaza_orele: bool = True):
    await interaction.response.defer(ephemeral=True)
    
    if user.id not in active_shifts:
        await interaction.followup.send(f"⚠️ {user.mention} nu este în tură în acest moment.", ephemeral=True)
        return

    if salveaza_orele:
        ore, minute = stop_pontaj_user(user.id)
        await interaction.followup.send(f"🔴 **Pontaj oprit forțat!** I s-a oprit tura lui {user.mention}. I s-au salvat **{ore}h și {minute}m**.", ephemeral=True)
    else:
        active_shifts.pop(user.id, None)
        await interaction.followup.send(f"🚫 **Pontaj anulat complet!** Tura activă a lui {user.mention} a fost ștearsă fără salvare.", ephemeral=True)

@bot.tree.command(name="reset_pontaje", description="Resetează toate pontajele din baza de date")
async def reset_pontaje(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    reset_all_pontaje()
    await interaction.followup.send("🧹 **Toate pontajele au fost șterse cu succes!**", ephemeral=True)

# --- 7. PORNIRE BOT ---
TOKEN = os.environ.get('DISCORD_TOKEN')

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ EROARE: Variabila DISCORD_TOKEN nu a fost găsită!")
