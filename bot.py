from typing import List
from os import getenv
import json
import random
import re
import requests
from discord import Intents, Message
from discord.ext import commands
from discord.ext.commands import Context
from dotenv import load_dotenv
from notifiers import get_notifier

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!", case_insensitive=True, intents=intents)


class SeznamPrikazu:
    def __init__(self) -> None:
        pass

    def create_message(self):
        message = (
            "```\n"
            "Příkazy:\n"
            "!list_memes\n"
            '!make_meme <id> "<text 1>" "<text 2>"\n'
            "!subscribe <email>\n"
            "!unsubscribe\n"
            "!play_hangman\n"
            "!guess <písmeno>\n"
            "```"
        )
        return message


class MemeGenerator:
    def __init__(self) -> None:
        pass

    def list_memes(self) -> str:
        response = requests.get("https://api.imgflip.com/get_memes",
                                timeout=10)
        memes = response.json()
        meme_id = []
        meme_name = []
        for i in range(25):
            meme_id.append(memes["data"]["memes"][i]["id"])
            meme_name.append(memes["data"]["memes"][i]["name"])
        message = "```"
        for i in range(25):
            message += "\n" + meme_id[i] + str(" ") + meme_name[i]
        message += "```"
        return message

    def make_meme(
        self, template_id: int, top_text: str, bottom_text: str
    ) -> str:
        response = requests.post("https://api.imgflip.com/caption_image",
                                 timeout=10,
                                 data={"template_id": template_id,
                                       "username": getenv("MEME_USERNAME"),
                                       "password": getenv("MEME_PASSWORD"),
                                       "text0": top_text,
                                       "text1": bottom_text})
        meme_data = response.json()
        return meme_data["data"]["url"]


class MentionsNotifier:
    def __init__(self) -> None:
        with open("emails.json", "r", encoding="utf8") as file:
            self.emails = json.load(file)

    def subscribe(self, user_id: int, email: str) -> None:
        with open("emails.json", "w", encoding="utf8") as file:
            self.emails[str(user_id)] = email
            json.dump(self.emails, file)

    def unsubscribe(self, user_id: int) -> None:
        if user_id in self.emails:
            with open("emails.json", "w", encoding="utf8") as file:
                del self.emails[user_id]
                json.dump(self.emails, file)

    def notify_about_mention(self, user_id: List, msg_url: str) -> None:
        user_email = self.emails[str(user_id)]
        email = get_notifier("email")
        settings = {'host': getenv("SMTP_HOST"),
                    'port': 465,
                    'ssl': True,
                    'username': getenv("MAIL_USERNAME"),
                    'password': getenv("MAIL_PASSWORD"),
                    'to': user_email,
                    'from': getenv("MAIL_USERNAME"),
                    'subject': "Discord mention notification",
                    'message': "Someone mentioned you in channel " + msg_url}
        email.notify(**settings)


class Hangman:
    def start_game(self, player) -> None:
        with open("words.txt", "r", encoding="utf8") as file:
            # nacteni slov ze souboru
            all_words = file.readlines()
        self.word_unformatted = random.choice(all_words)  # vyber slova
        # odebrani \n pokud ho slovo obsahuje
        if "\n" in self.word_unformatted:
            self.word = self.word_unformatted[:-1]
        else:
            self.word = self.word_unformatted
        print(self.word)  # vypsani slova do konzole pro kontrolu
        self.player = player
        self.lives = 7
        self.guesses = []
        self.word_letters = []
        for char in self.word:
            self.word_letters.append("- ")

    def play(self, letter) -> int:
        if letter in self.guesses:
            return 2  # pripad, kdy je jiz pismeno hadano
        self.guesses.append(letter)
        if letter in self.word:  # kontrola zda je pismeno ve slove
            k = self.word.count(letter)
            if k > 1:  # pokud je pismeno ve slove vickrat
                indices = [i.start() for i in re.finditer(letter, self.word)]
                for i in range(k):
                    self.word_letters[indices[i]] = letter
                return 1
            if k == 1:  # pokud je pismeno ve slove jednou
                self.word_letters[self.word.find(letter)] = letter
                return 1
        else:  # pismeno ve slove neni
            self.lives -= 1  # odebrani zivota
            return 0


# --- oznameni o pripojeni ---
@bot.event
async def on_ready() -> None:
    print("Bot se připojil.")


# --- seznam prikazu ---
seznam_prikazu = SeznamPrikazu


@bot.command(name="seznam_prikazu")
async def prikazy1(ctx: Context) -> None:
    await ctx.send(seznam_prikazu.create_message(ctx))


@bot.command(name="prikazy")
async def prikazy2(ctx: Context) -> None:
    await ctx.send(seznam_prikazu.create_message(ctx))

