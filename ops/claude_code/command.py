"""Pinned headless CLI contract; inference credentials never enter MCP tools."""
import json,os

def environment(home,output_tokens=4096):
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR')}
    env.update(HOME=str(home),CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
      CLAUDE_CODE_MAX_RETRIES='0',CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(output_tokens),
      CLAUDE_CODE_DISABLE_CLAUDE_MDS='1',CLAUDE_CODE_DISABLE_POLICY_SKILLS='1',
      CLAUDE_CODE_DISABLE_CRON='1',CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL='1',
      DISABLE_COMPACT='1',DISABLE_AUTO_COMPACT='1',DISABLE_EXTRA_USAGE_COMMAND='1',
      DISABLE_UPGRADE_COMMAND='1',DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',
      ENABLE_CLAUDEAI_MCP_SERVERS='false',ENABLE_TOOL_SEARCH='false',
      CLAUDE_CODE_MCP_ALLOWLIST_ENV='1',CLAUDE_CODE_SUBPROCESS_ENV_SCRUB='1',
      MAX_MCP_OUTPUT_TOKENS='4000',MAX_STRUCTURED_OUTPUT_RETRIES='0',CLAUDE_CODE_AUTO_CONNECT_IDE='false')
    return env

def command(policy,sid,mcp,system,resume=False,builder=False):
    args=[policy['cli'],'--restricted','-p','--verbose','--output-format','stream-json',
      '--tools','','--strict-mcp-config','--mcp-config',str(mcp),'--setting-sources','',
      '--settings',json.dumps({'disableAllHooks':True}), '--disable-slash-commands','--no-chrome',
      '--max-turns','1','--model',policy['model_roles']['builder' if builder else 'reviewer'],
      '--resume' if resume else '--session-id',sid,'--system-prompt',system]
    if builder:args+=['--allowedTools','mcp__phpretro__execute']
    else:args+=['--safe-mode']
    return args
