from helpers.decorators import command
from utils.messages import Messages
E={'smile':'😄','grin':'😁','joy':'😂','laugh':'🤣','wink':'😉','heart':'❤️','fire':'🔥','skull':'💀','ghost':'👻','robot':'🤖','heart_eyes':'😍','think':'🤔','cry':'😢','sob':'😭','angry':'😠','cool':'😎','thumbs_up':'👍','thumbs_down':'👎','ok':'👌','peace':'✌️','clap':'👏','pray':'🙏','muscle':'💪','check':'✅','cross':'❌','warning':'⚠️','lock':'🔒','key':'🔑','gear':'⚙️','crown':'👑','gift':'🎁','trophy':'🏆','money':'💰','gem':'💎','pizza':'🍕','burger':'🍔','coffee':'☕','cake':'🎂','cat':'🐱','dog':'🐶','fox':'🦊','bear':'🐻','panda':'🐼','tiger':'🐯','lion':'🦁','frog':'🐸','monkey':'🐵','penguin':'🐧','bird':'🐦','dragon':'🐉','whale':'🐳','arrow_up':'⬆️','arrow_down':'⬇️','question':'❓','exclamation':'❗','hundred':'💯'}
@command(r'emoji(?: (.+))?','Search emojis')
async def emoji_handler(e):
 q=(e.pattern_match.group(1) or '').strip().lower();h=[(k,v) for k,v in E.items() if q in k]
 if not q:return await e.edit('😀 '+' '.join(E.values()))
 if q in E:return await e.edit(f'**{q}** → {E[q]}')
 await e.edit(Messages.error(f'No emoji for `{q}`.') if not h else '\n'.join(f'• `{k}` {v}' for k,v in h))
@command('emojilist','List emojis')
async def emojilist_handler(e):await e.edit(f'**{len(E)} emojis**\n'+', '.join(f'`{k}`' for k in sorted(E)))
@command('emojihelp','Emoji help')
async def emojihelp_handler(e):await e.edit('😀 **EMOJI**\n`.emoji <keyword>` `.emoji` `.emojilist`')
