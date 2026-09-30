import base64,binascii,hashlib,secrets,string,urllib.parse,uuid
from datetime import datetime,timezone
from helpers.decorators import command
from utils.messages import Messages
@command(r'password(?:\s+(\d+))?','Generate password')
async def password_handler(e):
 n=int(e.pattern_match.group(1) or 20)
 if not 4<=n<=128:return await e.edit(Messages.error('Length must be 4–128.'))
 await e.edit('🔐 `'+''.join(secrets.choice(string.ascii_letters+string.digits+'!@#$%^&*()-_=+[]{}') for _ in range(n))+'`')
@command('uuid','Generate UUID4')
async def uuid_handler(e):await e.edit(f'🆔 `{uuid.uuid4()}`')
@command(r'token(?:\s+(\d+))?','Generate token')
async def token_handler(e):await e.edit(f'🎫 `{secrets.token_hex((int(e.pattern_match.group(1) or 32))//2)}`')
@command(r'hash (md5|sha1|sha256|sha512) (.+)','Hash text')
async def hash_handler(e):a=e.pattern_match;await e.edit(f'**{a.group(1)}**\n`{hashlib.new(a.group(1),a.group(2).encode()).hexdigest()}`')
@command(r'b64enc (.+)','Base64 encode')
async def b64enc_handler(e):await e.edit('`'+base64.b64encode(e.pattern_match.group(1).encode()).decode()+'`')
@command(r'b64dec (.+)','Base64 decode')
async def b64dec_handler(e):
 try:o=base64.b64decode(e.pattern_match.group(1)).decode(errors='replace')
 except Exception as x:return await e.edit(Messages.error(f'Invalid base64: {x}'))
 await e.edit(f'`{o}`')
@command(r'urlenc (.+)','URL encode')
async def urlenc_handler(e):await e.edit(f'`{urllib.parse.quote(e.pattern_match.group(1))}`')
@command(r'urldec (.+)','URL decode')
async def urldec_handler(e):await e.edit(f'`{urllib.parse.unquote(e.pattern_match.group(1))}`')
@command(r'bin (.+)','Text to binary')
async def bin_handler(e):await e.edit('`'+' '.join(format(ord(c),'08b') for c in e.pattern_match.group(1))+'`')
@command(r'unbin (.+)','Binary to text')
async def unbin_handler(e):
 try:o=''.join(chr(int(x,2)) for x in e.pattern_match.group(1).split())
 except Exception as x:return await e.edit(Messages.error(f'Invalid binary: {x}'))
 await e.edit(f'`{o}`')
@command(r'hex (.+)','Text to hex')
async def hex_handler(e):await e.edit(f'`{binascii.hexlify(e.pattern_match.group(1).encode()).decode()}`')
@command(r'unhex (.+)','Hex to text')
async def unhex_handler(e):
 try:o=binascii.unhexlify(e.pattern_match.group(1)).decode(errors='replace')
 except Exception as x:return await e.edit(Messages.error(f'Invalid hex: {x}'))
 await e.edit(f'`{o}`')
@command(r'epoch(?:\s+(\d+))?','Unix timestamp')
async def epoch_handler(e):
 a=e.pattern_match.group(1)
 if a:
  try:return await e.edit(f'🕒 `{a}`\n**UTC:** `{datetime.fromtimestamp(int(a),timezone.utc):%Y-%m-%d %H:%M:%S}`')
  except Exception as x:return await e.edit(Messages.error(str(x)))
 await e.edit(f'🕒 `{int(datetime.now(timezone.utc).timestamp())}`')
@command('devhelp','Devtools help')
async def devhelp_handler(e):await e.edit('🧰 `.password` `.uuid` `.token` `.hash` `.b64enc/.b64dec` `.urlenc/.urldec` `.bin/.unbin` `.hex/.unhex` `.epoch`')
