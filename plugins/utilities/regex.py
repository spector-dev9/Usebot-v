import re
from helpers.decorators import command
from utils.messages import Messages
@command(r'retest /(.+?)/ (.+)','Test regex')
async def retest_handler(e):
 try:m=re.findall(e.pattern_match.group(1),e.pattern_match.group(2))
 except re.error as x:return await e.edit(Messages.error(f'Bad pattern: `{x}`'))
 await e.edit(Messages.info('No matches.') if not m else f'🔍 **{len(m)} match(es)**\n'+'\n'.join(f'• `{x}`' for x in m[:40]))
@command(r'repl /(.+?)/ /(.+?)/ (.+)','Regex replace')
async def repl_handler(e):
 try:o=re.sub(e.pattern_match.group(1),e.pattern_match.group(2),e.pattern_match.group(3))
 except re.error as x:return await e.edit(Messages.error(f'Bad pattern: `{x}`'))
 await e.edit(f'```\n{o}\n```')
@command(r'resplit /(.+?)/ (.+)','Regex split')
async def resplit_handler(e):
 try:p=re.split(e.pattern_match.group(1),e.pattern_match.group(2))
 except re.error as x:return await e.edit(Messages.error(f'Bad pattern: `{x}`'))
 await e.edit(f'✂️ **{len(p)} parts**\n'+'\n'.join(f'{i+1}. `{x}`' for i,x in enumerate(p[:40])))
def ext(name,pat,label,icon):
 async def h(e):
  m=sorted(set(re.findall(pat,e.pattern_match.group(1))));await e.edit(Messages.info(f'No {label.lower()}.') if not m else f'{icon} **{label}**\n'+'\n'.join(f'• `{x}`' for x in m[:30]))
 h.__name__=name+'_handler';return command(f'{name} (.+)',f'Extract {label}')(h)
emails_handler=ext('emails',r'[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}','Emails','📧')
urls_handler=ext('urls',r'https?://[^\s<>"\']+','URLs','🔗')
phones_handler=ext('phones',r'(?:\+?\d[\d\s\-()]{7,}\d)','Phones','📞')
ips_handler=ext('ips',r'\b(?:\d{1,3}\.){3}\d{1,3}\b','IPs','🌐')
@command('regexhelp','Regex help')
async def regexhelp_handler(e):await e.edit('🔍 **REGEX**\n`.retest` `.repl` `.resplit` `.emails` `.urls` `.phones` `.ips`')
