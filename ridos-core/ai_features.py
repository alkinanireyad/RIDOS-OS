#!/usr/bin/env python3
"""RIDOS OS AI Features - Network, Hardware, Security, System tools"""
import os, sys, subprocess, socket, json
import urllib.request, urllib.error

# Colors
R="\033[0m"; P="\033[35m"; C="\033[36m"; G="\033[32m"
Y="\033[33m"; B="\033[34m"; W="\033[37m"; RED="\033[31m"

API_KEY_FILE = os.path.expanduser("~/.ridos/api_key")
API_URL = "https://api.anthropic.com/v1/messages"

def get_api_key():
    if os.path.exists(API_KEY_FILE):
        return open(API_KEY_FILE).read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

def ask_claude(prompt, system="You are RIDOS OS AI assistant. Be concise. Respond in English then Arabic."):
    key = get_api_key()
    if not key:
        return "[OFFLINE] No API key. Set key: mkdir -p ~/.ridos && echo 'YOUR_KEY' > ~/.ridos/api_key"
    try:
        data = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(API_URL, data=data, headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["content"][0]["text"]
    except Exception as e:
        return f"[OFFLINE] {e}\nLocal mode: Check your connection and API key."

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout + r.stderr
    except:
        return ""

def check_internet():
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except:
        return False

def banner():
    print(f"{P}{'='*60}")
    print(f"   RIDOS OS - AI Tools v1.0 Baghdad")
    print(f"{'='*60}{R}")

def menu():
    banner()
    print(f"\n{C}1.{R} AI Terminal Assistant")
    print(f"{C}2.{R} AI System Doctor")
    print(f"{C}3.{R} AI Network Analyzer")
    print(f"{C}4.{R} AI Hardware Fixer")
    print(f"{C}5.{R} AI Security Scanner")
    print(f"{C}0.{R} Exit\n")
    online = f"{G}ONLINE{R}" if check_internet() else f"{Y}OFFLINE{R}"
    print(f"Status: {online}")
    return input(f"\n{P}Select: {R}").strip()

def system_doctor():
    print(f"\n{P}=== AI System Doctor ==={R}")
    import psutil
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    data = f"CPU: {cpu}%, RAM: {ram.percent}% ({ram.used//1024//1024}MB/{ram.total//1024//1024}MB), Disk: {disk.percent}%"
    print(f"{C}{data}{R}")
    print(f"\n{Y}Analyzing with AI...{R}")
    result = ask_claude(f"System health: {data}. Give diagnosis and recommendations.")
    print(f"\n{G}{result}{R}")

def network_analyzer():
    print(f"\n{P}=== AI Network Analyzer ==={R}")
    ifaces = run_cmd("ip addr show")
    routes = run_cmd("ip route show")
    dns = run_cmd("cat /etc/resolv.conf")
    internet = "Connected" if check_internet() else "Disconnected"
    data = f"Interfaces: {ifaces[:500]}\nRoutes: {routes[:300]}\nDNS: {dns[:200]}\nInternet: {internet}"
    print(f"{C}Internet: {internet}{R}")
    print(f"\n{Y}Analyzing with AI...{R}")
    result = ask_claude(f"Network analysis: {data}. Give diagnosis.")
    print(f"\n{G}{result}{R}")

def hardware_fixer():
    print(f"\n{P}=== AI Hardware Fixer ==={R}")
    smart = run_cmd("smartctl -H /dev/sda 2>/dev/null || echo 'SMART N/A'")
    ram_info = run_cmd("free -h")
    cpu_info = run_cmd("lscpu | head -10")
    data = f"SMART: {smart[:300]}\nRAM: {ram_info}\nCPU: {cpu_info[:300]}"
    print(f"{C}Hardware scan complete{R}")
    print(f"\n{Y}Analyzing with AI...{R}")
    result = ask_claude(f"Hardware diagnostics: {data}. Give health report.")
    print(f"\n{G}{result}{R}")

def security_scanner():
    print(f"\n{P}=== AI Security Scanner ==={R}")
    target = input(f"{C}Enter target IP/domain [{R}localhost{C}]: {R}").strip() or "localhost"
    ports = run_cmd(f"nmap -F {target} 2>/dev/null || echo 'nmap N/A'")
    data = f"Target: {target}\nPort scan: {ports[:500]}"
    print(f"\n{Y}Analyzing with AI...{R}")
    result = ask_claude(f"Security scan results: {data}. Give risk assessment.")
    print(f"\n{G}{result}{R}")

def ai_terminal():
    print(f"\n{P}=== AI Terminal Assistant ==={R}")
    print(f"{C}Type Linux commands or questions. 'exit' to quit.{R}\n")
    while True:
        try:
            cmd = input(f"{P}ridos>{R} ").strip()
            if cmd.lower() in ['exit', 'quit']:
                break
            if not cmd:
                continue
            result = run_cmd(cmd)
            if result:
                print(f"{C}{result}{R}")
            else:
                print(f"{Y}Asking AI...{R}")
                answer = ask_claude(f"Linux question: {cmd}")
                print(f"{G}{answer}{R}")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    # Check if launched with option
    if len(sys.argv) > 1 and sys.argv[1] == "1":
        ai_terminal()
    else:
        while True:
            choice = menu()
            if choice == "1":
                ai_terminal()
            elif choice == "2":
                system_doctor()
            elif choice == "3":
                network_analyzer()
            elif choice == "4":
                hardware_fixer()
            elif choice == "5":
                security_scanner()
            elif choice == "0":
                print(f"\n{P}Goodbye! | مع السلامة{R}\n")
                break
            input(f"\n{C}Press Enter to continue...{R}")
