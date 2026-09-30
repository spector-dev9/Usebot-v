import httpx
from helpers.decorators import command
from utils.messages import Messages
T=15
@command(r'paste (.+)','Paste text')
async def paste_handler(e):
 try:
  async with httpx.AsyncClient(timeout=T) as c:r=await c.post('https://dpaste.com/api/v2/',data={'content':e.pattern_match.group(1),'expiry_days':7});r.raise_for_status()
  await e.edit(f'📋 {r.text.strip()}')
 except Exception as x:await e.edit(Messages.error(f'Upload failed: `{x}`'))
@command(r'shorten (\S+)','Shorten URL')
async def shorten_handler(e):
 u=e.pattern_match.group(1);u=u if u.startswith('http') else 'https://'+u
 try:
  async with httpx.AsyncClient(timeout=T) as c:r=await c.get('https://tinyurl.com/api-create.php',params={'url':u});r.raise_for_status()
  await e.edit('🔗 '+r.text.strip())
 except Exception as x:await e.edit(Messages.error(f'Shorten failed: `{x}`'))
@command(r'ipinfo(?: (.+))?','IP info')
async def ipinfo_handler(e):
 try:
  u=e.pattern_match.group(1) or ''
  async with httpx.AsyncClient(timeout=T) as c:d=(await c.get(f'https://ipinfo.io/{u}/json' if u else 'https://ipinfo.io/json')).json()
 except Exception as x:return await e.edit(Messages.error(f'Lookup failed: `{x}`'))
 await e.edit(f"🌐 **{d.get('ip','?')}**\n"+'\n'.join(f'• **{k}:** {d[k]}' for k in ('city','region','country','org','timezone','loc') if d.get(k)))
@command(r'dns (\S+)','DNS lookup')
async def dns_handler(e):
 d=e.pattern_match.group(1);o=[]
 try:
  async with httpx.AsyncClient(timeout=T) as c:
   for t in('A','AAAA','MX','TXT'):o += [f"**{t}** `{a['data']}`" for a in (await c.get('https://dns.google/resolve',params={'name':d,'type':t})).json().get('Answer',[])[:4]]
 except Exception as x:return await e.edit(Messages.error(f'DNS failed: `{x}`'))
 await e.edit('\n'.join(o) if o else Messages.error('No records found.'))
@command(r'httpget (\S+)','Fetch URL')
async def httpget_handler(e):
 u=e.pattern_match.group(1);u=u if u.startswith('http') else 'https://'+u
 try:
  async with httpx.AsyncClient(timeout=T,follow_redirects=True) as c:r=await c.get(u);r.raise_for_status()
  await e.edit(f'```\n{r.text[:2900]}\n```')
 except Exception as x:await e.edit(Messages.error(f'Request failed: `{x}`'))
@command(r'weather (.+)','Weather')
async def weather_handler(e):
 try:
  async with httpx.AsyncClient(timeout=T) as c:d=(await c.get(f"https://wttr.in/{e.pattern_match.group(1)}",params={'format':'j1'},headers={'User-Agent':'curl/8'})).json()
  x=d['current_condition'][0];await e.edit(f"🌤 **{e.pattern_match.group(1)}**\n{x['weatherDesc'][0]['value']}\nTemp: {x['temp_C']}°C\nHumidity: {x['humidity']}%\nWind: {x['windspeedKmph']} km/h")
 except Exception as x:await e.edit(Messages.error(f'Weather failed: `{x}`'))
@command('webhelp','Webtools help')
async def webhelp_handler(e):await e.edit('🌐 `.paste` `.shorten` `.ipinfo` `.dns` `.httpget` `.weather`')
