#!/usr/bin/env python3
"""
debian-flex — Flexible Debian system management CLI
For RIDOS OS — IT & Communications Professionals
Run: debian-flex --help
     debian-flex init switch --to openrc
     debian-flex pkg install --compile nginx
     debian-flex service add --name myapp --cmd "sleep 300"
"""
import argparse, sys, time, os, json, random

# ── Minimal rich-compatible output (no dependencies needed) ──
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False

    class _Table:
        def __init__(self, title="", **kw):
            self.title = title
            self.cols = []
            self.rows = []
        def add_column(self, name, **kw):
            self.cols.append(name)
        def add_row(self, *vals):
            # Strip rich markup
            clean = []
            for v in vals:
                import re
                clean.append(re.sub(r'\[.*?\]', '', str(v)))
            self.rows.append(clean)
        def show(self):
            widths = [max(len(c), max((len(r[i]) for r in self.rows), default=0))
                      for i, c in enumerate(self.cols)]
            sep = "+" + "+".join("-"*(w+2) for w in widths) + "+"
            def row_str(cells):
                return "|" + "|".join(f" {c:<{widths[i]}} "
                                       for i, c in enumerate(cells)) + "|"
            print(f"\n  {self.title}")
            print(sep)
            print(row_str(self.cols))
            print(sep)
            for r in self.rows:
                print(row_str(r))
            print(sep)

    class _Console:
        def print(self, msg="", **kw):
            import re
            print(re.sub(r'\[/?[^\]]*\]', '', str(msg)))
        def rule(self, title=""):
            import re
            t = re.sub(r'\[/?[^\]]*\]', '', title)
            print(f"\n{'─'*20} {t} {'─'*20}")

    class Table(_Table):
        pass

    class _Panel:
        def __init__(self, text, title="", border_style="", **kw):
            import re
            self._text  = re.sub(r'\[/?[^\]]*\]', '', text)
            self._title = re.sub(r'\[/?[^\]]*\]', '', title)
        def __str__(self):
            lines = self._text.split('\n')
            w = max(len(l) for l in lines + [self._title]) + 4
            border = "─" * w
            out = [f"┌{border}┐", f"│  {self._title:<{w-2}}│",
                   f"├{border}┤"]
            for l in lines:
                out.append(f"│  {l:<{w-2}}│")
            out.append(f"└{border}┘")
            return "\n".join(out)

    class Panel(_Panel):
        pass

    console = _Console()

    class _box:
        ROUNDED = None
    box = _box()

    class Progress:
        def __init__(self, *args, **kw):
            self._task_desc = ""
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def add_task(self, desc, total=10, **kw):
            self._total = total
            self._done = 0
            return 0
        def update(self, t, description="", **kw):
            self._task_desc = description
        def advance(self, t):
            self._done += 1
            pct = int(self._done / self._total * 30)
            bar = "█" * pct + "░" * (30 - pct)
            import re
            desc = re.sub(r'\[/?[^\]]*\]', '',
                          self._task_desc)[:35]
            print(f"\r  [{bar}] {desc:<35}", end="", flush=True)
            if self._done >= self._total:
                print()

    def SpinnerColumn(**kw): return None
    def BarColumn(**kw): return None
    def TextColumn(t, **kw): return None
    def TimeElapsedColumn(**kw): return None


def _print(obj):
    if RICH:
        if isinstance(obj, str):
            console.print(obj)
        else:
            console.print(obj)
    else:
        if hasattr(obj, 'show'):
            obj.show()
        else:
            print(str(obj))

# ── State ──────────────────────────────────────────────────────
STATE = "/tmp/debian-flex-state.json"

def load_state():
    if os.path.exists(STATE):
        try: return json.load(open(STATE))
        except: pass
    return {"services": {}, "packages": []}

def save_state(s):
    json.dump(s, open(STATE, "w"), indent=2)

