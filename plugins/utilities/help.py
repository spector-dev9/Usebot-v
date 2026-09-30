"""Help — professional help menu."""
from helpers.decorators import command
from utils.messages import Messages, SEP_FANCY
from Config.settings import Config
def _emoji(cat): return {"admin":"👑","utilities":"🛠","fun":"🎮","automation":"🤖","custom":"⚙️","moderation":"🛡","tools":"🔧","media":"🎬","info":"ℹ️","download":"📥","text":"📝","search":"🔍"}.get(cat.lower(),"📦")
LOGO=("╔══════════════════════════════╗\n║      ⚡  Z E R O X  ⚡       ║\n║   modular telegram userbot   ║\n╚══════════════════════════════╝")
@command("help(?: (.*))?","Show help")
async def help_handler(event):
    q=event.pattern_match.group(1); reg=event.client.plugin_registry
    if not q:return await _menu(event,reg)
    q=q.strip().lower()
    if q in ("all","everything"):return await _all(event,reg)
    ci=reg.get_command_info(q)
    if ci:return await _cmd(event,ci)
    cats=[c.lower() for c in reg.get_all_categories()]
    if q in cats:return await _cat(event,reg,q)
    res=reg.search_commands(q)
    if res:return await _search(event,res,q)
    await event.edit(Messages.error(f"Not found: `{q}`"))
async def _menu(event,reg):
    cats=reg.get_commands_by_category(); st=reg.get_stats(); t=f"{LOGO}\n\n{SEP_FANCY}\n**Commands**  `{st['total_commands']}`\n**Modules**   `{st['total_modules']}`\n**Handlers**  `{st['total_handlers']}`\n**Prefix**    `{Config.CMD_PREFIX}`\n**Version**   `{Config.VERSION}`\n{SEP_FANCY}\n\n**Access**\n▸ `.help all` — full reference\n▸ `.help <category>` — one category\n▸ `.help <command>` — one command\n{SEP_FANCY}\n\n**Categories**\n"
    for c in sorted(cats):
        cmds=cats[c]; sudo=sum(1 for x in cmds if x["sudo_only"]); badge=f"  🔒{sudo}" if sudo else ""; t+=f"\n{_emoji(c)} **{c.upper()}**  ·  {len(cmds)}{badge}\n"+"".join(("🔒 " if x["sudo_only"] else "   ")+f"`{x['name']}`\n" for x in cmds[:4]); t+=f"    _…+{len(cmds)-4} more_\n" if len(cmds)>4 else ""
    await event.edit(t)
async def _all(event,reg):
    cats=reg.get_commands_by_category(); t=f"{LOGO}\n\n📚 **FULL REFERENCE**\n{SEP_FANCY}\n"
    for c in sorted(cats):
        t+=f"\n{_emoji(c)} **{c.upper()}**\n"
        for x in cats[c]:t+=("🔒 " if x["sudo_only"] else "")+f"`{Config.CMD_PREFIX}{x['name']}`"+(f" — _{x['description']}_" if x["description"] else "")+"\n"
    await event.edit(t[:3900]+"\n\n_…truncated_" if len(t)>4000 else t)
async def _cat(event,reg,cat):
    cats=reg.get_commands_by_category(cat)
    if not cats or cat not in cats:return await event.edit(Messages.error("No such category."))
    t=f"{_emoji(cat)} **{cat.upper()}**  ·  {len(cats[cat])}\n{SEP_FANCY}\n\n"
    for x in cats[cat]:t+=("🔒 " if x["sudo_only"] else "▸ ")+f"`{Config.CMD_PREFIX}{x['name']}`"+(f"  _{x['description']}_" if x["description"] else "")+"\n"
    await event.edit(t)
async def _cmd(event,ci):
    t=f"📖 **COMMAND**\n{SEP_FANCY}\n\n{('🔒 ' if ci['sudo_only'] else '')}**`{Config.CMD_PREFIX}{ci['name']}`**\n**Category**  {_emoji(ci['category'])} {ci['category']}\n\n"+(f"_{ci['description']}_\n\n" if ci['description'] else "")
    if ci.get("docstring"):t+=f"```\n{ci['docstring'][:800]}\n```"
    await event.edit(t)
async def _search(event,results,q):
    t=f"🔍 **{len(results)} result(s)** for `{q}`\n{SEP_FANCY}\n\n"; by_cat={}
    for x in results:by_cat.setdefault(x["category"],[]).append(x)
    for c in sorted(by_cat):
        t+=f"{_emoji(c)} **{c.upper()}**\n"+"".join(("🔒 " if x["sudo_only"] else "▸ ")+f"`{x['name']}` — _{x['description']}_\n" for x in by_cat[c][:5])+"\n"
    await event.edit(t)
