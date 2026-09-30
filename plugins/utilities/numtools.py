import math
from helpers.decorators import command
from utils.messages import Messages
R=[(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
@command(r'roman (\d+)','Decimal to Roman')
async def roman_handler(e):
 n=int(e.pattern_match.group(1));o=''
 for v,s in R:o+=s*(n//v);n%=v
 await e.edit(f'`{o}`')
@command(r'unroman ([IVXLCDMivxlcdm]+)','Roman to Decimal')
async def unroman_handler(e):
 V={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000};s=e.pattern_match.group(1).upper();n=p=0
 for c in s[::-1]:x=V[c];n+=-x if x<p else x;p=max(p,x)
 await e.edit(f'**{n}**')
@command(r'tobase (\d+) (\d+)','Decimal to base')
async def tobase_handler(e):
 n=int(e.pattern_match.group(1));b=int(e.pattern_match.group(2));d='0123456789abcdefghijklmnopqrstuvwxyz';o='0' if n==0 else ''
 while n:o=d[n%b]+o;n//=b
 await e.edit(Messages.error('Base must 2–36.') if not 2<=b<=36 else f'`{o}`')
@command(r'frombase (\w+) (\d+)','Base to decimal')
async def frombase_handler(e):
 try:o=int(e.pattern_match.group(1),int(e.pattern_match.group(2)))
 except Exception as x:return await e.edit(Messages.error(f'Invalid: {x}'))
 await e.edit(f'**{o}**')
@command(r'temp (-?\d+(?:\.\d+)?) ?([cfkCFK]?)','Temperature')
async def temp_handler(e):
 v=float(e.pattern_match.group(1));u=(e.pattern_match.group(2) or 'C').upper();c=v if u=='C' else (v-32)*5/9 if u=='F' else v-273.15;await e.edit(f'🌡 `{c:.2f}°C` `{c*9/5+32:.2f}°F` `{c+273.15:.2f}K`')
@command(r'percent (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)','Percent')
async def percent_handler(e):await e.edit(f'**{float(e.pattern_match.group(1))*float(e.pattern_match.group(2))/100:g}**')
@command(r'bytes (\d+(?:\.\d+)?) (b|kb|mb|gb|tb)','Bytes')
async def bytes_handler(e):await e.edit(f'**{float(e.pattern_match.group(1))*{"b":1,"kb":1024,"mb":1024**2,"gb":1024**3,"tb":1024**4}[e.pattern_match.group(2)]:,.0f} B**')
@command(r'aspect (\d+) (\d+)','Aspect ratio')
async def aspect_handler(e):a=int(e.pattern_match.group(1));b=int(e.pattern_match.group(2));g=math.gcd(a,b);await e.edit(f'`{a//g}:{b//g}`')
@command(r'prime (\d+)','Prime check')
async def prime_handler(e):n=int(e.pattern_match.group(1));await e.edit('✅ prime' if n>1 and all(n%i for i in range(2,int(n**.5)+1)) else '❌ not prime')
@command(r'factorial (\d+)','Factorial')
async def factorial_handler(e):await e.edit(f'`{math.factorial(int(e.pattern_match.group(1)))}`')
@command(r'fib (\d+)','Fibonacci')
async def fib_handler(e):
 a,b=0,1
 for _ in range(int(e.pattern_match.group(1))):a,b=b,a+b
 await e.edit(f'`{a}`')
@command('numhelp','Numtools help')
async def numhelp_handler(e):await e.edit('🔢 `.roman` `.unroman` `.tobase` `.frombase` `.temp` `.percent` `.bytes` `.aspect` `.prime` `.factorial` `.fib`')