# ════════════════════════════════════════════════════════════════
# FEATURE 1 — init switch
# ════════════════════════════════════════════════════════════════
def cmd_init_switch(args):
    target = args.to
    _print(Panel(
        f"[bold cyan]debian-flex init switch[/bold cyan]\n"
        f"Target: [bold yellow]{target}[/bold yellow]\n"
        f"Mode: [bold green]SIMULATED[/bold green]",
        title="Init System Switcher", border_style="cyan"))

    steps_map = {
        "openrc":  [
            ("Detecting current init (systemd)",     "found: /run/systemd"),
            ("Resolving package conflicts",           "apt-mark hold systemd"),
            ("Installing openrc",                     "apt-get install openrc"),
            ("Converting service units → init.d",     "systemd-to-openrc migration"),
            ("Setting default runlevel",               "rc-update add default"),
            ("Updating initramfs",                     "update-initramfs -u"),
            ("Writing /etc/inittab",                   "runlevel 2 → default"),
            ("Configuring getty on tty1",              "agetty 115200 linux"),
            ("Preparing kexec payload",                "kexec -l /boot/vmlinuz"),
            ("would switch to openrc",                 "[SIMULATED] kexec --exec"),
        ],
        "runit":   [
            ("Detecting current init",                "systemd"),
            ("Installing runit",                      "apt-get install runit"),
            ("Creating /etc/sv directories",          "mkdir -p /etc/sv"),
            ("Migrating services → /etc/sv",          "openrc-to-runit script"),
            ("Setting PID 1 → runit",                 "update-alternatives"),
            ("Preparing kexec payload",               "kexec -l /boot/vmlinuz"),
            ("would switch to runit",                 "[SIMULATED] kexec --exec"),
        ],
        "s6":      [
            ("Detecting current init",                "systemd"),
            ("Installing s6 + s6-rc",                "apt-get install s6 s6-rc"),
            ("Compiling service database",            "s6-rc-compile /etc/s6/db"),
            ("Setting PID 1 → s6",                   "update-alternatives"),
            ("Preparing kexec payload",               "kexec -l /boot/vmlinuz"),
            ("would switch to s6",                    "[SIMULATED] kexec --exec"),
        ],
        "systemd": [
            ("Detecting current init",                "sysvinit"),
            ("Installing systemd",                    "apt-get install systemd"),
            ("Generating machine-id",                 "systemd-machine-id-setup"),
            ("Setting default.target",                "systemctl set-default"),
            ("Preparing kexec payload",               "kexec -l /boot/vmlinuz"),
            ("would switch to systemd",               "[SIMULATED] kexec --exec"),
        ],
        "sysvinit":[
            ("Detecting current init",                "systemd"),
            ("Installing sysvinit-core",              "apt-get install sysvinit-core"),
            ("Writing /etc/inittab",                  "runlevel 2 configured"),
            ("Preparing kexec payload",               "kexec -l /boot/vmlinuz"),
            ("would switch to sysvinit",              "[SIMULATED] kexec --exec"),
        ],
    }
    steps = steps_map.get(target, steps_map["openrc"])

    with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                  BarColumn(bar_width=30), TimeElapsedColumn(),
                  console=console) as p:
        t = p.add_task("Switching...", total=len(steps))
        for desc, detail in steps:
            p.update(t, description=f"{desc}...")
            time.sleep(0.35 if "kexec" not in desc else 0.7)
            p.advance(t)

    tbl = Table(title="Init Switch Summary", box=box.ROUNDED, border_style="cyan")
    tbl.add_column("Property");  tbl.add_column("Value"); tbl.add_column("Status")
    for prop, val, status in [
        ("Previous init",  "systemd",           "[green]replaced[/green]"),
        ("New init",       target,              "[bold green]ready[/bold green]"),
        ("PID 1",          f"/sbin/{target}",   "[green]configured[/green]"),
        ("Services",       "migrated",          "[green]OK[/green]"),
        ("kexec",          "prepared",          "[yellow]SIMULATED[/yellow]"),
        ("Config",         f"/etc/{target}.conf","[green]written[/green]"),
    ]:
        tbl.add_row(prop, val, status)
    _print(tbl)

    _print(Panel(
        f"[bold green]would switch to {target}[/bold green]\n"
        f"[yellow]In production: kexec reloads kernel with {target} as PID 1[/yellow]\n"
        f"[dim]Reboot required in real environment[/dim]",
        border_style="green"))


# ════════════════════════════════════════════════════════════════
# FEATURE 2 — hybrid package install
# ════════════════════════════════════════════════════════════════
def cmd_pkg_install(args):
    pkg = args.package
    _print(Panel(
        f"[bold cyan]debian-flex pkg install[/bold cyan]\n"
        f"Package: [bold yellow]{pkg}[/bold yellow]\n"
        f"Mode: [bold magenta]{'--compile (source build)' if args.compile else 'binary apt'}[/bold magenta]",
        title="Hybrid Package Manager", border_style="magenta"))

    if args.compile:
        _install_compile(pkg)
    else:
        _install_binary(pkg)


def _install_binary(pkg):
    steps = [
        (f"Fetching {pkg} from apt cache",   0.3),
        ("Resolving dependencies",            0.4),
        ("Downloading .deb package",          0.8),
        ("Verifying GPG signature",           0.2),
        ("Unpacking archive",                 0.4),
        ("Running dpkg --install",            0.3),
        ("Updating alternatives",             0.2),
        ("Running post-install hooks",        0.3),
    ]
    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                  BarColumn(bar_width=35), TextColumn("{task.percentage:>3.0f}%"),
                  console=console) as p:
        t = p.add_task("Installing...", total=len(steps))
        for desc, delay in steps:
            p.update(t, description=desc)
            time.sleep(delay); p.advance(t)

    deb = f"/tmp/{pkg}_1.0-1_amd64.deb"
    open(deb, "wb").write(f"Package: {pkg}\nVersion: 1.0-1\n".encode())
    _save_pkg(pkg, "1.0-1", "binary", deb)
    _show_pkg_table(pkg, "binary", deb)


