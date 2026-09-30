"""Currency — FX rates via frankfurter.app (free, keyless)."""
import httpx
from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger=setup_logger(__name__)
BASE="https://api.frankfurter.app"
_SYMS={"$":"USD","€":"EUR","£":"GBP","¥":"JPY","₹":"INR","₩":"KRW","₽":"RUB","₺":"TRY","R$":"BRL"}

def _norm(code):
    return _SYMS.get(code.strip(), code.strip().upper())

@command(r"fx (\w{3}) (\w{3})", "Current FX rate")
async def fx_handler(event):
    src,dst=_norm(event.pattern_match.group(1)),_norm(event.pattern_match.group(2))
    await event.edit(Messages.loading(f"{src} → {dst}…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{BASE}/latest",params={"from":src,"to":dst})
            if r.status_code==404:
                await event.edit(Messages.error(f"Pair `{src}/{dst}` not supported.")); return
            r.raise_for_status(); data=r.json()
    except Exception as e:
        logger.warning(f"fx: {e}"); await event.edit(Messages.error(f"Failed: `{e}`")); return
    rate=data.get("rates",{}).get(dst)
    if rate is None: await event.edit(Messages.error("No rate returned.")); return
    await event.edit(f"💱 **1 {src} = {rate:,.4f} {dst}**\n_as of {data.get('date','today')}_")

@command(r"convert (\d+(?:\.\d+)?) (\w{3}) (\w{3})", "Convert an amount")
async def convert_handler(event):
    amount=float(event.pattern_match.group(1)); src=_norm(event.pattern_match.group(2)); dst=_norm(event.pattern_match.group(3))
    await event.edit(Messages.loading("Converting…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{BASE}/latest",params={"amount":amount,"from":src,"to":dst})
            if r.status_code==404:
                await event.edit(Messages.error(f"Pair `{src}/{dst}` not supported.")); return
            r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    result=data.get("rates",{}).get(dst)
    if result is None: await event.edit(Messages.error("No rate.")); return
    await event.edit(f"💱 **{amount:,.2f} {src}** = **{result:,.2f} {dst}**\n_as of {data.get('date','today')}_")

@command(r"rates (\w{3})", "Show rates from a base currency")
async def rates_handler(event):
    base=_norm(event.pattern_match.group(1)); targets="INR,EUR,GBP,JPY,USD,AUD,CAD,CHF,CNY"
    await event.edit(Messages.loading(f"Rates for {base}…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{BASE}/latest",params={"from":base,"to":targets}); r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    lines=[f"💱 **1 {base}**\n"]
    for code,val in sorted(data.get("rates",{}).items()):
        if code!=base: lines.append(f"• {code}: `{val:,.4f}`")
    lines.append(f"\n_as of {data.get('date','today')}_"); await event.edit("\n".join(lines))

@command("currencyhelp", "Currency help")
async def currencyhelp_handler(event):
    await event.edit("💱 **CURRENCY**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "• `.fx <src> <dst>` — current rate\n• `.convert <amt> <src> <dst>` — amount\n"
                     "• `.rates <base>` — common pairs\n\n**Note:** No crypto here — use `.price`.\nECB rates via frankfurter.app (free).")
