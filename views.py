import discord
from database import start_pontaj, stop_pontaj, get_user_total_pontaj

class PontajView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 🟢 BUTON 1 - Intrare în tură
    @discord.ui.button(label="🟢 Intra In Tura", style=discord.ButtonStyle.green, custom_id="btn_start_pontaj")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        success = start_pontaj(user.id, str(user))
        
        if success:
            await interaction.response.send_message(f"🟢 Ai început pontajul, {user.mention}!", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ Ai deja un pontaj activ!", ephemeral=True)

    # 🔴 BUTON 2 - Ieșire din tură
    @discord.ui.button(label="🔴 Iesi Din Tura", style=discord.ButtonStyle.red, custom_id="btn_stop_pontaj")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        minutes = stop_pontaj(user.id)
        
        if minutes is not None:
            ore = minutes // 60
            rest_minute = minutes % 60
            await interaction.response.send_message(
                f"🔴 Ai încheiat pontajul!\n⏱️ Durată: **{ore} ore și {rest_minute} minute** ({minutes} minute total).", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("⚠️ Nu ai niciun pontaj activ în acest moment!", ephemeral=True)

    # 🔵 BUTON 3 - Verificare ore proprii
    @discord.ui.button(label="📊 Vezi Orele Tale", style=discord.ButtonStyle.blurple, custom_id="btn_orele_mele")
    async def my_hours_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        total_minutes, nr_pontaje = get_user_total_pontaj(user.id)
        
        if not total_minutes or total_minutes == 0:
            await interaction.response.send_message("ℹ️ Nu ai înregistrat niciun pontaj finalizat până acum.", ephemeral=True)
            return

        ore = total_minutes // 60
        rest_minute = total_minutes % 60
        
        embed = discord.Embed(
            title=f"⏱️ Orele tale de pontaj - {user.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="⏳ Timp total lucrat:", value=f"**{ore} ore și {rest_minute} minute**\n({total_minutes} minute în total)", inline=False)
        embed.add_field(name="📋 Total sesiuni încheiate:", value=f"`{nr_pontaje}` sesiuni", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