def _install_compile(pkg):
    ver = "1.24.0"
    src = f"/tmp/{pkg}-{ver}"
    deb = f"/tmp/{pkg}_{ver}-1_amd64.deb"
    steps = [
        (f"Fetching {pkg} {ver} source tarball",     0.3),
        ("Verifying source SHA256",                   0.2),
        (f"Extracting {pkg}-{ver}.tar.gz",            0.3),
        ("Installing build-deps: gcc make libssl-dev",0.5),
        ("./configure --prefix=/usr --with-http_ssl", 0.7),
        ("cc -O2 src/core/main.c",                    0.8),
        ("cc -O2 src/http/request.c",                 0.7),
        ("cc -O2 src/event/epoll.c",                  0.6),
        ("ld -o " + pkg + " obj/*.o",                 0.4),
        ("strip --strip-debug ./" + pkg,              0.2),
        ("checkinstall --pkgname=" + pkg,             0.4),
        (f"Created {pkg}_{ver}-1_amd64.deb",          0.3),
        ("dpkg --install " + deb,                     0.3),
    ]
    with Progress(SpinnerColumn(), TextColumn("[bold yellow]{task.description}"),
                  BarColumn(bar_width=28),
                  TextColumn("{task.percentage:>3.0f}%"),
                  TimeElapsedColumn(), console=console) as p:
        t = p.add_task("Building...", total=len(steps))
        for desc, delay in steps:
            p.update(t, description=desc)
            time.sleep(delay); p.advance(t)

    os.makedirs(src, exist_ok=True)
    with open(deb, "wb") as f:
        f.write(f"Package: {pkg}\nVersion: {ver}-1\nMethod: compiled\n".encode())
    _save_pkg(pkg, f"{ver}-1", "compiled", deb, src)
    _show_pkg_table(pkg, "compiled", deb, src)


def _save_pkg(name, ver, method, deb, src=None):
    from datetime import datetime
    s = load_state()
    s["packages"].append({"name": name, "version": ver, "method": method,
                           "path": deb, "src": src or "",
                           "installed": datetime.now().isoformat()})
    save_state(s)


def _show_pkg_table(pkg, method, deb, src=None):
    tbl = Table(title=f"Package Result: {pkg}", box=box.ROUNDED, border_style="magenta")
    tbl.add_column("Property"); tbl.add_column("Value"); tbl.add_column("Status")
    rows = [
        ("Package",  pkg,                   "[green]installed[/green]"),
        ("Method",   method,                "[bold green]OK[/bold green]"),
        (".deb file",deb,                   "[green]created[/green]"),
        ("Binary",   "/usr/sbin/" + pkg,    "[green]deployed[/green]"),
        ("Config",   f"/etc/{pkg}/",        "[green]ready[/green]"),
    ]
    if src:
        rows.append(("Source dir", src, "[green]kept[/green]"))
    for r in rows: tbl.add_row(*r)
    _print(tbl)
    _print(f"[bold green]Package '{pkg}' installed via {method}[/bold green]")
    _print(f"[dim].deb → {deb}[/dim]")


def cmd_pkg_list(args):
    s = load_state()
    pkgs = s.get("packages", [])
    if not pkgs:
        _print("[yellow]No packages installed yet.[/yellow]")
        return
    tbl = Table(title="Installed Packages", box=box.ROUNDED, border_style="magenta")
    for col in ["Package","Version","Method",".deb Path","Installed"]:
        tbl.add_column(col)
    for p in pkgs:
        tbl.add_row(p["name"], p["version"], p["method"],
                    p["path"], p["installed"][:19])
    _print(tbl)


