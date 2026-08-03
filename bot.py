import os
import sqlite3
import threading
from datetime import datetime
from flask import Flask
import discord
from discord.ext import commands

# Numele rolului permis
ROL_PERMIS = "pontaje"

# --- 1. BAZĂ DE DATE SQLITE (STABILĂ) ---
DB_FILE = "pontaj.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_shifts (
            user_id INTEGER PRIMARY KEY,
            start_time TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_hours (
            user_id INTEGER PRIMARY KEY,
            total_seconds INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def start_pontaj_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT start_time FROM active_shifts WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        conn.close()
        raise Exception("Ești deja în tură! Ieși mai întâi din tura curentă.")
    
    now_str = datetime.now().isoformat()
    cursor.execute("INSERT INTO active_shifts (user_id, start_time) VALUES (?, ?)", (user_id, now_str))
    conn.commit()
    conn.close()

def stop_pontaj_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT start_time FROM active_shifts WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None, None
    
    start_time = datetime.fromisoformat(row[0])
    duration = datetime.now() - start_time
    seconds_worked = int(duration.total_seconds())
    
    cursor.execute("DELETE FROM active_shifts WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO user_hours (user_id, total_seconds) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET total_seconds = total_seconds + ?", (user_id, seconds_worked, seconds_worked))
    
    conn.commit()
    conn.close()
    
    hours = seconds_worked // 3600
    minutes = (seconds_worked % 3600) // 60
    return hours, minutes

def get_ore_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT total_seconds FROM user_hours WHERE user_id = ?", (user_id,))
    row_hours = cursor.fetchone()
    total_seconds = row_hours[0] if row_hours else 0
    
    cursor.execute("SELECT start_time FROM active_shifts WHERE user_id = ?", (user_id,))
    row_shift = cursor.fetchone()
    if row_shift:
        start_time = datetime.fromisoformat(row_shift[0])
        current_duration = datetime.now() - start_time
        total_seconds += int(current_duration.total_seconds())
        
    conn.close()
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes

def reset_all_pontaje():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_shifts")
    cursor.execute("DELETE FROM user_hours")
    conn.commit()
    conn.close()

def get_all_active_shifts():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, start_time FROM active_shifts")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: datetime.fromisoformat(row[1]) for row in rows}

def get_all_users_with_records():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_hours UNION SELECT user_id FROM active_shifts")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def are_rolul_permis(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.name.lower() == ROL_PERMIS.lower() for role in interaction.user.roles)

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
    bot.add_view(PontajView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sincronizat cu succes {len(synced)} comenzi slash!")
    except Exception as e:
        print(f"❌ Eroare la sincronizare: {e}")

    print(f"🤖 Botul este online și conectat ca {bot.user}!")

# --- 6. COMENZI SLASH ---

@bot.tree.command(name="setup_pontaj", description="Trimite panoul principal pentru pontaj mecanici")
async def setup_pontaj(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not are_rolul_permis(interaction):
        await interaction.followup.send(f"⚠️ **Acces interzis!** Ai nevoie de rolul `{ROL_PERMIS}` pentru această comandă.", ephemeral=True)
        return

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
    
    # Trimitem pe canal mesajul public cu panoul
    await interaction.channel.send(embed=embed, view=PontajView())
    await interaction.followup.send("✅ Panoul a fost postat pe canal cu succes!", ephemeral=True)

@bot.tree.command(name="pontaje", description="Trimite lista cu orele totale ale mecanicilor în privat (DM)")
async def pontaje(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not are_rolul_permis(interaction):
        await interaction.followup.send(f"⚠️ **Acces interzis!** Ai nevoie de rolul `{ROL_PERMIS}` pentru această comandă.", ephemeral=True)
        return
    
    all_users = get_all_users_with_records()
    active_shifts = get_all_active_shifts()
    
    if not all_users:
        await interaction.followup.send("📋 **Nu există niciun pontaj înregistrat momentan!**", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Istoric Pontaje — Nexus Tuning",
        description="Mai jos regăsești situația orei totale lucrate:",
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
        await interaction.user.send(embed=embed)
        await interaction.followup.send("📩 **Lista totală ți-a fost trimisă în privat (DM)!**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Deschide mesajele private (DM) din setările Discord!", ephemeral=True)

@bot.tree.command(name="ture_active", description="Trimite lista cu mecanicii aflați ÎN TURĂ ACUM în privat (DM)")
async def ture_active(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not are_rolul_permis(interaction):
        await interaction.followup.send(f"⚠️ **Acces interzis!** Ai nevoie de rolul `{ROL_PERMIS}` pentru această comandă.", ephemeral=True)
        return
    
    active_shifts = get_all_active_shifts()
    if not active_shifts:
        await interaction.followup.send("🟢 **În acest moment NU există niciun mecanic în tură!**", ephemeral=True)
        return

    embed = discord.Embed(
        title="🟢 Mecanici Active în Tură — Nexus Tuning",
        description="Acești mecanici lucrează în atelier chiar acum:",
        color=discord.Color.green()
    )

    lista_text = ""
    acum = datetime.now()
    for user_id, start_time in active_shifts.items():
        durata = acum - start_time
        secunde = int(durata.total_seconds())
        ore = secunde // 3600
        minute = (secunde % 3600) // 60
        ora_intrare = start_time.strftime("%H:%M")
        
        lista_text += f"• <@{user_id}> — Intrat la ora **{ora_intrare}** (Timp activ: **{ore}h {minute}m**)\n"

    embed.add_field(name="În Tură Acum", value=lista_text, inline=False)
    embed.set_footer(text="Nexus Tuning • Monitorizare live")

    try:
        await interaction.user.send(embed=embed)
        await interaction.followup.send("📩 **Lista turelor active ți-a fost trimisă în privat (DM)!**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Deschide mesajele private (DM) din setările Discord!", ephemeral=True)

@bot.tree.command(name="stop_pontaj_user", description="Oprește forțat tura unui mecanic")
async def stop_pontaj_user_cmd(interaction: discord.Interaction, user: discord.Member, salveaza_orele: bool = True):
    await interaction.response.defer(ephemeral=True)
    if not are_rolul_permis(interaction):
        await interaction.followup.send(f"⚠️ **Acces interzis!** Ai nevoie de rolul `{ROL_PERMIS}` pentru această comandă.", ephemeral=True)
        return
    
    active_shifts = get_all_active_shifts()
    if user.id not in active_shifts:
        await interaction.followup.send(f"⚠️ {user.mention} nu este în tură în acest moment.", ephemeral=True)
        return

    if salveaza_orele:
        ore, minute = stop_pontaj_user(user.id)
        await interaction.followup.send(f"🔴 **Pontaj oprit forțat!** I s-a oprit tura lui {user.mention}. I s-au salvat **{ore}h și {minute}m**.", ephemeral=True)
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_shifts WHERE user_id = ?", (user.id,))
        conn.commit()
        conn.close()
        await interaction.followup.send(f"🚫 **Pontaj anulat complet!** Tura activă a lui {user.mention} a fost ștearsă fără salvare.", ephemeral=True)

@bot.tree.command(name="reset_pontaje", description="Resetează toate pontajele din baza de date")
async def reset_pontaje(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not are_rolul_permis(interaction):
        await interaction.followup.send(f"⚠️ **Acces interzis!** Ai nevoie de rolul `{ROL_PERMIS}` pentru această comandă.", ephemeral=True)
        return

    reset_all_pontaje()
    await interaction.followup.send("🧹 **Toate pontajele au fost șterse cu succes!**", ephemeral=True)

# --- 7. PORNIRE BOT ---
TOKEN = os.environ.get('DISCORD_TOKEN')

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ EROARE: Variabila DISCORD_TOKEN nu a fost găsită!")
