import codecs,random
from helpers.decorators import command
M=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789','.- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- -..- -.-- --.. ----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----.'.split()));MI={v:k for k,v in M.items()}
@command(r'upper (.+)','Uppercase')
async def upper_handler(e):await e.edit(e.pattern_match.group(1).upper())
@command(r'lower (.+)','Lowercase')
async def lower_handler(e):await e.edit(e.pattern_match.group(1).lower())
@command(r'titlecase (.+)','Title Case')
async def title_handler(e):await e.edit(e.pattern_match.group(1).title())
@command(r'swapcase (.+)','Swap case')
async def swapcase_handler(e):await e.edit(e.pattern_match.group(1).swapcase())
@command(r'capital (.+)','Capitalize')
async def capital_handler(e):await e.edit(e.pattern_match.group(1).capitalize())
@command(r'morse (.+)','Text to Morse')
async def morse_handler(e):await e.edit('`'+' '.join('/' if c==' ' else M.get(c,'?') for c in e.pattern_match.group(1).upper())+'`')
@command(r'unmorse (.+)','Morse to text')
async def unmorse_handler(e):await e.edit('`'+''.join(' ' if x=='/' else MI.get(x,'?') for x in e.pattern_match.group(1).split())+'`')
@command(r'rot13 (.+)','ROT13')
async def rot13_handler(e):await e.edit(f"`{codecs.encode(e.pattern_match.group(1),'rot_13')}`")
@command(r'caesar (\d+) (.+)','Caesar cipher')
async def caesar_handler(e):
 s=int(e.pattern_match.group(1))%26;t=e.pattern_match.group(2);o=''
 for c in t:o+=chr((ord(c)-(65 if c.isupper() else 97)+s)%26+(65 if c.isupper() else 97)) if c.isalpha() else c
 await e.edit(f'`{o}`')
@command(r'count (.+)','Count text')
async def count_handler(e):
 t=e.pattern_match.group(1);await e.edit(f'📊 chars:{len(t)} words:{len(t.split())} lines:{t.count(chr(10))+1}')
@command(r'sortlines (.+)','Sort lines')
async def sortlines_handler(e):await e.edit('```\n'+'\n'.join(sorted(set(e.pattern_match.group(1).splitlines())))+'\n```')
@command(r'dedupe (.+)','Remove duplicate lines')
async def dedupe_handler(e):await e.edit('```\n'+'\n'.join(dict.fromkeys(e.pattern_match.group(1).splitlines()))+'\n```')
@command(r'shufflines (.+)','Shuffle lines')
async def shufflines_handler(e):
 x=e.pattern_match.group(1).splitlines();random.shuffle(x);await e.edit('```\n'+'\n'.join(x)+'\n```')
@command('texthelp','Text help')
async def texthelp_handler(e):await e.edit('📝 `.upper` `.lower` `.titlecase` `.swapcase` `.capital` `.morse` `.unmorse` `.rot13` `.caesar` `.count` `.sortlines` `.dedupe` `.shufflines`')
