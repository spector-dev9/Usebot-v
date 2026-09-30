from helpers import animations


@command(r"ui(?:\s+(on|off))?", "Toggle typing animations")
@sudo_only
async def ui_handler(event):
    """Usage: `.ui on` / `.ui off`"""
    arg = (event.pattern_match.group(1) or "").lower()

    if not arg:
        state = "🟢 ON" if animations.enabled() else "🔴 OFF"
        await event.edit(Messages.info(f"Typing animations: **{state}**"))
        return

    if arg == "on":
        animations.set_enabled(True)
        await event.edit(Messages.success("Typing animations **enabled**."))
    elif arg == "off":
        animations.set_enabled(False)
        await event.edit(Messages.success("Typing animations **disabled**."))
    else:
        await event.edit(Messages.error("Usage: `.ui on|off`"))
