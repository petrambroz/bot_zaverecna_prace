from os import getenv
import requests
from discord import Intents, Message
from discord.ext import commands
from discord.ext.commands import Context
from dotenv import load_dotenv
from notifiers import get_notifier
import json
import re
import random
from typing import List
load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!", case_insensitive=True, intents=intents)


class MemeGenerator:
    def __init__(self) -> None:
        pass

    def list_memes(self) -> str:
        response = requests.get("https://api.imgflip.com/get_memes")
        memes = response.json()
        memes_striped = memes["data"]["memes"]
        meme_id = []
        meme_name = []
        for i in range(25):
            meme_id.append(memes["data"]["memes"][i]["id"])
            meme_name.append(memes["data"]["memes"][i]["name"])
        return_message = "```"
        for i in range(25):
            return_message += "\n" + meme_id[i] + str(" ") + meme_name[i]
        return_message += "```"
        return return_message

    def make_meme(
        self, template_id: int, top_text: str, bottom_text: str
    ) -> str:
        response = requests.post("https://api.imgflip.com/caption_image",
                                 data={"template_id": template_id,
                                       "username": getenv("MEME_USERNAME"),
                                       "password": getenv("MEME_PASSWORD"),
                                       "text0": top_text,
                                       "text1": bottom_text})
        meme_data = response.json()
        return meme_data["data"]["url"]


class MentionsNotifier:
    def __init__(self) -> None:
        with open("emails.json", "r") as file:
            self.emails = json.load(file)

    def subscribe(self, user_id: int, email: str) -> None:
        with open("emails.json", "w") as file:
            self.emails[str(user_id)] = email
            json.dump(self.emails, file)

    def unsubscribe(self, user_id: int) -> None:
        if user_id in self.emails:
            with open("emails.json", "w") as file:
                del self.emails[user_id]
                json.dump(self.emails, file)

    def notify_about_mention(self, user_id: List, msg_content: str,
                             msg_url: str) -> None:
        user_email = self.emails[str(user_id)]
        email = get_notifier("email")
        settings = {'host': 'ksi2022smtp.iamroot.eu',
                    'port': 465,
                    'ssl': True,
                    'username': getenv("MAIL_USERNAME"),
                    'password': getenv("MAIL_PASSWORD"),
                    'to': user_email,
                    'from': getenv("MAIL_USERNAME"),
                    'subject': "Discord mention notification",
                    'message': "Someone mentioned you in channel " + msg_url}
        res = email.notify(**settings)


class Hangman:
    def start_game(self, player) -> None:
        with open("words.txt", "r") as file:
            all_words = file.readlines()
        self.word_1 = random.choice(all_words)
        # odebrani \n pokud ho slovo obsahuje
        if "\n" in self.word_1:
            self.word = self.word_1[:-1]
        else:
            self.word = self.word_1
        print(self.word)
        self.player = player
        self.lives = 7
        self.guesses = []
        self.word_letters = []
        for char in self.word:
            self.word_letters.append("- ")

    def play(self, letter) -> int:
        if letter in self.guesses:
            return 2
        self.guesses.append(letter)
        if letter in self.word:
            k = self.word.count(letter)
            if k > 1:
                indices = [i.start() for i in re.finditer(letter, self.word)]
                for i in range(k):
                    self.word_letters[indices[i]] = letter
                return 1
            if k == 1:
                self.word_letters[self.word.find(letter)] = letter
                return 1
        else:
            self.lives -= 1
            return 0


# --- oznameni o pripojeni ---
@bot.event
async def on_ready() -> None:
    print(f"Bot se připojil.")


# --- seznam prikazu ---
@bot.command(name="seznam_prikazu")
async def prikazy(ctx: Context) -> None:
    message = (
        "**Příkazy **\n"
        "!list_memes\n"
        '!make_meme <id> "<text 1>" "<text 2>"\n'
        "!subscribe <email>\n"
        "!unsubscribe\n"
        "!play_hangman\n"
        "!guess <písmeno>\n"
    )
    await ctx.send(message)


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
        for i in range(len(users)):
            mentions.append(users[i].id)
    for user in mentions:
        if str(mentions[i]) in mentions_notifier.emails:
            mentions_notifier.notify_about_mention(mentions[i],
                                                   message.content,
                                                   message.jump_url)
    await bot.process_commands(message)


# --- hra hangman ---
hangman = Hangman()


@bot.command(name="play_hangman")
async def play_hangman(ctx: Context) -> None:
    hangman.start_game(ctx.author.name)
    guess = ""
    printword = ""
    for i in range(len(hangman.word)):
        printword += hangman.word_letters[i] + " "
    global msg_id
    msg_id = await ctx.send("**hangman**\n"
                            + "Player: " + str(hangman.player) + "\n"
                            + "Guesses: " + guess + "\n"
                            + "Lives: " + str(hangman.lives) + "\n"
                            + "Word: " + printword)


@bot.command(name="guess")
async def guess(ctx: Context, letter: str) -> None:
    await ctx.message.delete()
    global msg_id
    if len(letter) != 1 or not letter.isalpha():
        await ctx.send("Guess only one letter at time.")
        return
    r = hangman.play(letter)
    guessed_letters = ""
    printword = ""
    for i in range(len(hangman.word)):
        printword += hangman.word_letters[i] + " "
    for i in range(len(hangman.guesses)):
        guessed_letters += hangman.guesses[i] + " "
    if "- " not in hangman.word_letters:
        await msg_id.edit(content=("**hangman**\n"
                                   + "Player: " + str(hangman.player) + "\n"
                                   + "Guesses: " + guessed_letters + "\n"
                                   + "Lives: " + str(hangman.lives) + "\n"
                                   + "Word: " + printword + "\n"
                                   + "You won!"))
        msg_id = None
        return
    if r == 1:
        await msg_id.edit(content=("**hangman**\n"
                                   + "Player: " + str(hangman.player) + "\n"
                                   + "Guesses: " + guessed_letters + "\n"
                                   + "Lives: " + str(hangman.lives) + "\n"
                                   + "Word: " + printword + "\n"
                                   + "Correct guess."))
    elif r == 0:
        await msg_id.edit(content=("**hangman**\n"
                                   + "Player: " + str(hangman.player) + "\n"
                                   + "Guesses: " + guessed_letters + "\n"
                                   + "Lives: " + str(hangman.lives) + "\n"
                                   + "Word: " + printword + "\n"
                                   + "Wrong guess."))
    if r == 2:
        await msg_id.edit(content=("**hangman**\n"
                                   + "Player: " + str(hangman.player) + "\n"
                                   + "Guesses: " + guessed_letters + "\n"
                                   + "Lives: " + str(hangman.lives) + "\n"
                                   + "Word: " + printword + "\n"
                                   + "You already guessed that."))
    if hangman.lives == 0:
        await msg_id.edit(content=("**hangman**\n"
                                   + "Player: " + str(hangman.player) + "\n"
                                   + "Guesses: " + guessed_letters + "\n"
                                   + "Lives: " + str(hangman.lives) + "\n"
                                   + "Word: " + printword + "\n"
                                   + "You lost. The word was: "
                                   + hangman.word))
        msg_id = None

bot.run(TOKEN)
