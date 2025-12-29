import queue
import re
import threading
import time
import tkinter as tk
from datetime import timedelta
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from Sniffer import FontSniffer


class FontSnifferGUI:
    """字体嗅探器图形界面主类"""

    def __init__(self, root: tk.Tk) -> None:
        """初始化GUI主窗口"""
        self.root = root
        self.root.title("FontSniffer 0.9.0")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)

        # 应用 Sun Valley 深色主题
        self.setup_theme()

        # 状态管理
        self.is_searching: bool = False
        self.search_thread: Optional[threading.Thread] = None
        self.result_queue: queue.Queue = queue.Queue()
        self.start_time: Optional[float] = None

        # 统计计数
        self.found_count: int = 0
        self.current_page: int = 0
        self.total_pages: int = 383

        # 构建界面
        self.create_widgets()

        # 启动队列检查
        self.check_queue()

    def setup_theme(self) -> None:
        """配置 Sun Valley 深色主题"""
        try:
            from sv_ttk import set_theme
            set_theme("dark")
        except ImportError:
            messagebox.showerror("错误", "请先安装 sv-ttk: pip install sv-ttk")
            self.root.destroy()
            return

        # 主色调 #121928 配色方案
        self.colors = {
            "bg_primary": "#121928",
            "bg_secondary": "#1E293B",
            "accent": "#60A5FA",
            "text": "#F1F5F9",
            "text_dim": "#94A3B8",
            "success": "#34D399",
            "warning": "#FBBF24",
        }

        self.root.configure(bg=self.colors["bg_primary"])
        style = ttk.Style()

        # 全局样式
        style.configure("TFrame", background=self.colors["bg_primary"])
        style.configure("TLabelframe", background=self.colors["bg_primary"])
        style.configure("TLabelframe.Label", background=self.colors["bg_primary"],
                       foreground=self.colors["text"])

        # 标题样式
        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 28, "bold"),
            foreground=self.colors["accent"],
            background=self.colors["bg_primary"]
        )

        # 控件样式
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"),
                       padding=(20, 8))
        style.configure("TEntry", font=("Segoe UI", 12), padding=(10, 6))

        # 进度条样式
        style.configure(
            "TProgressbar",
            thickness=8,
            background=self.colors["accent"],
            troughcolor=self.colors["bg_secondary"]
        )

    def create_widgets(self) -> None:
        """构建所有界面组件"""
        # 主容器
        main_container = ttk.Frame(self.root, padding="30 25 30 25")
        main_container.pack(fill=tk.BOTH, expand=True)

        # ========== 标题区域 ==========
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 25))

        title = ttk.Label(title_frame, text="🔍 字体嗅探器",
                         style="Title.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            title_frame,
            text="从 downcc.com 智能搜索并下载免费字体",
            font=("Segoe UI", 11),
            foreground=self.colors["text_dim"],
            background=self.colors["bg_primary"]
        )
        subtitle.pack(anchor="w", pady=(8, 0))

        # ========== 搜索控制面板 ==========
        control_panel = ttk.LabelFrame(main_container, text="搜索配置",
                                      padding="20 15")
        control_panel.pack(fill=tk.X, pady=(0, 20))

        # 关键词输入行
        keyword_row = ttk.Frame(control_panel)
        keyword_row.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            keyword_row,
            text="搜索关键词",
            font=("Segoe UI", 11, "bold"),
            foreground=self.colors["text"]
        ).pack(anchor="w", pady=(0, 8))

        self.keyword_var = tk.StringVar()
        self.keyword_entry = ttk.Entry(keyword_row,
                                      textvariable=self.keyword_var,
                                      style="TEntry")
        self.keyword_entry.pack(fill=tk.X, ipady=10)
        self.keyword_entry.bind("<Return>", lambda e: self.start_search())

        # 高级选项折叠区域
        self.advanced_expanded = tk.BooleanVar(value=False)

        def toggle_advanced() -> None:
            if self.advanced_expanded.get():
                advanced_frame.pack(fill=tk.X, pady=(15, 0))
                adv_toggle.config(text="▲ 隐藏高级选项")
            else:
                advanced_frame.pack_forget()
                adv_toggle.config(text="▼ 显示高级选项")

        adv_toggle = ttk.Checkbutton(
            control_panel,
            text="▼ 显示高级选项",
            variable=self.advanced_expanded,
            command=toggle_advanced,
            style="TCheckbutton"
        )
        adv_toggle.pack(anchor="w")

        # 高级选项内容
        advanced_frame = ttk.Frame(control_panel)

        # User-Agent
        ua_frame = ttk.Frame(advanced_frame)
        ua_frame.pack(fill=tk.X, pady=(10, 10))
        ttk.Label(ua_frame, text="User-Agent:",
                 foreground=self.colors["text_dim"]).pack(anchor="w")
        self.ua_var = tk.StringVar(
            value="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        ttk.Entry(ua_frame, textvariable=self.ua_var, width=80).pack(fill=tk.X,
                                                                    pady=(5, 0))

        # 并发控制
        concurrency_frame = ttk.Frame(advanced_frame)
        concurrency_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(concurrency_frame, text="并发线程数:",
                 foreground=self.colors["text_dim"]).pack(side=tk.LEFT)
        self.concurrency_var = tk.StringVar(value="8")
        concurrency_spin = ttk.Spinbox(
            concurrency_frame,
            from_=1,
            to=20,
            textvariable=self.concurrency_var,
            width=5,
            font=("Segoe UI", 11)
        )
        concurrency_spin.pack(side=tk.LEFT, padx=(10, 0))

        # ========== 操作按钮 ==========
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        self.search_button = ttk.Button(
            button_frame,
            text="开始搜索",
            style="Accent.TButton",
            command=self.start_search
        )
        self.search_button.pack(side=tk.LEFT, padx=(0, 10))

        self.reset_button = ttk.Button(
            button_frame,
            text="重置",
            style="TButton",
            command=self.reset_search,
            state="disabled"
        )
        self.reset_button.pack(side=tk.LEFT)

        # ========== 进度区域 ==========
        progress_panel = ttk.LabelFrame(main_container, text="实时进度",
                                       padding="20 15")
        progress_panel.pack(fill=tk.X, pady=(0, 20))

        # 状态文本
        self.status_var = tk.StringVar(value="等待搜索指令...")
        self.status_label = ttk.Label(
            progress_panel,
            textvariable=self.status_var,
            font=("Segoe UI", 11),
            foreground=self.colors["text"],
            wraplength=900
        )
        self.status_label.pack(anchor="w", pady=(0, 12))

        # 进度条
        progress_bar_frame = ttk.Frame(progress_panel)
        progress_bar_frame.pack(fill=tk.X)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_bar_frame,
            variable=self.progress_var,
            maximum=100,
            length=600
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_percent = ttk.Label(
            progress_bar_frame,
            text="0%",
            font=("Segoe UI", 11, "bold"),
            foreground=self.colors["accent"],
            width=6
        )
        self.progress_percent.pack(side=tk.LEFT, padx=(10, 0))

        # 统计信息行
        stats_frame = ttk.Frame(progress_panel)
        stats_frame.pack(fill=tk.X, pady=(12, 0))

        self.stats_var = tk.StringVar(value="找到 0 个字体 | 当前第 0 页 | 用时 00:00")
        ttk.Label(
            stats_frame,
            textvariable=self.stats_var,
            font=("Segoe UI", 11),
            foreground=self.colors["text_dim"]
        ).pack(anchor="w")

        # ========== 结果展示区域 ==========
        result_panel = ttk.LabelFrame(main_container, text="搜索结果",
                                     padding="20 15")
        result_panel.pack(fill=tk.BOTH, expand=True)

        # 结果操作按钮
        result_actions = ttk.Frame(result_panel)
        result_actions.pack(fill=tk.X, pady=(0, 10))

        self.copy_all_button = ttk.Button(
            result_actions,
            text="复制全部链接",
            command=self.copy_all_urls,
            state="disabled"
        )
        self.copy_all_button.pack(side=tk.LEFT)

        self.clear_results_button = ttk.Button(
            result_actions,
            text="清空结果",
            command=self.clear_results,
            state="disabled"
        )
        self.clear_results_button.pack(side=tk.LEFT, padx=(10, 0))

        # 结果列表（带滚动条）
        self.result_list = tk.Listbox(
            result_panel,
            bg=self.colors["bg_secondary"],
            fg=self.colors["text"],
            selectmode=tk.SINGLE,
            font=("Segoe UI", 11),
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(result_panel, orient=tk.VERTICAL,
                                 command=self.result_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_list.configure(yscrollcommand=scrollbar.set)

        # 右键菜单
        self.context_menu = tk.Menu(self.result_list, tearoff=0)
        self.context_menu.add_command(label="复制下载链接",
                                     command=self.copy_selected_url)
        self.context_menu.add_command(label="在浏览器中打开",
                                     command=self.open_in_browser)

        self.result_list.bind("<Button-3>", self.show_context_menu)
        self.result_list.bind("<Double-Button-1>",
                             lambda e: self.open_in_browser())

        # 底部状态栏
        self.statusbar = ttk.Label(
            self.root,
            text="就绪",
            foreground=self.colors["text_dim"],
            background=self.colors["bg_primary"],
            padding=(10, 8)
        )
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_context_menu(self, event: tk.Event) -> None:
        """显示右键菜单"""
        try:
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(self.result_list.nearest(event.y))
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_selected_url(self) -> None:
        """复制选中项的 URL"""
        selection = self.result_list.curselection()
        if selection:
            item = self.result_list.get(selection[0])
            url_match = re.search(r'下载页面：(.+)', item)
            if url_match:
                url = url_match.group(1)
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                self.statusbar.config(text="已复制到剪贴板",
                                    foreground=self.colors["success"])
                self.root.after(2000, lambda: self.statusbar.config(
                    foreground=self.colors["text_dim"]))

    def open_in_browser(self) -> None:
        """在浏览器中打开"""
        selection = self.result_list.curselection()
        if selection:
            item = self.result_list.get(selection[0])
            url_match = re.search(r'下载页面：(.+)', item)
            if url_match:
                import webbrowser
                webbrowser.open(url_match.group(1))
                self.statusbar.config(text="正在打开浏览器...",
                                    foreground=self.colors["accent"])

    def copy_all_urls(self) -> None:
        """复制所有结果链接"""
        all_items = self.result_list.get(0, tk.END)
        urls = [match.group(1)
                for item in all_items
                if (match := re.search(r'下载页面：(.+)', item))]

        if urls:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(urls))
            self.statusbar.config(text=f"已复制 {len(urls)} 个链接",
                                foreground=self.colors["success"])
            self.root.after(2000, lambda: self.statusbar.config(
                foreground=self.colors["text_dim"]))

    def clear_results(self) -> None:
        """清空结果列表"""
        self.result_list.delete(0, tk.END)
        self.found_count = 0
        self.update_stats()
        self.statusbar.config(text="结果已清空")

    def update_stats(self, found_count: Optional[int] = None,
                     current_page: Optional[int] = None) -> None:
        """更新统计信息"""
        if found_count is not None:
            self.found_count = found_count
        if current_page is not None:
            self.current_page = current_page

        # 计算用时
        elapsed = "00:00"
        if self.start_time:
            elapsed = str(timedelta(seconds=int(time.time() - self.start_time)))[2:7]

        self.stats_var.set(
            f"找到 {self.found_count} 个字体 | "
            f"当前第 {self.current_page}/{self.total_pages} 页 | "
            f"用时 {elapsed}"
        )

        # 更新进度百分比
        if self.total_pages > 0:
            progress = (self.current_page / self.total_pages) * 100
            self.progress_var.set(progress)
            self.progress_percent.config(text=f"{int(progress)}%")

    def start_search(self) -> None:
        """启动或停止搜索"""
        keyword = self.keyword_var.get().strip()

        # 修复：重置所有状态
        if not self.is_searching:
            # 重置所有进度和统计状态
            self.found_count = 0
            self.current_page = 0
            self.total_pages = 383
            self.start_time = time.time()
            self.progress_var.set(0)
            self.progress_percent.config(text="0%")
            self.update_stats(found_count=0, current_page=0)
            self.status_var.set(f"🔍 正在搜索: {keyword}")

        if not keyword:
            messagebox.showwarning("搜索提示", "请输入要搜索的字体关键词！")
            self.keyword_entry.focus()
            return

        if not self.is_searching:
            # 开始搜索
            self.is_searching = True

            # 更新 UI 状态
            self.search_button.config(text="⏹ 停止搜索")
            self.reset_button.config(state="disabled")
            self.result_list.delete(0, tk.END)
            self.keyword_entry.config(state="disabled")
            self.copy_all_button.config(state="disabled")
            self.clear_results_button.config(state="disabled")

            # 初始化爬虫
            try:
                max_workers = int(self.concurrency_var.get())
                max_workers = max(1, min(max_workers, 20))
            except ValueError:
                max_workers = 8

            user_agent = self.ua_var.get().strip()
            self.sniffer = FontSniffer(user_agent=user_agent,
                                      max_workers=max_workers)

            # 启动后台线程
            self.search_thread = threading.Thread(
                target=self.run_search,
                args=(keyword,),
                daemon=True
            )
            self.search_thread.start()

            self.statusbar.config(text="搜索进行中...")
        else:
            # 停止搜索
            self.stop_search()

    def stop_search(self) -> None:
        """停止搜索"""
        self.is_searching = False
        self.status_var.set("⏹ 搜索已停止")
        self.statusbar.config(text="搜索已停止",
                            foreground=self.colors["warning"])
        self.reset_ui()

    def reset_search(self) -> None:
        """重置搜索"""
        self.keyword_var.set("")
        self.result_list.delete(0, tk.END)
        self.found_count = 0
        self.current_page = 0
        self.progress_var.set(0)
        self.progress_percent.config(text="0%")
        self.update_stats(found_count=0, current_page=0)
        self.status_var.set("等待搜索指令...")
        self.statusbar.config(text="就绪", foreground=self.colors["text_dim"])
        self.keyword_entry.focus()

    def reset_ui(self) -> None:
        """重置UI状态"""
        self.is_searching = False
        self.search_button.config(text="开始搜索")
        self.reset_button.config(state="normal")
        self.keyword_entry.config(state="normal")
        self.copy_all_button.config(
            state="normal" if self.found_count > 0 else "disabled")
        self.clear_results_button.config(
            state="normal" if self.found_count > 0 else "disabled")

    def run_search(self, keyword: str) -> None:
        """在后台线程运行搜索"""
        try:
            # 连接爬虫的停止检查
            self.sniffer.should_stop = lambda: not self.is_searching

            for item in self.sniffer.search(keyword):
                if not self.is_searching:
                    break
                self.result_queue.put(item)
        except Exception as e:
            self.result_queue.put({"type": "error", "content": str(e)})
        finally:
            self.result_queue.put({"type": "done"})

    def check_queue(self) -> None:
        """检查并处理单个队列项（避免UI阻塞）"""
        try:
            item: Dict[str, Any] = self.result_queue.get_nowait()

            if item["type"] == "status":
                # 解析页码
                page_match = re.search(r'第(\d+)页', item["content"])
                if page_match:
                    self.current_page = int(page_match.group(1))

                # 解析总页数
                total_match = re.search(r'共(\d+)页', item["content"])
                if total_match:
                    self.total_pages = int(total_match.group(1))
                    self.progress_bar.config(maximum=self.total_pages)

                self.status_var.set(item["content"])
                self.update_stats()

            elif item["type"] == "result":
                # 添加到结果列表
                self.result_list.insert(tk.END, item["content"])
                self.found_count += 1
                self.update_stats()

                # 自动滚动到底部
                self.result_list.see(tk.END)

            elif item["type"] == "error":
                messagebox.showerror("搜索错误", item["content"])

            elif item["type"] == "done":
                # 搜索完成
                self.status_var.set("✅ 搜索完成！")
                self.statusbar.config(text="搜索完成",
                                    foreground=self.colors["success"])
                self.reset_ui()
                # 显示统计报告
                if hasattr(self.sniffer, 'stats'):
                    report = (
                        f"总请求: {self.sniffer.stats['total_requests']} | "
                        f"成功: {self.sniffer.stats['successful_requests']} | "
                        f"失败: {self.sniffer.stats['failed_requests']}"
                    )
                    self.statusbar.config(text=report)
                return  # 停止调度

        except queue.Empty:
            pass

        # 继续调度
        self.root.after(50, self.check_queue)


def main() -> None:
    """程序入口"""
    root = tk.Tk()
    app = FontSnifferGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()