# ════════════════════════════════════════════════════════════════
# FEATURE 3 — service supervisor
# ════════════════════════════════════════════════════════════════
def cmd_service_add(args):
    name, cmd = args.name, args.cmd
    _print(Panel(
        f"[bold cyan]debian-flex service add[/bold cyan]\n"
        f"Name: [bold yellow]{name}[/bold yellow]\n"
        f"Command: [bold white]{cmd}[/bold white]",
        title="Service Supervisor", border_style="yellow"))

    steps = [
        ("Validating service definition",           0.2),
        ("Creating /etc/supervisor.d/" + name,      0.2),
        ("Writing unit configuration",              0.2),
        ("Registering with supervisor daemon",      0.3),
        (f"fork() → exec: {cmd[:30]}",              0.4),
        ("Waiting for process to become ready",     0.4),
        ("Registering PID in process table",        0.2),
    ]
    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                  BarColumn(bar_width=35), TimeElapsedColumn(),
                  console=console) as p:
        t = p.add_task("Starting...", total=len(steps))
        for desc, delay in steps:
            p.update(t, description=desc)
            time.sleep(delay); p.advance(t)

    from datetime import datetime
    pid = random.randint(1000, 32000)
    s = load_state()
    s["services"][name] = {
        "name": name, "cmd": cmd, "pid": pid,
        "status": "running",
        "started": datetime.now().isoformat(),
        "restarts": 0,
    }
    save_state(s)
    _show_svc_table(s["services"])
    _print(f"\n[bold green]service started[/bold green]")
    _print(f"[dim]PID {pid}  |  /etc/supervisor.d/{name}.conf[/dim]")


def cmd_service_list(args):
    s = load_state()
    svcs = s.get("services", {})
    if not svcs:
        _print("[yellow]No services registered. Use: service add --name X --cmd Y[/yellow]")
        return
    _show_svc_table(svcs)


def cmd_service_stop(args):
    s = load_state()
    if args.name not in s["services"]:
        _print(f"[red]Service '{args.name}' not found[/red]"); sys.exit(1)
    s["services"][args.name].update({"status": "stopped", "pid": "-"})
    save_state(s)
    _print(f"[yellow]Service '{args.name}' stopped[/yellow]")
    _show_svc_table(s["services"])


def _show_svc_table(svcs):
    tbl = Table(title="Service Supervisor", box=box.ROUNDED,
                border_style="yellow", show_lines=True)
    for col, w in [("Name",14),("PID",8),("Status",10),
                   ("Command",22),("Started",19),("Restarts",8)]:
        tbl.add_column(col, width=w)
    for n, v in svcs.items():
        st = v.get("status","?")
        st_str = ("[bold green]running[/bold green]" if st == "running"
                  else "[yellow]stopped[/yellow]" if st == "stopped"
                  else "[red]failed[/red]")
        tbl.add_row(n, str(v.get("pid","-")), st_str,
                    str(v.get("cmd",""))[:22],
                    str(v.get("started",""))[:19],
                    str(v.get("restarts",0)))
    _print(tbl)


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        prog="debian-flex",
        description="debian-flex — Flexible Debian system management (simulated mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py init switch --to openrc
  python3 main.py init switch --to runit
  python3 main.py pkg install nginx
  python3 main.py pkg install --compile nginx
  python3 main.py pkg list
  python3 main.py service add --name test --cmd "sleep 300"
  python3 main.py service list
  python3 main.py service stop --name test
        """)

    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # init
    ip = sub.add_parser("init",    help="Init system switcher")
    is_ = ip.add_subparsers(dest="sub", metavar="ACTION"); is_.required = True
    sw = is_.add_parser("switch",  help="Switch init system via simulated kexec")
    sw.add_argument("--to", required=True,
                    choices=["openrc","runit","s6","systemd","sysvinit"],
                    metavar="INIT",
                    help="Target: openrc | runit | s6 | systemd | sysvinit")
    sw.set_defaults(func=cmd_init_switch)

    # pkg
    pp = sub.add_parser("pkg",     help="Hybrid package manager")
    ps = pp.add_subparsers(dest="sub", metavar="ACTION"); ps.required = True
    pi = ps.add_parser("install",  help="Install a package (binary or compiled)")
    pi.add_argument("package",     help="Package name e.g. nginx")
    pi.add_argument("--compile",   action="store_true",
                    help="Build from source + create .deb via checkinstall")
    pi.set_defaults(func=cmd_pkg_install)
    pl = ps.add_parser("list",     help="List installed packages")
    pl.set_defaults(func=cmd_pkg_list)

    # service
    sp = sub.add_parser("service", help="Process supervisor")
    ss = sp.add_subparsers(dest="sub", metavar="ACTION"); ss.required = True
    sa = ss.add_parser("add",      help="Add and start a supervised service")
    sa.add_argument("--name", required=True, help="Service name")
    sa.add_argument("--cmd",  required=True, help="Command to supervise")
    sa.set_defaults(func=cmd_service_add)
    sl = ss.add_parser("list",     help="List all supervised services")
    sl.set_defaults(func=cmd_service_list)
    sst = ss.add_parser("stop",    help="Stop a supervised service")
    sst.add_argument("--name", required=True, help="Service name to stop")
    sst.set_defaults(func=cmd_service_stop)

    args = p.parse_args()
    console.rule("[bold cyan]debian-flex[/bold cyan] [dim]v1.0[/dim]")
    args.func(args)
    console.rule("[dim]done[/dim]")

if __name__ == "__main__":
    main()
