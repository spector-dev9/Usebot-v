import colorsys,random
from helpers.decorators import command
from utils.messages import Messages
def rgb(h):
 h=h.lstrip('#');h=''.join(c*2 for c in h) if len(h)==3 else h
 if len(h)!=6:raise ValueError
 return tuple(int(h[i:i+2],16) for i in(0,2,4))
def hx(r,g,b):return f'#{int(r):02X}{int(g):02X}{int(b):02X}'
@command(r'color (#?\w+)','Show color info')
async def color_handler(e):
 try:r,g,b=rgb(e.pattern_match.group(1))
 except:return await e.edit(Messages.error('Invalid hex color.'))
 h,l,s=colorsys.rgb_to_hls(r/255,g/255,b/255);await e.edit(f'🎨 **{hx(r,g,b)}**\n• RGB: `rgb({r}, {g}, {b})`\n• HSL: `hsl({int(h*360)}, {int(s*100)}%, {int(l*100)}%)`')
@command(r'rgb (\d+) (\d+) (\d+)','RGB to hex')
async def rgb_handler(e):
 v=tuple(map(int,[e.pattern_match.group(1),e.pattern_match.group(2),e.pattern_match.group(3)]));await e.edit(Messages.error('Each value must be 0–255.') if not all(0<=x<=255 for x in v) else f'🎨 `{hx(*v)}`')
@command('randomcolor','Random color')
async def randomcolor_handler(e):await e.edit(f'🎨 `{hx(*[random.randrange(256) for _ in range(3)])}`')
@command(r'palette (#?\w+)','Color palette')
async def palette_handler(e):
 try:r,g,b=rgb(e.pattern_match.group(1))
 except:return await e.edit(Messages.error('Invalid hex.'))
 h,l,s=colorsys.rgb_to_hls(r/255,g/255,b/255);f=lambda q: hx(*(x*255 for x in colorsys.hls_to_rgb(q%1,max(.05,min(.95,l)),s)));await e.edit('🎨 '+ ' '.join(f'`{f(h+d)}`' for d in(-.3,-.15,0,.15,.3)))
@command(r'gradient (#?\w+) (#?\w+) (\d+)','Color gradient')
async def gradient_handler(e):
 try:a=rgb(e.pattern_match.group(1));b=rgb(e.pattern_match.group(2));n=int(e.pattern_match.group(3))
 except:return await e.edit(Messages.error('Invalid inputs.'))
 if not 2<=n<=20:return await e.edit(Messages.error('Steps must be 2–20.'))
 await e.edit('\n'.join(f'{i+1}. `{hx(*(a[j]+(b[j]-a[j])*i/(n-1) for j in range(3)))}`' for i in range(n)))
@command('colorhelp','Color help')
async def colorhelp_handler(e):await e.edit('🎨 `.color` `.rgb` `.randomcolor` `.palette` `.gradient`')
