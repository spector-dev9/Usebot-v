"""Crypto — prices via CoinGecko (free, keyless)."""
import httpx
from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger = setup_logger(__name__)
API = "https://api.coingecko.com/api/v3"
_IDS = {"btc":"bitcoin","eth":"ethereum","usdt":"tether","bnb":"binancecoin","sol":"solana",
"xrp":"ripple","ada":"cardano","doge":"dogecoin","dot":"polkadot","matic":"matic-network",
"polygon":"matic-network","avax":"avalanche-2","link":"chainlink","ltc":"litecoin","trx":"tron",
"shib":"shiba-inu","uni":"uniswap","atom":"cosmos","xlm":"stellar","etc":"ethereum-classic",
"fil":"filecoin","near":"near","apt":"aptos","arb":"arbitrum","op":"optimism","ton":"the-open-network",
"pepe":"pepe","wbtc":"wrapped-bitcoin","dai":"dai","usdc":"usd-coin"}

def _resolve(name: str) -> str:
    return _IDS.get(name.strip().lower(), name.strip().lower())

@command(r"price (\w+)", "Crypto price")
async def price_handler(event):
    raw = event.pattern_match.group(1)
    cg_id = _resolve(raw)
    await event.edit(Messages.loading(f"Getting {raw}…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{API}/simple/price", params={"ids":cg_id,"vs_currencies":"usd,inr,eur,gbp",
                "include_24hr_change":"true","include_market_cap":"true"})
            if r.status_code == 404:
                await event.edit(Messages.error(f"Unknown coin `{raw}`."))
                return
            r.raise_for_status(); data = r.json()
    except Exception as e:
        logger.warning(f"price: {e}"); await event.edit(Messages.error(f"Lookup failed: `{e}`")); return
    if cg_id not in data:
        await event.edit(Messages.error(f"No data for `{raw}`.")); return
    d=data[cg_id]; change=d.get("usd_24h_change",0) or 0; cap=d.get("usd_market_cap",0) or 0
    def fmt(v):
        if v >= 1e9: return f"${v/1e9:.2f}B"
        if v >= 1e6: return f"${v/1e6:.2f}M"
        return f"${v:,.2f}"
    arrow="🟢" if change >= 0 else "🔴"
    await event.edit(f"💎 **{raw.upper()}**\n• USD: `{fmt(d.get('usd',0))}`\n• INR: `₹{d.get('inr',0):,.2f}`\n"
                     f"• EUR: `€{d.get('eur',0):,.2f}`\n• GBP: `£{d.get('gbp',0):,.2f}`\n"
                     f"• 24h: {arrow} `{change:+.2f}%`\n• Market cap: `{fmt(cap)}`")

@command("top10", "Top 10 coins by market cap")
async def top10_handler(event):
    await event.edit(Messages.loading("Fetching…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{API}/coins/markets",params={"vs_currency":"usd","order":"market_cap_desc","per_page":10,"page":1,"price_change_percentage":"24h"})
            r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    lines=["🏆 **Top 10 by market cap**\n"]
    for i,c in enumerate(data,1):
        change=c.get("price_change_percentage_24h",0) or 0; price=c.get("current_price",0)
        ps=f"${price:,.2f}" if price>=1 else f"${price:.6f}"
        lines.append(f"{i}. **{c['symbol'].upper()}** — {ps} {'🟢' if change>=0 else '🔴'} {change:+.2f}%")
    await event.edit("\n".join(lines))

@command(r"trending", "Trending coins on CoinGecko")
async def trending_handler(event):
    await event.edit(Messages.loading("Fetching…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{API}/search/trending"); r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    lines=["🔥 **Trending**\n"]
    for item in data.get("coins",[])[:10]:
        c=item.get("item",{}); lines.append(f"• **{c.get('symbol','?').upper()}** — {c.get('name','?')} (rank {c.get('market_cap_rank','?')})")
    await event.edit("\n".join(lines))

@command(r"convertcrypto (\S+) (\d+(?:\.\d+)?)", "Convert crypto amount to USD")
async def convertcrypto_handler(event):
    raw=event.pattern_match.group(1); amount=float(event.pattern_match.group(2)); cg_id=_resolve(raw)
    await event.edit(Messages.loading("Converting…"))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(f"{API}/simple/price",params={"ids":cg_id,"vs_currencies":"usd"}); r.raise_for_status(); data=r.json()
    except Exception as e:
        await event.edit(Messages.error(f"Failed: `{e}`")); return
    if cg_id not in data:
        await event.edit(Messages.error(f"Unknown coin `{raw}`.")); return
    price=data[cg_id]["usd"]; total=price*amount
    await event.edit(f"💱 **{amount} {raw.upper()}** = `${total:,.2f}`\n_@ ${price:,.2f} per {raw.upper()}_")

@command("cryptohelp", "Crypto help")
async def cryptohelp_handler(event):
    await event.edit("💎 **CRYPTO**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "• `.price <coin>` — current price\n• `.top10` — top 10 by cap\n"
                     "• `.trending` — trending now\n• `.convertcrypto <coin> <amt>` — USD value\n\n"
                     "**Aliases:** btc, eth, sol, doge, ada, xrp, …\nOr full CoinGecko id: `bitcoin`, `ethereum`")