# --- tvorba memu ---
meme_generator = MemeGenerator()


@bot.command(name="list_memes")
async def list_memes(ctx: Context) -> None:
    meme_list = meme_generator.list_memes()
    await ctx.send(meme_list)
    await ctx.send("https://imgflip.com/memetemplates")


@bot.command(name="make_meme")
async def make_meme(
    ctx: Context, template_id: int, top_text: str, bottom_text: str
) -> None:
    meme_url = meme_generator.make_meme(template_id, top_text, bottom_text)
    await ctx.send(meme_url)

# --- oznameni o oznacení mailem ---
mentions_notifier = MentionsNotifier()


@bot.command(name="subscribe")
async def subscribe(ctx: Context, email: str) -> None:
    mentions_notifier.subscribe(ctx.author.id, email)


@bot.command(name="unsubscribe")
async def unsubscribe(ctx: Context) -> None:
    mentions_notifier.unsubscribe(ctx.author.id)


@bot.event
async def on_message(message: Message) -> None:
    users = message.mentions
    mentions = []
    if users != []:
        for index, user in enumerate(users):
            mentions.append(users[index].id)
    for user in mentions:
        if str(user) in mentions_notifier.emails:
            mentions_notifier.notify_about_mention(user,
                                                   message.jump_url)
    await bot.process_commands(message)


# --- hra hangman ---
hangman = Hangman()


@bot.command(name="play_hangman")
async def play_hangman(ctx: Context) -> None:
    hangman.start_game(ctx.author.name)
    displayed_word = ""
    for key, value in enumerate(hangman.word):
        displayed_word += hangman.word_letters[key] + " "
    global MSG_ID
    MSG_ID = await ctx.send("**hangman**\n"
                            + "Hráč: " + str(hangman.player) + "\n"
                            + "Hádaná písmena: " + "\n"
                            + "Životy: " + str(hangman.lives) + "\n"
                            + "Slovo: " + displayed_word)


@bot.command(name="guess")
async def guess(ctx: Context, letter: str) -> None:
    await ctx.message.delete()
    global MSG_ID
    if len(letter) != 1 or not letter.isalpha():
        await ctx.send("Hádejte pouze 1 písmeno.")
        return
    return_code = hangman.play(letter)
    guessed_letters = ""
    displayed_word = ""
    for index, value in enumerate(hangman.word):
        displayed_word += hangman.word_letters[index] + " "
    for guess in hangman.guesses:
        guessed_letters += guess + " "
    if "- " not in hangman.word_letters:
        await MSG_ID.edit(content=("**hangman**\n"
                                   + "Hráč: " + str(hangman.player) + "\n"
                                   + "Hádaná písmena: "
                                   + guessed_letters + "\n"
                                   + "Životy: " + str(hangman.lives) + "\n"
                                   + "Slovo: " + displayed_word + "\n"
                                   + "Vyhráli jste!"))
        MSG_ID = None
        return
    if return_code == 1:
        await MSG_ID.edit(content=("**hangman**\n"
                                   + "Hráč: " + str(hangman.player) + "\n"
                                   + "Hádaná písmena: "
                                   + guessed_letters + "\n"
                                   + "Životy: " + str(hangman.lives) + "\n"
                                   + "Slovo: " + displayed_word + "\n"
                                   + "Správný tip."))
    elif return_code == 0:
        await MSG_ID.edit(content=("**hangman**\n"
                                   + "Hráč: " + str(hangman.player) + "\n"
                                   + "Hádaná písmena: "
                                   + guessed_letters + "\n"
                                   + "Životy: " + str(hangman.lives) + "\n"
                                   + "Slovo: " + displayed_word + "\n"
                                   + "Špatný tip."))
    if return_code == 2:
        await MSG_ID.edit(content=("**hangman**\n"
                                   + "Hráč: " + str(hangman.player) + "\n"
                                   + "Hádaná písmena: "
                                   + guessed_letters + "\n"
                                   + "Životy: " + str(hangman.lives) + "\n"
                                   + "Slovo: " + displayed_word + "\n"
                                   + "Písmeno již bylo hádáno."))
    if hangman.lives == 0:
        await MSG_ID.edit(content=("**hangman**\n"
                                   + "Hráč: " + str(hangman.player) + "\n"
                                   + "Hádaná písmena: "
                                   + guessed_letters + "\n"
                                   + "Životy: " + str(hangman.lives) + "\n"
                                   + "Slovo: " + displayed_word + "\n"
                                   + "Prohráváte. Slovo bylo: "
                                   + hangman.word))
        MSG_ID = None

bot.run(TOKEN)
