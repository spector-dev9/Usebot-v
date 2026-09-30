"""Ping — latency check with animated stages."""
import asyncio, time
from helpers.decorators import command
from utils.messages import Messages, SEP_FANCY
from core.logger import setup_logger
logger=setup_logger(__name__)
_RATINGS=[(80,"🟢","Excellent"),(150,"🟢","Great"),(300,"🟡","Good"),(600,"🟠","Fair"),(1200,"🔴","Slow")]
def _rate(latency_ms):
    for limit,dot,label in _RATINGS:
        if latency_ms<=limit:return dot,label
    return "🔴","Very slow"
def _bar(latency_ms,width=16):
    filled=max(1,int(min(latency_ms/1500,1.0)*width)); return "▰"*filled+"▱"*(width-filled)
async def _measure_edit_roundtrip(event):
    start=time.perf_counter(); await event.edit("⚡"); return (time.perf_counter()-start)*1000
@command("ping","Check bot latency")
async def ping_handler(event):
    frames=["🏓","🏓 ˙","🏓 ˙ ˙","🏓 ˙ ˙ ˙"]
    for f in frames:
        try: await event.edit(f)
        except Exception: break
        await asyncio.sleep(.12)
    samples=[]
    for _ in range(3):
        try:samples.append(await _measure_edit_roundtrip(event))
        except Exception:pass
        await asyncio.sleep(.08)
    if not samples: await event.edit(Messages.error("Couldn't measure latency.")); return
    samples.sort(); median=samples[len(samples)//2]; best=samples[0]; worst=samples[-1]; dot,rating=_rate(median)
    await event.edit(f"{dot}  **PONG**\n{SEP_FANCY}\n`{_bar(median)}`\n\n**Latency**   `{median:>6.1f} ms`  ·  {rating}\n**Best**      `{best:>6.1f} ms`\n**Worst**     `{worst:>6.1f} ms`\n**Samples**   `{len(samples)}`\n{SEP_FANCY}\n_Telegram edit roundtrip · not network ping_")
@command("p","Quick ping")
async def p_handler(event):
    t0=time.perf_counter(); await event.edit("⚡"); latency=(time.perf_counter()-t0)*1000; dot,rating=_rate(latency); await event.edit(f"{dot} `{latency:.0f} ms` · {rating}")
