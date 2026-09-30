"""Dictionary — free word definitions via dictionaryapi.dev."""
import httpx
from helpers.decorators import command
from utils.messages import Messages, SEP_FANCY
from core.logger import setup_logger
logger=setup_logger(__name__); API="https://api.dictionaryapi.dev/api/v2/entries/en/"
@command(r"define (.+)","Define a word")
async def define_handler(event):
    word=event.pattern_match.group(1).strip().lower(); await event.edit(Messages.loading(f"Looking up `{word}`…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(API+word)
            if r.status_code==404: await event.edit(Messages.error(f"No entry for `{word}`.")); return
            r.raise_for_status(); data=r.json()
    except Exception as e: logger.warning(f"define: {e}"); await event.edit(Messages.error("Lookup failed")); return
    if not data: await event.edit(Messages.error(f"No entry for `{word}`.")); return
    entry=data[0]; title=entry.get("word",word); phonetic=entry.get("phonetic","") or ""; parts=[f"📖 **{title.title()}**"]
    if phonetic: parts.append(f"_{phonetic}_")
    parts.append(SEP_FANCY); shown=0
    for meaning in entry.get("meanings",[]):
        pos=meaning.get("partOfSpeech",""); defs=meaning.get("definitions",[])
        if not defs: continue
        definition=defs[0].get("definition",""); example=defs[0].get("example",""); parts.append(f"\n**{pos}.**"); parts.append(f"  {definition}")
        if example: parts.append(f"  _{example}_")
        shown+=1
        if shown>=3: break
    syns=[]
    for m in entry.get("meanings",[])[:3]: syns.extend(m.get("synonyms",[]))
    if syns: parts.extend([f"\n{SEP_FANCY}",f"**Synonyms**  {', '.join(syns[:8])}"])
    await event.edit("\n".join(parts))
@command(r"synonym (.+)","Find synonyms")
async def synonym_handler(event):
    word=event.pattern_match.group(1).strip().lower(); await event.edit(Messages.loading("Searching…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(API+word)
            if r.status_code==404: await event.edit(Messages.error(f"No entry for `{word}`.")); return
            r.raise_for_status(); data=r.json()
    except Exception: await event.edit(Messages.error("Lookup failed")); return
    syns=set()
    for entry in data:
        for m in entry.get("meanings",[]): syns.update(m.get("synonyms",[]))
    if not syns: await event.edit(Messages.info(f"No synonyms for `{word}`.")); return
    await event.edit(f"🔎 **Synonyms of `{word}`**\n{SEP_FANCY}\n"+"\n".join(f"▸ {s}" for s in sorted(syns)[:30]))
@command("dicthelp","Dictionary help")
async def dicthelp_handler(event):
    await event.edit("📖 **DICTIONARY**\n"+SEP_FANCY+"\n\n▸ `.define <word>` — full definition\n▸ `.synonym <word>` — synonyms\n\n_Powered by dictionaryapi.dev_")
