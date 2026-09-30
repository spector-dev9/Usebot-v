"""Games — Telegram dice, quick games, duels and trivia."""
import asyncio
import random
from collections import defaultdict

from telethon import Button, events
from telethon.tl.types import InputMediaDice
from sqlalchemy import select

from helpers.decorators import command, listener
from utils.messages import Messages
from database.connection import get_session
from database.models import GameStat
from core.logger import setup_logger

logger = setup_logger(__name__)

_RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
_RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

_8BALL = [
    "It is certain.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.",
    "Outlook good.", "Yes.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.",
    "Concentrate and ask again.", "Don't count on it.",
    "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

_TRIVIA = [
    {"q": "What is the capital of France?", "o": ["Paris", "London", "Berlin", "Madrid"], "a": 0},
    {"q": "How many continents are commonly taught?", "o": ["5", "6", "7", "8"], "a": 2},
    {"q": "Largest planet?", "o": ["Earth", "Mars", "Jupiter", "Saturn"], "a": 2},
    {"q": "Who wrote Romeo and Juliet?", "o": ["Dickens", "Shakespeare", "Tolstoy", "Hemingway"], "a": 1},
    {"q": "WW2 ended in?", "o": ["1943", "1944", "1945", "1946"], "a": 2},
    {"q": "Chemical symbol for gold?", "o": ["Go", "Gd", "Au", "Ag"], "a": 2},
    {"q": "Sides in a hexagon?", "o": ["5", "6", "7", "8"], "a": 1},
    {"q": "Bits in a byte?", "o": ["4", "8", "16", "32"], "a": 1},
]
_trivia = {}


async def _bump(uid, field, amount=1):
    try:
        async with get_session() as session:
            result = await session.execute(
                select(GameStat).where(GameStat.user_id == uid)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = GameStat(user_id=uid)
                session.add(row)
            setattr(row, field, (getattr(row, field, 0) or 0) + amount)
    except Exception as e:
        logger.warning("game stat update failed: %s", e)


async def _dice(client, chat_id, emoji):
    try:
        sent = await client.send_message(chat_id, file=InputMediaDice(emoji))
        await asyncio.sleep(2)
        result = await client.get_messages(chat_id, ids=sent.id)
        return getattr(result.media, "value", None)
    except Exception as e:
        logger.warning("dice failed: %s", e)
        return None


@command("dice", "Roll dice")
async def dice_handler(event):
    await event.delete()
    value = await _dice(event.client, event.chat_id, "🎲")
    if value is not None:
        await _bump(event.sender_id, "dice_played")


@command("dart", "Throw a dart")
async def dart_handler(event):
    await event.delete()
    await _dice(event.client, event.chat_id, "🎯")


@command("bowl", "Roll a bowling ball")
async def bowl_handler(event):
    await event.delete()
    await _dice(event.client, event.chat_id, "🎳")


@command("basket", "Shoot basketball")
async def basket_handler(event):
    await event.delete()
    await _dice(event.client, event.chat_id, "🏀")


@command("football", "Kick football")
async def football_handler(event):
    await event.delete()
    await _dice(event.client, event.chat_id, "⚽")


@command("slot", "Spin slots")
async def slot_handler(event):
    await event.delete()
    value = await _dice(event.client, event.chat_id, "🎰")
    if value is None:
        return
    await _bump(event.sender_id, "slots_played")
    if value == 64:
        await _bump(event.sender_id, "jackpots")
        await event.client.send_message(event.chat_id, "🎉 **JACKPOT!** 🎰💰")


@command(r"8ball (.+)", "Magic 8-ball")
async def eightball_handler(event):
    await event.edit(
        f"🎱 **Q:** {event.pattern_match.group(1)}\n"
        f"**A:** _{random.choice(_8BALL)}_"
    )


@command("coinflip", "Flip a coin")
async def coinflip_handler(event):
    await event.edit(f"🪙 **{random.choice(['Heads', 'Tails'])}**")


@command(r"rps (rock|paper|scissors)", "Rock-paper-scissors")
async def rps_handler(event):
    user = event.pattern_match.group(1).lower()
    bot = random.choice(list(_RPS_BEATS))
    if user == bot:
        result = "🤝 **Tie!**"
    elif _RPS_BEATS[user] == bot:
        result = "🎉 **You win!**"
    else:
        result = "🤖 **Bot wins!**"
    await event.edit(
        f"**You:** {_RPS_EMOJI[user]} {user}\n"
        f"**Bot:** {_RPS_EMOJI[bot]} {bot}\n\n{result}"
    )


_duels = {}


@command("duel", "Challenge the replied user to an RPS duel")
async def duel_handler(event):
    if not event.is_reply:
        await event.edit(Messages.error("Reply to the user you want to challenge."))
        return

    replied = await event.get_reply_message()
    opponent = await replied.get_sender()
    if not opponent or opponent.id == event.sender_id or getattr(opponent, "bot", False):
        await event.edit(Messages.error("Invalid opponent."))
        return

    me = await event.get_sender()
    challenger_name = getattr(me, "first_name", None) or "You"
    opponent_name = getattr(opponent, "first_name", None) or str(opponent.id)

    message = await event.respond(
        f"⚔️ **DUEL**\n\n**{challenger_name}** challenges **{opponent_name}**!",
        buttons=[[
            Button.inline("⚔️ Accept", data=f"duel:accept:{event.sender_id}:{opponent.id}"),
            Button.inline("❌ Decline", data=f"duel:decline:{event.sender_id}:{opponent.id}"),
        ]],
    )
    _duels[message.id] = {
        "challenger": event.sender_id,
        "opponent": opponent.id,
        "challenger_name": challenger_name,
        "opponent_name": opponent_name,
    }
    await event.delete()


@listener(events.CallbackQuery())
async def duel_callback(event):
    try:
        data = event.data.decode()
    except Exception:
        return
    if not data.startswith("duel:"):
        return

    parts = data.split(":")
    if len(parts) != 4:
        return

    _, action, challenger, opponent = parts
    challenger, opponent = int(challenger), int(opponent)
    duel = _duels.get(event.message_id)
    if not duel:
        await event.answer("Expired.", alert=True)
        return

    if event.sender_id != opponent:
        await event.answer("Only the challenged user can respond.", alert=True)
        return

    if action == "decline":
        _duels.pop(event.message_id, None)
        await event.edit(f"❌ **{duel['opponent_name']}** declined.")
        return

    if action != "accept":
        return

    first = random.choice(list(_RPS_BEATS))
    second = random.choice(list(_RPS_BEATS))
    if first == second:
        result = "🤝 Tie!"
        winner = None
    elif _RPS_BEATS[first] == second:
        result = f"🏆 **{duel['challenger_name']}** wins!"
        winner = challenger
    else:
        result = f"🏆 **{duel['opponent_name']}** wins!"
        winner = opponent

    _duels.pop(event.message_id, None)
    await event.edit(
        "⚔️ **DUEL**\n\n"
        f"**{duel['challenger_name']}:** {_RPS_EMOJI[first]} {first}\n"
        f"**{duel['opponent_name']}:** {_RPS_EMOJI[second]} {second}\n\n"
        f"{result}"
    )
    if winner:
        loser = opponent if winner == challenger else challenger
        await _bump(winner, "duels_won")
        await _bump(loser, "duels_lost")


_LETTERS = ["A", "B", "C", "D"]

_trivia = {}


@command("trivia", "Trivia question")
async def trivia_handler(event):
    """Usage: `.trivia`"""
    question = random.choice(_TRIVIA)
    options = list(enumerate(question["o"]))
    random.shuffle(options)
    shuffled = [text for _, text in options]
    correct = next(i for i, (original, _) in enumerate(options) if original == question["a"])

    body = f"🧠 **TRIVIA**\n\n{question['q']}\n"
    for i, text in enumerate(shuffled):
        body += f"\n**{_LETTERS[i]}.**  {text}"

    msg = await event.respond(body)
    btns = [[Button.inline(_LETTERS[i], data=f"triv:{msg.id}:{i}")
             for i in range(len(shuffled))]]
    await msg.edit(body, buttons=btns)
    _trivia[msg.id] = {"correct": correct, "chat_id": event.chat_id}
    await event.delete()


@listener(events.CallbackQuery())
async def trivia_callback(event):
    try:
        data = event.data.decode("utf-8")
    except Exception:
        return
    if not data.startswith("triv:"):
        return
    parts = data.split(":")
    if len(parts) != 3:
        return
    _, _, cs = parts
    try:
        chosen = int(cs)
    except ValueError:
        await event.answer(); return

    state = _trivia.get(event.message_id)
    if not state:
        await event.answer("This trivia expired.", alert=True); return

    if chosen == state["correct"]:
        _trivia.pop(event.message_id, None)
        await _bump(event.sender_id, "trivia_won")
        try:
            user = await event.client.get_entity(event.sender_id)
            name = user.first_name or str(event.sender_id)
        except Exception:
            name = str(event.sender_id)
        await event.edit(f"🎉 **{name}** answered correctly!")
        await event.answer("✅ Correct!", alert=False)
    else:
        await _bump(event.sender_id, "trivia_lost")
        await event.answer("❌ Wrong — try again", alert=True)


@command(r"gstats(?:\s+(.+))?", "Show game statistics")
async def gstats_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    try:
        if arg:
            entity = await event.client.get_entity(
                int(arg) if arg.lstrip("-").isdigit() else arg
            )
        elif event.is_reply:
            entity = await (await event.get_reply_message()).get_sender()
        else:
            entity = await event.client.get_me()
    except Exception:
        await event.edit(Messages.error("Could not resolve that user."))
        return

    async with get_session() as session:
        result = await session.execute(
            select(GameStat).where(GameStat.user_id == entity.id)
        )
        row = result.scalar_one_or_none()

    name = getattr(entity, "first_name", None) or str(entity.id)
    if row is None:
        await event.edit(Messages.info(f"No game stats for **{name}**."))
        return

    await event.edit(
        f"🎮 **{name}**\n\n"
        f"🎲 Dice: **{row.dice_played}**\n"
        f"🎰 Slots: **{row.slots_played}**\n"
        f"💰 Jackpots: **{row.jackpots}**\n\n"
        f"⚔️ Duels W/L: **{row.duels_won}/{row.duels_lost}**\n"
        f"🧠 Trivia W/L: **{row.trivia_won}/{row.trivia_lost}**"
    )


@command("greset", "Reset your game statistics")
async def greset_handler(event):
    me = await event.client.get_me()
    async with get_session() as session:
        result = await session.execute(
            select(GameStat).where(GameStat.user_id == me.id)
        )
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
    await event.edit(Messages.success("Game statistics reset."))


@command("gamehelp", "Games help")
async def gamehelp_handler(event):
    await event.edit(
        "🎮 **GAMES**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "`.dice` `.dart` `.bowl` `.basket` `.football` `.slot`\n"
        "`.8ball <question>` `.coinflip` `.rps <rock|paper|scissors>`\n"
        "`.duel` (reply) · `.trivia`\n"
        "`.gstats` · `.greset`"
    )
