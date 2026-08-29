import discord
from discord.ext import commands
import yt_dlp
import asyncio

# ---------- BOT AYARLARI ----------
TOKEN = "MTU0MzM3NTI1OTU4MjA3ODk5Ng.G9Stue.U8xeYy6GE1uK7N-Xiek9NQChwEe5xXOgVMH2Zc"
PREFIX = "!"

# FFmpeg yolunuzu ayarlayın
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

# Intent Ayarları (Rol verme için members=True şarttır)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Spam Kontrolü İçin Kullanıcı Takip Deposu
user_spam_counter = {}

# ---------- YTDL & FFMPEG AYARLARI ----------
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **FFMPEG_OPTIONS), data=data)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} aktif ve tüm sistemler yüklendi!")


# ==================== SPAM KORUMASI (TIMEOUT + MESAJ SİLME) ====================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    user_id = message.author.id
    current_time = asyncio.get_event_loop().time()
    content = message.content.strip().lower()

    if content:
        if user_id in user_spam_counter:
            data = user_spam_counter[user_id]
            time_diff = current_time - data["last_time"]

            if time_diff <= 5.0 and data["last_msg"] == content:
                data["count"] += 1
                data["last_time"] = current_time
            else:
                user_spam_counter[user_id] = {"last_msg": content, "count": 1, "last_time": current_time}
        else:
            user_spam_counter[user_id] = {"last_msg": content, "count": 1, "last_time": current_time}

        if user_spam_counter[user_id]["count"] >= 3:
            try:
                duration = discord.utils.utcnow() + discord.utils.datetime.timedelta(seconds=60)
                await message.author.timeout(duration, reason="Aynı mesajı 5 saniye içinde defalarca tekrarlama (Spam)")
                
                user_spam_counter[user_id] = {"last_msg": "", "count": 0, "last_time": 0}

                def is_spam_author(m):
                    return m.author.id == user_id

                try:
                    deleted = await message.channel.purge(limit=20, check=is_spam_author)
                    deleted_count = len(deleted)
                except discord.Forbidden:
                    deleted_count = 0
                    print("⚠️ Spam mesajları silinirken 'Mesajları Yönet' yetkisi yetersizdi.")

                await message.channel.send(
                    f"⚠️ {message.author.mention}, aynı mesajı kısa süre içinde tekrarladığın için **1 dakika boyunca susturuldun** ve mesajların silindi!", 
                    delete_after=10
                )

                cmd_kanali = discord.utils.get(message.guild.text_channels, name="cmd")
                if cmd_kanali and cmd_kanali.permissions_for(message.guild.me).send_messages:
                    embed = discord.Embed(
                        title="🔇 Otomatik Timeout & Mesaj Temizliği",
                        description=(
                            f"**Kullanıcı:** {message.author.mention} (`{message.author.id}`)\n"
                            f"**Sebep:** Aynı mesajı 5 saniye içinde tekrarlama (Spam)\n"
                            f"**Süre:** 1 Dakika Timeout\n"
                            f"**Temizlenen Mesaj:** {deleted_count} adet"
                        ),
                        color=0xE74C3C
                    )
                    await cmd_kanali.send(embed=embed)

            except discord.Forbidden:
                print(f"⚠️ {message.author.name} kullanıcısına timeout atılamadı (Yetki yetersiz veya kullanıcı yönetici).")
            except Exception as e:
                print(f"❌ Spam Timeout Hatası: {e}")

    await bot.process_commands(message)


# ==================== KORUMA SİSTEMİ & OTOMATİK ROL VERME ====================

