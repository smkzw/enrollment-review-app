{"name":"bash","arguments":{"command":"for p in 8000 5173 3000 8080; do printf \"port %s -> \" $p; curl -sS -o /dev/null -m 2 -w \"%{http_code}\\n\" http://127.0.0.1:$p/ 2>&1 || echo \"no-listener\"; done","i":"Probe local HTTP listeners"}}
</tool_call>
