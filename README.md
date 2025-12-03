# AstrBot JM2PDF 插件

这是一个 AstrBot 插件，用于下载禁漫天堂（JMComic）的漫画并自动转换为 PDF 文件发送给用户。

## 功能特点

- 🚀 简单易用：只需发送 `jm <漫画ID>` 即可下载并转换
- 📥 自动下载：使用 JMComic-Crawler-Python 自动处理域名和网络连接
- 📄 无损转换：使用 img2pdf 进行无损 PDF 转换
- 🎨 格式处理：自动处理 RGBA、透明背景等特殊格式图片
- 📑 智能排序：按文件名自然排序确保页面顺序正确
- 🧹 自动清理：下载和发送后自动清理临时文件

## 安装

### 1. 安装依赖

```bash
pip install jmcomic img2pdf
```

### 2. 安装插件

将此插件目录放置到 AstrBot 的插件目录中。

## 使用方法

### 基本命令

```
/jm <漫画ID>
```

### 示例

```
/jm 123456
```

### 两种模式

**1. 静默模式（`send_progress_message: false`）**
- 用户发送指令后，机器人不会发送任何进度消息
- 只在最后发送 PDF 文件或错误消息
- 适合不想被进度消息打扰的用户

**2. 进度提示模式（`send_progress_message: true`，默认）**
- 机器人会发送下载进度、转换进度等消息
- 让用户了解当前处理状态
- 适合需要实时反馈的场景

### 处理流程

机器人会：
1. ✅ 验证漫画ID格式
2. � 检查是否已存在PDF文件（如果存在则直接发送，跳过下载）
3. �📥 下载指定漫画的所有章节
4. 🔄 将图片按顺序转换为PDF
5. 📤 发送PDF文件给用户
6. 🧹 自动清理临时文件（可配置保留）

> **提示**：设置 `keep_pdf=true` 可以缓存已下载的PDF，重复请求同一漫画时会直接发送已有文件，大幅提升响应速度！

## 配置

插件使用 `_conf_schema.json` 文件定义配置项。在 AstrBot 管理界面可以直接配置以下选项：

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `download_dir` | string | `./jm_downloads` | 漫画下载和PDF生成的临时目录 |
| `keep_images` | boolean | `false` | 下载完成后是否保留原始图片文件 |
| `keep_pdf` | boolean | `false` | 发送完成后是否保留生成的PDF文件。**建议设为true启用缓存，重复请求时直接发送已有PDF** |
| `max_file_size_mb` | integer | `0` | PDF文件大小限制(MB)，0表示不限制 |

### JMComic 客户端配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `jm_client_impl` | string | `html` | 客户端类型：html(网页端)或api(APP端)。**如遇IP限制请切换为api** |
| `jm_retry_times` | integer | `5` | 请求失败重试次数 |
| `jm_cookies_avs` | string | `""` | 登录Cookie(AVS)，用于访问需要登录的内容 |

> **提示**：插件会自动获取最新可用域名，无需手动配置。如遇访问问题，建议：
> 1. 切换客户端类型为 `api`（更稳定，不受IP限制）
> 2. 配置代理（见下方网络配置）
> 3. 如需访问登录内容，配置 `jm_cookies_avs`

### 网络配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `proxy` | string | `""` | HTTP代理地址，支持格式：http://127.0.0.1:7890 或 system/clash/v2ray |
| `timeout` | integer | `60` | 单个请求的超时时间(秒) |

### 下载配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `download_cache` | boolean | `true` | 启用下载缓存，已存在的文件跳过下载 |
| `image_decode` | boolean | `true` | 是否还原JM混淆过的图片（建议开启） |
| `image_suffix` | string | `""` | 图片格式转换，可选：.jpg/.png/.webp |
| `concurrent_images` | integer | `30` | 并发下载图片数(1-50) |
| `concurrent_photos` | integer | `8` | 并发下载章节数 |

### 文件夹配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `dir_rule` | string | `Bd/Ptitle` | 目录规则，如：Bd/Aid/Pindex |
| `normalize_zh` | string | `""` | 中文繁简转换：zh-cn(简体)/zh-tw(繁体) |

### 其他配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_jm_log` | boolean | `false` | 是否显示JMComic库的详细日志 |
| `send_progress_message` | boolean | `true` | 是否发送进度消息（关闭后只发送PDF或错误） |
| `log_level` | string | `simple` | 日志详细级别：simple(简略)/detailed(详细) |

