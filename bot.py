import os
import sqlite3
import threading
import time
import asyncio
import traceback
from datetime import datetime

from flask import Flask
import discord
from discord.ext import commands


# =========================================================
# CONFIG
# =========================================================

ROL_PERMIS = "pontaje"
DB_FILE = "pontaj.db"


# =========================================================
# BAZA DE DATE
# =========================================================

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_shifts (
                user_id INTEGER PRIMARY KEY,
                start_time TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_hours (
                user_id INTEGER PRIMARY KEY,
                total_seconds INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()

        print("✅ Baza de date a fost inițializată.", flush=True)

    except Exception as e:
        print(f"❌ Eroare DB: {e}", flush=True)
        traceback.print_exc()


# =========================================================
# PONTAJ
# =========================================================

def start_pontaj_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT start_time FROM active_shifts WHERE user_id = ?",
        (user_id,)
    )

    if cursor.fetchone():
        conn.close()
        raise Exception(
            "Ești deja în tură! Ieși mai întâi din tura curentă."
        )

    now_str = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO active_shifts (user_id, start_time)
        VALUES (?, ?)
        """,
        (user_id, now_str)
    )

    conn.commit()
    conn.close()


def stop_pontaj_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT start_time FROM active_shifts WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None, None

    start_time = datetime.fromisoformat(row[0])

    duration = datetime.now() - start_time
    seconds_worked = max(
        0,
        int(duration.total_seconds())
    )

    cursor.execute(
        "DELETE FROM active_shifts WHERE user_id = ?",
        (user_id,)
    )

    cursor.execute(
        """
        INSERT INTO user_hours (user_id, total_seconds)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET total_seconds = total_seconds + ?
        """,
        (
            user_id,
            seconds_worked,
            seconds_worked
        )
    )

    conn.commit()
    conn.close()

    hours = seconds_worked // 3600
    minutes = (seconds_worked % 3600) // 60

    return hours, minutes


def get_ore_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT total_seconds FROM user_hours WHERE user_id = ?",
        (user_id,)
    )

    row_hours = cursor.fetchone()

    total_seconds = (
        row_hours[0]
        if row_hours
        else 0
    )

    cursor.execute(
        "SELECT start_time FROM active_shifts WHERE user_id = ?",
        (user_id,)
    )

    row_shift = cursor.fetchone()

    if row_shift:
        start_time = datetime.fromisoformat(
            row_shift[0]
        )

        current_duration = (
            datetime.now() - start_time
        )

        total_seconds += max(
            0,
            int(current_duration.total_seconds())
        )

    conn.close()

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    return hours, minutes


def reset_all_pontaje():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM active_shifts"
    )

    cursor.execute(
        "DELETE FROM user_hours"
    )

    conn.commit()
    conn.close()


def get_all_active_shifts():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, start_time
        FROM active_shifts
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return {
        row[0]: datetime.fromisoformat(row[1])
        for row in rows
    }


def get_all_users_with_records():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id FROM user_hours

        UNION

        SELECT user_id FROM active_shifts
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        row[0]
        for row in rows
    ]


# =========================================================
# VERIFICARE ROL
# =========================================================

def are_rolul_permis(
    interaction: discord.Interaction
) -> bool:

    if not hasattr(
        interaction.user,
        "roles"
    ):
        return False

    return any(
        role.name.lower()
        == ROL_PERMIS.lower()
        for role in interaction.user.roles
    )


# =========================================================
# FLASK - RENDER
# =========================================================

app = Flask(__name__)


@app.route(
    "/",
    methods=["GET", "HEAD", "POST"]
)
def home():
    return (
        "Botul Nexus Tuning este online!",
        200
    )


def run_flask():
    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    print(
        f"🌐 Pornesc Flask pe portul {port}...",
        flush=True
    )

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================================================
# DISCORD INTENTS
# =========================================================

print(
    "⚙️ Configurez Discord intents...",
    flush=True
)

intents = discord.Intents.default()

# IMPORTANT
intents.message_content = True
intents.members = True
intents.presences = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# VIEW PONTAJ
# =========================================================

class PontajView(discord.ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Intra In Tura",
        style=discord.ButtonStyle.green,
        custom_id="intra_tura_btn"
    )
    async def intra_tura(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            if not are_rolul_permis(
                interaction
            ):

                await interaction.followup.send(
                    f"⚠️ **Acces interzis!**\n"
                    f"Ai nevoie de rolul "
                    f"`{ROL_PERMIS}`.",
                    ephemeral=True
                )

                return

            start_pontaj_user(
                interaction.user.id
            )

            await interaction.followup.send(
                "🟢 **Ai intrat în tură cu succes!**\n"
                "Spor la treabă! 🔧",
                ephemeral=True
            )

        except Exception as e:

            await interaction.followup.send(
                f"⚠️ **Notificare:** {e}",
                ephemeral=True
            )


    @discord.ui.button(
        label="Iesi Din Tura",
        style=discord.ButtonStyle.red,
        custom_id="iesi_tura_btn"
    )
    async def iesi_tura(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            if not are_rolul_permis(
                interaction
            ):

                await interaction.followup.send(
                    f"⚠️ **Acces interzis!**\n"
                    f"Ai nevoie de rolul "
                    f"`{ROL_PERMIS}`.",
                    ephemeral=True
                )

                return

            ore, minute = stop_pontaj_user(
                interaction.user.id
            )

            if ore is not None:

                await interaction.followup.send(
                    f"🔴 **Ai ieșit din tură!**\n"
                    f"Ai lucrat **{ore}h "
                    f"și {minute}m** "
                    f"în această tură.",
                    ephemeral=True
                )

            else:

                await interaction.followup.send(
                    "⚠️ Nu ești înregistrat "
                    "ca fiind în tură!",
                    ephemeral=True
                )

        except Exception as e:

            await interaction.followup.send(
                f"⚠️ **Notificare:** {e}",
                ephemeral=True
            )


    @discord.ui.button(
        label="Vezi Orele Tale",
        style=discord.ButtonStyle.blurple,
        custom_id="vezi_ore_btn"
    )
    async def vezi_ore(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            if not are_rolul_permis(
                interaction
            ):

                await interaction.followup.send(
                    f"⚠️ **Acces interzis!**\n"
                    f"Ai nevoie de rolul "
                    f"`{ROL_PERMIS}`.",
                    ephemeral=True
                )

                return

            total_ore, total_minute = (
                get_ore_user(
                    interaction.user.id
                )
            )

            await interaction.followup.send(
                f"📊 **Total ore lucrate:** "
                f"{total_ore}h "
                f"și {total_minute}m.",
                ephemeral=True
            )

        except Exception as e:

            await interaction.followup.send(
                f"⚠️ **Eroare:** {e}",
                ephemeral=True
            )


# =========================================================
# VARIABILE
# =========================================================

view_loaded = False
sync_done = False


# =========================================================
# ON CONNECT
# =========================================================

@bot.event
async def on_connect():

    print(
        "🔌 DISCORD GATEWAY CONECTAT!",
        flush=True
    )


# =========================================================
# ON READY
# =========================================================

@bot.event
async def on_ready():

    global view_loaded, sync_done

    print(
        "",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    print(
        "🤖 BOT DISCORD CONECTAT",
        flush=True
    )

    print(
        f"👤 Cont: {bot.user}",
        flush=True
    )

    print(
        f"🆔 ID: {bot.user.id}",
        flush=True
    )

    print(
        f"🌐 Servere: {len(bot.guilds)}",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # -----------------------------------------------------
    # VIEW
    # -----------------------------------------------------

    if not view_loaded:

        try:

            bot.add_view(
                PontajView()
            )

            view_loaded = True

            print(
                "✅ Panoul persistent "
                "a fost încărcat.",
                flush=True
            )

        except Exception as e:

            print(
                f"❌ Eroare panou: {e}",
                flush=True
            )

            traceback.print_exc()

    # -----------------------------------------------------
    # SYNC COMMANDS - O SINGURĂ DATĂ
    # Evită sincronizări repetate la reconnect, care pot
    # produce rate-limit (429).
    # -----------------------------------------------------

    if not sync_done:

        for guild in bot.guilds:

            try:

                print(
                    f"🔄 Sincronizez comenzile "
                    f"pe: {guild.name}",
                    flush=True
                )

                bot.tree.copy_global_to(
                    guild=guild
                )

                synced = await bot.tree.sync(
                    guild=guild
                )

                print(
                    f"✅ {len(synced)} comenzi "
                    f"sincronizate pe "
                    f"{guild.name}",
                    flush=True
                )

            except Exception as e:

                print(
                    f"❌ Eroare sync pe "
                    f"{guild.name}: {e}",
                    flush=True
                )

                traceback.print_exc()

        sync_done = True

    else:

        print(
            "ℹ️ Comenzile sunt deja sincronizate; "
            "nu mai fac sync la reconnect.",
            flush=True
        )

    print(
        "",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    print(
        "✅ BOTUL ESTE GATA DE FOLOSIRE!",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    print(
        "",
        flush=True
    )


# =========================================================
# DISCONNECT
# =========================================================

@bot.event
async def on_disconnect():

    print(
        "⚠️ BOTUL S-A DECONECTAT DE LA DISCORD!",
        flush=True
    )


# =========================================================
# RESUMED
# =========================================================

@bot.event
async def on_resumed():

    print(
        "🔄 CONEXIUNEA DISCORD A FOST RELUATĂ!",
        flush=True
    )


# =========================================================
# ERORI
# =========================================================

@bot.event
async def on_error(
    event,
    *args,
    **kwargs
):

    print(
        f"❌ EROARE DISCORD EVENT: {event}",
        flush=True
    )

    traceback.print_exc()


# =========================================================
# SETUP PONTAJ
# =========================================================

@bot.tree.command(
    name="setup_pontaj",
    description=(
        "Trimite panoul principal "
        "pentru pontaj mecanici"
    )
)
async def setup_pontaj(
    interaction: discord.Interaction
):

    await interaction.response.defer(
        ephemeral=False
    )

    if not are_rolul_permis(
        interaction
    ):

        await interaction.followup.send(
            f"⚠️ **Acces interzis!**\n"
            f"Ai nevoie de rolul "
            f"`{ROL_PERMIS}`.",
            ephemeral=True
        )

        return

    embed = discord.Embed(

        title=(
            "🛠️ Nexus Tuning — "
            "Pontaj Mecanici"
        ),

        description=(
            "Bine ai venit în tura ta la "
            "**Nexus Tuning**! 🏎️💨\n\n"

            "Folosește butoanele de mai jos "
            "pentru a-ți gestiona timpul "
            "petrecut în atelier:\n\n"

            "🟢 **Intră în tură** — "
            "Pornește ceasul când intri "
            "în atelier.\n\n"

            "🔴 **Ieși din tură** — "
            "Oprește pontajul la finalul "
            "programului.\n\n"

            "📊 **Vezi orele tale** — "
            "Verifică totalul de ore "
            "lucrate."
        ),

        color=discord.Color.teal()
    )

    embed.set_footer(
        text=(
            "Nexus Tuning • "
            "Keep tuning, keep driving! 🛠️"
        )
    )

    await interaction.followup.send(
        embed=embed,
        view=PontajView()
    )


# =========================================================
# PONTAJE
# =========================================================

@bot.tree.command(
    name="pontaje",
    description=(
        "Trimite lista cu orele totale "
        "ale mecanicilor în privat"
    )
)
async def pontaje(
    interaction: discord.Interaction
):

    await interaction.response.defer(
        ephemeral=True
    )

    if not are_rolul_permis(
        interaction
    ):

        await interaction.followup.send(
            f"⚠️ **Acces interzis!**\n"
            f"Ai nevoie de rolul "
            f"`{ROL_PERMIS}`.",
            ephemeral=True
        )

        return

    all_users = (
        get_all_users_with_records()
    )

    active_shifts = (
        get_all_active_shifts()
    )

    if not all_users:

        await interaction.followup.send(
            "📋 **Nu există niciun pontaj "
            "înregistrat momentan!**",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=(
            "📋 Istoric Pontaje — "
            "Nexus Tuning"
        ),
        color=discord.Color.gold()
    )

    lista_text = ""

    for user_id in all_users:

        ore, minute = get_ore_user(
            user_id
        )

        status = (
            "🟢 în tură"
            if user_id in active_shifts
            else "🔴 Off"
        )

        lista_text += (
            f"• <@{user_id}> "
            f"[{status}] — "
            f"**{ore}h {minute}m**\n"
        )

    if len(lista_text) > 1024:

        lista_text = (
            lista_text[:1000]
            + "\n..."
        )

    embed.add_field(
        name="Mecanici Pontați",
        value=lista_text,
        inline=False
    )

    try:

        await interaction.user.send(
            embed=embed
        )

        await interaction.followup.send(
            "📩 **Lista ți-a fost "
            "trimisă în privat (DM)!**",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "⚠️ Deschide mesajele private "
            "(DM) din setările Discord!",
            ephemeral=True
        )


# =========================================================
# TURE ACTIVE
# =========================================================

@bot.tree.command(
    name="ture_active",
    description=(
        "Trimite lista cu mecanicii "
        "aflați în tură în privat"
    )
)
async def ture_active(
    interaction: discord.Interaction
):

    await interaction.response.defer(
        ephemeral=True
    )

    if not are_rolul_permis(
        interaction
    ):

        await interaction.followup.send(
            f"⚠️ **Acces interzis!**\n"
            f"Ai nevoie de rolul "
            f"`{ROL_PERMIS}`.",
            ephemeral=True
        )

        return

    active_shifts = (
        get_all_active_shifts()
    )

    if not active_shifts:

        await interaction.followup.send(
            "🔴 **Nu există niciun mecanic "
            "în tură în acest moment!**",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=(
            "🟢 Mecanici Aflați "
            "în Tură Acum"
        ),
        color=discord.Color.green()
    )

    text = ""

    for user_id, start_time in (
        active_shifts.items()
    ):

        duration = (
            datetime.now()
            - start_time
        )

        sec = max(
            0,
            int(
                duration.total_seconds()
            )
        )

        h = sec // 3600
        m = (sec % 3600) // 60

        text += (
            f"• <@{user_id}> — "
            f"în tură de "
            f"**{h}h {m}m**\n"
        )

    if len(text) > 1024:

        text = (
            text[:1000]
            + "\n..."
        )

    embed.add_field(
        name="Mecanici Activi",
        value=text,
        inline=False
    )

    try:

        await interaction.user.send(
            embed=embed
        )

        await interaction.followup.send(
            "📩 **Lista mecanicilor activi "
            "ți-a fost trimisă în privat!**",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "⚠️ Deschide mesajele private "
            "(DM) din setările Discord!",
            ephemeral=True
        )


# =========================================================
# RESET
# =========================================================

@bot.tree.command(
    name="reset_pontaje",
    description=(
        "Resetează toate orele și turele"
    )
)
async def reset_pontaje(
    interaction: discord.Interaction
):

    await interaction.response.defer(
        ephemeral=True
    )

    if not are_rolul_permis(
        interaction
    ):

        await interaction.followup.send(
            f"⚠️ **Acces interzis!**\n"
            f"Ai nevoie de rolul "
            f"`{ROL_PERMIS}`.",
            ephemeral=True
        )

        return

    reset_all_pontaje()

    await interaction.followup.send(
        "🧹 **Toate pontajele și orele "
        "au fost resetate cu succes!**",
        ephemeral=True
    )


# =========================================================
# PORNIRE
# =========================================================

def main():

    print(
        "",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    print(
        "🚀 PORNESC BOTUL DISCORD...",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # -----------------------------------------------------
    # TOKEN
    # -----------------------------------------------------

    token = os.environ.get(
        "DISCORD_TOKEN"
    )

    if token is None:

        print(
            "❌ DISCORD_TOKEN NU EXISTĂ!",
            flush=True
        )

        return

    token = token.strip()

    if not token:

        print(
            "❌ DISCORD_TOKEN ESTE GOL!",
            flush=True
        )

        return

    print(
        "🔑 DISCORD_TOKEN a fost găsit.",
        flush=True
    )

    print(
        f"🔑 Lungime token: {len(token)} caractere.",
        flush=True
    )

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    init_db()

    # -----------------------------------------------------
    # FLASK
    # -----------------------------------------------------

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    print(
        "🌐 Flask thread pornit.",
        flush=True
    )

    # -----------------------------------------------------
    # DISCORD
    # -----------------------------------------------------

    print(
        "🔌 Mă conectez la Discord Gateway...",
        flush=True
    )

    try:

        bot.run(
            token,
            reconnect=True
        )

    except discord.LoginFailure:

        print(
            "❌ DISCORD LOGIN FAILURE!",
            flush=True
        )

        print(
            "❌ Tokenul Discord este invalid "
            "sau a fost regenerat.",
            flush=True
        )

        traceback.print_exc()

        # Nu lăsăm Render să repornească procesul în buclă.
        while True:
            time.sleep(3600)

    except discord.PrivilegedIntentsRequired:

        print(
            "❌ PRIVILEGED INTENTS REQUIRED!",
            flush=True
        )

        print(
            "❌ Verifică Message Content Intent "
            "și Server Members Intent.",
            flush=True
        )

        traceback.print_exc()

        while True:
            time.sleep(3600)

    except Exception as e:

        print(
            f"❌ EROARE BOT: {e}",
            flush=True
        )

        traceback.print_exc()

        # Dacă Discord răspunde cu 429, nu ieșim imediat.
        # Așteptăm ca rate-limit-ul să expire, evitând un
        # restart continuu al serviciului Render.
        if "429" in str(e) or "Too Many Requests" in str(e):

            print(
                "⏳ Discord a aplicat rate-limit (429). "
                "Aștept 120 secunde înainte de o nouă încercare.",
                flush=True
            )

            time.sleep(120)

            print(
                "🔄 Repornește serviciul pentru o nouă încercare "
                "după expirarea rate-limit-ului.",
                flush=True
            )

        else:

            print(
                "🛑 Procesul rămâne pornit pentru a evita "
                "restarturi repetate în Render.",
                flush=True
            )

        while True:
            time.sleep(3600)

    finally:

        print(
            "🛑 bot.run() s-a încheiat.",
            flush=True
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
