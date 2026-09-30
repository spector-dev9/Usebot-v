"""Facts — random jokes, quotes, facts, advice, cat/dog facts."""
import httpx
from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger=setup_logger(__name__)

async def _get_json(url):
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=True) as c:
            r=await c.get(url); r.raise_for_status(); return r.json()
    except Exception as e:
        logger.warning(f"facts fetch {url}: {e}"); return None

@command("joke", "Random joke")
async def joke_handler(event):
    await event.edit(Messages.loading("Loading joke…")); d=await _get_json("https://official-joke-api.appspot.com/random_joke")
    if not d: await event.edit(Messages.error("Joke API unavailable.")); return
    await event.edit(f"😂 **{d.get('setup','')}**\n\n{d.get('punchline','')}")

@command("quote", "Random quote")
async def quote_handler(event):
    await event.edit(Messages.loading("Loading quote…")); d=await _get_json("https://api.quotable.io/random")
    if not d:
        d=await _get_json("https://zenquotes.io/api/random")
        if d and isinstance(d,list) and d:
            await event.edit(f"💭 _{d[0].get('q','')}_\n\n— **{d[0].get('a','')}**"); return
        await event.edit(Messages.error("Quote API unavailable.")); return
    await event.edit(f"💭 _{d.get('content','')}_\n\n— **{d.get('author','')}**")

@command("fact", "Random useless fact")
async def fact_handler(event):
    await event.edit(Messages.loading("Loading fact…")); d=await _get_json("https://uselessfacts.jsph.pl/random.json?language=en")
    if not d: await event.edit(Messages.error("Fact API unavailable.")); return
    await event.edit(f"🧠 **Did you know?**\n\n{d.get('text','')}")

@command("advice", "Random advice")
async def advice_handler(event):
    await event.edit(Messages.loading("Loading advice…")); d=await _get_json("https://api.adviceslip.com/advice")
    if not d or "slip" not in d: await event.edit(Messages.error("Advice API unavailable.")); return
    await event.edit(f"💡 _{d['slip'].get('advice','')}_")

@command("catfact", "Random cat fact")
async def catfact_handler(event):
    await event.edit(Messages.loading("Loading cat fact…")); d=await _get_json("https://catfact.ninja/fact")
    if not d: await event.edit(Messages.error("Cat fact API unavailable.")); return
    await event.edit(f"🐱 **Cat fact**\n\n{d.get('fact','')}")

@command("dogfact", "Random dog fact")
async def dogfact_handler(event):
    await event.edit(Messages.loading("Loading dog fact…")); d=await _get_json("https://dogapi.dog/api/v2/facts")
    if not d: await event.edit(Messages.error("Dog fact API unavailable.")); return
    try: text=d["data"][0]["attributes"]["body"]
    except Exception: await event.edit(Messages.error("Parse failed.")); return
    await event.edit(f"🐶 **Dog fact**\n\n{text}")

@command("chucknorris", "Random Chuck Norris joke")
async def chucknorris_handler(event):
    await event.edit(Messages.loading("Loading…")); d=await _get_json("https://api.chucknorris.io/jokes/random")
    if not d: await event.edit(Messages.error("API unavailable.")); return
    await event.edit(f"💪 {d.get('value','')}")

@command("factshelp", "Facts help")
async def factshelp_handler(event):
    await event.edit("🎲 **FACTS**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "• `.joke` — random joke\n• `.quote` — random quote\n• `.fact` — useless fact\n"
                     "• `.advice` — random advice\n• `.catfact` · `.dogfact`\n• `.chucknorris` — CN joke")
