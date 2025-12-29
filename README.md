# FontSniffer

智能字体爬虫工具，支持从 downcc.com 并发搜索并下载免费字体，提供现代化深色主题图形界面。

## 功能特性
- 🔍 **智能搜索**：输入关键词快速匹配字体
- ⚡ **并发爬取**：可配置线程数加速搜索（建议5-10线程）
- 🎨 **现代UI**：Sun Valley 深色主题，支持响应式布局
- 📊 **实时统计**：显示进度、请求状态、搜索耗时
- 📋 **便捷操作**：支持复制链接、浏览器打开、一键清空结果
- ⚠️ **错误处理**：智能重试机制与失败统计

## 安装
```bash
# 克隆仓库
git clone https://github.com/your-username/FontSniffer.git
cd FontSniffer

# 安装依赖
pip install -r requirements.txt
```

依赖项：`sv-ttk`, `requests`, `beautifulsoup4`

## 快速开始
1. 运行主程序：`python gui_model.py`
2. 输入搜索关键词（如"楷体"）
3. 点击"开始搜索"
4. 右键结果可复制链接或浏览器打开

## 许可证
本项目采用 MIT License。依赖项 [Sun Valley ttk theme](https://github.com/rdbende/Sun-Valley-ttk-theme) 同样使用 MIT License。
