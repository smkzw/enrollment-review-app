{"name":"bash","arguments":{"command":"curl -sS -o /dev/null -m 3 -w \"%{http_code}\" http://127.0.0.1:4263/ && echo \" reachable\" || echo \" not-reachable\"","i":"Check local HTTP on port 4263"}}
</tool_call>
