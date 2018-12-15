import discord
from redbot.core import commands, Config
from redbot.core.i18n import Translator, cog_i18n
import aiohttp
import os
from PIL import Image, ImageColor, ImageFont, ImageDraw
from PIL import ImageSequence
from barcode import generate
from barcode.writer import ImageWriter
from redbot.core.data_manager import bundled_data_path
from io import BytesIO
from .templates import blank_template
from .badge_entry import Badge
import sys
import functools
import asyncio

_ = Translator("Badges", __file__)


@cog_i18n(_)
class Badges(getattr(commands, "Cog", object)):
    """
        Create fun fake badges based on your discord profile
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1545487348434)
        default_guild = {"badges":[]}
        default_global = {"badges": blank_template}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def remove_white_barcode(self, img):
        """https://stackoverflow.com/questions/765736/using-pil-to-make-all-white-pixels-transparent"""
        img = img.convert("RGBA")
        datas = img.getdata()

        newData = []
        for item in datas:
            if item[0] == 255 and item[1] == 255 and item[2] == 255:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)

        img.putdata(newData)
        return img

    def invert_barcode(self, img):
        """https://stackoverflow.com/questions/765736/using-pil-to-make-all-white-pixels-transparent"""
        img = img.convert("RGBA")
        datas = img.getdata()

        newData = []
        for item in datas:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                newData.append((255, 255, 255))
            else:
                newData.append(item)

        img.putdata(newData)
        return img

    async def dl_image(self, url):
        """Download bytes like object of user avatar"""
        async with self.session.get(url) as resp:
            test = await resp.read()
            return BytesIO(test)

    def make_template(self, user, badge, template):
        """Build the base template before determining animated or not"""
        if hasattr(user, "roles"):
            department = _("GENERAL SUPPORT") if user.top_role.name == "@everyone"\
                                         else user.top_role.name.upper()
            status = user.status
            level = str(len(user.roles))
        else:
            department = _("GENERAL SUPPORT")
            status = "online"
            level = "1"
        if str(status) == "online":
            status = _("ACTIVE")
        if str(status) == "offline":
            status = _("COMPLETING TASK")
        if str(status) == "idle":
            status = _("AWAITING INSTRUCTIONS")
        if str(status) == "dnd":
            status = _("MIA")
        barcode = BytesIO()
        temp_barcode = generate("code39", 
                                str(user.id), 
                                writer=ImageWriter(), 
                                output=barcode)
        barcode = Image.open(barcode)
        barcode = self.remove_white_barcode(barcode)
        fill = (0, 0, 0) # text colour fill
        if badge.is_inverted:
            fill = (255, 255, 255)
            barcode = self.invert_barcode(barcode)
        template = Image.open(template)
        template = template.convert("RGBA")        
        barcode = barcode.convert("RGBA")
        barcode = barcode.resize((555,125), Image.ANTIALIAS)
        template.paste(barcode, (400,520), barcode)
        # font for user information
        font_loc = str(bundled_data_path(self)/"arial.ttf") 
        try:
            font1 = ImageFont.truetype(font_loc, 30)
            font2 = ImageFont.truetype(font_loc, 24)
        except Exception as e:
            print(e)
            font1 = None
            font2 = None
        # font for extra information
        
        draw = ImageDraw.Draw(template)
        # adds username
        draw.text((225, 330), str(user.display_name), fill=fill, font=font1)
        # adds ID Class
        draw.text((225, 400), badge.code + "-" + str(user).split("#")[1], fill=fill, font=font1)
        # adds user id
        draw.text((250, 115), str(user.id), fill=fill, font=font2)
        # adds user status
        draw.text((250, 175), status, fill=fill, font=font2)
        # adds department from top role
        draw.text((250, 235), department, fill=fill, font=font2)
        # adds user level
        draw.text((420, 475), _("LEVEL ") + level, fill="red", font=font1)
        # adds user level
        if badge.badge_name != "discord" and user is discord.Member:
          draw.text((60, 585), str(user.joined_at), fill=fill, font=font2)
        else:
          draw.text((60, 585), str(user.created_at), fill=fill, font=font2)
        return template

    def make_animated_gif(self, template, avatar):
        """Create animated badge from gif avatar"""
        gif_list = [frame.copy() for frame in ImageSequence.Iterator(avatar)]
        img_list = []
        num = 0
        for frame in gif_list:
            temp2 = template.copy()
            watermark = frame.copy()
            watermark = watermark.convert("RGBA")
            watermark = watermark.resize((100,100))
            watermark.putalpha(128)
            id_image = frame.resize((165, 165))
            temp2.paste(watermark, (845,45, 945,145), watermark)
            temp2.paste(id_image, (60,95, 225, 260))
            temp2.thumbnail((500, 339), Image.ANTIALIAS)
            img_list.append(temp2)
            num += 1
            temp = BytesIO()

            temp2.save(temp, format="GIF", save_all=True, append_images=img_list, duration=0, loop=0)
            temp.name = "temp.gif"
            if sys.getsizeof(temp) > 7000000 and sys.getsizeof(temp) < 8000000:
                break
        return temp

    def make_badge(self, template, avatar):
        """Create basic badge from regular avatar"""
        watermark = avatar.convert("RGBA")
        watermark.putalpha(128)
        watermark = watermark.resize((100,100))
        id_image = avatar.resize((165, 165))
        template.paste(watermark, (845,45, 945,145), watermark)
        template.paste(id_image, (60,95, 225, 260))
        temp = BytesIO()
        template.save(temp, format="PNG")
        temp.name = "temp.gif"
        return temp

    async def create_badge(self, user, badge, is_gif:bool):
        """Async create badges handler"""
        template_img = await self.dl_image(badge.file_name)
        task = functools.partial(self.make_template, 
                                 user=user, 
                                 badge=badge, 
                                 template=template_img)
        task = self.bot.loop.run_in_executor(None, task)
        try:
            template = await asyncio.wait_for(task, timeout=60)
        except asyncio.TimeoutError:
            return
        if user.is_avatar_animated() and is_gif:
            url = user.avatar_url_as(format="gif")
            avatar = Image.open(await self.dl_image(url))
            task = functools.partial(self.make_animated_gif, 
                                     template=template, 
                                     avatar=avatar)
            task = self.bot.loop.run_in_executor(None, task)
            try:
                temp = await asyncio.wait_for(task, timeout=60)
            except asyncio.TimeoutError:
                return
            
        else:
            url = user.avatar_url_as(format="png")
            avatar = Image.open(await self.dl_image(url))
            task = functools.partial(self.make_badge, 
                                     template=template, 
                                     avatar=avatar)
            task = self.bot.loop.run_in_executor(None, task)
            try:
                temp = await asyncio.wait_for(task, timeout=60)
            except asyncio.TimeoutError:
                return
            
        temp.seek(0)
        return temp

    async def get_badge(self, badge_name, guild=None):
        if guild is None:
            guild_badges = []
        else:
            guild_badges = await self.config.guild(guild).badges()
        all_badges = await self.config.badges() + guild_badges
        to_return = None
        for badge in all_badges:
            if badge_name.lower() in badge["badge_name"].lower():
                to_return = await Badge.from_json(badge)
        return to_return

    @commands.command(aliases=["badge"])
    async def badges(self, ctx, *, badge):
        """
            Creates a fun fake badge based on your discord profile

            `badge` is the name of the badges
            do `[p]listbadges` to see available badges
        """
        guild = ctx.message.guild
        user = ctx.message.author
        if badge.lower() == "list":
            await ctx.invoke(self.listbadges)
            return
        badge = await self.get_badge(badge, guild)
        async with ctx.channel.typing():
            badge_img = await self.create_badge(user, badge, False)
            if badge_img is None:
                await ctx.send(_("Something went wrong sorry!"))
                return
            image = discord.File(badge_img)
            await ctx.send(file=image)

    @commands.command(aliases=["gbadge"])
    async def gbadges(self, ctx, *, badge):
        """
            Creates a fun fake gif badge based on your discord profile
            this only works if you have a gif avatar

            `badge` is the name of the badges
            do `[p]listbadges` to see available badges
        """
        guild = ctx.message.guild
        user = ctx.message.author
        if badge.lower() == "list":
            await ctx.invoke(self.listbadges)
            return
        badge = await self.get_badge(badge, guild)
        async with ctx.channel.typing():
            badge_img = await self.create_badge(user, badge, True)
            if badge_img is None:
                await ctx.send(_("Something went wrong sorry!"))
                return
            image = discord.File(badge_img)
            await ctx.send(file=image)


    @commands.command()
    async def listbadges(self, ctx):
        """
            List the available badges that can be created
        """
        guild = ctx.message.guild
        global_badges = await self.config.badges()
        guild_badges =  await self.config.guild(guild).badges()
        msg = ", ".join(badge["badge_name"] for badge in global_badges)

        em = discord.Embed()
        if await self.bot.db.guild(guild).use_bot_color():
            em.colour = guild.me.colour
        else:
            em.colour = await self.bot.db.color()
        #for badge in await self.config.badges():
        em.add_field(name=_("Global Badges"), value=msg)
        if guild_badges != []:
            badges = ", ".join(badge["badge_name"] for badge in guild_badges)
            em.add_field(name=_("Global Badges"), value=badges)
        await ctx.send(embed=em)
    
    def __unload(self):
        self.bot.loop.create_task(self.session.close())
