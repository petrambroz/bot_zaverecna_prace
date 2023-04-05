import random
from dataclasses import dataclass
from os import getenv
from typing import Dict, Set

import requests
from discord import Intents, Message
from discord.ext import commands
from discord.ext.commands import Context
from dotenv import load_dotenv
from notifiers import get_notifier

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")
IMGFLIP_API_URL = "https://api.imgflip.com"

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!", case_insensitive=True, intents=intents
)


class MemeGenerator:
    def list_memes(self) -> str:
        response = requests.get(url=f"{IMGFLIP_API_URL}/get_memes")

        data = response.json()
        if not data["success"]:
            return "Memes could not be listed."

        message = ""
        meme_data = data["data"]["memes"]
        for meme in meme_data[:25]:
            spaces = " " * (9 - len(meme["id"]))
            message += f"{meme['id']}{spaces} {meme['name']}\n"

        return f"**Memes**\n```{message}```"

    def make_meme(
        self, template_id: int, top_text: str, bottom_text: str
    ) -> str:
        response = requests.post(
            url=f"{IMGFLIP_API_URL}/caption_image",
            params={
                "template_id": template_id,
                "username": getenv("IMGFLIP_NAME"),
                "password": getenv("IMGFLIP_PASSWORD"),
                "text0": top_text,
                "text1": bottom_text,
            },
        )
        data = response.json()
        if not data["success"]:
            return f"Meme could not be generated. {data['error_message']}"

        meme_url = data["data"]["url"]
        return meme_url


class MentionsNotifier:
    def __init__(self) -> None:
        self.emails = {}

    def subscribe(self, user_id: int, email: str) -> None:
        self.emails[user_id] = email

    def unsubscribe(self, user_id: int) -> None:
        del self.emails[user_id]

    def notify_about_mention(self, user_id: int, msg_content: str) -> None:
        email = get_notifier("email")
        settings = {
            "host": "ksi2022smtp.iamroot.eu",
            "port": 587,
            "username": getenv("EMAIL_USERNAME"),
            "password": getenv("EMAIL_PASSWORD"),
            "tls": True,
            "to": self.emails.get(user_id),
            "from": getenv("EMAIL_USERNAME"),
            "subject": "Discord Mention",
            "message": msg_content,
        }
        email.notify(**settings)


@dataclass
class GameState:
    name: str
    word: str
    already_guessed: Set[str]
    lives: int
    message: Message

    def get_formatted_string(self) -> str:
        return (
            "**Hangman**\n"
            f"Player: {self.name}\n"
            f"Guesses: {', '.join(self.already_guessed).upper()}\n"
            f"Lives: {self.lives}\n"
            f"Word: {self._format_word_hidden()}\n"
        )

    def _format_word_hidden(self) -> str:
        return " ".join(
            "-" if letter not in self.already_guessed else letter.upper()
            for letter in self.word
        )


class Hangman:
    DEFAULT_LIVES_COUNT = 7

    def __init__(self) -> None:
        self.game_states_by_users: Dict[int, GameState] = {}

    def new_game(self, user_id: int, name: str, message: Message):
        self.game_states_by_users[user_id] = GameState(
            name=name,
            word=self.random_word(),
            already_guessed=set(),
            lives=self.DEFAULT_LIVES_COUNT,
            message=message,
        )

    def random_word(self) -> str:
        with open("words.txt", "r") as file:
            all_words = file.read().splitlines()
        return random.choice(all_words)

    def process_guess(self, user_id: int, letter: str) -> str:
        game_state = self.game_states_by_users.get(user_id)

        if game_state is None:
            return "You have to start a new game first."
        if len(letter) != 1 or not letter.isalpha():
            return "Enter only 1 letter at a time."
        if letter in game_state.already_guessed:
            return "You already guessed that."

        # Add letter to guessed letters
        game_state.already_guessed.add(letter)

        if letter in game_state.word:
            # Guess is correct
            if set(game_state.word).issubset(game_state.already_guessed):
                return "You won!"
            return "Correct guess."

        # Guess is incorrect
        game_state.lives -= 1
        if game_state.lives <= 0:
            return f"You lost! The word was: {game_state.word}"
        return "Wrong guess."

    def get_game_string_by_user_id(self, user_id: int) -> str:
        return self.game_states_by_users[user_id].get_formatted_string()

    def get_message_by_user_id(self, user_id: int) -> Message:
        return self.game_states_by_users[user_id].message

    def delete_game(self, user_id: int):
        del self.game_states_by_users[user_id]


# ---------------------------
@bot.event
async def on_ready() -> None:
    print(f"Bot has connected to Discord!")


@bot.command(name="list_commands")
async def commands(ctx: Context) -> None:
    msg = (
        "**Commands **\n"
        "!list_memes\n"
        '!make_meme <id> "<top_text>" "<bottom_text>"\n'
        "!subscribe <email-address>\n"
        "!unsubscribe\n"
        "!play_hangman\n"
        "!guess <letter>\n"
    )
    await ctx.send(msg)


# --------- LEVEL 1 ----------
meme_generator = MemeGenerator()


@bot.command(name="list_memes")
async def list_memes(ctx: Context) -> None:
    meme_list = meme_generator.list_memes()
    await ctx.send(meme_list)


@bot.command(name="make_meme")
async def make_meme(
    ctx: Context, template_id: int, top_text: str, bottom_text: str
) -> None:
    meme_url = meme_generator.make_meme(template_id, top_text, bottom_text)
    await ctx.send(meme_url)


# --------- LEVEL 2 ----------
mentions_notifier = MentionsNotifier()


@bot.command(name="subscribe")
async def subscribe(ctx: Context, email: str) -> None:
    mentions_notifier.subscribe(ctx.author.id, email)


@bot.command(name="unsubscribe")
async def unsubscribe(ctx: Context) -> None:
    mentions_notifier.unsubscribe(ctx.author.id)


@bot.event
async def on_message(message: Message) -> None:
    if message.mentions:
        for user in message.mentions:
            if user.id in mentions_notifier.emails:
                url = message.jump_url
                content = f"Someone mentioned you in channel {url}"
                mentions_notifier.notify_about_mention(user.id, content)

    await bot.process_commands(message)


# --------- LEVEL 3 ----------
hangman = Hangman()


@bot.command(name="play_hangman")
async def play_hangman(ctx: Context) -> None:
    message = await ctx.send("Starting a new game...")
    hangman.new_game(ctx.author.id, ctx.author.name, message)
    game_string = hangman.get_game_string_by_user_id(ctx.author.id)

    await message.edit(content=game_string)


@bot.command(name="guess")
async def guess(ctx: Context, letter: str) -> None:
    guess_result = hangman.process_guess(ctx.author.id, letter)
    if guess_result == "You have to start a new game first.":
        await ctx.send(content=guess_result)
        return

    game_string = hangman.get_game_string_by_user_id(ctx.author.id)
    message = hangman.get_message_by_user_id(ctx.author.id)

    if any(res in guess_result for res in ["You won!", "You lost!"]):
        hangman.delete_game(ctx.author.id)

    await message.edit(content=game_string + guess_result)
    await ctx.message.delete()


if TOKEN:
    bot.run(TOKEN)
