"""Commands list - Quick reference"""
from helpers.decorators import command
from Config.settings import Config


@command("commands(?: (.*))?", "Quick command reference")
async def commands_handler(event):
    """
    Quick reference of all available commands

    Usage:
        .commands - All commands (compact)
        .commands <category> - Category commands

    Examples:
        .commands
        .commands admin
        .commands utilities
    """
    category_filter = event.pattern_match.group(1)
    registry = event.client.plugin_registry

    if category_filter:
        category_filter = category_filter.strip().lower()
        categorized = registry.get_commands_by_category(category_filter)
    else:
        categorized = registry.get_commands_by_category()

    if not categorized:
        await event.edit("❌ No commands found")
        return

    text = "⚡ **ZEROX COMMAND REFERENCE**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"**Prefix:** `{Config.CMD_PREFIX}`\n\n"

    total = 0
    for category in sorted(categorized.keys()):
        commands = categorized[category]
        emoji = get_category_emoji(category)

        text += f"{emoji} **{category.upper()}** ({len(commands)})\n"

        cmd_names = [f"`{cmd['name']}`" for cmd in commands]
        for i in range(0, len(cmd_names), 3):
            text += "   " + " • ".join(cmd_names[i:i + 3]) + "\n"

        text += "\n"
        total += len(commands)

    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"**Total:** {total} commands\n"
    text += f"💡 Use `{Config.CMD_PREFIX}help zerox` for detailed help"

    await event.edit(text)


def get_category_emoji(category: str) -> str:
    """Get emoji for category"""
    emojis = {
        'admin': '👑',
        'utilities': '🛠',
        'fun': '🎮',
        'automation': '🤖',
        'custom': '⚙️',
        'moderation': '🛡',
        'tools': '🔧',
        'media': '🎬',
        'info': 'ℹ️'
    }
    return emojis.get(category.lower(), '📦')
