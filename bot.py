import discord
from discord import app_commands
from discord.ext import commands
from database import init_db, get_total_pontaje_per_user, get_user_total_pontaj, reset_all_pontaje, stop_pontaj, cancel_active_pontaj
from views import PontajView

TOKEN ="MTUzMzY0MDc0NDkwNzE4MjE0MQ.GFMq1k.9tl9yp2V7pVyiJj2BEDEMA68M1ZizUgcAbrdoA"


ID_GRAD_RESET =1533708951055761438

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        init_db()
        self.add_view(PontajView())
        print("🔄 Se sincronizează comenzile slash...")
        await self.tree.sync()
        print("✅ Comenzile au fost sincronizate!")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ {bot.user} este online și pregătit!")

# 🛡️ GESTIONAR DE ERORI (Prinde erorile de permisiuni și le ascunde din consolă)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Nu ai permisiunea de **Administrator** pentru această comandă!", ephemeral=True)
    else:
        print(f"⚠️ Eroare neașteptată: {error}")

# 🛠️ PANOU TEMATIZAT NEXUS TUNING (Doar Admini)
@bot.tree.command(name="setup_pontaj", description="Trimite panoul cu butoane de pontaj (doar Admini)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_pontaj(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛠️ Nexus Tuning — Pontaj Mecanici",
        description=(
            "Bine ai venit în tura ta la **Nexus Tuning**! 🏎️💨\n\n"
            "Folosește butoanele de mai jos pentru a-ți gestiona timpul petrecut în atelier:\n\n"
            "🟢 **Intră în tură** — Pornește ceasul când intri în atelier.\n"
            "🔴 **Ieși din tură** — Oprește pontajul la finalul programului.\n"
            "📊 **Vezi orele tale** — Verifică totalul de ore lucrate la Tuning."
        ),
        color=discord.Color.dark_teal()
    )
    embed.set_footer(text="Nexus Tuning • Keep tuning, keep driving! 🛠️")
    await interaction.response.send_message(embed=embed, view=PontajView())

# 📩 RAPORT GENERAL ÎN MESAJ PRIVAT (Doar Admini)
@bot.tree.command(name="pontaje", description="Trimite direct în Mesaje Private totalul orelor (doar Admini)")
@app_commands.checks.has_permissions(administrator=True)
async def pontaje(interaction: discord.Interaction):
    records = get_total_pontaje_per_user()
    
    if not records:
        await interaction.response.send_message("❌ Nu există niciun pontaj finalizat în baza de date.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📊 Nexus Tuning - Total Ore Lucrate",
        color=discord.Color.gold()
    )

    text_pontaje = ""
    for username, total_minutes, nr_pontaje in records:
        if total_minutes is None:
            total_minutes = 0
            
        ore = total_minutes // 60
        rest_minute = total_minutes % 60
        
        text_pontaje += f"👤 **{username}**\n"
        text_pontaje += f"⏱️ Total calculat: **{ore} ore și {rest_minute} minute** ({total_minutes} min total)\n"
        text_pontaje += f"📋 Număr sesiuni: `{nr_pontaje}`\n\n"

    embed.description = text_pontaje

    try:
        await interaction.user.send(embed=embed)
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()
    except discord.Forbidden:
        await interaction.response.send_message("⚠️ Deschide mesajele private (DM) în Discord ca să primești raportul!", ephemeral=True)

# 👤 ORE PERSONALE MEMBRU (Accesibil tuturor)
@bot.tree.command(name="orele_mele", description="Vezi câte ore ai pontat în total la Nexus Tuning")
async def orele_mele(interaction: discord.Interaction):
    user = interaction.user
    total_minutes, nr_pontaje = get_user_total_pontaj(user.id)
    
    if not total_minutes or total_minutes == 0:
        await interaction.response.send_message("ℹ️ Nu ai înregistrat niciun pontaj finalizat la Nexus Tuning până acum.", ephemeral=True)
        return

    ore = total_minutes // 60
    rest_minute = total_minutes % 60
    
    embed = discord.Embed(
        title=f"⏱️ Ore Nexus Tuning - {user.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="⏳ Timp total lucrat:", value=f"**{ore} ore și {rest_minute} minute**\n({total_minutes} minute în total)", inline=False)
    embed.add_field(name="📋 Total sesiuni încheiate:", value=f"`{nr_pontaje}` sesiuni", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 🛑 OPRIRE FORȚATĂ (Doar Admini)
@bot.tree.command(name="stop_pontaj_user", description="Oprește forțat pontajul activ al unui membru (doar Admini)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="Membru căruia vrei să-i oprești pontajul", salveaza_orele="True = Calculează orele, False = Anulează sesiunea complet")
async def stop_pontaj_user(interaction: discord.Interaction, user: discord.Member, salveaza_orele: bool = True):
    if salveaza_orele:
        minutes = stop_pontaj(user.id)
        if minutes is not None:
            ore = minutes // 60
            rest = minutes % 60
            await interaction.response.send_message(
                f"🛑 **Pontaj oprit forțat!** I-ai oprit tura lui {user.mention}.\n⏱️ I s-au salvat **{ore}h și {rest}m** ({minutes} min).", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"⚠️ {user.mention} nu este în tură în acest moment.", ephemeral=True)
    else:
        deleted = cancel_active_pontaj(user.id)
        if deleted:
            await interaction.response.send_message(f"🚫 **Pontaj anulat complet!** Tura activă a lui {user.mention} a fost ștersă.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {user.mention} nu este în tură în acest moment.", ephemeral=True)

# 🧹 RESETARE PONTAJE (Doar pentru gradul specificat la ID_GRAD_RESET)
@bot.tree.command(name="reset_pontaje", description="Șterge toate pontajele din baza de date (Doar pentru gradul autorizat)")
async def reset_pontaje(interaction: discord.Interaction):
    has_role = any(role.id == ID_GRAD_RESET for role in getattr(interaction.user, 'roles', []))
    
    if not has_role:
        await interaction.response.send_message("❌ Nu ai gradul necesar pentru a reseta pontajele!", ephemeral=True)
        return

    reset_all_pontaje()
    await interaction.response.send_message("🧹 **Toate pontajele au fost șterse cu succes!** Baza de date Nexus Tuning a fost resetată.", ephemeral=True)
import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# --- SERVER WEB PENTRU RENDER ---
app = Flask('')


@app.route('/')
def home():
  return 'Botul este online 24/7!'


def run():
  # Render atribuie un PORT automat în mediul său, altfel folosește 8080
  port = int(os.environ.get('PORT', 8080))
  app.run(host='0.0.0.0', port=port)


# Pornim serverul web pe un fir de execuție separat (background thread)
threading.Thread(target=run, daemon=True).start()

# --- CODUL BOTULUI TĂU DE DISCORD ---
# (Păstrează mai jos restul codului tău existent)
bot.run(os.environ.get("MTUzMzY0MDc0NDkwNzE4MjE0MQ.GFMq1k.9tl9yp2V7pVyiJj2BEDEMA68M1ZizUgcAbrdoA" ))
