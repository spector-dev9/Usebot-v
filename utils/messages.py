"""Messages — consistent, good-looking response templates."""
SEP_SHORT = "─" * 20
SEP_LONG = "─" * 30
SEP_FANCY = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
class Messages:
    SUCCESS="✅"; ERROR="❌"; WARNING="⚠️"; INFO="ℹ️"; LOADING="⏳"; PING="🏓"; ROCKET="🚀"; ARROW="▸"; BULLET="•"; CHECK="✓"; CROSS="✗"
    @staticmethod
    def success(text): return f"✅ **Success**\n{SEP_SHORT}\n{text}"
    @staticmethod
    def error(text): return f"❌ **Error**\n{SEP_SHORT}\n{text}"
    @staticmethod
    def warning(text): return f"⚠️ **Warning**\n{SEP_SHORT}\n{text}"
    @staticmethod
    def info(text): return f"ℹ️ {text}"
    @staticmethod
    def loading(text="Processing…"): return f"⏳ {text}"
    @staticmethod
    def header(emoji,title,subtitle=""):
        out=f"{emoji} **{title.upper()}**"; out += f"\n_{subtitle}_" if subtitle else ""; return out+f"\n{SEP_FANCY}"
    @staticmethod
    def card(emoji,title,rows): return (f"{emoji} **{title}**\n{SEP_FANCY}\n"+"".join(f"**{k}**  {v}\n" for k,v in rows)).rstrip()
    @staticmethod
    def fields(rows): return "\n".join(f"{'└' if i==len(rows)-1 else '├'} **{k}:** {v}" for i,(k,v) in enumerate(rows))
    @staticmethod
    def bullets(items,bullet="•"): return "\n".join(f"{bullet} {x}" for x in items)
    @staticmethod
    def numbered(items): return "\n".join(f"`{i:>2}.` {x}" for i,x in enumerate(items,1))
    @staticmethod
    def kv(key,value): return f"**{key}:** {value}"
    @staticmethod
    def format_key_value(key,value): return f"**{key}:** {value}"
    @staticmethod
    def code_block(text,language=""): return f"```{language}\n{text}\n```"
    @staticmethod
    def quote(text): return f"> {text}"
    @staticmethod
    def dim(text): return f"_{text}_"
    @staticmethod
    def bold(text): return f"**{text}**"
    @staticmethod
    def mono(text): return f"`{text}`"
    @staticmethod
    def footer(text): return f"{SEP_LONG}\n_{text}_"
    @staticmethod
    def empty(emoji,text): return f"{emoji} _{text}_"
