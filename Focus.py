import rumps
import customtkinter as ctk
import os, threading, time, json, sys, subprocess

# ファイルパス設定
CONFIG_FILE = os.path.expanduser("~/focus_config.json")
STATUS_FILE = os.path.expanduser("~/focus_status.json")
HOSTS_PATH = "/etc/hosts"
# アイコン画像パス（同じフォルダにある場合のみ使用）
ICON_LOCK = os.path.join(os.path.dirname(__file__), "icon_lock.png")

class FocusGui(ctk.CTk):
    def __init__(self, config):
        super().__init__()
        self.title("Focus")
        self.geometry("400x450")
        
        # 初期の最前面設定
        self.is_topmost = config.get("topmost", True)
        self.attributes('-topmost', self.is_topmost)
        
        ctk.set_appearance_mode("light")
        self.config_data = config
        
        self.tabview = ctk.CTkTabview(self, width=380, height=420)
        self.tabview.pack(padx=10, pady=5)
        self.tab_timer = self.tabview.add("タイマー")
        self.tab_limit = self.tabview.add("制限")

        self.setup_timer_tab()
        self.setup_limit_tab()
        self.update_ui()

    def setup_timer_tab(self):
        self.status_label = ctk.CTkLabel(self.tab_timer, text="現在：制限中 🔥", font=("Hiragino Sans", 20, "bold"), text_color="#E74C3C")
        self.status_label.pack(pady=(20, 10))
        self.timer_label = ctk.CTkLabel(self.tab_timer, text="00:00", font=("Helvetica", 70, "bold"), text_color="#3498db")
        self.timer_label.pack(pady=10)
        self.time_entry = ctk.CTkEntry(self.tab_timer, width=100, font=("Helvetica", 24), justify="center")
        self.time_entry.pack(pady=10)
        self.time_entry.insert(0, "15")
        self.start_btn = ctk.CTkButton(self.tab_timer, text="一時解除スタート", font=("Hiragino Sans", 18, "bold"), height=50, width=300, command=self.start_break)
        self.start_btn.pack(pady=30)

    def setup_limit_tab(self):
        ctk.CTkLabel(self.tab_limit, text="🚫 制限アプリ").pack()
        self.app_list = ctk.CTkTextbox(self.tab_limit, height=80)
        self.app_list.pack(pady=5, padx=10, fill="x")
        self.app_list.insert("1.0", "\n".join(self.config_data.get("apps", ["Music"])))
        ctk.CTkLabel(self.tab_limit, text="🌐 制限サイト").pack()
        self.site_list = ctk.CTkTextbox(self.tab_limit, height=80)
        self.site_list.pack(pady=5, padx=10, fill="x")
        self.site_list.insert("1.0", "\n".join(self.config_data.get("sites", ["youtube.com"])))
        ctk.CTkButton(self.tab_limit, text="保存して適用", command=self.save_config).pack(pady=10)

    def start_break(self):
        try:
            mins = int(self.time_entry.get())
            with open(CONFIG_FILE, "r") as f: data = json.load(f)
            data["break"] = mins
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except: pass

    def save_config(self):
        apps = [l.strip() for l in self.app_list.get("1.0", "end-1c").split("\n") if l.strip()]
        sites = [l.strip() for l in self.site_list.get("1.0", "end-1c").split("\n") if l.strip()]
        with open(CONFIG_FILE, "r") as f: data = json.load(f)
        data.update({"apps": apps, "sites": sites, "update_trigger": True})
        with open(CONFIG_FILE, "w") as f: json.dump(data, f)

    def update_ui(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    new_topmost = data.get("topmost", True)
                    if new_topmost != self.is_topmost:
                        self.is_topmost = new_topmost
                        self.attributes('-topmost', self.is_topmost)
            except: pass

        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    data = json.load(f)
                    t = data.get("display", "00:00")
                    self.timer_label.configure(text=t)
                    self.status_label.configure(text="解除中 ☕️" if t != "00:00" else "制限中 🔥")
            except: pass
        self.after(500, self.update_ui)

class FocusApp(rumps.App):
    def __init__(self):
        super(FocusApp, self).__init__("Focus", quit_button=None)
        self.set_lock_icon(True) 
        self.config = self.load_config()
        
        # アイテム作成
        self.timer_item = rumps.MenuItem("タイマーを開く", callback=self.open_gui)
        
        self.topmost_item = rumps.MenuItem("タイマーを常に最前面に表示", callback=self.toggle_topmost)
        self.topmost_item.state = 1 if self.config.get("topmost", True) else 0
        
        self.persist_item = rumps.MenuItem("アプリ終了後も制限を維持", callback=self.toggle_persistence)
        self.persist_item.state = 1 if self.config.get("persistent_limit") else 0
        
        # メニュー組み立て
        self.menu = [
            self.timer_item,
            None,
            self.topmost_item,
            self.persist_item,
            None,
            rumps.MenuItem("Version 1.0.0"),
            rumps.MenuItem("終了", callback=self.quit_app, key="q")
        ]
        
        self.remaining = 0
        self.is_break = False
        threading.Thread(target=self.worker, daemon=True).start()
        self.apply_site_block(True)

    def set_lock_icon(self, show):
        if show:
            if os.path.exists(ICON_LOCK):
                self.icon = ICON_LOCK
                self.title = None
            else:
                self.icon = None
                self.title = "🔒"
        else:
            self.icon = None

    def load_config(self):
        default = {"apps": ["Music"], "sites": ["youtube.com"], "persistent_limit": True, "topmost": True}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: default.update(json.load(f))
            except: pass
        with open(CONFIG_FILE, "w") as f: json.dump(default, f)
        return default

    def toggle_persistence(self, sender):
        sender.state = not sender.state
        self.config["persistent_limit"] = bool(sender.state)
        with open(CONFIG_FILE, "w") as f: json.dump(self.config, f)

    def toggle_topmost(self, sender):
        sender.state = not sender.state
        self.config["topmost"] = bool(sender.state)
        with open(CONFIG_FILE, "w") as f: json.dump(self.config, f)

    def apply_site_block(self, block):
        try:
            with open(CONFIG_FILE, "r") as f: data = json.load(f)
            sites = data.get("sites", [])
            if not sites: return
            clean_cmd = f"sudo sed -i '' '/127.0.0.1.*#Focus/d' {HOSTS_PATH}"
            if block:
                lines = "\\n".join([f"127.0.0.1 {s} #Focus\\n127.0.0.1 www.{s} #Focus" for s in sites])
                full_cmd = f"{clean_cmd} && printf '{lines}' | sudo tee -a {HOSTS_PATH}"
            else:
                full_cmd = clean_cmd
            full_cmd += " && dscacheutil -flushcache && killall -HUP mDNSResponder"
            ascript = f'do shell script "{full_cmd}" with administrator privileges'
            subprocess.call(["osascript", "-e", ascript])
        except Exception as e: print(f"Error: {e}")

    def worker(self):
        while True:
            try:
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "r") as f: data = json.load(f)
                    if data.get("update_trigger"):
                        data["update_trigger"] = False
                        with open(CONFIG_FILE, "w") as f: json.dump(data, f)
                        if not self.is_break: self.apply_site_block(True)
                    if "break" in data:
                        self.remaining = data.pop("break") * 60
                        self.is_break = True
                        with open(CONFIG_FILE, "w") as f: json.dump(data, f)
                        self.set_lock_icon(False) 
                        self.apply_site_block(False)
                if self.remaining > 0:
                    self.remaining -= 1
                    m, s = divmod(self.remaining, 60)
                    time_str = f"{m:02d}:{s:02d}"
                    self.title = f"☕️ {time_str}"
                    with open(STATUS_FILE, "w") as f: json.dump({"display": time_str}, f)
                elif self.is_break:
                    self.is_break = False
                    self.set_lock_icon(True)
                    with open(STATUS_FILE, "w") as f: json.dump({"display": "00:00"}, f)
                    self.apply_site_block(True)
                if not self.is_break:
                    for app in data.get("apps", []):
                        os.system(f"killall -9 '{app}' > /dev/null 2>&1")
            except: pass
            time.sleep(1)

    def open_gui(self, _):
        # アプリ化した際も正しく起動できるように設定
        if getattr(sys, 'frozen', False):
            # ビルド済みアプリの場合
            app_path = os.path.join(os.path.dirname(sys.executable), "Focus")
            subprocess.Popen([app_path, "--gui"])
        else:
            # Python実行の場合
            subprocess.Popen([sys.executable, __file__, "--gui"])

    def quit_app(self, _):
        try:
            with open(CONFIG_FILE, "r") as f: data = json.load(f)
            if not data.get("persistent_limit"):
                self.apply_site_block(False)
        except: pass
        rumps.quit_application()

if __name__ == "__main__":
    if "--gui" in sys.argv:
        try:
            with open(CONFIG_FILE, "r") as f: conf = json.load(f)
        except: conf = {"apps": ["Music"], "sites": ["youtube.com"], "topmost": True}
        FocusGui(conf).mainloop()
    else:
        FocusApp().run()