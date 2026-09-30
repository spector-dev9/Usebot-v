import io,httpx
from helpers.decorators import command
from utils.messages import Messages
@command(r'qr (.+)','Generate a QR code')
async def qr_handler(e):
 t=e.pattern_match.group(1).strip()
 try:
  async with httpx.AsyncClient(timeout=15) as c:r=await c.get('https://api.qrserver.com/v1/create-qr-code/',params={'data':t,'size':'512x512','margin':10});r.raise_for_status()
  b=io.BytesIO(r.content);b.name='qr.png';await e.client.send_file(e.chat_id,b,caption=f'🔲 `{t[:80]}`');await e.delete()
 except Exception as x:await e.edit(Messages.error(f'Failed: `{x}`'))
@command('qrhelp','QR help')
async def qrhelp_handler(e):await e.edit('🔲 **QR**\n`.qr <text>` — generate QR')
