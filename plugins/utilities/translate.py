import httpx
from helpers.decorators import command
from utils.messages import Messages
L={'en':'English','hi':'Hindi','es':'Spanish','fr':'French','de':'German','it':'Italian','pt':'Portuguese','ru':'Russian','ja':'Japanese','ko':'Korean','zh':'Chinese','ar':'Arabic','tr':'Turkish','bn':'Bengali','ta':'Tamil','te':'Telugu','mr':'Marathi','gu':'Gujarati','ur':'Urdu'}
async def go(t,to):
 try:
  async with httpx.AsyncClient(timeout=15) as c:r=await c.get('https://translate.googleapis.com/translate_a/single',params={'client':'gtx','sl':'auto','tl':to,'dt':'t','q':t});r.raise_for_status();d=r.json();return ''.join(x[0] for x in d[0] if x and x[0]),d[2] if len(d)>2 else 'auto'
 except:return None
@command(r'tr (\w\w) (.+)','Translate text')
async def tr_handler(e):
 to=e.pattern_match.group(1).lower();t=e.pattern_match.group(2)
 if to not in L:return await e.edit(Messages.error(f'Unknown code `{to}`.'))
 x=await go(t,to);await e.edit(Messages.error('Translation failed.') if not x else f'🌐 **{L.get(x[1],x[1])} → {L[to]}**\n\n{x[0]}')
@command(r'trto (\w\w) (.+)','Alias for translate')
async def trto_handler(e):await tr_handler(e)
@command('langs','List languages')
async def langs_handler(e):await e.edit('\n'.join(f'• `{k}` — {v}' for k,v in sorted(L.items())))
@command('trhelp','Translate help')
async def trhelp_handler(e):await e.edit('🌐 **TRANSLATE**\n`.tr <lang> <text>` `.trto <lang> <text>` `.langs`')