**日志级别说明：**
- `simple`（简略）：只记录关键操作日志（初始化、开始下载、下载完成、PDF转换成功、PDF发送）
- `detailed`（详细）：记录所有操作日志（包括配置读取、临时目录、文件收集、清理等详细信息）

### 配置示例

```json
{
  "download_dir": "/home/user/jm_downloads",
  "keep_images": false,
  "keep_pdf": false,
  "max_file_size_mb": 100,
  "jm_client_impl": "html",
  "jm_retry_times": 5,
  "jm_cookies_avs": "",
  "proxy": "",
  "timeout": 60,
  "download_cache": true,
  "image_decode": true,
  "image_suffix": "",
  "concurrent_images": 30,
  "concurrent_photos": 8,
  "dir_rule": "Bd/Ptitle",
  "normalize_zh": "",
  "enable_jm_log": false,
  "send_progress_message": true,
  "log_level": "simple"
}
```

### 目录规则说明

`dir_rule` 配置项用于控制下载文件的目录结构，支持以下变量：

**Album (本子) 相关：**
- `Aid` - 本子ID
- `Atitle` - 本子标题
- `Aauthor` - 本子作者
- `Aname` - 本子名称

**Photo (章节) 相关：**
- `Pid` - 章节ID
- `Pindex` - 章节序号
- `Ptitle` - 章节标题
- `Pname` - 章节名称

**示例：**
- `Bd/Aid/Pindex` → 根目录/本子ID/章节序号/
- `Bd/Ptitle` → 根目录/章节标题/ (默认)
- `Bd/Aauthor/(JM{Aid}-{Pindex})-{Pname}` → 根目录/作者/(JM本子ID-章节号)-章节名/

## 依赖项

- `jmcomic` - 禁漫天堂爬虫库
- `img2pdf` - 图片转PDF库（自动处理所有图片格式）

## 注意事项

- ⚠️ 请遵守相关法律法规，合理使用本插件
- ⚠️ 请不要一次性下载过多漫画，减轻服务器压力
- ⚠️ 确保有足够的磁盘空间存储临时文件
- ⚠️ 大文件可能需要较长的上传时间

## 技术说明

### 下载流程

1. 用户发送 `jm <ID>` 命令
2. 验证漫画ID格式（必须是纯数字）
3. 创建临时目录
4. 使用 `jmcomic.download_album(comic_id)` 下载漫画
5. 自动处理域名和网络连接问题

### PDF转换流程

1. 递归收集下载目录中的所有图片文件
2. 按文件名自然排序确保页面顺序正确
3. 直接使用 img2pdf 进行无损转换
   - JPEG/JPEG2000 → 直接嵌入（无重新编码）
   - PNG（无透明度）→ 直接嵌入
   - 其他格式 → img2pdf 自动应用最优压缩算法
4. 生成 PDF 文件并发送给用户
5. 清理临时文件和 PDF 文件

### 图片处理

- img2pdf 自动处理所有图片格式，无需手动转换
- 支持的图片格式：jpg, jpeg, png, gif, bmp, webp, tif, tiff
- 对于 JPEG/PNG 等常见格式，直接嵌入 PDF（零损耗、高速度、低内存）
- 对于特殊格式（RGBA、透明背景等），img2pdf 自动应用最优算法处理

## 故障排除

### 缺少依赖库

```
❌ 缺少必要的依赖库，请先安装 jmcomic 和 img2pdf
```

解决方法：
```bash
pip install jmcomic img2pdf
```

### 无效的漫画ID

```
❌ 无效的漫画ID格式: xxx
```

解决方法：确保输入的是纯数字ID，例如 `/jm 123456`

### 下载失败

可能的原因：
- 网络连接问题
- 漫画ID不存在
- 服务器限制

请检查日志获取详细错误信息。

## 更新日志

### v1.0.0 (2025-12-03)
- 🎉 首次发布
- ✅ 基本的下载和转换功能
- ✅ 自动清理临时文件
- ✅ 特殊格式图片处理

## 许可证

本项目仅供学习交流使用，请勿用于非法用途。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) - 禁漫天堂爬虫
- [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) - 图片转PDF工具
- [AstrBot](https://github.com/Soulter/AstrBot) - 机器人框架