@bot.event
async def on_member_join(member):
    """
    1. Sunucuya katılan botları otomatik atar.
    2. Katılan gerçek kullanıcılara otomatik 'VNT pub' rolünü verir.
    """
    print(f"📥 Katılan var: {member.name} (Bot mu: {member.bot})")

    # A) GELEN İZİNSİZ BOT İSE AT
    if member.bot and member != bot.user:
        try:
            await member.kick(reason="Anti-Bot Koruması: İzinsiz bot katılımı engellendi.")
            print(f"🛡️ [KORUMA SUCCESS] {member.name} başarıyla atıldı!")

            cmd_kanali = discord.utils.get(member.guild.text_channels, name="cmd")
            if cmd_kanali and cmd_kanali.permissions_for(member.guild.me).send_messages:
                embed = discord.Embed(
                    title="🛡️ Bot Koruması Devrede",
                    description=f"Sunucuya eklenmeye çalışan **{member.name}** (`{member.id}`) isimli bot güvenlik nedeniyle **otomatik olarak atıldı**.",
                    color=0xFF0000
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                await cmd_kanali.send(embed=embed)
        except discord.Forbidden:
            print(f"⚠️ [KORUMA HATASI] {member.name} botunu atmak için yetkim yetersiz!")
        except Exception as e:
            print(f"❌ Koruma hatası: {e}")
        return

    # B) GELEN KULLANICI İSE 'VNT pub' ROLÜ VER
    otomatik_rol = discord.utils.get(member.guild.roles, name="VNT pub")
    if otomatik_rol:
        try:
            await member.add_roles(otomatik_rol, reason="Otomatik Rol Verme (Yeni Üye)")
            print(f"✅ [OTO ROL] {member.name} kullanıcısına '{otomatik_rol.name}' rolü verildi.")
            
            # Opsiyonel: cmd kanalına bilgi bildirimi
            cmd_kanali = discord.utils.get(member.guild.text_channels, name="cmd")
            if cmd_kanali and cmd_kanali.permissions_for(member.guild.me).send_messages:
                embed = discord.Embed(
                    title="👤 Yeni Üye & Otomatik Rol",
                    description=f"**{member.mention}** sunucuya katıldı ve **{otomatik_rol.name}** rolü otomatik olarak verildi.",
                    color=0x2ECC71
                )
                await cmd_kanali.send(embed=embed)

        except discord.Forbidden:
            print(f"❌ [OTO ROL HATASI] Botun rol sırası '{otomatik_rol.name}' rolünden daha aşağıda veya 'Rolleri Yönet' yetkisi eksik!")
        except Exception as e:
            print(f"❌ Oto rol verirken hata oluştu: {e}")
    else:
        print("⚠️ [OTO ROL HATASI] Sunucuda 'VNT pub' adında bir rol bulunamadı! Rol isminin birebir eşleştiğinden emin olun.")


# ==================== ÖZEL ODA & OTOMATİK ATMA OTOMASYONU ====================

@bot.event
async def on_voice_state_update(member, before, after):
    if not member.bot and after.channel is not None:
        if after.channel.name == "discord.gg/VNT":
            try:
                await member.move_to(None)
            except discord.Forbidden:
                pass


# ---------- GELLA KOMUTU ----------
@bot.command(name="GELLA", aliases=["gella"])
async def gella_komutu(ctx):
    """En üste kilitli özel kanal açar, girer ve gelenleri atar."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.reply("❌ Bu komutu kullanmak için **Yönetici** yetkisi gereklidir.", delete_after=5)
        return

    kanallari_yonet = ctx.guild.me.guild_permissions.manage_channels
    kullanici_tasi = ctx.guild.me.guild_permissions.move_members

    if not (kanallari_yonet and kullanici_tasi):
        await ctx.reply("❌ Botun **Kanalları Yönet** ve **Üyeleri Taşı** yetkilerine ihtiyacı var!", delete_after=10)
        return

    kanal_adi = "discord.gg/VNT"
    hedef_kanal = discord.utils.get(ctx.guild.voice_channels, name=kanal_adi)

    if not hedef_kanal:
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=True, speak=False),
            ctx.guild.me: discord.PermissionOverwrite(connect=True, speak=True, move_members=True)
        }
        
        hedef_kanal = await ctx.guild.create_voice_channel(
            name=kanal_adi,
            position=0,
            overwrites=overwrites
        )
        await ctx.send(f"✅ **{kanal_adi}** kanalı en üste başarıyla oluşturuldu!")

    if ctx.voice_client is None:
        await hedef_kanal.connect()
    else:
        await ctx.voice_client.move_to(hedef_kanal)

    await ctx.reply(f"🔒 Bot **{hedef_kanal.name}** kanalına bağlandı ve 7/24 aktif tutuluyor. İçeri giren kullanıcılar otomatik atılacaktır.")


# ==================== YÖNETİM KOMUTLARI ====================

# ---------- CLEAR / SIL KOMUTU ----------
@bot.command(name="CLEAR", aliases=["clear", "sil", "clean"])
async def clear_komutu(ctx):
    """Sırayla kanal ve adet sorarak mesaj siler."""
    if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_messages):
        await ctx.reply("❌ Bu komut için **Mesajları Yönet** veya **Yönetici** yetkisi gerekli.", delete_after=8)
        return

    if not ctx.guild.me.guild_permissions.manage_messages:
        await ctx.reply("❌ Bot'un **Mesajları Yönet** yetkisi yok!", delete_after=10)
        return

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("❓ Hangi kanaldan mesaj silmek istiyorsun? (Kanalı etiketleyebilir veya adını yazabilirsin, örn: `#genel`)")
    
    try:
        msg_kanal = await bot.wait_for("message", check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Süre doldu, işlem iptal edildi.")
        return

    hedef_kanal = None
    if msg_kanal.channel_mentions:
        hedef_kanal = msg_kanal.channel_mentions[0]
    else:
        hedef_kanal = discord.utils.get(ctx.guild.text_channels, name=msg_kanal.content.strip().lstrip("#"))

    if not hedef_kanal:
        await ctx.send("❌ Belirttiğin metin kanalı bulunamadı. İşlem iptal edildi.")
        return

    await ctx.send(f"❓ **{hedef_kanal.mention}** kanalından kaç mesaj silinsin? (1 - 500 arası bir sayı yazın)")
    
    try:
        msg_adet = await bot.wait_for("message", check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Süre doldu, işlem iptal edildi.")
        return

    try:
        miktar = int(msg_adet.content.strip())
        if miktar <= 0 or miktar > 500:
            await ctx.send("❌ Lütfen 1 ile 500 arasında geçerli bir sayı girin.")
            return
    except ValueError:
        await ctx.send("❌ Geçersiz bir sayı girdiniz. İşlem iptal edildi.")
        return

    try:
        silinenler = await hedef_kanal.purge(limit=miktar)
        embed = discord.Embed(
            title="🧹 Mesajlar Temizlendi",
            description=f"**{hedef_kanal.mention}** kanalından **{len(silinenler)}** mesaj başarıyla silindi.",
            color=0x3498DB
        )
        embed.set_footer(text=f"İşlemi Yapan: {ctx.author.display_name}")
        await ctx.send(embed=embed, delete_after=10)
    except discord.Forbidden:
        await ctx.send("❌ O kanaldaki mesajları silmek için yeterli yetkim yok.")
    except Exception as e:
        await ctx.send(f"❌ Mesajlar silinirken bir hata oluştu: `{str(e)}`")


# ---------- ÇEK KOMUTU ----------
@bot.command(name="ÇEK", aliases=["cek", "pull", "topla"])
async def cek(ctx):
    """Tüm üyeleri senin ses kanalına çeker."""
    if not ctx.author.voice:
        await ctx.reply("❌ Önce bir ses kanalına katılmalısın! 🔊", delete_after=5)
        return

    if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.move_members):
        await ctx.reply("❌ Bu komut için **Üyeleri Taşı** veya **Yönetici** yetkisi gerekli.", delete_after=8)
        return

    if not ctx.guild.me.guild_permissions.move_members:
        await ctx.reply("❌ Bot'un **Üyeleri Taşı** yetkisi yok!", delete_after=10)
        return

    hedef = ctx.author.voice.channel
    tasinan = 0
    basarisiz = 0
    hata_listesi = []

    for ses_kanali in ctx.guild.voice_channels:
        if ses_kanali == hedef:
            continue

        for uye in ses_kanali.members:
            if uye == bot.user or uye.bot:
                continue

            try:
                await uye.move_to(hedef)
                tasinan += 1
            except discord.Forbidden:
                basarisiz += 1
                hata_listesi.append(f"{uye.display_name} → Rol hiyerarşisi hatası")
            except Exception as e:
                basarisiz += 1
                hata_listesi.append(f"{uye.display_name} → {type(e).__name__}")

    embed = discord.Embed(
        title="✅ İşlem Tamam" if tasinan > 0 else "⚠️ İşlem Kısmen Başarısız",
        description=f"**{hedef.name}** kanalına çekildi.",
        color=0x00FF00 if tasinan > 0 else 0xFFA500
    )
    embed.add_field(name="✅ Taşınan", value=str(tasinan), inline=True)
    embed.add_field(name="❌ Başarısız", value=str(basarisiz), inline=True)

    if hata_listesi:
        embed.add_field(
            name="📋 Hatalar",
            value="```\n" + "\n".join(hata_listesi[:5]) + "\n```",
            inline=False
        )

    await ctx.reply(embed=embed)


# ---------- MUTE KOMUTU ----------
@bot.command(name="MUTE", aliases=["mute", "sustur"])
async def mute_komutu(ctx):
    """Ses kanalında sen hariç herkesi susturur."""
    if not ctx.author.voice:
        await ctx.reply("❌ Önce bir ses kanalına katılmalısın! 🔊", delete_after=5)
        return

    hedef_kanal = ctx.author.voice.channel

    if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.mute_members):
        await ctx.reply("❌ Bu komut için **Üyeleri Sustur** veya **Yönetici** yetkisi gerekli.", delete_after=8)
        return

    if not ctx.guild.me.guild_permissions.mute_members:
        await ctx.reply("❌ Bot'un **Üyeleri Sustur** yetkisi yok!", delete_after=10)
        return

    mute_olan = 0
    zaten_mute = 0
    basarisiz = 0
    hata_listesi = []

    for uye in hedef_kanal.members:
        if uye == bot.user or uye.bot or uye == ctx.author:
            continue

        if uye.voice.mute:
            zaten_mute += 1
            continue

        try:
            await uye.edit(mute=True)
            mute_olan += 1
        except discord.Forbidden:
            basarisiz += 1
            hata_listesi.append(f"{uye.display_name} → Rol hiyerarşisi hatası")
        except Exception as e:
            basarisiz += 1
            hata_listesi.append(f"{uye.display_name} → {type(e).__name__}")

    embed = discord.Embed(
        title="🔇 Susturma İşlemi",
        description=f"**{hedef_kanal.name}** kanalındaki herkes susturuldu (sen hariç).",
        color=0x9B59B6
    )
    embed.add_field(name="🔇 Susturulan", value=str(mute_olan), inline=True)
    embed.add_field(name="🔇 Zaten Susturulmuş", value=str(zaten_mute), inline=True)
    embed.add_field(name="❌ Başarısız", value=str(basarisiz), inline=True)

    if hata_listesi:
        embed.add_field(
            name="📋 Hatalar",
            value="```\n" + "\n".join(hata_listesi[:5]) + "\n```",
            inline=False
        )

    embed.set_footer(text=f"Yetki: {ctx.author.display_name}")
    await ctx.reply(embed=embed)


# ---------- UNMUTE KOMUTU ----------
@bot.command(name="UNMUTE", aliases=["unmute", "konustur"])
async def unmute_komutu(ctx):
    """Ses kanalındaki herkesin susturmasını kaldırır."""
    if not ctx.author.voice:
        await ctx.reply("❌ Önce bir ses kanalına katılmalısın! 🔊", delete_after=5)
        return

    hedef_kanal = ctx.author.voice.channel

    if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.mute_members):
        await ctx.reply("❌ Bu komut için **Üyeleri Sustur** veya **Yönetici** yetkisi gerekli.", delete_after=8)
        return

    if not ctx.guild.me.guild_permissions.mute_members:
        await ctx.reply("❌ Bot'un **Üyeleri Sustur** yetkisi yok!", delete_after=10)
        return

    unmute_olan = 0
    zaten_acik = 0
    basarisiz = 0
    hata_listesi = []

    for uye in hedef_kanal.members:
        if uye == bot.user or uye.bot:
            continue

        if not uye.voice.mute:
            zaten_acik += 1
            continue

        try:
            await uye.edit(mute=False)
            unmute_olan += 1
        except discord.Forbidden:
            basarisiz += 1
            hata_listesi.append(f"{uye.display_name} → Rol hiyerarşisi hatası")
        except Exception as e:
            basarisiz += 1
            hata_listesi.append(f"{uye.display_name} → {type(e).__name__}")

    embed = discord.Embed(
        title="🔊 Susturma Kaldırıldı",
        description=f"**{hedef_kanal.name}** kanalındaki kullanıcıların susturması kaldırıldı.",
        color=0x2ECC71
    )
    embed.add_field(name="🔊 Açılan", value=str(unmute_olan), inline=True)
    embed.add_field(name="✅ Zaten Açık", value=str(zaten_acik), inline=True)
    embed.add_field(name="❌ Başarısız", value=str(basarisiz), inline=True)

    if hata_listesi:
        embed.add_field(
            name="📋 Hatalar",
            value="```\n" + "\n".join(hata_listesi[:5]) + "\n```",
            inline=False
        )

    embed.set_footer(text=f"Yetki: {ctx.author.display_name}")
    await ctx.reply(embed=embed)


# ==================== MÜZİK KOMUTLARI ====================

# ---------- PLAY KOMUTU ----------
@bot.command(name="PLAY", aliases=["play", "oynat", "p"])
async def play(ctx, *, search: str):
    """Bulunduğunuz ses kanalına girer ve belirtilen linki/şarkıyı çalar."""
    if not ctx.author.voice:
        await ctx.reply("❌ Önce bir ses kanalına katılmalısın! 🔊", delete_after=5)
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()

            ctx.voice_client.play(player, after=lambda e: print(f'Hata: {e}') if e else None)
            
            embed = discord.Embed(
                title="🎵 Şarkı Çalınıyor",
                description=f"**[{player.title}]({player.url})**",
                color=0x1DB954
            )
            embed.set_footer(text=f"İsteyen: {ctx.author.display_name}")
            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"❌ Şarkı oynatılırken bir hata oluştu: `{str(e)}`")


# ---------- STOP KOMUTU ----------
@bot.command(name="STOP", aliases=["stop", "dur", "dc", "leave"])
async def stop(ctx):
    """Şarkıyı durdurur ve botu ses kanalından çıkarır."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.reply("⏹️ Müzik durduruldu ve ses kanalından çıkıldı.")
    else:
        await ctx.reply("❌ Bot zaten bir ses kanalında değil.")


bot.run(TOKEN)