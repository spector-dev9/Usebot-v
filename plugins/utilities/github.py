"""GitHub — user, repo, and search via public API (no auth)."""
import httpx
from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger=setup_logger(__name__)
API="https://api.github.com"
HEADERS={"Accept":"application/vnd.github+json","User-Agent":"ZeroX-Userbot"}

async def _gh(path):
    try:
        async with httpx.AsyncClient(timeout=15,headers=HEADERS) as c:
            r=await c.get(f"{API}{path}")
            if r.status_code==404: return None
            r.raise_for_status(); return r.json()
    except Exception as e:
        logger.warning(f"gh {path}: {e}"); return None

@command(r"ghuser (\S+)", "GitHub user info")
async def ghuser_handler(event):
    user=event.pattern_match.group(1).strip(); await event.edit(Messages.loading(f"Looking up `{user}`…"))
    d=await _gh(f"/users/{user}")
    if d is None: await event.edit(Messages.error(f"User `{user}` not found.")); return
    await event.edit(
        f"🐙 **{d.get('name') or d.get('login')}** (@{d.get('login')})\n"
        f"• Bio: {d.get('bio') or '—'}\n• Company: {d.get('company') or '—'}\n"
        f"• Location: {d.get('location') or '—'}\n• Repos: **{d.get('public_repos',0)}** · Gists: **{d.get('public_gists',0)}**\n"
        f"• Followers: **{d.get('followers',0)}** · Following: **{d.get('following',0)}**\n"
        f"• Created: `{d.get('created_at','?')[:10]}`\n🔗 {d.get('html_url','')}"
    )

@command(r"ghrepo (\S+)/(\S+)", "GitHub repo info")
async def ghrepo_handler(event):
    owner=event.pattern_match.group(1).strip(); repo=event.pattern_match.group(2).strip()
    await event.edit(Messages.loading(f"Looking up `{owner}/{repo}`…")); d=await _gh(f"/repos/{owner}/{repo}")
    if d is None: await event.edit(Messages.error(f"Repo `{owner}/{repo}` not found.")); return
    desc=(d.get("description") or "—"); desc=desc[:300]+"…" if len(desc)>300 else desc
    await event.edit(
        f"🐙 **{d.get('full_name')}**\n_{desc}_\n\n• Stars: **{d.get('stargazers_count',0):,}** ⭐\n"
        f"• Forks: **{d.get('forks_count',0):,}\n• Watchers: **{d.get('watchers_count',0):,}**\n"
        f"• Open issues: **{d.get('open_issues_count',0)}**\n• Language: **{d.get('language') or '—'}**\n"
        f"• License: {(d.get('license') or {}).get('spdx_id') or '—'}\n"
        f"• Created: `{d.get('created_at','?')[:10]}`\n• Updated: `{d.get('updated_at','?')[:10]}`\n🔗 {d.get('html_url','')}"
    )

@command(r"ghsearch (.+)", "Search GitHub repos")
async def ghsearch_handler(event):
    q=event.pattern_match.group(1).strip(); await event.edit(Messages.loading(f"Searching `{q}`…"))
    try:
        async with httpx.AsyncClient(timeout=15,headers=HEADERS) as c:
            r=await c.get(f"{API}/search/repositories",params={"q":q,"per_page":10,"sort":"stars","order":"desc"})
            r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Search failed: `{e}`")); return
    items=data.get("items",[])
    if not items: await event.edit(Messages.info(f"No results for `{q}`.")); return
    lines=[f"🔍 **GitHub search** — {data.get('total_count',0):,} results\n"]
    for i,r in enumerate(items,1):
        lines.append(f"{i}. **{r.get('full_name')}** ⭐{r.get('stargazers_count',0):,}\n   _{(r.get('description') or '')[:80]}_")
    await event.edit("\n".join(lines),link_preview=False)

@command(r"ghfile (\S+)/(\S+)/(.+)", "Fetch a file from GitHub")
async def ghfile_handler(event):
    owner,repo,rest=event.pattern_match.group(1),event.pattern_match.group(2),event.pattern_match.group(3)
    if "/" not in rest: await event.edit(Messages.error("Format: `owner/repo/branch/path`")); return
    branch,path=rest.split("/",1); url=f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    await event.edit(Messages.loading("Fetching…"))
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=True) as c:
            r=await c.get(url)
            if r.status_code==404: await event.edit(Messages.error("File not found.")); return
            r.raise_for_status(); text=r.text
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    if len(text)>3000: text=text[:3000]+"\n…(truncated)"
    await event.edit(f"📄 `{owner}/{repo}/{branch}/{path}`\n```\n{text}\n```")

@command("ghhelp", "GitHub help")
async def ghhelp_handler(event):
    await event.edit("🐙 **GITHUB**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "• `.ghuser <username>` — user info\n• `.ghrepo <owner>/<repo>` — repo info\n"
                     "• `.ghsearch <query>` — search repos\n• `.ghfile <owner>/<repo>/<branch>/<path>`\n\nPublic API · 60 req/hour per IP")
